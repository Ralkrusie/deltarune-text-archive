"""Build a separate local restoration lab from an existing runtime review export."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

PROJECT = Path(__file__).resolve().parents[2]
WEB = Path(__file__).with_name('web')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(review, out):
    review, out = Path(review).resolve(strict=True), Path(out).resolve()
    if not out.is_relative_to(PROJECT / 'local') or out == PROJECT / 'local':
        raise ValueError('Output must be a new directory below this project local/')
    if out.exists() or out.is_relative_to(review) or review.is_relative_to(out):
        raise ValueError('Choose a new, separate local output directory')
    raw = (review / 'data.js').read_text(encoding='utf-8')
    if not raw.startswith('window.REVIEW_DATA=') or not raw.rstrip().endswith(';'):
        raise ValueError('Expected a runtime review dataset, not executable input')
    data = json.loads(raw[len('window.REVIEW_DATA='):].rstrip()[:-1])
    if data.get('schema') != 1 or not data.get('rows') or not data.get('sessions'):
        raise ValueError('Unsupported or empty review dataset')
    ids = [row['id'] for row in data['rows']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate observation identity')
    for row in data['rows']:
        if not all(key in row for key in ('partition', 'variant', 'body', 'view')):
            raise ValueError('Missing observation binding')
    assets = []
    for name, digest in data.get('assets', {}).items():
        if not re.fullmatch(r'spr_\w+_\d+\.png', name):
            raise ValueError('Invalid asset path')
        path = (review / 'assets' / name).resolve(strict=True)
        if not path.is_relative_to(review) or sha(path) != digest:
            raise ValueError('Asset hash mismatch: ' + name)
        assets.append((name, path))
    templates = PROJECT / 'tools/runtime/review_web'
    js = (templates / 'review.js').read_text(encoding='utf-8')
    anchor = "$('detail').innerHTML=content;"
    if js.count(anchor) != 1:
        raise ValueError('Review adapter anchor changed; update the local integration')
    # Adapt a generated copy only. The canonical reviewer and default generator
    # remain untouched and do not depend on the experimental preview.
    js = js.replace(anchor, anchor + '\n  window.mountReviewPreview(r);')
    html = (templates / 'index.html').read_text(encoding='utf-8')
    if html.count('<script src="review.js"></script>') != 1:
        raise ValueError('Review script anchor changed')
    html = html.replace('</head>', '<link rel="stylesheet" href="preview.css"></head>')
    html = html.replace('<script src="review.js"></script>',
                        '<script src="model.js"></script><script src="renderer.js"></script>'
                        '<script src="review-adapter.js"></script><script src="review.js"></script>')
    out.mkdir(parents=True)
    (out / 'assets').mkdir()
    for name, path in assets:
        shutil.copy2(path, out / 'assets' / name)
    for path in WEB.iterdir():
        if path.is_file():
            shutil.copy2(path, out / path.name)
    (out / 'data.js').write_text('window.REVIEW_DATA=' + json.dumps(data, ensure_ascii=False).replace('<', '\\u003c') + ';\n', encoding='utf-8')
    (out / 'review.js').write_text(js, encoding='utf-8')
    (out / 'review.html').write_text(html, encoding='utf-8')
    shutil.copy2(templates / 'review.css', out / 'review.css')
    manifest = dict(schema=1, kind='local_restore_framework', review_data_sha256=sha(review / 'data.js'),
                    rows=len(data['rows']), frames=len(assets), public_site_modified=False,
                    files={p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
    (out / 'build.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return dict(out=str(out), rows=manifest['rows'], frames=len(assets))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.review, args.out), ensure_ascii=False, indent=2))
