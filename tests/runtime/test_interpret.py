import copy
import unittest
from tools.runtime.interpret import interpret


class InterpretTests(unittest.TestCase):
    def body(self, text='Shut up!!'):
        return dict(text=text,occurrence_id='source',identity={'candidates':['queen'],'states':[{'face_code':21}]},
                    assets=[],coverage={'page_closed':True},smallfaces=[])

    def test_stale_face_does_not_assign_a_bubble(self):
        body=self.body();old=copy.deepcopy(body);result=interpret(body)
        self.assertEqual(result['candidates'],[])
        self.assertEqual(result['raw_candidates'],['queen'])
        self.assertTrue(result['suppressed']);self.assertEqual(old,body)

    def test_portrait_required_for_positive_states(self):
        body=self.body();body['assets']=[{'role':'portrait','face_code':21}]
        self.assertEqual(interpret(body)['candidates'],['queen'])
        body['identity']['states'].append({'face_code':1})
        self.assertEqual(interpret(body)['candidates'],[])

    def test_control_pages_do_not_hide_children(self):
        body=self.body('\\f0 \\f1\\f2/%');body['smallfaces']=[{'text':'Happy Birthday!'}]
        self.assertEqual(interpret(body)['kind'],'child_container')
        for text in ('%%','\\C2 ','\\TX \\F0 \\E2 \\FR \\TR %'):
            self.assertEqual(interpret(self.body(text))['kind'],'control')
        self.assertEqual(interpret(self.body('100% good'))['kind'],'text')
