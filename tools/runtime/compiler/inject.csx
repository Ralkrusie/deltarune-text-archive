using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Underanalyzer.Decompiler;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Compiler;

EnsureDataLoaded();
string configPath = Environment.GetEnvironmentVariable("DR_CAPTURE_CONFIG");
string build = Path.GetDirectoryName(configPath);
var config = JObject.Parse(File.ReadAllText(configPath));
var inventory = JObject.Parse(File.ReadAllText(Path.Combine(build, "sources.json")));
var profile = (string)config["profile"];
if (Data.GeneralInfo.Name.Content != "DELTARUNE" || Data.GeneralInfo.DisplayName.Content != "DELTARUNE Chapter 2")
    throw new Exception("Expected original CH2");
var dc = new GlobalDecompileContext(Data);
var settings = new DecompileSettings { RemoveSingleLineBlockBraces = true,
    OpenBlockBraceOnSameLine = false, EmptyLineAroundBranchStatements = false };
string Original(string name) => new DecompileContext(dc, Data.Code.ByName(name), settings).DecompileToString();
string Hash(string text) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text))).ToLowerInvariant();
var texts = new System.Collections.Generic.Dictionary<string, string>();
foreach (var property in ((JObject)inventory["patches"]).Properties())
{
    if (Hash(Original(property.Name).Trim()) != (string)property.Value)
        throw new Exception("Actual package/source mismatch: " + property.Name);
    texts[property.Name] = File.ReadAllText(Path.Combine(build, "patches", property.Name + ".gml"));
}
void ReplaceOnce(string name, string oldText, string newText)
{
    string t = texts.ContainsKey(name) ? texts[name] : Original(name);
    if (t.Split(new[] {oldText}, StringSplitOptions.None).Length != 2)
        throw new Exception("Expected exactly one mechanism anchor: " + name + " / " + oldText);
    texts[name] = t.Replace(oldText, newText);
}
ReplaceOnce("gml_Object_obj_npc_cafe_Other_10", "msgset(j, _dialogue[j]);", "cap_dlg_msgset(j, _dialogue[j]);");
// This recipe describes the cafe Draw inputs, not an observed Draw or a speaker label.
foreach (var name in new[] { "gml_Object_obj_npc_cafe_Draw_0", "gml_Object_obj_npc_cafe_Other_16" }) {
    var canonical = File.ReadAllText(Path.Combine((string)config["code_root"], name + ".gml"));
    if (Hash(Original(name).Trim()) != Hash(canonical.Trim())) throw new Exception("Cafe recipe source mismatch: " + name);
}
ReplaceOnce("gml_GlobalScript_c_cmd", "obj_cutscene_master.command[__cs_i] = arg0;",
    "obj_cutscene_master.command[__cs_i] = arg0;\n        obj_cutscene_master.cap_command[__cs_i] = 0;\n        obj_cutscene_master.cap_ix_commands[__cs_i] = global.cap_ix_active;\n        obj_cutscene_master.cap_ch_commands[__cs_i] = global.cap_ch_active;");
ReplaceOnce("gml_GlobalScript_c_cmd_x", "obj_cutscene_master.command[__cs_i] = arg0;",
    "obj_cutscene_master.command[__cs_i] = arg0;\n        obj_cutscene_master.cap_command[__cs_i] = 0;\n        obj_cutscene_master.cap_ix_commands[__cs_i] = global.cap_ix_active;\n        obj_cutscene_master.cap_ch_commands[__cs_i] = global.cap_ch_active;");
ReplaceOnce("gml_GlobalScript_scr_cutscene_master_commands_initialize", "command[i] = \"terminate\";",
    "command[i] = \"terminate\";\n        cap_command[i] = 0;\n        cap_ix_commands[i] = 0;\n        cap_ch_commands[i] = 0;");
foreach (var name in new[] { "gml_GlobalScript_scr_gamestart", "gml_Object_obj_initializer_Create_0" })
    ReplaceOnce(name, "global.msg = \" \";", "global.msg = cap_clear_buffer(\" \");");
ReplaceOnce("gml_GlobalScript_scr_cutscene_commands", "msgset(command_arg1[i], command_arg2[i]);",
    "{ msgset(command_arg1[i], command_arg2[i]); global.cap_source[command_arg1[i]] = cap_queue_source(i); }");
