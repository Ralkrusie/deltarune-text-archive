"""Export the website's game assets and Chinese main font with UndertaleModCli.

Game packages are read-only. Export into local/asset-build first; install only
manifest-listed files after validation, preserving replaced files in that run.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def command(cli):
    cli = Path(cli).resolve(strict=True)
    if not cli.is_file() or cli.suffix.lower() not in ('.exe', '.dll'):
        raise ValueError('--umt must be UndertaleModCli.exe or UndertaleModCli.dll')
    if cli.suffix.lower() == '.dll':
        dotnet = shutil.which('dotnet')
        if not dotnet:
            raise ValueError('dotnet is required to run UndertaleModCli.dll')
        return [dotnet, str(cli)]
    return [str(cli)]


def jobs(game, zh_game):
    plan = []
    for ch, scripts in (
        (1, ['export_brand_assets.csx']),
        (2, ['export_book_asset.csx', 'export_yellow_soul.csx', 'export_soul_switch.csx']),
        (4, ['export_soul_assets.csx', 'export_extra_souls.csx']),
        (5, ['export_soul_assets.csx', 'export_extra_souls.csx']),
    ):
        plan.append((f'en-ch{ch}', game/f'chapter{ch}_windows/data.win', ch, scripts))
    plan.append(('zh-main', zh_game/'chapter1_windows/data.win', 1, ['export_main_font.csx']))
    for label, package, _, _ in plan:
        if not package.is_file():
            raise ValueError(f'Missing {label} game package: {package}')
    sound = game/'chapter2_windows/snd_great_shine.ogg'
    if not sound.is_file():
        raise ValueError(f'Missing external sound: {sound}')
    return plan, sound


def build(game, zh_game, cli):
    from tools.text.import_texts import disjoint
    from tools.assets.site_assets import asset_payload
    for module in ('PIL', 'fontTools', 'brotli'):
        try:
            importlib.import_module(module)
        except ImportError as exc:
            raise ValueError('Install asset dependencies: python -m pip install -r requirements-assets.txt') from exc
    game, zh_game = Path(game).resolve(strict=True), Path(zh_game).resolve(strict=True)
    if game == zh_game:
        raise ValueError('Provide separate original and Chinese-patched game directories')
    prefix = command(cli)
    plan, sound = jobs(game, zh_game)
    target = ROOT/'local/ui-assets'
    archive = ROOT/'local/asset-build'
    for output in (target, archive):
        if output.resolve() != output:
            raise ValueError('Asset output must not redirect through links')
        for source in (game, zh_game, Path(cli).resolve().parent):
            disjoint(output.resolve(), source)
    archive.mkdir(parents=True, exist_ok=True)
    stage = archive/uuid.uuid4().hex
    stage.mkdir()
    generated = stage/'local/ui-assets'
    generated.mkdir(parents=True)
    fonts = stage/'font-input'
    inputs = {str(p): digest(p) for p in [*(p for _, p, _, _ in plan), sound]}
    record = {'schema': 1, 'status': 'building', 'inputs': inputs,
              'umt': {'path': str(Path(cli).resolve()), 'sha256': digest(cli)},
              'scripts': {name: digest(ROOT/'tools/assets/umt'/name) for _, _, _, names in plan for name in names},
              'dependencies': {name: importlib.import_module(name).__version__ for name in ('PIL', 'fontTools', 'brotli')}}
    def save():
        (stage/'report.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    save()
    print(f'Asset build evidence: {stage}', flush=True)
    try:
        for label, package, ch, scripts in plan:
            print('Exporting '+label+' ...', flush=True)
            env = {**os.environ,
                   'DR_UI_ASSETS': str(generated), 'DR_UI_SOUL_CHAPTER': str(ch),
                   'DR_YELLOW_ASSETS': str(generated/'yellow'),
                   'DR_SOUL_SWITCH_SOURCE': str(game/'chapter2_windows'),
                   'DR_SOUL_SWITCH_ASSETS': str(generated),
                   'DR_EXTRA_SOUL_CHAPTER': str(ch), 'DR_EXTRA_SOUL_ASSETS': str(generated/'extra'),
                   'DR_MAIN_FONT_ASSETS': str(fonts)}
            args = prefix+['load', str(package)]
            for name in scripts:
                args.extend(['-s', str(ROOT/'tools/assets/umt'/name)])
            with (stage/(label+'.log')).open('w', encoding='utf-8') as log:
                result = subprocess.run(args, env=env, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise ValueError(f'UMT failed: see {stage/(label+".log")}')
        from .font_woff import build_font, grid_for
        record['font'] = build_font(str(fonts/'fnt_main.png'), str(fonts/'glyphs_fnt_main.csv'),
                                   str(generated/'fnt_main.woff2'), 'zh', grid=grid_for('fnt_main', 'zh'))
        if not record['font']:
            raise ValueError('Font conversion produced no glyphs')
        from fontTools.ttLib import TTFont
        with TTFont(generated/'fnt_main.woff2') as font:
            if not set(map(ord, '台词库')).issubset(font.getBestCmap()):
                raise ValueError('Chinese main font is missing title glyphs; check --zh-game')
        # Validate the same whitelist as the website before touching live assets.
        (stage/'config').mkdir()
        shutil.copy2(ROOT/'config/site-assets.json', stage/'config/site-assets.json')
        shutil.copytree(ROOT/'web/assets', stage/'web/assets')
        asset_payload(stage)
        if any(digest(p) != expected for p, expected in inputs.items()):
            raise ValueError('A game input changed during export; live assets were not updated')
        manifest = json.loads((ROOT/'config/site-assets.json').read_text(encoding='utf-8'))
        files = [item['source'] for item in manifest['files'] if item['source'].startswith('local/ui-assets/')]
        record['outputs'] = {name: digest(stage/name) for name in files}
        record['replaced'] = []
        for name in files:
            dst = ROOT/name
            if dst.resolve() != dst or (dst.exists() and not dst.is_file()):
                raise ValueError(f'Unsafe live asset destination: {dst}')
        # Back up all changed files before replacing any of them.
        for name in files:
            dst = ROOT/name
            if dst.exists() and digest(dst) != record['outputs'][name]:
                backup = stage/'previous'/name
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, backup)
                record['replaced'].append(name)
        record['status'] = 'validated'
        save()
        for name in files:
            dst = ROOT/name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stage/name, dst)
        record['status'] = 'complete'
        record['game_inputs_unchanged'] = True
        save()
        (target/'asset-build.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(f'Installed {len(files)} game assets; bundled GIF uses web/assets. Previous files: {stage/"previous"}', flush=True)
        return stage
    except Exception as exc:
        record['status'] = 'failed'
        record['error'] = str(exc)
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True, help='Original game root containing chapterN_windows')
    parser.add_argument('--zh-game', type=Path, required=True, help='Chinese-patched game root; CH1 supplies main font')
    parser.add_argument('--umt', type=Path, required=True, help='UndertaleModCli.exe or .dll')
    parser.add_argument('--build-site', action='store_true', help='Also import input/ and assemble dist after exporting assets')
    args = parser.parse_args()
    build(args.game, args.zh_game, args.umt)
    if args.build_site:
        from tools.text.import_texts import run
        from tools.site.build_site import assemble
        run(ROOT/'input', ROOT/'build/texts')
        assemble()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit('Asset build failed: '+str(exc))
