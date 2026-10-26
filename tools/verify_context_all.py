"""Independent whole-source inventory audit for the five-chapter context catalog."""
from collections import Counter
import json
import time
from pathlib import Path
from context_paths import paths, parser
from context_conditions import ROOT, backend, digest
from context_data import catalog_payload, references


def verify(code, texts=ROOT/'build/texts', local=ROOT/'local/context-all', prior=None, report=None):
    code,texts,local=paths(code,texts,local)
    began=time.perf_counter();flow,gml,schema,calls=backend()
    manifest=(texts/'manifest.json').read_bytes()
    tables={ch:{r['key']:r for r in json.loads((texts/f'trilingual_chapter{ch}.json').read_text(encoding='utf-8'))['lines']} for ch in range(1,6)}
    catalog_payload(local,manifest,tables)
    proof=json.loads((local/'evidence.json').read_text(encoding='utf-8'))
    results=[];prior_ids=set()
    for ch in range(1,6):
        index=json.loads((local/f'index-ch{ch}.json').read_text(encoding='utf-8'))
        entries={e['file']:e for e in index['files']};covered=set();total=0;source_cache={}
        def source(name):
            if name not in source_cache:
                p=code/f'ch{ch}'/name;raw=p.read_bytes()
                assert digest(raw)==proof['sources'][f'ch{ch}/'+name],name
                text=p.read_text(encoding='utf-8-sig')
                source_cache[name]=(text,{c['offset']:c for c in calls(text)})
            return source_cache[name]
        for p in sorted((code/f'ch{ch}').glob('*.gml')):
            raw=p.read_bytes();assert digest(raw)==proof['sources'][f'ch{ch}/'+p.name]
            text=raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
            if '_gml_' not in text:
                assert p.name not in entries;continue
            starts={t.start() for t in flow.TOKEN.finditer(text) if t.group() in gml.FUNCTIONS}
            inventory=[]
            for event in gml.iter_events(text):
                if not event['is_message'] or event['pos'] not in starts:continue
                spec=gml.FUNCTIONS[event['name']]
                if spec[1] is None or not event['args']:continue
                key=gml.as_string_literal(event['args'][spec[1]])
                if key and gml.KEY_RE.fullmatch(key):inventory.append((key,event['name'],event['pos'],event['line']))
            if not inventory:
                assert p.name not in entries;continue
            assert p.name in entries,p.name
            scene=json.loads((local/entries[p.name]['path']).read_text(encoding='utf-8'))['scenes'][0]
            refs=list(references(scene['body']));native=[r for r in refs if r['source']['file']==p.name]
            actual=Counter((r['key'],r['call'],r['offset'],r['source']['line']) for r in native)
            assert actual==Counter(inventory),(p.name,actual-Counter(inventory),Counter(inventory)-actual)
            total+=len(native);covered.update(r['key'] for r in native)
            for r in refs:
                name=r['source']['file'];s,lookup=source(name);call=lookup[r['offset']]
                assert gml.as_string_literal(call['args'][-1])==r['key']
                spec=gml.FUNCTIONS[call['call']]
                literal=gml.as_string_literal(call['args'][spec[0]]) if spec[0] is not None else None
                binding='missing_key' if r['key'] not in tables[ch] else 'source_literal_differs' if spec[0] is not None and literal!=tables[ch][r['key']]['en'] else 'matched'
                assert r.get('binding','matched')==binding
                if binding!='matched':assert r['source_english']==literal
                assert r['source']['line']==s.count('\n',0,r['offset'])+1
                assert r['occurrence_id']==schema.occurrence_id(ch,'canonical',f'data/exported/code/ch{ch}/'+name,proof['sources'][f'ch{ch}/'+name],r['key'],r['offset'],call['call'])
            if ch in (4,5) and p.name in ('gml_Object_obj_ch4_DCC03_Step_0.gml','gml_Object_obj_room_town_school_Step_0.gml'):
                prior_ids.update(r['occurrence_id'] for r in refs)
            source_cache.pop(p.name,None)
        absent=sorted(set(tables[ch])-covered);assert absent==proof['missing_keys'][str(ch)]
        result={'chapter':ch,'files':len(entries),'references':total,'covered_keys':len(covered&set(tables[ch])),'no_source':len(absent)}
        results.append(result);print(json.dumps(result),flush=True)
    prior_preserved=None
    if prior is not None:
        previous=json.loads(Path(prior).read_text(encoding='utf-8'))
        assert {r['occurrence_id'] for s in previous['scenes'] for r in references(s['body'])}<=prior_ids
        prior_preserved=True
    result={'chapters':results,'prior_occurrences_preserved':prior_preserved,'seconds':round(time.perf_counter()-began,2)}
    if report is not None:
        report=Path(report).resolve()
        if any(report.is_relative_to(p) for p in (code,texts,local)):
            raise ValueError('Verification report must be outside inputs')
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('All files, references, source identities, binding differences and missing-key coverage passed')


if __name__=='__main__':
    p=parser(__doc__,'local/context-all')
    p.add_argument('--prior',type=Path,help='Optional historical scene package for occurrence regression')
    p.add_argument('--report',type=Path,help='Optional verification result outside input directories')
    a=p.parse_args();verify(a.code,a.texts,a.out,a.prior,a.report)
