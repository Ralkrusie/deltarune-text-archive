// Independent sidecar. Tokens follow message writes/command queues, never elapsed time.
function cap_ix_emit(cap_event) {
    global.cap_ix_seq++;
    cap_event.seq = global.cap_ix_seq;
    cap_event.io_failed = global.cap_ix_io_failed;
    var cap_file = file_text_open_append(global.cap_ix_log);
    if (cap_file < 0) { global.cap_ix_io_failed = true; return; }
    file_text_write_string(cap_file, json_stringify(cap_event) + chr(10));
    file_text_close(cap_file);
}
function cap_ix_asset(cap_sprite, cap_frame) {
    if (cap_sprite < 0 || !sprite_exists(cap_sprite)) return {id: -1, name: "", frame: -1, frames: 0};
    var cap_frames = sprite_get_number(cap_sprite);
    return {id: cap_sprite, name: sprite_get_name(cap_sprite), frames: cap_frames,
        frame: cap_frames > 0 ? ((floor(cap_frame) mod cap_frames) + cap_frames) mod cap_frames : -1};
}
function cap_ix_begin() {
    var cap_previous = global.cap_ix_active;
    global.cap_ix_count++;
    global.cap_ix_active = global.cap_ix_count;
    // A new interaction cannot inherit leftover slots from the previous dispatch.
    global.cap_ix_slots = array_create(100, 0);
    global.cap_ch_slots = array_create(100, 0);
    var cap_cafe = undefined;
    if (object_index == obj_npc_cafe) {
        cap_cafe = {evidence: "source_verified_cafe_draw_inputs_at_dispatch", seat: seat,
            recruit_id: global.flag[800 + seat], mode: mode,
            sprite: cap_ix_asset(mode == 1 ? _sprite : remsprite, image_index_fake)};
    }
    cap_ix_emit({kind: "interaction", interaction_id: global.cap_ix_active, parent_id: cap_previous,
        target_instance_id: id, x: x, y: y,
        snapshot: {room_name: room_get_name(room), object: object_get_name(object_index),
            sprite: cap_ix_asset(sprite_index, image_index), mask: cap_ix_asset(mask_index, 0),
            visible: visible, scale_x: image_xscale, scale_y: image_yscale, rotation: image_angle,
            blend: image_blend, alpha: image_alpha, image_speed: image_speed,
            bounds_relative: [bbox_left-x, bbox_top-y, bbox_right-x, bbox_bottom-y],
            evidence: "configured_instance_at_confirm_dispatch", cafe_draw_inputs: cap_cafe}});
    return cap_previous;
}
function cap_ix_end(cap_previous) {
    cap_ix_emit({kind: "dispatch_end", interaction_id: global.cap_ix_active});
    global.cap_ix_active = cap_previous;
}
function cap_ix_interact() {
    var cap_previous = cap_ix_begin();
    scr_interact();
    cap_ix_end(cap_previous);
}
function cap_ix_slot(cap_slot, cap_value) {
    if (cap_slot < 0 || cap_slot >= 100) return;
    global.cap_ix_slots[cap_slot] = global.cap_ix_active;
    global.cap_ix_texts[cap_slot] = cap_value;
    global.cap_ch_slots[cap_slot] = global.cap_ch_active;
}
function cap_ix_copy_slot(cap_j) {
    var cap_token = global.cap_ix_slots[cap_j];
    if (global.cap_ix_texts[cap_j] != global.msg[cap_j]) cap_token = 0;
    // An unowned first page must not revive tagged tail slots in a recycled buffer.
    if (global.cap_ix_slots[0] == 0) cap_token = 0;
    cap_ix_tokens[cap_j] = cap_token;
    cap_ix_originals[cap_j] = global.msg[cap_j];
    cap_ch_tokens[cap_j] = (global.cap_ix_texts[cap_j] == global.msg[cap_j] && global.cap_ch_slots[0] > 0) ? global.cap_ch_slots[cap_j] : 0;
}
function cap_ix_page(cap_source_id) {
    var cap_token = 0;
    if (variable_instance_exists(id, "cap_ix_tokens") && msgno >= 0 && msgno < 100) {
        if (mystring == cap_ix_originals[msgno]) cap_token = cap_ix_tokens[msgno];
    }
    cap_ix_emit({kind: "message_link", interaction_id: cap_token, message_id: cap_message,
        source_id: cap_source_id, writer_id: id, page: msgno,
        relation: cap_token > 0 ? "propagated_message_token" : "no_proven_interaction"});
}
function cap_ix_command_token(cap_index) {
    if (!variable_instance_exists(id, "cap_ix_commands")) return 0;
    if (cap_index < 0 || cap_index >= array_length(cap_ix_commands)) return 0;
    return cap_ix_commands[cap_index];
}
