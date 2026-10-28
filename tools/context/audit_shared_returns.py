"""Read-only census of shared menus and possible caller-side answer consumers.

Candidates are not proven control-flow edges or reachable game scenes. This
command writes a local audit only; it does not change context/site generation.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from .build_context_all import Sources
from .context_conditions import ROOT, backend, digest
from .context_files import Analyzer
from .shared_cases import SharedCases


def owner(name):
    match=re.fullmatch(r'gml_Object_(.+)_(?:Create|Step|Draw|Other|Alarm|Collision|Destroy|CleanUp|PreCreate|KeyPress|KeyRelease|Keyboard)_\d+\.gml',name)
    return match[1] if match else None


def targets(analyzer,site):
    """Syntactic target blocks in the caller file; deliberately not CFG proof."""
    a=analyzer;data=a.file(site['file']);out=[]
    transfers=site.get('same_object_state_transfers',[])
    for variable,value in sorted({(t['variable'],t['value']) for t in transfers}):
        for n in a.flow.walk(data['nodes']):
            if n.kind!='if' or not re.search(r'(?<![\w.])'+variable+r'\s*==\s*'+str(value)+r'(?!\d)',n.text):continue
            source=data['source'][n.start:n.end];refs=a.within(site['file'],n)
            out.append({'variable':variable,'value':value,'line':data['source'].count('\n',0,n.start)+1,
                'guard':n.text,'reads_choice':bool(re.search(r'\bglobal\.choice\b',source)),
                'reference_count':len(refs),'sample_keys':[r['key'] for r in refs[:2]]})
    return out


def audit(code,texts,out):
    code=code.resolve();texts=texts.resolve();out=out.resolve()
    if any(out.is_relative_to(p) for p in (code,texts)):raise ValueError('Audit output must be outside inputs')
    api=backend();chapters=[]
    for ch in range(1,6):
        tables={r['key']:r for r in json.loads((texts/f'trilingual_chapter{ch}.json').read_text(encoding='utf-8'))['lines']}
        sources=Sources(code/f'ch{ch}');a=Analyzer(sources,ch,tables,api,strict_bindings=False)
        name='gml_GlobalScript_scr_text.gml';record=a.file(name);planner=SharedCases(a,name)
        switches=[n for n in a.flow.walk(record['nodes']) if a.is_shared_switch(name,n)]
        if len(switches)!=1:raise ValueError(f'CH{ch}: unsupported scr_text entry')
        cases={int(n.text):n for n in switches[0].children if n.text.isdigit()};menus={}
        for number,n in cases.items():
            strings=[(node,planner.message(node)) for node in a.flow.walk(n.children)]
            prompts=[(node,t) for node,t in strings if t is not None and re.search(r'\\C[1-4]',t)]
            if not prompts:continue
            following=cases.get(number+1);tail=a.flat(following.children) if following else []
            tailtext=[planner.message(node) for node in tail if node.text!='break;']
            closing=bool(tailtext) and all(t is not None and t.strip()=='%%' for t in tailtext)
            response=record['source'][following.start:following.end] if following else ''
            response_kind=('close_only' if closing else 'reads_choice' if re.search(r'\bglobal\.choice\b',response)
                           else 'other' if following else 'missing')
            transfers=[];callbacks=[]
            if following:
                for scope in a.flow.walk(following.children):
                    if scope.kind!='with' or not re.fullmatch(r'obj_\w+',scope.text):continue
                    for node in a.flow.walk(scope.children):
                        if node.kind!='stmt':continue
                        assignment=re.fullmatch(r'(con|photocon|myinteract|talk_con)\s*=\s*(-?\d+)\s*;',node.text)
                        if assignment:transfers.append({'owner':scope.text,'variable':assignment[1],'value':int(assignment[2]),'line':record['source'].count('\n',0,node.start)+1})
                        for call in a.calls(node.text):
                            if call['args']==['global.choice']:
                                callbacks.append({'owner':scope.text,'call':call['call'],'line':record['source'].count('\n',0,node.start)+1})
            refs=a.within(name,n)
            menus[number]={'case':number,'line':record['source'].count('\n',0,n.start)+1,
                'controls':[m for _,t in prompts for m in re.findall(r'\\C([1-4])',t)],
                'response_kind':response_kind,'response_line':record['source'].count('\n',0,following.start)+1 if following else None,
                'state_transfers':transfers,'answer_callbacks':callbacks,
                'text_sample':[{'key':r['key'],'en':tables.get(r['key'],{}).get('en')} for r in refs[:5]],
                'bounded_options':bool(len(prompts)==1 and re.search(r'\\C[2-4]',prompts[0][1]) and planner.options(n,int(re.search(r'\\C([2-4])',prompts[0][1])[1])))}
        sites=[];consumers={};errors=[];msc_assignments=[]
        for filename in sources:
            source=sources[filename]
            if filename==name or not any(t in source for t in ('global.choice','scr_text','c_msc','global.msc')):
                if filename not in a.cache:sources.loaded.pop(filename,None)
                continue
            try:nodes=a.flow.parse(source)
            except (ValueError,IndexError,RecursionError) as exc:
                errors.append({'file':filename,'reason':str(exc)});continue
            reads=[]
            for n in a.flow.walk(nodes):
                if n.kind in ('if','switch') and re.search(r'\bglobal\.choice\b',n.text):
                    reads.append({'line':source.count('\n',0,n.start)+1,'kind':n.kind,'condition':n.text})
            if reads:consumers[filename]=reads
            def visit(nodes,trail=()):
                flat=a.flat(nodes)
                for i,n in enumerate(flat):
                    line=source.count('\n',0,n.start)+1
                    if n.kind=='stmt':
                        match=re.fullmatch(r'global\.msc\s*=\s*(\d+)\s*;',n.text)
                        if match:msc_assignments.append({'file':filename,'line':line,'case':int(match[1])})
                        for call in a.calls(n.text):
                            if call['call'] not in ('scr_text','c_msc') or len(call['args'])!=1:continue
                            arg=call['args'][0];value=None;binding='unresolved'
                            if arg.isdigit():value=int(arg);binding='literal'
                            elif arg=='global.msc' and i and flat[i-1].kind=='stmt':
                                prior=re.fullmatch(r'global\.msc\s*=\s*(\d+)\s*;',flat[i-1].text)
                                if prior:value=int(prior[1]);binding='adjacent_msc_assignment'
                            sites.append({'file':filename,'owner':owner(filename),'line':line,'call':call['call'],
                                'case':value,'binding':binding,'scope':list(trail)})
                    path=trail+({'kind':n.kind,'condition':n.text,'line':line},) if n.kind in ('if','with','switch','case') else trail
                    if n.children:visit(n.children,path)
                    if n.other:visit(n.other,trail+({'kind':'else','condition':n.text,'line':line},))
            visit(nodes)
            if filename not in a.cache:sources.loaded.pop(filename,None)
        byowner=defaultdict(list)
        for f,reads in consumers.items():
            if owner(f):byowner[owner(f)].append({'file':f,'reads':reads})
        for s in sites:
            if s['case'] in menus:
                s['menu_kind']=menus[s['case']]['response_kind']
                s['same_file_consumers']=consumers.get(s['file'],[])
                s['same_object_consumers']=byowner.get(s['owner'],[])
                s['same_object_state_transfers']=[t for t in menus[s['case']]['state_transfers'] if t['owner']==s['owner']]
                s['same_object_answer_callbacks']=[t for t in menus[s['case']]['answer_callbacks'] if t['owner']==s['owner']]
                if s['same_object_state_transfers'] or s['same_object_answer_callbacks']:
                    s['candidate_target_blocks']=targets(a,s)
                    s['candidate_kind']=('callback' if s['same_object_answer_callbacks'] else
                        'answer_routed_states' if len({t['value'] for t in s['same_object_state_transfers']})>1 else
                        'caller_reads_answer' if any(t['reads_choice'] for t in s['candidate_target_blocks']) else
                        'other_state_continuation')
        callers=[s for s in sites if 'menu_kind' in s]
        relevant=[s for s in callers if s['menu_kind']=='close_only' and s['same_object_consumers']]
        summary={'chapter':ch,'source_files':len(sources),'shared_menu_cases':len(menus),
            'response_kinds':dict(Counter(m['response_kind'] for m in menus.values())),
            'bound_menu_calls':len(callers),'close_only_menu_calls':sum(s['menu_kind']=='close_only' for s in callers),
            'close_only_calls_with_same_object_choice_conditions':len(relevant),
            'close_only_cases_with_same_object_choice_conditions':len({s['case'] for s in relevant}),
            'close_only_objects_with_choice_conditions':len({s['owner'] for s in relevant}),
            'calls_with_explicit_same_object_state_transfer':sum(bool(s['same_object_state_transfers']) for s in callers),
            'calls_with_explicit_same_object_answer_callback':sum(bool(s['same_object_answer_callbacks']) for s in callers),
            'candidate_kinds':dict(Counter(s['candidate_kind'] for s in callers if 'candidate_kind' in s)),
            'priority_candidates_with_text_in_target_block':sum(s.get('candidate_kind') in ('answer_routed_states','caller_reads_answer')
                and any(t['reference_count'] for t in s['candidate_target_blocks']) for s in callers),
            'parse_errors':len(errors)}
        chapters.append({'summary':summary,'menus':list(menus.values()),'calls':sites,'candidate_calls':relevant,
                         'choice_condition_files':consumers,'msc_assignments':msc_assignments,'parse_errors':errors,
                         'source_hashes':sources.hashes})
        print(json.dumps(summary,ensure_ascii=False),flush=True)
    report={'kind':'candidate_census_not_control_flow_proof','chapters':chapters,
            'text_manifest_sha256':digest((texts/'manifest.json').read_bytes())}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code',type=Path,required=True);p.add_argument('--texts',type=Path,default=ROOT/'build/texts')
    p.add_argument('--out',type=Path,default=ROOT/'build/context-cross-script/census.json')
    args=p.parse_args();audit(args.code,args.texts,args.out)
