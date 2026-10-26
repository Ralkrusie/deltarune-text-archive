"""Synthetic only: conditions are containment evidence, never invented CFG edges."""
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from context_conditions import analyze, backend, render



class ConditionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api=backend()

    def read(self,source,ch=2):
        return analyze(source,ch,f'data/exported/code/ch{ch}/fixture.gml',hashlib.sha256(source.encode()).hexdigest(),{},self.api)

    def test_nested_then_else_preserve_full_predicates(self):
        b=self.read('if (global.flag[2] >= 1 && value != 0) { if (mode == 2) msgsetloc(0,"a","f_slash_a_gml_1_0"); else msgsetloc(0,"b","f_slash_a_gml_2_0"); } else msgsetloc(0,"c","f_slash_a_gml_3_0");')
        r=b['references']
        self.assertEqual([g['branch'] for g in r[1]['guards']],['then','else'])
        self.assertEqual(r[0]['guards'][0]['expression'],'global.flag[2] >= 1 && value != 0')
        self.assertEqual(r[2]['guards'][0]['branch'],'else')
        self.assertEqual(b['edges'],[])

    def test_independent_if_not_else_if_or_dialogue_order(self):
        b=self.read('if (x==1) msgsetloc(0,"a","f_slash_a_gml_1_0"); if (x>=1) msgsetloc(0,"b","f_slash_a_gml_2_0");')
        self.assertEqual(len(b['blocks']),2)
        self.assertTrue(all(len(r['guards'])==1 for r in b['references']))
        self.assertEqual(b['execution_order'],'unproven')

    def test_comments_and_string_lookalikes_not_references(self):
        b=self.read('// msgsetloc(0,"fake","f_slash_a_gml_1_0");\nx="if (fake)"; msgsetloc(0,"real","f_slash_a_gml_2_0");')
        self.assertEqual(len(b['references']),1)
        self.assertEqual(b['references'][0]['line'],2)

    def test_same_key_keeps_occurrence_and_chapter_identity(self):
        s='msgsetloc(0,"a","f_slash_a_gml_1_0"); msgsetloc(0,"a","f_slash_a_gml_1_0");'
        a=self.read(s);b=self.read(s,3)
        self.assertNotEqual(a['references'][0]['occurrence_id'],a['references'][1]['occurrence_id'])
        self.assertNotEqual(a['references'][0]['occurrence_id'],b['references'][0]['occurrence_id'])

    def test_ch1_key_only_and_non_display_reference(self):
        b=self.read('if (x) itemname=scr_84_get_lang_string("f_slash_a_gml_1_0");',1)
        self.assertEqual(b['references'][0]['source_english'],None)
        self.assertEqual(b['references'][0]['usage'],'reference_only_not_proven_display')

    def test_switch_fallthrough_and_loop_remain_unresolved(self):
        b=self.read('switch(x){case 1: x=2; case 2: msgsetloc(0,"a","f_slash_a_gml_1_0"); break;} while(y){msgsetloc(0,"b","f_slash_a_gml_2_0");}')
        self.assertEqual(b['references'][0]['guards'],[])
        self.assertIn('switch_fallthrough_not_solved',[d['reason'] for d in b['diagnostics']])
        self.assertIn('while_scope_not_executed',[d['reason'] for d in b['diagnostics']])

    def test_parse_failure_keeps_inventory(self):
        b=self.read('if (x) { msgsetloc(0,"a","f_slash_a_gml_1_0");')
        self.assertEqual(len(b['references']),1)
        self.assertIsNone(b['references'][0]['node_id'])
        self.assertEqual(b['diagnostics'][0]['reason'],'parse_error')

    def test_mutation_return_and_dynamic_call_do_not_create_join(self):
        b=self.read('if (x==1){x=2; scr_text(dynamic_id); return;} if (x==2) msgsetloc(0,"b","f_slash_a_gml_2_0");')
        self.assertEqual(len(b['references'][0]['guards']),1)
        self.assertEqual(b['edges'],[])
        self.assertEqual(b['blocks'][0]['children'][0]['children'][0]['assignment'],['x','2'])

    def test_html_escapes_source_and_translation(self):
        b=self.read('if (x < 2) msgsetloc(0,"<script>bad</script>","f_slash_a_gml_1_0");')
        page=render(b)
        self.assertNotIn('<script>',page)
        self.assertIn('&lt;script&gt;',page)


if __name__=='__main__':unittest.main()
