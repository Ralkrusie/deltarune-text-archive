// Read-only export of a main font; never saves the game package.
using System;
using System.IO;
using System.Text;
using UndertaleModLib.Util;
EnsureDataLoaded();
string output = Environment.GetEnvironmentVariable("DR_MAIN_FONT_ASSETS");
if (String.IsNullOrWhiteSpace(output)) throw new Exception("Set DR_MAIN_FONT_ASSETS");
string name = Environment.GetEnvironmentVariable("DR_MAIN_FONT_NAME") ?? "fnt_main";
var font = Data.Fonts.ByName(name);
if (font?.Texture == null) throw new Exception("Missing font atlas: " + name);
Directory.CreateDirectory(output);
using (var worker = new TextureWorker())
    worker.ExportAsPNG(font.Texture, Path.Combine(output, name + ".png"));
using (var csv = new StreamWriter(Path.Combine(output, "glyphs_" + name + ".csv"), false, new UTF8Encoding(false))) {
    csv.WriteLine(FormattableString.Invariant($"{font.DisplayName};{font.EmSize};{font.Bold};{font.Italic};{font.Charset};{font.AntiAliasing};{font.ScaleX};{font.ScaleY}"));
    foreach (var g in font.Glyphs)
        csv.WriteLine(FormattableString.Invariant($"{g.Character};{g.SourceX};{g.SourceY};{g.SourceWidth};{g.SourceHeight};{g.Shift};{g.Offset}"));
}
ScriptMessage("Exported main font: " + font.Glyphs.Count + " glyphs; game unchanged.");
