"""Export three-stream captures and receive them into an independent evidence library.

Only the six established reader modules interpret collector evidence. ZIP transport
adds no identity inference. Original logs are retained unchanged; a single SQLite
index commits all streams together after validation in disposable databases.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import zipfile

from .legacy.store import canonical, digest, import_log, resolve_sources
from .legacy.interaction_store import import_interactions, read_lines
from .legacy.choice_store import import_choices

NAME = re.compile(r'(capture|interactions|choices)_([a-f0-9]{32})_([a-f0-9]{32})\.jsonl')
SHA = re.compile('[a-f0-9]{64}')
MAX_FILES = 301
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_BYTES = 512 * 1024 * 1024
KIND = 'deltarune_runtime_submission'


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def bad(value):
        raise ValueError('Non-finite JSON number: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def _header(raw):
    lines = raw.splitlines(keepends=True)
    if not lines or not lines[0].endswith(b'\n'):
        raise ValueError('Missing complete capture header')
    # Reject duplicate keys / non-finite values before the legacy readers see data.
    for line in lines[:-1] if not lines[-1].endswith(b'\n') else lines:
        if not isinstance(_json(line), dict):
            raise ValueError('Expected JSON event object')
    return _json(lines[0])


def _inventory(sources, expected):
    path = resolve_sources(Path(sources), expected)
    data = _json(path.read_bytes())
    if (data.get('schema') != 1 or data.get('chapter') != 2
            or not SHA.fullmatch(data.get('package_sha256', ''))):
        raise ValueError('Only the version-bound CH2 inventory is supported')
    ids = [row['source_id'] for row in data['sources']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate inventory source ID')
    return path, data


def _describe(files, sources):
    if not files or len(files) >= MAX_FILES:
        raise ValueError('Expected a bounded collection of capture logs')
    if sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError('Capture logs exceed submission size limit')
    runs, groups = set(), {}
    for name, raw in sorted(files.items()):
        match = NAME.fullmatch(name)
        if match is None or len(raw) > MAX_FILE_BYTES:
            raise ValueError('Invalid or oversized capture log: ' + name)
        stream, run, sid = match.groups()
        h = _header(raw)
        if h.get('run_id') != run or h.get('session_id') != sid:
            raise ValueError('Filename/header identity mismatch: ' + name)
        if not SHA.fullmatch(h.get('collector_sha256', '')):
            raise ValueError('Missing version-bound collector digest')
        runs.add(run)
        groups.setdefault(sid, {})[stream] = (name, h)
    if len(runs) != 1:
        raise ValueError('Export one run at a time')
    segments = []
    for sid, streams in sorted(groups.items()):
        if 'capture' not in streams:
            raise ValueError('Orphan sidecar without message stream')
        name, h = streams['capture']
        if h.get('schema') != 2 or h.get('mode') not in ('natural_play_pilot', 'mechanism_selftest'):
            raise ValueError('Only version 2 message captures are supported')
        inv_path, inv = _inventory(sources, h.get('source_manifest'))
        for stream, (_, other) in streams.items():
            for field in ('run_id', 'session_id', 'source_manifest', 'collector_sha256', 'mode'):
                if other.get(field) != h.get(field):
                    raise ValueError('Sidecar/message provenance mismatch: ' + field)
        binding = dict(chapter=2, language='en', source_manifest=h['source_manifest'],
                       collector_sha256=h['collector_sha256'], package_sha256=inv['package_sha256'],
                       mode=h['mode'])
        segments.append(dict(session_id=sid, partition_id=digest(binding), **binding,
                             files={k: v[0] for k, v in sorted(streams.items())}))
    return dict(schema=1, kind=KIND, run_id=next(iter(runs)), segments=segments,
                files={name: dict(sha256=_sha(raw), bytes=len(raw)) for name, raw in sorted(files.items())})


def _validate(files, manifest, sources, stage):
    """Create disposable per-stream DBs; nothing here touches the evidence library."""
    logdir = stage / 'logs'
    logdir.mkdir()
    for name, raw in files.items():
        (logdir / name).write_bytes(raw)
    summaries, warnings = [], []
    all_bodies, all_observations = {}, []
    totals = Counter(messages=0, interactions=0, choices=0, smallfaces=0, unmatched=0,
                     confirmed_choices=0, inline_images=0, portrait_pages=0, style_pages=0)
    for segment in manifest['segments']:
        sid = segment['session_id']
        dbdir = stage / sid
        dbdir.mkdir()
        names = segment['files']
        message = logdir / names['capture']
        result = import_log(dbdir / 'messages.sqlite', message, Path(sources))
        records, _ = read_lines(message)
        details = [r for r in records if r.get('kind') == 'attributes']
        counts = dict(messages=result['events'], unmatched=result['unmatched'],
                      smallfaces=sum(len(r.get('smallfaces', [])) for r in details),
                      inline_images=sum(sum(a.get('role') == 'inline' for a in r['assets']) for r in details),
                      portrait_pages=sum(any(a.get('role') == 'portrait' for a in r['assets']) for r in details),
                      style_pages=sum(bool(r.get('text_styles', {}).get('states')) for r in details))
        totals.update(counts)
        issues = []
        if result['tail_incomplete']:
            issues.append('message_tail_incomplete')
        if result['unclosed_pages']:
            issues.append('unclosed_pages:' + str(result['unclosed_pages']))
        if any(r.get('io_failed') for r in records):
            issues.append('message_io_failed')
        if any(r.get('overflow') for r in details):
            issues.append('attribute_overflow')
        stream_results = {'messages': result}
        for stream, importer in (('interactions', import_interactions), ('choices', import_choices)):
            if stream not in names:
                issues.append('missing_' + stream + '_stream')
                continue
            summary = importer(dbdir / (stream + '.sqlite'), logdir / names[stream], message, Path(sources))
            stream_results[stream] = summary
            totals[stream] += summary[stream]
            if stream == 'choices':
                totals['confirmed_choices'] += summary['confirmed']
            for key in ('tail_incomplete', 'io_failed', 'missing_links', 'unclosed_dispatches', 'unclosed_choices', 'overflow'):
                if summary.get(key):
                    issues.append(stream + ':' + key + ':' + str(summary[key]))
        with closing(sqlite3.connect(dbdir / 'messages.sqlite')) as db:
            bodies = {k: v for k, v in db.execute('SELECT variant_id,body FROM variants')}
            all_bodies.update(bodies)
            for observation in db.execute('SELECT session_id,message_id,variant_id,telemetry FROM observations'):
                all_observations.append((segment['partition_id'], *observation))
        warnings.extend(sid + ':' + issue for issue in issues)
        summaries.append(dict(session_id=sid, counts=counts, streams=stream_results, warnings=issues))
    result = dict(totals, segments=len(summaries), variants=len(all_bodies), warnings=warnings,
                  capture_complete=False, segment_summaries=summaries)
    return result, all_bodies, all_observations


def export_bundle(session_dir: Path, sources: Path, out: Path) -> dict:
    session_dir, sources, out = map(Path, (session_dir, sources, out))
    if out.exists():
        raise ValueError('Export destination already exists; choose a new file')
    files = {p.name: p.read_bytes() for p in sorted(session_dir.glob('*.jsonl')) if NAME.fullmatch(p.name)}
    manifest = _describe(files, sources)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.runtime-export-', dir=out.parent) as temporary:
        summary, _, _ = _validate(files, manifest, sources, Path(temporary))
    manifest['summary'] = summary
    manifest['bundle_id'] = digest(manifest)
    # A new file only; failure never overwrites another submission.
    created = False
    try:
        with out.open('xb') as handle:
            created = True
            with zipfile.ZipFile(handle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('manifest.json', canonical(manifest) + '\n')
                for name, raw in sorted(files.items()):
                    archive.writestr(name, raw)
    except BaseException:
        if created and out.exists():
            out.unlink()
        raise
    return dict(bundle_id=manifest['bundle_id'], run_id=manifest['run_id'], bytes=out.stat().st_size,
                summary=summary)


def _read_bundle(bundle):
    if Path(bundle).stat().st_size > MAX_BYTES:
        raise ValueError('Submission ZIP exceeds size limit')
    with zipfile.ZipFile(bundle) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        if len(infos) > MAX_FILES or len(names) != len(set(names)) or 'manifest.json' not in names:
            raise ValueError('Invalid ZIP entries')
        if sum(i.file_size for i in infos) > MAX_BYTES:
            raise ValueError('Uncompressed submission exceeds size limit')
        for item in infos:
            if (item.filename != 'manifest.json' and NAME.fullmatch(item.filename) is None
                    or item.file_size > MAX_FILE_BYTES or item.is_dir()
                    or (item.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('Forbidden ZIP member: ' + item.filename)
        manifest = _json(archive.read('manifest.json'))
        if not isinstance(manifest, dict) or manifest.get('schema') != 1 or manifest.get('kind') != KIND:
            raise ValueError('Unknown submission format')
        body = {k: v for k, v in manifest.items() if k != 'bundle_id'}
        if digest(body) != manifest.get('bundle_id'):
            raise ValueError('Submission manifest digest mismatch')
        files = {name: archive.read(name) for name in names if name != 'manifest.json'}
    expected = manifest.get('files')
    actual = {name: dict(sha256=_sha(raw), bytes=len(raw)) for name, raw in sorted(files.items())}
    if expected != actual:
        raise ValueError('Submission log digest mismatch')
    return manifest, files


@contextmanager
def _lock(library):
    lock = library / '.receive.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('Another receive is active; stale lock requires explicit local review')
    try:
        os.write(descriptor, str(os.getpid()).encode('ascii'))
        yield
    finally:
        os.close(descriptor)
        lock.unlink()


def _schema(db):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if names and ('meta' not in names or db.execute("SELECT value FROM meta WHERE key='schema'").fetchone() != ('runtime-library-1',)):
        raise ValueError('Refusing an unrelated evidence database')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
      INSERT OR IGNORE INTO meta VALUES('schema','runtime-library-1');
      CREATE TABLE IF NOT EXISTS bundles(bundle_id TEXT PRIMARY KEY,manifest TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,
          partition_id TEXT NOT NULL,files TEXT NOT NULL,bundle_id TEXT NOT NULL,summary TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS variants(variant_id TEXT PRIMARY KEY,body TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS observations(session_id TEXT NOT NULL,message_id INTEGER NOT NULL,
          partition_id TEXT NOT NULL,variant_id TEXT NOT NULL,telemetry TEXT NOT NULL,
          PRIMARY KEY(session_id,message_id));
    ''')


def _totals(db):
    counts = Counter(messages=0, interactions=0, choices=0, smallfaces=0, unmatched=0)
    for (raw,) in db.execute('SELECT summary FROM sessions'):
        s = json.loads(raw)
        counts.update({k: s['counts'].get(k, 0) for k in ('messages', 'smallfaces', 'unmatched')})
        for k in ('interactions', 'choices'):
            counts[k] += s['streams'].get(k, {}).get(k, 0)
    return dict(counts, sessions=db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],
                variants=db.execute('SELECT COUNT(DISTINCT variant_id) FROM observations').fetchone()[0],
                partitions=db.execute('SELECT COUNT(DISTINCT partition_id) FROM sessions').fetchone()[0])


def _continuation(old, current, files, library):
    """Accept only byte-preserving append or an older prefix; never splice streams."""
    if old[:2] != current[:2]:
        raise ValueError('Previously received session changed provenance; submission kept untouched')
    before_specs, after_specs = json.loads(old[2]), json.loads(current[2])
    if before_specs == after_specs:
        return 'same'
    before = {}
    for name, spec in before_specs.items():
        raw = (library / 'received' / old[3] / 'logs' / name).read_bytes()
        if dict(sha256=_sha(raw), bytes=len(raw)) != spec:
            raise ValueError('Stored session evidence changed; repair library before receiving')
        before[name] = raw
    after = {name: files[name] for name in after_specs}
    if before.keys() <= after.keys() and all(after[name].startswith(raw) for name, raw in before.items()):
        return 'extended'
    if after.keys() <= before.keys() and all(before[name].startswith(raw) for name, raw in after.items()):
        return 'older'
    raise ValueError('Previously received session changed within recorded bytes or mixed old/new streams; '
                     'submission kept untouched for manual review')


def receive_bundle(bundle: Path, sources: Path, library: Path) -> dict:
    bundle, sources, library = map(Path, (bundle, sources, library))
    manifest, files = _read_bundle(bundle)
    described = _describe(files, sources)
    if {k: manifest.get(k) for k in described} != described:
        raise ValueError('Submission provenance differs from locally verified sources')
    library.mkdir(parents=True, exist_ok=True)
    with _lock(library), tempfile.TemporaryDirectory(prefix='.validate-', dir=library) as temporary:
        stage = Path(temporary)
        summary, bodies, observations = _validate(files, described, sources, stage)
        if summary != manifest.get('summary'):
            raise ValueError('Submission summary differs from validation')
        bundle_id = manifest['bundle_id']
        db = sqlite3.connect(library / 'index.sqlite')
        try:
            _schema(db)
            with db:
                previous = db.execute('SELECT manifest FROM bundles WHERE bundle_id=?', (bundle_id,)).fetchone()
                if previous and previous[0] != canonical(manifest):
                    raise ValueError('Bundle identity reused')
                summaries = {s['session_id']: s for s in summary['segment_summaries']}
                fresh, extended, older = [], [], []
                for segment in manifest['segments']:
                    sid = segment['session_id']
                    identity = canonical({n: manifest['files'][n] for n in segment['files'].values()})
                    old = db.execute('SELECT run_id,partition_id,files,bundle_id FROM sessions WHERE session_id=?', (sid,)).fetchone()
                    current = (manifest['run_id'], segment['partition_id'], identity)
                    if not old:
                        fresh.append(sid)
                    else:
                        relation = _continuation(old, current, files, library)
                        if relation == 'extended':extended.append(sid)
                        if relation == 'older':older.append(sid)
                destination = library / 'received' / bundle_id
                if destination.exists():
                    # An interrupted transaction may leave a complete orphan directory.
                    if (destination / 'manifest.json').read_text(encoding='utf-8') != canonical(manifest) + '\n':
                        raise ValueError('Existing received evidence differs')
                    for name, raw in files.items():
                        if (destination / 'logs' / name).read_bytes() != raw:
                            raise ValueError('Existing received log differs')
                else:
                    (stage / 'manifest.json').write_text(canonical(manifest) + '\n', encoding='utf-8', newline='\n')
                    destination.parent.mkdir(exist_ok=True)
                    stage.rename(destination)
                db.execute('INSERT OR IGNORE INTO bundles VALUES (?,?)', (bundle_id, canonical(manifest)))
                for segment in manifest['segments']:
                    sid = segment['session_id']
                    if sid not in fresh and sid not in extended:
                        continue
                    identity = canonical({n: manifest['files'][n] for n in segment['files'].values()})
                    db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?)',
                               (sid, manifest['run_id'], segment['partition_id'], identity, bundle_id, canonical(summaries[sid])))
                for key, body in bodies.items():
                    old = db.execute('SELECT body FROM variants WHERE variant_id=?', (key,)).fetchone()
                    if old and old[0] != body:
                        raise ValueError('Variant hash conflict')
                    db.execute('INSERT OR IGNORE INTO variants VALUES (?,?)', (key, body))
                for partition, sid, mid, vid, telemetry in observations:
                    if sid in fresh or sid in extended:
                        db.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?)', (sid, mid, partition, vid, telemetry))
            return dict(bundle_id=bundle_id, run_id=manifest['run_id'], summary=summary,
                        new_bundle=previous is None, duplicate=not fresh and not extended,
                        new_sessions=len(fresh), updated_sessions=len(extended), older_sessions=len(older),
                        collector_validation='declared_consistent_not_authenticated',
                        library_totals=_totals(db))
        finally:
            db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    export = commands.add_parser('export')
    export.add_argument('--session', type=Path, required=True)
    export.add_argument('--sources', type=Path, required=True)
    export.add_argument('--out', type=Path, required=True)
    receive = commands.add_parser('receive')
    receive.add_argument('--bundle', type=Path, required=True)
    receive.add_argument('--sources', type=Path, required=True)
    receive.add_argument('--library', type=Path, required=True)
    args = parser.parse_args()
    result = (export_bundle(args.session, args.sources, args.out) if args.command == 'export' else
              receive_bundle(args.bundle, args.sources, args.library))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
