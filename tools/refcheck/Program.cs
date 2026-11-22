// RefCheck (docs/meitou-compat.md): what a built mod DLL asks of a Meitou release that the release does not have.
//
//   RefCheck check <mod.dll> <release dir>   MISSING lines for engine members (methods, constructors, fields) the DLL references by name and
//                                            parameter types that the release lacks, STAMP lines for engine assemblies referenced at a higher
//                                            version than the release's (the game refuses the mod: "entry type ... is not in its
//                                            assemblies"). Exit 1 when there is either.
//   RefCheck api <release dir>               the release's code-mod API version (Meitou.Modding.ModApi.Version).
//
// Compiling cannot catch either. A mod is built against one engine; a later release that changes a member's signature (Meitou 0.21 gave
// Inventory.Add a second, optional parameter) still compiles the mod's source, but the DLL already built asks the new game for the old member
// and fails at run time with MissingMethodException. .NET never binds a reference to an older assembly version.
using System.Collections.Immutable;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;

return args switch
{
    ["check", var mod, var release] => Check(mod, release),
    ["api", var release] => Api(release),
    _ => Usage(),
};

static int Usage()
{
    Console.Error.WriteLine("usage: RefCheck check <mod.dll> <release dir> | RefCheck api <release dir>");
    return 2;
}

static int Check(string mod, string release)
{
    using var mlc = Context(release);
    var engine = Engine.Load(mlc, release);

    using var pe = new PEReader(File.OpenRead(mod));
    var md = pe.GetMetadataReader();

    int stamps = Stamps(md, engine);
    var (checkedCount, missing) = Members(md, engine);

    Console.WriteLine($"{checkedCount} engine references checked, {missing} missing, {stamps} newer engine stamps");
    return missing + stamps == 0 ? 0 : 1;
}

static int Api(string release)
{
    using var mlc = Context(release);
    string client = Path.Combine(release, "MeitouClient.dll");
    var modApi = mlc.LoadFromAssemblyPath(client).GetType("Meitou.Modding.ModApi");
    var version = modApi?.GetField("Version")?.GetRawConstantValue();

    if (version is null)
    {
        Console.Error.WriteLine("no Meitou.Modding.ModApi.Version in " + client);
        return 2;
    }

    Console.WriteLine(version);
    return 0;
}

static MetadataLoadContext Context(string release)
{
    string runtime = System.Runtime.InteropServices.RuntimeEnvironment.GetRuntimeDirectory();
    var paths = Directory.GetFiles(release, "*.dll").Concat(Directory.GetFiles(runtime, "*.dll"));

    return new MetadataLoadContext(new PathAssemblyResolver(paths));
}

// Engine assemblies the DLL references at a higher version than the release stamps.
static int Stamps(MetadataReader md, Engine engine)
{
    int count = 0;

    foreach (var handle in md.AssemblyReferences)
    {
        var name = md.GetAssemblyReference(handle).GetAssemblyName();
        if (!engine.Versions.TryGetValue(name.Name!, out var have) || name.Version is null || name.Version <= have) continue;

        Console.WriteLine($"STAMP {name.Name} {name.Version} > {have}");
        count++;
    }

    return count;
}

// Every member reference to an engine type, by name and signature, against what the release declares.
static (int Checked, int Missing) Members(MetadataReader md, Engine engine)
{
    var names = new Names(md);
    int checkedCount = 0;
    int missing = 0;

    foreach (var handle in md.MemberReferences)
    {
        var reference = md.GetMemberReference(handle);
        string? parent = names.Parent(reference.Parent);
        if (parent is null || !engine.Types.Contains(parent)) continue;

        string key = names.Key(parent, reference);
        checkedCount++;
        if (engine.Members.Contains(key)) continue;

        Console.WriteLine("MISSING " + key);
        missing++;
    }

    return (checkedCount, missing);
}

/// <summary>
/// What a release's Meitou*.dll declare: type names, member keys (as <see cref="Names.Key"/> spells them) and assembly versions.
/// </summary>
sealed class Engine
{
    const BindingFlags All = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;

    public HashSet<string> Types { get; } = [];

    public HashSet<string> Members { get; } = [];

    public Dictionary<string, Version> Versions { get; } = [];

    public static Engine Load(MetadataLoadContext mlc, string release)
    {
        var engine = new Engine();

        foreach (string file in Directory.GetFiles(release, "Meitou*.dll"))
            engine.Add(mlc, file);

        return engine;
    }

    void Add(MetadataLoadContext mlc, string file)
    {
        Assembly assembly;
        try
        {
            assembly = mlc.LoadFromAssemblyPath(file);
        }
        catch (BadImageFormatException)
        {
            return;
        }

        var name = assembly.GetName();
        if (name.Version is not null) Versions[name.Name!] = name.Version;

        foreach (var type in Loadable(assembly))
            AddType(type);
    }

