"""Portable deltas must preserve originals, reject wrong inputs and stay bounded."""
import hashlib
import io
import json
from pathlib import Path
import random
import struct
import tempfile
import unittest

from tools.runtime import kit


def gm_string(value):
    raw = value.encode()
    body = struct.pack('<II', 1, 24) + struct.pack('<I', len(raw)) + raw + b'\0'
    chunk = b'STRG' + struct.pack('<I', len(body)) + body
    return b'FORM' + struct.pack('<I', len(chunk)) + chunk


def fixture(root):
    game, capture = root/'original', root/'capture'
    game.mkdir(); (capture/'game').mkdir(parents=True)
    path = 'C:/Users/Example/AppData/Local/DELTARUNE_CAPTURE_TEST'
    source = b'original-game-data'
    target = gm_string(path.lower())
    for name, raw in [('DELTARUNE.exe', b'runner'), ('data.win', source), ('audio/sound.ogg', b'sound'),
                      *[(f'chapter{i}_windows/data.win', source) for i in range(1, 6)]]:
        a, b = game/name, capture/'game'/name
        a.parent.mkdir(parents=True, exist_ok=True); b.parent.mkdir(parents=True, exist_ok=True)
        a.write_bytes(raw); b.write_bytes(target if name.endswith('data.win') else raw)
    inventory = {'chapter': 2, 'package_sha256': hashlib.sha256(source).hexdigest(),
                 'test_modifications': {'party_max_hp': 999}, 'sources': []}
    (capture/'sources.json').write_bytes(kit.canonical(inventory))
    originals = {p.relative_to(game).as_posix(): kit.sha(p) for p in game.rglob('*') if p.is_file()}
    outputs = {'game/'+p: kit.sha(capture/'game'/p) for p in originals}
    (capture/'original-files.json').write_bytes(kit.canonical(originals))
    manifest = {'kind': 'full_game_capture_pilot', 'revision': 30,
                'source_manifest': kit.sha(capture/'sources.json'),
                'collector_sha256': 'c'*64, 'profile': 'DELTARUNE_CAPTURE_TEST',
                'expected_save_path': path, 'outputs': outputs}
    (capture/'manifest.json').write_bytes(kit.canonical(manifest))
    return game, capture


class KitTests(unittest.TestCase):
    def test_inserted_bytes_and_repeated_chunks_roundtrip(self):
        generator = random.Random(42)
        base = generator.randbytes(2*1024*1024)
        target = base[:378] + b'inserted' + base[378:700000] + b'changed' + base[700100:]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'base'; path.write_bytes(base)
            patch = kit.make_delta(base, target)
            result = io.BytesIO(); meta = kit.apply_delta(path, patch, result)
            self.assertEqual(result.getvalue(), target)
            self.assertLess(len(patch), len(target)//3)
            self.assertEqual(meta['target_sha256'], hashlib.sha256(target).hexdigest())
            with self.assertRaises(ValueError): kit.apply_delta(path, patch+b'junk')

    def test_build_and_install_complete_copy_without_paths_or_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); game,capture=fixture(root)
            before={str(p):p.read_bytes() for p in game.rglob('*') if p.is_file()}
            manifest=kit.build_kit(game,capture,root/'kit')
            self.assertNotIn(b'Example', (root/'kit/kit.json').read_bytes())
            self.assertNotIn(b'Example', b''.join(p.read_bytes() for p in (root/'kit/patches').iterdir()))
            installed=kit.install_kit(root/'kit',game,root/'installed')
            self.assertEqual(installed['startup'],'game/DELTARUNE.exe')
            self.assertEqual(set(installed['outputs']), {'game/'+p for p in manifest['files']})
            for name, h in installed['outputs'].items(): self.assertEqual(kit.sha(root/'installed'/name), h)
            self.assertFalse((root/'installed/INSTALL_INCOMPLETE').exists())
            self.assertEqual((root/'installed/sources.json').read_bytes(), (capture/'sources.json').read_bytes())
            self.assertNotIn(b'example', (root/'installed/game/data.win').read_bytes())
            self.assertTrue(all(Path(p).read_bytes()==v for p,v in before.items()))

    def test_wrong_version_and_corrupt_patch_do_not_create_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); game,capture=fixture(root)
            manifest=kit.build_kit(game,capture,root/'kit')
            (game/'data.win').write_bytes(b'wrong-version')
            with self.assertRaisesRegex(ValueError,'version mismatch'):
                kit.install_kit(root/'kit',game,root/'wrong')
            self.assertFalse((root/'wrong').exists())
            (game/'data.win').write_bytes(b'original-game-data')
            path=root/'kit'/manifest['files']['data.win']['patch']; path.write_bytes(path.read_bytes()+b'broken')
            with self.assertRaisesRegex(ValueError,'integrity mismatch'):
                kit.install_kit(root/'kit',game,root/'corrupt')
            self.assertFalse((root/'corrupt').exists())

    def test_path_traversal_existing_and_nested_outputs_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); game,capture=fixture(root)
            kit.build_kit(game,capture,root/'kit')
            with self.assertRaisesRegex(ValueError,'separate'):
                kit.install_kit(root/'kit',game,game/'output')
            with self.assertRaisesRegex(ValueError,'must be new'):
                kit.install_kit(root/'kit',game,capture)
            path=root/'kit/kit.json'; manifest=json.loads(path.read_text())
            manifest['files']['../escape'] = manifest['files'].pop('audio/sound.ogg')
            path.write_bytes(kit.canonical(manifest))
            with self.assertRaisesRegex(ValueError,'relative path'):
                kit.install_kit(root/'kit',game,root/'unsafe')
            self.assertFalse((root/'unsafe').exists())

    def test_guard_edit_only_known_strg_entry(self):
        path='c:/users/person/appdata/local/deltarune_capture_test'
        original=gm_string(path)
        changed,evidence=kit.anonymize_guard(original,path)
        self.assertEqual(len(original),len(changed))
        self.assertEqual(original[:28],changed[:28])
        self.assertEqual(evidence['environment_branch'],'LOCALAPPDATA/profile')
        with self.assertRaises(ValueError): kit.anonymize_guard(original+b'extra',path)
        with self.assertRaises(ValueError): kit.anonymize_guard(original,path+'/other')


if __name__=='__main__': unittest.main()
