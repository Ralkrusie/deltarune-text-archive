"""Source-checked, bounded summaries for queued local dialogue choices.

The safety summary concerns construction of one command queue in one event.
It does not execute queued animation or prove that a scene is reachable.
"""
import re
from dataclasses import replace


NUMBER = r'-?\d+(?:\.\d+)?'
PURE = {'abs', 'ceil', 'floor', 'round', 'min', 'max', 'clamp', 'array_length',
        'instance_exists', 'variable_global_exists', 'sin', 'cos', 'point_distance', 'string'}
# These commands contain no new menu, indirect function execution, room change
# or state write. Their wrappers must still be proved to do nothing but enqueue.
COMMANDS = {'select', 'sprite', 'imageindex', 'imagespeed', 'imagealpha', 'autowalk',
    'autofacing', 'autodepth', 'walkdirect', 'walk', 'facing', 'addxy', 'setxy',
    'visible', 'depth', 'wait', 'waitif', 'speaker', 'msgfacenext', 'msgface',
    'msgset', 'msgnext', 'talk', 'waitdialoguer', 'msgside', 'msgstay', 'msgsnd',
    'actortokris', 'actortocaterpillar', 'actortocaterpillarstill', 'panobj', 'pan',
    'pannable', 'sndplay', 'snd_play', 'soundplay', 'shakeobj', 'mus2', 'mus', 'fe', 'waitbox', 'halt'}
VISUAL_FIELDS = {'x', 'y', 'sprite_index', 'image_index', 'image_speed', 'image_alpha',
    'image_blend', 'image_xscale', 'image_yscale', 'visible', 'depth', 'facing'}


