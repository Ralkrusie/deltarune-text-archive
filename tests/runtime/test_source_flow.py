import unittest
from tools.runtime.compiler.instrument import transform


class SourceFlowTests(unittest.TestCase):
    def run_transform(self, text):
        return transform(text,'gml_Object_enemy_Step_0.gml','a'*64,1)

    def test_branch_selected_source_and_single_evaluation(self):
        text='{ var words = (total == 1) ? stringsetloc("A", "key_a") : stringsetloc("B", "key_b"); scr_other(); msgset(0, words); }'
        output,rows,_=self.run_transform(text)
        self.assertEqual([r['key'] for r in rows],['key_a','key_b'])
        self.assertEqual(output.count('stringsetloc('),2)
        self.assertIn('cap_local_msgset(0, words, cap_tag_',output)
        self.assertIn('cap_local_value(cap_tag_',output)

    def test_same_text_overwrite_is_not_inferred(self):
        for write in ('words = words;', 'words += "";', 'var words = "A";'):
            output,rows,_=self.run_transform('{var words = stringsetloc("A", "key_a"); '+write+'msgset(0, words);}')
            self.assertFalse(rows)
            self.assertNotIn('cap_local_msgset',output)

    def test_unsupported_expression_and_outside_block_stay_unknown(self):
        for text in ('{ var words = stringsetloc("A", "key_a") + "B"; msgset(0, words); }',
                     '{ var words = stringsetloc("A", "key_a"); } msgset(0, words);'):
            output,rows,_=self.run_transform(text)
            self.assertFalse(rows)
            self.assertNotIn('cap_local_msgset',output)

    def test_template_return_is_captured_before_intervening_calls(self):
        output,rows,_=self.run_transform('{var words = scr_itemget_anytype_text(item, kind); msgsetloc(0,"First","first_key"); msgnext(words);}')
        self.assertIn('cap_local_itemget(cap_tag_',output)
        self.assertIn('cap_local_msgnext(words, cap_tag_',output)
        self.assertEqual(len(rows),1)

    def test_unbraced_condition_does_not_change_execution(self):
        text='if (ready) var words = stringsetloc("A", "key_a"); msgset(0, words);'
        output,rows,_=self.run_transform(text)
        self.assertEqual(output,text)
        self.assertFalse(rows)
