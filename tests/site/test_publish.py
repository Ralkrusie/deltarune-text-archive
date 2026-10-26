import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.site.publish import verified_payload


class PublicationTests(unittest.TestCase):
    def test_only_exact_verified_snapshot_is_publishable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'dist').mkdir()
            (root / 'build').mkdir()
            payload = {'index.html': b'hello', '.nojekyll': b''}
            report = {'files': []}
            for name, raw in payload.items():
                (root / 'dist' / name).write_bytes(raw)
                report['files'].append({'path': name, 'bytes': len(raw),
                                        'sha256': hashlib.sha256(raw).hexdigest()})
            manifest = root / 'build/site-build.json'
            manifest.write_text(json.dumps(report), encoding='utf-8')
            self.assertEqual(verified_payload(root), payload)
            (root / 'dist/index.html').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                verified_payload(root)
            (root / 'dist/index.html').write_bytes(b'hello')
            extra = root / 'dist/private.txt'
            extra.write_text('not in manifest')
            with self.assertRaises(ValueError):
                verified_payload(root)
            extra.unlink()
            for bad in ('../secret', 'local/secret', '.git/config', 'C:/secret'):
                report['files'][0]['path'] = bad
                manifest.write_text(json.dumps(report), encoding='utf-8')
                with self.assertRaises(ValueError):
                    verified_payload(root)
