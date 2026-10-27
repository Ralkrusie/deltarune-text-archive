// Read-only, requested frames only. Never modifies the loaded package.
using System;
using System.IO;
using Newtonsoft.Json.Linq;
using UndertaleModLib.Util;
EnsureDataLoaded();
var request = JObject.Parse(File.ReadAllText(Environment.GetEnvironmentVariable("DR_REVIEW_ASSETS")));
var root = (string)request["output"];
Directory.CreateDirectory(root);
using (var worker = new TextureWorker()) {
    foreach (var item in request["frames"]) {
        string name = (string)item["name"]; int frame = (int)item["frame"];
        if (!System.Text.RegularExpressions.Regex.IsMatch(name, @"^spr_\w+$")) throw new Exception("Unsafe sprite name");
        var sprite = Data.Sprites.ByName(name);
        if (sprite == null || frame < 0 || frame >= sprite.Textures.Count || sprite.Textures[frame]?.Texture == null)
            throw new Exception("Missing requested frame: " + name + "/" + frame);
        string path = Path.Combine(root, name + "_" + frame + ".png");
        if (!File.Exists(path)) worker.ExportAsPNG(sprite.Textures[frame].Texture, path, null, false);
    }
}
ScriptMessage("Requested review frames exported; game unchanged.");
