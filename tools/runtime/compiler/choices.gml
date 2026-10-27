// Choice evidence has its own stream. No most-recent-choice inference.
function cap_ch_emit(cap_event) {
    global.cap_ch_seq++;
    cap_event.seq = global.cap_ch_seq;
    cap_event.io_failed = global.cap_ch_io_failed;
    var cap_file = file_text_open_append(global.cap_ch_log);
    if (cap_file < 0) { global.cap_ch_io_failed = true; return; }
    file_text_write_string(cap_file, json_stringify(cap_event) + chr(10));
    file_text_close(cap_file);
}
function cap_ch_clear_slot(cap_slot, cap_text) {
    if (cap_slot >= 0 && cap_slot < 100) {
        global.cap_ch_sources[cap_slot] = 0;
        global.cap_ch_texts[cap_slot] = cap_text;
    }
    return cap_text;
}
function cap_ch_bind_slot(cap_slot, cap_text, cap_source) {
    cap_ch_clear_slot(cap_slot, cap_text);
    if (cap_slot >= 0 && cap_slot < 100) global.cap_ch_sources[cap_slot] = cap_source;
    return cap_text;
}
function cap_ch_options() {
    var cap_options = [];
    for (var cap_i = 0; cap_i < cap_ch_count; cap_i++) {
        var cap_text = "";
        var cap_source = 0;
        if (cap_ch_type == "neo") {
            cap_text = global.choicemsg[cap_i];
            if (cap_text == global.cap_ch_texts[cap_i]) cap_source = global.cap_ch_sources[cap_i];
        }
        cap_options[cap_i] = {slot: cap_i, text: cap_text, source_id: cap_source,
            text_status: cap_ch_type == "neo" ? "configured_option" : "embedded_in_parent_not_split"};
    }
    return cap_options;
}
function cap_ch_attach(cap_child, cap_type) {
    if (!instance_exists(cap_child) || !cap_open) return;
    if (variable_instance_exists(cap_child, "cap_ch_id")) return;
    global.cap_ch_count++;
    cap_child.cap_ch_id = global.cap_ch_count;
    cap_child.cap_ch_parent_writer = id;
    cap_child.cap_ch_parent_message = cap_message;
    cap_child.cap_ch_type = cap_type;
    cap_child.cap_ch_count = cap_type == "neo" ? cap_child.choicetotal + 1 : 2;
    cap_child.cap_ch_confirmed = -1;
    cap_child.cap_ch_keys = [];
    cap_child.cap_ch_overflow = false;
    cap_child.cap_ch_ended = false;
    cap_child.cap_ch_interaction = 0;
    if (msgno >= 0 && msgno < 100 && mystring == cap_ix_originals[msgno])
        cap_child.cap_ch_interaction = cap_ix_tokens[msgno];
    with (cap_child) {
        cap_ch_emit({kind: "choice_open", choice_id: cap_ch_id, parent_message_id: cap_ch_parent_message,
            parent_writer_id: cap_ch_parent_writer, interaction_id: cap_ch_interaction,
            selector_type: cap_ch_type, options: cap_ch_options()});
    }
}
function cap_ch_draw_text(cap_x, cap_y, cap_text) {
    draw_text(cap_x, cap_y, cap_text);
    if (!variable_instance_exists(id, "cap_ch_id")) return;
    var cap_font = draw_get_font();
    var cap_source = 0;
    if (global.choicemsg[i] == global.cap_ch_texts[i]) cap_source = global.cap_ch_sources[i];
    var cap_state = {slot: i, text: global.choicemsg[i], rendered_text: cap_text, source_id: cap_source,
        selected: mychoice == i, font_id: cap_font, font_name: cap_font >= 0 ? font_get_name(cap_font) : "default",
        color_bgr: draw_get_color(), alpha: draw_get_alpha()};
    var cap_key = json_stringify(cap_state);
    for (var cap_j = 0; cap_j < array_length(cap_ch_keys); cap_j++) if (cap_ch_keys[cap_j] == cap_key) return;
    if (array_length(cap_ch_keys) >= 128) { cap_ch_overflow = true; return; }
    cap_ch_keys[array_length(cap_ch_keys)] = cap_key;
    cap_ch_emit({kind: "choice_draw", choice_id: cap_ch_id, state: cap_state});
}
function cap_ch_confirm() {
    if (!variable_instance_exists(id, "cap_ch_id") || cap_ch_confirmed >= 0) return;
    cap_ch_confirmed = global.choice;
    cap_ch_emit({kind: "choice_confirm", choice_id: cap_ch_id, selected_slot: cap_ch_confirmed,
        options: cap_ch_options(), observed_states: array_length(cap_ch_keys)});
}
function cap_ch_end(cap_reason) {
    if (!variable_instance_exists(id, "cap_ch_id") || cap_ch_ended) return;
    cap_ch_ended = true;
    cap_ch_emit({kind: "choice_end", choice_id: cap_ch_id, reason: cap_reason,
        selected_slot: cap_ch_confirmed, overflow: cap_ch_overflow});
}
function cap_ch_reply(cap_selector) {
    // Called in the original dialoguer Alarm continuation, retaining its original two calls.
    var cap_previous = global.cap_ch_active;
    var cap_ix_previous = global.cap_ix_active;
    global.cap_ch_active = 0;
    global.cap_ix_active = 0;
    if (instance_exists(cap_selector) && variable_instance_exists(cap_selector, "cap_ch_id")) {
        if (writer == cap_selector.cap_ch_parent_writer && cap_selector.cap_ch_confirmed >= 0
            && global.choice == cap_selector.cap_ch_confirmed) {
            global.cap_ch_active = cap_selector.cap_ch_id;
            global.cap_ix_active = cap_selector.cap_ch_interaction;
        }
    }
    scr_text(global.msc);
    event_user(0);
    global.cap_ch_active = cap_previous;
    global.cap_ix_active = cap_ix_previous;
}
function cap_ch_page(cap_source) {
    var cap_token = 0;
    if (msgno >= 0 && msgno < 100 && mystring == cap_ix_originals[msgno]) cap_token = cap_ch_tokens[msgno];
    cap_ch_emit({kind: "message_link", choice_id: cap_token, message_id: cap_message,
        source_id: cap_source, writer_id: id, page: msgno,
        relation: cap_token > 0 ? "explicit_choice_continuation" : "no_proven_choice"});
}
function cap_ch_command_token(cap_index) {
    if (!variable_instance_exists(id, "cap_ch_commands")) return 0;
    if (cap_index < 0 || cap_index >= array_length(cap_ch_commands)) return 0;
    return cap_ch_commands[cap_index];
}
