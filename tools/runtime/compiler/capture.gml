// CH2 source/consumer, identity, sprite and text style evidence.
// Bounded buffers, with write invalidation and value checks. No text lookup.
function cap_local_value(cap_tag, cap_text, cap_sid) { cap_tag.source = cap_sid; return cap_text; }
function cap_local_msgset(cap_slot, cap_text, cap_tag) {
    msgset(cap_slot, cap_text);
    global.cap_source[cap_slot] = cap_tag.source;
}
function cap_local_msgnext(cap_text, cap_tag) {
    msgnext(cap_text);
    global.cap_source[global.msgno] = cap_tag.source;
}
function cap_local_itemget() {
    var cap_tag = argument[0];
    global.cap_item_return_source = 0;
    var cap_text = "";
    if (argument_count == 3) cap_text = scr_itemget_anytype_text(argument[1], argument[2]);
    else cap_text = scr_itemget_anytype_text(argument[1], argument[2], argument[3]);
    cap_tag.source = global.cap_item_return_source;
    if (argument_count == 4 && argument[3] != "" && argument[3] != "/" && argument[3] != "/%" && argument[3] != "%") cap_tag.source = 0;
    global.cap_item_return_source = 0;
    return cap_text;
}
function cap_btl_bind_slot(cap_slot, cap_text, cap_sid) {
    if (!variable_global_exists("cap_btl_sources")) {
        global.cap_btl_sources = array_create(100, 0);
        global.cap_btl_texts = array_create(100, "");
    }
    global.cap_btl_sources[cap_slot] = cap_sid;
    global.cap_btl_texts[cap_slot] = cap_text;
    return cap_text;
}
function cap_btl_clear_slot(cap_slot, cap_text) { return cap_btl_bind_slot(cap_slot, cap_text, 0); }
function cap_btl_to_msg(cap_slot, cap_from, cap_text) {
    var cap_sid = 0;
    if (variable_global_exists("cap_btl_sources") && cap_from >= 0 && cap_from < array_length(global.cap_btl_sources)) {
        if (global.cap_btl_texts[cap_from] == cap_text) cap_sid = global.cap_btl_sources[cap_from];
    }
    return cap_bind_slot(cap_slot, cap_text, cap_sid);
}
function cap_dlg_bind_slot(cap_slot, cap_text, cap_sid) {
    if (!variable_instance_exists(id, "cap_dlg_sources")) {
        cap_dlg_sources = array_create(100, 0);
        cap_dlg_texts = array_create(100, "");
    }
    cap_dlg_sources[cap_slot] = cap_sid;
    cap_dlg_texts[cap_slot] = cap_text;
    return cap_text;
}
function cap_dlg_clear_slot(cap_slot, cap_text) { return cap_dlg_bind_slot(cap_slot, cap_text, 0); }
function cap_dlg_msgset(cap_slot, cap_text) {
    var cap_sid = 0;
    if (variable_instance_exists(id, "cap_dlg_sources") && cap_slot >= 0 && cap_slot < array_length(cap_dlg_sources)) {
        if (cap_dlg_texts[cap_slot] == cap_text) cap_sid = cap_dlg_sources[cap_slot];
    }
    msgset(cap_slot, cap_text);
    global.cap_source[cap_slot] = cap_sid;
}
function cap_clear_buffer(cap_value)
{
    global.cap_source = array_create(100, 0);
    global.cap_ix_slots = array_create(100, 0);
    global.cap_ch_slots = array_create(100, 0);
    return cap_value;
}
function cap_clear_slot(cap_slot, cap_text)
{
    global.cap_source[cap_slot] = 0;
    cap_ix_slot(cap_slot, cap_text);
    return cap_text;
}
function cap_bind_slot(cap_slot, cap_text, cap_source_id)
{
    global.cap_source[cap_slot] = cap_source_id;
    cap_ix_slot(cap_slot, cap_text);
    return cap_text;
}
function cap_msgsetloc(cap_slot, cap_text, cap_key, cap_source_id)
{
    msgsetloc(cap_slot, cap_text, cap_key);
    global.cap_source[cap_slot] = cap_source_id;
}
function cap_msgnextloc(cap_text, cap_key, cap_source_id)
{
    msgnextloc(cap_text, cap_key);
    global.cap_source[global.msgno] = cap_source_id;
}
function cap_c_msgsetloc(cap_slot, cap_text, cap_key, cap_source_id)
{
    c_msgsetloc(cap_slot, cap_text, cap_key);
    if (instance_exists(obj_cutscene_master))
        obj_cutscene_master.cap_command[obj_cutscene_master.maximum_command - 2] = cap_source_id;
}
function cap_c_msgnextloc(cap_text, cap_key, cap_source_id)
{
    c_msgnextloc(cap_text, cap_key);
    if (instance_exists(obj_cutscene_master))
        obj_cutscene_master.cap_command[obj_cutscene_master.maximum_command - 2] = cap_source_id;
}
function cap_queue_source(cap_index)
{
    if (!variable_instance_exists(id, "cap_command")) return 0;
    if (cap_index < 0 || cap_index >= array_length(cap_command)) return 0;
    return cap_command[cap_index];
}
function cap_flush()
{
    if (global.cap_buffer != "")
    {
        var cap_file = file_text_open_append(global.cap_log);
        if (cap_file >= 0)
        {
            file_text_write_string(cap_file, global.cap_buffer);
            file_text_close(cap_file);
            global.cap_buffer = "";
        }
        else
            global.cap_io_failed = true;
    }
}

