"""Publish the verified dist snapshot to origin/gh-pages without switching branches."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def verified_payload(root):
    dist = root / 'dist'
    report = json.loads((root / 'build/site-build.json').read_text(encoding='utf-8'))
    payload = {}
    for item in report['files']:
        name = item['path']
        path = PurePosixPath(name)
        if (not name or '\\' in name or ':' in name or path.is_absolute()
                or any(part in ('.', '..', '.git') for part in name.split('/'))
                or path.parts[0] in ('input', 'local', 'build') or name in payload):
            raise ValueError(f'Unsafe or duplicate publication path: {name}')
        source = dist / name
        if source.is_symlink() or not source.resolve().is_relative_to(dist.resolve()):
            raise ValueError(f'Publication file escapes dist: {name}')
        raw = source.read_bytes()
        if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError(f'Build changed; rebuild and check before publishing: {name}')
        payload[name] = raw
    actual = {p.relative_to(dist).as_posix() for p in dist.rglob('*') if p.is_file()}
    if actual != set(payload) or not {'index.html', '.nojekyll'} <= set(payload):
        raise ValueError('dist does not match the complete publication manifest')
    return payload


def git(*args, cwd=ROOT, input=None):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    return subprocess.run(['git', '-c', 'credential.interactive=false', *args],
                          cwd=cwd, env=env, input=input, text=True,
                          stdout=subprocess.PIPE, check=True).stdout.strip()


def publish():
    if git('branch', '--show-current') != 'main' or git('status', '--porcelain'):
        raise ValueError('Commit source changes on a clean main branch before publishing')
    revision = git('rev-parse', 'HEAD')
    remote = git('remote', 'get-url', 'origin')
    upstream = git('ls-remote', '--heads', 'origin', 'refs/heads/main').split()
    if not upstream or upstream[0] != revision:
        raise ValueError('Push main and reconcile remote changes before publishing')
    payload = verified_payload(ROOT)
    author = {key: git('config', '--get', f'user.{key}') for key in ('name', 'email')}
    # A fresh temporary repository keeps the working branch and all local inputs untouched.
    with tempfile.TemporaryDirectory(prefix='pages-', dir=ROOT / 'build') as folder:
        stage = Path(folder).resolve()
        if not stage.is_relative_to((ROOT / 'build').resolve()):
            raise ValueError('Publication staging directory must stay under build')
        git('init', '--initial-branch=gh-pages', cwd=stage)
        git('config', 'core.autocrlf', 'false', cwd=stage)
        for key, value in author.items():
            git('config', f'user.{key}', value, cwd=stage)
        git('remote', 'add', 'origin', remote, cwd=stage)
        previous = git('ls-remote', '--heads', 'origin', 'refs/heads/gh-pages', cwd=stage)
        parents = []
        if previous:
            git('fetch', '--depth=1', 'origin', 'gh-pages', cwd=stage)
            parents = ['-p', git('rev-parse', 'FETCH_HEAD', cwd=stage)]
        for name, raw in payload.items():
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        git('add', '--all', cwd=stage)
        tree = git('write-tree', cwd=stage)
        if parents and tree == git('rev-parse', 'FETCH_HEAD^{tree}', cwd=stage):
            print('The published branch already contains this exact site.')
            return
        commit = git('commit-tree', tree, *parents, cwd=stage,
                     input=f'Publish site from main {revision}\n')
        # Ordinary fast-forward push: concurrent publication is rejected, never forced.
        git('push', 'origin', f'{commit}:refs/heads/gh-pages', cwd=stage)
        print(f'Published {len(payload)} files from {revision} as {commit}')


if __name__ == '__main__':
    try:
        publish()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f'Publication failed: {exc}')
