// Gated engine fixtures: no save import, scene replay or OS input automation.
function cap_attachment_step() {
    var cap_pace = environment_get_variable("DR_CAPTURE_TEST_PACE");
    if (global.cap_test_clock == 12) {
        global.darkzone = (cap_pace == "attachments_gui" ? 0 : 1);
        global.cap_source = array_create(100, 0);
        global.msg[0] = "* Can be defeated through various \\I3   s of kindness!/";
        global.msg[1] = "\\m3\t\t*Good eye for music!/";
        global.msg[2] = "Button \\*A/";
        global.msg[3] = "* They are free... for a price.\\f0\\f1/";
        global.msg[4] = "Default helper text\\f0/";
        global.msg[5] = "Progressive child\\f0/";
        global.msg[6] = "Overwritten slot\\f0/";
        global.msg[7] = "Hidden child\\f0/";
        global.msg[8] = "No-face child\\f0/";
        global.msg[9] = "Next page has no child./%";
        global.fc = 2;
        var cap_w = instance_create(160, 120, obj_writer);
        cap_w.cap_fixture = true; cap_w.cap_attachment = true; cap_w.cap_attachment_real = false;
        cap_w.dialoguer = 1; cap_w.facer = 0;
        global.cap_test_writer = cap_w;
    }
    if (global.cap_test_clock == 95) {
        if (instance_exists(global.cap_test_writer)) { show_debug_message("ERROR: attachment fixture did not end"); return; }
        // Invoke the original audited, side-effect-limited text factory case, not a copied source tag.
        var cap_old_choice = global.choice;
        global.choice = 0;
        scr_text(1178);
        global.choice = cap_old_choice;
        var cap_w = instance_create(160, 120, obj_writer);
        cap_w.cap_fixture = true; cap_w.cap_attachment = true; cap_w.cap_attachment_real = true;
        cap_w.dialoguer = 1; cap_w.facer = 0;
        global.cap_test_writer = cap_w;
    }
    if (global.cap_test_clock == 118)
        show_debug_message("CAPTURE_ATTACHMENT_END " + json_stringify({writer_alive:instance_exists(global.cap_test_writer),messages:global.cap_message}));
}
function cap_attachment_before() {
    global.input_held[5] = true;
    global.input_held[9] = true;
    var cap_hold = (environment_get_variable("DR_CAPTURE_TEST_PACE") == "attachments_repeat" ? 8 : 7);
    if (cap_attachment_real) cap_hold = 12;
    global.input_pressed[4] = (cap_fixture_age == cap_hold);
    // Exercise fractional and wrapped miniface frame requests; do not claim normal playback timing.
    if (!cap_attachment_real && msgno == 1) miniface_pos = ((cap_fixture_age - 1) mod 4) * 4 + 1;
    if (cap_fixture_age != 1 || cap_attachment_real) return;
    if (msgno == 0) global.writerimg[3] = spr_btact;
    if (msgno == 1) scr_miniface_init_sweet();
    if (msgno == 3) {
        cap_smallface(0,"susie",10,200,"bottom","What's the price.",0);
        cap_smallface(1,"lancer",14,"right","bottom","Zero dollars",0);
    }
    if (msgno == 4) scr_smallface_reset(0);
    if (msgno == 5) {
        cap_smallface(0,"noelle",0,"mid","bottom","Progressive typing sample",0);
        global.smtype[0] = 2; global.smcolor[0] = c_lime;
        global.smalarm[0] = 1;
    }
    if (msgno == 6) {
        scr_smallface_reset(0);
        global.smstring[0] = cap_sm_clear_slot(0, "Replacement has no source tag");
        global.smsprite[0] = spr_face_l0; // invalidates any stale named selector at attach
        global.smtype[0] = 1; global.smalarm[0] = 1;
    }
    if (msgno == 7) {
        cap_smallface(0,"susie",0,"mid","bottom","Configured but not drawn",0);
        global.smtype[0] = 1; global.smalarm[0] = 100;
    }
    if (msgno == 8) cap_smallface(0,"none",0,"mid","bottom","Notice",0);
}
function cap_attachment_after() {
    if (!cap_attachment_real && cap_fixture_page == 7 && instance_exists(smallface)) smallface.visible = false;
}
