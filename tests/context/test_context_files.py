"""Synthetic fixtures with unrelated state/case numbers: no scene recipes."""
from pathlib import Path
import sys
import unittest

from tools.context.context_conditions import backend
from tools.context.context_files import Analyzer
from tools.context.context_data import references

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

    def test_local_choice_joins_common_suffix_once(self):
        response=f'if(global.choice==0){{{msg(10)}}}else{{{msg(11)}}}{msg(12,"msgnextloc")}d_make();'
        for variable in ('con','myinteract'):
            scene,analyzer=self.analyze(self.array_choice(response,count=2).replace('con',variable))
            choice=next(n for n in all_nodes(scene['body']) if n['type']=='choice')
            self.assertTrue(choice['join_next'])
            self.assertEqual([[r['key'] for r in references(b['body'])] for b in choice['branches']],
                             [[f'fixture_slash_Test_gml_{i}_0'] for i in (10,11)])
            refs=list(references(scene['body']))
            self.assertEqual(sum(r['key']=='fixture_slash_Test_gml_12_0' for r in refs),1)
            self.assertEqual(scene['reference_count'],7)
            self.assertIn('common_tail_line',analyzer.evidence[-1])

    def test_raw_choice_join_keeps_same_text_in_distinct_arms(self):
        source=f'if(con==21){{if(global.choice==0){{{msg(1)}}}else{{{msg(1)}}}{msg(2)}}}'
        scene,analyzer=self.analyze(source)
        children=scene['body']['children'][0]['children']
        self.assertTrue(children[0]['join_next'])
        self.assertEqual(children[1]['key'],'fixture_slash_Test_gml_2_0')
        refs=list(references(scene['body']))
        self.assertEqual([r['key'] for r in refs],[f'fixture_slash_Test_gml_{i}_0' for i in (1,1,2)])
        self.assertEqual(len({r['occurrence_id'] for r in refs}),3)
        self.assertEqual(analyzer.evidence[-1]['rule'],'choice_common_tail')

    def test_unknown_call_before_response_does_not_link_menu(self):
        response=f'opaque_callback();if(global.choice==0){{{msg(10)}}}else{{{msg(11)}}}{msg(12,"msgnextloc")}'
        scene,_=self.analyze(self.array_choice(response,count=2))
        self.assertFalse(any(n['type']=='choice' for n in all_nodes(scene['body'])))
        # The lexical if/else still falls through to its suffix, but an opaque
        # call before it may change which answer is being consumed.
        self.assertTrue(any(n.get('join_next') for n in all_nodes(scene['body'])))
        self.assertEqual(scene['reference_count'],7)

    def test_common_join_rejects_exits_opaque_calls_and_next_menu(self):
        branch=f'if(global.choice==0){{{msg(10)}}}else{{{msg(11)}}}'
        suffix=msg(12,'msgnextloc')
        variants=[
            branch.replace(msg(10),msg(10)+'exit;')+suffix,
            branch.replace(msg(10),'if(flag)return;'+msg(10))+suffix,
            branch.replace(msg(10),'opaque_callback();'+msg(10))+suffix,
            branch.replace(msg(10),'global.choice=1;'+msg(10))+suffix,
            branch.replace(msg(10),'while(flag){'+msg(10)+'}')+suffix,
            branch+'opaque_callback();'+suffix,
            branch+'if(other){'+suffix+'}',
            branch+option(0)+suffix+'msgnext("\\\\C2");',
            branch+suffix+'global.choice=-1;msgnext("\\\\C2");',
            branch+'var shared='+suffix,
        ]
        for variant in variants:
            with self.subTest(source=variant):
                scene,analyzer=self.analyze(self.array_choice(variant,count=2))
                self.assertFalse(any(n.get('join_next') for n in all_nodes(scene['body'])))
                self.assertEqual(scene['reference_count'],len(analyzer.file(FILE)['refs']))

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

    def array_choice(self,consumer=None,count=4):
        options=','.join(f'stringsetloc("text{i}","fixture_slash_Test_gml_{i}_0")' for i in range(count))
        if count==2:options+=',stringset(""),stringset("")'
        if consumer is None:
            consumer=f'if(global.choice==0){{if(scr_flag_get(123)==0){{{msg(10)}}}else{{{msg(11)}}}}}else if(global.choice==1){{{msg(12)}}}else if(global.choice==2){{{msg(13)}}}'
        return f'if(con==41){{con=99;global.choice=-1;global.choicemsg=[{options}];if(times==0){{{msg(8)}}}else{{{msg(9)}}}msgnext("\\\\C{count}");}}if(con==99 && global.choice!=-1){{con=100;{consumer}}}'

    def test_array_four_options_elseif_flags_and_unhandled_option(self):
        scene,analyzer=self.analyze(self.array_choice())
        choices=[n for n in all_nodes(scene['body']) if n['type']=='choice']
        self.assertEqual(len(choices),1)
        branches=choices[0]['branches']
        self.assertEqual(len(branches),4)
        self.assertEqual([[r['key'] for r in references(b['body'])] for b in branches],
                         [[f'fixture_slash_Test_gml_{i}_0' for i in ids] for ids in ((10,11),(12,),(13,),())])
        self.assertEqual(branches[0]['body']['children'][0]['branches'][0]['label'],'scr_flag_get(123)==0')
        self.assertEqual(branches[3]['body']['children'],[])
        self.assertEqual(analyzer.evidence[0]['empty_options'],[3])
        self.assertEqual(scene['reference_count'],10)
        self.assertEqual(len(scene['body']['children']),1)

    def test_two_visible_array_options_ignore_empty_padding_and_accept_single_else(self):
        scene,_=self.analyze(self.array_choice(f'if(global.choice==0){{{msg(10)}}}else{{{msg(11)}}}',count=2))
        choice=next(n for n in all_nodes(scene['body']) if n['type']=='choice')
        self.assertEqual(len(choice['branches']),2)
        self.assertEqual([r['key'] for r in references(choice['branches'][1]['body'])],['fixture_slash_Test_gml_11_0'])

    def test_choice_revisit_requires_local_write_and_verified_helpers(self):
        helpers={
            'gml_GlobalScript_scr_flag_get.gml':'function scr_flag_get(arg0){return global.flag[arg0];}',
            'gml_GlobalScript_scr_flag_set.gml':'function scr_flag_set(arg0,arg1){global.flag[arg0]=arg1;}'}
        source=self.array_choice().replace(msg(10),'scr_flag_set(123,1);'+msg(10))
        scene,analyzer=self.analyze(source,helpers)
        revisits=[n for n in all_nodes(scene['body']) if 'revisit' in n]
        self.assertEqual(len(revisits),1)
        self.assertEqual(revisits[0]['revisit']['flag'],123)
        self.assertEqual([len(list(references(b['body']))) for b in revisits[0]['branches']],[1,1])
        self.assertEqual(scene['reference_count'],10)
        self.assertEqual(sum(e['rule']=='choice_flag_revisit' for e in analyzer.evidence),1)
        variants=[
            source.replace('scr_flag_set(123,1);',''),
            source.replace('scr_flag_set(123,1);','scr_flag_set(124,1);'),
            source.replace('scr_flag_set(123,1);','if(other) scr_flag_set(123,1);'),
            source.replace(msg(11),'scr_flag_set(123,0);'+msg(11)),
            source.replace(msg(11),'opaque_callback();'+msg(11)),
            source+'scr_flag_set(123,0);',
            source+'scr_flag_set(dynamic_flag,0);',
            source+'global.flag[123]=0;',
            source.replace('scr_flag_get(123)==0','scr_flag_get(123)==0 && other'),
        ]
        for variant in variants:
            with self.subTest(source=variant):
                changed,_=self.analyze(variant,helpers)
                self.assertFalse(any('revisit' in n for n in all_nodes(changed['body'])))
                self.assertEqual(changed['reference_count'],10)
        for changed_helpers in ({},{**helpers,'gml_GlobalScript_scr_flag_set.gml':'function scr_flag_set(arg0,arg1){global.other[arg0]=arg1;}'}):
            changed,_=self.analyze(source,changed_helpers)
            self.assertFalse(any('revisit' in n for n in all_nodes(changed['body'])))
        # A standalone flag conditional is not known to be a repeated choice.
        standalone=f'if(scr_flag_get(123)==0){{scr_flag_set(123,1);{msg(10)}}}else{{{msg(11)}}}'
        changed,_=self.analyze(standalone,helpers)
        self.assertFalse(any('revisit' in n for n in all_nodes(changed['body'])))

    def test_scoped_state_names_keep_owner_and_condition_boundaries(self):
        for variable in ('myinteract','talk_con','gcon','dialog_phase'):
            with self.subTest(variable=variable):
                source=self.array_choice().replace('con',variable)
                source=f'if(!scr_sideb_active()){{with(npc){{{source}}}}}'
                scene,analyzer=self.analyze(source)
                choices=[n for n in all_nodes(scene['body']) if n['type']=='choice']
                self.assertEqual(len(choices),1)
                self.assertEqual(scene['reference_count'],10)
                rule=analyzer.evidence[-1]
                self.assertEqual(rule['rule'],'scoped_choice_slots_to_state')
                self.assertEqual(rule['state_variable'],variable)
                self.assertEqual((rule['from_state'],rule['to_state']),(41,99))
                self.assertEqual([(s['kind'],s['expression']) for s in rule['scope']],
                                 [('if','!scr_sideb_active()'),('with','npc')])
                self.assertEqual(scene['body']['children'][0]['children'][0]['branches'][0]['label'],'!scr_sideb_active()')

    def test_identical_state_numbers_in_two_with_scopes_are_independent(self):
        source=self.array_choice().replace('con','myinteract')
        scene,analyzer=self.analyze(f'with(npc){{{source}}}with(npc2){{{source}}}')
        self.assertEqual(len([n for n in all_nodes(scene['body']) if n['type']=='choice']),2)
        self.assertEqual(scene['reference_count'],20)
        self.assertEqual([e['scope'][0]['expression'] for e in analyzer.evidence],['npc','npc2'])
        self.assertEqual(len({r['occurrence_id'] for r in references(scene['body'])}),20)

    def test_scoped_choice_rejects_cross_scope_and_ambiguous_writes(self):
        source=self.array_choice().replace('con','myinteract')
        producer,consumer=source.split('if(myinteract==99',1)
        consumer='if(myinteract==99'+consumer
        variants=[
            f'with(npc){{{producer}}}with(npc2){{{consumer}}}',
            f'with(npc){{{producer}}}with(npc){{{consumer}}}',
            f'if(flag){{{producer}}}else{{{consumer}}}',
            f'repeat(2){{{source}}}',
            f'with(targets[i]){{{source}}}',
            f'function callback(){{{source}}}',
            source+'if(other)myinteract=99;',
            source+'myinteract=dynamic_state;',
            source+'self.myinteract=1;',
            source+'var myinteract=0;',
            source+'scr_delay_var("myinteract",99,1);',
            producer+'global.choice=-1;'+consumer,
            source.replace('myinteract==41','myinteract==41 || other'),
            source.replace('myinteract=99;','if(flag) return;myinteract=99;'),
            f'var myinteract=0;with(npc){{{source}}}',
            f'var other=0,myinteract=0;with(npc){{{source}}}',
            source.replace('global.choice=-1;',''),
            source.replace('global.choice=-1;','global.choice=-1;global.choice=0;'),
            source.replace('global.choice=-1;','global.choice=-1;if(previous!=-1)global.choice=previous;'),
        ]
        for variant in variants:
            with self.subTest(source=variant):
                scene,analyzer=self.analyze(variant)
                self.assertFalse(any(e['rule']=='scoped_choice_slots_to_state' for e in analyzer.evidence))
                self.assertEqual(scene['reference_count'],10)

    def test_top_level_state_choice_keeps_extra_guard_and_resets_between_files(self):
        source=self.array_choice().replace('con','talk_con').replace('talk_con==41','talk_con==41 && global.flag[8]')
        scene,analyzer=self.analyze(source)
        self.assertEqual(len([n for n in all_nodes(scene['body']) if n['type']=='choice']),1)
        self.assertTrue(any(n.get('guard')=='global.flag[8]' for n in all_nodes(scene['body'])))
        second=analyzer.analyze(FILE)
        self.assertEqual(second,scene)
        analyzer.sources['gml_second.gml']=msg(20)
        self.assertEqual(analyzer.analyze('gml_second.gml')['reference_count'],1)
        self.assertEqual(analyzer.scoped_choices,{})
        self.assertEqual(analyzer.scoped_consumed,set())

    def test_indexed_empty_padding_and_nontext_scopes_remain_supported(self):
        source=f'if(con==41){{con=99;{option(0)}{option(1)}global.choicemsg[2]=stringset("");global.choicemsg[3]=stringset("");{msg(2)}msgnext("\\\\C2");}}if(con==99 && global.choice!=-1){{with(obj_writer) instance_destroy();if(global.choice==0){{{msg(3)}}}if(global.choice==1){{{msg(4)}}}with(bw_make()) skip=true;}}'
        scene,_=self.analyze(source)
        self.assertEqual(len([n for n in all_nodes(scene['body']) if n['type']=='choice']),1)

    def test_state_only_response_stays_empty_instead_of_claiming_dialogue_end(self):
        scene,_=self.analyze(self.array_choice('if(global.choice==0) con=123;',count=2))
        choice=next(n for n in all_nodes(scene['body']) if n['type']=='choice')
        for b in choice['branches']:
            self.assertEqual(b['body']['children'],[])

    def test_ambiguous_array_responses_preserve_inventory_without_choice(self):
        source=self.array_choice()
        variants=[
            source.replace('else if(global.choice==1)','else if(global.choice==0)'),
            source.replace('else if(global.choice==2)','else if(global.choice==7)'),
            self.array_choice(f'if(global.choice==0){{{msg(10)}}}else{{{msg(11)}}}'),
            source.replace('con=100;',f'con=100;{msg(14)}'),
            source.replace('con=100;','con=100;exit;'),
            source.replace('con=100;','con=100;++global.choice;'),
            source.replace('con=100;','con=100;global.choice*=2;'),
            source+'if(other) con=99;',
            source.replace('msgnext("\\\\C4");','// msgnext("\\\\C4");\n'),
            source.replace('msgnext("\\\\C4");',f'msgnext("\\\\C4");{msg(15)}'),
            source.replace('if(times==0)',f'if(other){{{option(0)}}}if(times==0)'),
            source.replace('if(times==0)',option(0)+'if(times==0)'),
            source.replace('stringsetloc("text0","fixture_slash_Test_gml_0_0")','prefix+stringsetloc("text0","fixture_slash_Test_gml_0_0")'),
        ]
        for variant in variants:
            with self.subTest(source=variant):
                scene,analyzer=self.analyze(variant)
                self.assertFalse(any(n['type']=='choice' for n in all_nodes(scene['body'])))
                self.assertEqual(scene['reference_count'],len(analyzer.file(FILE)['refs']))

    def test_array_comma_inside_label_keeps_slot_alignment(self):
        source=self.array_choice().replace('"text0"','"text,0"')
        table={f'fixture_slash_Test_gml_{i}_0':{'en':'text,0' if i==0 else f'text{i}'} for i in range(50)}
        analyzer=Analyzer({FILE:source},4,table,self.api)
        scene=analyzer.analyze(FILE)
        choice=next(n for n in all_nodes(scene['body']) if n['type']=='choice')
        self.assertEqual([b['option']['key'] for b in choice['branches']], [f'fixture_slash_Test_gml_{i}_0' for i in range(4)])

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
