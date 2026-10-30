"""Choice planning/projection regressions, isolated from protocol verification.

The protocol stub only accepts tiny inert fixture calls. Real engine and helper
validation has its own tests; none of these fixtures claims to validate GML's
queue implementation.
"""
from collections import Counter
import re
import unittest
from unittest.mock import patch

from tools.context.context_conditions import backend
from tools.context.context_data import references
from tools.context.context_files import Analyzer

FILE='gml_Object_obj_fixture_Step_0.gml'


def key(i):return f'fixture_slash_Test_gml_{i}_0'
def message(i):return f'c_msgsetloc(0,"text{i}","{key(i)}");'
def option(slot,i):return f'global.choicemsg[{slot}]=stringsetloc("text{i}","{key(i)}");'
def menu(target='21.25',first=1):
    return ('global.msc=-99;global.choice=-1;'+option(0,first)+option(1,first+1)+
            'c_msgset(0,"\\\\C2");c_customfunc(open_menu,0);c_waitcustom();con='+target+';')
def consumer(body,target='21.25'):
    return ('if(con=='+target+' && customcon==1 && global.choice!=-1){'
            'customcon=0;c_waitcustom_end();k_d(3);'+body+'}')
def answers(first=10):
    return f'if(global.choice==0){{{message(first)}}}if(global.choice==1){{{message(first+1)}}}'
def walk(node):
    yield node
    if 'prefix' in node:yield from walk(node['prefix'])
    for c in node.get('children',[]):yield from walk(c)
    for b in node.get('branches',[]):yield from walk(b['body'])


class InertProtocol:
    """Narrow fixture protocol; fail closed on answer writes and opaque work."""
    def __init__(self,analyzer,name):
        self.a=analyzer;self.reason=None;self.helpers={'fixture_protocol'}
    def ready(self):return True
    def fail(self,reason):self.reason=reason;return False
    def labels(self,nodes):return True
    def menu_setup(self,node):return None
    def staging_callback(self,node):return False
    def compact(self,text):return ''.join(t.group() for t in self.a.flow.TOKEN.finditer(text) if not t.group().startswith(('//','/*')))
    def prompt(self,node):
        calls=list(self.a.calls(node.text))
        return (node.kind=='stmt' and bool(calls) and calls[0]['call'] in ('c_msgset','c_msgnext','c_msgsetloc','c_msgnextloc')
                and calls[0]['offset']==0 and calls[0]['end']==len(node.text.rstrip(';').strip()))
    def maker(self,node):
        return node.kind=='stmt' and re.fullmatch(r'c_customfunc\(open_menu,\s*0\);',node.text) is not None
    def safe(self,nodes,allow_state=False,_last_text=None):
        allowed={'c_msgsetloc','c_speaker','c_waitcustom_end','k_d','c_wait','move_actor'}
        for n in self.a.flow.walk(nodes):
            if n.kind not in ('block','if','stmt'):
                self.reason='control_flow';return False
            clean=''.join(t.group() for t in self.a.flow.TOKEN.finditer(n.text) if not t.group().startswith(('//','/*')))
            if re.search(r'global\.choice(?:msg)?(?:\[|=(?!=)|(?:\+|-|\*|/|%|&|\||\^|<<|>>|\?\?)=|\+\+|--)|(?:\+\+|--)global\.choice|\w+\.(?:customcon|con)=(?!=)',clean):
                self.reason='answer_write';return False
            if any(t.group() in ('exit','return','break','continue','function') for t in self.a.flow.TOKEN.finditer(n.text)):
                self.reason='transfer';return False
            for call in self.a.calls(n.text):
                if call['call'] not in allowed:
                    self.reason='opaque_call';return False
        return True


class QueuedChoicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api=backend()

    def analyze(self,source):
        tables={key(i):{'en':f'text{i}'} for i in range(60)}
        analyzer=Analyzer({FILE:source},5,tables,self.api)
        with patch('tools.context.queued_choices.QueuedProtocol',InertProtocol):
            scene=analyzer.analyze(FILE)
        actual=Counter(r['occurrence_id'] for r in references(scene['body']))
        expected=Counter(r['occurrence_id'] for r in analyzer.file(FILE)['refs'])
        self.assertEqual(actual,expected)
        return scene,analyzer

    def choices(self,scene):return [n for n in walk(scene['body']) if n['type']=='choice']
    def keys(self,node):return [r['key'] for r in references(node)]
    def fixture(self,body=None):return 'if(con==20){'+menu()+'}'+consumer(answers() if body is None else body)

    def test_decimal_constant_and_exclusive_answers(self):
        scene,a=self.analyze(self.fixture())
        choice,=self.choices(scene)
        self.assertEqual([b['option']['key'] for b in choice['branches']],[key(1),key(2)])
        self.assertEqual([self.keys(b['body']) for b in choice['branches']],[[key(10)],[key(11)]])
        self.assertEqual(a.queue_audit[0]['status'],'connected')
        self.assertEqual(a.queue_audit[0]['state'],'21.25')

    def test_nested_producer_keeps_parent_condition(self):
        source='if(con==20){if(flag){'+message(0)+menu()+'}else{'+message(3)+'}}'+consumer(answers())
        scene,_=self.analyze(source)
        conditions=[n for n in walk(scene['body']) if n['type']=='condition']
        parent=next(n for n in conditions if n['branches'][0]['label']=='flag')
        self.assertEqual(len(self.choices({'body':parent['branches'][0]['body']})),1)
        self.assertEqual(self.keys(parent['branches'][1]['body']),[key(3)])

    def test_nested_new_question_has_its_own_answers(self):
        response='if(global.choice==0){'+message(10)+menu('30',20)+'}if(global.choice==1){'+message(11)+'}'
        source=self.fixture(response)+consumer(answers(40),'30')
        scene,a=self.analyze(source)
        choices=self.choices(scene)
        self.assertEqual(len(choices),2)
        outer=next(c for c in choices if c['branches'][0]['option']['key']==key(1))
        inner=next(c for c in choices if c['branches'][0]['option']['key']==key(20))
        self.assertIn(inner,list(walk(outer['branches'][0]['body'])))
        self.assertEqual(self.keys(outer['branches'][1]['body']),[key(11)])
        self.assertEqual([self.keys(b['body']) for b in inner['branches']],[[key(40)],[key(41)]])
        self.assertEqual(sum(r['status']=='connected' for r in a.queue_audit),2)

    def test_common_prefix_tail_and_repeated_action_only_answer(self):
        source=self.fixture(message(30)+answers()+'if(global.choice==0){move_actor();}'+message(31))
        scene,_=self.analyze(source)
        choice,=self.choices(scene)
        self.assertEqual(self.keys(choice['prefix']),[key(30)])
        self.assertTrue(choice['join_next'])
        self.assertEqual(self.keys(scene['body']).count(key(30)),1)
        self.assertEqual(self.keys(scene['body']).count(key(31)),1)
        self.assertNotIn(key(31),self.keys(choice))
        self.assertEqual([self.keys(b['body']) for b in choice['branches']],[[key(10)],[key(11)]])

    def test_decimal_equivalent_competing_writer_is_rejected(self):
        source=self.fixture().replace('21.25','21.1')+'if(other_flag){other.con=21.10;}'
        scene,a=self.analyze(source)
        self.assertEqual(self.choices(scene),[])
        self.assertIn('competing_or_dynamic_state_write',[r['reason'] for r in a.queue_audit])

    def test_dynamic_string_state_write_is_rejected(self):
        source=self.fixture()+'if(other_flag){c_var_instance(id,"con",21.25);}'
        scene,_=self.analyze(source)
        self.assertEqual(self.choices(scene),[])

    def test_extra_guard_and_earlier_consumer_are_rejected(self):
        source=self.fixture()
        for changed in (source.replace('customcon==1','customcon==1 && flag'),consumer(answers())+'if(con==20){'+menu()+'}'):
            with self.subTest(source=changed):
                scene,_=self.analyze(changed)
                self.assertEqual(self.choices(scene),[])

    def test_repeated_textual_answer_or_common_interleaving_is_rejected(self):
        for body in (answers()+'if(global.choice==0){'+message(12)+'}',
                     'if(global.choice==0){'+message(10)+'}'+message(12)+'if(global.choice==1){'+message(11)+'}'):
            with self.subTest(body=body):
                scene,_=self.analyze(self.fixture(body))
                self.assertEqual(self.choices(scene),[])

    def test_answer_overwrite_exit_and_unknown_calls_are_rejected(self):
        for prefix in ('global.choice=0;','if(timer>30){global.choice=0;}','if(flag){exit;}','opaque();'):
            with self.subTest(prefix=prefix):
                scene,_=self.analyze(self.fixture(prefix+answers()))
                self.assertEqual(self.choices(scene),[])

    def test_unknown_nested_question_does_not_permit_old_answer_overwrite(self):
        nested=menu('30',20).replace('c_customfunc(open_menu,0);','c_customfunc(opaque,0);')
        response='if(global.choice==0){'+message(10)+nested+'}if(global.choice==1){'+message(11)+'}'
        scene,_=self.analyze(self.fixture(response)+consumer(answers(40),'30'))
        self.assertEqual(self.choices(scene),[])

    def test_ancillary_assignment_does_not_drop_child_or_parent_menu(self):
        response='if(global.choice==0){'+message(10)+menu('30',20)+'}else{'+message(11)+'}'
        staging='marker=make_marker(10,20);marker.visible=false;marker.depth=900;'
        child='if(global.choice==0){'+staging+message(40)+'}else{'+message(41)+'}'
        scene,a=self.analyze(self.fixture(response)+consumer(child,'30'))
        choices=self.choices(scene)
        self.assertEqual(len(choices),2)
        outer=next(c for c in choices if c['branches'][0]['option']['key']==key(1))
        inner=next(c for c in choices if c['branches'][0]['option']['key']==key(20))
        self.assertIn(inner,list(walk(outer['branches'][0]['body'])))
        self.assertEqual([self.keys(b['body']) for b in inner['branches']],[[key(40)],[key(41)]])
        row=next(r for r in a.queue_audit if r.get('state')=='30')
        self.assertTrue(any('make_marker' in r['statement'] for r in row['response_review']))
        self.assertEqual(row['relation_scope'],'local_menu_response')
        self.assertNotIn('response_review',str(scene))

    def test_response_assignment_relaxation_keeps_control_hazards(self):
        for statement in ('marker=script_execute(callback);','marker=c_customfunc(callback);',
                          'marker=room_goto(next_room);','marker=function(){return 0;};',
                          'marker=variable_global_set("choice",1);',
                          'global.marker=make_marker();','master.customcon=1;','master.con=5;',
                          'marker=make_marker("\\\\C2");'):
            with self.subTest(statement=statement):
                scene,_=self.analyze(self.fixture('if(global.choice==0){'+statement+message(10)+'}else{'+message(11)+'}'))
                self.assertEqual(self.choices(scene),[])

    def test_with_loop_or_deferred_producer_is_not_hoisted(self):
        for wrapped in ('with(other){'+menu()+'}','while(flag){'+menu()+'}',
                        'c_customfunc(function(){'+menu()+'});'):
            with self.subTest(wrapped=wrapped):
                scene,_=self.analyze('if(con==20){'+wrapped+'}'+consumer(answers()))
                self.assertEqual(self.choices(scene),[])

    def test_multivariable_local_state_shadowing_is_rejected(self):
        for declaration in ('var spare, con;','var spare=0, con;','static spare=0, con;'):
            with self.subTest(declaration=declaration):
                scene,_=self.analyze(declaration+self.fixture())
                self.assertEqual(self.choices(scene),[])

    def test_local_wait_flag_cannot_shadow_the_queue_instance_field(self):
        for declaration in ('var customcon=0;','var spare=0, customcon;',
                            'static customcon=0;','globalvar customcon;'):
            with self.subTest(declaration=declaration):
                scene,a=self.analyze(declaration+self.fixture())
                self.assertEqual(self.choices(scene),[])
                self.assertIn('competing_or_dynamic_state_write',[r['reason'] for r in a.queue_audit])

    def test_all_compound_state_updates_are_competing_writes(self):
        for update in ('con+=1;','con-=1;','con*=2;','con/=2;','con%=2;',
                       'con&=1;','con|=1;','con^=1;','con<<=1;','con>>=1;',
                       'con??=1;','con++;','con--;','++con;','--con;'):
            with self.subTest(update=update):
                scene,a=self.analyze(self.fixture()+'if(other_flag){'+update+'}')
                self.assertEqual(self.choices(scene),[])
                self.assertIn('competing_or_dynamic_state_write',[r['reason'] for r in a.queue_audit])
        # Similar-looking reads and quoted text are not state writes.
        scene,_=self.analyze(self.fixture()+'if((con<<1)==42 || (con%3)==1){move_actor();}'+
                            'var unrelated="con %= 2; customcon";')
        self.assertEqual(len(self.choices(scene)),1)

    def test_unrecognized_prompt_api_or_extra_effect_is_rejected(self):
        for prompt in ('c_msgsetevil(0,"\\\\C2");','c_msgset(0,"\\\\C2")+opaque();'):
            with self.subTest(prompt=prompt):
                source=self.fixture().replace('c_msgset(0,"\\\\C2");',prompt)
                scene,_=self.analyze(source)
                self.assertEqual(self.choices(scene),[])

    def test_deferred_answer_write_before_immediate_reset_is_rejected(self):
        # Queue order differs from GML source evaluation: this callback executes
        # later, after the immediate reset, and can forge a menu answer.
        source=('if(con==20){c_customfunc(function(){global.choice=0;});'+menu()+'}'+consumer(answers()))
        scene,_=self.analyze(source)
        self.assertEqual(self.choices(scene),[])

    def test_deferred_ancestor_prefix_cannot_forge_nested_menu_answer(self):
        source=('if(con==20){c_customfunc(function(){global.choice=0;});if(flag){'+menu()+'}}'+consumer(answers()))
        scene,_=self.analyze(source)
        self.assertEqual(self.choices(scene),[])

    def test_unproved_staging_before_menu_is_audited_not_a_veto(self):
        prefix='var marker=unknown_create();marker.visible=false;unknown_walk(marker);'
        scene,a=self.analyze('if(con==20){'+prefix+menu()+'}'+consumer(answers()))
        choice,=self.choices(scene)
        self.assertEqual([self.keys(b['body']) for b in choice['branches']],[[key(10)],[key(11)]])
        row=a.queue_audit[0]
        self.assertEqual(row['relation_scope'],'local_menu_response')
        self.assertTrue(any('unknown_walk' in r['statement'] for r in row['prefix_review']))
        self.assertNotIn('prefix_review',str(scene))

    def test_local_prefix_hazards_are_still_rejected(self):
        prefixes=('global.choice=0;', 'global.choice%=2;', '++global.choice;',
                  'global.choicemsg[0]="old";', 'master.customcon=1;',
                  'if(flag){exit;}', 'c_customfunc(named_callback);',
                  'c_delay_customfunc(30,named_callback);',
                  'variable_global_set("choice",1);', 'c_cmd("customfunc",callback);')
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                scene,_=self.analyze('if(con==20){'+prefix+menu()+'}'+consumer(answers()))
                self.assertEqual(self.choices(scene),[])

    def test_local_prefix_ignores_comments_strings_and_read_only_conditions(self):
        prefix='unknown_walk("global.choice=0; con=9;");/* global.choice=0; */if(global.choice==0){unknown_walk();}'
        scene,_=self.analyze('if(con==20){'+prefix+menu()+'}'+consumer(answers()))
        self.assertEqual(len(self.choices(scene)),1)

    def test_prefix_relaxation_does_not_apply_between_menu_and_answer(self):
        source=self.fixture().replace('c_waitcustom();','c_waitcustom();unknown_walk();')
        scene,_=self.analyze(source)
        self.assertEqual(self.choices(scene),[])

    def test_conditional_display_work_inside_menu_setup(self):
        source=self.fixture().replace('c_customfunc(open_menu,0);',
            'if(global.lang=="ja"){move_actor();}c_customfunc(open_menu,0);')
        scene,_=self.analyze(source)
        choice,=self.choices(scene)
        self.assertEqual([self.keys(b['body']) for b in choice['branches']],[[key(10)],[key(11)]])
        for effect in ('global.choice=0;','opaque();','exit;',option(0,30)):
            with self.subTest(effect=effect):
                result,_=self.analyze(source.replace('move_actor();',effect))
                self.assertEqual(self.choices(result),[])

    def test_opaque_common_suffix_keeps_answer_mapping_and_separate_source_block(self):
        tail='var animation=function(){with(actor){step_func=function(){opacity-=0.1;};}};attach(animation);'+message(30)+'if(flag){'+message(31)+'}con=40;'
        scene,a=self.analyze(self.fixture(answers()+tail)+'if(con==40){'+message(40)+'}')
        choice,=self.choices(scene)
        self.assertEqual([self.keys(b['body']) for b in choice['branches']],[[key(10)],[key(11)]])
        self.assertNotIn('join_next',choice)
        self.assertEqual(self.keys(scene['body']).count(key(30)),1)
        self.assertTrue(any(n['type']=='condition' and n['branches'][0]['label']=='flag' for n in walk(scene['body'])))
        self.assertFalse(any(r['rule']=='queued_state_continuation' for r in a.evidence))
        self.assertTrue(any(r.get('scope')=='unexpanded_common_tail' for r in a.queue_audit[0]['response_review']))

    def test_opaque_work_before_or_inside_answers_is_not_a_common_suffix(self):
        for body in ('opaque();'+answers(),
                     'if(global.choice==0){opaque();'+message(10)+'}else{'+message(11)+'}',
                     answers()+'opaque();global.choice=0;',
                     answers()+'opaque();c_msgset(0,"\\\\C2");',
                     'if(global.choice==0){'+message(10)+'}if(flag){'+message(30)+'}if(global.choice==1){'+message(11)+'}'):
            with self.subTest(body=body):
                scene,_=self.analyze(self.fixture(body))
                self.assertEqual(self.choices(scene),[])

    def test_opaque_producer_condition_is_not_assumed_effect_free(self):
        for source in ('if(con==20 && opaque()){'+menu()+'}'+consumer(answers()),
                       'if(con==20){if(opaque()){'+menu()+'}}'+consumer(answers())):
            with self.subTest(source=source):
                scene,_=self.analyze(source)
                self.assertEqual(self.choices(scene),[])

    def test_state_only_answers_reach_their_text_and_shared_landing_once(self):
        source=self.fixture('if(global.choice==0){con=30;}else{con=40;}')
        source+='if(con==30){'+message(30)+'con=50;}if(con==40){'+message(40)+'con=50;}if(con==50){'+message(50)+'}'
        scene,a=self.analyze(source)
        choice,=self.choices(scene)
        self.assertEqual([self.keys(b['body']) for b in choice['branches']],[[key(30)],[key(40)]])
        jumps=[n for n in walk(scene['body']) if n['type']=='jump']
        self.assertEqual(len(jumps),2)
        self.assertEqual(len({j['target'] for j in jumps}),1)
        self.assertEqual(self.keys(scene['body']).count(key(50)),1)
        self.assertTrue(any(n.get('anchor')==jumps[0]['target'] for n in walk(scene['body'])))

    def test_state_continuation_nests_an_existing_question(self):
        source=self.fixture('if(global.choice==0){con=30;}else{con=40;}')
        source+='if(con==30){'+message(30)+menu('31',20)+'}'+consumer(answers(40),'31')
        source+='if(con==40){'+message(50)+'}'
        scene,_=self.analyze(source)
        outer=self.choices(scene)[0]
        self.assertEqual(len(self.choices({'body':outer['branches'][0]['body']})),1)
        self.assertEqual(self.keys(outer['branches'][1]['body']),[key(50)])

    def test_routes_do_not_follow_cycles_extra_guards_or_conditional_writes(self):
        for suffix in ('if(con==30 && flag){'+message(30)+'}',
                       'if(con==30){if(flag){exit;}con=40;}if(con==40){'+message(40)+'}',
                       'if(con==30){if(flag){con=31;}con=40;}if(con==40){'+message(40)+'}'):
            with self.subTest(suffix=suffix):
                scene,_=self.analyze(self.fixture('if(global.choice==0){con=30;}else{'+message(11)+'}')+suffix)
                outer=self.choices(scene)[0]
                self.assertNotIn(key(40),self.keys(outer['branches'][0]['body']))
        source='if(con==10){'+message(30)+'}'+self.fixture('if(global.choice==0){con=10;}else{'+message(11)+'}')
        scene,_=self.analyze(source)
        self.assertNotIn(key(30),self.keys(self.choices(scene)[0]))

    def test_state_writes_do_not_reorder_later_messages_or_link_empty_landings(self):
        scene,_=self.analyze(self.fixture('if(global.choice==0){con=30;'+message(12)+'}else{'+message(11)+'}')+
                             'if(con==30){'+message(30)+'}')
        self.assertEqual(self.keys(self.choices(scene)[0]['branches'][0]['body']),[key(12)])
        scene,_=self.analyze(self.fixture('if(global.choice==0){con=30;}else{con=30;}')+'if(con==30){move_actor();}')
        self.assertFalse(any(n['type']=='jump' for n in walk(scene['body'])))

    def test_timed_gate_keeps_automatic_answer_and_two_response_arms(self):
        source='if(con==20){'+menu()+'timer=0;}'
        source+='if(con==21.25 && customcon==1){timer++;if(timer>=30)global.choice=0;if(global.choice!=-1){con=22;timer=0;customcon=0;c_waitcustom_end();}}'
        source+='if(con==22){'+answers()+'}'
        scene,a=self.analyze(source)
        choice,=self.choices(scene)
        self.assertEqual(choice['auto_answer'],{'condition':'timer>=30','option':0})
        self.assertEqual([self.keys(b['body']) for b in choice['branches']],[[key(10)],[key(11)]])
        for changed in (source.replace('global.choice=0;','global.choice=unknown;'),
                        source.replace('timer>=30','other>=30'),
                        source.replace('c_waitcustom_end();','opaque();c_waitcustom_end();'),
                        source.replace('if(con==22)','if(con==22 && flag)')):
            with self.subTest(source=changed):
                result,_=self.analyze(changed)
                self.assertEqual(self.choices(result),[])


if __name__=='__main__':unittest.main()
