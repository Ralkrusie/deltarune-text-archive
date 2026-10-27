// Real text factory, original selector Draw/confirmation/Alarm, synthetic scheduling.
function cap_ch_test_start(cap_case, cap_variant) {
    with (obj_choicer_neo) instance_destroy();
    with (obj_choicer_old) instance_destroy();
    with (obj_writer) instance_destroy();
    with (obj_dialoguer) instance_destroy();
    with (obj_face) instance_destroy();
    global.cap_ch_test_variant = cap_variant;
    global.darkzone = cap_variant == 1 ? 0 : 1;
    global.msc = cap_case;
    var cap_d = instance_create(0, 0, obj_dialoguer);
    cap_d.alarm[0] = -1;
    cap_d.side = 1;
    if (cap_variant == 0) {
        var cap_target = instance_create(80, 80, obj_npc_sign);
        with (cap_target) {
            skip = 1; visible = false; sprite_index = spr_npc_prisoner_dog_eye;
            var cap_previous = cap_ix_begin();
            scr_text(1177);
            cap_ix_end(cap_previous);
        }
    } else scr_text(cap_case);
    if (cap_variant == 2) {
        // Legacy choices draw their text in the parent writer, not choicemsg.
        msgset(0, "Yes          No\\C1");
        msgset(1, " ");
    }
    with (cap_d) event_user(0);
}
function cap_ch_test_step() {
    var cap_t = global.cap_test_clock;
    if (cap_t == 12) cap_ch_test_start(1177, 0);
    if (cap_t == 42) cap_ch_test_start(1177, 1);
    if (cap_t == 76) cap_ch_test_start(1177, 2);
    if (cap_t == 96) cap_ch_test_start(1183, 3);
    if (cap_t == 112) {
        with (obj_choicer_neo) instance_destroy();
        with (obj_writer) instance_destroy();
        with (obj_dialoguer) instance_destroy();
        global.choice = 0;
        scr_text(1178); // Same reply text outside a proven choice continuation.
        var cap_w = instance_create(100,120,obj_writer);
        cap_w.dialoguer = 1; cap_w.facer = 0;
    }
}
function cap_ch_test_selector() {
    if (string_pos("choices", environment_get_variable("DR_CAPTURE_TEST_PACE")) != 1) return;
    if (!variable_instance_exists(id, "cap_ch_test_age")) cap_ch_test_age = 0;
    if (!canchoose) return;
    cap_ch_test_age++;
    mychoice = global.cap_ch_test_variant == 1 ? 1 : 0;
    var cap_at = global.cap_ch_test_variant == 1 ? 1 : 5;
    if (global.cap_ch_test_variant != 3 && cap_ch_test_age == cap_at) event_user(0);
}