// Attribute schema 2: one page entry plus one final observation; never one log per glyph.
function cap_emit(cap_event) {
    global.cap_sequence++;
    cap_event.seq = global.cap_sequence;
    global.cap_buffer += json_stringify(cap_event) + chr(10);
    cap_flush();
}
function cap_observe(cap_trigger = "draw") {
    if (!variable_instance_exists(id, "cap_open")) cap_open = false;
    if (cap_open && cap_page == msgno) return;
    if (cap_open) cap_finish("page_changed_outside_nextmsg");
    global.cap_message++;
    cap_message = global.cap_message;
    cap_page = msgno;
    cap_open = true;
    cap_style_init();
    cap_smallfaces = [];
    cap_states = [];
    cap_positions = [];
    cap_assets = [];
    cap_asset_keys = [];
    cap_has_consumed = false;
    cap_overflow = false;
    cap_draws = 0;
    cap_face_frames = 0;
    cap_face_wait_frames = 0;
    cap_x = false;
    cap_ctrl = false;
    cap_fast = false;
    cap_advance = false;
    cap_confirm_pending = false;
    cap_advance_wait = 0;
    cap_advance_guard = "not_requested";
    cap_portrait_ready = false;
    cap_last_face = -1;
    cap_last_expression = -1;
    cap_formatted = "";
    var cap_id = 0;
    if (msgno >= 0 && msgno < array_length(cap_sources)) cap_id = cap_sources[msgno];
    if (mystring != nstring[msgno]) cap_id = 0;
    cap_emit({kind: "observation", message_id: cap_message, source_id: cap_id,
        language: global.lang, channel: "obj_writer", room_name: room_get_name(room),
        writer_id: id, page: msgno, text: mystring, stage: "page_enter", trigger: cap_trigger,
        partial: true, io_failed: global.cap_io_failed});
    cap_ix_page(cap_id);
    cap_ch_page(cap_id);
}
function cap_input() {
    if (!cap_open) return;
    cap_draws++;
    if (global.input_held[5]) cap_x = true;
    if (global.input_held[9]) cap_ctrl = true;
    if (skipme == 1 || (halt == 0 && button2 == 1 && pos < length && skippable == 1)) cap_fast = true;
}
function cap_consume() {
    if (!cap_open) return;
    cap_formatted = mystring;
    // The original choice renderer can walk beyond the string and draw an empty glyph.
    if (n < 1 || n > string_length(mystring) || mychar == "") return;
    cap_has_consumed = true;
    if (cap_last_face != global.fc || cap_last_expression != global.fe) cap_portrait_ready = false;
    cap_last_face = global.fc;
    cap_last_expression = global.fe;
    var cap_state = -1;
    for (var cap_i = 0; cap_i < array_length(cap_states); cap_i++) {
        var cap_s = cap_states[cap_i];
        if (cap_s.face_code == global.fc && cap_s.expression == global.fe && cap_s.typer == global.typer) cap_state = cap_i;
    }
    if (cap_state < 0) {
        if (array_length(cap_states) >= 64) { cap_overflow = true; return; }
        cap_state = array_length(cap_states);
        cap_states[cap_state] = {face_code: global.fc, expression: global.fe, typer: global.typer};
    }
    if (n > 8192) { cap_overflow = true; return; }
    // 0 means no glyph was consumed at this formatted-string position.
    if (array_length(cap_positions) <= n) {
        for (var cap_j = array_length(cap_positions); cap_j <= n; cap_j++) cap_positions[cap_j] = 0;
    }
    cap_positions[n] = cap_state + 1;
}
function cap_record_asset(cap_sprite, cap_frame, cap_xx, cap_yy, cap_sx, cap_sy, cap_rot, cap_color, cap_alpha, cap_site, cap_role) {
    var cap_writer = id;
    if (cap_role == "portrait") {
        if (!variable_instance_exists(id, "cap_owner")) return;
        cap_writer = cap_owner;
    }
    if (!instance_exists(cap_writer)) return;
    if (!variable_instance_exists(cap_writer, "cap_open")) return;
    if (!cap_writer.cap_open || cap_writer.cap_page != cap_writer.msgno) return;
    if (cap_role == "portrait" && !cap_writer.cap_has_consumed) return;
    if (cap_role == "portrait") cap_frame_assets++;
    var cap_index = -1;
    if (cap_role == "inline") cap_index = n;
    var cap_frames = sprite_get_number(cap_sprite);
    var cap_selected = floor(cap_frame == -1 ? image_index : cap_frame);
    if (cap_frames > 0) cap_selected = ((cap_selected mod cap_frames) + cap_frames) mod cap_frames;
    var cap_asset = {sprite_id: cap_sprite, sprite_name: sprite_get_name(cap_sprite),
        subimage: cap_selected, requested_subimage: cap_frame, frame_count: cap_frames,
        site: cap_site, role: cap_role, formatted_index: cap_index,
        face_code: global.fc, expression: global.fe, scale_x: cap_sx, scale_y: cap_sy,
        rotation: cap_rot, blend: cap_color, alpha: cap_alpha,
        relative_x: cap_xx - cap_writer.x, relative_y: cap_yy - cap_writer.y};
    var cap_key = json_stringify(cap_asset);
    with (cap_writer) {
        for (var cap_k = 0; cap_k < array_length(cap_asset_keys); cap_k++) {
            if (cap_asset_keys[cap_k] == cap_key) return;
        }
        if (array_length(cap_assets) >= 256) { cap_overflow = true; return; }
        cap_asset_keys[array_length(cap_asset_keys)] = cap_key;
        cap_assets[array_length(cap_assets)] = cap_asset;
    }
}
function cap_draw_sprite_ext(cap_sprite, cap_frame, cap_xx, cap_yy, cap_sx, cap_sy, cap_rot, cap_color, cap_alpha, cap_site, cap_role) {
    draw_sprite_ext(cap_sprite, cap_frame, cap_xx, cap_yy, cap_sx, cap_sy, cap_rot, cap_color, cap_alpha);
    cap_record_asset(cap_sprite, cap_frame, cap_xx, cap_yy, cap_sx, cap_sy, cap_rot, cap_color, cap_alpha, cap_site, cap_role);
}
function cap_draw_sprite(cap_sprite, cap_frame, cap_xx, cap_yy, cap_site, cap_role) {
    draw_sprite(cap_sprite, cap_frame, cap_xx, cap_yy);
    cap_record_asset(cap_sprite, cap_frame, cap_xx, cap_yy, 1, 1, 0, c_white, 1, cap_site, cap_role);
}
function cap_face_status(cap_waiting) {
    cap_frame_assets = 0;
    if (!variable_instance_exists(id, "cap_owner")) return;
    if (!instance_exists(cap_owner)) return;
    if (!variable_instance_exists(cap_owner, "cap_open")) return;
    if (!cap_owner.cap_open) return;
    cap_owner.cap_face_frames++;
    if (cap_waiting) cap_owner.cap_face_wait_frames++;
}
// Called after the entire face Draw, so a first layer cannot prematurely release a page.
function cap_face_complete() {
    if (!variable_instance_exists(id, "cap_owner") || cap_frame_assets <= 0) return;
    if (!instance_exists(cap_owner)) return;
    if (!variable_instance_exists(cap_owner, "cap_open")) return;
    if (!cap_owner.cap_open || cap_owner.cap_page != cap_owner.msgno) return;
    if (!variable_instance_exists(cap_owner, "cap_portrait_instance")) return;
    if (cap_owner.cap_portrait_instance != id) return;
    if (cap_owner.cap_last_face == global.fc && cap_owner.cap_last_expression == global.fe)
        cap_owner.cap_portrait_ready = true;
}
function cap_gate_advance() {
    if (!cap_open) return;
    // Script-directed progression and choicers keep their original behavior.
    if (forcebutton1 || (halt != 1 && halt != 2)) { cap_confirm_pending = false; return; }
    if (siner <= 0 || (!button1 && !cap_confirm_pending)) return;
    cap_advance = true;
    var cap_expected = false;
    if (cap_has_consumed && global.fc > 0 && variable_instance_exists(id, "cap_portrait_instance")) {
        if (instance_exists(cap_portrait_instance)) {
            if (variable_instance_exists(cap_portrait_instance, "cap_owner"))
                cap_expected = (cap_portrait_instance.cap_owner == id);
        }
    }
    if (!cap_expected) cap_advance_guard = "not_applicable";
    else if (cap_portrait_ready && cap_last_face == global.fc && cap_last_expression == global.fe)
        cap_advance_guard = "portrait_pass_complete";
    else if (cap_advance_wait >= 4) cap_advance_guard = "timeout_partial";
    else {
        cap_confirm_pending = true;
        cap_advance_wait++;
        cap_advance_guard = "waiting";
        button1 = 0;
        return;
    }
    cap_confirm_pending = false;
    button1 = 1;
}
function cap_finish(cap_reason) {
    if (!variable_instance_exists(id, "cap_open")) return;
    if (!cap_open) return;
    cap_open = false;
    var cap_spans = [];
    var cap_start = 0;
    var cap_last = 0;
    for (var cap_i = 0; cap_i <= array_length(cap_positions); cap_i++) {
        var cap_current = 0;
        if (cap_i < array_length(cap_positions)) cap_current = cap_positions[cap_i];
        if (cap_current != cap_last) {
            if (cap_last > 0) cap_spans[array_length(cap_spans)] = {start_index: cap_start, end_index: cap_i, state_index: cap_last - 1};
            cap_start = cap_i;
            cap_last = cap_current;
        }
    }
    cap_emit({kind: "attributes", message_id: cap_message, page: cap_page, writer_id: id,
        reason: cap_reason, formatted_text: cap_formatted, index_space: "formatted_mystring_1based",
        identity_states: cap_states, identity_spans: cap_spans, assets: cap_assets,
        text_styles: cap_style_finish(),
        smallfaces: cap_smallfaces,
        telemetry: {x_held: cap_x, ctrl_held: cap_ctrl, fast_reveal: cap_fast,
            advance_requested: cap_advance, draw_calls: cap_draws, glyphs_consumed: cap_has_consumed,
            portrait_event_calls: cap_face_frames, portrait_wait_calls: cap_face_wait_frames,
            text_style_record_us: cap_style_us, text_style_calls: cap_style_calls, text_style_max_call_us: cap_style_max_us,
            advance_wait_frames: cap_advance_wait, advance_guard: cap_advance_guard},
        overflow: cap_overflow, io_failed: global.cap_io_failed, partial: true});
}
