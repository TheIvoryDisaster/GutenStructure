using Rivalry;

namespace ConsumerMod.Tests;

/// <summary>
/// The locked Rivalry Core loads at run time and answers a dependent's registration, as the game's loader would let it before the first world.
/// </summary>
public sealed class ConsumerTests
{
    [Fact]
    public void The_locked_framework_loads_and_registers_a_dependent()
    {
        var rivalry = new RivalryMod();

        Assert.Equal("rivalry.core", RivalryMod.Id);
        Assert.Equal("0.6.0", typeof(RivalryMod).Assembly.GetName().Version?.ToString(3));
        Assert.NotNull(ConsumerEntry.Register(rivalry));
    }
}