ReplaceOnce("gml_GlobalScript_scr_cutscene_commands", "msgnext(command_arg1[i]);",
    "{ msgnext(command_arg1[i]); global.cap_source[global.msgno] = cap_queue_source(i); }");
ReplaceOnce("gml_Object_obj_writer_Create_0", "nstring[j] = global.msg[j];",
    "{ nstring[j] = global.msg[j]; cap_sources[j] = global.cap_source[j]; cap_ix_copy_slot(j); }");
ReplaceOnce("gml_Object_obj_writer_Create_0", "mystring = global.msg[0];",
    "cap_sources = array_create(100, 0);\ncap_ix_tokens = array_create(100, 0);\ncap_ch_tokens = array_create(100, 0);\ncap_ix_originals = array_create(100, \"\");\nmystring = global.msg[0];");
// Consume global tokens once; the writer owns its frozen copy from now on.
texts["gml_Object_obj_writer_Create_0"] += "\nglobal.cap_ix_slots = array_create(100, 0);\nglobal.cap_ch_slots = array_create(100, 0);\n";
ReplaceOnce("gml_GlobalScript_scr_cutscene_commands", "function scr_cutscene_commands()\n{",
    "function scr_cutscene_commands()\n{\n    var cap_ix_prior = global.cap_ix_active;\n    var cap_ch_prior = global.cap_ch_active;\n    global.cap_ch_active = cap_ch_command_token(i);\n    global.cap_ix_active = cap_ix_command_token(i);");
var ixCommands = texts["gml_GlobalScript_scr_cutscene_commands"];
if (Regex.IsMatch(Original("gml_GlobalScript_scr_cutscene_commands"), @"\b(return|exit)\b")) throw new Exception("Unexpected command early exit");
texts["gml_GlobalScript_scr_cutscene_commands"] = ixCommands.Insert(ixCommands.LastIndexOf('}'), "\n    global.cap_ix_active = cap_ix_prior;\n    global.cap_ch_active = cap_ch_prior;\n");
texts["gml_Object_obj_writer_Draw_0"] = "cap_fixture_before();\ncap_observe();\n" + Original("gml_Object_obj_writer_Draw_0") + "\ncap_fixture_after();\n";
// Capture copy: disable only writer automash; keep normal X reveal and manual confirm.
ReplaceOnce("gml_Object_obj_writer_Draw_0", "if (button3_h() == 1)", "if (false) // capture: Ctrl automash disabled");
ReplaceOnce("gml_Object_obj_writer_Draw_0", "if (halt == 0 && button2 == 1", "cap_input();\nif (halt == 0 && button2 == 1");
ReplaceOnce("gml_Object_obj_writer_Draw_0", "if (accept == 1)\n    {", "if (accept == 1)\n    {\n        cap_consume();");
ReplaceOnce("gml_Object_obj_writer_Draw_0", "if (halt != 0 && button1 == 1 && siner > 0)\n{", "cap_gate_advance();\nif (halt != 0 && button1 == 1 && siner > 0)\n{\n    cap_advance = true;");
ReplaceOnce("gml_GlobalScript_scr_nextmsg", "msgno += 1;", "cap_finish(\"next_page\");\n    msgno += 1;");
ReplaceOnce("gml_GlobalScript_scr_nextmsg", "mystring = nstring[msgno];", "mystring = nstring[msgno];\n    cap_observe(\"next_page\");");
ReplaceOnce("gml_GlobalScript_scr_facechoice", "myface = instance_create(writer.x + (8 * f), writer.y + (5 * f), obj_face);",
    "myface = instance_create(writer.x + (8 * f), writer.y + (5 * f), obj_face);\n    myface.cap_owner = writer;\n    writer.cap_portrait_instance = myface;");
ReplaceOnce("gml_GlobalScript_scr_battletext", "myface = instance_create(xx + 26, yy + 380, obj_face);",
    "myface = instance_create(xx + 26, yy + 380, obj_face);\n    myface.cap_owner = battlewriter;\n    battlewriter.cap_portrait_instance = myface;");
