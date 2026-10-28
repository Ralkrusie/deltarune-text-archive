"""Direct second-question regressions with source-checked dialogue helpers."""
import unittest
from collections import Counter
from unittest.mock import patch

from tools.context.context_conditions import backend
from tools.context.context_files import Analyzer
from tools.context.context_data import references
from tests.context.test_queued_protocol import helpers

FILE = 'gml_Object_obj_fixture_Step_0.gml'


def key(i): return f'fixture_slash_Test_gml_{i}_0'
def msg(i): return f'msgsetloc(0,"text{i}","{key(i)}");'
def menu(value='21.25', first=1, maker='d_make();'):
    return (('con='+value+';' if value else '') + 'global.interact=1;global.msc=-99;global.choice=-1;'
            + ''.join(f'global.choicemsg[{j}]=stringsetloc("text{i}","{key(i)}");' for j,i in enumerate([first,first+1]))
            + 'msgset(0,"\\\\C2");' + maker)
def target(body, value='21.25'): return f'if(con=={value} && global.choice!=-1){{{body}}}'
def answers(first=10): return f'if(global.choice==0){{{msg(first)}}}else{{{msg(first+1)}}}'
def walk(n):
    yield n
    for c in n.get('children',[]): yield from walk(c)
    if 'prefix' in n: yield from walk(n['prefix'])
    for b in n.get('branches',[]): yield from walk(b['body'])


class DirectChoicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.api=backend()

    def analyze(self, source, changed=None, chapter=5):
        sources=helpers()
        sources.update({
            'gml_GlobalScript_d_ex.gml':'function d_ex(){return instance_exists(obj_dialoguer);}',
            'gml_GlobalScript_msgset.gml':'function msgset(arg0,arg1){global.msgno=arg0;global.msg[arg0]=arg1;}',
            'gml_GlobalScript_msgnext.gml':'function msgnext(arg0){global.msgno++;msgset(global.msgno,arg0);}',
            'gml_GlobalScript_msgsetloc.gml':'function msgsetloc(arg0,arg1,arg2){var msg_index=arg0;var str=arg1;var localized_string_id=arg2;if(!is_english())str=scr_84_get_lang_string(localized_string_id);msgset(msg_index,str);}',
            'gml_GlobalScript_scr_speaker.gml':'function scr_speaker(arg0){_speaker=arg0;global.fc=0;if(_speaker=="someone")global.typer=5;}',
            FILE:source,
        })
        sources.update(changed or {})
        a=Analyzer(sources,chapter,{key(i):{'en':f'text{i}'} for i in range(50)},self.api)
        # Isolate the added matcher from the older broad local-choice rule.
        with patch.object(Analyzer,'local_choice',return_value=None), patch.object(Analyzer,'connect_scoped_choices'):
            scene=a.analyze(FILE)
        self.assertEqual(Counter(r['occurrence_id'] for r in references(scene['body'])),
                         Counter(r['occurrence_id'] for r in a.file(FILE)['refs']))
        return scene,a

    def choices(self,scene): return [n for n in walk(scene['body']) if n['type']=='choice']
    def keys(self,n): return [r['key'] for r in references(n)]
    def fixture(self): return 'if(con==20 && !d_ex()){'+menu()+'}'+target(answers())

    def test_decimal_menu_maps_answers(self):
        scene,a=self.analyze(self.fixture())
        c,=self.choices(scene)
        self.assertEqual([b['option']['key'] for b in c['branches']],[key(1),key(2)])
        self.assertEqual([self.keys(b['body']) for b in c['branches']],[[key(10)],[key(11)]])
        self.assertEqual(a.direct_audit[0]['state'],'21.25')

    def test_nested_menu_inherits_state_and_common_creation(self):
        body='con=30;if(global.choice==0){'+msg(10)+menu(None,20,'')+'}else{con=40;'+msg(11)+'}var d=d_make();d.side=0;'
        scene,_=self.analyze('if(con==20){'+menu()+'}'+target(body)+target(answers(30),'30'))
        outer,inner=self.choices(scene)
        self.assertIn(inner,list(walk(outer['branches'][0]['body'])))
        self.assertNotIn(key(30),self.keys(outer['branches'][1]['body']))
        self.assertEqual(self.keys(inner['branches'][0]['body']),[key(30)])

    def test_branch_local_state_after_common_write_and_empty_option(self):
        body='con=-1;marker.image_speed=0.25;if(global.choice==1){'+msg(11)+'}else{'+menu('30',20)+'}'
        response='con=100;if(global.choice==0){if(scr_flag_get(9)==0){scr_flag_set(9,1);}'+msg(30)+'}'
        extra={'gml_GlobalScript_scr_flag_get.gml':'function scr_flag_get(arg0){return global.flag[arg0];}',
               'gml_GlobalScript_scr_flag_set.gml':'function scr_flag_set(arg0,arg1){global.flag[arg0]=arg1;}'}
        scene,_=self.analyze('if(con==20){'+menu()+'}'+target(body)+target(response,'30'),extra)
        outer,inner=self.choices(scene)
        self.assertIn(inner,list(walk(outer['branches'][0]['body'])))
        self.assertEqual(self.keys(inner['branches'][1]['body']),[])

    def test_unknown_callback_reset_creation_and_competing_states_are_rejected(self):
        base=self.fixture()
        variants=[base.replace('d_make();','unknown();d_make();'),
                  base.replace('d_make();','var d=d_make();d.side=unknown();'),
                  base.replace('d_make();','var d=d_make();d=other;d.side=0;'),
                  base.replace('con=21.25;','con=21.25;if(flag){con=30;}'),
                  base+'if(timer>30){con=21.25;}',
                  base.replace('global.choice==0','global.choice==0').replace(msg(10),'global.choice=1;'+msg(10)),
                  base.replace('global.msc=-99;','global.msc=42;'),
                  'var customcon=0;'+base]
        for source in variants:
            with self.subTest(source=source):
                scene,_=self.analyze(source)
                self.assertEqual(self.choices(scene),[])

    def test_helper_side_effects_and_missing_protocol_reject(self):
        variants=[{'gml_GlobalScript_scr_speaker.gml':'function scr_speaker(arg0){global.choice=1;}'},
                  {'gml_GlobalScript_msgset.gml':'function msgset(arg0,arg1){global.choice=1;global.msg[arg0]=arg1;}'},
                  {'gml_GlobalScript_d_ex.gml':'function d_ex(){global.choice=1;return true;}'}]
        source=self.fixture().replace(msg(10),'scr_speaker("someone");'+msg(10))
        for extra in variants:
            with self.subTest(extra=extra):
                scene,_=self.analyze(source,extra)
                self.assertEqual(self.choices(scene),[])

    def test_shared_target_and_timeout_guard_not_duplicated(self):
        source=self.fixture()+target('global.choice=0;')
        scene,_=self.analyze(source)
        self.assertEqual(self.choices(scene),[])
        scene,_=self.analyze(self.fixture().replace('global.choice!=-1','global.choice!=-1 && timer<30'))
        self.assertEqual(self.choices(scene),[])

    def test_common_prefix_tail_once_and_termination_before_text(self):
        source='if(con==20){'+menu()+'}'+target(msg(40)+answers()+msg(41))
        scene,_=self.analyze(source)
        c,=self.choices(scene)
        self.assertEqual(self.keys(c['prefix']),[key(40)])
        self.assertEqual(self.keys(scene['body']).count(key(41)),1)
        self.assertTrue(c['join_next'])
        extra={'gml_GlobalScript_c_stop.gml':'function c_stop(){c_cmd("terminatekillactors",0,0,0,0);}'}
        scene,_=self.analyze(source.replace(msg(40),'c_stop();'+msg(40)),extra)
        self.assertEqual(self.choices(scene),[])


if __name__=='__main__': unittest.main()
