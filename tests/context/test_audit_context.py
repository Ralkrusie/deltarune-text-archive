"""Audit discovery must retain rejected and opaque candidates, not invent links."""
import unittest

from tools.context.audit_context import FileRegistry, identity, summarize, reconcile_calls, compare
from tools.context.context_conditions import backend
from tools.context.context_files import Analyzer, sequence

FILE='gml_Object_obj_audit_Step_0.gml'


def key(i): return f'audit_slash_Step_gml_{i}_0'
def msg(i, text='text'): return f'msgsetloc(0,"{text}","{key(i)}");'
def opt(i): return f'global.choicemsg[{i}]=stringsetloc("option{i}","{key(i)}");'


class ContextAuditTests(unittest.TestCase):
    def registry(self, source, table=None, file=FILE, scene=None, diagnostics=None, chapter=4):
        table=table or {key(i):{'en':'text','zh_default':'示例'} for i in range(20)}
        a=Analyzer({file:source},chapter,table,backend(),strict_bindings=False)
        return FileRegistry(a,file,scene,diagnostics)

    def test_rejected_shared_second_question_is_discovered(self):
        source='function scr_text(arg0){switch(arg0){case 8:'+opt(0)+opt(1)+msg(5,'\\\\C2')+'global.msg[1]=" ";break;case 9:'+msg(6,'\\\\C2')+'break;}}'
        reg=self.registry(source,file='gml_GlobalScript_scr_text.gml',diagnostics={'shared_rejections':{8:'message_after_prompt'}})
        rows=reg.build();menus=[r for r in rows if r['kind']=='choice']
        self.assertEqual(len(menus),2)
        self.assertEqual(menus[0]['family'],'shared_script')
        self.assertEqual(menus[0]['status'],'unconnected')
        self.assertIn('message_after_prompt',menus[0]['reasons'])
        self.assertEqual(menus[0]['observations'],['whitespace_message_slots_after_prompt','next_case_contains_choice_prompt'])

    def test_ch1_control_from_bound_english_table(self):
        source=f'global.msg[0]=scr_84_get_lang_string("{key(7)}");'
        reg=self.registry(source,table={key(7):{'en':' \\C2 '}},chapter=1)
        menus=[r for r in reg.build() if r['kind']=='choice']
        self.assertEqual(len(menus),1)
        self.assertEqual(menus[0]['option_count'],2)

    def test_shared_padding_and_caller_reference_are_registered(self):
        shared='gml_GlobalScript_scr_text.gml'
        source='function scr_text(arg0){switch(arg0){case 8:'+opt(0)+opt(1)+f'global.choicemsg[2]=stringsetloc(" ","{key(2)}");'+msg(5,'\\\\C2')+'break;}}'
        table={key(0):{'en':'option0'},key(1):{'en':'option1'},key(2):{'en':' '},key(5):{'en':'\\C2'}}
        reg=self.registry(source,table=table,file=shared)
        source_rows=reg.build()
        self.assertEqual(len(next(r for r in source_rows if r['kind']=='choice')['option_candidates']),2)
        scene={'body':sequence([{'type':'choice','branches':[{'option':reg.refs[i],'body':sequence([])} for i in (0,1)]}])}
        proof={'rule':'queued_choice_callback','offset':0,'case':8,'script':shared}
        rows=self.registry('c_msc(8);',scene=scene,diagnostics={'rules':[proof]}).build()
        caller=next(r for r in rows if r['kind']=='choice_call')
        self.assertEqual(caller['source']['offset'],0)
        reconcile_calls(source_rows+rows)
        prompt=next(r for r in source_rows if r['kind']=='choice')
        self.assertEqual(prompt['status'],'linked_at_callsite')
        self.assertEqual(caller['source_prompt_ids'],[prompt['id']])
        unmatched=self.registry('c_msc(8);',scene=scene).build()
        gap=next(r for r in unmatched if r['kind']=='projection_gap')
        self.assertEqual(gap['location_precision'],'file_only')

    def test_comments_and_unbound_or_dynamic_controls(self):
        source='// msgset(0,"\\\\C2");\n/* "\\\\C3" */\n' + 'global.msg[0]="\\\\C2";msgnext("\\\\C"+string(n));x="\\\\C1";'
        rows=self.registry(source).build()
        menus=[r for r in rows if r['kind']=='choice']
        self.assertEqual(len(menus),2)
        self.assertEqual(menus[0]['family'],'buffer_literal')
        self.assertEqual(menus[1]['status'],'uncertain')
        self.assertTrue(any(r.get('signal')=='dynamic_message_argument' for r in rows))

    def test_options_are_signals_not_additional_menus(self):
        rows=self.registry(opt(0)+opt(1)).build()
        self.assertEqual([r['kind'] for r in rows],['signal','signal'])

    def test_exact_option_occurrences_required_for_linked_status(self):
        reg=self.registry(opt(0)+opt(1)+msg(5,'\\\\C2')+msg(8))
        refs=reg.refs
        choice={'type':'choice','branches':[{'option':refs[i],'body':sequence([refs[-1]])} for i in (0,1)]}
        scene={'body':sequence([choice])}
        rows=self.registry(reg.source,scene=scene).build()
        menu=next(r for r in rows if r['kind']=='choice')
        self.assertEqual(menu['status'],'linked')
        changed=self.registry(reg.source,chapter=5,scene=scene).build()
        self.assertNotEqual(next(r for r in changed if r['kind']=='choice')['status'],'linked')

    def test_two_prompts_cannot_claim_one_projection(self):
        reg=self.registry(opt(0)+opt(1)+msg(5,'\\\\C2')+msg(6,'\\\\C2'))
        scene={'body':sequence([{'type':'choice','branches':[{'option':reg.refs[i],'body':sequence([])} for i in (0,1)]}])}
        menus=[r for r in self.registry(reg.source,scene=scene).build() if r['kind']=='choice']
        self.assertTrue(all(r['status']=='uncertain' for r in menus))

    def test_condition_text_links_to_its_choice_without_interpreting_flag(self):
        source=opt(0)+opt(1)+msg(5,'\\\\C2')+'if(global.flag[5]){'+msg(8)+'}'
        reg=self.registry(source)
        condition={'type':'condition','branches':[{'label':'global.flag[5]','body':sequence([reg.refs[-1]])},
                    {'label':'!(global.flag[5])','body':sequence([])}]}
        scene={'body':sequence([{'type':'choice','branches':[{'option':reg.refs[0],'body':sequence([condition])},
                    {'option':reg.refs[1],'body':sequence([])}]}])}
        rows=self.registry(source,scene=scene).build()
        choice=next(r for r in rows if r['kind']=='choice')
        flag=next(r for r in rows if r['kind']=='condition')
        self.assertEqual(flag['text_contained_in_choice_ids'],[choice['id']])
        self.assertEqual(flag['meaning'],'unreviewed')

    def test_conditions_keep_independent_occurrences_and_unknown_meaning(self):
        source='if(global.flag[9]==0){'+msg(8)+'}else{'+msg(9)+'}if(global.flag[9]==0){'+msg(8)+'}'
        reg=self.registry(source);scene=reg.a.analyze(FILE)
        rows=self.registry(source,scene=scene).build()
        conditions=[r for r in rows if r['kind']=='condition']
        self.assertEqual(len(conditions),2)
        self.assertNotEqual(conditions[0]['id'],conditions[1]['id'])
        self.assertEqual([r['text_shape'] for r in conditions],['multiple_text_arms','single_text_arm'])
        self.assertTrue(all(r['status']=='represented' and r['meaning']=='unreviewed' for r in conditions))

    def test_switch_and_indirect_calls_are_not_claimed_as_solved(self):
        source='switch(global.choice){case 0:c_msc(12);break;case 1:'+msg(8)+'break;}if(scr_sideb_active())c_msc(10);'
        rows=[r for r in self.registry(source).build() if r['kind']=='condition']
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['reasons'],['switch_cases_not_execution_edges'])
        self.assertEqual(rows[1]['category'],'sideb')
        self.assertEqual(rows[1]['reasons'],['indirect_message_calls_not_expanded'])

    def test_opaque_function_ternary_and_parse_failure_remain_visible(self):
        source='callback=function(){if(global.flag[3]){'+msg(8)+'}};'+msg(7).replace('"text"','(flag?"a":"b")')
        rows=self.registry(source).build()
        reasons=[reason for r in rows if r['kind']=='condition_gap' for reason in r['reasons']]
        self.assertIn('conditional_in_opaque_scope',reasons)
        self.assertIn('ternary_not_projected',reasons)
        broken=self.registry('if(x){'+msg(1,'\\\\C2')).build()
        self.assertTrue(any(r['kind']=='choice' for r in broken))
        self.assertTrue(any('parse_failure' in r.get('reasons',[]) for r in broken))
        unrelated=self.registry('cb=function(){if(x)image_index=0;};'+msg(1)).build()
        self.assertFalse(any(r['kind']=='condition_gap' for r in unrelated))

    def test_projection_without_prompt_is_reported(self):
        reg=self.registry(opt(0)+opt(1))
        scene={'body':sequence([{'type':'choice','branches':[{'option':reg.refs[i],'body':sequence([])} for i in (0,1)]}])}
        rows=self.registry(reg.source,scene=scene).build()
        self.assertEqual(sum(r['kind']=='projection_gap' for r in rows),1)
        summary=summarize(rows,1,{},'context','text')
        self.assertNotIn('choice',summary['statuses'])
        self.assertEqual(summary['statuses']['projection_gap'],{'needs_audit_mapping':1})
        self.assertNotEqual(identity(1,FILE,0,'choice'),identity(2,FILE,0,'choice'))

    def test_diff_keeps_source_rebinding_and_disappearance_distinct(self):
        old=[dict(id='a',status='unconnected',reasons=['blocked'],source_sha256='1'),
             dict(id='b',status='unconnected',reasons=['blocked'],source_sha256='1')]
        new=[dict(id='a',status='linked',reasons=[],source_sha256='2'),
             dict(id='c',status='uncertain',reasons=[],source_sha256='3')]
        delta=compare(old,new)
        self.assertEqual(delta['added'],['c'])
        self.assertEqual(delta['removed'],['b'])
        self.assertTrue(delta['changed'][0]['source_changed'])
        self.assertEqual(delta['changed'][0]['before_status'],'unconnected')
        self.assertEqual(compare(new,new)['changed'],[])


if __name__=='__main__':unittest.main()
