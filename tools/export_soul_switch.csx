// Read-only export of the external original sound. Load the matching chapter package first.
using System;
using System.IO;
using System.Security.Cryptography;
EnsureDataLoaded();
if (Data.Sounds.ByName("snd_great_shine") == null) throw new Exception("Missing sound definition");
string source = Environment.GetEnvironmentVariable("DR_SOUL_SWITCH_SOURCE");
string output = Environment.GetEnvironmentVariable("DR_SOUL_SWITCH_ASSETS");
byte[] raw = File.ReadAllBytes(Path.Combine(source, "snd_great_shine.ogg"));
Directory.CreateDirectory(output);
File.WriteAllBytes(Path.Combine(output, "snd_great_shine.ogg"), raw);
ScriptMessage("snd_great_shine bytes=" + raw.Length + " sha256=" + Convert.ToHexString(SHA256.HashData(raw)).ToLowerInvariant());
