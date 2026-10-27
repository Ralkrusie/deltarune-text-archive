"""Build and install a version-bound runtime kit without redistributing a game.

The kit carries COPY/literal deltas against participants' verified originals.
Installation copies the complete verified file inventory into a new directory.
No game process, compiler, shell command, or save-file operation is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import zlib

MAGIC = b'DRDELTA1\n'
MAX_FILE = 1024 * 1024 * 1024
MAX_META = 16 * 1024 * 1024
MAX_FILES = 10000
MAX_TOTAL = 16 * MAX_FILE
MIN_CHUNK, MAX_CHUNK = 16384, 262144
# A content anchor survives inserted bytes; the maximum bounds sparse regions.
ANCHOR = re.compile(b'\x00\xff')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Invalid SHA-256')
    return value


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or PurePosixPath(value).is_absolute() or any(p in ('', '.', '..') for p in value.split('/'))
            or any(p.endswith(('.', ' ')) or any(ord(c) < 32 or c in '<>"|?*' for c in p) for p in value.split('/'))):
        raise ValueError('Unsafe relative path')
    if any(re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p, re.I) for p in value.split('/')):
        raise ValueError('Reserved Windows path')
    return value


def _plain(path):
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
            raise ValueError('Linked paths are not supported')
    return path


def _new_output(out, *inputs):
    out = _plain(out)
    if out.exists():
        raise ValueError('Output directory must be new')
    resolved = out.resolve()
    for value in inputs:
        source = Path(value).resolve()
        if resolved == source or resolved.is_relative_to(source) or source.is_relative_to(resolved):
            raise ValueError('Output must be separate from input directories')
    return out


def _chunks(data):
    start = 0
    for match in ANCHOR.finditer(data):
        end = match.end()
        while end - start > MAX_CHUNK:
            yield start, start + MAX_CHUNK
            start += MAX_CHUNK
        if end - start >= MIN_CHUNK:
            yield start, end
            start = end
    while len(data) - start > MAX_CHUNK:
        yield start, start + MAX_CHUNK
        start += MAX_CHUNK
    if start < len(data):
        yield start, len(data)


def make_delta(base: bytes, target: bytes) -> bytes:
    if max(len(base), len(target)) > MAX_FILE:
        raise ValueError('Delta file exceeds bound')
    index = {}
    for start, end in _chunks(base):
        index.setdefault(hashlib.sha256(base[start:end]).digest(), (start, end))
    ops, literals = [], bytearray()
    for start, end in _chunks(target):
        part = target[start:end]
        match = index.get(hashlib.sha256(part).digest())
        if match is not None and base[match[0]:match[1]] == part:
            op = ['copy', match[0], len(part)]
        else:
            op = ['data', len(literals), len(part)]
            literals.extend(part)
        if ops and ops[-1][0] == op[0] and ops[-1][1] + ops[-1][2] == op[1]:
            ops[-1][2] += op[2]
        else:
            ops.append(op)
    meta = canonical({'schema': 1, 'base_size': len(base), 'target_size': len(target),
                      'base_sha256': hashlib.sha256(base).hexdigest(),
                      'target_sha256': hashlib.sha256(target).hexdigest(),
                      'literal_size': len(literals), 'ops': ops})
    if len(meta) > MAX_META:
        raise ValueError('Too many delta operations')
    return MAGIC + struct.pack('<I', len(meta)) + meta + zlib.compress(literals, 9)


def _read_delta(patch: bytes):
    if len(patch) > MAX_FILE + MAX_META or not patch.startswith(MAGIC):
        raise ValueError('Invalid or oversized delta')
    if len(patch) < len(MAGIC) + 4:
        raise ValueError('Truncated delta')
    size = struct.unpack('<I', patch[len(MAGIC):len(MAGIC)+4])[0]
    if size > MAX_META:
        raise ValueError('Oversized delta metadata')
    end = len(MAGIC) + 4 + size
    meta = json.loads(patch[len(MAGIC)+4:end])
    if meta.get('schema') != 1:
        raise ValueError('Unsupported delta schema')
    for name in ('base_size', 'target_size', 'literal_size'):
        if type(meta.get(name)) is not int or not 0 <= meta[name] <= MAX_FILE:
            raise ValueError('Invalid delta size')
    _hash(meta.get('base_sha256')); _hash(meta.get('target_sha256'))
    if meta['literal_size'] > meta['target_size'] or not isinstance(meta.get('ops'), list):
        raise ValueError('Invalid literal size or operations')
    total = 0
    for op in meta['ops']:
        if (not isinstance(op, list) or len(op) != 3 or op[0] not in ('copy', 'data')
                or type(op[1]) is not int or type(op[2]) is not int or op[1] < 0 or op[2] <= 0
                or op[1]+op[2] > meta['base_size' if op[0] == 'copy' else 'literal_size']):
            raise ValueError('Delta operation outside source bounds')
        total += op[2]
    if total != meta['target_size']:
        raise ValueError('Delta output length mismatch')
    inflater = zlib.decompressobj()
    literals = inflater.decompress(patch[end:], meta['literal_size'] + 1)
    if (len(literals) != meta['literal_size'] or not inflater.eof
            or inflater.unconsumed_tail or inflater.unused_data):
        raise ValueError('Delta literal stream mismatch')
    return meta, literals


def apply_delta(base: Path, patch: bytes, output=None):
    """Validate and stream a delta; output=None verifies without writing a copy."""
    meta, literals = _read_delta(patch)
    if base.stat().st_size != meta['base_size'] or sha(base) != meta['base_sha256']:
        raise ValueError('Delta original version mismatch')
    digest = hashlib.sha256()
    with base.open('rb') as stream:
        for mode, start, size in meta['ops']:
            if mode == 'copy':
                stream.seek(start)
            for offset in range(0, size, 1024 * 1024):
                count = min(size-offset, 1024 * 1024)
                block = stream.read(count) if mode == 'copy' else literals[start+offset:start+offset+count]
                if len(block) != count:
                    raise ValueError('Truncated delta source')
                digest.update(block)
                if output is not None:
                    output.write(block)
    if digest.hexdigest() != meta['target_sha256']:
        raise ValueError('Delta reconstructed hash mismatch')
    return meta


def anonymize_guard(data: bytes, expected_path: str):
    """Replace one precisely indexed GM STRG entry with an equal-length sentinel.

    Revision 30 also accepts LOCALAPPDATA/profile. Only the obsolete machine
    fallback literal changes; code and STRG offsets/lengths are preserved.
    """
    needle = expected_path.replace('\\', '/').rstrip('/').lower().encode('utf-8')
    if len(needle) < 16 or len(needle) > 1024:
        raise ValueError('Unexpected save-root fallback length')
    if data[:4] != b'FORM' or len(data) < 8 or struct.unpack('<I', data[4:8])[0] != len(data)-8:
        raise ValueError('Expected a complete GameMaker FORM')
    pos, matches = 8, []
    while pos < len(data):
        if pos+8 > len(data):
            raise ValueError('Truncated GameMaker chunk')
        name, size = data[pos:pos+4], struct.unpack('<I', data[pos+4:pos+8])[0]
        start, end = pos+8, pos+8+size
        if end > len(data):
            raise ValueError('GameMaker chunk outside package')
        if name == b'STRG':
            count = struct.unpack('<I', data[start:start+4])[0]
            table_end = start+4+4*count
            if table_end > end:
                raise ValueError('Invalid STRG table')
            for index in range(count):
                ptr = struct.unpack('<I', data[start+4+4*index:start+8+4*index])[0]
                if ptr < table_end or ptr+4 > end:
                    raise ValueError('Invalid STRG entry')
                n = struct.unpack('<I', data[ptr:ptr+4])[0]
                if ptr+4+n >= end or data[ptr+4+n] != 0:
                    raise ValueError('Invalid STRG string boundary')
                if data[ptr+4:ptr+4+n] == needle:
                    matches.append((index, ptr+4))
        pos = end
    if len(matches) != 1 or data.count(needle) != 1:
        raise ValueError('Expected exactly one indexed save-root fallback')
    replacement = b'capture-portable-invalid-root/' + b'_' * (len(needle)-30)
    if len(replacement) != len(needle):
        raise ValueError('Sentinel must keep the STRG length')
    index, offset = matches[0]
    changed = data[:offset] + replacement + data[offset+len(needle):]
    return changed, {'kind': 'same_length_STRG_save_fallback', 'string_index': index,
                     'offset': offset, 'bytes': len(needle),
                     'prior_literal_sha256': hashlib.sha256(needle).hexdigest(),
                     'replacement': replacement.decode('ascii'),
                     'environment_branch': 'LOCALAPPDATA/profile'}


def _read_json(path):
    path = _plain(path)
    if path.stat().st_size > MAX_META:
        raise ValueError('Oversized metadata')
    return json.loads(path.read_text(encoding='utf-8'))


def build_kit(original: Path, capture: Path, out: Path) -> dict:
    original, capture = _plain(original).resolve(strict=True), _plain(capture).resolve(strict=True)
    out = _new_output(out, original, capture)
    old = _read_json(capture/'manifest.json')
    expected = _read_json(capture/'original-files.json')
    source_bytes = (capture/'sources.json').read_bytes()
    inventory = json.loads(source_bytes)
    if (old.get('kind') != 'full_game_capture_pilot' or old.get('revision') != 30
            or hashlib.sha256(source_bytes).hexdigest() != old.get('source_manifest')
            or inventory.get('chapter') != 2):
        raise ValueError('Expected the verified CH2 revision 30 capture build')
    if re.search(rb'[A-Za-z]:[\\/]', source_bytes) or len(source_bytes) > MAX_META:
        raise ValueError('Inventory contains machine paths or exceeds size bound')
    if not expected or len(expected) > MAX_FILES:
        raise ValueError('Invalid original inventory')
    required = {'DELTARUNE.exe', 'data.win', *[f'chapter{i}_windows/data.win' for i in range(1, 6)]}
    if not required.issubset(expected) or inventory.get('package_sha256') != expected['chapter2_windows/data.win']:
        raise ValueError('Complete game or chapter source binding missing')
    output_hashes = old['outputs']
    if set(output_hashes) != {'game/'+name for name in expected}:
        raise ValueError('Capture does not contain the complete original inventory')
    files, total = {}, 0
    for name, expected_sha in sorted(expected.items()):
        _relative(name); _hash(expected_sha)
        source, target = _plain(original/name), _plain(capture/'game'/name)
        if sha(source) != expected_sha or sha(target) != output_hashes['game/'+name]:
            raise ValueError('Original or capture file changed: '+name)
        size, target_size = source.stat().st_size, target.stat().st_size
        if max(size, target_size) > MAX_FILE:
            raise ValueError('File exceeds kit bound')
        total += size
        files[name] = {'original_sha256': expected_sha, 'original_size': size,
                       'target_sha256': output_hashes['game/'+name], 'target_size': target_size}
    if total > MAX_TOTAL:
        raise ValueError('Game inventory exceeds kit bound')
    out.mkdir(parents=True)
    (out/'patches').mkdir()
    (out/'sources.json').write_bytes(source_bytes)
    for name, record in files.items():
        if record['original_sha256'] == record['target_sha256']:
            continue
        if name != 'data.win' and not re.fullmatch('chapter[1-5]_windows/data.win', name):
            raise ValueError('Unexpected modified resource: '+name)
        data = (capture/'game'/name).read_bytes()
        data, evidence = anonymize_guard(data, old['expected_save_path'])
        record['capture_sha256'] = record['target_sha256']
        record['target_sha256'] = hashlib.sha256(data).hexdigest()
        record['isolation_edit'] = evidence
        patch = make_delta((original/name).read_bytes(), data)
        patch_name = 'patches/'+hashlib.sha256(patch).hexdigest()+'.drdelta'
        (out/patch_name).write_bytes(patch)
        record['patch'] = patch_name
        record['patch_sha256'] = hashlib.sha256(patch).hexdigest()
        record['patch_size'] = len(patch)
        apply_delta(original/name, patch)
    manifest = {'schema': 1, 'kind': 'runtime_capture_kit', 'revision': 30,
                'chapters': [2], 'language': 'en', 'startup': 'game/DELTARUNE.exe',
                'profile': old['profile'], 'source_manifest': old['source_manifest'],
                'collector_sha256': old['collector_sha256'],
                'package_sha256': inventory['package_sha256'],
                'test_modifications': inventory['test_modifications'],
                'modes': ['natural_play_pilot', 'mechanism_selftest'],
                'files': files, 'save_policy': 'LOCALAPPDATA/profile; no saves bundled',
                'coverage': 'CH2 supported consumers only; other chapters preserve isolation only'}
    _validate_kit(manifest)
    (out/'kit.json').write_bytes(canonical(manifest)+b'\n')
    return manifest


def _validate_kit(manifest):
    if (manifest.get('schema') != 1 or manifest.get('kind') != 'runtime_capture_kit'
            or manifest.get('chapters') != [2] or manifest.get('language') != 'en'
            or manifest.get('startup') != 'game/DELTARUNE.exe' or manifest.get('revision') not in (30, 31)
            or not re.fullmatch('DELTARUNE_CAPTURE_[A-Za-z0-9_]+', manifest.get('profile', ''))):
        raise ValueError('Unsupported capture kit')
    for field in ('source_manifest', 'collector_sha256', 'package_sha256'):
        _hash(manifest.get(field))
    files = manifest.get('files')
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES or 'DELTARUNE.exe' not in files:
        raise ValueError('Invalid kit file inventory')
    if not {'data.win', *[f'chapter{i}_windows/data.win' for i in range(1, 6)]}.issubset(files):
        raise ValueError('Kit must copy the launcher and all five chapters')
    if files['chapter2_windows/data.win'].get('original_sha256') != manifest['package_sha256']:
        raise ValueError('Chapter source binding mismatch')
    folded, total = set(), 0
    for name, record in files.items():
        _relative(name)
        if name.casefold() in folded:
            raise ValueError('Case-insensitive path collision')
        folded.add(name.casefold())
        for key in ('original_sha256', 'target_sha256'):
            _hash(record.get(key))
        for key in ('original_size', 'target_size'):
            if type(record.get(key)) is not int or not 0 <= record[key] <= MAX_FILE:
                raise ValueError('Invalid kit file size')
        total += max(record['original_size'], record['target_size'])
        if 'patch' in record:
            _relative(record['patch']); _hash(record.get('patch_sha256'))
            if not re.fullmatch('patches/[a-f0-9]{64}\\.drdelta', record['patch']):
                raise ValueError('Invalid patch location')
            if type(record.get('patch_size')) is not int or not 0 < record['patch_size'] <= MAX_FILE+MAX_META:
                raise ValueError('Invalid patch size')
        elif record['original_sha256'] != record['target_sha256'] or record['original_size'] != record['target_size']:
            raise ValueError('Changed file is missing a patch')
    if total > MAX_TOTAL:
        raise ValueError('Oversized kit inventory')
    for name in folded:
        if any(parent.as_posix() in folded for parent in PurePosixPath(name).parents if parent.as_posix() != '.'):
            raise ValueError('Kit file/directory path collision')


def install_kit(kit: Path, game: Path, out: Path) -> dict:
    kit, game = _plain(kit).resolve(strict=True), _plain(game).resolve(strict=True)
    out = _new_output(out, kit, game)
    manifest = _read_json(kit/'kit.json')
    _validate_kit(manifest)
    source_path = _plain(kit/'sources.json')
    if source_path.stat().st_size > MAX_META or sha(source_path) != manifest['source_manifest']:
        raise ValueError('Source inventory integrity mismatch')
    # Validate every original and reconstruct all deltas before making output.
    for name, record in manifest['files'].items():
        source = _plain(game/name)
        if source.stat().st_size != record['original_size'] or sha(source) != record['original_sha256']:
            raise ValueError('Game version mismatch: '+name)
        if 'patch' in record:
            patch_path = _plain(kit/record['patch'])
            if patch_path.stat().st_size != record['patch_size'] or sha(patch_path) != record['patch_sha256']:
                raise ValueError('Patch integrity mismatch: '+name)
            meta = apply_delta(source, patch_path.read_bytes())
            if meta['target_size'] != record['target_size'] or meta['target_sha256'] != record['target_sha256']:
                raise ValueError('Patch target does not match kit')
    required = sum(r['target_size'] for r in manifest['files'].values()) + 16*1024*1024
    parent = out.parent
    while not parent.exists():
        parent = parent.parent
    if shutil.disk_usage(parent).free < required:
        raise ValueError('Insufficient disk space for complete isolated game copy')
    out.mkdir(parents=True)
    (out/'INSTALL_INCOMPLETE').write_text('Do not launch until capture.json exists.\n', encoding='utf-8')
    shutil.copy2(source_path, out/'sources.json')
    for name, record in manifest['files'].items():
        target = out/'game'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        if 'patch' in record:
            with target.open('xb') as stream:
                apply_delta(game/name, (kit/record['patch']).read_bytes(), stream)
        else:
            shutil.copy2(game/name, target)
        if target.stat().st_size != record['target_size'] or sha(target) != record['target_sha256']:
            raise ValueError('Installed file verification failed: '+name)
    result = {k: manifest[k] for k in ('schema', 'revision', 'chapters', 'language', 'startup', 'profile',
              'source_manifest', 'collector_sha256', 'package_sha256', 'test_modifications', 'modes', 'coverage')}
    result.update(kind='portable_runtime_capture', kit_sha256=sha(kit/'kit.json'),
                  outputs={'game/'+name: record['target_sha256'] for name, record in manifest['files'].items()},
                  save_policy='capture/saves/profile via child LOCALAPPDATA', save_layout='local_appdata_v1')
    (out/'capture.json').write_bytes(canonical(result)+b'\n')
    (out/'INSTALL_INCOMPLETE').unlink()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('build')
    build.add_argument('--original', type=Path, required=True)
    build.add_argument('--capture', type=Path, required=True)
    build.add_argument('--out', type=Path, required=True)
    install = commands.add_parser('install')
    install.add_argument('--kit', type=Path, required=True)
    install.add_argument('--game', type=Path, required=True)
    install.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = (build_kit(args.original, args.capture, args.out) if args.command == 'build'
              else install_kit(args.kit, args.game, args.out))
    print(json.dumps({'kind': result['kind'], 'files': len(result.get('files', result.get('outputs', {}))),
                      'revision': result['revision'], 'out': str(args.out)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
