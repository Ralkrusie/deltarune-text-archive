"""Build minimal chapter data: original strings with within-chapter dictionary sharing."""
import argparse
import json
import re
from pathlib import Path
from import_texts import CHAPTERS, FILES, disjoint, load_json, sha


def compact(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')


def build(texts, out, sources=None):
    texts, out = Path(texts).resolve(strict=True), Path(out).resolve()
    disjoint(texts, out)
    manifest_raw = (texts / 'manifest.json').read_bytes()
    source_manifest = load_json(manifest_raw, 'manifest.json')
    expected = {r['path']: r['sha256'] for r in source_manifest['outputs']}
    pending, chapters = [], []
    for ch in CHAPTERS:
        filename = f'trilingual_chapter{ch}.json'
        raw = (texts / filename).read_bytes()
        if sha(raw) != expected[filename]:
            raise ValueError(f'Input digest mismatch: {filename}; rerun text import')
        data = load_json(raw, filename)
        if data.get('chapter') != ch or data.get('schema') != 1:
            raise ValueError(f'Unexpected chapter schema: {filename}')
        strings, indices, rows, keys = [], {}, [], set()
        for line in data['lines']:
            key = line['key']
            if key in keys or not isinstance(key, str):
                raise ValueError(f'Invalid/duplicate key: {filename}/{key}')
            keys.add(key)
            row = [key]
            for field in FILES:
                value = line[field]
                if value is None:
                    row.append(None)
                elif isinstance(value, str):
                    if value not in indices:
                        indices[value] = len(strings)
                        strings.append(value)
                    row.append(indices[value])
                else:
                    raise ValueError(f'Invalid text: {filename}/{key}/{field}')
            rows.append(row)
        links = {'files': [], 'by_key': {}}
        if sources is not None:
            links = load_json((Path(sources) / f'ch{ch}.json').read_bytes(), 'source links')
            if links.get('chapter') != ch or links.get('schema') != 1 or links.get('text_manifest_sha256') != sha(manifest_raw):
                raise ValueError('Source links are stale; rerun prepare_source_links.py')
            if any(not re.fullmatch(r'gml_[A-Za-z0-9_]+\.gml', f) for f in links['files']):
                raise ValueError('Invalid source filename')
        for row in rows:
            locations = links['by_key'].get(row[0], [])
            for file_id, line in locations:
                if type(file_id) is not int or not 0 <= file_id < len(links['files']) or type(line) is not int or line < 1:
                    raise ValueError('Invalid source location')
            row.append(locations)
        encoded = compact({'source_files': links['files'], 'schema': 1, 'chapter': ch, 'languages': list(FILES), 'strings': strings, 'rows': rows})
        name = f'ch{ch}.json'
        pending.append((name, encoded))
        chapters.append({'chapter': ch, 'path': name, 'rows': len(rows), 'strings': len(strings),
                         'bytes': len(encoded), 'sha256': sha(encoded)})
    manifest = {'schema': 1, 'kind': 'viewer-site-data', 'languages': list(FILES),
                'source_manifest_sha256': sha(manifest_raw), 'chapters': chapters,
                'total_rows': sum(r['rows'] for r in chapters)}
    pending.append(('manifest.json', compact(manifest)))
    for name, _ in pending:
        path = out / name
        if not path.resolve().is_relative_to(out) or (path.exists() and not path.is_file()):
            raise ValueError(f'Unsafe destination: {path}')
    out.mkdir(parents=True, exist_ok=True)
    for name, raw in pending:
        (out / name).write_bytes(raw)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--texts', type=Path, default=Path('build/texts'))
    parser.add_argument('--out', type=Path, default=Path('build/site-data'))
    parser.add_argument('--sources', type=Path, help='Optional verified source-location directory')
    args = parser.parse_args()
    try:
        result = build(args.texts, args.out, args.sources)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'Build error: {exc}\n')
    print(f"Built {result['total_rows']} rows; chapter data {sum(r['bytes'] for r in result['chapters']) / 1024**2:.2f} MiB")
