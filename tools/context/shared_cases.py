"""Bounded scr_text menu protocol; no case IDs or dialogue keys are recipes."""
import re

WRITE=r'(?:(?:[+*/%&|^\-]|<<|>>)?=(?!=)|\+\+|--)'


class SharedCases:
    def __init__(self,analyzer,name):
        self.a=analyzer;self.name=name;self.rejections={}

    def tokens(self,text):
        return [t.group() for t in self.a.flow.TOKEN.finditer(text) if not t.group().startswith(('//','/*'))]

    def protocol(self):
        a=self.a
        required={
            'gml_Object_obj_choicer_neo_Other_10.gml':['global.choice = mychoice; alarm[0] = 1;'],
            'gml_Object_obj_choicer_neo_Alarm_0.gml':['global.msc += 1; scr_text(global.msc);'],
            'gml_Object_obj_choicer_neo_Create_0.gml':['global.choice = -1;'],
            'gml_Object_obj_choicer_neo_Step_0.gml':['if (left_h()) mychoice = 0;',
                ('if (right_h()) mychoice = 1;','if (choicetotal >= 1 && right_h()) mychoice = 1;'),
                ('if (up_h()) mychoice = 2;','if (choicetotal >= 2 && up_h()) mychoice = 2;'),
                ('if (down_h()) mychoice = 3;','if (choicetotal >= 3 && down_h()) mychoice = 3;')],
            'gml_Object_obj_choicer_neo_Draw_0.gml':['string_hash_to_newline(global.choicemsg[i])'],
            'gml_Object_obj_writer_Draw_0.gml':['if (nextchar == "C")',
                'if (nextchar2 == "2" || nextchar2 == "3" || nextchar2 == "4")',
                'choicer = instance_create(0, 0, obj_choicer_neo); choicer.choicetotal = real(nextchar2) - 1;'],
        }
        for name,fragments in required.items():
            if name not in a.sources:return None
            tokens=self.tokens(a.file(name)['source'])
            for fragment in fragments:
                alternatives=fragment if isinstance(fragment,tuple) else (fragment,)
                matches=0
                for variant in alternatives:
                    wanted=self.tokens(variant)
                    matches+=sum(tokens[i:i+len(wanted)]==wanted for i in range(len(tokens)))
                if matches<1 or (matches!=1 and name!='gml_Object_obj_choicer_neo_Draw_0.gml'):return None
            clean=''.join(tokens)
            expected={'gml_Object_obj_choicer_neo_Other_10.gml':('global.choice','global.choice=mychoice'),
                      'gml_Object_obj_choicer_neo_Alarm_0.gml':('global.msc','global.msc+=1'),
                      'gml_Object_obj_choicer_neo_Create_0.gml':('global.choice','global.choice=-1'),
                      'gml_Object_obj_writer_Draw_0.gml':('choicer.choicetotal','choicer.choicetotal=real(nextchar2)-1')}.get(name)
            if expected:
                assignments=re.findall(re.escape(expected[0])+r'(?:=(?!=)|\+=|-=|\*=|/=|\+\+|--)[^;]*',clean)
                if assignments!=[expected[1]]:return None
        # Exclude literal entry points that bypass scr_text(global.msc). An
        # unbounded indirect entry invalidates this narrow rule entirely.
        excluded=set();literal_entries=[]
        for name in a.sources:
            source=a.sources[name]
            if 'scr_text' in source:
                tokens=self.tokens(source)
                for i,t in enumerate(tokens):
                    if t=='"scr_text"':return None
                    if t!='scr_text' or (i and tokens[i-1]=='function'):continue
                    if i+1==len(tokens) or tokens[i+1]!='(':return None
                for call in a.calls(source):
                    if call['call']!='scr_text':continue
                    if re.search(r'\bfunction\s*$',source[:call['offset']]):continue
                    if call['args']==['global.msc']:continue
                    if len(call['args'])==1 and re.fullmatch(r'\d+',call['args'][0]):
                        value=int(call['args'][0]);bound=False
                        # Only an immediately preceding sibling assignment can
                        # establish the literal entry's matching message index.
                        # A matching assignment in another branch is insufficient.
                        def scan(nodes):
                            nonlocal bound
                            flat=a.flat(nodes)
                            for index,n in enumerate(flat):
                                if n.start==call['offset'] and index:
                                    previous=flat[index-1]
                                    if previous.kind=='stmt' and self.tokens(previous.text)==self.tokens(f'global.msc={value};'):
                                        bound=True
                                scan(n.children);scan(n.other)
                        scan(a.flow.parse(source))
                        if not bound:excluded.add(value)
                        else:literal_entries.append({'file':name,'line':source.count('\n',0,call['offset'])+1,'value':value})
                    else:return None
            if hasattr(a.sources,'loaded') and name not in a.cache:a.sources.loaded.pop(name,None)
        return {'helpers':list(required),'excluded_literal_entries':sorted(excluded),'bound_literal_entries':literal_entries}

    def message(self,n):
        """Only direct message-buffer writes/calls, including CH1 key lookups."""
        a=self.a
        if n.kind!='stmt':return None
        assignment=re.fullmatch(r'global\.msg\[(\d+)\]\s*=\s*([\s\S]*);',n.text)
        expr=assignment[2].strip() if assignment else n.text.strip().rstrip(';').strip()
        literal=a.gml.as_string_literal(expr)
        if assignment and literal is not None:return literal
        calls=list(a.calls(expr))
        if len(calls)!=1 or calls[0]['offset']!=0 or calls[0]['end']!=len(expr):return None
        call=calls[0];spec=a.gml.FUNCTIONS.get(call['call'])
        if not assignment and not call['call'].startswith(('msgset','msgnext')):return None
        if spec:
            if spec[0] is not None:return a.gml.as_string_literal(call['args'][spec[0]])
            key=a.gml.as_string_literal(call['args'][spec[1]])
            return a.tables.get(key,{}).get('en')
        if call['call'] in ('msgset','msgnext'):return a.gml.as_string_literal(call['args'][1 if call['call']=='msgset' else 0])
        return None

    def prompts(self,nodes,before=(),after=()):
        a=self.a;flat=a.flat(nodes);found=[]
        for i,n in enumerate(flat):
            prefix=list(before)+flat[:i];suffix=flat[i+1:]+list(after)
            text=self.message(n)
            if text is not None:
                markers=re.findall(r'\\C([2-4])(?!\d)',text)
                if len(markers)==1:found.append((n,int(markers[0]),prefix,suffix))
                elif markers:found.extend([(n,0,prefix,suffix)]*len(markers))
            if n.kind=='if':
                found+=self.prompts(n.children,prefix,suffix)
                found+=self.prompts(n.other,prefix,suffix)
        return found

    def options(self,menu,count):
        a=self.a;options={};assignments=[]
        for n in a.flat(menu.children):
            m=re.fullmatch(r'global\.choicemsg\[(\d+)\]\s*=\s*([\s\S]*);',n.text) if n.kind=='stmt' else None
            if not m:continue
            slot=int(m[1]);refs=a.within(self.name,n);expr=m[2].strip();calls=list(a.calls(expr))
            if slot in options:return None
            if len(refs)==1 and len(calls)==1 and calls[0]['offset']==0 and calls[0]['end']==len(expr):
                ref=refs[0];en=a.tables.get(ref['key'],{}).get('en')
                if en is None or ref.get('binding'):return None
                options[slot]=(ref,en)
            elif a.gml.as_string_literal(expr) is not None:options[slot]=(None,a.gml.as_string_literal(expr))
            else:return None
            assignments.append(n.start)
        if any(i not in options or options[i][0] is None or not options[i][1].strip() for i in range(count)):return None
        if any(text.strip() for i,(_,text) in options.items() if i>=count):return None
        for n in a.flow.walk(menu.children):
            if n.kind=='stmt' and n.start not in assignments and re.search(r'global\.choicemsg', ''.join(self.tokens(n.text))):return None
        return {i:options[i][0] for i in range(count)}

    def plan(self,switch):
        a=self.a
        if self.name!='gml_GlobalScript_scr_text.gml':return {},set()
        protocol=self.protocol()
        if protocol is None:return {},set()
        plans={};consumed=set();cases=switch.children
        for menu,response in zip(cases,cases[1:]):
            if menu.start in consumed or not menu.text.isdigit() or not response.text.isdigit():continue
            value=int(menu.text)
            if int(response.text)!=value+1 or {value,value+1}&set(protocol['excluded_literal_entries']):continue
            def reject(reason):self.rejections[value]=reason
            # Both cases must terminate rather than fall through, and no later
            # duplicate case label can compete for these entry points.
            if any(sum(c.text==label for c in cases)!=1 for label in (menu.text,response.text)):continue
            menu_nodes=a.flat(menu.children);response_nodes=a.flat(response.children)
            if not menu_nodes or not response_nodes or menu_nodes[-1].text!='break;' or response_nodes[-1].text!='break;':continue
            prompts=self.prompts(menu.children)
            if len(prompts)!=1:reject('non_unique_prompt');continue
            prompt,count,before,after=prompts[0]
            options=self.options(menu,count)
            if not options:reject('dynamic_or_missing_options');continue
            if any(r['offset']>prompt.start for r in options.values()):reject('late_option_assignment');continue
            if any(n.kind!='stmt' for n in before+after):reject('complex_prompt_path');continue
            if any('%' in (self.message(n) or '') or re.search(r'\\C\d',self.message(n) or '') for n in before):reject('earlier_message_end');continue
            if any(self.message(n) is not None for n in after):reject('message_after_prompt');continue
            safe=set(a.gml.FUNCTIONS)|{'msgset','msgnext','scr_speaker'}
            if any(c['call'] not in safe for n in a.flow.walk(menu.children) if n.kind!='block' for c in a.calls(n.text)):
                reject('opaque_menu_call');continue
            menu_token_list=self.tokens(a.file(self.name)['source'][menu.start:menu.end])
            menu_tokens=''.join(menu_token_list)
            response_tokens=self.tokens(a.file(self.name)['source'][response.start:response.end])
            if any(t in ('return','exit','continue','function') for t in menu_token_list+response_tokens) or menu_token_list.count('break')!=1 or response_tokens.count('break')!=1:
                reject('early_transfer');continue
            if re.search(r'global\.(?:msc|choice)'+WRITE+r'|(?:\+\+|--)global\.(?:msc|choice)',menu_tokens):reject('menu_protocol_write');continue
            if re.search(r'global\.choice(?:msg)?(?:\[|'+WRITE+r')|(?:\+\+|--)global\.choice', ''.join(response_tokens)):
                reject('new_menu_or_choice_write');continue
            if self.prompts(response.children):reject('response_opens_menu');continue
            roots=[n for n in response_nodes[:-1] if n.kind=='if']
            # One exclusive if/else chain avoids re-evaluating an answer after
            # an opaque side effect in a preceding independent if arm.
            if len(roots)!=1:reject('non_exclusive_response');continue
            first=response_nodes.index(roots[0])
            if any(c['call'] not in safe for n in response_nodes[:first] for c in a.calls(n.text)):
                reject('opaque_response_prefix');continue
            matched=a.choice_responses(self.name,response.children,options)
            if matched is None:reject('unmapped_response_or_common_text');continue
            mapped,tail=matched
            if tail:reject('common_response_tail');continue
            # Each visible answer must have its own lexical response arm.
            if any(not mapped[i] for i in options):reject('missing_response_arm');continue
            plans[menu.start]={'options':options,'mapped':mapped,'prompt':prompt.start,
                'consumed':response.start,'omit':{r['occurrence_id'] for r in options.values()}}
            a.shared_message_writes.update(n.start for n in a.flow.walk(menu.children+response.children)
                if self.message(n) is not None)
            consumed.add(response.start)
            a.evidence.append({'rule':'shared_case_choice','file':self.name,'menu_case':value,'response_case':value+1,
                'menu_line':a.file(self.name)['source'].count('\n',0,menu.start)+1,
                'response_line':a.file(self.name)['source'].count('\n',0,response.start)+1,
                'option_count':count,'entry':'scr_text(global.msc)','protocol':protocol})
        return plans,consumed
