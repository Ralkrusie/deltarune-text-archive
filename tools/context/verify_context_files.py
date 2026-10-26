"""Independent complete-file inventory and source identity verification."""
from collections import Counter
import json
from pathlib import Path
from .context_paths import paths, parser
from .context_conditions import ROOT, backend, digest
from .context_data import references, validate


def verify(code, texts=ROOT/'build/texts', local=ROOT/'local/context-files', prior=None):
    code,texts,local=paths(code,texts,local)
    raw=(local/'contexts.json').read_bytes()
    pack=json.loads(raw);proof=json.loads((local/'evidence.json').read_text(encoding='utf-8'))
    assert digest(raw)==proof['contexts_sha256']
    _,gml,schema,calls=backend()
    tables={ch:{r['key']:r for r in json.loads((texts/f'trilingual_chapter{ch}.json').read_text(encoding='utf-8'))['lines']} for ch in range(1,6)}
    validate(pack,(texts/'manifest.json').read_bytes(),tables)
    sources={}
    for path,sha in proof['sources'].items():
        file=code/path
        assert digest(file.read_bytes())==sha
        source=file.read_text(encoding='utf-8-sig');sources[path]=(source,{c['offset']:c for c in calls(source)})
    for scene in pack['scenes']:
        ch=scene['chapter'];name=scene['file'];refs=list(references(scene['body']))
        native=[r for r in refs if r['source']['file']==name]
        # Separate lexer/event inventory, not the projection's own traversal.
        original=gml.scan_file(code/f'ch{ch}'/name)
        expected=Counter((r['key'],r['call'],r['line']) for r in original if r['key_ok'])
        actual=Counter((r['key'],r['call'],r['source']['line']) for r in native)
        assert actual==expected,(name,expected-actual,actual-expected)
        assert len(native)==scene['reference_count']
        for r in refs:
            path=f'ch{ch}/'+r['source']['file'];source,lookup=sources[path];call=lookup[r['offset']]
            assert gml.as_string_literal(call['args'][-1])==r['key']
            spec=gml.FUNCTIONS[call['call']]
            if spec[0] is not None:assert gml.as_string_literal(call['args'][spec[0]])==tables[ch][r['key']]['en']
            assert r['source']['line']==source.count('\n',0,r['offset'])+1
            assert r['occurrence_id']==schema.occurrence_id(ch,'canonical','data/exported/code/'+path,proof['sources'][path],r['key'],r['offset'],call['call'])
        print(f'{name}: {len(native)}/{sum(expected.values())} native references; {len(refs)-len(native)} linked references')
        if name=='gml_Object_obj_ch4_DCC03_Step_0.gml':
            def visit(node):
                yield node
                for child in node.get('children',[]):yield from visit(child)
                for branch in node.get('branches',[]):yield from visit(branch['body'])
            condition=next(n for n in visit(scene['body']) if n['type']=='condition' and n['branches'][0]['label']=='obj_mainchara.x >= 4310 && global.interact == 0')
            assert [r['key'] for r in references(condition['branches'][0]['body'])]==[
                f'obj_ch4_DCC03_slash_Step_0_gml_{i}_0' for i in (910,911,927)]
            assert not list(references(condition['branches'][1]['body']))
            assert not any(n.get('label')=='L651' for n in scene['body']['children'])
            print('L651 continuation is inside the true branch; false branch remains empty')
    # An optional prior snapshot must retain its occurrence identities.
    if prior is not None:
        prior=Path(prior)
        old=json.loads(prior.read_text(encoding='utf-8'))
        oldids={r['occurrence_id'] for s in old['scenes'] for r in references(s['body'])}
        newids={r['occurrence_id'] for s in pack['scenes'] for r in references(s['body'])}
        assert oldids<=newids
        print(f'{len(oldids)} previous identities preserved')
    print('Whole-file inventory, literals, offsets, source hashes and occurrence identity passed')


if __name__=='__main__':
    p=parser(__doc__,'local/context-files')
    p.add_argument('--prior',type=Path)
    a=p.parse_args();verify(a.code,a.texts,a.out,a.prior)
