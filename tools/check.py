"""Run unit checks; optionally validate an already-built full site."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FULL_SITE = {'site/actions.cjs', 'site/search_worker.cjs', 'text/full_display.cjs'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-site', action='store_true',
                        help='Also check existing dist, build/site-data and build/texts')
    args = parser.parse_args()
    node = shutil.which('node')
    if node is None:
        parser.error('Node.js is required for JavaScript checks')
    (ROOT / 'build').mkdir(exist_ok=True)
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
           'TMP': str(ROOT / 'build'), 'TEMP': str(ROOT / 'build'), 'TMPDIR': str(ROOT / 'build')}
    commands = [[sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-t', '.', '-v']]
    for path in sorted((ROOT / 'tests').rglob('*.cjs')):
        if path.relative_to(ROOT / 'tests').as_posix() in FULL_SITE and not args.full_site:
            continue
        commands.append([node, str(path.relative_to(ROOT))])
    for command in commands:
        print('CHECK ' + ' '.join(command[1:]), flush=True)
        subprocess.run(command, cwd=ROOT, env=env, check=True)
    print('Checks passed.' + (' Existing full site checked.' if args.full_site else
          ' Full data not checked; use --full-site after building it.'))


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode)
