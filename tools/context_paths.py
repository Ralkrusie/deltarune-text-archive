"""Explicit, read-only inputs for current context generators."""
import argparse
from pathlib import Path
from import_texts import load_json, sha

ROOT = Path(__file__).resolve().parents[1]

def validate_text_snapshot(texts):
    """Reject altered intermediates before binding context to their import manifest."""
    manifest = load_json((texts/'manifest.json').read_bytes(), 'text manifest')
    if (not isinstance(manifest, dict) or manifest.get('schema') != 1 or
            manifest.get('kind') != 'unified-language-folder'):
        raise ValueError('Unsupported text manifest; rerun text import')
    records = manifest.get('outputs')
    expected = {f'trilingual_chapter{ch}.json' for ch in range(1, 6)}
    if (not isinstance(records, list) or len(records) != 5 or
            any(not isinstance(r, dict) or not isinstance(r.get('path'), str) for r in records) or
            {r['path'] for r in records} != expected):
        raise ValueError('Text manifest must list each chapter output exactly once')
    for record in records:
        name = record['path']
        raw = (texts/name).read_bytes()
        if (record.get('sha256') != sha(raw) or type(record.get('bytes')) is not int or
                record['bytes'] != len(raw)):
            raise ValueError(f'Text input digest mismatch: {name}; rerun text import')

def paths(code, texts, out):
    code = Path(code).resolve(strict=True)
    texts = Path(texts).resolve(strict=True)
    out = Path(out).resolve()
    for source in (code, texts):
        if out == source or out.is_relative_to(source) or source.is_relative_to(out):
            raise ValueError('Output must not overlap source or text inputs')
    for ch in range(1, 6):
        if not (code/f'ch{ch}').is_dir() or not any((code/f'ch{ch}').glob('*.gml')):
            raise ValueError(f'Missing GML chapter directory: ch{ch}')
        if not (texts/f'trilingual_chapter{ch}.json').is_file():
            raise ValueError(f'Missing text chapter: {ch}')
    if not (texts/'manifest.json').is_file():
        raise ValueError('Missing text manifest')
    validate_text_snapshot(texts)
    return code, texts, out

def parser(description, default_out):
    p = argparse.ArgumentParser(description=description)
    p.add_argument('--code', type=Path, required=True, help='GML directory containing ch1..ch5')
    p.add_argument('--texts', type=Path, default=ROOT/'build/texts')
    p.add_argument('--out', type=Path, default=ROOT/default_out)
    return p
