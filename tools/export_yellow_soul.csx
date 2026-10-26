// Load original chapter2_windows/data.win; only export resources, never save the package.
using System;
using System.IO;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text.Json;
using UndertaleModLib.Util;
EnsureDataLoaded();
string output = Environment.GetEnvironmentVariable("DR_YELLOW_ASSETS");
if (String.IsNullOrWhiteSpace(output)) throw new Exception("Set DR_YELLOW_ASSETS.");
Directory.CreateDirectory(output);
var records = new List<object>();
using (var worker = new TextureWorker()) {
    foreach (string name in new [] { "spr_yellowheart", "spr_yheart_charge", "spr_yheart_shot", "spr_yheart_bigshot" }) {
        var sprite = Data.Sprites.ByName(name);
        if (sprite == null) throw new Exception("Missing sprite: " + name);
        for (int frame = 0; frame < sprite.Textures.Count; frame++) {
            string file = name + "_" + frame + ".png";
            string path = Path.Combine(output, file);
            // Keep full sprite canvas, including transparent margins, for original origin coordinates.
            worker.ExportAsPNG(sprite.Textures[frame].Texture, path, name, true);
            records.Add(new { file, sprite = name, frame, width = sprite.Width, height = sprite.Height,
                origin_x = sprite.OriginX, origin_y = sprite.OriginY,
                sha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant() });
        }
    }
}
foreach (string name in new [] { "snd_heartshot_dr_b", "snd_chargeshot_charge", "snd_chargeshot_fire" }) {
    var sound = Data.Sounds.ByName(name);
    if (sound?.AudioFile?.Data == null || sound.GroupID != 0) throw new Exception("Missing embedded sound: " + name);
    string file = name + ".wav";
    File.WriteAllBytes(Path.Combine(output, file), sound.AudioFile.Data);
    records.Add(new { file, sound = name, bytes = sound.AudioFile.Data.Length,
        sha256 = Convert.ToHexString(SHA256.HashData(sound.AudioFile.Data)).ToLowerInvariant() });
}
File.WriteAllText(Path.Combine(output, "resources.json"), JsonSerializer.Serialize(records, new JsonSerializerOptions { WriteIndented = true }));
ScriptMessage("Exported original CH2 yellow soul frames and three WAV effects.");
