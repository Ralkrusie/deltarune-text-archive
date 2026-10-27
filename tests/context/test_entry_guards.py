"""Guard facts describe the source check, never a later mutable value."""
import unittest
from tests.context import test_context_files as fixtures
from tests.context.test_context_files import all_nodes, msg, FILE


class EntryGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ContextFilesTests.setUpClass()
        cls.fixture=fixtures.ContextFilesTests()

    def guards(self,scene,key):
        result=[]
        def walk(n,inherited):
            inherited=inherited+n.get('entry_guards',[])
            if n.get('key')==f'fixture_slash_Test_gml_{key}_0':result.append(inherited)
            for c in n.get('children',[]):walk(c,inherited)
            for b in n.get('branches',[]):
                if 'option' in b:walk(b['option'],inherited)
                walk(b['body'],inherited)
        walk(scene['body'],[])
        return result

    def test_exit_check_only_applies_to_following_text_and_retains_check_position(self):
        scene,a=self.fixture.analyze(f'{msg(1)}\nif(global.plot<25)exit;\nglobal.plot=99;\nif(leave_con==1){{{msg(2)}}}\nif(other){{{msg(3)}}}')
        self.assertEqual(self.guards(scene,1),[[]])
        for key in (2,3):
            guard=self.guards(scene,key)[0][0]
            self.assertEqual(guard,{'condition':'!(global.plot<25)','source':{'file':FILE,'line':2},'visible':True,'meaning':'passed_at_source'})
        self.assertEqual(sum(r['rule']=='passed_exit_guard' for r in a.evidence),1)
        self.assertEqual(scene['reference_count'],3)

    def test_nested_guard_does_not_escape_branch_case_or_iteration(self):
        for shell in ('if(outer){{{body}}}', 'with(npc){{{body}}}', 'while(loop){{{body}}}', 'switch(value){{case 1:{body}break;case 2:{other}break;}}'):
            source=shell.format(body=f'if(blocked)exit;{msg(1)}',other=msg(3))+msg(2)
            scene,_=self.fixture.analyze(source)
            self.assertEqual(len(self.guards(scene,1)[0]),1)
            self.assertEqual(self.guards(scene,2),[[]])
            if 'switch' in shell:self.assertEqual(self.guards(scene,3),[[]])

    def test_deferred_functions_do_not_inherit_enclosing_guard(self):
        source=f'if(global.flag[4])exit;function callback(){{{msg(1)}if(disabled)return;{msg(2)}}}handler=function(){{{msg(3)}}};{msg(4)}'
        scene,_=self.fixture.analyze(source)
        self.assertEqual(self.guards(scene,1),[[]])
        self.assertEqual([x['condition'] for x in self.guards(scene,2)[0]],['!(disabled)'])
        self.assertEqual(self.guards(scene,3),[[]])
        self.assertEqual([x['condition'] for x in self.guards(scene,4)[0]],['!(global.flag[4])'])

    def test_nonterminal_arm_is_not_promoted_and_flow_guards_stay_quiet(self):
        source=f'if(flag){{if(other)exit;}}{msg(1)}if(con<0)exit;{msg(2)}if(a)exit;else flag=0;{msg(3)}'
        scene,_=self.fixture.analyze(source)
        self.assertEqual(self.guards(scene,1),[[]])
        for key in (2,3):
            guards=self.guards(scene,key)[0]
            self.assertEqual(len(guards),1)
            self.assertFalse(guards[0]['visible'])

    def test_choices_keep_later_entry_checks_after_relocation(self):
        source=self.fixture.array_choice(f'if(global.choice==0){{{msg(10)}}}else{{{msg(11)}}}',count=2).replace('if(con==99','if(global.plot<25)exit;\nif(con==99')
        scene,a=self.fixture.analyze(source)
        self.assertTrue(any(n['type']=='choice' for n in all_nodes(scene['body'])))
        self.assertEqual(self.guards(scene,0),[[]])
        for key in (10,11):self.assertEqual(self.guards(scene,key)[0][0]['condition'],'!(global.plot<25)')
        self.assertEqual(a.analyze(FILE),scene)
