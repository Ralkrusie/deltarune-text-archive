// Explicit synthetic scheduling, real NPC event and original shared text factory.
function cap_ix_test_writer() {
    var cap_w = instance_create(100, 120, obj_writer);
    cap_w.cap_fixture = true;
    cap_w.dialoguer = 1;
    cap_w.facer = 0;
}
function cap_ix_test_step() {
    var cap_t = global.cap_test_clock;
    if (cap_t <= 13) show_debug_message("CAPTURE_IX_CLOCK " + string(cap_t));
    if (cap_t == 12) {
        global.cap_ix_test_a = instance_create(80, 80, obj_npc_sign);
        show_debug_message("CAPTURE_IX_CREATED_A");
        global.cap_ix_test_b = instance_create(220, 80, obj_npc_sign);
        show_debug_message("CAPTURE_IX_CREATED_B");
        with (global.cap_ix_test_a) { visible = false; skip = 1; sprite_index = spr_npc_prisoner_dog_eye; }
        with (global.cap_ix_test_b) { visible = false; skip = 1; sprite_index = spr_npc_prisoner_dog_lesser; }
    }
    if (cap_t == 12 || cap_t == 24 || cap_t == 36 || cap_t == 48 || cap_t == 60 || cap_t == 76 || cap_t == 88 || cap_t == 100) {
        with (obj_writer) instance_destroy();
    }
    if (cap_t == 12 || cap_t == 24) {
        with (global.cap_ix_test_a) cap_ix_interact();
        cap_ix_test_writer();
    }
    if (cap_t == 36) {
        with (global.cap_ix_test_b) cap_ix_interact();
        cap_ix_test_writer();
    }
    if (cap_t == 48) {
        with (global.cap_ix_test_a) {
            var cap_prev = cap_ix_begin();
            scr_text(225);
            cap_ix_end(cap_prev);
        }
        cap_ix_test_writer();
    }
    if (cap_t == 60) {
        global.cap_ix_test_master = instance_create(0, 0, obj_cutscene_master);
        with (global.cap_ix_test_master) { waiting = 1; i = 0; }
        with (global.cap_ix_test_a) {
            var cap_prev = cap_ix_begin();
            c_cmd_x("delaycmd", 2, "msc", 225, 0, 0, 0);
            cap_ix_end(cap_prev);
        }
    }
    if (cap_t == 62) {
        // A different, later interaction must not steal A's queued response.
        with (global.cap_ix_test_b) cap_ix_interact();
    }
    if (cap_t == 64) {
        with (global.cap_ix_test_master) {
            i = 0;
            command_actor[0] = global.cap_ix_test_a;
            _c = command[0];
            scr_cutscene_commands();
        }
    }
    if (cap_t == 68) cap_ix_test_writer();
    if (cap_t == 76) {
        scr_text(225); // Identical shared source, outside any proven interaction.
        cap_ix_test_writer();
    }
    if (cap_t == 88) {
        with (global.cap_ix_test_a) {
            var cap_prev = cap_ix_begin();
            scr_text(225);
            cap_ix_end(cap_prev);
        }
        msgset(0, global.msg[0]); // Same text overwrite outside the dispatch invalidates ownership.
        cap_ix_test_writer();
    }
    if (cap_t == 100) cap_ix_test_writer(); // Reused message buffer cannot revive consumed tokens.
    if (cap_t == 112) {
        with (obj_writer) instance_destroy();
        show_debug_message("CAPTURE_INTERACTION_PROVENANCE_END " + json_stringify({active: global.cap_ix_active,
            interactions: global.cap_ix_count, messages: global.cap_message, io_failed: global.cap_ix_io_failed}));
    }
}
