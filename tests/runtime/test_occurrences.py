import unittest

from tools.context.parser.attribution_schema import occurrence_id
from tools.runtime.verify_migration import compare_inventory


class RuntimeOccurrenceTests(unittest.TestCase):
    def source(self, offset=4, sha='a' * 64):
        source = dict(source_id=1, chapter=2, path='data/exported/code/ch2/example.gml',
                      sha256=sha, key='same_key', offset=offset, call='scr_84_get_lang_string')
        source['occurrence_id'] = occurrence_id(2, 'canonical', source['path'], sha,
                                                source['key'], offset, source['call'])
        return source

    def refs(self, source):
        return {source['occurrence_id']: {key: source[key] for key in
                                         ('chapter', 'path', 'sha256', 'key', 'offset', 'call')}}

    def test_exact_source_identity_matches(self):
        source = self.source()
        result = compare_inventory({'sources': [source]}, self.refs(source))
        self.assertEqual(result['exact_context_matches'], 1)

    def test_same_key_different_occurrence_is_not_matched(self):
        result = compare_inventory({'sources': [self.source(offset=5)]}, self.refs(self.source(offset=4)))
        self.assertEqual(result['exact_context_matches'], 0)
        self.assertEqual(result['missing_context'], 1)

    def test_reformatted_source_is_not_matched(self):
        result = compare_inventory({'sources': [self.source(sha='b' * 64)]}, self.refs(self.source()))
        self.assertEqual(result['missing_context'], 1)

    def test_forged_identity_and_duplicate_source_rejected(self):
        source = self.source()
        source['offset'] = 9
        with self.assertRaisesRegex(ValueError, 'identity'):
            compare_inventory({'sources': [source]}, {})
        source = self.source()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            compare_inventory({'sources': [source, source]}, self.refs(source))


if __name__ == '__main__':
    unittest.main()
