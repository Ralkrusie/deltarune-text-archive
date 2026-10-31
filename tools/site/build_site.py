"""Assemble only the static viewer and verified chapter packages into dist/."""
import json
import html
import re
import base64
from pathlib import Path
from tools.text.import_texts import sha, disjoint
from .build_site_data import build
from tools.context.context_data import validate, catalog_payload
from tools.assets.site_assets import asset_payload

ROOT = Path(__file__).resolve().parents[2]
WEB_FILES = (
    'index.html', 'favicon.svg', 'style.css', 'text.js', 'model.js', 'actions.js', 'query.js',
    'soul.js',
    'app.js', 'context.js', 'search-worker.js', 'i18n.js',
    'fonts/JetBrainsMonoNL-Regular.ttf', 'fonts/OFL.txt', 'fonts/SOURCE.json',
)


def assemble(root=ROOT):
    root = Path(root).resolve()
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()
    match = re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-(alpha|beta|rc)\.([1-9]\d*))?', version)
    if not match:
        raise ValueError('VERSION must use X.Y.Z or X.Y.Z-alpha/beta/rc.N')
    source, data, target = root / 'web', root / 'build/site-data', root / 'dist'
    links = root / 'local/source-links'
    build(root / 'build/texts', data, links if links.exists() else None)
    for p in [source, data, root / 'input', root / 'local']:
        disjoint(p.resolve(), target.resolve())
    payload = {'.nojekyll': b''}
    for name in WEB_FILES:
        payload[name] = (source / name).read_bytes()
    release_path = root / 'local/release.json'
    release = json.loads(release_path.read_text(encoding='utf-8')) if release_path.exists() else {}
    fresh = release.get('text_manifest_sha256') == sha((root / 'build/texts/manifest.json').read_bytes())
    patch = release.get('translation_version') if fresh else None
    game = release.get('game_version') if fresh else None
    game_date = release.get('game_release_date') if fresh else None
    markup = payload['index.html'].decode('utf-8-sig').replace('__PATCH_VERSION__', html.escape(patch or '版本待核对')).replace('__GAME_VERSION__', html.escape(game or '版本待核对'))
    markup = markup.replace('__GAME_DATE__', html.escape(game_date or '日期待核对'))
    markup = markup.replace('__SITE_VERSION__', version)
    for script in ('context.js', 'app.js', 'soul.js', 'i18n.js'):
        markup = markup.replace(f'src="{script}"', f'src="{script}?v={sha(payload[script])}"')
    markup = markup.replace('href="style.css"', 'href="style.css?v='+sha(payload['style.css'])+'"')
    payload['index.html'] = markup.encode('utf-8')
    payload.update(asset_payload(root))
    # Embed the original sprite: SVG follows the dark rim, with no external image request.
    book = base64.b64encode(payload['assets/ui/brand/spr_castle_book_pillar_0.png']).decode('ascii')
    payload['favicon.svg'] = payload['favicon.svg'].replace(b'__BOOK_PILLAR_PNG__', book.encode('ascii'))
    for name in ['manifest.json', *[f'ch{ch}.json' for ch in range(1, 6)]]:
        payload['data/' + name] = (data / name).read_bytes()
    context_path=root/'local/context-files/contexts.json'
    all_context=root/'local/context-all'
    text_manifest=(root/'build/texts/manifest.json').read_bytes()
    context={'schema':1,'text_manifest_sha256':sha(text_manifest),'scenes':[]}
    if context_path.exists() and not (all_context/'contexts.json').exists():
        raw=context_path.read_bytes()
        evidence=json.loads(context_path.with_name('evidence.json').read_text(encoding='utf-8'))
        if sha(raw)!=evidence['contexts_sha256']:raise ValueError('Context package digest mismatch')
        context=json.loads(raw)
        tables={ch:{r['key'] for r in json.loads((root/f'build/texts/trilingual_chapter{ch}.json').read_text(encoding='utf-8'))['lines']} for ch in range(1,6)}
        validate(context,text_manifest,tables)
    payload['data/contexts.json']=(json.dumps(context,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    if (all_context/'contexts.json').exists():
        tables={ch:{r['key'] for r in json.loads((root/f'build/texts/trilingual_chapter{ch}.json').read_text(encoding='utf-8'))['lines']} for ch in range(1,6)}
        payload.update(catalog_payload(all_context,text_manifest,tables))
    unexpected = [p.relative_to(target).as_posix() for p in target.rglob('*')
                  if p.is_file() and p.relative_to(target).as_posix() not in payload]
    if unexpected:
        raise ValueError(f'Unexpected files in dist; inspect before rebuilding: {unexpected}')
    for name in payload:
        path = target / name
        if not path.resolve().is_relative_to(target.resolve()):
            raise ValueError(f'Unsafe output path: {path}')
    target.mkdir(exist_ok=True)
    for name, raw in payload.items():
        p = target / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    report = {'site_version': version,
              'files': [{'path': name, 'bytes': len(raw), 'sha256': sha(raw)} for name, raw in payload.items()],
              'total_bytes': sum(map(len, payload.values()))}
    (root / 'build/site-build.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"Built {len(payload)} files, {report['total_bytes']/1024**2:.2f} MiB into {target}")
    return target


if __name__ == '__main__':
    try:
        assemble()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f'Build failed: {exc}')
