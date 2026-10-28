"""Safety checks for the bounded queued-choice protocol, without game inputs."""
import unittest

from tools.context.context_conditions import backend
from tools.context.context_files import Analyzer
from tools.context.queued_protocol import QueuedProtocol


FILE='gml_Object_obj_fixture_Step_0.gml'
CREATE='gml_Object_obj_fixture_Create_0.gml'
KEY='fixture_slash_Test_gml_1_0'
MESSAGE='c_msgsetloc(0,"response","'+KEY+'");'


def helpers():
    result={}
    def add(name,source):result['gml_GlobalScript_'+name+'.gml']=source
    for name,count in [('c_cmd',4),('c_cmd_x',6)]:
        args=','.join('arg'+str(i) for i in range(count+1))
        writes=''.join(f'obj_cutscene_master.command_arg{i}[__cs_i]=arg{i};' for i in range(1,count+1))
        add(name,f'function {name}({args}){{if(instance_exists(obj_cutscene_master)){{'
            '__cs_i=obj_cutscene_master.maximum_command-1;obj_cutscene_master.command[__cs_i]=arg0;'
            +writes+'with(obj_cutscene_master)maximum_command++;}}')
    add('c_customfunc','function c_customfunc(arg0,arg1=-1){if(instance_exists(obj_cutscene_master)){with(obj_cutscene_master)array_push(customfuncs,arg0);c_cmd("customfunc",arg1,0,0,0);}}')
    add('c_waitcustom','function c_waitcustom(){c_cmd("waitcustom",0,0,0,0);}')
    add('c_waitcustom_end','function c_waitcustom_end(){with(obj_cutscene_master){cs_wait_custom=0;waiting=0;}}')
    add('c_msgset','function c_msgset(arg0,arg1){c_cmd("msgset",arg0,arg1,0,0);}')
    add('c_msgnext','function c_msgnext(arg0){c_cmd("msgnext",arg0,0,0,0);}')
    add('scr_cutscene_make','function scr_cutscene_make(){_cutscene_master=instance_create(0,0,obj_cutscene_master);_cutscene_master.master_object=id;return _cutscene_master;}')
    add('scr_cutscene_commands','''function scr_cutscene_commands(){
      if(_c=="waitcustom"){with(master_object)customcon=1;cs_wait_custom=1;waiting=1;breakme=1;}
      if(_c=="customfunc"){
        if(object_index==obj_cutscene_delaycmd||object_index==obj_cutscene_messagecmd){
          if(command_arg1[i]!=-1)command_arg2[i](command_arg1[i]);else command_arg2[i]();
        }else if(array_length(customfuncs)>0){
          if(command_arg1[i]!=-1)customfuncs[0](command_arg1[i]);else customfuncs[0]();
          array_delete(customfuncs,0,1);
        }
      }
      if(_c=="msgset")msgset(command_arg1[i],command_arg2[i]);
      if(_c=="msgnext")msgnext(command_arg1[i]);
      if(_c=="addxy"){}
      if(_c=="var"){}
      if(_c=="terminatekillactors"){}
    }''')
    add('scr_text','function scr_text(arg0){switch(arg0){case 42: break; default: break;}}')
    add('d_make','function d_make(arg0=-1,arg1=-1,arg2=-1,arg3=-1,arg4=-1){var _____d=instance_create(0,0,obj_dialoguer);if(arg0!=-1)_____d.side=arg0;if(arg1!=-1)_____d.zurasu=arg1;if(arg2!=-1)_____d.stay=arg2;if(arg3!=-1)_____d.runcheck=arg3;if(arg4!=-1)_____d.preventcskip=arg3;return _____d;}')
    add('c_msgsetloc','function c_msgsetloc(arg0,arg1,arg2){var msg_index=arg0;var english=arg1;var localized_string_id=arg2;var str=english;if(!is_english())str=scr_84_get_lang_string(localized_string_id);c_msgset(msg_index,str);}')
    add('is_english','function is_english(){return !variable_global_exists("lang")||global.lang=="en";}')
    add('stringset','function stringset(arg0){return arg0;}')
    add('stringsetloc','function stringsetloc(arg0,arg1){var str=arg0;if(!is_english())str=scr_84_get_lang_string(arg1);return stringset(str);}')
    add('scr_84_get_lang_string','function scr_84_get_lang_string(arg0){var lang_string_id=arg0;var str=ds_map_find_value(global.lang_map,lang_string_id);if(is_undefined(str)){if(!ds_map_find_value(global.lang_missing_map,lang_string_id)){ds_map_add(global.lang_missing_map,lang_string_id,true);show_debug_message("ERROR: string id "+lang_string_id+" for language "+global.lang+" is missing");}str="--missing-string--";}return str;}')
    result.update({
        'gml_Object_obj_choicer_neo_Other_10.gml':'if(canchoose==1&&choiced==0){choiced=1;global.choice=mychoice;alarm[0]=1;}',
        'gml_Object_obj_choicer_neo_Alarm_0.gml':'global.msc+=1;scr_text(global.msc);',
        'gml_Object_obj_choicer_neo_Create_0.gml':'global.choice=-1;',
        'gml_Object_obj_choicer_neo_Step_0.gml':'if(left_h())mychoice=0;if(choicetotal>=1&&right_h())mychoice=1;if(choicetotal>=2&&up_h())mychoice=2;if(choicetotal>=3&&down_h())mychoice=3;',
        'gml_Object_obj_choicer_neo_Draw_0.gml':'string_hash_to_newline(global.choicemsg[i]);',
        'gml_Object_obj_writer_Draw_0.gml':'if(nextchar=="C"){if(nextchar2=="2"||nextchar2=="3"||nextchar2=="4"){choicer=instance_create(0,0,obj_choicer_neo);choicer.choicetotal=real(nextchar2)-1;}}',
    })
    return result


class QueuedProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api=backend()

    def protocol(self,source='',overrides=None,chapter=5):
        sources={**helpers(),FILE:source,**(overrides or {})}
        analyzer=Analyzer(sources,chapter,{KEY:{'en':'response'}},self.api)
        return QueuedProtocol(analyzer,FILE)

    def test_source_checked_protocol_and_chapter_variant(self):
        self.assertTrue(self.protocol().ready())
        sources=helpers();engine='gml_GlobalScript_scr_cutscene_commands.gml'
        sources[engine]=sources[engine].replace('||object_index==obj_cutscene_messagecmd','')
        self.assertTrue(self.protocol(overrides=sources,chapter=4).ready())
        del sources['gml_GlobalScript_c_customfunc.gml']
        analyzer=Analyzer(sources,3,{},self.api)
        q=QueuedProtocol(analyzer,FILE)
        self.assertFalse(q.ready())

    def test_protocol_mutations_fail_closed(self):
        examples=[
            ('gml_GlobalScript_c_cmd.gml','maximum_command++;','maximum_command++;global.choice=1;'),
            ('gml_GlobalScript_scr_cutscene_make.gml','master_object=id','master_object=other.id'),
            ('gml_GlobalScript_scr_cutscene_commands.gml','customcon=1','customcon=2'),
            ('gml_Object_obj_choicer_neo_Other_10.gml','global.choice=mychoice','global.choice=0'),
            ('gml_Object_obj_writer_Draw_0.gml','choicetotal=real(nextchar2)-1','choicetotal=real(nextchar2)'),
            ('gml_GlobalScript_scr_text.gml','default: break;','default: global.choice=0;break;'),
            ('gml_GlobalScript_scr_text.gml','case 42:','case -98:'),
            ('gml_GlobalScript_scr_text.gml','switch(arg0)','global.choice=0;switch(arg0)'),
        ]
        for filename,before,after in examples:
            with self.subTest(filename=filename,before=before):
                altered=helpers()[filename].replace(before,after)
                self.assertFalse(self.protocol(overrides={filename:altered}).ready())
        for filename in ('gml_Object_obj_writer_Draw_0.gml','gml_Object_obj_choicer_neo_Create_0.gml',
                         'gml_Object_obj_choicer_neo_Alarm_0.gml'):
            with self.subTest(extra_write=filename):
                self.assertFalse(self.protocol(overrides={filename:helpers()[filename]+'++global.choice;'}).ready())

    def test_named_and_anonymous_makers_not_name_recipes(self):
        definition='open_menu_here=function(arg0=1){var d=d_make();d.side=arg0;};'
        for source in ('c_customfunc(open_menu_here,0);','c_customfunc(function(){d_make();});'):
            q=self.protocol(source,{CREATE:definition})
            self.assertTrue(q.maker(q.a.file(FILE)['nodes'][0]),q.reason)
        for body in ('d_make();global.choice=0;','d_make();unknown();'):
            source='c_customfunc(function(){'+body+'});'
            q=self.protocol(source)
            self.assertFalse(q.maker(q.a.file(FILE)['nodes'][0]))
        q=self.protocol('c_customfunc(open_menu_here,side);',{CREATE:definition})
        self.assertFalse(q.maker(q.a.file(FILE)['nodes'][0]))

    def test_constant_dialoguer_properties_and_readonly_existence(self):
        source='c_customfunc(function(){var box=d_make();box.stay=5;box.side=1;});'
        q=self.protocol(source)
        self.assertTrue(q.maker(q.a.file(FILE)['nodes'][0]))
        for mutation in ('box.side=opaque();','box.side=1;box.side=2;','box.choice=1;'):
            p=self.protocol(source.replace('box.side=1;',mutation))
            self.assertFalse(p.maker(p.a.file(FILE)['nodes'][0]))
        extra={'gml_GlobalScript_d_ex.gml':'function d_ex(){return instance_exists(obj_dialoguer);}'}
        self.assertTrue(self.protocol(overrides=extra).pure('!d_ex()'))
        extra['gml_GlobalScript_d_ex.gml']='function d_ex(){global.choice=0;return instance_exists(obj_dialoguer);}'
        self.assertFalse(self.protocol(overrides=extra).pure('!d_ex()'))

    def test_waitbox_halt_handlers_and_transitive_helper_are_verified(self):
        engine=helpers()['gml_GlobalScript_scr_cutscene_commands.gml'][:-1]+'''
            if(_c=="waitbox"){if(!instant){waiting=1;cs_wait_box=command_arg1[i];breakme=1;}}
            if(_c=="halt"){with(command_actor[i])scr_halt();}}'''
        extra={'gml_GlobalScript_scr_cutscene_commands.gml':engine,
               'gml_GlobalScript_scr_halt.gml':'function scr_halt(){image_index=0;image_speed=0;speed=0;}',
               'gml_GlobalScript_c_halt.gml':'function c_halt(){c_cmd("halt",0,0,0,0);}',
               'gml_GlobalScript_c_wait_box.gml':'function c_wait_box(arg0){c_cmd("waitbox",arg0,0,0,0);}'}
        q=self.protocol('global.interact=1;c_wait_box(2);c_halt();',extra)
        self.assertTrue(q.safe(q.a.file(FILE)['nodes']),q.reason)
        for name,before,after in [('scr_halt','speed=0;','speed=0;global.choice=1;'),
                                  ('scr_cutscene_commands','breakme=1;}','breakme=1;opaque();}')]:
            changed=dict(extra);key='gml_GlobalScript_'+name+'.gml'
            changed[key]=changed[key].replace(before,after)
            q=self.protocol('c_wait_box(2);c_halt();',changed)
            self.assertFalse(q.safe(q.a.file(FILE)['nodes']))

    def test_actual_queued_prompt_requires_wrapper_and_pure_arguments(self):
        source='c_msgset(0,"\\\\C2");'
        q=self.protocol(source);node=q.a.file(FILE)['nodes'][0]
        self.assertTrue(q.prompt(node))
        self.assertFalse(q.safe([node]))
        altered='function c_msgset(arg0,arg1){global.choice=1;c_cmd("msgset",arg0,arg1,0,0);}'
        q=self.protocol(source,{'gml_GlobalScript_c_msgset.gml':altered})
        self.assertFalse(q.prompt(q.a.file(FILE)['nodes'][0]))
        q=self.protocol('c_msgset(opaque(),"\\\\C2");')
        self.assertFalse(q.prompt(q.a.file(FILE)['nodes'][0]))

    def test_decimal_state_and_repeated_read_only_answer_test(self):
        source='if(global.choice==0){c_move(3);}if(global.choice==1){c_move(4);}if(global.choice==0){c_move(5);}con=7.25;customcon=0;'
        extra={'gml_GlobalScript_c_move.gml':'function c_move(arg0){c_cmd("addxy",arg0,0,0,0);}'}
        q=self.protocol(source,extra);nodes=q.a.file(FILE)['nodes']
        self.assertTrue(q.safe(nodes,allow_state=True),q.reason)
        self.assertFalse(q.safe(nodes,allow_state=False))
        for change in ('global.choice=1;','global.choice=-1;','exit;','con+=1;','con=unknown;'):
            q=self.protocol(change,extra)
            self.assertFalse(q.safe(q.a.file(FILE)['nodes'],allow_state=True),change)

    def test_unknown_calls_and_dynamic_fields_remain_unsafe(self):
        extra={
            'gml_GlobalScript_c_move.gml':'function c_move(arg0){opaque();c_cmd("addxy",arg0,0,0,0);}',
            'gml_GlobalScript_c_var_instance.gml':'function c_var_instance(arg0,arg1,arg2){c_cmd_x("var",arg0,arg1,arg2,0,0,0);}',
        }
        for source in ('c_move(3);','c_customfunc(unknown);','c_var_instance(id,"choice",0);',
                       'c_var_instance(id,field,0);','if(opaque()){con=1;}'):
            q=self.protocol(source,extra)
            self.assertFalse(q.safe(q.a.file(FILE)['nodes'],True),source)
        q=self.protocol('c_var_instance(id,"sprite_index",7);',extra)
        self.assertTrue(q.safe(q.a.file(FILE)['nodes'],True),q.reason)

    def test_queue_handler_with_new_answer_write_is_not_trusted(self):
        filename='gml_GlobalScript_scr_cutscene_commands.gml'
        mutated=helpers()[filename].replace('if(_c=="addxy"){}','if(_c=="addxy"){global.choice=0;}')
        extra={filename:mutated,'gml_GlobalScript_c_move.gml':'function c_move(arg0){c_cmd("addxy",arg0,0,0,0);}'}
        q=self.protocol('c_move(3);',extra)
        self.assertFalse(q.safe(q.a.file(FILE)['nodes']))

    def test_localization_lookup_must_not_change_answer(self):
        q=self.protocol(MESSAGE)
        self.assertTrue(q.safe(q.a.file(FILE)['nodes']),q.reason)
        name='gml_GlobalScript_scr_84_get_lang_string.gml'
        q=self.protocol(MESSAGE,{name:helpers()[name].replace('return str;','global.choice=0;return str;')})
        self.assertFalse(q.safe(q.a.file(FILE)['nodes']))

    def test_label_getter_must_not_change_answer(self):
        source='global.choicemsg[0]=stringsetloc("Yes","key");'
        q=self.protocol(source)
        self.assertTrue(q.labels(q.a.file(FILE)['nodes']))
        filename='gml_GlobalScript_stringsetloc.gml'
        q=self.protocol(source,{filename:helpers()[filename].replace('return stringset(str);','global.choice=1;return stringset(str);')})
        self.assertFalse(q.labels(q.a.file(FILE)['nodes']))

    def test_older_localization_and_cleanup_variant(self):
        lookup='gml_GlobalScript_scr_84_get_lang_string.gml'
        kd='function k_d(arg0=0){with(obj_dialoguer){if(arg0>0){var _stayer=instance_create_depth(x,y,depth+1,obj_writer_stay);_stayer.side=side;_stayer.xoff=xoff;_stayer.yoff=yoff;_stayer.boxwidth=boxwidth;_stayer.boxheight=boxheight;_stayer.cur_jewel=cur_jewel;scr_doom(_stayer,arg0);}instance_destroy();}with(obj_writer)instance_destroy();}'
        extra={lookup:helpers()[lookup].replace('+lang_string_id+', '+string(lang_string_id)+'),
               'gml_GlobalScript_k_d.gml':kd,
               'gml_GlobalScript_scr_doom.gml':'function scr_doom(arg0=id,arg1){with(instance_create_depth(0,0,0,obj_doom)){alarm[0]=arg1;target=arg0;persistent=arg0.persistent;}}',
               'gml_Object_obj_doom_Alarm_0.gml':'with(target)instance_destroy();instance_destroy();'}
        q=self.protocol('k_d(3);'+MESSAGE,extra,chapter=4)
        self.assertTrue(q.safe(q.a.file(FILE)['nodes']),q.reason)
        for changed in ({**extra,'gml_Object_obj_doom_Create_0.gml':'global.choice=0;'},
                        {**extra,'gml_Object_obj_doom_Alarm_0.gml':'global.choice=0;'}):
            q=self.protocol('k_d(3);',changed,chapter=4)
            self.assertFalse(q.safe(q.a.file(FILE)['nodes']))

    def test_termination_is_detected_through_wrapper_before_text(self):
        extra={'gml_GlobalScript_c_wrap_end.gml':'function c_wrap_end(){c_cmd("terminatekillactors",0,0,0,0);}'}
        for source in ('c_wrap_end();'+MESSAGE,'if(global.choice==0){c_wrap_end();}'+MESSAGE):
            q=self.protocol(source,extra)
            self.assertFalse(q.safe(q.a.file(FILE)['nodes']),q.reason)
            self.assertEqual(q.reason,'queue_termination_before_text')
        q=self.protocol(MESSAGE+'c_wrap_end();',extra)
        self.assertTrue(q.safe(q.a.file(FILE)['nodes']),q.reason)


if __name__=='__main__':unittest.main()
