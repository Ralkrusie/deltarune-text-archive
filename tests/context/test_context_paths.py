"""Input boundaries and local parser independence."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from tools.context.context_paths import paths
from tools.context.context_conditions import backend
from tools.text.import_texts import sha

class ContextPathsTests(unittest.TestCase):
    def inputs(self, root):
        code=root/'code';texts=root/'texts'
        code.mkdir();texts.mkdir();records=[]
        for ch in range(1,6):
            (code/f'ch{ch}').mkdir()
            (code/f'ch{ch}/fixture.gml').write_text('// fixture')
            name=f'trilingual_chapter{ch}.json'
            raw=json.dumps({'schema':1,'chapter':ch,'lines':[]}).encode()
            (texts/name).write_bytes(raw)
            records.append({'path':name,'sha256':sha(raw),'bytes':len(raw)})
        manifest={'schema':1,'kind':'unified-language-folder','outputs':records}
        (texts/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        return code,texts

    def test_missing_chapter_and_overlapping_output_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);code,texts=self.inputs(root)
            self.assertEqual(paths(code,texts,root/'out')[0],code.resolve())
            for out in (code,code/'nested',texts,root):
                with self.assertRaises(ValueError):paths(code,texts,out)
            (code/'ch5/fixture.gml').unlink()
            with self.assertRaisesRegex(ValueError,'ch5'):paths(code,texts,root/'out')

    def test_tampered_text_snapshot_rejected_by_all_current_entries(self):
        from tools.context.build_context_all import build as build_all
        from tools.context.context_files import build as build_files
        from tools.context.verify_context_all import verify as verify_all
        from tools.context.verify_context_files import verify as verify_files
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);code,texts=self.inputs(root);out=root/'out'
            # A valid JSON edit must not inherit the unchanged import manifest's identity.
            (texts/'trilingual_chapter1.json').write_text('{"schema":1,"chapter":1,"lines":[{"key":"changed","en":"edited"}]}',encoding='utf-8')
            entries=(lambda:build_all(code,texts,out),lambda:build_files([],code,texts,out),
                     lambda:verify_all(code,texts,out),lambda:verify_files(code,texts,out))
            for entry in entries:
                with self.assertRaisesRegex(ValueError,'digest mismatch'):entry()
                self.assertFalse(out.exists())

    def test_incomplete_or_duplicate_manifest_output_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);code,texts=self.inputs(root)
            path=texts/'manifest.json';original=json.loads(path.read_text())
            for outputs in (original['outputs'][:-1],original['outputs'][:-1]+[original['outputs'][0]]):
                with self.subTest(outputs=outputs):
                    path.write_text(json.dumps({**original,'outputs':outputs}),encoding='utf-8')
                    with self.assertRaisesRegex(ValueError,'exactly once'):paths(code,texts,root/'out')

    def test_backend_uses_local_package_without_changing_import_path(self):
        before=list(sys.path)
        api=backend()
        self.assertEqual(sys.path,before)
        root=Path(__file__).resolve().parents[2]/'tools/context/parser'
        for module in api[:3]:
            self.assertTrue(Path(module.__file__).resolve().is_relative_to(root))
        self.assertEqual(api[3].__module__,'tools.context.parser.calls')

if __name__=='__main__':unittest.main()
