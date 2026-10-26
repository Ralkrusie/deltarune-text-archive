"""Optional copier: prepare the unified folder without changing original files."""
import argparse
from pathlib import Path

from import_texts import CHAPTERS, FILES, disjoint, encode, language, sha

GAME_NAMES = {
    'ja': 'lang_ja.json', 'zh_default': 'lang_en.json',
    'zh_names': 'lang_en_names.json', 'zh_recruitable': 'lang_en_names_recruitable.json',
}


def prepare(english_dir, game_dir, out, provenance=None):
    english_dir, game_dir = Path(english_dir).resolve(strict=True), Path(game_dir).resolve(strict=True)
    out = Path(out).resolve()
    disjoint(english_dir, out)
    disjoint(game_dir, out)
    if out.exists():
        raise ValueError(f'Refusing to overwrite an existing input snapshot: {out}')
    provenance = (Path(provenance).resolve() if provenance is not None else
                  Path(__file__).resolve().parents[1] / 'local' / (out.name + '-provenance.json'))
    if provenance.exists():
        raise ValueError(f'Refusing to overwrite provenance: {provenance}')
    for source_root in (english_dir, game_dir, out):
        if provenance.is_relative_to(source_root):
            raise ValueError('Provenance must be outside game, English and unified input folders')
    pending, sources = [], []
    for ch in CHAPTERS:
        for field, filename in FILES.items():
            source = (english_dir / f'lang_en_ch{ch}.json' if field == 'en' else
                      game_dir / f'chapter{ch}_windows/lang' / GAME_NAMES[field])
            raw = source.read_bytes()
            texts, metadata = language(raw, str(source))
            relative = f'ch{ch}/{filename}'
            pending.append((relative, raw))
            sources.append({'path': relative, 'source_path': str(source), 'sha256': sha(raw),
                            'bytes': len(raw), 'entries': len(texts), 'metadata': metadata})
    for record in sources:
        if sha(Path(record['source_path']).read_bytes()) != record['sha256']:
            raise ValueError(f"Source changed while preparing: {record['source_path']}")
    out.mkdir(parents=True)
    for relative, raw in pending:
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_bytes(encode({
        'schema': 1, 'kind': 'byte-identical-copy', 'sources': sources,
        'note': 'Local provenance only; not required by import_texts. Dates in inputs are not verified release versions.',
    }))
    return sources


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--english-dir', type=Path, required=True)
    parser.add_argument('--game-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--provenance', type=Path, help='Local record; default: project local/<output-name>-provenance.json')
    args = parser.parse_args()
    try:
        records = prepare(args.english_dir, args.game_dir, args.out, args.provenance)
    except (OSError, ValueError) as exc:
        parser.exit(2, f'Preparation error: {exc}\n')
    print(f'Copied {len(records)} language files to {args.out}; originals unchanged')
