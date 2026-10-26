"""Build chapter text inventories from one ch1..ch5 language folder (Python 3.10+)."""
import argparse
import hashlib
import json
from pathlib import Path

FILES = {
    'en': 'lang_en.json',
    'ja': 'lang_ja.json',
    'zh_default': 'lang_zh.json',
    'zh_names': 'lang_zh_names.json',
    'zh_recruitable': 'lang_zh_recruitable.json',
}
CHAPTERS = range(1, 6)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key!r}')
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError(f'invalid JSON constant: {value}')


def load_json(raw, label):
    try:
        return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object,
                          parse_constant=invalid_constant)
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f'{label}: {exc}') from exc


def language(raw, label):
    data = load_json(raw, label)
    if not isinstance(data, dict):
        raise ValueError(f'{label}: expected a JSON object mapping keys to strings')
    metadata = {k: v for k, v in data.items() if k == 'date'}
    texts = {k: v for k, v in data.items() if k != 'date'}
    for key, value in texts.items():
        if not key or not isinstance(value, str):
            raise ValueError(f'{label}: {key!r} must have a nonempty key and a string value; '
                             'omit missing translations instead of using null')
    return texts, metadata


def chapter_payload(chapter, tables):
    keys = sorted(set().union(*(set(t) for t in tables.values())))
    rows = []
    for key in keys:
        row = {'key': key, **{field: tables[field].get(key) for field in FILES}}
        missing = sorted(field for field in FILES if key not in tables[field])
        zh = {row[f] for f in FILES if f.startswith('zh_') and row[f] is not None}
        row.update(missing=missing,
                   status='missing_' + '_'.join(missing) if missing else 'complete',
                   zh_variant='differs' if len(zh) > 1 else 'same')
        rows.append(row)
    stats = {
        'total': len(rows),
        'complete': sum(not r['missing'] for r in rows),
        'missing_by_language': {f: sum(f in r['missing'] for r in rows) for f in FILES},
        'zh_differs': sum(r['zh_variant'] == 'differs' for r in rows),
    }
    return {'schema': 1, 'chapter': chapter, 'stats': stats, 'lines': rows}


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def disjoint(input_dir, output_dir):
    if input_dir.is_relative_to(output_dir) or output_dir.is_relative_to(input_dir):
        raise ValueError('Input and output directories must be separate, not nested')


def run(input_dir, output_dir):
    input_dir = Path(input_dir).resolve(strict=True)
    output_dir = Path(output_dir).resolve()
    disjoint(input_dir, output_dir)
    prepared, inputs = [], []
    # Validate all 25 files before touching an existing result.
    for ch in CHAPTERS:
        tables = {}
        for field, filename in FILES.items():
            relative = f'ch{ch}/{filename}'
            path = input_dir / relative
            raw = path.read_bytes()
            tables[field], metadata = language(raw, relative)
            inputs.append({'path': relative, 'sha256': sha(raw), 'bytes': len(raw),
                           'entries': len(tables[field]), 'metadata': metadata})
        payload = chapter_payload(ch, tables)
        prepared.append((f'trilingual_chapter{ch}.json', encode(payload), payload['stats']))
    manifest = {
        'schema': 1,
        'kind': 'unified-language-folder',
        'inputs': inputs,
        'outputs': [{'path': name, 'sha256': sha(raw), 'bytes': len(raw), 'stats': stats}
                    for name, raw, stats in prepared],
        'total_rows': sum(stats['total'] for _, _, stats in prepared),
    }
    prepared.append(('manifest.json', encode(manifest), None))
    for name, _, _ in prepared:
        target = output_dir / name
        resolved = target.resolve()
        if not resolved.is_relative_to(output_dir) or resolved.is_relative_to(input_dir):
            raise ValueError(f'Unsafe output destination: {target}')
        if target.exists() and not target.is_file():
            raise ValueError(f'Output destination is not a file: {target}')
    for record in inputs:
        if sha((input_dir / record['path']).read_bytes()) != record['sha256']:
            raise ValueError(f"Input changed during import: {record['path']}")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, raw, _ in prepared:
        (output_dir / name).write_bytes(raw)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Folder containing ch1..ch5')
    parser.add_argument('--out', type=Path, default=Path('build/texts'))
    args = parser.parse_args()
    try:
        result = run(args.input, args.out)
    except (OSError, ValueError) as exc:
        parser.exit(2, f'Input error: {exc}\n')
    print(f"Imported {result['total_rows']} chapter/key rows from 25 files into {args.out}")


if __name__ == '__main__':
    main()
