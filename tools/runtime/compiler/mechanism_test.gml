// Engine-level synthetic fixture, explicitly marked mechanism_selftest.
// Original functions and Draw paths run; no room replay, input injection at OS level, or save import.
function cap_mechanism_step() {
    if (!variable_global_exists("cap_test_clock")) global.cap_test_clock = 0;
    global.cap_test_clock++;
    if (environment_get_variable("DR_CAPTURE_TEST_PACE") == "sources") {
        try { cap_source_test_step(); }
        catch (cap_error) { show_debug_message("CAPTURE_EXCEPTION " + json_stringify(cap_error)); game_end(); }
        return;
    }
    if (string_pos("choices", environment_get_variable("DR_CAPTURE_TEST_PACE")) == 1) {
        try { cap_ch_test_step(); }
        catch (cap_error) { show_debug_message("CAPTURE_EXCEPTION " + json_stringify(cap_error)); game_end(); }
        return;
    }
    if (environment_get_variable("DR_CAPTURE_TEST_PACE") == "provenance") {
        try { cap_ix_test_step(); }
        catch (cap_error) { show_debug_message("CAPTURE_EXCEPTION " + json_stringify(cap_error)); game_end(); }
        return;
    }
    if (environment_get_variable("DR_CAPTURE_TEST_PACE") == "interactions") {
        cap_interaction_test_step(); return;
    }
    if (string_pos("attachments", environment_get_variable("DR_CAPTURE_TEST_PACE")) == 1) {
        cap_attachment_step(); return;
    }
    if (global.cap_test_clock == 12) {
        scr_speaker("toriel");
        msgsetloc(0, "\\E3* It is YOUR knife in this empty tin, is it not!?/", "obj_krisroom_slash_Step_0_gml_393_0");
        scr_susface(1, 2);
        msgsetloc(2, "\\E2* Yeah, yeah^1... It's been what^1, a day?/", "obj_ch2_scene4_slash_Step_0_gml_67_0");
        scr_anyface("alphys", 3, 0);
        msgsetloc(4, "\\E0* Th-they're great^1, Tori!/", "obj_ch2_lw_cutscenes_short_slash_Step_0_gml_185_0");
        scr_noface(5);
        msgsetloc(6, "* The door is locked./%", "obj_readable_room1_slash_Other_10_gml_120_0");
        var cap_test_pace = environment_get_variable("DR_CAPTURE_TEST_PACE");
        if (string_pos("guard", cap_test_pace) == 1) {
            scr_lanface(5, 3);
            msgsetloc(6, "\\E3* Ahaha!^1! Not if I surprise myself first!!/", "obj_ch2_scene6_slash_Step_0_gml_644_0");
            scr_noface(7);
            msgsetloc(8, "* The door is locked./%", "obj_readable_room1_slash_Other_10_gml_120_0");
        }
        if (string_pos("styles", cap_test_pace) == 1) {
            // Explicitly synthetic scheduling: real wording, page terminators adapted.
            global.cap_source = array_create(100, 0);
            global.fc = 0;
            global.msg[0] = "* (Try using Ralsei's \\cBPACIFY\\cW!)/";
            global.msg[1] = "NOOOOOOOO---!!! /";
            global.msg[2] = "* The door is locked./";
            global.msg[3] = "\\cRRED\\cW WHITE/";
            global.msg[4] = "\\cRGlowing text/";
            global.msg[5] = "Moving \\cRtext/";
            global.msg[6] = "Parameter change/";
            global.msg[7] = "Sub-centesimal shake/";
            global.msg[8] = "\\cRTrail update guard/%";
        }
        var cap_w = instance_create(160, 120, obj_writer);
        cap_w.cap_fixture = true;
        cap_w.dialoguer = 1;
        cap_w.facer = 1;
        if (string_pos("styles", cap_test_pace) != 1) {
            var cap_f = instance_create(100, 120, obj_face);
            cap_f.cap_owner = cap_w;
            cap_w.cap_portrait_instance = cap_f;
            if (cap_test_pace == "guard_missing") cap_f.visible = false;
        } else { cap_w.facer = 0; }
        global.cap_test_writer = cap_w;
        show_debug_message("CAPTURE_HP_CHECK " + json_stringify({max_hp: [global.maxhp[1],global.maxhp[2],global.maxhp[3],global.maxhp[4]],light_max_hp:global.lmaxhp}));
    }
    if (global.cap_test_clock == 100) {
        show_debug_message("CAPTURE_FIXTURE_END " + json_stringify({writer_alive:instance_exists(global.cap_test_writer),messages:global.cap_message}));
    }
}
function cap_fixture_before() {
    if (!variable_instance_exists(id, "cap_fixture")) return;
    if (!cap_fixture) return;
    cap_old_x = global.input_held[5];
    cap_old_ctrl = global.input_held[9];
    cap_old_confirm = global.input_pressed[4];
    cap_old_flag = global.flag[10];
    if (!variable_instance_exists(id, "cap_fixture_page") || cap_fixture_page != msgno) {
        cap_fixture_page = msgno;
        cap_fixture_age = 0;
    }
    cap_fixture_age++;
    if (string_pos("choices", environment_get_variable("DR_CAPTURE_TEST_PACE")) == 1) {
        global.input_held[5] = true;
        global.input_held[9] = false;
        global.input_pressed[4] = cap_fixture_age == 5;
        return;
    }
    if (environment_get_variable("DR_CAPTURE_TEST_PACE") == "provenance") {
        global.input_held[5] = true;
        global.input_held[9] = false;
        global.input_pressed[4] = (cap_fixture_age == 5);
        return;
    }
    global.input_held[5] = (msgno == 0);
    global.input_pressed[4] = (msgno == 0 && global.cap_test_clock >= 30);
    global.input_held[9] = (msgno > 0);
    if (environment_get_variable("DR_CAPTURE_TEST_PACE") == "delayed" && (msgno == 2 || msgno == 4) && cap_fixture_age < 12) {
        global.input_held[9] = false;
        global.input_held[5] = true;
    }
    if (environment_get_variable("DR_CAPTURE_TEST_PACE") == "manual") {
        // Keep Ctrl held, reveal with X, and press confirm once every 12 Draws.
        global.input_held[9] = true;
        global.input_held[5] = true;
        global.input_pressed[4] = ((cap_fixture_age mod 12) == 0);
        if (cap_fixture_age == 8) show_debug_message("CAPTURE_MANUAL_HOLD " + json_stringify({page:msgno,age:cap_fixture_age}));
    }
    if (string_pos("guard", environment_get_variable("DR_CAPTURE_TEST_PACE")) == 1) {
        global.input_held[9] = true;
        global.input_held[5] = true;
        // One early confirm only; buffered progression must not need a second key press.
        global.input_pressed[4] = (cap_fixture_age == 2);
        if (cap_fixture_age == 2) show_debug_message("CAPTURE_SINGLE_CONFIRM " + string(msgno));
    }
    var cap_style_pace = environment_get_variable("DR_CAPTURE_TEST_PACE");
    if (string_pos("styles", cap_style_pace) == 1) {
        global.input_held[9] = true;
        global.input_held[5] = true;
        global.input_pressed[4] = (cap_fixture_age == (cap_style_pace == "styles_slow" ? 9 : 5));
        if (cap_fixture_age == 1) {
            special = 0; shake = 0; specfade = 1; textscale = 1;
            if (cap_style_pace == "styles_slow") siner = 27;
            if (msgno == 1) shake = 1;
            if (msgno == 3) { special = 1; shake = 0.5; }
            if (msgno == 4) { special = 2; shake = 9; specfade = 0.75; }
            if (msgno == 5 || msgno == 8) { special = 3; shake = 9; }
            if (msgno == 6 || msgno == 7) shake = 1;
        }
        if (msgno == 6 && cap_fixture_age >= 3) shake = 2;
        if (msgno == 7 && cap_fixture_age >= 3) shake = 1.001;
    }
    global.flag[10] = 1;
    if (variable_instance_exists(id, "cap_attachment")) cap_attachment_before();
}
function cap_fixture_after() {
    if (!variable_instance_exists(id, "cap_fixture")) return;
    if (!cap_fixture) return;
    if (variable_instance_exists(id, "cap_attachment")) cap_attachment_after();
    global.input_held[5] = cap_old_x;
    global.input_held[9] = cap_old_ctrl;
    global.input_pressed[4] = cap_old_confirm;
    global.flag[10] = cap_old_flag;
}
