"""Whole-file text projection with conservative, mechanically proven choice links.

No scene names, dialogue keys, state numbers or hand-picked source ranges.
The analyzer uses local syntax helpers and explicit read-only source inputs.
"""
import argparse
from collections import Counter
from bisect import bisect_left
import copy
import json
from pathlib import Path
import re
from context_conditions import ROOT, backend, digest
from context_data import references, validate


def sequence(children):
    return {'type':'sequence','children':children}


def inverse(expression):
    expression=expression.strip()
    return expression[1:] if re.fullmatch(r'![\w.]+\([^()]*\)',expression) else '!('+expression+')'


class Analyzer:
    def __init__(self, sources, chapter, tables, api, source_hashes=None, strict_bindings=True):
        self.sources=sources;self.chapter=chapter;self.tables=tables
        self.strict_bindings=strict_bindings
        self.source_hashes={} if source_hashes is None else source_hashes
        self.flow,self.gml,self.schema,self.calls=api
        self.cache={};self.evidence=[];self.diagnostics=[];self.continuations={}

    def file(self,name):
        if name not in self.cache:
            source=self.sources[name];rawhash=self.source_hashes.get(name,digest(source.encode('utf-8')))
            refs=[];calls=list(self.calls(source))
            for c in calls:
                spec=self.gml.FUNCTIONS.get(c['call'])
                if not spec or spec[1] is None or not c['args']:continue
                key=self.gml.as_string_literal(c['args'][spec[1]])
                if key is None or not self.gml.KEY_RE.fullmatch(key):continue
                literal=self.gml.as_string_literal(c['args'][spec[0]]) if spec[0] is not None else None
                binding='missing_key' if key not in self.tables else 'source_literal_differs' if spec[0] is not None and literal!=self.tables[key]['en'] else 'matched'
                if self.strict_bindings and binding!='matched':raise ValueError('Context text binding: '+binding+' '+key)
                refs.append(dict(type='message',key=key,
                    occurrence_id=self.schema.occurrence_id(self.chapter,'canonical',f'data/exported/code/ch{self.chapter}/'+name,rawhash,key,c['offset'],c['call']),
                    source={'file':name,'line':source.count('\n',0,c['offset'])+1},offset=c['offset'],call=c['call']))
                if binding!='matched':refs[-1].update(binding=binding,source_english=literal)
            parse_error=None
            try:nodes=self.flow.parse(source)
            except (ValueError,IndexError,RecursionError) as e:
                nodes=[];parse_error=str(e)
            self.cache[name]={'source':source,'hash':rawhash,'refs':refs,'offsets':[r['offset'] for r in refs],'calls':calls,'nodes':nodes,'parse_error':parse_error}
        return self.cache[name]

    def within(self,name,node):
        data=self.file(name)
        return data['refs'][bisect_left(data['offsets'],node.start):bisect_left(data['offsets'],node.end)]

    def flat(self,nodes):
        out=[]
        for n in nodes:
            out.extend(self.flat(n.children) if n.kind=='block' else [n])
        return out

    def options(self,name,nodes):
        """Literal option slots assigned at this exact scope, not nested alternatives."""
        out={}
        for n in self.flat(nodes):
            match=re.match(r'global\.choicemsg\[(\d+)\]\s*=',n.text) if n.kind=='stmt' else None
            if match:
                rs=self.within(name,n)
                if len(rs)==1:out[int(match[1])]=rs[0]
        return out

    def stage(self,n):
        if n.kind!='if':return None
        parts=re.split(r'\s*&&\s*',n.text)
        matches=[re.fullmatch(r'con\s*==\s*(-?\d+)',p) for p in parts]
        values=[int(m[1]) for m in matches if m]
        return values[0] if len(values)==1 else None

    def state_assignment(self,nodes):
        values=[]
        for n in self.flat(nodes):
            if n.kind=='stmt' and re.fullmatch(r'con\s*=\s*-?\d+\s*;',n.text):
                values.append(int(n.text.split('=')[1].strip(' ;')))
            elif any(re.search(r'\bcon\s*(?:=(?!=)|\+=|-=|\+\+|--)',c.text) for c in self.flow.walk([n])):
                return None
        return values[-1] if values else None

    def root_guard(self,n):
        if self.stage(n) is None:return n.text
        internal=r'(?:con\s*==\s*-?\d+|customcon\s*==\s*\d+|!d_ex\(\)|global\.interact\s*==\s*\d+|!i_ex\(obj_cutscene_master\))'
        return ' && '.join(p for p in re.split(r'\s*&&\s*',n.text) if not re.fullmatch(internal,p))

    def project(self,name,nodes,omit=()):
        out=[]
        for n in self.flat(nodes):
            if not any(r['occurrence_id'] not in omit for r in self.within(name,n)):continue
            if n.kind=='if':
                yes=self.project(name,n.children,omit);no=self.project(name,n.other,omit)
                for arm,body in (('then',yes),('else',no)):
                    target=self.continuations.get((name,n.start,arm))
                    if target is not None:body.extend(self.project(name,target.children,omit))
                out.append(dict(type='condition',title='',branches=[
                    {'label':n.text,'body':sequence(yes)},
                    {'label':inverse(n.text),'body':sequence(no)}]))
            elif n.kind=='stmt':
                rs=[copy.deepcopy(r) for r in self.within(name,n) if r['occurrence_id'] not in omit]
                # A string reference is not automatically a displayed main message.
                for r in rs:
                    if not r['call'].startswith(('msg','c_msg')):
                        r['usage']='reference'
                out.extend(rs)
            elif n.kind=='switch':
                cases=[]
                for case in n.children:
                    children=self.project(name,case.children,omit)
                    if children:cases.append(dict(type='block',label=f'switch ({n.text}) · case {case.text}',children=children))
                out.append(dict(type='blocks',children=cases))
            else:
                # Loops, with and switch scopes are retained without pretending that
                # their iterations/cases execute as one dialogue sequence.
                children=self.project(name,n.children+n.other,omit)
                if children:out.append(dict(type='block',label=n.kind+' ('+n.text+')',children=children))
        return out

    def con_writes(self,source):
        """Token-aware write inventory; opaque expressions remain unknown."""
        tokens=[t.group() for t in self.flow.TOKEN.finditer(source)
                if not t.group().startswith(('//','/*'))]
        out=[]
        for i,t in enumerate(tokens[:-1]):
            if t=='con' and i and tokens[i-1] in ('++','--'):
                out.append(None);continue
            if t!='con' or tokens[i+1] not in ('=','+=','-=','++','--'):continue
            value=None
            if tokens[i+1]=='=':
                rest=tokens[i+2:];sign=-1 if rest and rest[0]=='-' else 1
                if sign==-1:rest=rest[1:]
                if len(rest)>1 and rest[0].isdigit() and rest[1]==';':value=sign*int(rest[0])
            out.append(value)
        return out

    def connect_dialogue_continuations(self,name,nodes,stages,choices,consumed):
        """Attach a unique later dialogue state to the branch that schedules it.

        This bounded rule requires a terminal conditional, an unambiguous literal
        state write, direct dialogue creation, and only con + !d_ex() at the
        consumer. It does not solve arbitrary state-machine reachability.
        """
        data=self.file(name);writes=self.con_writes(data['source'])
        if None in writes:return
        counts=Counter(writes)
        allowed_calls=set(self.gml.FUNCTIONS)|{'d_make','scr_speaker','scr_anyface_next','with'}

        def branches(scope):
            flat=self.flat(scope)
            # No common tail may execute between the branch and its continuation.
            if len(flat)!=1 or flat[0].kind!='if':return
            condition=flat[0]
            for arm,body in (('then',condition.children),('else',condition.other)):
                if not body:continue
                yield condition,arm,body
                yield from branches(body)

        for parent in nodes:
            if self.stage(parent) is None or parent.other or parent.start in consumed or parent.start in choices:continue
            for condition,arm,body in branches(parent.children):
                flat=self.flat(body)
                if any(n.kind not in ('stmt','with') for n in flat):continue
                if any(n.kind=='with' and self.con_writes(data['source'][n.start:n.end]) for n in flat):continue
                span=data['source'][body[0].start:body[-1].end]
                local_writes=self.con_writes(span)
                if len(local_writes)!=1 or local_writes[0] is None:continue
                value=local_writes[0]
                assignments=[n for n in flat if n.kind=='stmt' and re.fullmatch(r'con\s*=\s*'+str(value)+r'\s*;',n.text)]
                if len(assignments)!=1 or counts[value]!=1:continue
                if any(re.match(r'\s*(?:return|exit|break|continue)\b',n.text) for n in self.flow.walk(body)):continue
                local_calls=list(self.calls(span))
                if any(c['call'] not in allowed_calls for c in local_calls):continue
                makers=[n for n in flat if n.kind=='stmt' and any(c['call']=='d_make' for c in self.calls(n.text))]
                if len(makers)!=1:continue
                if not any(self.within(name,n) for n in flat):continue
                if any(r['offset']>makers[0].start for n in flat for r in self.within(name,n)):continue
                if len(stages.get(value,[]))!=1:continue
                target=stages[value][0]
                if target.start<parent.end or target.start in consumed or target.start in choices or target.other:continue
                parts=re.split(r'\s*&&\s*',target.text)
                if len(parts)!=2 or '!d_ex()' not in parts or any(p!='!d_ex()' and not re.fullmatch(r'con\s*==\s*'+str(value),p) for p in parts):continue
                if not self.within(name,target):continue
                # This is a continuation edge, not a re-test of the earlier guard.
                self.continuations[name,condition.start,arm]=target
                consumed.add(target.start)
                line=lambda offset:data['source'].count('\n',0,offset)+1
                self.evidence.append({'rule':'branch_dialogue_continuation','file':name,
                    'condition':condition.text,'branch':arm,'assignment_line':line(assignments[0].start),
                    'state':value,'target_line':line(target.start),'target_guard':target.text,
                    'scope':'unique literal writer and consumer in this file'})

    def local_choice(self,name,n,stages):
        if n.other:return None
        options=self.options(name,n.children)
        if len(options)<2 or sorted(options)!=list(range(len(options))):return None
        data=self.file(name);source=data['source'][n.start:n.end]
        if not re.search(r'\\\\C'+str(len(options)),source):return None
        target=self.state_assignment(n.children)
        if target not in stages or len(stages[target])!=1:return None
        consumer=stages[target][0]
        if consumer.other:return None
        if not re.search(r'global\.choice\s*!=\s*-1',consumer.text):return None
        if re.search(r'global\.choice\s*(?:=(?!=)|\+=|-=|\+\+|--)',data['source'][consumer.start:consumer.end]):return None
        if any(not re.fullmatch(r'(?:con\s*==\s*-?\d+|global\.choice\s*!=\s*-1|!d_ex\(\))',p) for p in re.split(r'\s*&&\s*',consumer.text)):return None
        children=self.flat(consumer.children);mapped={}
        for child in children:
            m=re.fullmatch(r'global\.choice\s*==\s*(\d+)',child.text) if child.kind=='if' else None
            if m and not child.other:mapped[int(m[1])]=child
            elif self.within(name,child):return None
        if set(mapped)!=set(options):return None
        if len(mapped)!=sum(c.kind=='if' and bool(re.fullmatch(r'global\.choice\s*==\s*\d+',c.text)) for c in children):return None
        self.evidence.append({'rule':'local_choice_slots_to_state','file':name,'offset':n.start,'target':consumer.start})
        return {'options':options,'bodies':{i:self.project(name,mapped[i].children) for i in options},
                'consumed':[consumer.start],'omit':{r['occurrence_id'] for r in options.values()}}

    def callback_states(self,name,method,indices):
        data=self.file(name)
        matches=[n for n in data['nodes'] if n.kind=='stmt' and re.match(re.escape(method)+r'\s*=\s*function\s*\(',n.text)]
        if len(matches)!=1:return None
        text=matches[0].text
        match=re.match(re.escape(method)+r'\s*=\s*function\s*\(\s*(\w+)\s*\)\s*\{',text)
        if not match:return None
        body=self.flow.parse(text[match.end():text.rfind('}')])
        def execute(nodes,env):
            for n in self.flat(nodes):
                if n.kind=='if':
                    value=self.flow.constant(n.text,env)
                    if value is self.flow.UNKNOWN:return False
                    if not execute(n.children if value else n.other,env):return False
                elif n.kind=='stmt':
                    a=self.flow.assignments(n.text)
                    if not a or a[0]!='con':return False
                    value=self.flow.constant(a[1],env)
                    if type(value) is not int:return False
                    env['con']=value
                else:return False
            return True
        out={}
        for i in indices:
            env={match[1]:i}
            if not execute(body,env) or 'con' not in env:return None
            out[i]=env['con']
        return out

    def shared_choice(self,name,n,stages):
        if n.other:return None
        data=self.file(name)
        candidates=[c for c in data['calls'] if n.start<=c['offset']<n.end and c['call']=='c_msc' and len(c['args'])==1 and c['args'][0].isdigit()]
        if len(candidates)!=1:return None
        call=candidates[0]
        # Only a direct queued call at the end of this text-bearing block.
        stmts=self.flat(n.children)
        if not any(s.kind=='stmt' and s.start<=call['offset']<s.end for s in stmts):return None
        if any(r['offset']>call['offset'] for r in self.within(name,n)):return None
        helpers=['gml_GlobalScript_scr_text.gml','gml_Object_obj_choicer_neo_Alarm_0.gml','gml_Object_obj_choicer_neo_Other_10.gml','gml_GlobalScript_scr_cutscene_commands.gml','gml_GlobalScript_c_msc.gml']
        if not all(h in self.sources for h in helpers):return None
        # Derive the fixed continuation protocol from engine code, not case IDs.
        alarm=self.file(helpers[1])['source'];other=self.file(helpers[2])['source'];commands=self.file(helpers[3])['source']
        wrapper=self.file(helpers[4])['source']
        if not re.fullmatch(r'\s*function c_msc\(arg0\)\s*\{\s*c_cmd\("msc",\s*arg0,\s*0,\s*0,\s*0\);\s*\}\s*',wrapper):return None
        if not re.search(r'global\.msc\s*\+=\s*1;\s*scr_text\(global\.msc\)',alarm):return None
        if 'global.choice = mychoice;' not in other or not re.search(r'global\.msc\s*=\s*command_arg1\[i\];\s*scr_text\(global\.msc\)',commands):return None
        shared=self.file(helpers[0])
        functions=[x for x in shared['nodes'] if x.kind=='function' and re.fullmatch(r'scr_text\(\s*\w+\s*\)',x.text)]
        if len(functions)!=1:return None
        argument=functions[0].text.split('(')[1].rstrip(')').strip()
        switches=[x for x in self.flow.walk(functions[0].children) if x.kind=='switch' and x.text==argument]
        if len(switches)!=1:return None
        cases={c.text:c for c in switches[0].children};value=int(call['args'][0])
        a,b=cases.get(str(value)),cases.get(str(value+1))
        if not a or not b:return None
        if not a.children or a.children[-1].text!='break;' or not b.children or b.children[-1].text!='break;':return None
        options=self.options(helpers[0],a.children)
        if len(options)<2 or sorted(options)!=list(range(len(options))):return None
        if len(self.within(helpers[0],a))!=len(options):return None
        if not re.search(r'\\\\C'+str(len(options)),shared['source'][a.start:a.end]):return None
        owner=re.fullmatch(r'gml_Object_(.+)_Step_\d+\.gml',name)
        if not owner:return None
        callbacks=[]
        for scope in b.children:
            if scope.kind=='with' and scope.text==owner[1]:
                callbacks += [c for c in shared['calls'] if scope.start<=c['offset']<scope.end and c['args']==['global.choice']]
        if len(callbacks)!=1:return None
        create='gml_Object_'+owner[1]+'_Create_0.gml'
        if create not in self.sources:return None
        states=self.callback_states(create,callbacks[0]['call'],options)
        if not states or len(set(states.values()))!=len(states) or any(v not in stages or len(stages[v])!=1 for v in states.values()):return None
        targets={i:stages[v][0] for i,v in states.items()}
        if any(t.start==n.start for t in targets.values()):return None
        if any(self.root_guard(t) for t in targets.values()):return None
        self.evidence.append({'rule':'queued_choice_callback','file':name,'offset':call['offset'],'case':value,
                              'script':helpers[0],'callback':callbacks[0]['call'],'targets':{i:t.start for i,t in targets.items()}})
        return {'options':options,'bodies':{i:self.project(name,t.children) for i,t in targets.items()},'consumed':[t.start for t in targets.values()],'omit':set()}

    def analyze(self,name):
        self.evidence=[];self.diagnostics=[];self.continuations={}
        data=self.file(name);nodes=data['nodes'];stages={}
        if data.get('parse_error') is not None:self.diagnostics.append({'file':name,'reason':'parse_error','detail':data['parse_error']})
        for n in nodes:
            value=self.stage(n)
            if value is not None:stages.setdefault(value,[]).append(n)
        choices={};consumed=set()
        for n in nodes:
            if self.stage(n) is None:continue
            choice=self.local_choice(name,n,stages) or self.shared_choice(name,n,stages)
            if choice and not consumed.intersection(choice['consumed']) and n.start not in consumed:
                choices[n.start]=choice;consumed.update(choice['consumed'])
        self.connect_dialogue_continuations(name,nodes,stages,choices,consumed)
        blocks=[]
        for n in nodes:
            if n.start in consumed:continue
            plain_stage=self.stage(n) is not None and not n.other
            choice=choices.get(n.start);children=self.project(name,n.children if plain_stage else [n],choice['omit'] if choice else ())
            if choice:
                children.append(dict(type='choice',title='玩家选择',branches=[
                    {'option':r,'body':sequence(choice['bodies'][i])} for i,r in sorted(choice['options'].items())]))
            if not children:continue
            # Stage guards are source metadata, not imagined story labels.
            guard=self.root_guard(n) if plain_stage else ''
            blocks.append(dict(type='block',label='L'+str(data['source'].count('\n',0,n.start)+1),guard=guard,raw_guard=n.text if n.kind=='if' else '',children=children))
        # Unsupported/parser-failed references still belong to the complete file.
        present={r['occurrence_id'] for r in references({'type':'blocks','children':blocks})}
        missing=[r for r in data['refs'] if r['occurrence_id'] not in present]
        for r in missing:blocks.append(dict(type='block',label='L'+str(r['source']['line']),children=[copy.deepcopy(r)],unresolved=True))
        scene=dict(id=f'ch{self.chapter}/'+name,chapter=self.chapter,title=name,file=name,body={'type':'blocks','children':blocks})
        actual=Counter(r['occurrence_id'] for r in references(scene['body']) if r['source']['file']==name)
        expected=Counter(r['occurrence_id'] for r in data['refs'])
        if actual!=expected:raise ValueError('Whole-file reference coverage mismatch: '+name)
        scene['reference_count']=sum(expected.values())
        return scene


