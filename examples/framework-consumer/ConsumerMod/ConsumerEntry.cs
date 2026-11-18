using Meitou.Modding;
using Rivalry;

namespace ConsumerMod;

/// <summary>
/// Registers with Rivalry Core through its public API, as a real dependent does in Initialize.
/// </summary>
public sealed class ConsumerEntry : IMod
{
    /// <summary>
    /// The mod's manifest id.
    /// </summary>
    public const string Id = "example.consumer";

    public void Initialize(ModContext context)
    {
        context.Log("loaded");
    }

    /// <summary>
    /// This mod's registrations in the given framework instance.
    /// </summary>
    public static IRivalryRegistry Register(IRivalryApi rivalry) => rivalry.For(Id);
}
