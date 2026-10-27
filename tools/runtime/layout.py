"""Move an existing capture copy under its tool and retain isolated save progress."""
import argparse
import json
from pathlib import Path
import shutil

from .launcher import load_install, plain, under, sha, save_roots, ProfileLock


def migrate_capture(source, tool_home, legacy_saves=None):
    source, tool_home = plain(source).resolve(strict=True), plain(tool_home).resolve(strict=True)
    target = under(tool_home, 'capture')
    if source != target and (target.exists() or target.is_relative_to(source) or source.is_relative_to(target)):
        raise ValueError('迁入目标必须是全新的 capture 文件夹，不能与来源嵌套。')
    meta = load_install(source)
    # Validate every child before a directory rename; no reparse-point traversal.
    for child in source.rglob('*'):
        plain(child)
    if source != target and source.drive.lower() != target.drive.lower():
        raise ValueError('迁入需要在同一磁盘；跨盘请先复制完整采集副本，再选择该副本。')
    if meta.get('save_layout') != 'local_appdata_v1':
        if legacy_saves is None:
            candidates = save_roots(meta['profile'])
            present = [p for p in candidates if p.is_dir()]
            if len(present) > 1:
                raise ValueError('发现多个旧隔离存档目录，请显式指定 --legacy-saves。')
            legacy_saves = present[0] if present else None
        if legacy_saves is not None:
            legacy_saves = plain(legacy_saves).resolve(strict=True)
    locked = ProfileLock(meta['profile'], source)
    try:
        copied = {}
        if meta.get('save_layout') != 'local_appdata_v1':
            dest = under(source, 'saves/' + meta['profile'])
            candidates = []
            if legacy_saves is not None:
                for old in legacy_saves.rglob('*'):
                    plain(old)
                    relative = old.relative_to(legacy_saves).as_posix()
                    if not old.is_file() or old.name.startswith(('capture_', 'choices_', 'interactions_')):
                        continue
                    new = under(source, 'saves/' + meta['profile'] + '/' + relative)
                    digest = sha(old)
                    if new.exists() and sha(new) != digest:
                        raise ValueError('本地存档已存在且不同，停止迁入：' + relative)
                    candidates.append((old, new, relative, digest))
            for old, new, relative, digest in candidates:
                new.parent.mkdir(parents=True, exist_ok=True)
                if not new.exists():
                    shutil.copy2(old, new)
                if sha(new) != digest:
                    raise ValueError('Save migration verification failed: ' + relative)
                copied[relative] = digest
            dest.mkdir(parents=True, exist_ok=True)
            meta.update(save_layout='local_appdata_v1', save_policy='capture/saves/profile via child LOCALAPPDATA')
            under(source, 'capture.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        receipt = dict(schema=1, moved=source != target, source=str(source), destination=str(target),
                       copied_saves=copied, old_saves_preserved=True)
        under(source, 'layout-migration.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        locked.close()
    if source != target:
        # Both resolved absolute paths were checked above; rename never overwrites.
        source.rename(target)
    load_install(target)
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--tool-home', type=Path, required=True)
    p.add_argument('--legacy-saves', type=Path)
    a = p.parse_args()
    print(json.dumps(migrate_capture(a.source, a.tool_home, a.legacy_saves), ensure_ascii=False, indent=2))
