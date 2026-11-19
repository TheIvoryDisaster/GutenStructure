// Resolves the frameworks a Meitou mod repository locks in meitou.lock.json (docs/framework-lock.md): downloads each release asset once into
// deps/, checks its SHA-256, extracts it, and returns the assemblies to reference and the mod folders to deploy. Frameworks built from a local
// clone (MeitouFrameworkSources) are skipped here; their project references are added by Meitou.Frameworks.targets. Also checks that every
// locked framework names the same engine commit as the repository's engine submodule and that each manifest's dependency ranges accept the
// versions present. Compiled by RoslynCodeTaskFactory, so only netstandard2.0 APIs.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net.Http;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.Build.Framework;
using Microsoft.Build.Utilities;

public sealed class ResolveMeitouFrameworks : Task
{
    [Required] public string LockFile { get; set; } = "";
    [Required] public string DepsDir { get; set; } = "";
    public string EngineDir { get; set; } = "";
    public bool Strict { get; set; }
    public ITaskItem[] Sources { get; set; } = Array.Empty<ITaskItem>();
    public ITaskItem[] Manifests { get; set; } = Array.Empty<ITaskItem>();

    [Output] public ITaskItem[] Assemblies { get; set; } = Array.Empty<ITaskItem>();
    [Output] public ITaskItem[] ModFolders { get; set; } = Array.Empty<ITaskItem>();

    public override bool Execute()
    {
        try
        {
            var lockFile = Read<LockFileData>(LockFile);
            var sourceManifests = Sources.Select(s => ManifestBeside(s.ItemSpec)).ToList();
            var sourceIds = new HashSet<string>(sourceManifests.Select(m => m.Id ?? ""));

            var assemblies = new List<ITaskItem>();
            var folders = new List<ITaskItem>();
            var present = new Dictionary<string, string>();
            var manifests = new List<KeyValuePair<string, Manifest>>();

            foreach (var source in sourceManifests)
            {
                present[source.Id ?? ""] = source.Version ?? "";
                manifests.Add(new KeyValuePair<string, Manifest>(source.Id ?? "", source));
            }

            foreach (var entry in lockFile.Frameworks ?? new List<LockEntry>())
            {
                if (sourceIds.Contains(entry.Id ?? "")) continue;

                var folder = Fetch(entry);
                var manifest = Read<Manifest>(Path.Combine(folder, "meitou.json"));
                if (manifest.Id != entry.Id) throw new InvalidOperationException($"{entry.Asset} holds mod '{manifest.Id}', the lock says '{entry.Id}'.");

                present[manifest.Id ?? ""] = manifest.Version ?? "";
                manifests.Add(new KeyValuePair<string, Manifest>(manifest.Id ?? "", manifest));
                folders.Add(FolderItem(folder, entry));
                foreach (var name in manifest.Assemblies ?? new List<string>()) assemblies.Add(AssemblyItem(folder, name, entry));
            }

            foreach (var item in Manifests.Where(m => File.Exists(m.ItemSpec)))
            {
                var own = Read<Manifest>(item.ItemSpec);
                manifests.Add(new KeyValuePair<string, Manifest>(own.Id ?? "", own));
            }

            CheckRanges(manifests, present);
            CheckEngine(lockFile, sourceIds);

            Assemblies = assemblies.ToArray();
            ModFolders = folders.ToArray();
            return !Log.HasLoggedErrors;
        }
        catch (Exception e) when (e is IOException || e is InvalidOperationException || e is HttpRequestException || e is SerializationException || e is InvalidDataException)
        {
            Log.LogError($"meitou.lock.json: {e.Message}");
            return false;
        }
    }

    #region Download

