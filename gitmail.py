import os
import argparse
import requests
import subprocess
import shutil
import asyncio
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('targets', nargs='*', help='Handles of either users or organizations')
parser.add_argument('--clean', action='store_true', help='Clean cache')
parser.add_argument('--include-members', action='store_true', help='Include org members')
parser.add_argument('--cache-dir', default=Path('/tmp/gitmail'), help='Directory used for cache. Default: %(default)s', type=Path)
parser.add_argument('--github-token', help='Github OAuth token used when making requests to github. Can also be set with the environment variable GITMAIL_TOKEN.')
parser.add_argument('--include-forks', action='store_true', help='Also search forked repositories')
args = parser.parse_args()

def github_token():
    if args.github_token:
        return args.github_token
    return os.environ.get('GITMAIL_TOKEN')

def main():
    if args.clean:
        print('Deleting cached repositories')
        shutil.rmtree(args.cache_dir)
        print('Done')
        return

    all_emails = set()
    for t in args.targets:
        print(f'Scanning {t}')
        all_emails.update(asyncio.run(process_target(t)))

    if len(args.targets) > 1:
        print(f'All emails')
        print(max(map(len, all_emails), default=12) * '-')
        print('\n'.join(sorted(all_emails)))
        print()

async def process_target(target):
    emails = set()
    curr = args.cache_dir / target
    curr.mkdir(parents=True, exist_ok=True)

    repos = get_target(target)
    if args.include_members:
        for m in get_org_members(target):
            repos.extend(get_user_repos(m))
    results = await asyncio.gather(*[scan_repo(r, curr) for r in repos])
    for r in results:
        emails.update(r)

    print()
    print(f'Emails for {target}')
    print(max(map(len, emails), default=12) * '-')
    print('\n'.join(sorted(emails)))
    print()

    return emails


async def scan_repo(repo, wd):
    git_dir = wd / f"{repo['name']}.git"
    if git_dir.exists():
        print(f"Repo '{repo['owner']['login']}/{repo['name']}' found in cache, cloning skipped")
    else:
        print(f"Cloning '{repo['owner']['login']}/{repo['name']}'")
        proc = await asyncio.create_subprocess_exec('git', 'clone', '--bare', repo['html_url'], cwd=wd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
    res = subprocess.run(['git', '--git-dir', str(git_dir), 'log', "--pretty=%ae", '--all'], capture_output=True, text=True)
    return set(res.stdout.split())

def github_request(url):
    token = github_token()
    headers = token and {'Authorization': f'token {token}'} or {}
    return requests.get(url, headers=headers).json()

def get_target(target):
    if target.startswith('https://') or target.startswith('git@'):
        return get_repo(target)
    return get_user_repos(target)

def get_repo(target):
    parts = target.split('/')
    if len(parts) < 2:
        print('Invalid repository identifier specified')
        return []
    user, repo = parts[-2:]
    if repo.endswith('.git'):
        repo = repo[:-4]
    return [github_request(f'https://api.github.com/repos/{user}/{repo}')]

def get_user_repos(target):
    repos = github_request(f'https://api.github.com/users/{target}/repos?per_page=100&sort=pushed')
    return args.include_forks and repos or [r for r in repos if not r['fork']]

def get_org_members(target):
    users = github_request(f'https://api.github.com/orgs/{target}/members?per_page=100')
    return [u['login'] for u in users]

if __name__ == '__main__':
    main()