var drawSites = new JArray();
ReplaceOnce("gml_Object_obj_face_Draw_0", "if (facechange <= 0)", "cap_face_status(facechange > 0);\nif (facechange <= 0)");
texts["gml_Object_obj_face_Draw_0"] += "\ncap_face_complete();\n";
foreach (var pair in new[] { ("gml_Object_obj_face_Draw_0", "portrait"), ("gml_Object_obj_writer_Draw_0", "inline") }) {
    string t = texts.ContainsKey(pair.Item1) ? texts[pair.Item1] : Original(pair.Item1);
    t = Regex.Replace(t, @"\b(draw_sprite_ext|draw_sprite)\(([^;\r\n]+)\);", m => {
        int site = drawSites.Count + 1;
        drawSites.Add(new JObject { ["site"] = site, ["code"] = pair.Item1, ["role"] = pair.Item2, ["original_call"] = m.Value });
        return "cap_" + m.Groups[1].Value + "(" + m.Groups[2].Value + ", " + site + ", \"" + pair.Item2 + "\");";
    });
    texts[pair.Item1] = t;
}
File.WriteAllText(Path.Combine(build,"draw-sites.json"),drawSites.ToString());
// Site recipes are bound to the complete audited renderer, not guessed across versions.
var styleSpec = JObject.Parse(File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "text-style-sites.json")));
string styleSourceHash = Hash(Original("gml_Object_obj_writer_Draw_0").Trim());
if (styleSourceHash != (string)styleSpec["source_sha256"]) throw new Exception("Text style renderer changed; re-audit recipes");
int textSite = 0;
texts["gml_Object_obj_writer_Draw_0"] = Regex.Replace(texts["gml_Object_obj_writer_Draw_0"],
    @"\b(draw_text_transformed|draw_text_color|draw_text)\(([^;\r\n]+)\);", m => {
        var expected = styleSpec["sites"][textSite++];
        if (m.Value != (string)expected["original_call"]) throw new Exception("Text style call mismatch");
        return "cap_" + m.Groups[1].Value + "(" + m.Groups[2].Value + ", " + textSite + ");";
    });
if (textSite != 19) throw new Exception("Expected 19 audited writer text calls");
File.WriteAllText(Path.Combine(build,"text-style-sites.json"),styleSpec.ToString());
var smallSpecText = File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "smallface-spec.json"));
var smallSpec = JObject.Parse(smallSpecText);
foreach (var s in ((JObject)smallSpec["sources"]).Properties())
    if (Hash(Original(s.Name).Trim()) != (string)s.Value) throw new Exception("Smallface source changed: " + s.Name);
ReplaceOnce("gml_GlobalScript_scr_smallface_reset", "global.smalarm[arg0] = 5;",
    "global.cap_sm_selector[arg0] = \"\";\n    global.cap_sm_selected_sprite[arg0] = -1;\n    global.smalarm[arg0] = 5;");
ReplaceOnce("gml_GlobalScript_scr_smallface", "global.smstring[arg0] = cap_sm_clear_slot(arg0, arg5);",
    "global.smstring[arg0] = cap_sm_clear_slot(arg0, arg5);\n    cap_sm_selector(arg0, arg1);");
ReplaceOnce("gml_Object_obj_writer_Draw_0", "smallface.writergod = id;",
    "smallface.writergod = id;\n                    cap_sm_attach(smallface, fam, n);");
foreach (var item in new[] { ("gml_Object_obj_smallface_Draw_0", "world"), ("gml_Object_obj_smallface_Draw_64", "gui") }) {
    string t = Original(item.Item1); int count = 0;
    t = Regex.Replace(t, @"\bdraw_sprite_ext\(([^;\r\n]+)\);", m => "cap_sm_sprite(" + m.Groups[1].Value + ", \"" + item.Item2 + "\");");
    t = Regex.Replace(t, @"\bdraw_text\(([^;\r\n]+)\);", m => "cap_sm_draw_text(" + m.Groups[1].Value + ", " + (++count) + ", \"" + item.Item2 + "\");");
    if (count != 3) throw new Exception("Expected three smallface text branches");
    texts[item.Item1] = t;
}
ReplaceOnce("gml_GlobalScript_scr_84_init_localization", "if (!variable_global_exists(\"lang_loaded\"))",
    "global.lang = \"en\";\n    if (!variable_global_exists(\"lang_loaded\"))");
// Full-copy build: preserve the original launcher and chapter-switch implementation.
// Delayed commands have an independently copied command buffer; unknown source.
ReplaceOnce("gml_GlobalScript_scr_cutscene_commands", "delaycmd.command_actor[0] = command_actor[i];",
    "delaycmd.command_actor[0] = command_actor[i];\n        delaycmd.cap_command[0] = 0;\n        delaycmd.cap_ix_commands[0] = cap_ix_command_token(i);\n        delaycmd.cap_ch_commands[0] = cap_ch_command_token(i);");
