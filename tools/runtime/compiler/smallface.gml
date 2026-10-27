// CH2 writer-created smallfaces. Parent identity is frozen at creation, not inferred by proximity.
function cap_sm_clear_slot(cap_slot, cap_value) {
    global.cap_sm_source[cap_slot] = 0;
    global.cap_sm_text[cap_slot] = cap_value;
    return cap_value;
}
function cap_sm_bind_slot(cap_slot, cap_value, cap_source_id) {
    global.cap_sm_source[cap_slot] = cap_source_id;
    global.cap_sm_text[cap_slot] = cap_value;
    return cap_value;
}
function cap_smallface(cap_slot, cap_who, cap_frame, cap_xpos, cap_ypos, cap_text, cap_source_id) {
    scr_smallface(cap_slot, cap_who, cap_frame, cap_xpos, cap_ypos, cap_text);
    global.cap_sm_source[cap_slot] = cap_source_id;
    global.cap_sm_text[cap_slot] = global.smstring[cap_slot];
}
function cap_sm_selector(cap_slot, cap_who) {
    global.cap_sm_selector[cap_slot] = cap_who;
    global.cap_sm_selected_sprite[cap_slot] = global.smsprite[cap_slot];
}
function cap_sm_attach(cap_child, cap_slot, cap_anchor) {
    if (!cap_open || !instance_exists(cap_child)) return;
    cap_formatted = mystring;
    if (array_length(cap_smallfaces) >= 32) { cap_overflow = true; return; }
    var cap_sid = global.cap_sm_source[cap_slot];
    if (cap_child.mystring != global.cap_sm_text[cap_slot]) cap_sid = 0;
    var cap_selected = global.cap_sm_selector[cap_slot];
    if (cap_child.sprite_index != global.cap_sm_selected_sprite[cap_slot]) cap_selected = "";
    var cap_record = {ordinal: array_length(cap_smallfaces), parent_message_id: cap_message,
        slot: cap_slot, anchor_index: cap_anchor, source_id: cap_sid, text: cap_child.mystring,
        selector: cap_selected, configured_sprite_id: cap_child.sprite_index,
        configured_type: cap_child.type, configured_color: cap_child.mycolor,
        configured_frame: cap_child.image_index, image_speed: cap_child.image_speed,
        initial_x: cap_child.x - x, initial_y: cap_child.y - y,
        entry_speed: cap_child.speed, entry_direction: cap_child.direction, alarm_steps: cap_child.alarm[0],
        motion_model: "entry_until_alarm_then_stop;exit_accelerates_if_getrid",
        sprites: [], text_states: [], samples: [], overflow: false,
        draw_events: 0, partial: true};
    cap_smallfaces[array_length(cap_smallfaces)] = cap_record;
    cap_child.cap_sm_record = cap_record;
    cap_child.cap_sm_parent = id;
    cap_child.cap_sm_parent_message = cap_message;
    cap_child.cap_sm_sprite_keys = [];
    cap_child.cap_sm_text_keys = [];
    cap_child.cap_sm_last_sample_draw = -1;
}
function cap_sm_live() {
    if (!variable_instance_exists(id, "cap_sm_record")) return false;
    if (!instance_exists(cap_sm_parent)) return false;
    if (!variable_instance_exists(cap_sm_parent, "cap_open")) return false;
    return cap_sm_parent.cap_open && cap_sm_parent.cap_message == cap_sm_parent_message;
}
function cap_sm_overflow() {
    cap_sm_record.overflow = true;
    cap_sm_parent.cap_overflow = true;
}
function cap_sm_sprite(cap_sprite, cap_frame, cap_xx, cap_yy, cap_sx, cap_sy, cap_rotation, cap_blend, cap_alpha, cap_pass) {
    draw_sprite_ext(cap_sprite, cap_frame, cap_xx, cap_yy, cap_sx, cap_sy, cap_rotation, cap_blend, cap_alpha);
    if (!cap_sm_live()) return;
    cap_sm_record.draw_events++;
    if (sprite_exists(cap_sprite)) {
        var cap_frames = sprite_get_number(cap_sprite);
        var cap_selected = floor(cap_frame == -1 ? image_index : cap_frame);
        if (cap_frames > 0) cap_selected = ((cap_selected mod cap_frames) + cap_frames) mod cap_frames;
        var cap_asset = {sprite_id: cap_sprite, sprite_name: sprite_get_name(cap_sprite),
            frame_count: cap_frames, subimage: cap_selected, scale_x: cap_sx, scale_y: cap_sy,
            rotation: cap_rotation, blend: cap_blend, pass: cap_pass, alpha_model: "facealpha_plus_0.2_until_1"};
        var cap_key = json_stringify(cap_asset);
        var cap_found = false;
        for (var cap_j = 0; cap_j < array_length(cap_sm_sprite_keys); cap_j++)
            if (cap_sm_sprite_keys[cap_j] == cap_key) cap_found = true;
        if (!cap_found) {
            if (array_length(cap_sm_sprite_keys) >= 128) cap_sm_overflow();
            else {
                cap_sm_sprite_keys[array_length(cap_sm_sprite_keys)] = cap_key;
                var cap_assets = cap_sm_record.sprites;
                cap_assets[array_length(cap_assets)] = cap_asset;
                cap_sm_record.sprites = cap_assets;
            }
        }
    }
    // Actual phase/position/alpha samples stay raw, outside variant identity.
    if (array_length(cap_sm_record.samples) < 4) {
        var cap_samples = cap_sm_record.samples;
        cap_samples[array_length(cap_samples)] = {kind: "sprite", pass: cap_pass, alpha: cap_alpha,
            relative_x: x - cap_sm_parent.x, relative_y: y - cap_sm_parent.y,
            draw_x: cap_xx, draw_y: cap_yy, speed: speed, direction: direction, requested_frame: cap_frame};
        cap_sm_record.samples = cap_samples;
    }
}
function cap_sm_draw_text(cap_xx, cap_yy, cap_rendered, cap_site, cap_pass) {
    draw_text(cap_xx, cap_yy, cap_rendered);
    if (!cap_sm_live()) return;
    var cap_font = draw_get_font();
    var cap_state = {text: mystring, site: cap_site, pass: cap_pass, type: type,
        font_id: cap_font, font_name: (cap_font >= 0 ? font_get_name(cap_font) : "default"),
        color_bgr: draw_get_color(), motion: (cap_site == 3 ? "random_xy_1" : "none"),
        alpha_model: "facealpha_plus_0.2_until_1"};
    var cap_key = json_stringify(cap_state);
    var cap_index = -1;
    for (var cap_j = 0; cap_j < array_length(cap_sm_text_keys); cap_j++)
        if (cap_sm_text_keys[cap_j] == cap_key) cap_index = cap_j;
    if (cap_index < 0) {
        if (array_length(cap_sm_text_keys) >= 64) { cap_sm_overflow(); return; }
        cap_index = array_length(cap_sm_text_keys);
        cap_sm_text_keys[cap_index] = cap_key;
        cap_state.rendered_text = "";
        cap_state.complete_text_drawn = false;
        var cap_states = cap_sm_record.text_states;
        cap_states[cap_index] = cap_state;
        cap_sm_record.text_states = cap_states;
    }
    var cap_existing = cap_sm_record.text_states[cap_index];
    if (string_length(cap_rendered) >= string_length(cap_existing.rendered_text)) cap_existing.rendered_text = cap_rendered;
    var cap_full = string_hash_to_newline(mystring);
    if (cap_rendered == cap_full || (cap_site == 3 && cap_rendered == " " + cap_full)) cap_existing.complete_text_drawn = true;
    if (array_length(cap_sm_record.samples) < 8 && cap_sm_last_sample_draw != cap_sm_record.draw_events) {
        var cap_samples = cap_sm_record.samples;
        var cap_basex = x + 70;
        var cap_basey = y + (cap_site == 1 ? 10 : 15);
        if (cap_pass == "gui") { cap_basex -= cx; cap_basey -= cy; }
        cap_samples[array_length(cap_samples)] = {kind: "text", site: cap_site, pass: cap_pass,
            offset_x: cap_xx - cap_basex, offset_y: cap_yy - cap_basey, alpha: draw_get_alpha()};
        cap_sm_record.samples = cap_samples;
        cap_sm_last_sample_draw = cap_sm_record.draw_events;
    }
}
