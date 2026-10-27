import hashlib
import json
import unittest
from tests.runtime import test_bundles as fixtures
from tools.runtime.review import build


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.BundleTests();self.fixture.setUp()
    def tearDown(self):self.fixture.tearDown()

    def test_projection_preserves_archive_and_removes_unbacked_candidate(self):
        f=self.fixture
        inv=json.loads(f.sources.read_text());inv['face_entities']={'21':'queen'}
        f.sources.write_text(json.dumps(inv));f.source_hash=hashlib.sha256(f.sources.read_bytes()).hexdigest()
        folder=f.session(text='Shut up!! </script>')
        log=next(folder.glob('capture_*.jsonl'));rows=[json.loads(l) for l in log.read_text().splitlines()]
        rows[-1]['identity_states']=[dict(face_code=21,expression=7,typer=50)]
        log.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        bundle,_=f.export(folder);before=bundle.read_bytes()
        result=build([bundle],f.sources,f.library,f.root/'review')
        raw=(f.root/'review/data.js').read_text(encoding='utf-8')
        data=json.loads(raw.removeprefix('window.REVIEW_DATA=').strip().removesuffix(';'))
        self.assertEqual(result['rows'],1)
        self.assertEqual(data['rows'][0]['body']['identity']['candidates'],['queen'])
        self.assertEqual(data['rows'][0]['view']['candidates'],[])
        self.assertNotIn('</script>',raw)
        self.assertEqual(bundle.read_bytes(),before)

    def test_wrong_source_snapshot_fails_closed(self):
        f=self.fixture;inv=json.loads(f.sources.read_text());inv['sources'][0].update(path='data/exported/code/ch2/test.gml',sha256='f'*64,line=1)
        f.sources.write_text(json.dumps(inv));f.source_hash=hashlib.sha256(f.sources.read_bytes()).hexdigest()
        bundle,_=f.export(f.session());code=f.root/'code';code.mkdir();(code/'test.gml').write_text('wrong snapshot')
        with self.assertRaisesRegex(ValueError,'Source changed'):
            build([bundle],f.sources,f.library,f.root/'review',code_root=code)