// Bind choice mechanisms to complete canonical source before patching them.
foreach (var name in new[] { "gml_Object_obj_choicer_neo_Draw_0", "gml_Object_obj_choicer_neo_Other_10", "gml_Object_obj_choicer_old_Other_10", "gml_Object_obj_choicer_neo_Alarm_0", "gml_Object_obj_choicer_old_Alarm_0" }) {
    string canonical = File.ReadAllText(Path.Combine((string)config["code_root"], name + ".gml"));
    if (Hash(Original(name).Trim()) != Hash(canonical.Trim())) throw new Exception("Choice source mismatch: " + name);
}
ReplaceOnce("gml_Object_obj_writer_Draw_0", "choicer = instance_create(0, 0, obj_choicer_old);",
    "{ choicer = instance_create(0, 0, obj_choicer_old); cap_ch_attach(choicer, \"old\"); }");
ReplaceOnce("gml_Object_obj_writer_Draw_0", "choicer.choicetotal = real(nextchar2) - 1;",
    "choicer.choicetotal = real(nextchar2) - 1; cap_ch_attach(choicer, \"neo\");");
ReplaceOnce("gml_Object_obj_choicer_neo_Draw_0", "draw_text(textx, texty, string_hash_to_newline(global.choicemsg[i]));",
    "cap_ch_draw_text(textx, texty, string_hash_to_newline(global.choicemsg[i]));");
foreach (var type in new[] { "old", "neo" }) {
    ReplaceOnce("gml_Object_obj_choicer_" + type + "_Other_10", "global.choice = mychoice;", "global.choice = mychoice; cap_ch_confirm();");
    ReplaceOnce("gml_Object_obj_choicer_" + type + "_Alarm_0", "scr_text(global.msc);\n        event_user(0);", "cap_ch_reply(other);");
}
var group = new CodeImportGroup(Data) { MainThreadAction = MainThreadAction };
foreach (var type in new[] { "old", "neo" })
    group.QueuePrepend("gml_Object_obj_choicer_" + type + "_Step_0", "cap_ch_test_selector();");
// Overlay is bound to the audited CH2 exploration dispatcher; do not enable original debug.
if (Hash(Original("gml_Object_obj_mainchara_Step_0").Trim()) != "2b75ab68f8ff7024893d6f41b072b1f8fa4d3c866e1522e80bf28e361f2edb41"
    || Hash(Original("gml_GlobalScript_scr_interact").Trim()) != "ee4315d80912bad3b3d055571c78177a34fcaaa92a9a5a18eb1397be668ed9b7")
    throw new Exception("Interaction dispatcher changed; re-audit overlay scope");
var ixMain = Original("gml_Object_obj_mainchara_Step_0");
if (ixMain.Split(new[] { "scr_interact();" }, StringSplitOptions.None).Length != 5) throw new Exception("Expected four confirm dispatches");
texts["gml_Object_obj_mainchara_Step_0"] = ixMain.Replace("scr_interact();", "cap_ix_interact();");
if (Data.Code.ByName("gml_Object_obj_time_Draw_73") != null)
    throw new Exception("Unexpected existing time Draw End event");
group.QueueReplace("gml_Object_obj_time_Draw_73", "cap_interaction_draw();\ncap_interaction_test_draw();");
if ((int?)config["test_max_hp"] == 999) {
    var hp = (JObject)JObject.Parse(File.ReadAllText(Path.Combine(build,"hp-patches.json")))["2"];
    foreach (var p in hp.Properties()) {
        if (Hash(Original(p.Name).Trim()) != (string)p.Value["sha256"]) throw new Exception("HP source mismatch: " + p.Name);
        string t = texts.ContainsKey(p.Name) ? texts[p.Name] : Original(p.Name);
        foreach (var edit in (JArray)p.Value["edits"]) {
            if (!t.Contains((string)edit["old"])) throw new Exception("Missing HP anchor: " + p.Name);
            t=t.Replace((string)edit["old"],(string)edit["new"]);
        }
        texts[p.Name]=t;
    }
}
foreach (var p in texts) group.QueueReplace(p.Key, p.Value);
group.QueueReplace("gml_GlobalScript_cap_runtime", File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "capture.gml"))
    + File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "mechanism_test.gml"))
    + File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "styles.gml"))
    + File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "smallface.gml"))
    + File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "attachments_test.gml"))
    + File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "interaction_overlay.gml"))
    + File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "interactions.gml"))
    + File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "interaction_test.gml"))
    + File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "choices.gml"))
    + File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "choices_test.gml"))
    + File.ReadAllText(Path.Combine(build,"substitution_wrappers.gml"))
    + File.ReadAllText(Path.Combine(build,"source_test.gml"))
    + "\nfunction cap_hp_limit(cap_i, cap_value) { if (cap_i >= 1 && cap_i <= 4) return 999; return cap_value; }\n");
