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
from .context_conditions import ROOT, backend, digest
from .context_data import references, validate


def sequence(children):
    return {'type':'sequence','children':children}


def choice_nodes(choice):
    node=dict(type='choice',title='玩家选择',branches=[
        {'option':copy.deepcopy(r),'body':sequence(choice['bodies'][i])} for i,r in sorted(choice['options'].items())])
    tail=choice.get('tail',[])
    if choice.get('prefix'):node['prefix']=sequence(choice['prefix'])
    if tail:node['join_next']=True
    return [node,*tail]


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
        self.scoped_choices={};self.scoped_consumed=set()
        self.queued=None;self.queue_audit=[];self.direct=None;self.direct_audit=[]

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

    def annotate_entry_guards(self,name,scene):
        """Record passed exit checks at their source positions, not live values.

        Only a direct exit/return arm restricts later siblings. Facts do not
        escape a branch, loop, with, switch case or function body. A function
        declaration does not execute its body and starts a fresh fact scope.
        """
        data=self.file(name);conditions={};proofs={}
        def visit(nodes,active=(),function=False):
            active=list(active)
            for n in self.flat(nodes):
                body=self.flat(n.children)
                terminal=body[0].text.strip() if len(body)==1 and body[0].kind=='stmt' else ''
                if (n.kind=='if' and not n.other and not self.within(name,n)
                    and (terminal=='exit;' or (function and re.fullmatch(r'return(?:\s+(?:true|false|-?\d+))?;',terminal)))):
                    line=data['source'].count('\n',0,n.start)+1
                    proof={'condition':inverse(n.text),'source':{'file':name,'line':line},
                           'meaning':'passed_at_source','visible':not bool(re.fullmatch(r'(?:con|customcon)\s*(?:==|!=|<=|>=|<|>)\s*-?\d+',n.text))}
                    active.append(proof);proofs[line,proof['condition']]=proof
                    continue
                if n.kind=='function':
                    visit(n.children,(),True)
                    continue
                if n.kind=='stmt' and any(t.group()=='function' for t in self.flow.TOKEN.finditer(n.text)):
                    for r in self.within(name,n):conditions[r['occurrence_id']]=[]
                    continue
                # Conditions, loop headers and opaque statements may themselves
                # contain references; keep their inherited checks too.
                for r in self.within(name,n):conditions[r['occurrence_id']]=list(active)
                if n.children:visit(n.children,active,function)
                if n.other:visit(n.other,active,function)
        visit(data['nodes'])
        used=set()
        def attach(n,inherited=()):
            rs=list(references(n))
            shared=list(conditions.get(rs[0]['occurrence_id'],())) if rs else []
            for r in rs[1:]:
                other=conditions.get(r['occurrence_id'],())
                shared=shared[:next((i for i,(a,b) in enumerate(zip(shared,other)) if a!=b),min(len(shared),len(other)))]
            # Independent source blocks stay independent, including after an
            # event-level guard; avoid one distant heading for the whole file.
            if n['type']=='blocks':shared=list(inherited)
            own=[p for p in shared if p not in inherited]
            if own:
                n['entry_guards']=own
                used.update((p['source']['line'],p['condition']) for p in own)
            for c in n.get('children',[]):attach(c,shared)
            if 'prefix' in n:attach(n['prefix'],shared)
            for b in n.get('branches',[]):
                # Choice labels remain identity-bearing references as well.
                if 'option' in b:attach(b['option'],shared)
                attach(b['body'],shared)
        attach(scene['body'])
        for identity in sorted(used):
            self.evidence.append({'rule':'passed_exit_guard','file':name,**proofs[identity]})

    def options(self,name,nodes,count=None):
        """Exact-scope literal slots or one array; never guess dynamic/overwritten slots."""
        out={};assignments=set();array_seen=False
        for n in self.flat(nodes):
            match=re.match(r'global\.choicemsg\[(\d+)\]\s*=',n.text) if n.kind=='stmt' else None
            if match:
                slot=int(match[1])
                if slot in out or array_seen:return {}
                rs=self.within(name,n)
                calls=list(self.calls(n.text[match.end():].strip().rstrip(';')))
                expr=n.text[match.end():].strip().rstrip(';').strip()
                if len(rs)==1 and len(calls)==1 and calls[0]['offset']==0 and calls[0]['end']==len(expr):out[slot]=rs[0]
                elif self.gml.as_string_literal(expr)=='' or (len(calls)==1 and calls[0]['call']=='stringset' and calls[0]['offset']==0 and calls[0]['end']==len(expr) and calls[0]['args']==['""']):out[slot]=None
                else:return {}
                assignments.add(n.start)
                continue
            array=re.fullmatch(r'global\.choicemsg\s*=\s*\[([\s\S]*)\]\s*;',n.text) if n.kind=='stmt' else None
            if not array:continue
            if out or array_seen:return {}
            array_seen=True;assignments.add(n.start)
            inner=array[1];args,_,ok=self.gml.split_args('('+inner+')',0)
            if not ok:return {}
            pos=n.start+array.start(1)
            for slot,arg in enumerate(args):
                rs=[r for r in self.within(name,n) if pos<=r['offset']<pos+len(arg)]
                expr=arg.strip();calls=list(self.calls(expr))
                if len(rs)==1 and len(calls)==1 and calls[0]['offset']==0 and calls[0]['end']==len(expr):
                    out[slot]=rs[0]
                elif self.gml.as_string_literal(expr)=='' or (len(calls)==1 and calls[0]['call']=='stringset' and calls[0]['offset']==0 and calls[0]['end']==len(expr) and calls[0]['args']==['""']):
                    out[slot]=None
                else:return {}
                pos+=len(arg)+1
        # Nested/repeated/opaque assignments can change which labels are shown.
        for n in self.flow.walk(nodes):
            if n.kind!='stmt' or n.start in assignments:continue
            tokens=[t.group() for t in self.flow.TOKEN.finditer(n.text) if not t.group().startswith(('//','/*'))]
            if re.search(r'global\.choicemsg(?:\[[^]]*\])?(?:=(?!=)|\+=|-=|\+\+|--)', ''.join(tokens)):return {}
        if count is None:count=len(out)
        if set(out)!=set(range(len(out))) or count>len(out):return {}
        if any(out[i] is None for i in range(count)) or any(out[i] is not None for i in range(count,len(out))):return {}
        return {i:out[i] for i in range(count)}

    def choice_prompt(self,name,nodes):
        """One direct message control, excluding comments and unrelated string literals."""
        found=[]
        for n in self.flat(nodes):
            if n.kind!='stmt':continue
            for c in self.calls(n.text):
                if c['call'] not in ('msgset','msgnext','c_msgset','c_msgnext') and not c['call'].startswith(('msgsetloc','msgnextloc','c_msgsetloc','c_msgnextloc')):continue
                index=1 if 'set' in c['call'] else 0
                if len(c['args'])<=index:continue
                literal=self.gml.as_string_literal(c['args'][index])
                if literal is not None:
                    found.extend((int(m[1]),n.start+c['offset']) for m in re.finditer(r'\\C([2-4])(?!\d)',literal))
        return found[0] if len(found)==1 else None

    def choice_responses(self,name,nodes,indices):
        """Disjoint equality arms, including else-if and an unhandled option.

        Non-choice conditions inside an arm are kept verbatim. A proven common
        suffix stays outside the branches; shared defaults remain unresolved.
        """
        mapped={};default=None
        def chain(n):
            nonlocal default
            m=re.fullmatch(r'global\.choice\s*==\s*(\d+)',n.text) if n.kind=='if' else None
            if not m or int(m[1]) not in indices or int(m[1]) in mapped:return False
            mapped[int(m[1])]=n.children
            tail=self.flat(n.other)
            if not tail:return True
            if len(tail)==1 and tail[0].kind=='if' and re.fullmatch(r'global\.choice\s*==\s*\d+',tail[0].text):return chain(tail[0])
            if default is not None:return False
            default=tail;return True
        children=self.flat(nodes)
        roots=[n for n in children if n.kind=='if']
        last=children.index(roots[-1]) if roots else -1
        common=children[last+1:]
        for n in children:
            if n.kind=='if':
                if not chain(n):return None
            elif self.within(name,n) and n not in common:return None
        if not mapped:return None
        if default is not None:
            remaining=set(indices)-set(mapped)
            if len(roots)!=1 or len(remaining)!=1:return None
            mapped[remaining.pop()]=default
        tail=[]
        if any(self.within(name,n) for n in common):
            if any(n.kind!='stmt' for n in common):return None
            if not self.proven_tail(name,children[:last+1],common):return None
            tail=self.project(name,common)
        return {i:mapped.get(i,[]) for i in indices},tail

    def proven_tail(self,name,branches,following):
        """Only a direct message suffix after fall-through choice arms.

        This is lexical flow, not runtime reachability. Opaque calls, exits,
        loops, another menu and text references in assignments fail closed.
        """
        direct=[]
        for n in self.flat(following):
            if n.kind!='stmt':break
            direct.append(n)
        textual=[i for i,n in enumerate(direct) if self.within(name,n)]
        if not textual:return False
        for n in direct:
            tokens=[t.group() for t in self.flow.TOKEN.finditer(n.text) if not t.group().startswith(('//','/*'))]
            if re.search(r'global\.choice(?:msg)?(?:\[|=(?!=))',''.join(tokens)):return False
            for call in self.calls(n.text):
                if call['call'] in ('scr_readychoicer','c_msc'):return False
                for arg in call['args']:
                    literal=self.gml.as_string_literal(arg)
                    if literal and re.search(r'\\C[2-4]',literal):return False
        checked=branches+direct[:textual[-1]+1]
        allowed=set(k for k in self.gml.FUNCTIONS if k.startswith(('msg','c_msg')))|{
            'scr_speaker','scr_anyface_next','d_make','k_d',
            'c_speaker','c_facenext','c_talk_wait','c_wait','c_sel','c_facing','c_addxy',
            'c_msgside','c_msgsprite','c_sprite','c_imagespeed','c_imageindex','c_halt',
            'c_var_instance','c_sel_sprite','c_sel_facing','c_shakeobj','c_lerp_var_instance',
            'c_walkdirect_wait','c_soundplay','c_autowalk'}
        for n in self.flow.walk(checked):
            if n.kind not in ('block','if','stmt'):return False
            if n.kind=='block':continue
            tokens=[t.group() for t in self.flow.TOKEN.finditer(n.text) if not t.group().startswith(('//','/*'))]
            if any(t in ('return','exit','break','continue','function') for t in tokens):return False
            clean=''.join(tokens)
            if re.search(r'(?:global\.choice(?:msg(?:\[[^]]*\])?)?(?:=(?!=)|\+=|-=|\*=|/=|\+\+|--)|(?:\+\+|--)global\.choice)',clean):return False
            for call in self.calls(n.text):
                if call['call'] not in allowed:return False
                for arg in call['args']:
                    literal=self.gml.as_string_literal(arg)
                    if literal and re.search(r'\\C[2-4]',literal):return False
            if n.kind=='stmt':
                for ref in self.within(name,n):
                    # The localized call must itself be the statement, not a
                    # variable initializer, menu label, or nested expression.
                    if not ref['call'].startswith(('msg','c_msg')) or ref['offset']!=n.start:return False
        return True

    def stage(self,n,variable='con'):
        if n.kind!='if':return None
        parts=re.split(r'\s*&&\s*',n.text)
        matches=[re.fullmatch(re.escape(variable)+r'\s*==\s*(-?\d+)',p) for p in parts]
        values=[int(m[1]) for m in matches if m]
        return values[0] if len(values)==1 else None

    def state_assignment(self,nodes,variable='con'):
        values=[]
        variable=re.escape(variable)
        for n in self.flat(nodes):
            if n.kind=='stmt' and re.fullmatch(variable+r'\s*=\s*-?\d+\s*;',n.text):
                values.append(int(n.text.split('=')[1].strip(' ;')))
            elif any(re.search(r'\b'+variable+r'\s*(?:=(?!=)|\+=|-=|\+\+|--)',c.text) for c in self.flow.walk([n])):
                return None
        return values[-1] if values else None

    def root_guard(self,n,variable='con'):
        if self.stage(n,variable) is None:return n.text
        internal=r'(?:'+re.escape(variable)+r'\s*==\s*-?\d+|customcon\s*==\s*\d+|!d_ex\(\)|global\.interact\s*==\s*\d+|!i_ex\(obj_cutscene_master\))'
        return ' && '.join(p for p in re.split(r'\s*&&\s*',n.text) if not re.fullmatch(internal,p))

    def repeat_choice(self,name,n):
        """A local 0 -> 1 flag transition, not a proof of global visit history."""
        match=re.fullmatch(r'scr_flag_get\(\s*(\d+)\s*\)\s*==\s*0',n.text)
        if not match or not n.other:return None
        flag=int(match[1]);data=self.file(name)
        # Verify the input's helper definitions rather than trusting their names.
        def tokens(source):
            return [t.group() for t in self.flow.TOKEN.finditer(source) if not t.group().startswith(('//','/*'))]
        for helper,args,body in (
            ('get','arg0','return global.flag[arg0];'),
            ('set','arg0,arg1','global.flag[arg0]=arg1;')):
            filename=f'gml_GlobalScript_scr_flag_{helper}.gml'
            if filename not in self.sources:return None
            source=self.file(filename)['source']
            actual=tokens(source);expected=tokens(f'function scr_flag_{helper}({args}){{{body}}}')
            if sum(actual[i:i+len(expected)]==expected for i in range(len(actual)))!=1:return None
        yes=self.flat(n.children);no=self.flat(n.other)
        if not yes or not no or any(c.kind!='stmt' for c in yes+no):return None
        setter=re.fullmatch(r'scr_flag_set\(\s*'+str(flag)+r'\s*,\s*1\s*\)\s*;',yes[0].text)
        if not setter or not any(self.within(name,c) for c in yes) or not any(self.within(name,c) for c in no):return None
        # No opaque side effects, nested writes or early exits in either arm.
        allowed=set(self.gml.FUNCTIONS)|{'scr_speaker'}
        for stmt in yes[1:]+no:
            expr=stmt.text.strip().rstrip(';').strip();calls=list(self.calls(expr))
            if len(calls)!=1 or calls[0]['call'] not in allowed or calls[0]['offset']!=0 or calls[0]['end']!=len(expr):return None
        writes=[]
        for call in data['calls']:
            if call['call'] not in ('scr_flag_set','scr_flag_set_ext'):continue
            args=call['args']
            if not args or not re.fullmatch(r'\d+',args[0].strip()):return None
            if int(args[0])==flag:writes.append(call)
        if len(writes)!=1 or writes[0]['offset']!=yes[0].start:return None
        # Direct or aliased global-array writes are outside this rule's scope.
        clean=''.join(tokens(data['source']))
        if re.search(r'(?:global\.flag(?:\[[^]]*\])?(?:=(?!=)|\+=|-=|\*=|/=|\+\+|--)|(?:\+\+|--)global\.flag)',clean):return None
        proof={'flag':flag,'from':0,'to':1,'write_line':data['source'].count('\n',0,yes[0].start)+1}
        self.evidence.append({'rule':'choice_flag_revisit','file':name,'condition':n.text,**proof,
                              'scope':'local choice; assumes no intervening flag reset'})
        return proof

    def project(self,name,nodes,omit=(),choice_scope=False):
        out=[]
        if self.queued:omit=set(omit)|self.queued.omit
        if self.direct:omit=set(omit)|self.direct.omit
        flat=self.flat(nodes)
        for index,n in enumerate(flat):
            if n.start in self.scoped_consumed:continue
            routes=self.queued.routes if self.queued else None
            route=routes and n.start in routes.edges
            prompts=set(self.prompt_choices)|(set(self.queued.plans) if self.queued else set())
            if self.direct:prompts.update(self.direct.plans)
            if not route and not any(r['occurrence_id'] not in omit for r in self.within(name,n)) and not any(n.start<=p<n.end for p in prompts):continue
            if n.start in self.scoped_choices:
                choice,variable=self.scoped_choices[n.start]
                children=self.project(name,n.children,set(omit)|choice['omit'])
                children.extend(choice_nodes(choice))
                out.append(dict(type='block',label='',guard=self.root_guard(n,variable),raw_guard=n.text,children=children))
                continue
            if n.kind=='if':
                yes=self.project(name,n.children,omit);no=self.project(name,n.other,omit)
                for arm,body in (('then',yes),('else',no)):
                    target=self.continuations.get((name,n.start,arm))
                    if target is not None:body.extend(self.project(name,target.children,omit))
                out.append(dict(type='condition',title='',branches=[
                    {'label':n.text,'body':sequence(yes)},
                    {'label':inverse(n.text),'body':sequence(no)}]))
                if choice_scope:
                    revisit=self.repeat_choice(name,n)
                    if revisit:out[-1]['revisit']=revisit
                if (n.other and re.fullmatch(r'global\.choice\s*==\s*\d+',n.text)
                    and not out[-1].get('revisit') and self.proven_tail(name,[n],flat[index+1:])):
                    out[-1]['join_next']=True
                    next_ref=next(r for following in flat[index+1:] for r in self.within(name,following))
                    self.evidence.append({'rule':'choice_common_tail','file':name,
                        'branch_line':self.file(name)['source'].count('\n',0,n.start)+1,
                        'tail_line':next_ref['source']['line'],'scope':'same lexical block; no opaque transfer before suffix'})
            elif n.kind=='stmt':
                rs=[copy.deepcopy(r) for r in self.within(name,n) if r['occurrence_id'] not in omit]
                # A string reference is not automatically a displayed main message.
                for r in rs:
                    if n.start in self.shared_padding_writes or (not r['call'].startswith(('msg','c_msg')) and n.start not in self.shared_message_writes):
                        r['usage']='reference'
                out.extend(rs)
                if n.start in self.prompt_choices:
                    choice=self.prompt_choices[n.start]
                    nested=choice.get('nested')
                    if nested:self.prompt_choices[nested['prompt']]=nested
                    bodies={i:self.project(name,choice['mapped'][i],choice['omit']) for i in choice['options']}
                    prefix=self.project(name,choice.get('prefix_nodes',[]),choice['omit'])
                    if nested:del self.prompt_choices[nested['prompt']]
                    out.extend(choice_nodes({**choice,'bodies':bodies,'prefix':prefix}))
                if self.queued and n.start in self.queued.plans:
                    out.extend(self.queued.render(n.start))
                if self.direct and n.start in self.direct.plans:
                    out.extend(self.direct.render(n.start))
                if route:
                    out.extend(routes.render(n.start))
            elif n.kind=='switch':
                cases=[]
                plans={};consumed=set()
                if self.is_shared_switch(name,n):
                    from .shared_cases import SharedCases
                    planner=SharedCases(self,name)
                    plans,consumed=planner.plan(n)
                    self.shared_rejections=planner.rejections
                for case in n.children:
                    if case.start in consumed:continue
                    choice=plans.get(case.start)
                    if choice:self.prompt_choices[choice['prompt']]=choice
                    children=self.project(name,case.children,set(omit)|(choice['omit'] if choice else set()))
                    if choice:del self.prompt_choices[choice['prompt']]
                    if children:cases.append(dict(type='block',label=f'switch ({n.text}) · case {case.text}',children=children))
                out.append(dict(type='blocks',children=cases))
            else:
                # Loops, with and switch scopes are retained without pretending that
                # their iterations/cases execute as one dialogue sequence.
                children=self.project(name,n.children+n.other,omit)
                if children:out.append(dict(type='block',label=n.kind+' ('+n.text+')',children=children))
        return out

    def is_shared_switch(self,name,node):
        if name!='gml_GlobalScript_scr_text.gml':return False
        functions=[n for n in self.file(name)['nodes'] if n.kind=='function' and re.fullmatch(r'scr_text\(\s*\w+\s*\)',n.text)]
        if len(functions)!=1:return False
        fn=functions[0];body=self.flat(fn.children)
        return len(body)==1 and body[0] is node and node.text==fn.text.split('(')[1].rstrip(')').strip()

    def con_writes(self,source,variable='con',strict=False):
        """Token-aware write inventory; opaque expressions remain unknown."""
        tokens=[t.group() for t in self.flow.TOKEN.finditer(source)
                if not t.group().startswith(('//','/*'))]
        out=[]
        for i,t in enumerate(tokens[:-1]):
            if t==variable and i and tokens[i-1] in ('++','--'):
                out.append(None);continue
            if t!=variable or tokens[i+1] not in ('=','+=','-=','*=','/=','++','--'):continue
            if strict and i and tokens[i-1] in ('.','var','static','globalvar'):
                out.append(None);continue
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

    def local_choice(self,name,n,stages,variable='con',scope=None):
        if n.other:return None
        prompt=self.choice_prompt(name,n.children)
        if prompt is None:return None
        count,prompt_offset=prompt
        options=self.options(name,n.children,count)
        if len(options)<2 or sorted(options)!=list(range(len(options))):return None
        data=self.file(name)
        if any(r['offset']>prompt_offset for r in self.within(name,n)):return None
        target=self.state_assignment(n.children,variable)
        if target not in stages or len(stages[target])!=1:return None
        consumer=stages[target][0]
        if consumer.other or consumer.start<n.end:return None
        if not re.search(r'global\.choice\s*!=\s*-1',consumer.text):return None
        tokens=[t.group() for t in self.flow.TOKEN.finditer(data['source'][consumer.start:consumer.end]) if not t.group().startswith(('//','/*'))]
        clean=''.join(tokens)
        if re.search(r'(?:global\.choice(?:=(?!=)|\+=|-=|\*=|/=|\+\+|--)|(?:\+\+|--)global\.choice)',clean):return None
        if any(t in ('return','exit','break','continue') for t in tokens):return None
        if any(not re.fullmatch(r'(?:'+re.escape(variable)+r'\s*==\s*-?\d+|global\.choice\s*!=\s*-1|!d_ex\(\))',p) for p in re.split(r'\s*&&\s*',consumer.text)):return None
        responses=self.choice_responses(name,consumer.children,options)
        if responses is None:return None
        mapped,tail=responses
        # Multiple producers of the same response state are not a unique dialogue.
        scope_source=data['source'] if scope is None else scope
        writes=self.con_writes(scope_source,variable,strict=scope is not None)
        if writes.count(target)!=1 or (scope is not None and None in writes):return None
        bodies={i:self.project(name,mapped[i],choice_scope=True) for i in options}
        self.evidence.append({'rule':'local_choice_slots_to_state','file':name,'offset':n.start,'target':consumer.start,
                              'option_count':len(options),'empty_options':[i for i in options if not any(self.within(name,c) for c in mapped[i])]})
        if tail:
            self.evidence[-1]['common_tail_line']=next(references(sequence(tail)))['source']['line']
        return {'options':options,'bodies':bodies,'tail':tail,
                'consumed':[consumer.start],'omit':{r['occurrence_id'] for r in options.values()}}

    def connect_scoped_choices(self,name,nodes,excluded):
        """Match bare state variables only among siblings of one lexical scope.

        Each with statement has a separate owner, even when its expression is the
        same. Never cross if arms, loops, functions, or a producer already linked.
        """
        data=self.file(name);source=data['source']
        file_tokens=' '.join(t.group() for t in self.flow.TOKEN.finditer(source) if not t.group().startswith(('//','/*')))
        def visit(scope,owner,trail):
            flat=self.flat(scope);stages={}
            for n in flat:
                if n.kind!='if' or n.start in excluded:continue
                for part in re.split(r'\s*&&\s*',n.text):
                    m=re.fullmatch(r'([A-Za-z_]\w*)\s*==\s*(-?\d+)',part)
                    if m and m[1]!='con':stages.setdefault(m[1],{}).setdefault(int(m[2]),[]).append(n)
            owner_source='\n'.join(source[n.start:n.end] for n in self.flat(owner))
            for n in flat:
                if n.start in excluded or n.start in self.scoped_consumed:continue
                candidates=[var for var in stages if self.stage(n,var) is not None]
                if len(candidates)!=1:continue
                var=candidates[0]
                # GML locals can remain visible inside with; their declaration
                # elsewhere in the event makes instance ownership ambiguous.
                if re.search(r'\b(?:var|static|globalvar)\b[^;]*\b'+re.escape(var)+r'\b',file_tokens):continue
                if list(self.flow.split_top(n.text,('||','or'))):continue
                target=self.state_assignment(n.children,var)
                targets=stages[var].get(target,[])
                if len(targets)!=1 or flat.index(targets[0])!=flat.index(n)+1:continue
                # Reject delayed/dynamic writes named through strings, and opaque
                # scope changes inside the prompt. The response may draw in with.
                if any(var==self.gml.as_string_literal(arg) for call in self.calls(owner_source) for arg in call['args']):continue
                if any(c.kind in ('with','while','for','repeat','function') for c in self.flow.walk(n.children)):continue
                if any(t.group() in ('return','exit','break','continue') for t in self.flow.TOKEN.finditer(source[n.start:n.end])):continue
                prompt=self.choice_prompt(name,n.children)
                resets=[c for c in self.flat(n.children) if c.kind=='stmt' and re.fullmatch(r'global\.choice\s*=\s*-1\s*;',c.text)]
                if prompt is None or len(resets)!=1 or resets[0].end>prompt[1]:continue
                if self.con_writes(source[n.start:n.end],'choice')!=[-1]:continue
                before=len(self.evidence)
                choice=self.local_choice(name,n,stages[var],var,owner_source)
                if not choice:continue
                if any(offset in excluded or offset in self.scoped_choices or offset in self.scoped_consumed for offset in choice['consumed']):
                    del self.evidence[before:];continue
                self.scoped_choices[n.start]=(choice,var);self.scoped_consumed.update(choice['consumed'])
                proof=self.evidence[-1]
                proof.update(rule='scoped_choice_slots_to_state',state_variable=var,from_state=self.stage(n,var),
                             to_state=self.state_assignment(n.children,var),scope=trail,
                             source_line=source.count('\n',0,n.start)+1,
                             target_line=source.count('\n',0,targets[0].start)+1)
            for n in flat:
                if n.start in excluded or n.start in self.scoped_choices or n.start in self.scoped_consumed:continue
                line=source.count('\n',0,n.start)+1
                if n.kind=='with' and re.fullmatch(r'[A-Za-z_]\w*',n.text):
                    visit(n.children,n.children,trail+[{'kind':'with','expression':n.text,'line':line}])
                elif n.kind=='if':
                    for arm,body in (('then',n.children),('else',n.other)):
                        visit(body,owner,trail+[{'kind':'if','expression':n.text,'arm':arm,'line':line}])
        visit(nodes,nodes,[])

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
        prompt=self.choice_prompt(helpers[0],a.children)
        if prompt is None:return None
        options=self.options(helpers[0],a.children,prompt[0])
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
        self.queued=None;self.queue_audit=[];self.direct=None;self.direct_audit=[]
        self.scoped_choices={};self.scoped_consumed=set()
        self.prompt_choices={};self.shared_rejections={}
        self.shared_message_writes=set();self.shared_padding_writes=set()
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
        self.connect_scoped_choices(name,nodes,set(choices)|consumed)
        from .queued_choices import QueuedChoices
        self.queued=QueuedChoices(self,name,set(choices)|consumed|set(self.scoped_choices)|self.scoped_consumed).build()
        self.queue_audit=self.queued.audit
        from .direct_choices import DirectChoices
        excluded=set(choices)|consumed|set(self.scoped_choices)|self.scoped_consumed|self.queued.consumed
        excluded.update(p['root'].start for p in self.queued.plans.values())
        self.direct=DirectChoices(self,name,excluded).build()
        self.direct_audit=self.direct.audit
        blocks=[]
        for n in nodes:
            if n.start in consumed or n.start in self.scoped_consumed or n.start in self.queued.consumed or n.start in self.direct.consumed:continue
            plain_stage=self.stage(n) is not None and not n.other
            choice=choices.get(n.start);children=self.project(name,n.children if plain_stage else [n],choice['omit'] if choice else ())
            if choice:
                children.extend(choice_nodes(choice))
            if not children:continue
            # Stage guards are source metadata, not imagined story labels.
            guard=self.root_guard(n) if plain_stage else ''
            blocks.append(dict(type='block',label='L'+str(data['source'].count('\n',0,n.start)+1),guard=guard,raw_guard=n.text if n.kind=='if' else '',children=children))
            if self.queued.routes and n.start in self.queued.routes.anchors:
                blocks[-1]['anchor']=self.queued.routes.anchors[n.start]
        # Unsupported/parser-failed references still belong to the complete file.
        present={r['occurrence_id'] for r in references({'type':'blocks','children':blocks})}
        missing=[r for r in data['refs'] if r['occurrence_id'] not in present]
        for r in missing:blocks.append(dict(type='block',label='L'+str(r['source']['line']),children=[copy.deepcopy(r)],unresolved=True))
        scene=dict(id=f'ch{self.chapter}/'+name,chapter=self.chapter,title=name,file=name,body={'type':'blocks','children':blocks})
        actual=Counter(r['occurrence_id'] for r in references(scene['body']) if r['source']['file']==name)
        expected=Counter(r['occurrence_id'] for r in data['refs'])
        if actual!=expected:raise ValueError('Whole-file reference coverage mismatch: '+name)
        scene['reference_count']=sum(expected.values())
        self.annotate_entry_guards(name,scene)
        return scene