class QueuedProtocol:
    def __init__(self, analyzer, name):
        self.a=analyzer;self.name=name;self.reason='';self.helpers=set();self._ready=None
        self._functions={};self._checking=set();self._commands={};self.effects=set()

    def fail(self,reason):
        self.reason=reason;return False

    def tokens(self,text):
        return [t.group() for t in self.a.flow.TOKEN.finditer(text)
                if not t.group().startswith(('//','/*'))]

    def compact(self,text):return ''.join(self.tokens(text))

    def writes(self,text,variable):
        """Token-based direct writes, including unexpected update operators."""
        clean=self.compact(text)
        result=re.findall(re.escape(variable)+r'(?:=(?!=)|\+=|-=|\*=|/=|\+\+|--)[^;]*',clean)
        if re.search(r'(?:\+\+|--)'+re.escape(variable),clean):result.append('prefix_update')
        return result

    def source(self,name):
        if name not in self.a.sources:return None
        self.helpers.add(name)
        return self.a.file(name)['source']

    def function(self,name):
        if name in self._functions:return self._functions[name]
        preferred='gml_GlobalScript_'+name+'.gml';found=[]
        if preferred in self.a.sources:candidates=[preferred]
        else:
            index=getattr(self.a,'_queued_function_index',None)
            if index is None:
                index={}
                for filename in self.a.sources:
                    if not filename.startswith('gml_GlobalScript_'):continue
                    source=self.a.sources[filename]
                    for m in re.finditer(r'(?m)^function\s+(\w+)\s*\(',source):
                        index.setdefault(m[1],[]).append(filename)
                    if hasattr(self.a.sources,'loaded') and filename not in self.a.cache:
                        self.a.sources.loaded.pop(filename,None)
                self.a._queued_function_index=index
            candidates=index.get(name,[])
        for filename in candidates:
            source=self.source(filename)
            for node in self.a.file(filename)['nodes']:
                if node.kind=='function' and re.match(re.escape(name)+r'\s*\(',node.text):
                    found.append((filename,node,source))
        self._functions[name]=found[0] if len(found)==1 else None
        return self._functions[name]

    def exact_function(self,name,body):
        fn=self.function(name)
        return bool(fn and self.compact(fn[2][fn[1].start:fn[1].end])==self.compact(body))

    def ready(self):
        if self._ready is not None:return self._ready
        self._ready=False
        # Verify the queue writer, rather than trusting a c_ function prefix.
        for name,count in (('c_cmd',4),('c_cmd_x',6)):
            arguments=', '.join('arg'+str(i) for i in range(count+1))
            writes=''.join('obj_cutscene_master.command_arg%d[__cs_i] = arg%d;'%(i,i)
                           for i in range(1,count+1))
            body='function '+name+'('+arguments+'){if(instance_exists(obj_cutscene_master)){'+\
                '__cs_i=obj_cutscene_master.maximum_command-1;obj_cutscene_master.command[__cs_i]=arg0;'+\
                writes+'with(obj_cutscene_master)maximum_command++;}}'
            if not self.exact_function(name,body):return self.fail('queue_writer_protocol')
        exact={
            'c_customfunc':'function c_customfunc(arg0,arg1=-1){if(instance_exists(obj_cutscene_master)){with(obj_cutscene_master)array_push(customfuncs,arg0);c_cmd("customfunc",arg1,0,0,0);}}',
            'c_waitcustom':'function c_waitcustom(){c_cmd("waitcustom",0,0,0,0);}',
            'c_waitcustom_end':'function c_waitcustom_end(){with(obj_cutscene_master){cs_wait_custom=0;waiting=0;}}',
            'c_msgset':'function c_msgset(arg0,arg1){c_cmd("msgset",arg0,arg1,0,0);}',
            'scr_cutscene_make':'function scr_cutscene_make(){_cutscene_master=instance_create(0,0,obj_cutscene_master);_cutscene_master.master_object=id;return _cutscene_master;}',
        }
        for name,body in exact.items():
            if not self.exact_function(name,body):return self.fail(name+'_protocol')
        engine=self.function('scr_cutscene_commands')
        if not engine:return self.fail('missing_queue_engine')
        wanted={
            'waitcustom':'with(master_object)customcon=1;cs_wait_custom=1;waiting=1;breakme=1;',
            'customfunc':'if(object_index==obj_cutscene_delaycmd||object_index==obj_cutscene_messagecmd){if(command_arg1[i]!=-1)command_arg2[i](command_arg1[i]);else command_arg2[i]();}else if(array_length(customfuncs)>0){if(command_arg1[i]!=-1)customfuncs[0](command_arg1[i]);else customfuncs[0]();array_delete(customfuncs,0,1);}',
            'msgset':'msgset(command_arg1[i],command_arg2[i]);',
            'msgnext':'msgnext(command_arg1[i]);',
        }
        for command,body in wanted.items():
            matches=[n for n in self.a.flat(engine[1].children)
                     if n.kind=='if' and self.compact(n.text)==self.compact('_c=="'+command+'"')]
            if len(matches)!=1 or matches[0].other:return self.fail('queue_command_'+command)
            actual=''.join(engine[2][n.start:n.end] for n in self.a.flat(matches[0].children))
            variants=[body]
            if command=='customfunc':
                variants.append(body.replace('||object_index==obj_cutscene_messagecmd',''))
            if not any(self.compact(actual)==self.compact(v) for v in variants):return self.fail('queue_command_'+command)
        other=self.source('gml_Object_obj_choicer_neo_Other_10.gml')
        alarm=self.source('gml_Object_obj_choicer_neo_Alarm_0.gml')
        if other is None or self.compact(other)!=self.compact('if(canchoose==1&&choiced==0){choiced=1;global.choice=mychoice;alarm[0]=1;}'):
            return self.fail('chooser_answer_protocol')
        if alarm is None or self.compact('global.msc+=1;scr_text(global.msc);') not in self.compact(alarm):
            return self.fail('chooser_return_protocol')
        if self.writes(alarm,'global.choice') or self.writes(alarm,'global.msc')!=['global.msc+=1']:
            return self.fail('chooser_return_changes_answer')
        fragments={
            'gml_Object_obj_choicer_neo_Create_0.gml':['global.choice=-1;'],
            'gml_Object_obj_choicer_neo_Step_0.gml':['if(left_h())mychoice=0;',
                'if(choicetotal>=1&&right_h())mychoice=1;',
                'if(choicetotal>=2&&up_h())mychoice=2;',
                'if(choicetotal>=3&&down_h())mychoice=3;'],
            'gml_Object_obj_choicer_neo_Draw_0.gml':['string_hash_to_newline(global.choicemsg[i])'],
            'gml_Object_obj_writer_Draw_0.gml':['if(nextchar=="C")',
                'if(nextchar2=="2"||nextchar2=="3"||nextchar2=="4")',
                'choicer=instance_create(0,0,obj_choicer_neo);choicer.choicetotal=real(nextchar2)-1;'],
        }
        for filename,required in fragments.items():
            source=self.source(filename)
            if source is None or any(self.compact(f) not in self.compact(source) for f in required):
                return self.fail('choice_control_protocol')
            expected=['global.choice=-1'] if filename.endswith('obj_choicer_neo_Create_0.gml') else []
            if self.writes(source,'global.choice')!=expected or self.writes(source,'global.msc'):
                return self.fail('choice_control_extra_write')
            if filename.endswith('obj_writer_Draw_0.gml') and self.writes(source,'choicer.choicetotal')!=['choicer.choicetotal=real(nextchar2)-1']:
                return self.fail('choice_control_count_write')
            if any(c['call'] in ('variable_global_set','script_execute') for c in self.a.calls(source)):
                return self.fail('choice_control_dynamic_write')
        text=self.function('scr_text')
        if not text:return self.fail('missing_scr_text')
        body=self.a.flat(text[1].children)
        switches=[n for n in body if n.kind=='switch']
        parameter=re.fullmatch(r'scr_text\(\s*(\w+)\s*\)',text[1].text)
        if len(body)!=1 or len(switches)!=1 or not parameter or switches[0].text!=parameter[1]:
            return self.fail('shared_return_structure')
        cases=switches[0].children
        if any(n.text!='default' and not re.fullmatch(r'-?\d+',n.text) for n in cases):
            return self.fail('dynamic_shared_case')
        if any(n.text!='default' and int(n.text)==-98 for n in cases):return self.fail('shared_return_has_case')
        defaults=[n for n in cases if n.text=='default']
        if len(defaults)!=1 or [self.compact(n.text) for n in self.a.flat(defaults[0].children)]!=['break;']:
            return self.fail('shared_return_default')
        self._ready=True;self.reason='';return True

    def direct_call(self,statement):
        expression=statement.text.strip().rstrip(';').strip()
        calls=list(self.a.calls(expression))
        return calls[0] if calls and calls[0]['offset']==0 and calls[0]['end']==len(expression) else None

    def menu_setup(self, statement):
        """A queued literal menu initializer, preserving original source offsets."""
        call = self.direct_call(statement)
        if not call or call['call'] != 'c_customfunc' or len(call['args']) != 1:
            return None
        text = statement.text
        match = re.fullmatch(r'c_customfunc\s*\(\s*function\s*\(\s*\)\s*\{([\s\S]*)\}\s*\)\s*;', text)
        if not match:
            return None
        shift = statement.start + match.start(1)
        def shifted(n):
            return replace(n, start=n.start+shift, end=n.end+shift,
                           children=[shifted(c) for c in n.children], other=[shifted(c) for c in n.other])
        nodes = [shifted(n) for n in self.a.flow.parse(match[1])]
        if (len(nodes) < 3 or self.compact(nodes[0].text) != 'global.msc=-99;'
                or self.compact(nodes[1].text) != 'global.choice=-1;'
                or any(n.kind != 'stmt' or not re.match(r'global\.choicemsg(?:\[|\s*=)', n.text) for n in nodes[2:])
                or not self.labels(nodes[2:])):
            return None
        return nodes

    def choice_layout(self):
        """The display-only chooser offset helper, including its deferred updater."""
        fields = [f'opt{i}{axis}off' for i in range(4) for axis in ('x','y')] + ['heartxoff','heartyoff']
        params = ','.join(f'arg{i}=0' for i in range(10))
        init = ''.join(f'__{f}=arg{i};' for i,f in enumerate(fields))
        apply = ''.join(f'{f}=other.__{f}'+('/2;' if i < 8 else ';') for i,f in enumerate(fields))
        expected = ('function scr_choiceradjust('+params+'){var choiceradjuster=instance_create_depth(0,0,0,obj_object);'
                    'with(choiceradjuster){'+init+'scr_debug_print("CREATED");begin_step_func=function(){var done=false;'
                    'with(obj_choicer_neo){'+apply+'done=true;}if(done){scr_debug_print("donezo");instance_destroy();}};}'
                    'return choiceradjuster;}')
        return self.exact_function('scr_choiceradjust', expected)

    def maker(self,statement):
        call=self.direct_call(statement)
        if not call or call['call']!='c_customfunc' or not 1<=len(call['args'])<=2:
            return self.fail('not_queued_dialogue_maker')
        callback=call['args'][0].strip()
        if len(call['args'])==2 and not re.fullmatch(NUMBER,call['args'][1].strip()):
            return self.fail('dynamic_dialogue_side')
        if re.fullmatch(r'\w+',callback):
            create=re.sub(r'_Step_\d+\.gml$','_Create_0.gml',self.name)
            source=self.source(create)
            if source is None:return self.fail('missing_maker_definition')
            definitions=[n for n in self.a.file(create)['nodes'] if n.kind=='stmt'
                         and re.match(re.escape(callback)+r'\s*=\s*function\s*\(',n.text)]
            if len(definitions)!=1:return self.fail('non_unique_maker')
            callback=definitions[0].text.split('=',1)[1].strip().rstrip(';')
            # Do not trust a constructor method which is reassigned in this event.
            own=self.source(self.name) or ''
            if re.search(r'\b'+re.escape(call['args'][0])+r'\s*=(?!=)',own):
                return self.fail('reassigned_maker')
        match=re.fullmatch(r'function\s*\(\s*(?:(\w+)\s*=\s*'+NUMBER+r')?\s*\)\s*\{([\s\S]*)\}',callback)
        if not match:return self.fail('opaque_dialogue_maker')
        body=self.compact(match[2]);parameter=match[1]
        if body=='d_make();':return self.dialogue_factory()
        layout = re.fullmatch(r'if\(global\.lang=="[a-z]+"\)scr_choiceradjust\(([^()]*)\);d_make\(\);', body)
        if layout and all(re.fullmatch(NUMBER, a) for a in layout[1].split(',')):
            return self.choice_layout() and self.dialogue_factory()
        if not parameter:
            constant=re.fullmatch(r'var(\w+)=d_make\(\);((?:\1\.(?:side|stay)=-?\d+;)+)',body)
            if constant:
                fields=re.findall(r'\.(side|stay)=',constant[2])
                return len(fields)==len(set(fields)) and self.dialogue_factory()
        if parameter:
            pattern=r'var(\w+)=d_make\(\);\1\.side='+re.escape(parameter)+r';'
            if re.fullmatch(pattern,body):return self.dialogue_factory()
        return self.fail('opaque_dialogue_maker')

    def prompt(self,statement):
        """Verify an actual queued message statement; a string alone is not a menu."""
        call=self.direct_call(statement)
        if not call or not re.fullmatch(r'c_msg(?:set|next)(?:sub)?(?:loc)?',call['call']):
            return self.fail('not_queued_message_prompt')
        if any(not self.pure(arg) for arg in call['args']):return self.fail('opaque_prompt_argument')
        if not self.summary(call['call'],call['args']):return self.fail('unproved_prompt_wrapper')
        return True

    def dialogue_factory(self):
        fn=self.function('d_make')
        if not fn:return self.fail('missing_dialogue_factory')
        body=self.compact(fn[2][fn[1].start:fn[1].end])
        expected='function d_make(arg0=-1,arg1=-1,arg2=-1,arg3=-1,arg4=-1){var _____d=instance_create(0,0,obj_dialoguer);if(arg0!=-1)_____d.side=arg0;if(arg1!=-1)_____d.zurasu=arg1;if(arg2!=-1)_____d.stay=arg2;if(arg3!=-1)_____d.runcheck=arg3;if(arg4!=-1)_____d.preventcskip=arg3;return _____d;}'
        return body==self.compact(expected) or self.fail('dialogue_factory_protocol')

    def labels(self, nodes):
        """Do not skip a label getter's effects when removing protocol writes."""
        for n in nodes:
            if n.kind != 'stmt' or not re.match(r'global\.choicemsg(?:\[|\s*=)', n.text):continue
            for c in self.a.calls(n.text):
                if c['call']=='stringset':
                    if not self.exact_function('stringset','function stringset(arg0){return arg0;}'):return False
                elif c['call']=='stringsetloc':
                    source='function stringsetloc(arg0,arg1){var str=arg0;if(!is_english())str=scr_84_get_lang_string(arg1);return stringset(str);}'
                    fn=self.function('c_msgsetloc')
                    if not (self.exact_function('stringsetloc',source)
                            and self.exact_function('stringset','function stringset(arg0){return arg0;}')
                            and fn and self.localized('c_msgsetloc',fn)):return False
                else:return False
        return True

    def pure(self,expression):
        tokens=self.tokens(expression)
        if any(t in ('function','=','+=','-=','*=','/=','++','--') for t in tokens):return False
        for call in self.a.calls(expression):
            if call['call'] in PURE:continue
            if call['call']=='d_ex' and not any(a.strip() for a in call['args']) and self.exact_function('d_ex','function d_ex(){return instance_exists(obj_dialoguer);}'):continue
            if call['call']=='scr_flag_get' and self.exact_function('scr_flag_get','function scr_flag_get(arg0){return global.flag[arg0];}'):continue
            return False
        return True

    def queue_call(self,args):
        if not args:return False
        command=self.a.gml.as_string_literal(args[0])
        if not self.command_body(command):return False
        if command in COMMANDS:return True
        if command=='delaycmd':
            return len(args)>2 and self.queue_call(args[2:])
        if command in ('var','varto','varadd'):
            # var: object (0 means current actor), field, value.
            return (len(args)>2 and self.a.gml.as_string_literal(args[2]) in VISUAL_FIELDS
                    and self.command_body('var'))
        if command=='msgcmd':
            if len(args)<2:return False
            nested=self.a.gml.as_string_literal(args[1])
            if nested in ('msgcmd','delaycmd','terminatekillactors'):return False
            # The dispatcher copies four parameters and initializes slots 5/6
            # to zero. Apply the ordinary command checks to the actual payload.
            payload=list(args[2:6])
            payload += ['0']*(4-len(payload))
            return self.queue_call([args[1],*payload,'0','0'])
        # Termination only belongs after the last projected text. The parent
        # connector checks position before requesting a tail summary.
        if command=='terminatekillactors':
            self.effects.add('queue_termination');return True
        return False

    def command_body(self,command):
        """Reject newly introduced direct/reflective answer writes in a handler.

        Animation/object-event effects remain outside this local summary; the
        caller must not use it to claim whole-game runtime reachability.
        """
        if command in self._commands:return self._commands[command]
        self._commands[command]=False
        engine=self.function('scr_cutscene_commands')
        if not engine or not isinstance(command,str):return False
        def handles(n):
            if n.kind!='if':return False
            parts=self.compact(n.text).split('||')
            return (all(re.fullmatch(r'_c=="\w+"',p) for p in parts)
                    and '_c=="'+command+'"' in parts)
        matches=[n for n in self.a.flat(engine[1].children) if handles(n)]
        if len(matches)!=1 or matches[0].other:return False
        source=engine[2][matches[0].start:matches[0].end]
        if command=='msgcmd':
            expected=('if(!v_ex("msgcmd")||!i_ex(msgcmd))msgcmd=instance_create(0,0,obj_cutscene_messagecmd);'
                'var _count=msgcmd.count;msgcmd.master_object=master_object;'
                'msgcmd.command_actor[_count]=command_actor[i];msgcmd.command_num[_count]=global.msgno;'
                'msgcmd.command[_count]=command_arg1[i];'+
                ''.join(f'msgcmd.command_arg{j}[_count]=command_arg{j+1}[i];' for j in range(1,5))+'msgcmd.count++;')
            actual=''.join(engine[2][n.start:n.end] for n in self.a.flat(matches[0].children))
            if self.compact(actual)!=self.compact(expected) or not self.message_dispatch():return False
        if command=='delaycmd':
            expected='delaycmd=instance_create(0,0,obj_cutscene_delaycmd);delaycmd.master_object=master_object;delaycmd.command_actor[0]=command_actor[i];delaycmd.alarm[0]=command_arg1[i];delaycmd._c=command_arg2[i];'+''.join(f'delaycmd.command_arg{j}[0]=command_arg{j+2}[i];' for j in range(1,5))+'if(instant){delaycmd.alarm[0]=0;delaycmd.instant=1;with(delaycmd)event_user(0);}'
            actual=''.join(engine[2][n.start:n.end] for n in self.a.flat(matches[0].children))
            event=self.source('gml_Object_obj_cutscene_delaycmd_Other_10.gml')
            if (self.compact(actual)!=self.compact(expected) or not event
                    or self.compact(event)!='i=0;if(i_ex(command_actor[0])||_c=="customfunc")scr_cutscene_commands();instance_destroy();'):
                return False
        if command in ('waitbox','halt'):
            bodies={
                'waitbox':'if(!instant){waiting=1;cs_wait_box=command_arg1[i];breakme=1;}',
                'halt':'with(command_actor[i])scr_halt();',
            }
            actual=''.join(engine[2][n.start:n.end] for n in self.a.flat(matches[0].children))
            if self.compact(actual)!=self.compact(bodies[command]):return False
            if command=='halt' and not self.exact_function('scr_halt','function scr_halt(){image_index=0;image_speed=0;speed=0;}'):return False
        if self.writes(source,'global.choice') or self.writes(source,'global.msc'):return False
        if re.search(r'global\.choicemsg(?:\[[^]]*\])?(?:=(?!=)|\+=|-=|\+\+|--)',self.compact(source)):return False
        if any(c['call'] in ('variable_global_set','script_execute') for c in self.a.calls(source)):return False
        self._commands[command]=True;return True

    def message_dispatch(self):
        """Verify deferred commands retain their parameters and dispatch route."""
        expected={
            'Create_0':('instant=0;command_num[0]=0;command[0]=0;'+
                ''.join(f'command_arg{i}[0]=0;' for i in range(1,7))+
                'i=0;count=0;_c="none";command_actor[0]=43894389;master_object=4839438;alarm[0]=1;msg_active=false;'
                'if(i_ex(obj_cutscene_master))depth=obj_cutscene_master.depth-5;'),
            'Step_0':('var _msgno=-1;'
                'with(obj_cutscene_master){if(i_ex(mydialoguer)){if(mydialoguer.active==1&&i_ex(mydialoguer.writer))'
                '_msgno=mydialoguer.writer.msgno;}}if(_msgno<0)exit;while(_msgno==command_num[i]){'
                '_c=command[i];scr_cutscene_commands();i++;if(i>=array_length(command)){instance_destroy();break;}}'),
        }
        names={f'gml_Object_obj_cutscene_messagecmd_{event}.gml':body for event,body in expected.items()}
        if {name for name in self.a.sources if name.startswith('gml_Object_obj_cutscene_messagecmd_')}!=set(names):return False
        return all((source:=self.source(name)) is not None and self.compact(source)==self.compact(body)
                   for name,body in names.items())

    def staging_callback(self, statement):
        """Inspect a literal callback's local work, never execute it.

        Object creation is retained as review evidence: events of the created
        object are outside this local menu projection. Named/delayed callbacks,
        state/answer writes and new dialogue cannot pass this path.
        """
        if statement.kind!='stmt':return False
        match=re.fullmatch(r'c_customfunc\s*\(\s*function\s*\(\s*\)\s*\{([\s\S]*)\}\s*\)\s*;',statement.text)
        if not match or not self.ready():return False
        def walk(nodes):
            for node in self.a.flat(nodes):
                if node.kind in ('if','with'):
                    if not self.pure(node.text):return False
                    if not walk(node.children) or not walk(node.other):return False
                    continue
                if node.kind!='stmt':return False
                assignment=re.fullmatch(r'(?:var\s+)?(\w+(?:\.\w+)?)\s*=(?!=)\s*([\s\S]+);',node.text)
                if assignment:
                    names=assignment[1].split('.')
                    if names[0] in ('global','self','other') or names[-1] in ('choice','choicemsg','msc','con','customcon'):return False
                    if not self.pure(assignment[2]):return False
                    continue
                call=self.direct_call(node)
                if not call or any(not self.pure(arg) for arg in call['args']):return False
                name,args=call['call'],call['args']
                if name in ('instance_create','instance_create_depth'):
                    count=3 if name=='instance_create' else 4
                    if len(args)!=count or not re.fullmatch(r'obj_\w+',args[-1].strip()):return False
                    if re.search(r'writer|dialoguer|choicer|cutscene',args[-1]):return False
                elif name in ('snd_play','soundplay','sound_play'):
                    template=('function '+name+'(arg0,arg1=1,arg2=1){var _snd=audio_play_sound(arg0,50,0);'
                        'if(arg1!=1)audio_sound_gain(_snd,arg1,0);if(arg2!=1)audio_sound_pitch(_snd,arg2);return _snd;}')
                    if not 1<=len(args)<=3 or not self.exact_function(name,template):return False
                elif name=='k_d':
                    if not self.cleanup():return False
                elif name=='scr_flag_set':
                    if len(args)!=2 or not self.summary(name,args):return False
                else:return False
            return True
        return walk(self.a.flow.parse(match[1]))

    def summary(self,name,args):
        """Prove a helper only queues approved commands or writes local temps."""
        if len(args)==1 and not args[0].strip():args=[]
        if name in self._checking:return False
        if name in ('c_cmd','c_cmd_x'):return self.queue_call(args)
        if name=='c_waitcustom_end':return self.ready()
        if name=='c_waitcustom':
            self.effects.add('queue_pause')
            return self.ready()
        if name=='scr_flag_set':
            return self.exact_function(name,'function scr_flag_set(arg0,arg1){global.flag[arg0]=arg1;}')
        if name=='show_debug_message_concat':
            return self.exact_function(name,'function show_debug_message_concat(){}')
        if name=='k_d':return self.cleanup()
        if name=='scr_choiceradjust':
            return len(args)<=10 and all(re.fullmatch(NUMBER,a.strip()) for a in args) and self.choice_layout()
        fn=self.function(name)
        if not fn or not name.startswith('c_'):return False
        if name in ('c_customfunc','c_delay_customfunc','c_waitcustom'):return False
        if 'loc' in name:return self.localized(name,fn)
        signature=fn[1].text[fn[1].text.find('(')+1:-1]
        params,_,ok=self.a.gml.split_args('('+signature+')',0)
        if not signature.strip():params=[]
        if not ok:return False
        env={}
        for i,param in enumerate(params):
            parts=param.strip().split('=',1)
            if not re.fullmatch(r'\w+',parts[0].strip()):return False
            value=args[i] if i<len(args) else parts[1].strip() if len(parts)>1 else None
            if value is None:return False
            env[parts[0].strip()]=value
        source=fn[2];locals_=set(re.findall(r'\bvar\s+(\w+)',source[fn[1].start:fn[1].end]))
        body=source[fn[1].start:fn[1].end]
        if len(args)>len(params) and (params or not re.search(r'\bargument(?:_count|\d+|\s*\[)',body)):
            return False
        def expand(text):
            # Quoted literals are data; argument_count selects only the branch
            # used by this call. Do not inspect missing args in dead branches.
            pattern=r'"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27|\bargument_count\b|\bargument\s*\[\s*(\d+)\s*\]|\bargument(\d+)\b|\b\w+\b'
            def substitute(m):
                if m[0].startswith(('"',"'")):return m[0]
                if m[0]=='argument_count':return str(len(args))
                if m[1] is not None or m[2] is not None:
                    index=int(m[1] if m[1] is not None else m[2])
                    if index>=len(args):raise ValueError('Missing variadic argument')
                    return args[index]
                return env.get(m[0],m[0])
            return re.sub(pattern,substitute,text)
        def walk(nodes):
            for node in self.a.flat(nodes):
                if node.kind in ('if','with'):
                    count=re.fullmatch(r'argument_count\s*(==|!=|<=|>=|<|>)\s*(\d+)',node.text) if node.kind=='if' else None
                    if count:
                        left,right=len(args),int(count[2])
                        take={'==':left==right,'!=':left!=right,'<=':left<=right,'>=':left>=right,'<':left<right,'>':left>right}[count[1]]
                        if not walk(node.children if take else node.other):return False
                        continue
                    if not self.pure(expand(node.text)):return False
                    if not walk(node.children) or not walk(node.other):return False
                    continue
                if node.kind!='stmt':return False
                text=node.text.strip()
                assignment=re.fullmatch(r'(?:var\s+)?(\w+)\s*=\s*([\s\S]+);',text)
                if assignment:
                    if assignment[1] not in locals_ or not self.pure(expand(assignment[2])):return False
                    continue
                call=self.direct_call(node)
                if not call:return False
                expanded=[expand(arg) for arg in call['args']]
                if any(not self.pure(arg) for arg in expanded):return False
                if not self.summary(call['call'],expanded):return False
            return True
        self._checking.add(name)
        try:return walk(fn[1].children)
        except ValueError:return False
        finally:self._checking.remove(name)

    def localized(self,name,fn):
        # These templates select a string and delegate to an already verified
        # queue wrapper; they do not interpret localized text as code.
        templates={
            'msgsetloc':('function msgsetloc(arg0,arg1,arg2){var msg_index=arg0;var str=arg1;var localized_string_id=arg2;if(!is_english())str=scr_84_get_lang_string(localized_string_id);msgset(msg_index,str);}','msgset',['0','"text"']),
            'msgnextloc':('function msgnextloc(arg0,arg1){var str=arg0;var localized_string_id=arg1;if(!is_english())str=scr_84_get_lang_string(localized_string_id);msgnext(str);}','msgnext',['"text"']),
            'c_msgsetloc':('function c_msgsetloc(arg0,arg1,arg2){var msg_index=arg0;var english=arg1;var localized_string_id=arg2;var str=english;if(!is_english())str=scr_84_get_lang_string(localized_string_id);c_msgset(msg_index,str);}','c_msgset', ['0','"text"']),
            'c_msgnextloc':('function c_msgnextloc(arg0,arg1){var str=arg0;var localized_string_id=arg1;if(!is_english())str=scr_84_get_lang_string(localized_string_id);c_msgnext(str);}','c_msgnext',['"text"']),
            'c_msgsetsubloc':('function c_msgsetsubloc(){var len=argument_count;var args;for(var i=0;i<len;i++)args[i]=argument[i];var msg_index=argument[0];var format_string=argument[1];var localized_format_string_id=argument[len-1];if(!is_english())format_string=scr_84_get_lang_string(localized_format_string_id);var str=substringargs(format_string,2,args);c_msgset(msg_index,str);}','c_msgset',['0','"text"']),
            'c_msgnextsubloc':('function c_msgnextsubloc(){var len=argument_count;var args;for(var i=0;i<len;i++)args[i]=argument[i];var format_string=argument[0];var localized_string_id=argument[len-1];if(!is_english())format_string=scr_84_get_lang_string(localized_string_id);var str=substringargs(format_string,1,args);c_msgnext(str);}','c_msgnext',['"text"']),
        }
        item=templates.get(name)
        if not item:return False
        language='function is_english(){return !variable_global_exists("lang")||global.lang=="en";}'
        lookup='function scr_84_get_lang_string(arg0){var lang_string_id=arg0;var str=ds_map_find_value(global.lang_map,lang_string_id);if(is_undefined(str)){if(!ds_map_find_value(global.lang_missing_map,lang_string_id)){ds_map_add(global.lang_missing_map,lang_string_id,true);show_debug_message("ERROR: string id "+lang_string_id+" for language "+global.lang+" is missing");}str="--missing-string--";}return str;}'
        if 'sub' in name:
            substring='function substringargs(arg0,arg1,arg2){var str=arg0;var offset=arg1;var args=arg2;var sub_id=1;var num_args=array_length_1d(args);var len=(num_args-offset)+1;while(sub_id<len){var sub="~"+string(sub_id);var ndx=(sub_id+offset)-1;str=string_replace_all(str,sub,args[ndx]);sub_id=sub_id+1;}return str;}'
            if not self.exact_function('substringargs',substring):return False
        return (self.compact(fn[2][fn[1].start:fn[1].end])==self.compact(item[0])
            and self.exact_function('is_english',language)
            and (self.exact_function('scr_84_get_lang_string',lookup)
                 or self.exact_function('scr_84_get_lang_string',lookup.replace('+lang_string_id+', '+string(lang_string_id)+')))
            and self.summary(item[1],item[2]))

    def cleanup(self):
        fn=self.function('k_d')
        if not fn:return False
        # Bound the cleanup effects to existing dialoguer/writer/chooser objects
        # and the optional visual stay writer. Unknown calls fail closed.
        source=fn[2][fn[1].start:fn[1].end]
        expected='function k_d(arg0=0){with(obj_dialoguer){if(arg0>0){var _stayer=instance_create_depth(x,y,depth+1,obj_writer_stay);_stayer.side=side;_stayer.xoff=xoff;_stayer.yoff=yoff;_stayer.boxwidth=boxwidth;_stayer.boxheight=boxheight;_stayer.cur_jewel=cur_jewel;_stayer.doom=arg0;_stayer.c_border=c_border;_stayer.c_inner=c_inner;}instance_destroy();}with(obj_writer)instance_destroy();with(obj_choicer_neo)instance_destroy();}'
        if self.compact(source)==self.compact(expected):return True
        older=expected.replace('_stayer.doom=arg0;_stayer.c_border=c_border;_stayer.c_inner=c_inner;', 'scr_doom(_stayer,arg0);').replace('with(obj_choicer_neo)instance_destroy();','')
        doom='function scr_doom(arg0=id,arg1){with(instance_create_depth(0,0,0,obj_doom)){alarm[0]=arg1;target=arg0;persistent=arg0.persistent;}}'
        if self.compact(source)!=self.compact(older) or not self.exact_function('scr_doom',doom):return False
        events={name for name in self.a.sources if name.startswith('gml_Object_obj_doom_')}
        alarm=self.source('gml_Object_obj_doom_Alarm_0.gml')
        return (events=={'gml_Object_obj_doom_Alarm_0.gml'} and alarm is not None
                and self.compact(alarm)==self.compact('with(target)instance_destroy();instance_destroy();'))

    def safe(self,nodes,allow_state=False,_last_text=None):
        self.reason=''
        if _last_text is None:
            _last_text=max((r['offset'] for n in self.a.flat(nodes)
                for r in self.a.within(self.name,n)),default=-1)
        for node in self.a.flat(nodes):
            if node.kind=='if':
                if not self.pure(node.text):return self.fail('opaque_condition')
                if not self.safe(node.children,allow_state,_last_text) or not self.safe(node.other,allow_state,_last_text):return False
                continue
            if node.kind!='stmt':return self.fail('unsupported_response_control')
            text=node.text.strip();tokens=self.tokens(text);clean=''.join(tokens)
            if clean in ('global.interact=0;','global.interact=1;'):continue
            if re.fullmatch(r'global\.facing=[0-3];',clean):continue
            if any(t in ('return','exit','break','continue','function') for t in tokens):return self.fail('response_control_transfer')
            if re.search(r'global\.(?:choice(?:msg)?|msc)(?:\[|=(?!=)|\+=|-=|\+\+|--)',clean):return self.fail('answer_or_menu_write')
            assignment=re.fullmatch(r'(?:var\s+)?(\w+)\s*=\s*([\s\S]+);',text)
            if assignment:
                variable,value=assignment[1],assignment[2].strip()
                if variable=='con':
                    if not allow_state or not re.fullmatch(NUMBER,value):return self.fail('dynamic_response_state')
                elif variable=='customcon':
                    if value!='0':return self.fail('wait_state_write')
                elif not text.startswith('var ') or not self.pure(value):return self.fail('unproved_assignment')
                continue
            call=self.direct_call(node)
            if not call:return self.fail('unsupported_response_statement')
            if any(not self.pure(arg) for arg in call['args']):return self.fail('opaque_call_argument')
            if any(re.search(r'\\C[1-4]',self.a.gml.as_string_literal(arg) or '') for arg in call['args']):
                return self.fail('new_choice_prompt')
            self.effects=set()
            if not self.summary(call['call'],call['args']):return self.fail('unproved_call:'+call['call'])
            if 'queue_termination' in self.effects and node.start<_last_text:
                return self.fail('queue_termination_before_text')
            if 'queue_pause' in self.effects and node.start<_last_text:
                return self.fail('queue_pause_before_text')
        return True
