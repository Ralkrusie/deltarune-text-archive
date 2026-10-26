"""Explicit local-source to public-asset mapping; no recursive game-resource copying."""
import json
from pathlib import PurePosixPath


def asset_payload(root):
    manifest = json.loads((root / 'config/site-assets.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 1:
        raise ValueError('Unsupported site asset manifest')
    payload, seen = {}, set()
    for item in manifest['files']:
        source, target = item['source'], item['target']
        for name in (source, target):
            p = PurePosixPath(name)
            if not name or '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts or p.as_posix() != name:
                raise ValueError(f'Unsafe asset path: {name}')
        source_root = next((prefix for prefix in ('local/ui-assets/', 'web/assets/') if source.startswith(prefix)), None)
        if source_root is None or not target.startswith(('assets/ui/', 'assets/soul/', 'assets/dialogue/')):
            raise ValueError(f'Invalid asset namespace: {item}')
        if target.casefold() in seen:
            raise ValueError(f'Duplicate asset target: {target}')
        seen.add(target.casefold())
        path = root / source
        if not path.resolve().is_relative_to((root / source_root).resolve()):
            raise ValueError(f'Asset source escaped its root: {source}')
        payload[target] = path.read_bytes()
    return payload
