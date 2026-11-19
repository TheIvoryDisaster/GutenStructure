# Workshop Watcher

Workshop Watcher runs on a mod author's own Windows PC. On a schedule the author picks, it checks GitHub for a new release of each watched mod, verifies the release ZIP's SHA-256 and updates the author's existing Steam Workshop item with Valve's steamcmd.

- **Credentials stay on the PC.** steamcmd saves the author's Steam login after one interactive sign-in (password plus Steam Guard). The watcher never sees or stores the password, and nothing Steam-related goes into GitHub.
- **Update only.** It updates an item ID from the author's own config. It never creates items and never changes an item's title, description, preview image or visibility.
- **Release files are data.** It downloads, hash-checks and unpacks the ZIP; it never runs code from a repository or release.
- Each author runs their own copy with their own Steam account. Never share a Steam login.

Script: [`tools/workshop-watcher/WorkshopWatcher.ps1`](../tools/workshop-watcher/WorkshopWatcher.ps1). It needs only Windows PowerShell 5.1, which ships with Windows 10 and 11.

## Before you start

- The Workshop item must already exist and belong to your Steam account. Publish it once from the game (FCS for Kenshi, the in-game uploader for RimWorld) and note the number after `?id=` in its URL.
- The mod's GitHub releases must have one ZIP asset and a SHA-256 for it: either GitHub's asset digest (shown on every asset uploaded since 2025) or a `<zip name>.sha256` asset. Releases made by GutenStructure's [mod packaging](../.github/workflows/package-meitou-mod.yml) have both.
- The ZIP holds either one folder (the mod folder, uploaded as the item's content) or the mod's files at its root.

## Install

1. Open **Windows PowerShell** from the Start menu.
2. **Change to your Downloads folder:**

   ```powershell
   cd $HOME\Downloads
   ```

3. Download the script:

   ```powershell
   Invoke-WebRequest https://raw.githubusercontent.com/TheIvoryDisaster/GutenStructure/main/tools/workshop-watcher/WorkshopWatcher.ps1 -OutFile WorkshopWatcher.ps1
   ```

   To test a version that is still on `beta`, replace `main` in the URL with `beta`.

4. Run the installer:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\WorkshopWatcher.ps1 install
   ```

   The installer copies the script to `%LOCALAPPDATA%\WorkshopWatcher`, downloads steamcmd there, opens the Steam sign-in (type your password, then approve in the Steam app or type the Steam Guard code), asks which mods to watch and asks how often to check.

5. For private repositories only, save a [fine-grained GitHub token](https://github.com/settings/personal-access-tokens/new) with read-only **Contents** access to those repositories. It is stored encrypted for your Windows user:

   ```powershell
   powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\WorkshopWatcher\WorkshopWatcher.ps1" set-token
   ```

The installer can also run without questions:

```powershell
powershell -ExecutionPolicy Bypass -File .\WorkshopWatcher.ps1 install -Account mysteamlogin -Repo TheIvoryDisaster/Rimshi-Skeletons -AppId 294100 -ItemId 3841311958 -At 09:00
```

## Everyday commands

Set the installed script's path once per PowerShell window, then copy the commands as they are:

```powershell
$Watcher = "$env:LOCALAPPDATA\WorkshopWatcher\WorkshopWatcher.ps1"
```

| Task | Command |
| --- | --- |
| Show every command and option | `powershell -ExecutionPolicy Bypass -File $Watcher help` |
| Show settings, next run and recent log | `powershell -ExecutionPolicy Bypass -File $Watcher status` |
| Check now and upload anything new | `powershell -ExecutionPolicy Bypass -File $Watcher run` |
| Check and verify without uploading | `powershell -ExecutionPolicy Bypass -File $Watcher run -DryRun` |
| Sign in to Steam again | `powershell -ExecutionPolicy Bypass -File $Watcher login` |
| Watch another mod | `powershell -ExecutionPolicy Bypass -File $Watcher add-item -Repo owner/name -AppId 233860 -ItemId 1234567890` |
| Stop watching a mod | `powershell -ExecutionPolicy Bypass -File $Watcher remove-item -Repo owner/name` |
| Remove the scheduled task | `powershell -ExecutionPolicy Bypass -File $Watcher uninstall` |
| Remove everything, including the saved Steam login | `powershell -ExecutionPolicy Bypass -File $Watcher uninstall -RemoveData` |

`add-item` options: `-Asset <pattern>` picks the ZIP when a release has several (default `*.zip`), `-Prereleases` also uploads prereleases, and `-UploadCurrent` uploads the release that exists today on the next run. Without `-UploadCurrent` only releases published after the mod is added are uploaded.

Steam app IDs: Kenshi `233860`, RimWorld `294100`.

## Schedule

Choose exactly one of three forms with `schedule`. All times are the PC's local time. A run missed while the PC is off or asleep happens as soon as it is back on.

| Form | Meaning | Example |
| --- | --- | --- |
| `-Every <minutes>` | Repeat every N minutes, at least 5 | `-Every 360` (every 6 hours) |
| `-At <HH:mm[,HH:mm]>` | Every day at these 24-hour times | `-At 09:00` or `-At "07:30,19:30"` |
| `-Cron "<expression>"` | A cron expression | `-Cron "0 9 * * 1-5"` (weekdays at 09:00) |

```powershell
powershell -ExecutionPolicy Bypass -File $Watcher schedule -At "07:30,19:30"
```

`preview` takes the same options and lists the next run times without changing anything (`-Count` sets how many, default 5):

```powershell
powershell -ExecutionPolicy Bypass -File $Watcher preview -Cron "0 */6 * * *"
```

### Cron expressions

Five fields separated by spaces:

| Field | Values |
| --- | --- |
| minute | `0`-`59` |
| hour | `0`-`23` |
| day of month | `1`-`31` |
| month | `1`-`12` or `JAN`-`DEC` |
| day of week | `0`-`7` (`0` and `7` are Sunday) or `SUN`-`SAT` |

In any field: `*` every value, `5` one value, `1-5` a range, `1,15` a list, `*/6` every 6th value, `9-17/2` every 2nd value in a range. When both day of month and day of week are set, a day matching either one runs, as in standard cron. Shortcuts: `@hourly`, `@daily`, `@weekly`, `@monthly`, `@yearly`.

| Expression | Runs |
| --- | --- |
| `0 9 * * *` | every day at 09:00 |
| `0 */6 * * *` | every 6 hours on the hour (00:00, 06:00, 12:00, 18:00) |
| `30 18 * * 1-5` | weekdays at 18:30 |
| `0 8,20 * * *` | 08:00 and 20:00 every day |
| `0 12 * * SUN` | Sundays at 12:00 |
| `0 3 1 * *` | 03:00 on the 1st of each month |

To write one: start from `* * * * *` (every minute), set the minute and then the hour of the time you want (09:30 is `30 9 * * *`), narrow the days if needed (`30 9 * * 1-5` for weekdays), then check it with `preview`.

## What a run does

1. Schedules the next run.
2. For each watched mod, reads the repository's releases and takes the newest published one (skipping drafts, and prereleases unless `-Prereleases`). Nothing happens if it was already uploaded.
3. Downloads the one asset matching the pattern, and checks its SHA-256 against GitHub's asset digest and the `.sha256` asset when present; the two must agree.
4. Unpacks it into a temporary folder, refusing any path that would land outside it.
5. Runs steamcmd with the saved login to update the item, using the release title and link as the change note.
6. Records the release as uploaded and shows a Windows notification. A failed upload is retried on the next run.

If Steam asks for a new sign-in, the run stops, the notification says so, and `login` fixes it. Settings, state and `watcher.log` live in `%LOCALAPPDATA%\WorkshopWatcher`.

## Security notes

- Anyone who can read your Windows user's files can use the saved Steam login, as with the Steam client itself. `uninstall -RemoveData` deletes it.
- The scheduled task runs as you, only while you are signed in to Windows, with normal (not administrator) rights. A PowerShell window may flash briefly when it starts.
- Download the script only from GutenStructure, and read it before running it.
