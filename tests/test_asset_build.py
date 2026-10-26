"""Asset export failure must never replace usable local assets."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import build_assets


class AssetBuildTests(unittest.TestCase):
    def test_failed_export_preserves_game_and_live_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            game, zh = root/'game', root/'zh'
            for folder, chapters in ((game, (1, 2, 4, 5)), (zh, (1,))):
                for ch in chapters:
                    p=folder/f'chapter{ch}_windows/data.win'
                    p.parent.mkdir(parents=True); p.write_bytes(b'game')
            (game/'chapter2_windows/snd_great_shine.ogg').write_bytes(b'sound')
            cli=root/'umt/UndertaleModCli.exe';cli.parent.mkdir();cli.write_bytes(b'fake')
            plan, _=build_assets.jobs(game, zh)
            (root/'tools').mkdir()
            for _,_,_,scripts in plan:
                for name in scripts:(root/'tools'/name).write_text('// read only',encoding='utf-8')
            live=root/'local/ui-assets/keep.png';live.parent.mkdir(parents=True);live.write_bytes(b'previous')
            with patch.object(build_assets, 'ROOT', root), \
                 patch.object(build_assets.importlib, 'import_module', return_value=SimpleNamespace(__version__='test')), \
                 patch.object(build_assets.subprocess, 'run', return_value=SimpleNamespace(returncode=1)) as run:
                with self.assertRaisesRegex(ValueError, 'UMT failed'):
                    build_assets.build(game, zh, cli)
            self.assertEqual(live.read_bytes(), b'previous')
            self.assertTrue(all(p.read_bytes()==b'game' for _,p,_,_ in plan))
            self.assertNotIn('-o', run.call_args.args[0])
            report=next((root/'local/asset-build').glob('*/report.json'))
            self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['status'], 'failed')

    def test_missing_game_input_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Missing en-ch1'):
                build_assets.jobs(Path(tmp), Path(tmp)/'zh')
