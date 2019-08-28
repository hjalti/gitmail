import argparse
import requests
import subprocess
import shutil
import asyncio
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('targets', nargs='*')
parser.add_argument('--clean', action='store_true', help='Clean cache')
args = parser.parse_args()

TMPFILE = Path('/tmp/gitmail')

def main():
    if args.clean:
        print('Deleting cached repositories')
        shutil.rmtree(TMPFILE)
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
    curr = TMPFILE / target
    curr.mkdir(parents=True, exist_ok=True)

    repos = get_repos(target)
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

def get_repos(target):
    repos = requests.get(f'https://api.github.com/users/{target}/repos?per_page=100&sort=pushed').json()
    return [r for r in repos if not r['fork']]

if __name__ == '__main__':
    main()
