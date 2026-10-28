import copy
import unittest
from tools.site.display_dedup import annotate


def package(ch, entries):
    strings, rows = [], []
    for key, en, ja, uses in entries:
        e = None if en is None else len(strings)
        if en is not None:
            strings.append(en)
        j = len(strings)
        strings.append(ja)
        rows.append([key, e, j, None, None, None, [[0, n+1] for n in range(uses)]])
    return {'chapter': ch, 'languages': ['en','ja','zh_default','zh_names','zh_recruitable'],
            'strings': strings, 'rows': rows}


class DisplayDedupTests(unittest.TestCase):
    def test_unique_renamed_key_translation_independent_and_no_data_loss(self):
        a = package(1, [('obj_scene_slash_Step_0_gml_108_0', r'\TN Hello', '甲', 1)])
        b = package(2, [('obj_scene_slash_Step_0_gml_112_0', r'\TN Hello', '乙', 1)])
        before = copy.deepcopy([a,b])
        self.assertEqual(annotate([a,b]), 1)
        self.assertEqual(a['display_dedup']['groups'], b['display_dedup']['groups'])
        self.assertEqual(a['display_dedup']['chapters'], {'0': [1,2]})
        self.assertEqual(a['display_dedup']['chapters'], b['display_dedup']['chapters'])
        for data, original in zip([a,b], before):
            data.pop('display_dedup')
            self.assertEqual(data, original)

    def test_repetition_in_unselected_chapter_blocks_cross_key_pairing(self):
        a = package(1, [('obj_gml_1_0','Hello','',1)])
        b = package(2, [('obj_gml_2_0','Hello','',1)])
        c = package(5, [('obj_gml_1_0','Hello','',1),('obj_gml_3_0_b','Hello','',1)])
        annotate([a,b,c])
        self.assertEqual(a['display_dedup']['groups'][0], c['display_dedup']['groups'][0])
        self.assertIsNone(b['display_dedup']['groups'][0])
        self.assertIsNone(c['display_dedup']['groups'][1])

    def test_multiple_uses_block_cross_key_but_preserve_exact_key(self):
        a = package(1, [('obj_gml_1_0','Hello','',2)])
        b = package(2, [('obj_gml_2_0','Hello','',1),('obj_gml_1_0','Hello','',1)])
        annotate([a,b])
        self.assertIsNone(b['display_dedup']['groups'][0])
        self.assertEqual(a['display_dedup']['groups'][0], b['display_dedup']['groups'][1])

    def test_english_full_value_prefix_and_missing_boundaries(self):
        for key, text in [('other_gml_1_0','Hello'),('obj_gml_1_0','hello'),
                          ('obj_gml_1_0','Hello '),('obj_gml_1_0','Hello\\E1')]:
            a = package(1, [('obj_gml_1_0','Hello','',1)])
            b = package(2, [(key,text,'',1)])
            self.assertEqual(annotate([a,b]), 0)
        for en in [None,'']:
            self.assertEqual(annotate([package(1,[('same',en,'同文',1)]),
                                       package(2,[('same',en,'同文',1)])]),0)

    def test_non_numbered_key_exact_only_and_deterministic(self):
        data = [package(1,[('name','Hello','',0)]),package(2,[('name','Hello','',0)])]
        annotate(data)
        expected = copy.deepcopy(data)
        annotate(data)
        self.assertEqual(data, expected)

    def test_group_revision_changes_when_membership_changes(self):
        data = [package(1,[('name','Hello','',0)]), package(2,[('name','Hello','',0)])]
        annotate(data)
        before = data[0]['display_dedup']['revision']
        self.assertEqual(before, data[1]['display_dedup']['revision'])
        data[1]['chapter'] = 3
        annotate(data)
        self.assertNotEqual(before, data[0]['display_dedup']['revision'])
