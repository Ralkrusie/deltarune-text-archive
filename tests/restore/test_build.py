import json
from pathlib import Path
import tempfile
import unittest
from tools.restore.build import build, PROJECT


class LocalBuildTests(unittest.TestCase):
    def setUp(self):
        (PROJECT / 'local').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=PROJECT / 'local')
        self.root = Path(self.tmp.name)
        self.review = self.root / 'input'
        self.review.mkdir()
        self.data = dict(schema=1, sessions=[dict(id='s')], assets={}, rows=[dict(id='s:1', partition='p', variant='v', body={}, view={})])
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        (self.review / 'data.js').write_text('window.REVIEW_DATA=' + json.dumps(self.data) + ';', encoding='utf-8')

    def test_generated_review_only_and_immutable_input(self):
        raw = (self.review / 'data.js').read_bytes()
        template = PROJECT / 'tools/runtime/review_web/review.js'
        original = template.read_bytes()
        out = self.root / 'lab'
        build(self.review, out)
        self.assertEqual((self.review / 'data.js').read_bytes(), raw)
        self.assertEqual(template.read_bytes(), original)
        self.assertIn('window.mountReviewPreview(r)', (out / 'review.js').read_text(encoding='utf-8'))
        self.assertTrue((out / 'index.html').is_file())
        self.assertTrue((out / 'review.html').is_file())
        with self.assertRaises(ValueError):
            build(self.review, out)

    def test_rejects_public_output_and_unsafe_assets(self):
        with self.assertRaisesRegex(ValueError, 'below this project local'):
            build(self.review, PROJECT / 'dist/restore-test')
        self.data['assets'] = {'../outside.png': 'bad'}
        self.write()
        with self.assertRaisesRegex(ValueError, 'Invalid asset'):
            build(self.review, self.root / 'invalid')
        self.assertFalse((self.root / 'invalid').exists())

    def test_mismatched_frame_fails_before_output(self):
        (self.review / 'assets').mkdir()
        (self.review / 'assets/spr_face_0.png').write_bytes(b'wrong frame')
        self.data['assets'] = {'spr_face_0.png': '0'*64}
        self.write()
        with self.assertRaisesRegex(ValueError, 'Asset hash'):
            build(self.review, self.root / 'invalid')
