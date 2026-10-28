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
    def labels(self,nodes):return True
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
            if re.search(r'global\.choice(?:msg)?(?:\[|=(?!=)|\+=|-=|\+\+|--)|(?:\+\+|--)global\.choice',clean):
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

    def test_opaque_producer_condition_is_not_assumed_effect_free(self):
        for source in ('if(con==20 && opaque()){'+menu()+'}'+consumer(answers()),
                       'if(con==20){if(opaque()){'+menu()+'}}'+consumer(answers())):
            with self.subTest(source=source):
                scene,_=self.analyze(source)
                self.assertEqual(self.choices(scene),[])


if __name__=='__main__':unittest.main()
