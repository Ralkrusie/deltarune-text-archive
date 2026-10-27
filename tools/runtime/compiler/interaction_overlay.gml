// CH2 exploration candidates, using the same two parent families as obj_mainchara.
// World-space Draw End: the engine applies the camera; invisible readable masks count.
function cap_interaction_toggle(cap_f6, cap_f7) {
    if (cap_f6) global.cap_interaction_boxes = !global.cap_interaction_boxes;
    if (cap_f7) global.cap_interaction_names = !global.cap_interaction_names;
}
function cap_interaction_keys() {
    cap_interaction_toggle(keyboard_check_pressed(vk_f6), keyboard_check_pressed(vk_f7));
}
function cap_interaction_box(cap_solid) {
    if (sprite_index < 0 && mask_index < 0) return;
    if (bbox_right < bbox_left || bbox_bottom < bbox_top) return;
    var cap_col = cap_solid ? make_color_rgb(255, 184, 64) : make_color_rgb(64, 255, 144);
    draw_set_color(c_black);
    draw_rectangle(bbox_left - 1, bbox_top - 1, bbox_right + 1, bbox_bottom + 1, true);
    draw_set_color(cap_col);
    draw_rectangle(bbox_left, bbox_top, bbox_right, bbox_bottom, true);
    if (global.cap_interaction_names) {
        var cap_label = object_get_name(object_index);
        draw_set_color(c_black);
        draw_text(bbox_left + 1, bbox_top - 11, cap_label);
        draw_set_color(cap_col);
        draw_text(bbox_left, bbox_top - 12, cap_label);
    }
    if (global.cap_interaction_fixture) {
        array_push(global.cap_interaction_test_boxes, {object: object_get_name(object_index),
            solid_family: cap_solid, visible: visible, bounds: [bbox_left, bbox_top, bbox_right, bbox_bottom]});
    }
}
function cap_interaction_draw() {
    if (global.cap_interaction_fixture) global.cap_interaction_test_boxes = [];
    if (!global.cap_interaction_boxes) return;
    // Hide in menus, battles and dialogue; no change to interaction or collision state.
    if (!global.cap_interaction_fixture) {
        if (!instance_exists(obj_mainchara) || global.interact != 0) return;
    }
    var cap_color = draw_get_color();
    var cap_alpha = draw_get_alpha();
    var cap_font = draw_get_font();
    var cap_halign = draw_get_halign();
    var cap_valign = draw_get_valign();
    draw_set_alpha(1);
    if (global.cap_interaction_names) {
        draw_set_font(fnt_main);
        draw_set_halign(fa_left);
        draw_set_valign(fa_top);
    }
    with (obj_interactable) cap_interaction_box(false);
    with (obj_interactablesolid) cap_interaction_box(true);
    draw_set_color(cap_color);
    draw_set_alpha(cap_alpha);
    draw_set_font(cap_font);
    draw_set_halign(cap_halign);
    draw_set_valign(cap_valign);
}

// Isolated engine fixture: no interaction events, no game saves or scene replay.
function cap_interaction_test_step() {
    if (global.cap_test_clock == 12) {
        global.cap_interaction_fixture = true;
        // The boot menu paints a full-screen GUI over world Draw End. Hide its
        // visuals only in this isolated fixture so screenshots inspect the boxes.
        with (all) {
            if (object_index != obj_time) visible = false;
        }
        var cap_a = instance_create(80, 100, obj_readable);
        cap_a.sprite_index = spr_solidblock;
        cap_a.image_xscale = 2;
        cap_a.image_yscale = 0.5;
        cap_a.visible = false;
        var cap_b = instance_create(210, 150, obj_interactablesolid);
        cap_b.sprite_index = spr_solidblock;
        cap_b.image_xscale = -1.5;
        cap_b.image_yscale = 2;
        cap_b.visible = false;
        var cap_c = instance_create(300, 150, obj_solidblock);
        cap_c.sprite_index = spr_solidblock;
        cap_c.visible = false;
        global.cap_interaction_test_instances = [cap_a, cap_b, cap_c];
    }
}
function cap_interaction_test_draw() {
    if (!global.cap_interaction_fixture) return;
    var cap_t = global.cap_test_clock;
    if (cap_t != 20 && cap_t != 30 && cap_t != 40) return;
    // Exercise the same toggle helper as the actual F6/F7 input path.
    if (cap_t == 30) cap_interaction_toggle(true, false);
    if (cap_t == 40) cap_interaction_toggle(true, true);
    var cap_before = [draw_get_color(), draw_get_alpha(), draw_get_font(), draw_get_halign(), draw_get_valign()];
    cap_interaction_draw();
    var cap_after = [draw_get_color(), draw_get_alpha(), draw_get_font(), draw_get_halign(), draw_get_valign()];
    var cap_expected = [];
    for (var cap_i = 0; cap_i < 2; cap_i++) {
        var cap_inst = global.cap_interaction_test_instances[cap_i];
        array_push(cap_expected, {object: object_get_name(cap_inst.object_index),
            bounds: [cap_inst.bbox_left, cap_inst.bbox_top, cap_inst.bbox_right, cap_inst.bbox_bottom]});
    }
    show_debug_message("CAPTURE_INTERACTION_CHECK " + json_stringify({clock: cap_t,
        enabled: global.cap_interaction_boxes, names: global.cap_interaction_names,
        before: cap_before, after: cap_after, boxes: global.cap_interaction_test_boxes,
        expected: cap_expected, interact: global.interact}));
    if ((cap_t == 20 || cap_t == 40) && surface_exists(application_surface))
        surface_save(application_surface, "capture_" + environment_get_variable("DR_CAPTURE_SESSION") + "_boxes_" + string(cap_t) + ".png");
}
