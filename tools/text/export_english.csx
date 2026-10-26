// Read-only source export for English defaults. Does not save the game package.
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Underanalyzer.Decompiler;
using UndertaleModLib.Decompiler;

EnsureDataLoaded();
string output = Environment.GetEnvironmentVariable("DR_ENGLISH_CODE");
if (String.IsNullOrWhiteSpace(output)) throw new Exception("Set DR_ENGLISH_CODE");
Directory.CreateDirectory(output);
var context = new GlobalDecompileContext(Data);
var settings = new DecompileSettings();
await Task.Run(() => Parallel.ForEach(Data.Code.Where(c => c.ParentEntry is null), code => {
    string source = new DecompileContext(context, code, settings).DecompileToString();
    // Keep only potential localization sources; failures propagate, never become empty files.
    if (source.Contains("setloc(") || source.Contains("nextloc(") ||
        source.Contains("setsubloc(") || source.Contains("nextsubloc("))
        File.WriteAllText(Path.Combine(output, code.Name.Content + ".gml"), source, new UTF8Encoding(false));
}));
ScriptMessage("Exported English localization sources; game unchanged.");
