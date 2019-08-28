import argparse
import requests
import subprocess
import shutil
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

    emails = set()
    for t in args.targets:
        curr = TMPFILE / t
        curr.mkdir(parents=True, exist_ok=True)

        repos = get_repos(t)
        for r in repos:
            emails.update(scan_repo(r, curr))

    print()
    print('FOUND EMAILS')
    print(max(map(len, emails), default=12) * '-')
    print('\n'.join(sorted(emails)))

def scan_repo(repo, wd):
    git_dir = wd / f"{repo['name']}.git"
    if git_dir.exists():
        print(f"Repo '{repo['owner']['login']}/{repo['name']}' found in cache, cloning skipped")
    else:
        subprocess.run(['git', 'clone', '--bare', repo['html_url']], cwd=wd)
    res = subprocess.run(['git', '--git-dir', str(git_dir), 'log', "--pretty=%ae", '--all'], capture_output=True, text=True)
    return set(res.stdout.split())

def get_repos(target):
    repos = requests.get(f'https://api.github.com/users/{target}/repos?per_page=100&sort=pushed').json()
    return [r for r in repos if not r['fork']]

if __name__ == '__main__':
    main()
