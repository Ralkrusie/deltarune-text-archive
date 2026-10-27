"""Compile CH2 from explicit originals, updating a portable kit without a developer game copy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from .kit import _validate_kit, _new_output, _plain, sha, canonical, make_delta, apply_delta
from .compiler.instrument import generate, substitution_wrappers
from .compiler.source_fixture import generate as fixture


def compile_kit(original, code_root, base_kit, hp_patches, cli, out):
    original,code_root,base_kit,hp_patches,cli=map(lambda p:_plain(p).resolve(strict=True),(original,code_root,base_kit,hp_patches,cli))
    out=_new_output(out,original,code_root,base_kit)
    base=json.loads((base_kit/'kit.json').read_text(encoding='utf-8'));_validate_kit(base)
    for name,entry in base['files'].items():
        if sha(original/name)!=entry['original_sha256']:raise ValueError('Original version mismatch: '+name)
        if 'patch' in entry and sha(base_kit/entry['patch'])!=entry['patch_sha256']:raise ValueError('Base patch changed')
    prior=json.loads((base_kit/'sources.json').read_text(encoding='utf-8'))
    if sha(base_kit/'sources.json')!=base['source_manifest']:raise ValueError('Base inventory changed')
    stage=out/'compile';stage.mkdir(parents=True)
    source=Path(__file__).with_name('compiler')
    inv=generate(code_root,stage/'patches',previous=prior)
    for name in ('package_sha256','capabilities','test_modifications','face_entities','identity_evidence'):
        inv[name]=prior[name]
    (stage/'sources.json').write_text(json.dumps(inv,ensure_ascii=False,indent=2),encoding='utf-8')
    fixture(stage)
    (stage/'substitution_wrappers.gml').write_text(substitution_wrappers(),encoding='utf-8')
    shutil.copy2(hp_patches,stage/'hp-patches.json')
    inputs={p.name:sha(p) for p in sorted(source.iterdir()) if p.suffix in ('.gml','.csx','.json','.py')}
    config=dict(profile=base['profile'],expected_save_path='capture-portable-invalid-root/'+'_'*33,
                source_manifest=sha(stage/'sources.json'),attribute_schema=2,test_max_hp=999,
                collector_sha256=hashlib.sha256(canonical(inputs)).hexdigest(),code_root=str(code_root))
    (stage/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    env=dict(os.environ,DR_CAPTURE_CONFIG=str(stage/'config.json'))
    with (stage/'compile.log').open('wb') as log:
        proc=subprocess.run([str(cli),'load',str(original/'chapter2_windows/data.win'),'-s',str(source/'inject.csx'),'-o',str(stage/'data.win')],env=env,stdout=log,stderr=subprocess.STDOUT)
    if proc.returncode or not (stage/'data.win').exists():raise RuntimeError('Compile failed; see '+str(stage/'compile.log'))
    kit=out/'kit';shutil.copytree(base_kit,kit)
    shutil.copy2(stage/'sources.json',kit/'sources.json')
    data=(stage/'data.win').read_bytes();patch=make_delta((original/'chapter2_windows/data.win').read_bytes(),data)
    apply_delta(original/'chapter2_windows/data.win',patch)
    patch_name='patches/'+hashlib.sha256(patch).hexdigest()+'.drdelta'
    (kit/patch_name).write_bytes(patch)
    old=base['files']['chapter2_windows/data.win']
    base['files']['chapter2_windows/data.win']=dict(original_sha256=old['original_sha256'],original_size=old['original_size'],
          target_sha256=sha(stage/'data.win'),target_size=len(data),patch=patch_name,patch_sha256=hashlib.sha256(patch).hexdigest(),patch_size=len(patch))
    base.update(revision=31,source_manifest=config['source_manifest'],collector_sha256=config['collector_sha256'])
    _validate_kit(base);(kit/'kit.json').write_bytes(canonical(base)+b'\n')
    # Keep only referenced deltas in the distributable kit; compile evidence stays separate.
    referenced={v.get('patch') for v in base['files'].values()}
    for p in (kit/'patches').glob('*.drdelta'):
        if p.relative_to(kit).as_posix() not in referenced:p.unlink()
    previous={r['occurrence_id']:r['source_id'] for r in prior['sources']}
    current={r['occurrence_id']:r['source_id'] for r in inv['sources']}
    if not all(current.get(k)==v for k,v in previous.items()):raise ValueError('Existing occurrence IDs changed')
    result=dict(revision=31,kit=str(kit),sources=len(inv['sources']),added_sources=len(current)-len(previous),
                old_ids_preserved=True,compiler_inputs=inputs,hp_patches_sha256=sha(hp_patches),runtime_verified=False)
    (out/'build.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('original','code-root','base-kit','hp-patches','cli','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(compile_kit(a.original,a.code_root,a.base_kit,a.hp_patches,a.cli,a.out),indent=2))