def build(files, code, texts=ROOT/'build/texts', out=ROOT/'local/context-files'):
    from .context_paths import paths
    from .build_context_all import Sources
    code,texts,out=paths(code,texts,out)
    api=backend();scenes=[];evidence=[];hashes={};diagnostics=[];queue_audit=[];direct_audit=[]
    tables={ch:{r['key']:r for r in json.loads((texts/f'trilingual_chapter{ch}.json').read_text(encoding='utf-8'))['lines']} for ch in range(1,6)}
    for path in files:
        p=Path(path)
        if len(p.parts)!=2 or not re.fullmatch(r'ch[1-5]',p.parts[0]) or not re.fullmatch(r'gml_\w+\.gml',p.name):raise ValueError('Invalid code path')
        ch=int(p.parts[0][-1])
        sources=Sources(code/p.parts[0]);source_hashes=sources.hashes
        analyzer=Analyzer(sources,ch,tables[ch],api,source_hashes);scene=analyzer.analyze(p.name);scenes.append(scene)
        evidence.extend(analyzer.evidence);diagnostics.extend(analyzer.diagnostics)
        queue_audit.extend({'chapter':ch,**e} for e in analyzer.queue_audit)
        direct_audit.extend({'chapter':ch,**e} for e in analyzer.direct_audit)
        hashes.update({f'ch{ch}/'+name:record['hash'] for name,record in analyzer.cache.items()})
        print(json.dumps({'file':path,'references':scene['reference_count'],'links':dict(Counter(e['rule'] for e in analyzer.evidence))},ensure_ascii=False),flush=True)
    manifest=(texts/'manifest.json').read_bytes()
    pack={'schema':1,'kind':'automatic-file-context','text_manifest_sha256':digest(manifest),'scenes':scenes}
    validate(pack,manifest,tables)
    out.mkdir(parents=True,exist_ok=True)
    payload=(json.dumps(pack,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    (out/'contexts.json').write_bytes(payload)
    (out/'evidence.json').write_text(json.dumps({'contexts_sha256':digest(payload),'sources':hashes,'rules':evidence,'queued_menus':queue_audit,'direct_menus':direct_audit,'diagnostics':diagnostics,'coverage':{s['id']:s['reference_count'] for s in scenes}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return pack


if __name__=='__main__':
    from .context_paths import parser as context_parser
    parser=context_parser(__doc__,'local/context-files');parser.add_argument('--file',action='append',dest='files')
    args=parser.parse_args();build(args.files or json.loads((ROOT/'config/context-files.json').read_text())['files'],args.code,args.texts,args.out)
