"""Portable launcher file operations; no real game process is started."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.runtime.launcher import collect, load_install, save_roots, under, cleanup_archived


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.install = self.root / 'participant copy'
        self.install.mkdir()
        (self.install / 'game').mkdir()
        (self.install / 'game/DELTARUNE.exe').write_bytes(b'not an executable; no process test')
        self.profile = self.root / 'isolated logs'
        self.profile.mkdir()
        self.run, self.segment = '1' * 32, '2' * 32
        self.inventory = dict(schema=1, chapter=2, package_sha256='a' * 64,
                              test_modifications={'party_max_hp': 999}, face_entities={}, sources=[
                                  dict(source_id=1, occurrence_id='occurrence:' + 'b' * 32,
                                       key='test_key', chapter=2)])
        self.write_json(self.install / 'sources.json', self.inventory)
        self.source_hash = hashlib.sha256((self.install / 'sources.json').read_bytes()).hexdigest()
        self.meta = dict(schema=1, kind='portable_runtime_capture', chapters=[2], language='en',
                         profile='DELTARUNE_CAPTURE_EN_FULL_D203', startup='game/DELTARUNE.exe',
                         source_manifest=self.source_hash, collector_sha256='c' * 64,
                         outputs={'game/DELTARUNE.exe': hashlib.sha256(
                             (self.install / 'game/DELTARUNE.exe').read_bytes()).hexdigest()})
        self.write_json(self.install / 'capture.json', self.meta)

    def tearDown(self):
        self.temp.cleanup()

    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def logs(self):
        binding = dict(run_id=self.run, session_id=self.segment, source_manifest=self.source_hash,
                       collector_sha256='c' * 64, mode='natural_play_pilot', kind='header')
        message = dict(seq=1, kind='observation', message_id=1, page=0, writer_id=100,
                       language='en', stage='page_enter', channel='obj_writer', text='* Hello.',
                       source_id=1, room_name='room_example', io_failed=False)
        attributes = dict(seq=2, kind='attributes', message_id=1, page=0, writer_id=100,
                          index_space='formatted_mystring_1based', formatted_text='* Hello.',
                          identity_states=[], identity_spans=[], assets=[], overflow=False,
                          telemetry={'glyphs_consumed': True}, reason='page_end')
        rows = {
            'capture': [dict(binding, schema=2, test_modifications={'party_max_hp': 999}), message, attributes],
            'interactions': [dict(binding, schema=1, seq=1, io_failed=False),
                             dict(message, seq=2, kind='message_link', interaction_id=0, relation='no_proven_interaction')],
            'choices': [dict(binding, schema=1, seq=1, io_failed=False),
                        dict(message, seq=2, kind='message_link', choice_id=0, relation='no_proven_choice')],
        }
        for stream, records in rows.items():
            name = f'{stream}_{self.run}_{self.segment}.jsonl'
            (self.profile / name).write_text(''.join(json.dumps(r) + '\n' for r in records), encoding='utf-8')
        return self.profile / f'capture_{self.run}_{self.segment}.jsonl'

    def test_relative_install_validates_after_directory_move(self):
        renamed = self.root / 'another computer path'
        self.install.rename(renamed)
        self.assertEqual(load_install(renamed)['source_manifest'], self.source_hash)

    def test_changed_game_or_sources_rejected(self):
        game = self.install / 'game/DELTARUNE.exe'
        original = game.read_bytes()
        game.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'game was changed'):
            load_install(self.install)
        game.write_bytes(original)
        (self.install / 'sources.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            load_install(self.install)

    def test_profile_and_manifest_path_escape_rejected(self):
        self.meta['profile'] = 'DELTARUNE'
        self.write_json(self.install / 'capture.json', self.meta)
        with self.assertRaisesRegex(ValueError, 'profile'):
            load_install(self.install)
        for value in ('../outside', 'E:/outside', 'folder\\outside'):
            with self.assertRaises(ValueError):
                under(self.install, value)

    def test_save_roots_use_participant_environment(self):
        with patch.dict('os.environ', {'LOCALAPPDATA': str(self.root / 'user/AppData/Local'),
                                      'USERPROFILE': str(self.root / 'user')}):
            roots = save_roots('DELTARUNE_CAPTURE_EN_FULL_D203')
        self.assertEqual(roots, [(self.root / 'user/AppData/Local/DELTARUNE_CAPTURE_EN_FULL_D203').resolve()])

    def test_collect_only_three_streams_and_preserves_originals(self):
        self.logs()
        (self.profile / 'filech2_0').write_text('private save', encoding='utf-8')
        (self.profile / 'runner.log').write_text('private machine path', encoding='utf-8')
        (self.profile / ('capture_' + '9' * 32 + '_' + self.segment + '.jsonl')).write_text('other run')
        before = {p.name: p.read_bytes() for p in self.profile.iterdir()}
        report = collect(self.install, self.run, [self.profile], cleanup=False)
        self.assertEqual(report['status'], 'exported')
        self.assertEqual(report['summary']['messages'], 1)
        with zipfile.ZipFile(report['export_file']) as archive:
            self.assertEqual(len(archive.namelist()), 4)
            self.assertFalse(any('private' in n for n in archive.namelist()))
        after = {p.name: p.read_bytes() for p in self.profile.iterdir()}
        self.assertEqual(before, after)
        repeated = collect(self.install, self.run, [self.profile], cleanup=False)
        self.assertEqual(report['bundle_id'], repeated['bundle_id'])

    def test_collect_without_ch2_logs_is_explicit(self):
        result = collect(self.install, self.run, [self.profile])
        self.assertEqual(result['status'], 'no_ch2_capture')
        self.assertEqual(result['messages'], 0)

    def test_collect_rejects_changed_existing_bytes(self):
        source = self.logs()
        collect(self.install, self.run, [self.profile], cleanup=False)
        source.write_bytes(source.read_bytes().replace(b'Hello.', b'Changed'))
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            collect(self.install, self.run, [self.profile])

    def test_collect_rejects_another_build(self):
        source = self.logs()
        source.write_bytes(source.read_bytes().replace(('c' * 64).encode(), ('d' * 64).encode()))
        with self.assertRaisesRegex(ValueError, 'capture build'):
            collect(self.install, self.run, [self.profile])

    def test_cleanup_preserves_zip_saves_and_other_runs_and_recovery_reuses_zip(self):
        self.logs()
        save = self.profile / 'filech2_0'; save.write_bytes(b'keep save')
        other = self.profile / ('capture_' + '9' * 32 + '_' + self.segment + '.jsonl')
        other.write_bytes(b'other run')
        result = collect(self.install, self.run, [self.profile])
        self.assertEqual(result['cleanup']['deleted_jsonl'], 6)
        self.assertEqual(save.read_bytes(), b'keep save')
        self.assertEqual(other.read_bytes(), b'other run')
        self.assertFalse(list((self.install / 'sessions' / self.run).glob('*.jsonl')))
        self.assertEqual(len(list((self.install / 'exports').glob('*.zip'))), 1)
        again = collect(self.install, self.run, [self.profile])
        self.assertEqual(result['export_file'], again['export_file'])
        self.assertEqual(again['summary']['messages'], 1)
        self.assertEqual(again['cleanup']['deleted_jsonl'], 3)

    def test_export_failure_keeps_raw_records(self):
        src = self.logs()
        with patch('tools.runtime.bundles.export_bundle', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                collect(self.install, self.run, [self.profile])
        self.assertTrue(src.exists())
        self.assertEqual(len(list((self.install / 'sessions' / self.run).glob('*.jsonl'))), 3)

    def test_corrupt_archive_refuses_cleanup(self):
        self.logs()
        result = collect(self.install, self.run, [self.profile], cleanup=False)
        Path(result['export_file']).write_bytes(b'bad zip')
        with self.assertRaises((ValueError, zipfile.BadZipFile)):
            cleanup_archived(self.install, self.run, Path(result['export_file']), [self.profile])
        self.assertEqual(len(list(self.profile.glob('*.jsonl'))), 3)

    def test_changed_source_after_export_is_not_deleted(self):
        src = self.logs()
        result = collect(self.install, self.run, [self.profile], cleanup=False)
        src.write_bytes(src.read_bytes() + b'new bytes')
        status = cleanup_archived(self.install, self.run, Path(result['export_file']), [self.profile])
        self.assertEqual(status['deleted_jsonl'], 0)
        self.assertTrue(status['warnings'])
        self.assertEqual(len(list(self.profile.glob('*.jsonl'))), 3)

    def test_portable_paths_follow_install_after_move(self):
        roots = save_roots(self.meta['profile'], self.install)
        self.assertEqual(roots, [self.install / 'saves' / self.meta['profile']])

    def test_cleaned_partial_export_can_be_extended_without_losing_prior_zip(self):
        main = self.logs()
        full = {p.name: p.read_bytes() for p in self.profile.glob('*.jsonl')}
        main.write_bytes(full[main.name][:-5])
        partial = collect(self.install, self.run, [self.profile])
        self.assertTrue(partial['summary']['warnings'])
        for name, raw in full.items():
            (self.profile / name).write_bytes(raw)
        complete = collect(self.install, self.run, [self.profile])
        self.assertNotEqual(partial['bundle_id'], complete['bundle_id'])
        self.assertTrue(Path(partial['export_file']).is_file())
        self.assertFalse(complete['summary']['warnings'])
        self.assertFalse(list(self.profile.glob('*.jsonl')))

    def test_migration_moves_game_and_copies_only_saves(self):
        from tools.runtime.layout import migrate_capture
        self.logs()
        (self.profile / 'filech2_0').write_bytes(b'progress')
        (self.profile / 'dr.ini').write_bytes(b'config')
        tool = self.root / 'DialogueCapture'; tool.mkdir()
        source = self.install
        result = migrate_capture(source, tool, self.profile)
        self.assertFalse(source.exists())
        target = tool / 'capture'
        self.assertEqual(load_install(target)['save_layout'], 'local_appdata_v1')
        local = target / 'saves' / self.meta['profile']
        self.assertEqual((local / 'filech2_0').read_bytes(), b'progress')
        self.assertFalse(list(local.glob('*.jsonl')))
        self.assertTrue((self.profile / 'filech2_0').exists())
        self.assertEqual(len(result['copied_saves']), 2)

    def test_migration_existing_destination_or_conflicting_save_is_preserved(self):
        from tools.runtime.layout import migrate_capture
        tool = self.root / 'DialogueCapture'; (tool / 'capture').mkdir(parents=True)
        with self.assertRaises(ValueError):
            migrate_capture(self.install, tool, self.profile)
        tool2 = self.root / 'another tool'; tool2.mkdir()
        (self.profile / 'filech2_0').write_bytes(b'old progress')
        local = self.install / 'saves' / self.meta['profile']; local.mkdir(parents=True)
        (local / 'filech2_0').write_bytes(b'new progress')
        with self.assertRaisesRegex(ValueError, '存档已存在'):
            migrate_capture(self.install, tool2, self.profile)
        self.assertEqual((local / 'filech2_0').read_bytes(), b'new progress')


if __name__ == '__main__':
    unittest.main()
