"""Check the asset whitelist without requiring game resources."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from site_assets import asset_payload


class SiteAssetsTests(unittest.TestCase):
    def setUp(self):
        parent = Path(__file__).resolve().parents[1] / 'build'
        parent.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='asset-test-', dir=parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        if not self.root.resolve().is_relative_to(parent.resolve()):
            raise ValueError('Test directory escaped build')
        (self.root / 'config').mkdir()
        (self.root / 'local/ui-assets').mkdir(parents=True)
        (self.root / 'local/ui-assets/used.png').write_bytes(b'original frame')
        (self.root / 'local/ui-assets/research.png').write_bytes(b'not published')
        self.entry = {'source': 'local/ui-assets/used.png', 'target': 'assets/soul/sprites/used.png'}

    def manifest(self, files):
        (self.root / 'config/site-assets.json').write_text(json.dumps({'schema': 1, 'files': files}), encoding='utf-8')

    def test_only_listed_assets_and_exact_bytes(self):
        self.manifest([self.entry])
        self.assertEqual(asset_payload(self.root), {'assets/soul/sprites/used.png': b'original frame'})

    def test_missing_resource_is_error(self):
        self.manifest([{**self.entry, 'source': 'local/ui-assets/missing.png'}])
        with self.assertRaises(FileNotFoundError):
            asset_payload(self.root)

    def test_bundled_web_asset_is_read_without_local_copy(self):
        path = self.root/'web/assets/ui/placeholder/test.gif'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'GIF89a')
        self.manifest([{'source': 'web/assets/ui/placeholder/test.gif', 'target': 'assets/ui/placeholder/test.gif'}])
        self.assertEqual(asset_payload(self.root), {'assets/ui/placeholder/test.gif': b'GIF89a'})

    def test_duplicate_target_case_insensitive(self):
        self.manifest([self.entry, {**self.entry, 'target': 'assets/soul/sprites/USED.png'}])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            asset_payload(self.root)

    def test_reject_paths_outside_asset_namespaces(self):
        for key, value in [('target', '../outside.png'), ('target', '/outside.png'),
                           ('target', 'assets/extra/a.png'), ('source', 'local/ui-assets/../secret'),
                           ('source', 'C:/private.png'), ('source', 'local\\ui-assets\\used.png')]:
            with self.subTest(key=key, value=value):
                self.manifest([{**self.entry, key: value}])
                with self.assertRaises(ValueError):
                    asset_payload(self.root)
