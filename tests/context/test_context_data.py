"""Context identity and release safety; synthetic strings only."""
import copy
from pathlib import Path
import sys
import unittest
import tempfile
import json

from tools.context.context_data import references, validate, catalog_payload
from tools.text.import_texts import sha


class ContextContractTests(unittest.TestCase):
    def setUp(self):
        self.manifest=b'text manifest'
        self.message={'type':'message','key':'same-key','occurrence_id':'occurrence:one',
                      'source':{'file':'gml_fixture.gml','line':1}}
        self.pack={'schema':1,'text_manifest_sha256':sha(self.manifest),
                   'scenes':[{'id':'scene','chapter':4,'body':self.message}]}
        self.tables={4:{'same-key'},5:{'other-key'}}

    def test_stale_input_rejected(self):
        with self.assertRaisesRegex(ValueError,'stale'):validate(self.pack,b'new input',self.tables)

    def test_reference_cannot_cross_chapters(self):
        self.pack['scenes'][0]['chapter']=5
        with self.assertRaisesRegex(ValueError,'reference'):validate(self.pack,self.manifest,self.tables)

    def test_no_absolute_source_paths(self):
        self.message['source']['file']='gml_/../../private.gml'
        with self.assertRaisesRegex(ValueError,'source'):validate(self.pack,self.manifest,self.tables)

    def test_duplicate_scene_rejected(self):
        self.pack['scenes'].append(copy.deepcopy(self.pack['scenes'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate'):validate(self.pack,self.manifest,self.tables)

    def test_unknown_flow_node_rejected(self):
        self.message['type']='unproven-call'
        with self.assertRaisesRegex(ValueError,'Unknown'):validate(self.pack,self.manifest,self.tables)

    def test_entry_guard_is_a_source_fact_with_a_safe_location(self):
        fact={'condition':'!(blocked)','meaning':'passed_at_source','visible':True,
              'source':{'file':'gml_fixture.gml','line':2}}
        self.message['entry_guards']=[fact]
        validate(self.pack,self.manifest,self.tables)
        for bad in (None,{}, {**fact,'meaning':'current_value'}, {**fact,'visible':1},
                    {**fact,'source':{'file':'gml_/../private.gml','line':2}},
                    {**fact,'source':{'file':'gml_fixture.gml','line':0}}):
            self.message['entry_guards']=[bad]
            with self.assertRaisesRegex(ValueError,'entry guard'):validate(self.pack,self.manifest,self.tables)

    def test_join_requires_one_following_message_in_the_same_sequence(self):
        fork={'type':'condition','join_next':True,'branches':[
            {'label':'global.choice == 0','body':self.message},
            {'label':'else','body':self.message}]}
        body={'type':'sequence','children':[fork,self.message]}
        self.pack['scenes'][0]['body']=body
        validate(self.pack,self.manifest,self.tables)
        body['children'].pop()
        with self.assertRaisesRegex(ValueError,'following'):validate(self.pack,self.manifest,self.tables)

    def test_revisit_preserves_conditions_and_requires_transition_evidence(self):
        body={'type':'condition','revisit':{'flag':123,'from':0,'to':1,'write_line':8},
              'branches':[{'label':'flag == 0','body':self.message},
                          {'label':'!(flag == 0)','body':self.message}]}
        self.pack['scenes'][0]['body']=body
        validate(self.pack,self.manifest,self.tables)
        for bad in ({'flag':123}, {'flag':123,'from':0,'to':0,'write_line':8},
                    {'flag':123,'from':0,'to':1,'write_line':0}):
            body['revisit']=bad
            with self.assertRaisesRegex(ValueError,'revisit'):validate(self.pack,self.manifest,self.tables)

    def test_choice_options_and_repeated_uses_stay_distinct(self):
        second=copy.deepcopy(self.message);second['occurrence_id']='occurrence:two'
        body={'type':'choice','branches':[
            {'option':self.message,'body':{'type':'sequence','children':[second]}},
            {'option':second,'body':{'type':'end','label':'Return'}}]}
        self.pack['scenes'][0]['body']=body
        validate(self.pack,self.manifest,self.tables)
        self.assertEqual([r['occurrence_id'] for r in references(body)],
                         ['occurrence:one','occurrence:two','occurrence:two'])

    def test_choice_shared_response_prefix_and_tail_keep_each_use_once(self):
        def message(identity):
            return {**self.message,'occurrence_id':'occurrence:'+identity}
        choice={'type':'choice','join_next':True,
                'prefix':{'type':'sequence','children':[message('prefix')]},
                'branches':[{'option':message('option0'),'body':message('answer0')},
                            {'option':message('option1'),'body':message('answer1')}]}
        body={'type':'sequence','children':[choice,message('tail')]}
        self.pack['scenes'][0]['body']=body
        validate(self.pack,self.manifest,self.tables)
        self.assertEqual([r['occurrence_id'] for r in references(body)],
                         ['occurrence:'+s for s in ('option0','option1','prefix','answer0','answer1','tail')])
        choice['prefix']['children'][0]['key']='not-in-texts'
        with self.assertRaisesRegex(ValueError,'reference'):validate(self.pack,self.manifest,self.tables)

    def test_response_prefix_is_nonempty_and_only_belongs_to_a_choice(self):
        choice={'type':'choice','branches':[
            {'option':self.message,'body':self.message},
            {'option':self.message,'body':self.message}]}
        self.pack['scenes'][0]['body']=choice
        for invalid in (None,{}, {'type':'sequence','children':[]},
                        {'type':'block','children':[self.message]}):
            choice['prefix']=invalid
            with self.subTest(prefix=invalid),self.assertRaisesRegex(ValueError,'response prefix'):
                validate(self.pack,self.manifest,self.tables)
        self.pack['scenes'][0]['body']={**self.message,'prefix':{'type':'sequence','children':[self.message]}}
        with self.assertRaisesRegex(ValueError,'response prefix'):validate(self.pack,self.manifest,self.tables)

    def catalog(self,folder,corruption=None):
        binding=sha(self.manifest);chapters={};files={}
        for ch in range(1,6):
            path=f'index-ch{ch}.json'
            data={'schema':2,'chapter':ch,'text_manifest_sha256':binding,'files':[],
                  'by_key':{'invented':[0]} if corruption=='lookup' and ch==1 else {},'related_by_key':{}}
            raw=json.dumps(data).encode();(folder/path).write_bytes(raw)
            meta={'path':path,'sha256':sha(raw),'bytes':len(raw)};chapters[str(ch)]=meta;files[path]=meta
        if corruption=='path':chapters['1']={**chapters['1'],'path':'../private.json'}
        raw=json.dumps({'schema':2,'text_manifest_sha256':binding,'chapters':chapters}).encode()
        (folder/'contexts.json').write_bytes(raw)
        (folder/'evidence.json').write_text(json.dumps({'contexts_sha256':sha(raw),'files':files}))
        if corruption=='bytes':(folder/'index-ch1.json').write_text('{}')

    def test_catalog_checks_paths_bytes_and_lookup(self):
        for bad,expected in [('path','Unsafe'),('bytes','digest'),('lookup','lookup')]:
            with self.subTest(corruption=bad),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp);self.catalog(folder,bad)
                with self.assertRaisesRegex(ValueError,expected):catalog_payload(folder,self.manifest,self.tables)

    def test_catalog_does_not_copy_unlisted_local_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);self.catalog(folder);(folder/'private.txt').write_text('private')
            payload=catalog_payload(folder,self.manifest,self.tables)
            self.assertEqual(len(payload),6)
            self.assertNotIn('private.txt',' '.join(payload))

    def test_missing_key_requires_explicit_source_binding(self):
        self.message['key']='not-in-texts'
        with self.assertRaisesRegex(ValueError,'reference'):validate(self.pack,self.manifest,self.tables)
        self.message.update(binding='missing_key',source_english='source only')
        validate(self.pack,self.manifest,self.tables)

if __name__=='__main__':unittest.main()