    /// <summary>
    /// The extracted mod folder of a locked asset: reused when deps/ already holds it with the lock's hash, else downloaded, checked and moved
    /// into place in one rename, so parallel builds never see a half-written folder.
    /// </summary>
    string Fetch(LockEntry entry)
    {
        var sha = (entry.Sha256 ?? "").ToLowerInvariant();
        var target = Path.Combine(DepsDir, entry.Tag ?? "");
        var folder = Path.Combine(target, entry.Folder ?? "");
        var marker = Path.Combine(target, ".sha256");
        if (File.Exists(marker) && File.ReadAllText(marker).Trim() == sha && Directory.Exists(folder)) return folder;

        Directory.CreateDirectory(DepsDir);
        var staging = Path.Combine(DepsDir, ".staging-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(staging);
        try
        {
            var zip = Path.Combine(staging, entry.Asset ?? "asset.zip");
            Download(entry, zip);
            var actual = Sha256(zip);
            if (actual != sha) throw new InvalidOperationException($"{entry.Asset} from {entry.Tag} has SHA-256 {actual}, the lock says {sha}.");

            var extracted = Path.Combine(staging, "x");
            ZipFile.ExtractToDirectory(zip, extracted);
            if (!Directory.Exists(Path.Combine(extracted, entry.Folder ?? ""))) throw new InvalidOperationException($"{entry.Asset} has no folder '{entry.Folder}'.");
            File.WriteAllText(Path.Combine(extracted, ".sha256"), sha);

            if (Directory.Exists(target)) Directory.Delete(target, true);
            Directory.Move(extracted, target);
            Log.LogMessage(MessageImportance.High, $"Fetched {entry.Id} {entry.Tag} ({sha}) into {target}");
        }
        catch (IOException) when (File.Exists(marker) && File.ReadAllText(marker).Trim() == sha)
        {
            // Another build moved the same verified folder into place first.
        }
        finally
        {
            if (Directory.Exists(staging)) Directory.Delete(staging, true);
        }
        return folder;
    }

    void Download(LockEntry entry, string path)
    {
        var url = $"https://github.com/{entry.Repo}/releases/download/{entry.Tag}/{entry.Asset}";
        using (var http = new HttpClient { Timeout = TimeSpan.FromMinutes(5) })
        using (var response = http.GetAsync(url).GetAwaiter().GetResult())
        {
            if (!response.IsSuccessStatusCode) throw new InvalidOperationException($"{url} answered {(int)response.StatusCode}.");
            using (var file = File.Create(path)) response.Content.CopyToAsync(file).GetAwaiter().GetResult();
        }
    }

    static string Sha256(string path)
    {
        using (var sha = SHA256.Create())
        using (var file = File.OpenRead(path))
            return string.Concat(sha.ComputeHash(file).Select(b => b.ToString("x2")));
    }

    #endregion

    #region Checks

    /// <summary>
    /// Every dependency a present manifest declares is present (unless optional) at a version its range accepts.
    /// </summary>
    void CheckRanges(List<KeyValuePair<string, Manifest>> manifests, Dictionary<string, string> present)
    {
        foreach (var pair in manifests)
        {
            foreach (var dependency in pair.Value.Dependencies ?? new List<Dependency>())
            {
                string version;
                if (!present.TryGetValue(dependency.Id ?? "", out version))
                {
                    if (!dependency.Optional) Log.LogError($"meitou.lock.json: {pair.Key} needs {dependency.Id} {dependency.Version}; add it to the lock.");
                    continue;
                }
                if (!SemVer.Satisfies(version, dependency.Version ?? ""))
                    Log.LogError($"meitou.lock.json: {pair.Key} needs {dependency.Id} {dependency.Version}; the lock has {version}. Move {dependency.Id} in the lock.");
            }
        }
    }

    /// <summary>
    /// All locked frameworks name one engine commit, and it is the commit the engine submodule is checked out at. An error on CI (Strict), a
    /// warning on a developer's machine, where an engine branch may be checked out on purpose. Skipped when frameworks come from clones.
    /// </summary>
    void CheckEngine(LockFileData lockFile, HashSet<string> sourceIds)
    {
        var engines = (lockFile.Frameworks ?? new List<LockEntry>()).Where(f => !sourceIds.Contains(f.Id ?? "")).Select(f => (f.Engine ?? "").ToLowerInvariant()).Distinct().ToList();
        if (engines.Count > 1) Report($"locked frameworks were built on different engine commits ({string.Join(", ", engines)}); move them to releases built on one.");
        if (engines.Count != 1 || sourceIds.Count > 0 || EngineDir.Length == 0) return;

        var head = EngineHead(EngineDir);
        if (head is null) Report($"can't read the engine commit in {EngineDir}; run git submodule update --init.");
        else if (head != engines[0]) Report($"engine/ is at {head}, the locked frameworks were built on {engines[0]}; move the engine submodule to {engines[0]}.");
    }

    void Report(string message)
    {
        if (Strict) Log.LogError("meitou.lock.json: " + message);
        else Log.LogWarning("meitou.lock.json: " + message);
    }

    /// <summary>
    /// The commit a submodule's checkout is at, read from its git directory (engine/.git is a file naming it); null when not a detached checkout.
    /// </summary>
    static string EngineHead(string engineDir)
    {
        var dotGit = Path.Combine(engineDir, ".git");
        string gitDir;
        if (Directory.Exists(dotGit)) gitDir = dotGit;
        else if (File.Exists(dotGit))
        {
            var text = File.ReadAllText(dotGit).Trim();
            if (!text.StartsWith("gitdir:")) return null;
            gitDir = Path.GetFullPath(Path.Combine(engineDir, text.Substring("gitdir:".Length).Trim()));
        }
        else return null;

        var headFile = Path.Combine(gitDir, "HEAD");
        if (!File.Exists(headFile)) return null;
        var head = File.ReadAllText(headFile).Trim().ToLowerInvariant();
        return Regex.IsMatch(head, "^[0-9a-f]{40}$") ? head : null;
    }

    #endregion

    #region Items and files

    ITaskItem AssemblyItem(string folder, string name, LockEntry entry)
    {
        var item = new TaskItem(Path.GetFileNameWithoutExtension(name));
        item.SetMetadata("HintPath", Path.Combine(folder, name));
        item.SetMetadata("FrameworkId", entry.Id ?? "");
        return item;
    }

    ITaskItem FolderItem(string folder, LockEntry entry)
    {
        var item = new TaskItem(folder);
        item.SetMetadata("ModName", entry.Folder ?? "");
        item.SetMetadata("FrameworkId", entry.Id ?? "");
        return item;
    }

    static Manifest ManifestBeside(string project) => Read<Manifest>(Path.Combine(Path.GetDirectoryName(Path.GetFullPath(project)) ?? "", "meitou.json"));

    static T Read<T>(string path)
    {
        if (!File.Exists(path)) throw new IOException($"no file {path}.");
        var settings = new DataContractJsonSerializerSettings { UseSimpleDictionaryFormat = true };
        using (var stream = new MemoryStream(Encoding.UTF8.GetBytes(File.ReadAllText(path))))
            return (T)new DataContractJsonSerializer(typeof(T), settings).ReadObject(stream);
    }

    #endregion
}

[DataContract]
public sealed class LockFileData
{
    [DataMember(Name = "format")] public int Format { get; set; }
    [DataMember(Name = "frameworks")] public List<LockEntry> Frameworks { get; set; }
}

[DataContract]
public sealed class LockEntry
{
    [DataMember(Name = "id")] public string Id { get; set; }
    [DataMember(Name = "repo")] public string Repo { get; set; }
    [DataMember(Name = "tag")] public string Tag { get; set; }
    [DataMember(Name = "asset")] public string Asset { get; set; }
    [DataMember(Name = "sha256")] public string Sha256 { get; set; }
    [DataMember(Name = "folder")] public string Folder { get; set; }
    [DataMember(Name = "engine")] public string Engine { get; set; }
}

[DataContract]
public sealed class Manifest
{
    [DataMember(Name = "id")] public string Id { get; set; }
    [DataMember(Name = "version")] public string Version { get; set; }
    [DataMember(Name = "assemblies")] public List<string> Assemblies { get; set; }
    [DataMember(Name = "dependencies")] public List<Dependency> Dependencies { get; set; }
}

[DataContract]
public sealed class Dependency
{
    [DataMember(Name = "id")] public string Id { get; set; }
    [DataMember(Name = "version")] public string Version { get; set; }
    [DataMember(Name = "optional")] public bool Optional { get; set; }
}

/// <summary>
/// SemVer ranges as manifests write them: space-separated comparators (>=, >, <=, <, =) that must all hold; prerelease sorts before release.
/// </summary>
public static class SemVer
{
    public static bool Satisfies(string version, string range)
    {
        var v = Parse(version);
        if (v is null) return false;
        foreach (var part in range.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries))
        {
            var m = Regex.Match(part, "^(>=|<=|>|<|=)?(.+)$");
            var bound = Parse(m.Groups[2].Value);
            if (bound is null) return false;
            var c = Compare(v, bound);
            if (!Holds(m.Groups[1].Value, c)) return false;
        }
        return true;
    }

