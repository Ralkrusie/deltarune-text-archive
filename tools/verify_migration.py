"""Audit migration against saved legacy rows; does not claim to re-extract game code."""
import argparse
from pathlib import Path
import shutil
import uuid
from contextlib import contextmanager

from import_texts import CHAPTERS, FILES, disjoint, encode, language, load_json, run, sha


@contextmanager
def audit_temp(out):
    path = out / ('migration-' + uuid.uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        if not path.resolve().is_relative_to(out) or path.resolve() == out:
            raise ValueError('Audit cleanup escaped output')
        shutil.rmtree(path)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_rows(path, chapter):
    raw = path.read_bytes()
    payload = load_json(raw, str(path))
    require(payload.get('chapter') == chapter, f'Chapter mismatch: {path}')
    rows = payload['lines']
    index = {r['key']: r for r in rows}
    require(len(index) == len(rows), f'Duplicate output keys: {path}')
    return index, sha(raw)


def audit(legacy_dir, input_dir, texts_dir, out):
    legacy_dir, input_dir, texts_dir = [Path(p).resolve(strict=True) for p in (legacy_dir, input_dir, texts_dir)]
    out = Path(out).resolve()
    for source in (legacy_dir, input_dir, texts_dir):
        disjoint(source, out)
    out.mkdir(parents=True, exist_ok=True)
    tracked = {}
    chapters, differences, missing_examples = [], [], []
    # Temporary old-language fixture is reconstructed from saved rows, NOT the unavailable old installation.
    with audit_temp(out) as directory:
        temp = Path(directory).resolve()
        require(temp.is_relative_to(out), 'Temporary directory escaped audit output')
        baseline_input, baseline_output = temp / 'input', temp / 'output'
        old_by_ch = {}
        for ch in CHAPTERS:
            path = legacy_dir / f'trilingual_chapter{ch}.json'
            old, tracked[path] = read_rows(path, ch)
            old_by_ch[ch] = old
            for field, filename in FILES.items():
                p = baseline_input / f'ch{ch}' / filename
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(encode({key: r[field] for key, r in old.items() if r.get(field) is not None}))
        baseline_manifest = run(baseline_input, baseline_output)
        for ch in CHAPTERS:
            old = old_by_ch[ch]
            baseline, _ = read_rows(baseline_output / f'trilingual_chapter{ch}.json', ch)
            require(old.keys() == baseline.keys(), f'Baseline key mismatch ch{ch}')
            for key in old:
                for field in (*FILES, 'status', 'zh_variant'):
                    require(old[key].get(field) == baseline[key].get(field), f'Baseline mismatch ch{ch}/{key}/{field}')
            path = texts_dir / f'trilingual_chapter{ch}.json'
            current, tracked[path] = read_rows(path, ch)
            tables = {}
            for field, filename in FILES.items():
                source = input_dir / f'ch{ch}' / filename
                raw = source.read_bytes()
                tracked[source] = sha(raw)
                tables[field], _ = language(raw, str(source))
                projection = {key: r[field] for key, r in current.items() if r[field] is not None}
                require(projection == tables[field], f'Current input projection mismatch ch{ch}/{field}')
            require(set(current) == set().union(*(set(t) for t in tables.values())), f'Current key union mismatch ch{ch}')
            added, removed = sorted(current.keys() - old.keys()), sorted(old.keys() - current.keys())
            counts = {f: 0 for f in FILES}
            changed_keys = 0
            for key in sorted(old.keys() & current.keys()):
                changes = {}
                for field in FILES:
                    if old[key].get(field) != current[key].get(field):
                        changes[field] = {'old': old[key].get(field), 'new': current[key].get(field)}
                        counts[field] += 1
                if changes:
                    changed_keys += 1
                    differences.append({'chapter': ch, 'key': key, 'changes': changes})
            for kind, keys, table in [('added', added, current), ('removed', removed, old)]:
                for key in keys:
                    differences.append({'chapter': ch, 'key': key, 'kind': kind, 'row': table[key]})
            missing_examples.extend({'chapter': ch, 'key': key, 'missing': r['missing'],
                                     'texts': {f: r[f] for f in FILES}}
                                    for key, r in list((k, r) for k, r in current.items() if r['missing'])[:1])
            chapters.append({'chapter': ch, 'rows': len(current), 'baseline_equal': True,
                             'current_matches_inputs': True, 'added_keys': len(added), 'removed_keys': len(removed),
                             'changed_keys': changed_keys, 'changed_fields': counts})
        # Verify saved output bytes match a fresh import, including manifest; no extra persistent copy.
        repeat = temp / 'repeat'
        run(input_dir, repeat)
        for path in repeat.iterdir():
            target = texts_dir / path.name
            require(path.read_bytes() == target.read_bytes(), f'Reproducibility mismatch: {path.name}')
    require(all(sha(p.read_bytes()) == digest for p, digest in tracked.items()), 'Source changed during audit')
    result = {
        'schema': 1, 'baseline_method': 'Language files reconstructed from saved legacy rows; old installation unavailable.',
        'baseline_rows': baseline_manifest['total_rows'], 'chapters': chapters,
        'current_reproducible': True, 'audited_files_unchanged': True,
        'source_hashes': [{'path': str(p), 'sha256': digest} for p, digest in tracked.items()],
        'differences': differences, 'missing_examples': missing_examples,
    }
    (out / 'comparison.json').write_bytes(encode(result))
    lines = ['# 第一步：统一输入对账', '',
             '旧安装目录不可用：旧基线由保留的三语产物还原语言文件后走新入口验证，不代表重新从旧游戏提取。', '',
             '| 章 | 总条目 | 新增 key | 删除 key | 英文变化 | 日文变化 | 中文默认 | 中文 names | 中文 recruitable |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in chapters:
        counts = r['changed_fields']
        values = [r['chapter'], r['rows'], r['added_keys'], r['removed_keys'], *(counts[f] for f in FILES)]
        lines.append('| ' + ' | '.join(map(str, values)) + ' |')
    lines += ['', f"旧基线 {result['baseline_rows']} 条的 key、五档原文、status、zh_variant 全部一致。",
              '新版各语言投影与 25 份输入逐项一致；重复构建字节一致；检查过的输入与旧产物 SHA-256 未变。', '',
              '以下列出所有正文变化；完整结构化证据见 [comparison.json](comparison.json)。', '']
    for diff in differences:
        lines += [f"## 第 {diff['chapter']} 章 · {diff['key']}", '']
        for field, pair in diff.get('changes', {}).items():
            lines += [f'**{field}**', '', '旧：', '```text', pair['old'] if pair['old'] is not None else '(缺失)',
                      '```', '新：', '```text', pair['new'] if pair['new'] is not None else '(缺失)', '```', '']
        if 'kind' in diff:
            lines += [diff['kind'], '']
    (out / 'review.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-dir', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--texts', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('build/migration'))
    args = parser.parse_args()
    try:
        result = audit(args.legacy_dir, args.input, args.texts, args.out)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'Audit failed: {exc}\n')
    print(f"Baseline: {result['baseline_rows']} rows equal; current input matches; reproducibility verified.")
    for chapter in result['chapters']:
        print(chapter)
