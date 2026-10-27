import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.runtime.bundles import export_bundle, receive_bundle
from tools.runtime.legacy.store import digest


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sources = self.root / 'sources.json'
        self.sources.write_text(json.dumps(dict(schema=1, chapter=2, package_sha256='a'*64,
            test_modifications={'party_max_hp':999}, face_entities={}, sources=[dict(source_id=1,
                occurrence_id='occurrence:'+'b'*32, key='test_key', chapter=2)])), encoding='utf-8')
        import hashlib
        self.source_hash = hashlib.sha256(self.sources.read_bytes()).hexdigest()
        self.library = self.root / 'library'

    def tearDown(self):
        self.temp.cleanup()

    def session(self, run='1'*32, sid='2'*32, text='* Hello.', collector='c'*64):
        target = self.root / (run + sid)
        target.mkdir(exist_ok=True)
        binding = dict(run_id=run, session_id=sid, source_manifest=self.source_hash,
                       collector_sha256=collector, mode='natural_play_pilot', kind='header')
        message = dict(seq=1, kind='observation', message_id=1, page=0, writer_id=100,
                       language='en', stage='page_enter', channel='obj_writer', text=text,
                       source_id=1, room_name='room_example', io_failed=False)
        attributes = dict(seq=2, kind='attributes', message_id=1, page=0, writer_id=100,
                          index_space='formatted_mystring_1based', formatted_text=text,
                          identity_states=[], identity_spans=[], assets=[], overflow=False,
                          telemetry={'glyphs_consumed':True}, reason='page_end')
        rows = {
            'capture': [dict(binding, schema=2, test_modifications={'party_max_hp':999}), message, attributes],
            'interactions': [dict(binding, schema=1, seq=1, io_failed=False),
                dict(message, seq=2, kind='message_link', interaction_id=0, relation='no_proven_interaction')],
            'choices': [dict(binding, schema=1, seq=1, io_failed=False),
                dict(message, seq=2, kind='message_link', choice_id=0, relation='no_proven_choice')],
        }
        for stream, records in rows.items():
            (target / f'{stream}_{run}_{sid}.jsonl').write_bytes(
                ('\n'.join(json.dumps(r) for r in records)+'\n').encode())
        return target

    def export(self, target, name='submission.zip'):
        path = self.root / name
        result = export_bundle(target, self.sources, path)
        return path, result

    def index_counts(self):
        db = sqlite3.connect(self.library / 'index.sqlite')
        try:
            return [db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                    for table in ('bundles','sessions','variants','observations')]
        finally:
            db.close()

    def rewrite_zip(self, original, name, mutate):
        with zipfile.ZipFile(original) as archive:
            items = {n: archive.read(n) for n in archive.namelist()}
        mutate(items)
        out = self.root / name
        with zipfile.ZipFile(out, 'w') as archive:
            for key, value in items.items():
                archive.writestr(key, value)
        return out

    def test_export_whitelist_and_idempotent_receive(self):
        session = self.session()
        (session/'filech2_0').write_text('private save')
        (session/'runner.log').write_text('private machine path')
        package, exported = self.export(session)
        with zipfile.ZipFile(package) as archive:
            self.assertEqual(len(archive.namelist()), 4)
            self.assertNotIn(b'private', archive.read('manifest.json'))
        self.assertEqual(exported['summary']['messages'], 1)
        first = receive_bundle(package, self.sources, self.library)
        second = receive_bundle(package, self.sources, self.library)
        self.assertTrue(first['new_bundle'])
        self.assertFalse(second['new_bundle'])
        self.assertTrue(second['duplicate'])
        self.assertEqual(first['library_totals'], second['library_totals'])
        self.assertEqual(self.index_counts(), [1,1,1,1])

    def test_independent_observers_share_variant(self):
        a, _ = self.export(self.session(), 'a.zip')
        b, _ = self.export(self.session(run='3'*32, sid='4'*32), 'b.zip')
        receive_bundle(a, self.sources, self.library)
        result = receive_bundle(b, self.sources, self.library)
        self.assertEqual(result['library_totals']['messages'], 2)
        self.assertEqual(result['library_totals']['variants'], 1)

    def test_real_difference_retained_and_collector_partitioned(self):
        for i, (text, collector) in enumerate([('* Hello.','c'*64),('* Different.','c'*64),('* Hello.','d'*64)]):
            package, _ = self.export(self.session(run=str(i+1)*32, sid=str(i+4)*32, text=text, collector=collector), str(i)+'.zip')
            result = receive_bundle(package, self.sources, self.library)
        self.assertEqual(result['library_totals']['messages'], 3)
        self.assertEqual(result['library_totals']['variants'], 3)
        self.assertEqual(result['library_totals']['partitions'], 2)

    def test_changed_existing_session_is_rejected_atomically(self):
        a, _ = self.export(self.session(), 'a.zip')
        receive_bundle(a, self.sources, self.library)
        before = self.index_counts()
        b, _ = self.export(self.session(text='* Altered.'), 'b.zip')
        with self.assertRaisesRegex(ValueError, 'session changed'):
            receive_bundle(b, self.sources, self.library)
        self.assertEqual(before, self.index_counts())
        self.assertEqual(len(list((self.library/'received').iterdir())), 1)

    def test_source_mismatch_is_rejected_before_index(self):
        package, _ = self.export(self.session())
        other = self.root / 'other.json'
        other.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'inventory not found'):
            receive_bundle(package, other, self.library)
        self.assertFalse((self.library/'index.sqlite').exists())

    def test_sidecar_binding_mismatch_rejected(self):
        session = self.session()
        log = next(session.glob('choices_*'))
        rows = log.read_text().splitlines()
        header = json.loads(rows[0]); header['collector_sha256'] = 'e'*64
        log.write_text('\n'.join([json.dumps(header),*rows[1:]])+'\n')
        with self.assertRaisesRegex(ValueError, 'provenance mismatch'):
            self.export(session)

    def test_truncated_final_event_is_saved_with_warning(self):
        session = self.session()
        log = next(session.glob('capture_*'))
        with log.open('ab') as out:out.write(b'{"seq":3')
        package, exported = self.export(session)
        self.assertIn('message_tail_incomplete', str(exported['summary']['warnings']))
        received = receive_bundle(package, self.sources, self.library)
        self.assertEqual(received['library_totals']['messages'], 1)
        saved = self.library / 'received' / received['bundle_id'] / 'logs' / log.name
        self.assertEqual(saved.read_bytes(), log.read_bytes())

    def test_interior_corruption_rejected(self):
        session = self.session()
        log = next(session.glob('capture_*'))
        with log.open('ab') as out:out.write(b'{bad}\n')
        with self.assertRaises(ValueError):self.export(session)

    def test_duplicate_json_key_rejected(self):
        session = self.session()
        log = next(session.glob('capture_*'))
        raw = log.read_bytes().replace(b'"schema": 2', b'"schema": 1,"schema": 2')
        log.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):self.export(session)

    def test_zip_path_traversal_and_tamper_rejected(self):
        package, _ = self.export(self.session())
        bad = self.rewrite_zip(package, 'path.zip', lambda d:d.update({'../outside':'bad'}))
        with self.assertRaisesRegex(ValueError, 'Forbidden ZIP'):receive_bundle(bad,self.sources,self.library)
        def alter(items):
            name = next(n for n in items if n.startswith('capture_'))
            items[name] += b'\n'
        bad = self.rewrite_zip(package, 'tamper.zip', alter)
        with self.assertRaisesRegex(ValueError, 'log digest'):receive_bundle(bad,self.sources,self.library)
        self.assertFalse((self.root/'outside').exists())
        self.assertFalse((self.library/'index.sqlite').exists())

    def test_manifest_summary_cannot_claim_extra_coverage(self):
        package, _ = self.export(self.session())
        def alter(items):
            manifest = json.loads(items['manifest.json'])
            manifest['summary']['messages'] = 1000
            manifest.pop('bundle_id')
            manifest['bundle_id'] = digest(manifest)
            items['manifest.json'] = json.dumps(manifest).encode()
        bad = self.rewrite_zip(package, 'counts.zip', alter)
        with self.assertRaisesRegex(ValueError, 'summary differs'):receive_bundle(bad,self.sources,self.library)
        self.assertFalse((self.library/'index.sqlite').exists())

    def test_multiple_segments_keep_local_message_ids(self):
        a = self.session()
        b = self.session(sid='5'*32)
        for log in b.glob('*.jsonl'):(a/log.name).write_bytes(log.read_bytes())
        package, _ = self.export(a)
        result = receive_bundle(package, self.sources, self.library)
        self.assertEqual(result['library_totals']['messages'], 2)
        self.assertEqual(result['library_totals']['sessions'], 2)
        self.assertEqual(result['library_totals']['variants'], 1)

    def test_missing_stream_is_explicit(self):
        session = self.session()
        next(session.glob('choices_*')).unlink()
        package, exported = self.export(session)
        self.assertIn('missing_choices_stream', str(exported['summary']['warnings']))
        result = receive_bundle(package, self.sources, self.library)
        self.assertEqual(result['library_totals']['messages'], 1)

    def test_unknown_choice_continuation_is_rejected(self):
        session = self.session()
        log = next(session.glob('choices_*'))
        records = [json.loads(line) for line in log.read_text().splitlines()]
        records[1]['choice_id'] = 7
        records[1]['relation'] = 'explicit_choice_continuation'
        log.write_text('\n'.join(json.dumps(r) for r in records)+'\n')
        with self.assertRaisesRegex(ValueError, 'Continuation without confirmation'):self.export(session)

    def test_partial_last_event_can_complete_without_losing_old_evidence(self):
        session = self.session()
        log = next(session.glob('capture_*'))
        complete = log.read_bytes()
        pieces = complete.splitlines(keepends=True)
        log.write_bytes(b''.join(pieces[:-1]) + pieces[-1][:23])
        first, _ = self.export(session, 'partial.zip')
        original = receive_bundle(first, self.sources, self.library)
        self.assertEqual(original['summary']['segment_summaries'][0]['streams']['messages']['unclosed_pages'], 1)
        old_bytes = log.read_bytes()
        log.write_bytes(complete)
        second, _ = self.export(session, 'completed.zip')
        result = receive_bundle(second, self.sources, self.library)
        self.assertEqual(result['updated_sessions'], 1)
        self.assertEqual(result['new_sessions'], 0)
        self.assertEqual(result['library_totals']['messages'], 1)
        self.assertEqual(result['library_totals']['variants'], 1)
        archived = self.library/'received'/original['bundle_id']/'logs'/log.name
        self.assertEqual(archived.read_bytes(), old_bytes)
        again = receive_bundle(first, self.sources, self.library)
        self.assertEqual(again['older_sessions'], 1)
        self.assertEqual(again['updated_sessions'], 0)
        self.assertEqual(again['library_totals'], result['library_totals'])

    def test_late_sidecar_is_added_to_existing_session(self):
        session = self.session()
        log = next(session.glob('choices_*')); original = log.read_bytes(); log.unlink()
        first, _ = self.export(session, 'without-choice.zip')
        receive_bundle(first, self.sources, self.library)
        log.write_bytes(original)
        second, _ = self.export(session, 'with-choice.zip')
        result = receive_bundle(second, self.sources, self.library)
        self.assertEqual(result['updated_sessions'], 1)
        self.assertEqual(result['summary']['warnings'], [])
        self.assertEqual(result['library_totals']['messages'], 1)

    def test_whole_log_append_updates_counts_once(self):
        session = self.session()
        first, _ = self.export(session, 'first.zip')
        receive_bundle(first, self.sources, self.library)
        for log in session.glob('*.jsonl'):
            rows = [json.loads(row) for row in log.read_text().splitlines()]
            additions = rows[1:] if log.name.startswith('capture_') else [rows[1]]
            for i, row in enumerate(additions, rows[-1]['seq']+1):
                row.update(seq=i, message_id=2, page=1)
            with log.open('ab') as out:
                out.write(('\n'.join(json.dumps(row) for row in additions)+'\n').encode())
        second, _ = self.export(session, 'second.zip')
        result = receive_bundle(second, self.sources, self.library)
        self.assertEqual(result['updated_sessions'], 1)
        self.assertEqual(result['library_totals']['messages'], 2)
        self.assertEqual(result['library_totals']['variants'], 1)
        repeated = receive_bundle(second, self.sources, self.library)
        self.assertEqual(repeated['library_totals'], result['library_totals'])
        self.assertEqual(repeated['updated_sessions'], 0)

    def test_transaction_failure_preserves_evidence_and_retries(self):
        first, _ = self.export(self.session(), 'first.zip')
        receive_bundle(first, self.sources, self.library)
        before = self.index_counts()
        second, exported = self.export(self.session(run='3'*32, sid='4'*32), 'second.zip')
        db = sqlite3.connect(self.library/'index.sqlite')
        try:
            db.execute("CREATE TRIGGER simulated_failure BEFORE INSERT ON observations BEGIN SELECT RAISE(ABORT, 'simulated failure'); END")
            db.commit()
        finally:db.close()
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'simulated failure'):
            receive_bundle(second, self.sources, self.library)
        self.assertEqual(self.index_counts(), before)
        evidence = self.library/'received'/exported['bundle_id']
        self.assertTrue((evidence/'manifest.json').exists())
        self.assertEqual(len(list((evidence/'logs').glob('*.jsonl'))), 3)
        db = sqlite3.connect(self.library/'index.sqlite')
        try:
            db.execute('DROP TRIGGER simulated_failure'); db.commit()
        finally:db.close()
        retried = receive_bundle(second, self.sources, self.library)
        self.assertEqual(retried['new_sessions'], 1)
        self.assertEqual(retried['library_totals']['messages'], 2)

    def test_export_race_does_not_delete_other_export(self):
        session = self.session(); out = self.root/'race.zip'
        from tools.runtime import bundles
        real_validate = bundles._validate
        def raced(*args, **kwargs):
            result = real_validate(*args, **kwargs)
            out.write_bytes(b'another writer owns this output')
            return result
        with patch.object(bundles, '_validate', side_effect=raced):
            with self.assertRaises(FileExistsError):export_bundle(session, self.sources, out)
        self.assertEqual(out.read_bytes(), b'another writer owns this output')


if __name__ == '__main__':
    unittest.main()