def build(files, code, texts=ROOT/'build/texts', out=ROOT/'local/context-files'):
    from context_paths import paths
    code,texts,out=paths(code,texts,out)
    api=backend();scenes=[];evidence=[];hashes={};diagnostics=[]
    tables={ch:{r['key']:r for r in json.loads((texts/f'trilingual_chapter{ch}.json').read_text(encoding='utf-8'))['lines']} for ch in range(1,6)}
    for path in files:
        p=Path(path)
        if len(p.parts)!=2 or not re.fullmatch(r'ch[1-5]',p.parts[0]) or not re.fullmatch(r'gml_\w+\.gml',p.name):raise ValueError('Invalid code path')
        ch=int(p.parts[0][-1]);names=[p.name,'gml_GlobalScript_scr_text.gml','gml_Object_obj_choicer_neo_Alarm_0.gml','gml_Object_obj_choicer_neo_Other_10.gml','gml_GlobalScript_scr_cutscene_commands.gml','gml_GlobalScript_c_msc.gml']
        names.append(re.sub(r'_Step_\d+\.gml$','_Create_0.gml',p.name))
        sources={name:(code/p.parts[0]/name).read_text(encoding='utf-8-sig') for name in set(names) if (code/p.parts[0]/name).exists()}
        source_hashes={name:digest((code/p.parts[0]/name).read_bytes()) for name in sources}
        analyzer=Analyzer(sources,ch,tables[ch],api,source_hashes);scene=analyzer.analyze(p.name);scenes.append(scene)
        evidence.extend(analyzer.evidence);diagnostics.extend(analyzer.diagnostics)
        hashes.update({f'ch{ch}/'+name:record['hash'] for name,record in analyzer.cache.items()})
        print(json.dumps({'file':path,'references':scene['reference_count'],'links':dict(Counter(e['rule'] for e in analyzer.evidence))},ensure_ascii=False),flush=True)
    manifest=(texts/'manifest.json').read_bytes()
    pack={'schema':1,'kind':'automatic-file-context','text_manifest_sha256':digest(manifest),'scenes':scenes}
    validate(pack,manifest,tables)
    out.mkdir(parents=True,exist_ok=True)
    payload=(json.dumps(pack,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    (out/'contexts.json').write_bytes(payload)
    (out/'evidence.json').write_text(json.dumps({'contexts_sha256':digest(payload),'sources':hashes,'rules':evidence,'diagnostics':diagnostics,'coverage':{s['id']:s['reference_count'] for s in scenes}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return pack


if __name__=='__main__':
    from context_paths import parser as context_parser
    parser=context_parser(__doc__,'local/context-files');parser.add_argument('--file',action='append',dest='files')
    args=parser.parse_args();build(args.files or json.loads((ROOT/'config/context-files.json').read_text())['files'],args.code,args.texts,args.out)
