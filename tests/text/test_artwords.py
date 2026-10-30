import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from tools.text.artwords import project


class ArtwordTests(unittest.TestCase):
    def test_binding_and_changed_input(self):
        raw = '* \\O0!/'
        entry = {'chapter': 3, 'key': 'first', 'fields': {'en': {
            'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(), 'slots': {'0': 'LOVE'}}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'words.json'
            path.write_text(json.dumps({'schema': 1, 'entries': [entry]}), encoding='utf8')
            rows = [{'key': 'first', 'en': raw}, {'key': 'second', 'en': raw}]
            self.assertEqual(project(path, 3, rows), {'first': {'en': {'0': 'LOVE'}}})
            self.assertEqual(project(path, 4, rows), {})
            rows[0]['en'] += 'changed'
            self.assertEqual(project(path, 3, rows), {})

    def test_catalog(self):
        path = Path(__file__).resolve().parents[2] / 'config/text/artwords.json'
        data = json.loads(path.read_text(encoding='utf8'))
        self.assertEqual(len(data['entries']), 72)
        for entry in data['entries']:
            self.assertTrue(entry['evidence'])
            for binding in entry['fields'].values():
                self.assertRegex(binding['raw_sha256'], r'^[0-9a-f]{64}$')
                self.assertTrue(binding['slots'])

    def test_reviewed_lettering_is_language_specific(self):
        path = Path(__file__).resolve().parents[2] / 'config/text/artwords.json'
        entries = json.loads(path.read_text(encoding='utf8'))['entries']
        tv = next(e for e in entries if e['key'] == 'obj_ch3_GSA01G_slash_Step_0_gml_175_0')
        self.assertEqual(tv['fields']['en']['slots']['2'], 'TV TiME!')
        self.assertEqual(tv['fields']['zh_default']['slots']['2'], 'TV时间！')
        self.assertEqual(tv['fields']['ja']['slots']['2'], "IT'S!! TV!! TiME!!!")
        resumes = next(e for e in entries if e['key'] == 'obj_npc_sign_slash_Other_10_gml_31_0')
        self.assertEqual(resumes['fields']['en']['slots']['1'], 'Résumés')
