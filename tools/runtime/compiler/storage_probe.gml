// Runs before original initialization. Never write before checking the actual root.
var cap_path = string_lower(string_replace_all(game_save_id, chr(92), "/"));
while (string_length(cap_path) > 0 && string_char_at(cap_path, string_length(cap_path)) == "/")
    cap_path = string_delete(cap_path, string_length(cap_path), 1);
var cap_envroot = string_lower(string_replace_all(environment_get_variable("LOCALAPPDATA"), chr(92), "/"));
while (string_length(cap_envroot) > 0 && string_char_at(cap_envroot, string_length(cap_envroot)) == "/")
    cap_envroot = string_delete(cap_envroot, string_length(cap_envroot), 1);
var cap_envpath = cap_envroot + "/" + string_lower(__PROFILE__);
if (cap_path != __EXPECTED_PATH__ && cap_path != cap_envpath)
{
    show_debug_message("CAPTURE_SAVE_ROOT_MISMATCH:" + cap_path);
    show_error("Capture save isolation failed. No probe files were written.", true);
    exit;
}
var cap_a = "capture_storage_a.tmp";
var cap_b = "capture_storage_b.tmp";
var cap_c = "capture_storage_c.tmp";
if (file_exists(cap_a) || file_exists(cap_b) || file_exists(cap_c) || file_exists("capture_storage.ini"))
{
    show_error("Capture storage probe requires a fresh profile.", true);
    exit;
}
var cap_f = file_text_open_write(cap_a);
file_text_write_string(cap_f, "capture-storage-v1");
file_text_close(cap_f);
cap_f = file_text_open_read(cap_a);
var cap_text = file_text_read_string(cap_f);
file_text_close(cap_f);
file_copy(cap_a, cap_b);
file_rename(cap_b, cap_c);
var cap_copied = file_exists(cap_c) && !file_exists(cap_b);
file_delete(cap_a);
file_delete(cap_c);
ini_open("capture_storage.ini");
ini_write_string("capture", "profile", __PROFILE__);
ini_close();
ini_open("capture_storage.ini");
var cap_ini = ini_read_string("capture", "profile", "missing");
ini_close();
file_delete("capture_storage.ini");
var cap_ok = cap_text == "capture-storage-v1" && cap_copied && cap_ini == __PROFILE__
    && !file_exists(cap_a) && !file_exists(cap_c) && !file_exists("capture_storage.ini");
cap_f = file_text_open_write("capture_storage_report.json");
file_text_write_string(cap_f, json_stringify({schema: 1, kind: "storage_selftest",
    profile: __PROFILE__, actual_save_path: game_save_id, passed: cap_ok,
    write_read: cap_text == "capture-storage-v1", copy_rename: cap_copied,
    ini_read_write: cap_ini == __PROFILE__, normal_game_started: false}));
file_text_close(cap_f);
// The stripped boot object's next Step ends the process cleanly.
