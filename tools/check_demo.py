"""Run portable project checks and build the example; optionally check an existing full site."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
from build_demo import build_demo

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-site', action='store_true',
                        help='Also check existing dist and build/site-data against full build/texts')
    args = parser.parse_args()
    node = shutil.which('node')
    if node is None:
        raise SystemExit('Node.js is required for the JavaScript checks. Install it and retry.')
    (ROOT / 'build').mkdir(exist_ok=True)
    # Keep temporary test fixtures inside the ignored workspace, including in restricted shells.
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
           'TMP': str(ROOT / 'build'), 'TEMP': str(ROOT / 'build'), 'TMPDIR': str(ROOT / 'build')}
    commands = [[sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v']]
    commands.extend([node, f'tests/{name}.cjs'] for name in (
        'text_display', 'ui_model', 'query', 'startup', 'worker_lifecycle', 'context',
        'soul_motion', 'soul_yellow', 'soul_audio', 'soul_switch',
        'soul_extra', 'soul_extra_audio', 'soul_purple',
    ))
    for command in commands:
        print('CHECK ' + ' '.join(command[1:]), flush=True)
        subprocess.run(command, cwd=ROOT, env=env, check=True)
    site = build_demo()
    subprocess.run([node, 'tests/demo_worker.cjs', str(site)], cwd=ROOT, env=env, check=True)
    if args.full_site:
        for file in ('tests/actions.cjs', 'tests/search_worker.cjs', 'tools/check_display.cjs'):
            print('CHECK ' + file, flush=True)
            subprocess.run([node, file], cwd=ROOT, env=env, check=True)
    print('Project checks passed. ' + ('Existing full site checked.' if args.full_site else
          'Full game data not checked; use --full-site after building it.'))


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode)
