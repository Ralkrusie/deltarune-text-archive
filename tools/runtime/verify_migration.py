"""Read-only comparison of legacy capture evidence and migrated runtime readers."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import sqlite3
import tempfile

from tools.context.context_data import references
from tools.context.parser.attribution_schema import occurrence_id
from .legacy.store import import_log, resolve_sources
from .legacy.interaction_store import import_interactions
from .legacy.choice_store import import_choices


def sha(path):
    with Path(path).open('rb') as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def child(root, name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or p.as_posix() != name:
        raise ValueError('Invalid relative evidence path')
    result = (root / name).resolve(strict=True)
    if not result.is_relative_to(root.resolve()):
        raise ValueError('Evidence path escapes its root')
    return result


def checked_payload(root, entry):
    path = child(root, entry['path'])
    if path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
        raise ValueError('Context output digest mismatch: ' + entry['path'])
    return read(path)


def context_sources(context, chapter, code=None):
    """Verify reference IDs against source hashes, not key or visible text matches."""
    catalog = read(context / 'contexts.json')
    proof = read(context / 'evidence.json')
    if (catalog.get('schema') != 2 or proof.get('schema') != 2
            or sha(context / 'contexts.json') != proof['contexts_sha256']
            or catalog['text_manifest_sha256'] != proof['text_manifest_sha256']):
        raise ValueError('Context evidence/catalog mismatch')
    index = checked_payload(context, catalog['chapters'][str(chapter)])
    if index['chapter'] != chapter or index['text_manifest_sha256'] != catalog['text_manifest_sha256']:
        raise ValueError('Context chapter/text mismatch')
    result = {}
    checked_code = set()
    for entry in index['files']:
        if proof['files'].get(entry['path']) != {k: entry[k] for k in ('path', 'sha256', 'bytes')}:
            raise ValueError('Context index/evidence mismatch')
        pack = checked_payload(context, entry)
        if pack['text_manifest_sha256'] != catalog['text_manifest_sha256']:
            raise ValueError('Context file/text mismatch')
        for scene in pack['scenes']:
            if scene['chapter'] != chapter:
                raise ValueError('Context scene chapter mismatch')
            for ref in references(scene['body']):
                source_name = f'ch{chapter}/' + ref['source']['file']
                source_hash = proof['sources'][source_name]
                if code is not None and source_name not in checked_code:
                    if sha(child(code, source_name)) != source_hash:
                        raise ValueError('Actual source digest differs: ' + source_name)
                    checked_code.add(source_name)
                logical_path = 'data/exported/code/' + source_name
                oid = occurrence_id(chapter, 'canonical', logical_path, source_hash,
                                    ref['key'], ref['offset'], ref['call'])
                if ref['occurrence_id'] != oid:
                    raise ValueError('Context occurrence identity differs')
                value = dict(chapter=chapter, path=logical_path, sha256=source_hash,
                             key=ref['key'], offset=ref['offset'], call=ref['call'])
                if oid in result and result[oid] != value:
                    raise ValueError('Conflicting context occurrence identity')
                result[oid] = value
    return result, len(checked_code)


def compare_inventory(inventory, refs):
    matched, missing = 0, []
    seen_ids = set()
    for source in inventory['sources']:
        if source['source_id'] in seen_ids:
            raise ValueError('Duplicate runtime source ID')
        seen_ids.add(source['source_id'])
        oid = occurrence_id(source['chapter'], 'canonical', source['path'], source['sha256'],
                            source['key'], source['offset'], source['call'])
        if oid != source['occurrence_id']:
            raise ValueError('Runtime occurrence identity differs')
        projected = {key: source[key] for key in ('chapter', 'path', 'sha256', 'key', 'offset', 'call')}
        if oid in refs:
            if refs[oid] != projected:
                raise ValueError('Context/runtime identity collision')
            matched += 1
        else:
            # Missing remains explicit; do not fall back to a same-key use.
            missing.append(dict(occurrence_id=oid, key=source['key'], path=source['path']))
    return dict(sources=len(seen_ids), exact_context_matches=matched,
                missing_context=len(missing), missing=missing)


def snapshot(database, segment, kind):
    """Open only in SQLite read-only mode, selecting the one audited segment."""
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        tables = {'messages': ['sessions', 'events', 'observations'],
                  'interactions': ['sessions', 'events', 'interactions', 'links'],
                  'choices': ['sessions', 'events', 'choices', 'links']}[kind]
        result = {table: sorted(db.execute(f'SELECT * FROM {table} WHERE session_id=?', (segment,)).fetchall())
                  for table in tables}
        if kind == 'messages':
            query = 'SELECT DISTINCT v.* FROM variants v JOIN observations o USING(variant_id) WHERE o.session_id=?'
            result['variants'] = sorted(db.execute(query, (segment,)).fetchall())
        elif kind == 'choices':
            query = 'SELECT DISTINCT v.* FROM variants v JOIN choices o USING(variant_id) WHERE o.session_id=?'
            result['variants'] = sorted(db.execute(query, (segment,)).fetchall())
        else:
            query = 'SELECT DISTINCT v.* FROM snapshots v JOIN interactions o USING(snapshot_id) WHERE o.session_id=?'
            result['snapshots'] = sorted(db.execute(query, (segment,)).fetchall())
    return result


def projected_example(old, new, segment, mid, inventory, interactions):
    old_obs = {row[1]: row for row in old['observations']}
    new_obs = {row[1]: row for row in new['observations']}
    if mid not in new_obs:
        return None
    old_body = json.loads(dict(old['variants'])[old_obs[mid][2]])
    body = json.loads(dict(new['variants'])[new_obs[mid][2]])
    by_oid = {s['occurrence_id']: s for s in inventory['sources']}
    source = by_oid.get(body['occurrence_id'])
    links = {row[1]: row for row in interactions.get('links', [])}
    interaction_id = links[mid][2] if mid in links else None
    targets = {row[1]: json.loads(row[3])['snapshot'] for row in interactions.get('interactions', [])}
    target = targets.get(interaction_id)

    def concise(value):
        return dict(occurrence_id=value['occurrence_id'], identity=value['identity'],
                    assets=value['assets'], smallfaces=value.get('smallfaces', []),
                    text_styles=value.get('text_styles'), coverage=value['coverage'])

    return dict(segment_id=segment, message_id=mid, text=body['text'],
                key=source['key'] if source else None, before=concise(old_body), after=concise(body),
                unchanged=old_body == body, interaction_id=interaction_id,
                interaction_snapshot=target, interpretation='Trigger object is not a speaker assignment.')


def verify(capture, session, context, out, code=None):
    capture, session, context = (Path(p).resolve(strict=True) for p in (capture, session, context))
    code = Path(code).resolve(strict=True) if code is not None else None
    out = Path(out).resolve()
    roots = [capture, session, context] + ([code] if code else [])
    if any(out.is_relative_to(root) for root in roots):
        raise ValueError('Report must be outside all input directories')
    if out.exists():
        raise ValueError('Report exists; use a new output path')
    main_logs = sorted(session.glob('capture_*.jsonl'))
    if not main_logs:
        raise ValueError('No message logs found')
    current = read(capture / 'sources.json')
    refs, code_count = context_sources(context, current['chapter'], code)
    current_match = compare_inventory(current, refs)
    old_databases = {'messages': capture / 'observations-v2.sqlite',
                     'interactions': capture / 'interactions.sqlite', 'choices': capture / 'choices.sqlite'}
    inputs = set(old_databases.values()) | {capture / 'sources.json'} | set(session.glob('*.jsonl'))
    inputs |= {context / 'contexts.json', context / 'evidence.json'}
    before_hashes = {p: sha(p) for p in inputs}
    totals = Counter()
    segments, examples, manifests = [], [], {}
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='verify-runtime-', dir=out.parent) as temporary:
        fresh = {k: Path(temporary) / p.name for k, p in old_databases.items()}
        for main in main_logs:
            header = json.loads(main.read_bytes().splitlines()[0])
            if header.get('schema') != 2 or header.get('mode') != 'natural_play_pilot':
                raise ValueError('This verifier expects natural schema-2 capture logs')
            segment = header['session_id']
            source_path = resolve_sources(capture / 'sources.json', header['source_manifest'])
            before_hashes[source_path] = sha(source_path)
            inventory = read(source_path)
            binding = compare_inventory(inventory, refs)
            manifests[header['source_manifest']] = binding
            # Every retained source ID must still describe the identical source use.
            current_sources = {s['source_id']: s for s in current['sources']}
            if any(current_sources.get(s['source_id']) != s for s in inventory['sources']):
                raise ValueError('Current inventory changed a historical source ID')
            first = {'messages': import_log(fresh['messages'], main, source_path)}
            repeated = {'messages': import_log(fresh['messages'], main, source_path)}
            for prefix, importer in [('interactions', import_interactions), ('choices', import_choices)]:
                log = main.with_name(main.name.replace('capture_', prefix + '_', 1))
                if not log.exists():
                    raise ValueError('Required sidecar missing: ' + log.name)
                first[prefix] = importer(fresh[prefix], log, main, source_path)
                repeated[prefix] = importer(fresh[prefix], log, main, source_path)
            additions = repeated['messages']
            if any(additions[k] for k in ('new_events', 'new_observations', 'new_variants', 'updated_observations')):
                raise ValueError('Repeated message import changed data')
            if any(v for k in ('interactions', 'choices') for v in repeated[k]['new'].values()):
                raise ValueError('Repeated relation import changed data')
            pairs = {}
            counts = {}
            for kind in fresh:
                old = snapshot(old_databases[kind], segment, kind)
                new = snapshot(fresh[kind], segment, kind)
                if old != new:
                    differing = [name for name in old if old[name] != new[name]]
                    raise ValueError(f'{kind} changed during migration: {differing}')
                pairs[kind] = old, new
                counts[kind] = {table: len(rows) for table, rows in new.items()}
            bodies = [json.loads(dict(pairs['messages'][1]['variants'])[row[2]])
                      for row in pairs['messages'][1]['observations']]
            totals.update(messages=len(bodies), unknown_sources=sum(b['occurrence_id'] is None for b in bodies),
                          smallfaces=sum(len(b.get('smallfaces', [])) for b in bodies),
                          interactions=counts['interactions']['interactions'], choices=counts['choices']['choices'])
            for mid in (159, 196, 203, 214):
                example = projected_example(*pairs['messages'], segment, mid, inventory, pairs['interactions'][1])
                if example is not None:
                    examples.append(example)
            segments.append(dict(segment_id=segment, run_id=header['run_id'],
                                 source_manifest=header['source_manifest'], collector_sha256=header['collector_sha256'],
                                 first_import=first, repeated_import=repeated, compared_rows=counts,
                                 all_compared_rows_equal=True))
    if any(sha(p) != digest for p, digest in before_hashes.items()):
        raise ValueError('An input changed during verification')
    report = dict(schema=1, scope='legacy_schema2_three_stream_readers_and_context_identity',
                  chapter=current['chapter'], current_inventory_sha256=sha(capture / 'sources.json'),
                  current_inventory=current_match, historical_inventories=manifests,
                  source_files_checked=code_count, actual_source_hashes_checked=code is not None,
                  totals=dict(totals), segments=segments, examples=examples,
                  input_files_unchanged=True, exact_database_rows_equal=True,
                  limits=['No new gameplay or chapter coverage is established.',
                          'Unknown sources and speaker judgments remain unchanged.',
                          'Web attributes and human-review decisions are not migrated by this verifier.'])
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'session', 'context', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--code', type=Path, help='Optional original GML root with chN directories; checked read-only')
    args = parser.parse_args()
    report = verify(args.capture, args.session, args.context, args.out, args.code)
    print(json.dumps({k: report[k] for k in ('totals', 'source_files_checked', 'input_files_unchanged',
                                          'exact_database_rows_equal')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
