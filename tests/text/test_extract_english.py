import json
from pathlib import Path
import tempfile
import unittest

from tools.text.extract_english import aggregate, extract, scan
from tools.text.import_texts import sha


KEY = 'obj_test_slash_Step_0_gml_1_0'


class EnglishExtractionTests(unittest.TestCase):
    def temporary(self):
        parent = Path(__file__).resolve().parents[2]/'build'
        parent.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(prefix='english-test-', dir=parent)

    def test_lexical_calls_and_exact_escapes(self):
        text = ('// msgsetloc(0, "fake", "' + KEY + '");\n'
                'label = "msgsetloc(0, fake, fake)";\n'
                'msgsetloc(0, "* A\\nB\\\\E1^1/", "' + KEY + '");\n'
                'stringsetsubloc("~1%", string(123), "other_slash_Other_1_gml_2_0");')
        records, unresolved = scan(text, 'example.gml')
        self.assertFalse(unresolved)
        self.assertEqual([r['english'] for r in records], ['* A\nB\\E1^1/', '~1%'])
        self.assertEqual(records[0]['line'], 3)

    def test_different_values_require_exact_reviewed_signature(self):
        records = [{'key': KEY, 'file': 'a.gml', 'call': 'msgsetloc', 'english': value}
                   for value in ('first', 'second')]
        table, conflicts, _ = aggregate(records, {})
        self.assertNotIn(KEY, table)
        self.assertEqual(len(conflicts), 1)
        choice = {KEY: {'file': 'a.gml', 'call': 'msgsetloc', 'english_sha256': sha(b'second'),
                        'variants_sha256': [sha(b'first'), sha(b'second')]}}
        table, conflicts, applied = aggregate(records, choice)
        self.assertEqual(table, {KEY: 'second'})
        self.assertFalse(conflicts)
        self.assertEqual(applied, [KEY])
        added = records + [{**records[0], 'english': 'unexpected new variant'}]
        self.assertTrue(aggregate(added, choice)[1])
        choice[KEY]['file'] = 'other.gml'
        self.assertTrue(aggregate(records, choice)[1])

    def test_dynamic_default_is_unresolved(self):
        records, unresolved = scan(f'msgsetloc(0, variable, "{KEY}");', 'test.gml')
        self.assertFalse(records)
        self.assertEqual(unresolved[0]['key'], KEY)

    def test_extract_all_chapters_and_refuse_overwrite(self):
        with self.temporary() as temp:
            root = Path(temp)
            for chapter in range(2, 6):
                path = root/'code'/f'ch{chapter}'
                path.mkdir(parents=True)
                (path/'test.gml').write_text(f'msgsetloc(0, "", "{KEY}");', encoding='utf-8')
            report = {}
            extract(root/'code', root/'out', {}, report)
            for chapter in range(2, 6):
                self.assertEqual(json.loads((root/'out'/f'ch{chapter}/lang_en.json').read_text()), {KEY: ''})
            self.assertEqual(len(report['chapters']), 4)
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                extract(root/'code', root/'out', {}, {})

    def test_conflict_writes_no_partial_language_output(self):
        with self.temporary() as temp:
            root = Path(temp)
            for chapter in range(2, 6):
                path = root/'code'/f'ch{chapter}'
                path.mkdir(parents=True)
                (path/'test.gml').write_text(f'msgsetloc(0, "first", "{KEY}");\n'
                                            f'msgsetloc(0, "second", "{KEY}");', encoding='utf-8')
            report = {}
            with self.assertRaisesRegex(ValueError, 'Unresolved'):
                extract(root/'code', root/'out', {}, report)
            self.assertFalse((root/'out').exists())
            self.assertEqual(len(report['chapters'][0]['conflicts']), 1)


if __name__ == '__main__':
    unittest.main()
