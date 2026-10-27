"""Freeze the participant UI and assemble a portable ZIP beside a verified kit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


def package(kit, out, dependencies=None):
    project = Path(__file__).resolve().parents[2]
    kit, out = Path(kit).resolve(strict=True), Path(out).absolute()
    if out.exists():
        raise ValueError('Choose a new package directory')
    if not (kit / 'kit.json').is_file():
        raise ValueError('Missing kit.json')
    out.mkdir(parents=True)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [str(dependencies.resolve()) if dependencies else '', str(project)])))
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
               '--name', 'DialogueCapture', '--distpath', str(out / 'app'), '--workpath', str(out / 'freeze'),
               '--specpath', str(out), '--paths', str(project),
               '--add-data', str(project / 'tools/runtime/legacy/text-style-sites.json') + ';tools/runtime/legacy',
               '--add-data', str(project / 'tools/runtime/legacy/smallface-spec.json') + ';tools/runtime/legacy',
               str(project / 'tools/runtime/participant.py')]
    with (out / 'build.log').open('wb') as log:
        subprocess.run(command, cwd=project, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    release = out / 'app/DialogueCapture'
    shutil.copytree(kit, release / 'kit')
    for source, target in [('docs/build/RUNTIME_PARTICIPANTS.md', '使用说明.md'), ('LICENSE', 'LICENSE.txt')]:
        shutil.copy2(project / source, release / target)
    # Ship the small project-owned participant sources alongside the frozen executable.
    code = release / 'source/tools/runtime'
    code.mkdir(parents=True)
    for path in (project / 'tools/runtime').rglob('*'):
        if path.is_file() and path.suffix in {'.py', '.json', '.gml', '.csx', '.html', '.js', '.css'} and '__pycache__' not in path.parts:
            target = code / path.relative_to(project / 'tools/runtime')
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, target)
    (release / 'source/tools/__init__.py').write_text('', encoding='utf-8')
    for license_file in (Path(sys.base_prefix) / 'LICENSE.txt', Path(sys.base_prefix) / 'Lib/site-packages/PyInstaller/COPYING.txt'):
        if license_file.exists():
            shutil.copy2(license_file, release / ('Python-' + license_file.name))
    if dependencies:
        for path in (dependencies / 'PyInstaller').glob('COPYING*'):
            shutil.copy2(path, release / ('PyInstaller-' + path.name))
    manifest = {p.relative_to(release).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in release.rglob('*') if p.is_file()}
    (out / 'release-files.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    revision = json.loads((kit / 'kit.json').read_text(encoding='utf-8'))['revision']
    archive = out / f'DialogueCapture-r{revision}-local.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(release.rglob('*')):
            if path.is_file():
                zipped.write(path, 'DialogueCapture/' + path.relative_to(release).as_posix())
    return {'zip': str(archive), 'bytes': archive.stat().st_size, 'files': len(manifest),
            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--dependencies', type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.kit, args.out, args.dependencies), ensure_ascii=False, indent=2))
