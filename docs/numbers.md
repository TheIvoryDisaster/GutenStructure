# Mod number blocks

Meitou lets code mods claim numbers that every loaded mod shares, and refuses to load a second mod that claims a number already taken. To keep
our mods (and mods by other authors) from clashing, each mod owns one block of 100 numbers. The list is
[`registry/numbers.json`](../registry/numbers.json).

## The pools

A block applies to each of these pools (engine `docs/modding.md`). Each pool starts at 1000 (`SimulationExtensions.FirstModCode`).

| Pool | Claimed with |
| --- | --- |
| Task type | `AddGoalType` and `AddJobType` (one pool for both) |
| Dialogue condition | `AddDialogueCondition` |
| Dialogue effect | `AddDialogueEffect` |

A framework that takes a number from its dependents, such as Husbandry's `AddSkill(skill, taskType, races)`, gets it from the dependent's block.

## Blocks

| Block | Mod (`meitou.json` id) | Repository |
| --- | --- | --- |
| 1600-1699 | `rivalry.core` | Meitou-Modding-Ecosystem/RivalryCore |
| 4400-4499 | `bathhouse` | Meitou-Modding-Ecosystem/Bathhouse |
| 4500-4599 | `husbandry` | Meitou-Modding-Ecosystem/Husbandry |
| 4600-4699 | `ashen.hand` | Meitou-Modding-Ecosystem/AshenHand |
| 4700-4799 | `squad.arena` | Meitou-Modding-Ecosystem/SquadArena |
| 4800-4899 | `logistics.core` | Meitou-Modding-Ecosystem/LogisticsCore |
| 4900-4999 | `animal.behaviors` | Meitou-Modding-Ecosystem/AnimalBehaviors |
| 5000-5099 | `kenshi.races` | Meitou-Modding-Ecosystem/KenshiRaces |
| 5100-5199 | `storage` | Meitou-Modding-Ecosystem/Storage |
| 7300-7399 | `fiefdom` | teppuM/meitou-fiefdom |

## Rules

- Claim numbers only inside your block. A mod that needs more than 100 in a pool asks for a second block.
- List every number the mod claims in its README's `## Numbers` section. A test from MeitouModTemplate (`NumbersTests`) checks that each listed
  number lies inside the block named there.
- To get a block, open a PR that adds it to `registry/numbers.json` and the table above. Take the next free hundred. Authors outside the org are
  welcome. The `test_numbers` test refuses overlapping or misaligned blocks and a mod with two blocks.