    static bool Holds(string op, int c)
    {
        if (op == ">=") return c >= 0;
        if (op == "<=") return c <= 0;
        if (op == ">") return c > 0;
        if (op == "<") return c < 0;
        return c == 0;
    }

    static string[] Parse(string text)
    {
        var m = Regex.Match(text.Trim(), @"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+.*)?$");
        return m.Success ? new[] { m.Groups[1].Value, m.Groups[2].Value, m.Groups[3].Value, m.Groups[4].Value } : null;
    }

    static int Compare(string[] a, string[] b)
    {
        for (var i = 0; i < 3; i++)
        {
            var c = long.Parse(a[i]).CompareTo(long.Parse(b[i]));
            if (c != 0) return c;
        }
        if (a[3].Length == 0 || b[3].Length == 0) return b[3].Length.CompareTo(a[3].Length);
        return ComparePrerelease(a[3], b[3]);
    }

    static int ComparePrerelease(string a, string b)
    {
        var x = a.Split('.');
        var y = b.Split('.');
        for (var i = 0; i < Math.Min(x.Length, y.Length); i++)
        {
            long p, q;
            var c = long.TryParse(x[i], out p) && long.TryParse(y[i], out q) ? p.CompareTo(q) : string.CompareOrdinal(x[i], y[i]);
            if (c != 0) return c;
        }
        return x.Length.CompareTo(y.Length);
    }
}
