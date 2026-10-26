import json
from pathlib import Path
import sys
import shutil
import uuid
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from import_texts import CHAPTERS, FILES, language, run
from prepare_inputs import prepare, GAME_NAMES
from verify_migration import audit
from build_site_data import build


class TextImport(unittest.TestCase):
    def setUp(self):
        parent = (Path(__file__).resolve().parents[1] / 'build/tests').resolve()
        parent.mkdir(parents=True, exist_ok=True)
        self.root = parent / uuid.uuid4().hex
        self.root.mkdir()
        self.addCleanup(self.clean_root, parent)
        self.input = self.root / 'input'
        self.out = self.root / 'output'
        for ch in CHAPTERS:
            (self.input / f'ch{ch}').mkdir(parents=True)
            for field, filename in FILES.items():
                values = {'date': 'fixture', 'same': '', 'controls': '\\E1* Synthetic\n\\I2 ~1/%'}
                if field == 'ja':
                    del values['controls']
                    values['ja_only'] = '合成テスト'
                if field == 'zh_names':
                    values['controls'] = '合成名称'
                (self.input / f'ch{ch}' / filename).write_text(json.dumps(values), encoding='utf-8-sig')

    def clean_root(self, parent):
        if not self.root.resolve().is_relative_to(parent) or self.root.resolve() == parent:
            raise ValueError('Test cleanup escaped workspace')
        shutil.rmtree(self.root)

    def test_union_controls_empty_missing_and_variants(self):
        manifest = run(self.input, self.out)
        self.assertEqual(manifest['total_rows'], 15)
        data = json.loads((self.out / 'trilingual_chapter1.json').read_text(encoding='utf-8'))
        rows = {r['key']: r for r in data['lines']}
        self.assertNotIn('date', rows)
        self.assertEqual(rows['same']['en'], '')
        self.assertEqual(rows['same']['missing'], [])
        self.assertEqual(rows['controls']['en'], '\\E1* Synthetic\n\\I2 ~1/%')
        self.assertIsNone(rows['controls']['ja'])
        self.assertEqual(rows['controls']['missing'], ['ja'])
        self.assertEqual(rows['controls']['zh_variant'], 'differs')
        self.assertIsNone(rows['ja_only']['en'])
        self.assertEqual(data['stats']['missing_by_language']['zh_names'], 1)

    def test_repeated_build_is_identical_and_read_only(self):
        before = {p: p.read_bytes() for p in self.input.rglob('*.json')}
        run(self.input, self.out)
        first = {p.name: p.read_bytes() for p in self.out.iterdir()}
        run(self.input, self.out)
        self.assertEqual(first, {p.name: p.read_bytes() for p in self.out.iterdir()})
        self.assertTrue(all(p.read_bytes() == raw for p, raw in before.items()))

    def test_bad_json_values_duplicates_and_encoding(self):
        for raw in [b'{"a":"x","a":"y"}', b'[]', b'{"a":null}', b'{"a":3}',
                    b'{"a":{}}', b'{"a":true}', b'{"":"text"}', b'{', b'\xff', b'{"date":NaN}']:
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'fixture.json'):
                language(raw, 'fixture.json')

    def test_late_invalid_input_preserves_previous_result(self):
        run(self.input, self.out)
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        (self.input / 'ch5/lang_zh_recruitable.json').write_text('{"bad":null}', encoding='utf-8')
        with self.assertRaises(ValueError):
            run(self.input, self.out)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.iterdir()})

    def test_missing_file_does_not_create_output(self):
        (self.input / 'ch5/lang_zh_recruitable.json').unlink()
        with self.assertRaises(FileNotFoundError):
            run(self.input, self.out)
        self.assertFalse(self.out.exists())

    def test_nested_paths_rejected(self):
        for output in [self.input, self.input / 'out', self.root]:
            with self.subTest(output=output), self.assertRaises(ValueError):
                run(self.input, output)

    def test_audit_detects_changed_output_and_cleans_temporary_copies(self):
        legacy = self.root / 'legacy'
        run(self.input, legacy)
        run(self.input, self.out)
        report_dir = self.root / 'audit'
        result = audit(legacy, self.input, self.out, report_dir)
        self.assertEqual(result['differences'], [])
        self.assertFalse(any(p.is_dir() for p in report_dir.iterdir()))
        target = self.out / 'trilingual_chapter2.json'
        data = json.loads(target.read_text(encoding='utf-8'))
        data['lines'][0]['en'] = 'silently corrupted'
        target.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'projection mismatch'):
            audit(legacy, self.input, self.out, report_dir)
        self.assertFalse(any(p.is_dir() for p in report_dir.iterdir()))

    def test_audit_detects_changed_baseline_alignment(self):
        legacy = self.root / 'legacy'
        run(self.input, legacy)
        run(self.input, self.out)
        target = legacy / 'trilingual_chapter1.json'
        data = json.loads(target.read_text(encoding='utf-8'))
        data['lines'][0]['status'] = 'incorrect'
        target.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Baseline mismatch'):
            audit(legacy, self.input, self.out, self.root / 'audit')

    def test_site_dictionary_roundtrip_and_no_local_paths(self):
        run(self.input, self.out)
        destination = self.root / 'site'
        result = build(self.out, destination)
        self.assertEqual(result['total_rows'], 15)
        for ch in CHAPTERS:
            source = json.loads((self.out / f'trilingual_chapter{ch}.json').read_text(encoding='utf-8'))
            packed = json.loads((destination / f'ch{ch}.json').read_text(encoding='utf-8'))
            for before, row in zip(source['lines'], packed['rows']):
                self.assertEqual(before['key'], row[0])
                for n, field in enumerate(packed['languages'], 1):
                    self.assertEqual(before[field], None if row[n] is None else packed['strings'][row[n]])
        self.assertNotIn(str(self.root), (destination / 'manifest.json').read_text(encoding='utf-8'))

    def test_site_build_rejects_stale_input_before_overwrite(self):
        run(self.input, self.out)
        destination = self.root / 'site'
        build(self.out, destination)
        before = {p.name: p.read_bytes() for p in destination.iterdir()}
        with (self.out / 'trilingual_chapter5.json').open('ab') as f:
            f.write(b' ')
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            build(self.out, destination)
        self.assertEqual(before, {p.name: p.read_bytes() for p in destination.iterdir()})

    def test_copier_mapping_bytes_and_overwrite_protection(self):
        english, game, out = self.root / 'english', self.root / 'game', self.root / 'prepared'
        english.mkdir()
        expected = {}
        for ch in CHAPTERS:
            lang = game / f'chapter{ch}_windows/lang'
            lang.mkdir(parents=True)
            for field, filename in FILES.items():
                raw = ('\ufeff' + json.dumps({'unique': f'{ch}/{field}'})).encode('utf-8')
                source = english / f'lang_en_ch{ch}.json' if field == 'en' else lang / GAME_NAMES[field]
                source.write_bytes(raw)
                expected[f'ch{ch}/{filename}'] = raw
        with self.assertRaisesRegex(ValueError, 'Provenance must be outside'):
            prepare(english, game, out, out / 'provenance.json')
        self.assertFalse(out.exists())
        prepare(english, game, out, self.root / 'local/provenance.json')
        self.assertTrue(all((out / rel).read_bytes() == raw for rel, raw in expected.items()))
        self.assertTrue((self.root / 'local/provenance.json').exists())
        self.assertFalse((out / 'provenance.json').exists())
        with self.assertRaises(ValueError):
            prepare(english, game, out, self.root / 'local/provenance.json')


if __name__ == '__main__':
    unittest.main()
