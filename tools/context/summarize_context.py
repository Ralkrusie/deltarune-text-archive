"""Summarize a generated context catalog; counts are not gameplay coverage."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .context_conditions import digest
from .context_data import references


def walk(n):
    yield n
    for c in n.get('children', []):yield from walk(c)
    if 'prefix' in n:yield from walk(n['prefix'])
    for b in n.get('branches', []):
        if 'option' in b:yield b['option']
        yield from walk(b['body'])


def summarize(folder):
    folder=Path(folder)
    evidence=json.loads((folder/'evidence.json').read_text(encoding='utf-8'))
    chapters=[];all_nodes=Counter();all_choices=Counter();fallback=0
    for summary in evidence['chapters']:
        ch=summary['chapter'];index=json.loads((folder/f'index-ch{ch}.json').read_text(encoding='utf-8'))
        nodes=Counter();choices=Counter();native=0
        for meta in index['files']:
            raw=(folder/meta['path']).read_bytes()
            if digest(raw)!=meta['sha256'] or len(raw)!=meta['bytes']:
                raise ValueError('Context chunk integrity: '+meta['path'])
            scene=json.loads(raw)['scenes'][0]
            native+=sum(r['source']['file']==scene['file'] for r in references(scene['body']))
            for n in walk(scene['body']):
                nodes[n['type']]+=1
                if n.get('unresolved'):fallback+=sum(1 for _ in references(n))
                if n['type']=='choice':
                    sizes=[len(list(references(b['body']))) for b in n['branches']]
                    choices['menus']+=1
                    choices['options']+=len(sizes)
                    choices['empty_options']+=sum(s==0 for s in sizes)
                    choices['menus_with_reply_text']+=any(sizes)
                    choices['menus_without_reply_text']+=not any(sizes)
                    choices['shared_response_prefixes']+=bool(n.get('prefix'))
                    choices['joins_to_next_message']+=bool(n.get('join_next'))
                if n.get('revisit'):choices['revisit_conditions']+=1
                if n.get('join_next'):choices['all_join_groups']+=1
        if native!=summary['references']:raise ValueError('Reference count mismatch')
        chapters.append({**summary,'structure_nodes':dict(nodes),'choices':dict(choices)})
        all_nodes.update(nodes);all_choices.update(choices)
    audits={}
    for key in ('queued_menus','direct_menus'):
        rows=evidence.get(key,[])
        audits[key]={'candidate_prompts':len(rows),'connected_by_this_rule':sum(r['status']=='connected' for r in rows),
                     'handled_by_existing_rule':sum(r['reason']=='existing_relation_scope' for r in rows),
                     'other_reasons':dict(Counter(r['reason'] for r in rows if r['status']!='connected'
                                                 and r['reason']!='existing_relation_scope'))}
    total={key:sum(c.get(key,0) for c in chapters) for key in (
        'scanned_files','context_files','text_records','covered_keys','no_source_keys',
        'references','matched','source_literal_differs','missing_key')}
    return {'scope':'Static source positions, including cross-chapter copies and tests; not unique playable scenes or semantic accuracy.',
            'text_manifest_sha256':evidence['text_manifest_sha256'],'totals':total,
            'structure_nodes':dict(all_nodes),'choices':dict(all_choices),'fallback_references':fallback,
            'rules':dict(Counter(r['rule'] for r in evidence['rules'])),'audits':audits,
            'diagnostics':evidence['diagnostics'],'chapters':chapters}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--context',type=Path,default=Path('local/context-all'))
    p.add_argument('--out',type=Path,default=Path('build/context-summary.json'))
    a=p.parse_args();result=summarize(a.context)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='chapters'},ensure_ascii=False,indent=2))
