// Export two original CH1 frames for the local website; never saves the game package.
using System;
using System.IO;
using UndertaleModLib.Util;
EnsureDataLoaded();
string output = Environment.GetEnvironmentVariable("DR_UI_ASSETS");
if (String.IsNullOrWhiteSpace(output)) throw new Exception("Set DR_UI_ASSETS to an output directory.");
Directory.CreateDirectory(output);
using (var worker = new TextureWorker()) {
    foreach (string name in new [] { "spr_heart", "IMAGE_LOGO" }) {
        var sprite = Data.Sprites.ByName(name);
        if (sprite == null || sprite.Textures.Count == 0) throw new Exception("Missing sprite: " + name);
        worker.ExportAsPNG(sprite.Textures[0].Texture, Path.Combine(output, name + "_0.png"), null, false);
    }
}
ScriptMessage("Exported heart and title frames; game unchanged.");
