"""Different source representations use the verified chooser protocol."""
import unittest
from tools.context.context_conditions import backend
from tools.context.context_files import Analyzer
from tools.context.context_data import references
from tests.context.test_context_files import all_nodes

FILE='gml_GlobalScript_scr_text.gml'
def key(i):return f'fixture_slash_Shared_gml_{i}_0'
TEXTS={0:'#Yes',1:'#No',2:'* Take it?/',3:'\\C2 ',4:'* Taken./%',5:'* Left./%',6:' ',7:'* Already gone./%',8:'* Before./'}


class SharedCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api=backend()

    def sources(self,chapter):
        def text(i):
            if chapter==1:return f'scr_84_get_lang_string("{key(i)}")'
            import json
            return f'stringsetloc({json.dumps(TEXTS[i])},"{key(i)}")'
        return {FILE:f'''function scr_text(arg0){{switch(arg0){{
case 773:
global.choicemsg[0]={text(0)};global.choicemsg[1]={text(1)};
global.choicemsg[2]={text(6)};
if(global.flag[81]==0){{global.msg[0]={text(2)};global.msg[1]={text(3)};}}
else global.msg[0]={text(7)};
break;
case 774:
if(global.choice==0){{global.msg[0]={text(4)};scr_itemget(3);}}else{{global.msg[0]={text(5)};}}
break;
}}}}''',
        'gml_Object_obj_choicer_neo_Other_10.gml':'if(canchoose==1 && choiced==0){choiced=1;global.choice=mychoice;alarm[0]=1;}',
        'gml_Object_obj_choicer_neo_Alarm_0.gml':'with(obj_dialoguer){global.msc+=1;scr_text(global.msc);event_user(0);}',
        'gml_Object_obj_choicer_neo_Create_0.gml':'global.choice=-1;',
        'gml_Object_obj_choicer_neo_Step_0.gml':'if(left_h())mychoice=0;if(right_h())mychoice=1;if(up_h())mychoice=2;if(down_h())mychoice=3;',
        'gml_Object_obj_choicer_neo_Draw_0.gml':'draw_text(x,y,string_hash_to_newline(global.choicemsg[i]));',
        'gml_Object_obj_writer_Draw_0.gml':'if(nextchar=="C"){if(nextchar2=="2" || nextchar2=="3" || nextchar2=="4"){choicer=instance_create(0,0,obj_choicer_neo);choicer.choicetotal=real(nextchar2)-1;}}',
        'gml_Object_entry_Step_0.gml':'global.msc=773;scr_text(global.msc);'}

    def analyze(self,ch,sources):
        tables={key(i):{'en':t} for i,t in TEXTS.items()}
        a=Analyzer(sources,ch,tables,self.api)
        scene=a.analyze(FILE)
        return scene,a

    def test_ch1_lookup_and_later_literals_preserve_conditional_menu(self):
        for ch in (1,2,3,4,5):
            with self.subTest(chapter=ch):
                scene,a=self.analyze(ch,self.sources(ch))
                choices=[n for n in all_nodes(scene['body']) if n['type']=='choice']
                self.assertEqual(len(choices),1)
                self.assertEqual([b['option']['key'] for b in choices[0]['branches']],[key(0),key(1)])
                self.assertEqual([[r['key'] for r in references(b['body'])] for b in choices[0]['branches']],[[key(4)],[key(5)]])
                conditional=next(n for n in all_nodes(scene['body']) if n['type']=='condition')
                self.assertTrue(any(n['type']=='choice' for n in all_nodes(conditional['branches'][0]['body'])))
                self.assertFalse(any(n['type']=='choice' for n in all_nodes(conditional['branches'][1]['body'])))
                self.assertEqual(scene['reference_count'],8)
                self.assertEqual(len({r['occurrence_id'] for r in references(scene['body'])}),8)
                self.assertEqual(a.analyze(FILE),scene)
                self.assertEqual(a.evidence[0]['menu_case'],773)

    def test_bad_protocol_and_alternate_entries_do_not_link(self):
        for filename,old,new in (
            ('gml_Object_obj_choicer_neo_Alarm_0.gml','global.msc+=1;','global.msc+=2;'),
            ('gml_Object_obj_choicer_neo_Other_10.gml','global.choice=mychoice;','global.choice=3-mychoice;'),
            ('gml_Object_obj_writer_Draw_0.gml','choicer.choicetotal=real(nextchar2)-1;','choicer.choicetotal=real(nextchar2)-1;choicer.choicetotal=3;'),
            ('gml_Object_entry_Step_0.gml','global.msc=773;scr_text(global.msc);','global.msc=772;scr_text(773);'),
            ('gml_Object_entry_Step_0.gml','scr_text(global.msc);','scr_text(dynamic_value);'),
            ('gml_Object_entry_Step_0.gml','scr_text(global.msc);','script_execute(scr_text,global.msc);')):
            sources=self.sources(1);sources[filename]=sources[filename].replace(old,new)
            scene,a=self.analyze(1,sources)
            self.assertFalse(any(n['type']=='choice' for n in all_nodes(scene['body'])))
            self.assertEqual(scene['reference_count'],8)

    def test_unbounded_menu_and_response_variants_fail_closed(self):
        base=self.sources(2)
        for old,new in (
            ('case 774:','case 775:'),
            ('if(global.flag[81]==0)','if(global.flag[81]==0)global.choicemsg[0]="changed";if(global.flag[81]==0)'),
            ('case 773:','case 773:opaque_callback();'),
            ('case 773:','case 773:global.msc=882;'),
            ('case 773:','case 773:++global.msc;'),
            ('case 773:','case 773:global.msc*=2;'),
            ('case 773:','case 773:exit;'),
            ('case 774:','case 774:opaque_callback();'),
            ('scr_itemget(3);','exit;'),
            ('scr_itemget(3);','break;'),
            ('scr_itemget(3);','global.choice=1;'),
            ('scr_itemget(3);','global.choice*=2;'),
            ('else{global.msg[0]=','if(global.choice==1){global.msg[0]='),
            ('case 774:','case 774:global.choicemsg[0]="Next";')):
            sources={**base,FILE:base[FILE].replace(old,new)}
            scene,a=self.analyze(2,sources)
            self.assertFalse(any(n['type']=='choice' for n in all_nodes(scene['body'])),(old,new))
            self.assertEqual(scene['reference_count'],8)

    def test_unrelated_literal_entry_does_not_block_other_menu(self):
        sources=self.sources(2)
        sources['gml_Object_extra_Step_0.gml']='scr_text(900);'
        scene,a=self.analyze(2,sources)
        self.assertEqual(sum(n['type']=='choice' for n in all_nodes(scene['body'])),1)
        self.assertEqual(a.evidence[0]['protocol']['excluded_literal_entries'],[900])

    def test_guarded_navigation_and_bound_literal_entry(self):
        sources=self.sources(2)
        step='gml_Object_obj_choicer_neo_Step_0.gml'
        for i,direction in enumerate(('right','up','down'),1):
            sources[step]=sources[step].replace(f'if({direction}_h())',f'if(choicetotal>={i} && {direction}_h())')
        entry='gml_Object_entry_Step_0.gml'
        sources[entry]='if(ready){global.msc=773;scr_text(773);}'
        scene,a=self.analyze(2,sources)
        self.assertEqual(sum(n['type']=='choice' for n in all_nodes(scene['body'])),1)
        self.assertEqual(a.evidence[0]['protocol']['bound_literal_entries'][0]['value'],773)
        for code in ('if(ready)global.msc=773;scr_text(773);',
                     'global.msc=773;opaque();scr_text(773);',
                     'global.msc=772;scr_text(773);'):
            sources[entry]=code
            scene,a=self.analyze(2,sources)
            self.assertFalse(any(n['type']=='choice' for n in all_nodes(scene['body'])))
