"""Extract CH2–5 English defaults from original GML localization calls."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from tools.context.parser.calls import _calls
from tools.context.parser.gml_dialogue import FUNCTIONS, KEY_RE, as_string_literal
from tools.text.import_texts import disjoint, encode, language, load_json, sha

ROOT = Path(__file__).resolve().parents[2]
CHAPTERS = range(2, 6)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def scan(text, filename):
    records, unresolved = [], []
    for call in _calls(text):
        name, args = call['call'], call['args']
        if name not in FUNCTIONS:
            continue
        english_index, key_index = FUNCTIONS[name]
        if english_index is None or key_index is None or not args:
            continue
        key = as_string_literal(args[-1])
        if not key or not KEY_RE.fullmatch(key):
            continue
        record = {'key': key, 'file': filename, 'call': name,
                  'line': text.count('\n', 0, call['offset']) + 1}
        english = as_string_literal(args[english_index]) if len(args) > english_index else None
        if english is None:
            unresolved.append({**record, 'reason': 'English argument is not a string literal'})
        else:
            records.append({**record, 'english': english})
    return records, unresolved


def aggregate(records, choices):
    groups = defaultdict(list)
    for record in records:
        groups[record['key']].append(record)
    table, conflicts, applied = {}, [], []
    for key, candidates in sorted(groups.items()):
        if len({item['english'] for item in candidates}) == 1:
            table[key] = candidates[0]['english']
            continue
        choice = choices.get(key, {})
        variants = {sha(item['english'].encode('utf-8')) for item in candidates}
        hits = [item for item in candidates
                if all(item.get(field) == choice.get(field) for field in ('file', 'call'))
                and sha(item['english'].encode('utf-8')) == choice.get('english_sha256')
                and variants == set(choice.get('variants_sha256', []))]
        if not hits:
            conflicts.append({'key': key, 'candidates': candidates,
                              'reason': 'No matching reviewed choice'})
        else:
            table[key] = hits[0]['english']
            applied.append(key)
    return table, conflicts, applied


def extract(code, out, choices, report):
    code, out = Path(code).resolve(strict=True), Path(out).resolve()
    disjoint(code, out)
    if out.exists():
        raise ValueError(f'Refusing to overwrite output: {out}')
    pending = {}
    report['chapters'] = []
    for chapter in CHAPTERS:
        files = sorted((code/f'ch{chapter}').glob('*.gml'))
        if not files:
            raise ValueError(f'No GML files in {code / f"ch{chapter}"}')
        records, unresolved = [], []
        hashes = {}
        for path in files:
            raw = path.read_bytes()
            text = raw.decode('utf-8-sig')
            if 'DECOMPILER FAILED!' in text:
                raise ValueError(f'Failed decompilation: {path}')
            found, unknown = scan(text, path.name)
            records.extend(found)
            unresolved.extend(unknown)
            hashes[path.name] = sha(raw)
        table, conflicts, applied = aggregate(records, choices.get(str(chapter), {}))
        report['chapters'].append({'chapter': chapter, 'keys': len(table),
                                   'files_sha256': hashes, 'choices_applied': applied,
                                   'conflicts': conflicts, 'unresolved': unresolved})
        if not records and not unresolved:
            raise ValueError(f'No English localization calls found in chapter {chapter}')
        pending[chapter] = encode(table)
    if any(ch['conflicts'] or ch['unresolved'] for ch in report['chapters']):
        raise ValueError('Unresolved English calls or duplicate keys; inspect the local report before choosing a value')
    # Validate the exact bytes that will become import inputs; never normalize dialogue.
    for chapter, raw in pending.items():
        language(raw, f'ch{chapter}/lang_en.json')
    out.mkdir(parents=True)
    for chapter, raw in pending.items():
        target = out/f'ch{chapter}'
        target.mkdir()
        (target/'lang_en.json').write_bytes(raw)


def export_game(game, cli, code, stage):
    game, cli = Path(game).resolve(strict=True), Path(cli).resolve(strict=True)
    for source in (game, cli.parent):
        disjoint(source, stage)
    if cli.suffix.lower() not in ('.exe', '.dll'):
        raise ValueError('--umt must point to UndertaleModCli.exe or .dll')
    prefix = [str(cli)]
    if cli.suffix.lower() == '.dll':
        dotnet = shutil.which('dotnet')
        if not dotnet:
            raise ValueError('dotnet is required for the CLI DLL')
        prefix = [dotnet, str(cli)]
    packages = [game/f'chapter{ch}_windows/data.win' for ch in CHAPTERS]
    before = {str(path): digest(path) for path in packages}
    try:
        for chapter, package in zip(CHAPTERS, packages):
            print(f'Exporting CH{chapter} English source...', flush=True)
            env = {**os.environ, 'DR_ENGLISH_CODE': str(code/f'ch{chapter}')}
            with (stage/f'ch{chapter}.log').open('w', encoding='utf-8') as log:
                subprocess.run(prefix+['load', str(package), '-s', str(Path(__file__).with_name('export_english.csx'))],
                               env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    finally:
        if any(digest(path) != value for path, value in before.items()):
            raise ValueError('A game package changed during extraction; do not use this batch')
    return before


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--game', type=Path, help='Original game root containing chapterN_windows')
    source.add_argument('--code', type=Path, help='Already decompiled ch2..ch5 GML directories')
    parser.add_argument('--umt', type=Path, help='UndertaleModCli.exe or .dll (required with --game)')
    parser.add_argument('--out', type=Path, required=True, help='New folder for ch2..ch5/lang_en.json')
    parser.add_argument('--choices', type=Path, default=ROOT/'config/text/english-choices.json')
    args = parser.parse_args()
    if bool(args.game) != bool(args.umt):
        parser.error('Use --game with --umt, or --code alone')
    out = args.out.resolve()
    if out.exists():
        parser.error(f'Refusing to overwrite output: {out}')
    stage_root = ROOT/'local/english-extract'
    stage = stage_root/uuid.uuid4().hex
    if stage.resolve() != stage:
        parser.error('Local extraction output must not redirect through links')
    for source_path in (args.game or args.code, args.umt.parent if args.umt else args.code):
        disjoint(Path(source_path).resolve(strict=True), out)
        disjoint(Path(source_path).resolve(strict=True), stage)
    disjoint(stage, out)
    stage.mkdir(parents=True)
    report = {'schema': 1, 'status': 'extracting', 'out': str(out)}
    print(f'Local extraction report: {stage / "report.json"}', flush=True)
    try:
        choices_raw = args.choices.read_bytes()
        choices = load_json(choices_raw, str(args.choices))
        report['choices_sha256'] = sha(choices_raw)
        if args.game:
            code = stage/'code'
            report['packages_sha256'] = export_game(args.game, args.umt, code, stage)
        else:
            code = args.code
        report['code'] = str(code.resolve())
        extract(code, out, choices, report)
        report['status'] = 'complete'
        print(f'Wrote CH2–5 English tables to {out}. Copy CH1 English from the original lang folder.')
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        report.update(status='failed', error=str(exc))
        parser.exit(2, f'English extraction failed: {exc}\nSee {stage / "report.json"}\n')
    finally:
        (stage/'report.json').write_bytes(encode(report))


if __name__ == '__main__':
    main()
