// Read-only CH4/CH5 export; does not save or patch the game package.
using System;
using System.IO;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text.Json;
using UndertaleModLib.Util;
EnsureDataLoaded();
string output = Environment.GetEnvironmentVariable("DR_EXTRA_SOUL_ASSETS");
string chapter = Environment.GetEnvironmentVariable("DR_EXTRA_SOUL_CHAPTER");
if (String.IsNullOrWhiteSpace(output)) throw new Exception("Set DR_EXTRA_SOUL_ASSETS");
Directory.CreateDirectory(output);
var names = new List<string>();
if (chapter == "4") names.Add("spr_spearblocker");
else {
    names.AddRange(new [] {"spr_orangeheart_outline", "spr_orangeheart_white", "spr_orangeheart_dash"});
    foreach (string name in new [] {"obj_pinkdust", "obj_pinktrail"}) {
        var obj = Data.GameObjects.ByName(name);
        names.Add(obj.Sprite.Name.Content);
    }
}
var records = new List<object>();
using (var worker = new TextureWorker()) {
    foreach (string name in names) {
        var sprite = Data.Sprites.ByName(name);
        for (int frame=0; frame<sprite.Textures.Count; frame++) {
            string file=name+"_"+frame+".png";
            worker.ExportAsPNG(sprite.Textures[frame].Texture,Path.Combine(output,file),name,true);
            records.Add(new {file, width=sprite.Width, height=sprite.Height, origin_x=sprite.OriginX, origin_y=sprite.OriginY});
        }
    }
}
if (chapter == "5") foreach (string name in new [] {"snd_wing", "snd_explosion_mmx3", "snd_chargeshot_charge"}) {
    var sound=Data.Sounds.ByName(name);
    if (sound?.AudioFile?.Data == null || sound.GroupID != 0) throw new Exception("Not embedded: "+name);
    byte[] raw=sound.AudioFile.Data;
    string file=name+".wav";
    File.WriteAllBytes(Path.Combine(output,file),raw);
    records.Add(new {file, bytes=raw.Length, sha256=Convert.ToHexString(SHA256.HashData(raw)).ToLowerInvariant()});
}
File.WriteAllText(Path.Combine(output,"resources-ch"+chapter+".json"),JsonSerializer.Serialize(records,new JsonSerializerOptions{WriteIndented=true}));
ScriptMessage(JsonSerializer.Serialize(records));
