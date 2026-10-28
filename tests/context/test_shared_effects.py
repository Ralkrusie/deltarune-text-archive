"""Sequential answer tests must not become exclusive through an opaque call."""
import unittest
from tools.context.context_data import references
from tools.context.context_files import Analyzer
from tools.context.context_conditions import backend
from tests.context.test_context_files import all_nodes
from tests.context.test_shared_cases import FILE,TEXTS,key
from tests.context import test_shared_cases as shared_fixtures


class IndependentSharedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.api=backend()

    def sources(self,ch=2):
        s=shared_fixtures.SharedCaseTests().sources(ch)
        s[FILE]=s[FILE].replace('scr_itemget(3);','global.flag[82]=1;scr_speaker("fixture");').replace('else{global.msg[0]=','if(global.choice==1){global.msg[0]=')
        helpers={
            'stringset':'function stringset(arg0){return arg0;}',
            'is_english':'function is_english(){return !variable_global_exists("lang")||global.lang=="en";}',
            'stringsetloc':'function stringsetloc(arg0,arg1){var str=arg0;if(!is_english())str=scr_84_get_lang_string(arg1);return stringset(str);}',
            'scr_84_get_lang_string':'function scr_84_get_lang_string(arg0){return ds_map_find_value(global.lang_map,arg0);}',
            'scr_speaker':'function scr_speaker(arg0){_speaker=arg0;global.fc=0;global.fe=0;if(global.darkzone==1)global.typer=6;else global.typer=5;}',
            'scr_lanface':f'function scr_lanface(arg0){{global.msg[arg0]=scr_84_get_lang_string("{key(8)}");}}',
            'msgset':'function msgset(arg0,arg1){global.msgno=arg0;global.msg[arg0]=arg1;}',
            'msgnext':'function msgnext(arg0){global.msgno++;msgset(global.msgno,arg0);}',
            'msgsetloc':'function msgsetloc(arg0,arg1,arg2){var msg_index=arg0;var str=arg1;var localized_string_id=arg2;if(!is_english())str=scr_84_get_lang_string(localized_string_id);msgset(msg_index,str);}',
            'msgnextloc':'function msgnextloc(arg0,arg1){var str=arg0;var localized_string_id=arg1;if(!is_english())str=scr_84_get_lang_string(localized_string_id);msgnext(str);}',
        }
        s.update({'gml_GlobalScript_'+name+'.gml':code for name,code in helpers.items()})
        return s

    def analyze(self,s,ch=2):
        a=Analyzer(s,ch,{key(i):{'en':text} for i,text in TEXTS.items()},self.api)
        scene=a.analyze(FILE)
        self.assertEqual(sorted(r['occurrence_id'] for r in references(scene['body'])),
                         sorted(r['occurrence_id'] for r in a.file(FILE)['refs']))
        return a,scene,[n for n in all_nodes(scene['body']) if n['type']=='choice']

    def test_chapter_bound_helpers_and_independent_answers(self):
        for ch in range(1,6):
            a,scene,choices=self.analyze(self.sources(ch),ch)
            self.assertEqual(len(choices),1)
            self.assertEqual([[r['key'] for r in references(b['body'])] for b in choices[0]['branches']],[[key(4)],[key(5)]])
            e=next(e for e in a.evidence if e['rule']=='shared_case_choice')
            self.assertEqual(e['response_form'],'independent_equality')
            for h in e['effect_helpers']:self.assertEqual(h['sha256'],a.file(h['file'])['hash'])
            names={h['file'] for h in e['effect_helpers']}
            self.assertIn('gml_GlobalScript_scr_speaker.gml',names)
            self.assertEqual('gml_GlobalScript_stringsetloc.gml' in names,ch!=1)
            self.assertEqual(a.analyze(FILE),scene)

    def test_three_options_reversed_guard_order(self):
        s=self.sources(1)
        s[FILE]=s[FILE].replace(f'global.choicemsg[2]=scr_84_get_lang_string("{key(6)}");',f'global.choicemsg[2]=scr_84_get_lang_string("{key(9)}");')
        s[FILE]=s[FILE].replace('case 774:','case 774:if(global.choice==2){global.msg[0]=scr_84_get_lang_string("'+key(12)+'");}')
        table={key(i):{'en':text} for i,text in TEXTS.items()};table[key(3)]['en']='\\C3 '
        a=Analyzer(s,1,table,self.api);scene=a.analyze(FILE)
        c=next(n for n in all_nodes(scene['body']) if n['type']=='choice')
        self.assertEqual([[r['key'] for r in references(b['body'])] for b in c['branches']],[[key(4)],[key(5)],[key(12)]])

    def test_bounded_message_helper_is_checked_not_expanded(self):
        s=self.sources(1);s[FILE]=s[FILE].replace('global.flag[82]=1;','scr_lanface(3);global.flag[82]=1;')
        a,scene,choices=self.analyze(s,1)
        self.assertEqual(len(choices),1)
        self.assertNotIn(key(8),[r['key'] for r in references(scene['body'])])
        self.assertIn('gml_GlobalScript_scr_lanface.gml',[r['file'] for r in a.evidence[0]['effect_helpers']])

    def test_indirect_and_cross_object_execution_stays_unconnected(self):
        for code in ('opaque();','event_user(0);','script_execute(callback);','with(obj_other)con=4;',
                     'obj_other.con=4;','instance_create(0,0,obj_other);','while(ready)con=4;',
                     'obj_other.stringsetloc("x","y");','var scr_speaker=callback;'):
            s=self.sources();s[FILE]=s[FILE].replace('global.flag[82]=1;',code)
            self.assertFalse(self.analyze(s)[2],code)

    def test_writes_and_nested_argument_effects_stay_unconnected(self):
        for code in ('global.choice%=2;','global.choice|=2;','global.choice<<=1;',
                     'choice=1;','choicemsg=other_options;','msc=77;',
                     '++global.choice;','global.choice[0]=1;','variable_global_set("choice",1);',
                     'global.flag[82]=opaque();','global.flag[82]=(global.choice=1);',
                     'global.flag[opaque()]=1;','scr_speaker(opaque());','scr_speaker((callback)());'):
            s=self.sources();s[FILE]=s[FILE].replace('global.flag[82]=1;',code)
            self.assertFalse(self.analyze(s)[2],code)

    def test_helper_or_transitive_dependency_changes_invalidate_the_link(self):
        for name,extra in (('scr_speaker','global.choice=1;'),('scr_lanface','event_user(0);'),
                           ('stringset','global.choice=1;'),('scr_84_get_lang_string','global.choice=1;'),
                           ('is_english','global.choice=1;')):
            s=self.sources();s[FILE]=s[FILE].replace('global.flag[82]=1;','scr_lanface(3);global.flag[82]=1;')
            filename='gml_GlobalScript_'+name+'.gml'
            s[filename]=s[filename].replace('{','{'+extra,1)
            self.assertFalse(self.analyze(s)[2],name)

    def test_duplicate_missing_or_rebound_helper_definition(self):
        for mode in ('duplicate','missing','top_level_effect'):
            s=self.sources();filename='gml_GlobalScript_scr_speaker.gml'
            if mode=='duplicate':s['gml_GlobalScript_other.gml']=s[filename]
            elif mode=='missing':del s[filename]
            else:s[filename]+='global.choice=1;'
            self.assertFalse(self.analyze(s)[2],mode)

    def test_changed_menu_getter_and_helper_control_prompt_are_rejected(self):
        s=self.sources(1)
        s[FILE]=s[FILE].replace('global.flag[82]=1;','scr_lanface(3);global.flag[82]=1;')
        fn='gml_GlobalScript_scr_lanface.gml';s[fn]=s[fn].replace(key(8),key(3))
        self.assertFalse(self.analyze(s,1)[2])
        s=self.sources(1);fn='gml_GlobalScript_scr_84_get_lang_string.gml'
        s[fn]=s[fn].replace('return ','global.choice=1;return ')
        self.assertFalse(self.analyze(s,1)[2])

    def test_duplicate_partial_or_non_equality_guards_are_rejected(self):
        for old,new in (('if(global.choice==1)','if(global.choice==0)'),
                        ('if(global.choice==1)','if(global.choice<2)'),
                        ('if(global.choice==1)','if(global.choice==2)'),
                        ('if(global.choice==1)','else if(global.choice==1)')):
            s=self.sources();s[FILE]=s[FILE].replace(old,new)
            # The final variant belongs to the old exclusive-chain rule and
            # must not be claimed as a newly proved independent response.
            a,_,choices=self.analyze(s)
            if new.startswith('else'):
                self.assertEqual(len(choices),1);self.assertFalse(any(e.get('response_form') for e in a.evidence))
            else:self.assertFalse(choices,new)

    def test_default_response_overwrite_is_not_part_of_this_rule(self):
        s=self.sources(1);s[FILE]=s[FILE].replace('case 774:','case 774:global.msg[0]=scr_84_get_lang_string("'+key(8)+'");')
        self.assertFalse(self.analyze(s,1)[2])

    def test_message_wrappers_allow_only_the_menu_prompt(self):
        import re
        s=self.sources()
        s[FILE]=re.sub(r'global\.msg\[(\d+)\]=stringsetloc\(([^;]+)\);',r'msgsetloc(\1,\2);',s[FILE])
        s[FILE]=s[FILE].replace('msgsetloc(1,','msgnextloc(')
        a,_,choices=self.analyze(s)
        self.assertEqual(len(choices),1)
        self.assertIn('gml_GlobalScript_msgset.gml',[h['file'] for h in a.evidence[0]['effect_helpers']])
        changed=dict(s);fn='gml_GlobalScript_msgset.gml'
        changed[fn]=changed[fn].replace('{','{global.choice=1;',1)
        self.assertFalse(self.analyze(changed)[2])
        changed=dict(s);changed[FILE]=changed[FILE].replace('global.flag[82]=1;',f'msgnextloc("\\\\C2 ","{key(3)}");')
        self.assertFalse(self.analyze(changed)[2])

    def test_unknown_effect_between_or_after_arms_is_not_ignored(self):
        for old,new in (('if(global.choice==1)','opaque();if(global.choice==1)'),
                        ('}}','opaque();}}')):
            s=self.sources();s[FILE]=s[FILE].replace(old,new)
            self.assertFalse(self.analyze(s)[2])
