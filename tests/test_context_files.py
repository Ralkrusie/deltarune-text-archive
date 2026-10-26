"""Synthetic fixtures with unrelated state/case numbers: no scene recipes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from context_conditions import backend
from context_files import Analyzer
from context_data import references

FILE='gml_Object_obj_fixture_Step_0.gml'


def msg(i,call='msgsetloc'):
    return f'{call}('+('0,' if 'set' in call else '')+f'"text{i}","fixture_slash_Test_gml_{i}_0");'


def option(i):
    return f'global.choicemsg[{i}]=stringsetloc("text{i}","fixture_slash_Test_gml_{i}_0");'


def all_nodes(node):
    yield node
    for c in node.get('children',[]):yield from all_nodes(c)
    for b in node.get('branches',[]):yield from all_nodes(b['body'])


class ContextFilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api=backend()

    def analyze(self,source,extra=None):
        sources={FILE:source,**(extra or {})}
        table={f'fixture_slash_Test_gml_{i}_0':{'en':f'text{i}'} for i in range(50)}
        analyzer=Analyzer(sources,4,table,self.api)
        scene=analyzer.analyze(FILE)
        return scene,analyzer

    def test_entire_file_keeps_unrelated_blocks_and_repeated_keys(self):
        source=f'if(con==41){{{msg(1)}}} if(con==88){{{msg(2)}{msg(1,"msgnextloc")}}}'
        scene,_=self.analyze(source)
        refs=list(references(scene['body']))
        self.assertEqual(scene['reference_count'],3)
        self.assertEqual(len(scene['body']['children']),2)
        self.assertNotEqual(refs[0]['occurrence_id'],refs[2]['occurrence_id'])

    def test_if_else_common_tail_is_lexically_outside_branches(self):
        scene,_=self.analyze(f'if(con==41){{if(!scr_mode()){{{msg(1)}}}else{{{msg(2)}}}{msg(3,"msgnextloc")}}}')
        children=scene['body']['children'][0]['children']
        self.assertEqual([b['label'] for b in children[0]['branches']],['!scr_mode()','scr_mode()'])
        self.assertEqual(children[1]['key'],'fixture_slash_Test_gml_3_0')

    def test_local_choice_uses_slots_and_state_not_file_or_line_numbers(self):
        source=f'if(con==41){{con=99;{option(0)}{option(1)}{msg(2)}msgnext("\\\\C2");}} if(con==99 && global.choice!=-1){{if(global.choice==0){{{msg(3)}}}if(global.choice==1){{{msg(4)}}}}}'
        scene,analyzer=self.analyze(source)
        choices=[n for n in all_nodes(scene['body']) if n['type']=='choice']
        self.assertEqual(len(choices),1)
        self.assertEqual(len(scene['body']['children']),1)
        self.assertEqual(scene['reference_count'],5)
        self.assertEqual([b['option']['key'] for b in choices[0]['branches']],['fixture_slash_Test_gml_0_0','fixture_slash_Test_gml_1_0'])
        # A later mutation could make both independent if blocks run; do not map it.
        changed=source.replace('if(global.choice==1)','global.choice=1; if(global.choice==1)')
        _,analyzer=self.analyze(changed)
        self.assertEqual(analyzer.evidence,[])

    def shared_sources(self):
        return {
            'gml_GlobalScript_scr_text.gml':f'function scr_text(arg0){{switch(arg0){{case 77:{option(0)}{option(1)}msgset(0,"\\\\C2");break;case 78:with(obj_fixture) choose_path(global.choice);break;}}}}',
            'gml_Object_obj_fixture_Create_0.gml':'choose_path=function(answer){if(answer==0) con=81; else con=92;};',
            'gml_Object_obj_choicer_neo_Alarm_0.gml':'global.msc += 1; scr_text(global.msc);',
            'gml_Object_obj_choicer_neo_Other_10.gml':'global.choice = mychoice;',
            'gml_GlobalScript_scr_cutscene_commands.gml':'global.msc = command_arg1[i]; scr_text(global.msc);',
            'gml_GlobalScript_c_msc.gml':'function c_msc(arg0){ c_cmd("msc",arg0,0,0,0); }'}

    def test_shared_callback_resolves_arbitrary_case_method_and_states(self):
        source=f'if(con==61){{{msg(2,"c_msgsetloc")}c_msc(77);}} if(con==81){{{msg(3)}}} if(con==92){{{msg(4)}}}'
        scene,analyzer=self.analyze(source,self.shared_sources())
        self.assertEqual(len(analyzer.evidence),1)
        self.assertEqual(scene['reference_count'],3)
        self.assertEqual(len(list(references(scene['body']))),5)
        self.assertEqual(len(scene['body']['children']),1)

    def test_missing_protocol_or_ambiguous_state_keeps_full_inventory(self):
        source=f'if(con==61){{{msg(2,"c_msgsetloc")}c_msc(77);}} if(con==81){{{msg(3)}}} if(con==92){{{msg(4)}}}'
        extra=self.shared_sources();extra['gml_Object_obj_choicer_neo_Alarm_0.gml']='scr_text(dynamic_id);'
        scene,analyzer=self.analyze(source,extra)
        self.assertEqual(scene['reference_count'],3);self.assertEqual(analyzer.evidence,[])
        scene,analyzer=self.analyze(source+f'if(con==81){{{msg(5)}}}',self.shared_sources())
        self.assertEqual(scene['reference_count'],4);self.assertEqual(analyzer.evidence,[])

    def test_parse_failure_preserves_every_reference_without_connections(self):
        scene,analyzer=self.analyze('if(unclosed){'+msg(1)+msg(2))
        self.assertEqual(scene['reference_count'],2)
        self.assertEqual(len(scene['body']['children']),2)
        self.assertEqual(analyzer.diagnostics[0]['reason'],'parse_error')

    def test_comments_and_string_lookalikes_do_not_expand_inventory(self):
        scene,_=self.analyze('// '+msg(1)+'\nx="msgsetloc(0,fake,key)";'+msg(2))
        self.assertEqual(scene['reference_count'],1)

    def test_conditional_dialogue_continuation_stays_in_the_entered_branch(self):
        source=f'if(con==31){{if(global.flag[8]){{con=72;{msg(1)}{msg(2,"msgnextloc")}d_make();}}}} if(con==72 && !d_ex()){{con=90;{msg(3)}d_make();}}'
        scene,analyzer=self.analyze(source)
        self.assertEqual(len(scene['body']['children']),1)
        condition=scene['body']['children'][0]['children'][0]
        self.assertEqual([r['key'] for r in references(condition['branches'][0]['body'])],
                         [f'fixture_slash_Test_gml_{i}_0' for i in (1,2,3)])
        self.assertEqual(list(references(condition['branches'][1]['body'])),[])
        self.assertEqual(analyzer.evidence[-1]['rule'],'branch_dialogue_continuation')
        self.assertEqual(scene['reference_count'],3)

    def test_else_continuation_is_not_attached_to_true_branch(self):
        source=f'if(con==31){{if(flag){{{msg(1)}d_make();}}else{{con=72;{msg(2)}d_make();}}}} if(con==72 && !d_ex()){{{msg(3)}d_make();}}'
        scene,_=self.analyze(source)
        condition=scene['body']['children'][0]['children'][0]
        self.assertEqual([len(list(references(b['body']))) for b in condition['branches']],[1,2])

    def test_ambiguous_or_overwritten_continuation_does_not_move_text(self):
        source=f'if(con==31){{if(flag){{con=72;{msg(1)}d_make();}}}} if(con==72 && !d_ex()){{{msg(2)}d_make();}}'
        variants=[source+'if(other) con=72;',
                  source.replace('con=72;','con=72;con=80;'),
                  source.replace('con=72;','with(other) con=72;'),
                  source.replace('!d_ex()','!d_ex() && global.flag[9]'),
                  source.replace('con=72;','con=72;reset_state();'),
                  source.replace('con=72;','con=72;return;'),
                  source+'con=dynamic_state;',source+'++con;',
                  source.replace('d_make();}}', 'd_make();} con=80;}',1)]
        for variant in variants:
            with self.subTest(source=variant):
                scene,analyzer=self.analyze(variant)
                self.assertFalse(any(e['rule']=='branch_dialogue_continuation' for e in analyzer.evidence))
                self.assertEqual(scene['reference_count'],2)

    def test_backward_dialogue_state_does_not_form_recursive_tree(self):
        source=f'if(con==72 && !d_ex()){{{msg(2)}d_make();}} if(con==31){{if(flag){{con=72;{msg(1)}d_make();}}}}'
        scene,analyzer=self.analyze(source)
        self.assertEqual(analyzer.evidence,[])
        self.assertEqual(scene['reference_count'],2)

    def test_all_mode_preserves_missing_and_conflicting_literals(self):
        source=msg(1)+msg(2)+msg(3)
        table={'fixture_slash_Test_gml_1_0':{'en':'text1'},'fixture_slash_Test_gml_2_0':{'en':'changed'}}
        analyzer=Analyzer({FILE:source},4,table,self.api,strict_bindings=False)
        scene=analyzer.analyze(FILE);refs=list(references(scene['body']))
        self.assertEqual([r.get('binding','matched') for r in refs],['matched','source_literal_differs','missing_key'])
        self.assertEqual(refs[1]['source_english'],'text2');self.assertEqual(refs[2]['source_english'],'text3')

    def test_analyzing_multiple_files_does_not_leak_prior_continuations(self):
        first=f'if(con==31){{if(flag){{con=72;{msg(1)}d_make();}}}} if(con==72 && !d_ex()){{{msg(2)}d_make();}}'
        table={f'fixture_slash_Test_gml_{i}_0':{'en':f'text{i}'} for i in (1,2,3)}
        analyzer=Analyzer({FILE:first,'gml_second.gml':msg(3)},4,table,self.api)
        analyzer.analyze(FILE);self.assertTrue(analyzer.continuations)
        second=analyzer.analyze('gml_second.gml');self.assertEqual(analyzer.continuations,{})
        self.assertEqual(second['reference_count'],1)

    def test_stage_else_keeps_its_condition_instead_of_becoming_orphan_text(self):
        scene,_=self.analyze(f'if(con==3){{{msg(1)}}}else{{{msg(2)}}}')
        condition=scene['body']['children'][0]['children'][0]
        self.assertEqual(condition['type'],'condition')
        self.assertEqual([b['label'] for b in condition['branches']],['con==3','!(con==3)'])
        self.assertEqual([len(list(references(b['body']))) for b in condition['branches']],[1,1])

if __name__=='__main__':unittest.main()
