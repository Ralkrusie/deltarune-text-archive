// CH2 obj_writer actual text calls only. Wrappers evaluate original arguments once.
// Random offsets / cyclic phases are diagnostic samples, never style identifiers.
function cap_style_init() {
    cap_style_states = [];
    cap_style_points = [];
    cap_style_samples = [];
    cap_style_sample_counts = [];
    cap_style_sample_frames = [];
    cap_style_changes = [];
    cap_style_lookup = ds_map_create();
    cap_style_last = ds_map_create();
    cap_style_max_index = 0;
    cap_style_overflow = false;
    cap_style_us = 0;
    cap_style_calls = 0;
    cap_style_max_us = 0;
}
function cap_style_record(cap_xx, cap_yy, cap_text, cap_sx, cap_sy, cap_rotation,
    cap_c1, cap_c2, cap_c3, cap_c4, cap_call_alpha, cap_site) {
    if (!cap_open || n < 1 || cap_text == "" || n > string_length(mystring)) return;
    if (n > 8192) { cap_style_overflow = true; cap_overflow = true; return; }
    var cap_started = get_timer();
    var cap_layer = (cap_site == 19 ? i : 0);
    var cap_shake = (cap_site <= 5 ? shake : 0);
    var cap_gain = (cap_site >= 6 && cap_site <= 14 ? specfade : 1);
    var cap_alpha = draw_get_alpha();
    var cap_static_alpha = (cap_site <= 5 || (cap_site >= 15 && cap_site <= 18) ? cap_alpha : 1);
    var cap_font = draw_get_font();
    var cap_key = json_stringify([cap_site, cap_layer, cap_font, cap_c1, cap_c2, cap_c3, cap_c4,
        cap_sx, cap_sy, cap_rotation, cap_call_alpha, cap_static_alpha, cap_shake, cap_gain]);
    var cap_state;
    if (ds_map_exists(cap_style_lookup, cap_key)) cap_state = ds_map_find_value(cap_style_lookup, cap_key);
    else {
        cap_state = array_length(cap_style_states);
        if (cap_state >= 128) { cap_style_overflow = true; cap_overflow = true; return; }
        ds_map_add(cap_style_lookup, cap_key, cap_state);
        var cap_motion = "none";
        if (cap_site <= 5 && cap_shake != 0) cap_motion = "random_xy";
        if (cap_site >= 15 && cap_site <= 18) cap_motion = "orbit";
        if (cap_site == 19) cap_motion = "drifting_trail";
        var cap_alpha_model = "constant";
        if (cap_site == 6) cap_alpha_model = "gain";
        if (cap_site >= 7 && cap_site <= 10) cap_alpha_model = "glow_axial";
        if (cap_site >= 11 && cap_site <= 14) cap_alpha_model = "glow_diagonal";
        if (cap_site == 19) cap_alpha_model = "trail_fade";
        var cap_divisor = 0;
        if (cap_site == 15) cap_divisor = 4;
        if (cap_site == 16) cap_divisor = 5;
        if (cap_site == 17) cap_divisor = 7;
        if (cap_site == 18) cap_divisor = 9;
        cap_style_states[cap_state] = {site: cap_site, layer: cap_layer, font_id: cap_font,
            font_name: (cap_font >= 0 ? font_get_name(cap_font) : "default"),
            colors_bgr: [cap_c1, cap_c2, cap_c3, cap_c4], scale_x: cap_sx, scale_y: cap_sy,
            rotation: cap_rotation, call_alpha: cap_call_alpha, global_alpha: cap_static_alpha,
            alpha_model: cap_alpha_model, gain: cap_gain, motion: cap_motion,
            shake: cap_shake, orbit_divisor: cap_divisor, trail_updates_observed: false};
        cap_style_points[cap_state] = [];
        cap_style_sample_counts[cap_state] = 0;
        cap_style_sample_frames[cap_state] = -1;
    }
    // This branch only advances shared trail offsets when formatted index n == 1.
    if (cap_site == 19 && n == 1) {
        var cap_trail_state = cap_style_states[cap_state];
        cap_trail_state.trail_updates_observed = true;
    }
    if (n > cap_style_max_index) cap_style_max_index = n;
    var cap_pts = cap_style_points[cap_state];
    for (var cap_p = array_length(cap_pts); cap_p <= n; cap_p++) cap_pts[cap_p] = 0;
    cap_pts[n] = 1;
    cap_style_points[cap_state] = cap_pts;
    var cap_position_key = string(cap_site) + ":" + string(cap_layer) + ":" + string(n);
    if (ds_map_exists(cap_style_last, cap_position_key)) {
        var cap_previous = ds_map_find_value(cap_style_last, cap_position_key);
        if (cap_previous != cap_state) {
            if (array_length(cap_style_changes) < 512)
                cap_style_changes[array_length(cap_style_changes)] = {formatted_index: n, from_state: cap_previous, to_state: cap_state};
            else { cap_style_overflow = true; cap_overflow = true; }
        }
    }
    if (ds_map_exists(cap_style_last, cap_position_key)) ds_map_replace(cap_style_last, cap_position_key, cap_state);
    else ds_map_add(cap_style_last, cap_position_key, cap_state);
    if (cap_style_sample_counts[cap_state] < 2 && cap_style_sample_frames[cap_state] != cap_draws) {
        cap_style_samples[array_length(cap_style_samples)] = {state_index: cap_state, formatted_index: n,
            draw: cap_draws, offset_x: cap_xx - wx, offset_y: cap_yy - wy, alpha: cap_alpha, phase: siner};
        cap_style_sample_counts[cap_state]++;
        cap_style_sample_frames[cap_state] = cap_draws;
    }
    var cap_elapsed = get_timer() - cap_started;
    cap_style_us += cap_elapsed;
    cap_style_calls++;
    cap_style_max_us = max(cap_style_max_us, cap_elapsed);
}
function cap_style_finish() {
    var cap_spans = [];
    for (var cap_s = 0; cap_s < array_length(cap_style_states); cap_s++) {
        var cap_pts = cap_style_points[cap_s];
        var cap_start = 0;
        for (var cap_p = 1; cap_p <= array_length(cap_pts); cap_p++) {
            var cap_present = (cap_p < array_length(cap_pts) ? cap_pts[cap_p] : 0);
            if (cap_present && cap_start == 0) cap_start = cap_p;
            if (!cap_present && cap_start != 0) {
                if (array_length(cap_spans) >= 8192) { cap_style_overflow = true; cap_overflow = true; break; }
                cap_spans[array_length(cap_spans)] = {state_index: cap_s, start_index: cap_start, end_index: cap_p};
                cap_start = 0;
            }
        }
    }
    ds_map_destroy(cap_style_lookup);
    ds_map_destroy(cap_style_last);
    return {schema: 1, scope: "ch2_obj_writer_text_calls", states: cap_style_states,
        spans: cap_spans, changes: cap_style_changes, samples: cap_style_samples, overflow: cap_style_overflow};
}
function cap_draw_text(cap_xx, cap_yy, cap_text, cap_site) {
    draw_text(cap_xx, cap_yy, cap_text);
    var cap_c = draw_get_color();
    cap_style_record(cap_xx, cap_yy, cap_text, 1, 1, 0, cap_c, cap_c, cap_c, cap_c, 1, cap_site);
}
function cap_draw_text_transformed(cap_xx, cap_yy, cap_text, cap_sx, cap_sy, cap_rotation, cap_site) {
    draw_text_transformed(cap_xx, cap_yy, cap_text, cap_sx, cap_sy, cap_rotation);
    var cap_c = draw_get_color();
    cap_style_record(cap_xx, cap_yy, cap_text, cap_sx, cap_sy, cap_rotation, cap_c, cap_c, cap_c, cap_c, 1, cap_site);
}
function cap_draw_text_color(cap_xx, cap_yy, cap_text, cap_c1, cap_c2, cap_c3, cap_c4, cap_alpha, cap_site) {
    draw_text_color(cap_xx, cap_yy, cap_text, cap_c1, cap_c2, cap_c3, cap_c4, cap_alpha);
    cap_style_record(cap_xx, cap_yy, cap_text, 1, 1, 0, cap_c1, cap_c2, cap_c3, cap_c4, cap_alpha, cap_site);
}