    static IEnumerable<Type> Loadable(Assembly assembly)
    {
        try
        {
            return assembly.GetTypes();
        }
        catch (ReflectionTypeLoadException e)
        {
            return e.Types.OfType<Type>();
        }
    }

    void AddType(Type type)
    {
        string name = Names.Clean(type.FullName ?? type.Name);
        Types.Add(name);

        try
        {
            foreach (var method in type.GetMethods(All))
                Members.Add($"{name}::{method.Name}({Parameters(method)})");
            foreach (var constructor in type.GetConstructors(All))
                Members.Add($"{name}::{constructor.Name}({Parameters(constructor)})");
            foreach (var field in type.GetFields(All))
                Members.Add($"{name}::{field.Name}");
        }
        catch (FileNotFoundException)
        {
            // A member whose signature names an assembly the release folder lacks: no mod can call it either.
        }
    }

    static string Parameters(MethodBase method) => string.Join(",", method.GetParameters().Select(p => Names.Of(p.ParameterType)));
}

/// <summary>
/// Spells types and member references the same way from the mod's metadata and from the release's reflection.
/// </summary>
sealed class Names(MetadataReader md) : ISignatureTypeProvider<string, object?>
{
    public static string Clean(string name)
    {
        int bracket = name.IndexOf('[');
        string bare = bracket >= 0 ? name[..bracket] : name;

        return bare.Replace('+', '/');
    }

    public static string Of(Type type)
    {
        if (type.IsByRef) return Of(type.GetElementType()!) + "&";
        if (type.IsArray) return Of(type.GetElementType()!) + "[]";
        if (type.IsPointer) return Of(type.GetElementType()!) + "*";
        if (type.IsGenericParameter) return (type.DeclaringMethod is null ? "!" : "!!") + type.GenericParameterPosition;
        if (!type.IsGenericType) return Clean(type.FullName ?? type.Name);

        string definition = Clean(type.GetGenericTypeDefinition().FullName!);
        return $"{definition}<{string.Join(",", type.GetGenericArguments().Select(Of))}>";
    }

    public string? Parent(EntityHandle parent) => parent.Kind switch
    {
        HandleKind.TypeReference => GetTypeFromReference(md, (TypeReferenceHandle)parent, 0),
        HandleKind.TypeSpecification => Generic(md.GetTypeSpecification((TypeSpecificationHandle)parent).DecodeSignature(this, null)),
        _ => null,
    };

    public string Key(string parent, MemberReference reference)
    {
        string name = md.GetString(reference.Name);
        if (reference.GetKind() != MemberReferenceKind.Method) return $"{parent}::{name}";

        var signature = reference.DecodeMethodSignature(this, null);
        return $"{parent}::{name}({string.Join(",", signature.ParameterTypes)})";
    }

    // A generic instantiation's parent is its definition: List<int>::Add is List`1::Add.
    static string Generic(string instantiation)
    {
        int angle = instantiation.IndexOf('<');
        return angle >= 0 ? instantiation[..angle] : instantiation;
    }

    public string GetArrayType(string element, ArrayShape shape) => element + "[]";

    public string GetByReferenceType(string element) => element + "&";

    public string GetFunctionPointerType(MethodSignature<string> signature) => "fnptr";

    public string GetGenericInstantiation(string definition, ImmutableArray<string> arguments) => $"{definition}<{string.Join(",", arguments)}>";

    public string GetGenericMethodParameter(object? context, int index) => "!!" + index;

    public string GetGenericTypeParameter(object? context, int index) => "!" + index;

    public string GetModifiedType(string modifier, string unmodified, bool isRequired) => unmodified;

    public string GetPinnedType(string element) => element;

    public string GetPointerType(string element) => element + "*";

    public string GetPrimitiveType(PrimitiveTypeCode code) => "System." + code switch
    {
        PrimitiveTypeCode.Object => "Object",
        PrimitiveTypeCode.TypedReference => "TypedReference",
        _ => code.ToString(),
    };

    public string GetSZArrayType(string element) => element + "[]";

    public string GetTypeFromDefinition(MetadataReader reader, TypeDefinitionHandle handle, byte kind)
    {
        var type = reader.GetTypeDefinition(handle);
        string ns = reader.GetString(type.Namespace);
        string name = reader.GetString(type.Name);

        return ns.Length > 0 ? $"{ns}.{name}" : name;
    }

    public string GetTypeFromReference(MetadataReader reader, TypeReferenceHandle handle, byte kind)
    {
        var type = reader.GetTypeReference(handle);
        string name = reader.GetString(type.Name);

        if (type.ResolutionScope.Kind == HandleKind.TypeReference)
            return GetTypeFromReference(reader, (TypeReferenceHandle)type.ResolutionScope, kind) + "/" + name;

        string ns = reader.GetString(type.Namespace);
        return ns.Length > 0 ? $"{ns}.{name}" : name;
    }

    public string GetTypeFromSpecification(MetadataReader reader, object? context, TypeSpecificationHandle handle, byte kind) =>
        reader.GetTypeSpecification(handle).DecodeSignature(this, context);
}
