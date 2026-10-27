"""Generate bounded source tests from the prepared original-source patches."""
import json
import re


def generate(stage):
    inv=json.loads((stage/'sources.json').read_text())
    cafe=(stage/'patches/gml_GlobalScript_scr_text.gml').read_text(encoding='utf-8')
    lines=[s.strip() for s in cafe.splitlines() if 'global.choicemsg[' in s and '(room == room_dw_castle_cafe) ?' in s]
    assert len(lines)==3
    branch='\n'.join(lines).replace('(room == room_dw_castle_cafe)','cap_cafe')
    encounter=(stage/'patches/gml_GlobalScript_scr_encountersetup.gml').read_text(encoding='utf-8')
    battle=next(s.strip() for s in encounter.splitlines() if 'Jigsaw Joe jigs in!' in s)
    copy=(stage/'patches/gml_Object_obj_battlecontroller_Step_0.gml').read_text(encoding='utf-8')
    transfer=next(s.strip() for s in copy.splitlines() if 'global.msg[0] = cap_btl_to_msg' in s)
    ids={s['key']:s['source_id'] for s in inv['sources']}
    expected=[ids[k] for k in ('scr_text_slash_scr_text_gml_4930_0','scr_text_slash_scr_text_gml_4931_0_b','scr_text_slash_scr_text_gml_4932_0_b','scr_text_slash_scr_text_gml_4931_0','scr_text_slash_scr_text_gml_4931_1')]
    text='''
function cap_source_assert(cap_ok, cap_label) { if (!cap_ok) throw "source fixture: " + cap_label; }
function cap_source_branches(cap_cafe) { __BRANCH__ }
function cap_source_test_step() {
 if (global.cap_test_clock != 12) return;
 cap_source_branches(true);
 cap_source_assert(global.cap_ch_sources[0] == __A__ && global.cap_ch_sources[1] == __B__ && global.cap_ch_sources[2] == __C__, "cafe branches");
 cap_source_branches(false);
 cap_source_assert(global.cap_ch_sources[0] == __D__ && global.cap_ch_sources[1] == __E__ && global.cap_ch_sources[2] == 0, "other branches and literal clear");
 scr_speaker("noone");
 scr_recruit_info(5);
 cap_dlg_msgset(0, _dialogue[0]);
 cap_source_assert(global.cap_source[0] > 0, "recruit source");
 var cap_w = instance_create(100,120,obj_writer); cap_w.dialoguer=1; cap_w.facer=0;
 cap_observe_for_test(cap_w);
 with (cap_w) { cap_finish("fixture"); instance_destroy(); }
 _dialogue[0] = cap_dlg_clear_slot(0, _dialogue[0]);
 cap_dlg_msgset(0, _dialogue[0]);
 cap_source_assert(global.cap_source[0] == 0, "same-text overwrite must clear");
 __BATTLE__
 __TRANSFER__
 cap_source_assert(global.cap_source[0] > 0, "battle source");
 cap_w = instance_create(100,120,obj_writer); cap_w.dialoguer=1;cap_w.facer=0;
 cap_observe_for_test(cap_w);
 with (cap_w) { cap_finish("fixture"); instance_destroy(); }
 global.battlemsg[0] = cap_btl_clear_slot(0, global.battlemsg[0]);
 __TRANSFER__
 cap_source_assert(global.cap_source[0] == 0, "battle same-text overwrite");
 var cap_npc = instance_create(200,200,obj_npc_cafe);
 with (cap_npc) {
  seat=0; global.flag[800]=6; event_user(6);
  var cap_prev=cap_ix_begin(); cap_ix_end(cap_prev); instance_destroy();
 }
 show_debug_message("CAPTURE_SOURCE_TEST_PASS");
}
function cap_observe_for_test(cap_w) { with (cap_w) cap_observe("source_fixture"); }
'''
    for k,v in zip(('A','B','C','D','E'),expected):text=text.replace('__'+k+'__',str(v))
    text=text.replace('__BRANCH__',branch).replace('__BATTLE__',battle).replace('__TRANSFER__',transfer)
    # Execute the newly transformed real ACT assignments, both ternary branches.
    extra=[]
    for stem in ('werewire','tasque'):
        patch=(stage/f'patches/gml_Object_obj_{stem}_enemy_Step_0.gml').read_text(encoding='utf-8')
        m=re.search(r'(var cap_tag_\d+ = \{source: 0\};\s*var simultext = [^\n]+;)',patch)
        assert m, stem
        tag=re.search(r'var (cap_tag_\d+)',m[1])[1]
        consume=f'cap_local_msgset(0, simultext, {tag});'
        extra.append(f'function cap_fixture_{stem}(simultotal) {{ {m[1]} {consume} return {tag}.source; }}')
    extra.append('''function cap_fixture_record() {
        var cap_w = instance_create(100,120,obj_writer); cap_w.dialoguer=1; cap_w.facer=0;
        cap_observe_for_test(cap_w); with(cap_w) { cap_finish("fixture"); instance_destroy(); }
    }''')
    assertions=[]
    for stem,key in [('werewire','obj_werewire_enemy_slash_Step_0_gml_399_'),('tasque','obj_tasque_enemy_slash_Step_0_gml_133_')]:
        for total,suffix in [(1,'0'),(2,'1')]:
            assertions.append(f'cap_source_assert(cap_fixture_{stem}({total}) == {ids[key+suffix]}, "local {stem} branch {total}"); cap_fixture_record();')
    assertions.append('''var cap_item_tag = {source:0};
        var cap_item_text = cap_local_itemget(cap_item_tag, 10, "armor");
        cap_local_msgset(0, cap_item_text, cap_item_tag);
        cap_source_assert(global.cap_source[0] == __ITEM__, "item template return"); cap_fixture_record();
        global.cap_item_return_source = 999;
        cap_local_msgnext(cap_item_text, cap_item_tag);
        cap_source_assert(global.cap_source[global.msgno] == __ITEM__, "return tag survives unrelated global state");
        cap_item_text = cap_local_itemget(cap_item_tag, 18, "weapon");
        cap_local_msgset(0, cap_item_text, cap_item_tag); cap_fixture_record();
        cap_source_assert(global.cap_source[0] == __ITEM__, "weapon template return");
        cap_item_text = cap_local_itemget(cap_item_tag, 0, "money", "unrelated extra words");
        cap_source_assert(cap_item_tag.source == 0, "unsupported suffix stays unknown");
    '''.replace('__ITEM__',str(ids['obj_treasure_room_slash_Other_10_gml_76_0'])))
    text=text.replace('show_debug_message("CAPTURE_SOURCE_TEST_PASS");','\n'.join(assertions)+'\nshow_debug_message("CAPTURE_SOURCE_TEST_PASS");')
    (stage/'source_test.gml').write_text(text+'\n'+'\n'.join(extra),encoding='utf-8')
