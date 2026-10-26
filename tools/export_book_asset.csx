// Load original CH2 data.win; export frame zero without saving the game package.
using System;
using System.IO;
using UndertaleModLib.Util;
EnsureDataLoaded();
string output = Environment.GetEnvironmentVariable("DR_UI_ASSETS");
if (String.IsNullOrWhiteSpace(output)) throw new Exception("Set DR_UI_ASSETS to an output directory.");
var sprite = Data.Sprites.ByName("spr_castle_book_pillar");
if (sprite == null || sprite.Textures.Count == 0) throw new Exception("Missing spr_castle_book_pillar; load the original CH2 package.");
Directory.CreateDirectory(output);
using (var worker = new TextureWorker()) {
    worker.ExportAsPNG(sprite.Textures[0].Texture, Path.Combine(output, "spr_castle_book_pillar_0.png"), null, false);
}
ScriptMessage("Exported book pillar; game unchanged.");
