"""Check the public example from a copy containing no game inputs or legacy tree."""
import json
import re
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from build_demo import WEB_FILES, build_demo, demo_markup
from import_texts import FILES, sha

ROOT = Path(__file__).resolve().parents[1]


class DemoBuildTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT/'build'
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='demo-test-', dir=parent)
        self.root = Path(self.temp.name).resolve()
        if not self.root.is_relative_to(parent.resolve()):
            raise ValueError('Test directory escaped build')
        self.addCleanup(self.temp.cleanup)
        for name in WEB_FILES:
            target = self.root/'web'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/'web'/name, target)
        shutil.copytree(ROOT/'examples/input', self.root/'examples/input')

    def test_clean_copy_builds_and_preserves_all_language_values(self):
        site = build_demo(self.root)
        self.assertFalse((self.root/'local').exists())
        self.assertFalse((self.root/'input').exists())
        self.assertFalse((self.root/'dist').exists())
        report = json.loads((site/'demo-build.json').read_text())
        self.assertEqual(report['rows'], 40)
        for name, digest in report['files'].items():
            self.assertEqual(sha((site/name).read_bytes()), digest)
        for name, digest in report['sources'].items():
            self.assertEqual(sha((self.root/name).read_bytes()), digest)
        self.assertNotIn(str(self.root), (site/'demo-build.json').read_text())
        for ch in range(1, 6):
            pack = json.loads((site/f'data/ch{ch}.json').read_text(encoding='utf-8'))
            self.assertEqual(len(pack['rows']), 8)
            self.assertIsInstance(pack['source_files'], list)
            for field, filename in FILES.items():
                original = json.loads((self.root/f'examples/input/ch{ch}'/filename).read_text(encoding='utf-8'))
                column = pack['languages'].index(field)+1
                for row in pack['rows']:
                    actual = None if row[column] is None else pack['strings'][row[column]]
                    self.assertEqual(actual, original.get(row[0]))
        markup = (site/'index.html').read_text(encoding='utf-8')
        self.assertIn('真实台词示例', markup)
        self.assertNotIn('assets/', markup)
        self.assertNotIn('soul.js', markup)
        for script in re.findall(r'<script\b[^>]*src="([^"]+)"', markup):
            self.assertTrue((site/script).is_file(), script)
        self.assertIn('好人汉化组', markup)
        self.assertNotIn('assets/', (site/'style.css').read_text(encoding='utf-8'))
        contexts = json.loads((site/'data/contexts.json').read_text())
        manifest = json.loads((site/'data/manifest.json').read_text())
        self.assertEqual(contexts['scenes'], [])
        self.assertEqual(contexts['text_manifest_sha256'], manifest['source_manifest_sha256'])

    def test_rebuild_is_deterministic(self):
        site = build_demo(self.root)
        before = {p.relative_to(site): p.read_bytes() for p in site.rglob('*') if p.is_file()}
        build_demo(self.root)
        after = {p.relative_to(site): p.read_bytes() for p in site.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_unmanaged_files_are_preserved_and_block_rebuild(self):
        site = build_demo(self.root)
        (site/'keep.txt').write_text('keep')
        before = (site/'index.html').read_bytes()
        with self.assertRaisesRegex(ValueError, 'Unexpected demo file'):
            build_demo(self.root)
        self.assertEqual((site/'keep.txt').read_text(), 'keep')
        self.assertEqual((site/'index.html').read_bytes(), before)

    def test_changed_page_contract_fails_explicitly(self):
        source = (self.root/'web/index.html').read_text(encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'no longer matches'):
            demo_markup(source.replace('id="about-dialog"', 'id="different-dialog"'))


if __name__ == '__main__':
    unittest.main()
