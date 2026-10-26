"""Exercise the actual site builder with temporary inputs, without a public demo."""
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

from tools.site.build_site import assemble, WEB_FILES
from tools.text.import_texts import FILES, run, sha

ROOT = Path(__file__).resolve().parents[2]


class SiteBuildTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'build'
        parent.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix='site-test-', dir=parent)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name in WEB_FILES:
            target = self.root / 'web' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'web' / name, target)
        for ch in range(1, 6):
            folder = self.root / 'input' / f'ch{ch}'
            folder.mkdir(parents=True)
            for filename in FILES.values():
                (folder / filename).write_text(json.dumps({'test': '* Test./'}), encoding='utf-8')
        (self.root / 'config').mkdir()
        self.asset = self.root / 'local/ui-assets/test.png'
        self.asset.parent.mkdir(parents=True)
        self.asset.write_bytes(b'asset fixture')
        (self.root / 'config/site-assets.json').write_text(json.dumps({'schema': 1, 'files': [
            {'source': 'local/ui-assets/test.png', 'target': 'assets/ui/test.png'},
        ]}), encoding='utf-8')
        run(self.root / 'input', self.root / 'build/texts')

    def test_build_uses_actual_page_modules_and_roundtrips_text(self):
        site = assemble(self.root)
        markup = (site / 'index.html').read_text(encoding='utf-8')
        for name in re.findall(r'<script\b[^>]*src="([^"]+)"', markup):
            self.assertTrue((site / name).is_file(), name)
        for ch in range(1, 6):
            data = json.loads((site / f'data/ch{ch}.json').read_text(encoding='utf-8'))
            self.assertEqual(data['rows'][0][0], 'test')
            self.assertTrue(all(data['strings'][i] == '* Test./' for i in data['rows'][0][1:6]))
        self.assertEqual((site / 'assets/ui/test.png').read_bytes(), self.asset.read_bytes())
        self.assertFalse((site / 'local').exists())
        contexts = json.loads((site / 'data/contexts.json').read_text())
        self.assertEqual(contexts['scenes'], [])
        self.assertEqual(contexts['text_manifest_sha256'], sha((self.root / 'build/texts/manifest.json').read_bytes()))

    def test_rebuild_deterministic_and_unknown_files_preserved(self):
        site = assemble(self.root)
        before = {p.relative_to(site): p.read_bytes() for p in site.rglob('*') if p.is_file()}
        assemble(self.root)
        self.assertEqual(before, {p.relative_to(site): p.read_bytes() for p in site.rglob('*') if p.is_file()})
        (site / 'keep.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'Unexpected files'):
            assemble(self.root)
        self.assertEqual((site / 'keep.txt').read_text(), 'keep')
        self.assertEqual((site / 'index.html').read_bytes(), before[Path('index.html')])

    def test_missing_asset_does_not_replace_site(self):
        site = assemble(self.root)
        before = (site / 'index.html').read_bytes()
        self.asset.unlink()
        with self.assertRaises(FileNotFoundError):
            assemble(self.root)
        self.assertEqual((site / 'index.html').read_bytes(), before)
