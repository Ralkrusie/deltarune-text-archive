// Load original CH4 or CH5 data.win. Export only the named soul frames; never save the package.
using System;
using System.IO;
using UndertaleModLib.Util;
EnsureDataLoaded();
string output = Environment.GetEnvironmentVariable("DR_UI_ASSETS");
string chapter = Environment.GetEnvironmentVariable("DR_UI_SOUL_CHAPTER");
if (String.IsNullOrWhiteSpace(output)) throw new Exception("Set DR_UI_ASSETS.");
string[] names;
if (chapter == "4") names = new [] { "spr_greenheart" };
else if (chapter == "5") names = new [] { "spr_dodgeheart", "spr_yellowheart", "spr_orangeheart", "spr_orangeheart2", "spr_purpleheart" };
else throw new Exception("Set DR_UI_SOUL_CHAPTER to the loaded chapter (4 or 5).");
Directory.CreateDirectory(output);
using (var worker = new TextureWorker()) {
    foreach (string name in names) {
        var sprite = Data.Sprites.ByName(name);
        if (sprite == null || sprite.Textures.Count == 0) throw new Exception("Missing sprite: " + name);
        // Frame 0 is the complete black-bordered orange sprite; frame 3 is the separate outline kept for provenance.
        foreach (int frame in name == "spr_orangeheart2" ? new [] { 0, 3 } : new [] { 0 }) {
            if (sprite.Textures.Count <= frame) throw new Exception("Missing frame: " + name);
            worker.ExportAsPNG(sprite.Textures[frame].Texture, Path.Combine(output, name + "_" + frame + ".png"), null, false);
            ScriptMessage(name + ": frame " + frame + ", original " + sprite.Width + " x " + sprite.Height);
        }
    }
}