foreach (var type in new[] { "old", "neo" }) {
    group.QueueAppend("gml_Object_obj_choicer_" + type + "_Destroy_0", "cap_ch_end(\"destroy\");");
    group.QueueAppend("gml_Object_obj_choicer_" + type + "_Other_3", "cap_ch_end(\"game_end\");");
    group.QueueAppend("gml_Object_obj_choicer_" + type + "_Other_5", "cap_ch_end(\"room_end\");");
}
group.QueueAppend("gml_Object_obj_writer_Destroy_0", "cap_finish(\"destroy\");");
group.QueueAppend("gml_Object_obj_writer_Create_0", "if (string_pos(\"choices\", environment_get_variable(\"DR_CAPTURE_TEST_PACE\")) == 1) cap_fixture = true;");
group.QueueAppend("gml_Object_obj_writer_Other_3", "cap_finish(\"game_end\");");
group.QueueAppend("gml_Object_obj_writer_Other_5", "cap_finish(\"room_end\");");
group.QueueAppend("gml_Object_obj_time_Step_0", @"
cap_interaction_keys();
if (environment_get_variable(""DR_CAPTURE_MECHANISM_TEST"") == ""1"") cap_mechanism_step();
if (environment_get_variable(""DR_CAPTURE_SMOKE"") == ""1"") {
    if (!variable_instance_exists(id, ""cap_smoke_frames"")) cap_smoke_frames = 0;
    cap_smoke_frames++;
    if (cap_smoke_frames == 1) {
        var cap_music = working_directory + ""../mus/menu.ogg"";
        var cap_stream = audio_create_stream(cap_music);
        show_debug_message(""CAPTURE_AUDIO_CHECK "" + json_stringify({path: cap_music,
            exists: file_exists(cap_music), stream_ok: cap_stream >= 0, launcher: global.launcher,
            room_name: room_get_name(room)}));
        if (cap_stream >= 0) audio_destroy_stream(cap_stream);
    }
    if (cap_smoke_frames >= 120) { cap_flush(); game_end(); }
}
");
group.Import();
// Put the added global definitions first, then initialize provenance before original scripts.
var added = Data.GlobalInitScripts.First(s => s.Code.Name.Content == "gml_GlobalScript_cap_runtime");
Data.GlobalInitScripts.Remove(added);
Data.GlobalInitScripts.Insert(0, added);
string probe = File.ReadAllText(Path.Combine(Path.GetDirectoryName(ScriptPath), "storage_probe.gml"));
string guard = probe.Substring(0, probe.IndexOf("var cap_a ="))
    .Replace("__PROFILE__", JsonConvert.SerializeObject(profile))
    .Replace("__EXPECTED_PATH__", JsonConvert.SerializeObject(((string)config["expected_save_path"]).Replace('\\','/').TrimEnd('/').ToLowerInvariant()));
string init = @"
global.cap_source = array_create(100, 0);
global.cap_ch_active = 0;
global.cap_ch_count = 0;
global.cap_ch_seq = 0;
global.cap_ch_io_failed = false;
global.cap_ch_slots = array_create(100, 0);
global.cap_ch_sources = array_create(100, 0);
global.cap_ch_texts = array_create(100, """");
global.cap_ix_active = 0;
global.cap_ix_count = 0;
global.cap_ix_seq = 0;
global.cap_ix_io_failed = false;
global.cap_ix_slots = array_create(100, 0);
global.cap_ix_texts = array_create(100, """");
global.cap_interaction_boxes = true;
global.cap_interaction_names = false;
global.cap_interaction_fixture = false;
global.cap_interaction_test_boxes = [];
global.cap_sm_source = array_create(100, 0);
global.cap_sm_text = array_create(100, """");
global.cap_sm_selector = array_create(100, """");
global.cap_sm_selected_sprite = array_create(100, -1);
global.cap_buffer = """";
global.cap_sequence = 0;
global.cap_message = 0;
global.cap_io_failed = false;
var cap_session = environment_get_variable(""DR_CAPTURE_SESSION"");
if (string_length(cap_session) != 32)
    cap_session = md5_string_utf8(string(date_current_datetime()) + "":"" + string(get_timer()));
var cap_segment = md5_string_utf8(cap_session + "":"" + string(get_timer()) + "":"" + string(date_current_datetime()));
global.cap_log = ""capture_"" + cap_session + ""_"" + cap_segment + "".jsonl"";
if (file_exists(global.cap_log)) { show_error(""Capture session already exists."", true); exit; }
var cap_mode = ""natural_play_pilot"";
if (environment_get_variable(""DR_CAPTURE_MECHANISM_TEST"") == ""1"") cap_mode = ""mechanism_selftest"";
global.cap_buffer = json_stringify({kind: ""header"", schema: 2, session_id: cap_segment, run_id: cap_session,
    source_manifest: __MANIFEST__, collector_sha256: __COLLECTOR__, mode: cap_mode,
    text_style_schema: 1, text_style_source_sha256: __STYLE_SOURCE__,
    smallface_schema: 1, smallface_spec_sha256: __SMALL_SPEC__,
    input_policy: ""ch2_writer_portrait_guard4_no_ctrl"",
    fixture_pace: environment_get_variable(""DR_CAPTURE_TEST_PACE""),
    test_modifications: {party_max_hp: 999, lightworld_max_hp: 999, automatic_healing: false}}) + chr(10);
cap_flush();
global.cap_ix_log = ""interactions_"" + cap_session + ""_"" + cap_segment + "".jsonl"";
if (file_exists(global.cap_ix_log)) { show_error(""Interaction session already exists."", true); exit; }
cap_ix_emit({kind: ""header"", schema: 1, session_id: cap_segment, run_id: cap_session,
    source_manifest: __MANIFEST__, collector_sha256: __COLLECTOR__, mode: cap_mode,
    scope: ""ch2_confirm_dispatch_message_writes_and_cutscene_commands""});
global.cap_ch_log = ""choices_"" + cap_session + ""_"" + cap_segment + "".jsonl"";
if (file_exists(global.cap_ch_log)) { show_error(""Choice session already exists."", true); exit; }
cap_ch_emit({kind: ""header"", schema: 1, session_id: cap_segment, run_id: cap_session,
    source_manifest: __MANIFEST__, collector_sha256: __COLLECTOR__, mode: cap_mode});
".Replace("__MANIFEST__", JsonConvert.SerializeObject((string)config["source_manifest"]))
 .Replace("__COLLECTOR__", JsonConvert.SerializeObject((string)config["collector_sha256"] ?? "development"));
init = init.Replace("__STYLE_SOURCE__", JsonConvert.SerializeObject(styleSourceHash));
init = init.Replace("__SMALL_SPEC__", JsonConvert.SerializeObject(Hash(smallSpecText)));
var initGroup = new CodeImportGroup(Data) { MainThreadAction = MainThreadAction };
initGroup.QueuePrepend(added.Code, guard);
initGroup.QueueAppend(added.Code, init);
initGroup.Import();
Data.GeneralInfo.Name = Data.Strings.MakeString(profile);
Data.GeneralInfo.DisplayName = Data.Strings.MakeString("DELTARUNE EN CH2 - capture pilot");
File.WriteAllText(Path.Combine(build, "compile_audit.json"), JsonConvert.SerializeObject(new {
    compiled = true, verified_source_files = ((JObject)inventory["patches"]).Count,
    modified_code_entries = texts.Count, global_first = Data.GlobalInitScripts[0].Code.Name.Content
}, Formatting.Indented));
File.WriteAllText(Path.Combine(build,"sprites.json"), JsonConvert.SerializeObject(Data.Sprites.Select((s,i)=>new {id=i,name=s.Name.Content,frames=s.Textures.Count}),Formatting.Indented));
ScriptMessage("Source, consumed identity signals, actual sprite draws and input telemetry compiled.");
