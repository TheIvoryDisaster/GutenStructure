<#
.SYNOPSIS
Uploads new GitHub releases of your mods to the Steam Workshop from your own PC, on a schedule you choose.

.DESCRIPTION
Workshop Watcher checks the GitHub repositories you list for a new release, verifies the release ZIP's SHA-256,
and updates your existing Steam Workshop item with steamcmd. It uses your own Steam login, which steamcmd saves
after one interactive sign-in; the watcher never sees or stores your Steam password. It never creates Workshop
items and never changes an item's title, description or visibility.

Run "WorkshopWatcher.ps1 help" for every command and schedule option, with cron examples.

.LINK
https://github.com/TheIvoryDisaster/GutenStructure/blob/main/docs/workshop-watcher.md
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Command = 'help',
    [int]$Every,
    [string]$At,
    [string]$Cron,
    [int]$Count = 5,
    [string]$Repo,
    [long]$AppId,
    [long]$ItemId,
    [string]$Asset = '*.zip',
    [switch]$Prereleases,
    [switch]$UploadCurrent,
    [string]$Account,
    [switch]$DryRun,
    [switch]$RemoveData,
    [switch]$ScheduledRun
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$script:WatcherVersion = '1.0.0'
$script:TaskName = 'WorkshopWatcher'
$script:TaskPath = '\WorkshopWatcher\'
$script:MinimumEveryMinutes = 5
$script:SteamCmdUrl = 'https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip'
$script:UploadTimeoutMinutes = 30

#region Schedule

$script:MonthNames = @{ JAN = 1; FEB = 2; MAR = 3; APR = 4; MAY = 5; JUN = 6; JUL = 7; AUG = 8; SEP = 9; OCT = 10; NOV = 11; DEC = 12 }
$script:DayNames = @{ SUN = 0; MON = 1; TUE = 2; WED = 3; THU = 4; FRI = 5; SAT = 6 }
$script:CronMacros = @{
    '@hourly'  = '0 * * * *'
    '@daily'   = '0 0 * * *'
    '@weekly'  = '0 0 * * 0'
    '@monthly' = '0 0 1 * *'
    '@yearly'  = '0 0 1 1 *'
}

function ConvertTo-CronNumber {
    param([string]$Text, [hashtable]$Names, [string]$FieldName)

    $upper = $Text.ToUpperInvariant()
    if ($Names -and $Names.ContainsKey($upper)) { return [int]$Names[$upper] }

    $value = 0
    if (-not [int]::TryParse($Text, [ref]$value)) { throw "Cron $FieldName field: '$Text' is not a number." }
    return $value
}

function ConvertFrom-CronField {
    param([string]$Text, [int]$Min, [int]$Max, [hashtable]$Names, [string]$FieldName)

    $values = New-Object 'System.Collections.Generic.SortedSet[int]'
    foreach ($part in $Text.Split(',')) {
        if ($part -eq '') { throw "Cron $FieldName field: empty list entry in '$Text'." }

        $step = 1
        $range = $part
        if ($part.Contains('/')) {
            $pieces = $part.Split('/')
            if ($pieces.Count -ne 2) { throw "Cron $FieldName field: '$part' has more than one '/'." }
            $range = $pieces[0]
            $step = ConvertTo-CronNumber -Text $pieces[1] -FieldName $FieldName
            if ($step -lt 1) { throw "Cron $FieldName field: step in '$part' must be 1 or more." }
        }

        if ($range -eq '*') {
            $low = $Min
            $high = $Max
        }
        elseif ($range.Contains('-')) {
            $bounds = $range.Split('-')
            if ($bounds.Count -ne 2) { throw "Cron $FieldName field: '$range' is not a range." }
            $low = ConvertTo-CronNumber -Text $bounds[0] -Names $Names -FieldName $FieldName
            $high = ConvertTo-CronNumber -Text $bounds[1] -Names $Names -FieldName $FieldName
        }
        else {
            $low = ConvertTo-CronNumber -Text $range -Names $Names -FieldName $FieldName
            $high = $low
            if ($part.Contains('/')) { $high = $Max }
        }

        if ($low -lt $Min -or $high -gt $Max -or $low -gt $high) {
            throw "Cron $FieldName field: '$part' is outside $Min-$Max."
        }

        for ($value = $low; $value -le $high; $value += $step) { [void]$values.Add($value) }
    }

    return , @($values)
}

function ConvertFrom-CronExpression {
    param([Parameter(Mandatory)][string]$Expression)

    $text = $Expression.Trim()
    if ($script:CronMacros.ContainsKey($text.ToLowerInvariant())) { $text = $script:CronMacros[$text.ToLowerInvariant()] }

    $fields = @($text -split '\s+')
    if ($fields.Count -ne 5) {
        throw "A cron expression has 5 fields (minute hour day-of-month month day-of-week); '$Expression' has $($fields.Count)."
    }

    $weekdays = ConvertFrom-CronField -Text $fields[4] -Min 0 -Max 7 -Names $script:DayNames -FieldName 'day-of-week'
    $weekdays = @($weekdays | ForEach-Object { $_ % 7 } | Sort-Object -Unique)

    return [pscustomobject]@{
        Minutes     = ConvertFrom-CronField -Text $fields[0] -Min 0 -Max 59 -FieldName 'minute'
        Hours       = ConvertFrom-CronField -Text $fields[1] -Min 0 -Max 23 -FieldName 'hour'
        Days        = ConvertFrom-CronField -Text $fields[2] -Min 1 -Max 31 -FieldName 'day-of-month'
        Months      = ConvertFrom-CronField -Text $fields[3] -Min 1 -Max 12 -Names $script:MonthNames -FieldName 'month'
        Weekdays    = $weekdays
        AnyDay      = ($fields[2] -eq '*')
        AnyWeekday  = ($fields[4] -eq '*')
    }
}

function Test-CronDay {
    param($Cron, [datetime]$Date)

    if ($Cron.Months -notcontains $Date.Month) { return $false }

    $dayMatches = $Cron.Days -contains $Date.Day
    $weekdayMatches = $Cron.Weekdays -contains [int]$Date.DayOfWeek

    # Standard cron rule: when both day fields are restricted, a day matching either one runs.
    if ($Cron.AnyDay -and $Cron.AnyWeekday) { return $true }
    if ($Cron.AnyDay) { return $weekdayMatches }
    if ($Cron.AnyWeekday) { return $dayMatches }
    return ($dayMatches -or $weekdayMatches)
}

function Get-NextCronTime {
    param([Parameter(Mandatory)][string]$Expression, [Parameter(Mandatory)][datetime]$After)

    $cron = ConvertFrom-CronExpression -Expression $Expression
    $start = $After.Date.AddHours($After.Hour).AddMinutes($After.Minute + 1)

    # Eight years covers every leap-day schedule (for example 0 0 29 2 *).
    for ($offset = 0; $offset -le 2930; $offset++) {
        $date = $start.Date.AddDays($offset)
        if (-not (Test-CronDay -Cron $cron -Date $date)) { continue }

        foreach ($hour in $cron.Hours) {
            foreach ($minute in $cron.Minutes) {
                $candidate = $date.AddHours($hour).AddMinutes($minute)
                if ($candidate -ge $start) { return $candidate }
            }
        }
    }

    throw "The cron expression '$Expression' never matches a real date."
}

function ConvertFrom-TimesOfDay {
    param([Parameter(Mandatory)][string]$Text)

    $times = @()
    foreach ($part in $Text.Split(',')) {
        $trimmed = $part.Trim()
        if ($trimmed -notmatch '^([01]?\d|2[0-3]):([0-5]\d)$') {
            throw "Time of day '$trimmed' must be 24-hour HH:mm, for example 07:30 or 19:00."
        }
        $times += New-TimeSpan -Hours ([int]$Matches[1]) -Minutes ([int]$Matches[2])
    }

    return , @($times | Sort-Object -Unique)
}

function Get-NextDailyTime {
    param([Parameter(Mandatory)][string]$Times, [Parameter(Mandatory)][datetime]$After)

    $parsed = ConvertFrom-TimesOfDay -Text $Times
    foreach ($dayOffset in 0, 1) {
        foreach ($time in $parsed) {
            $candidate = $After.Date.AddDays($dayOffset).Add($time)
            if ($candidate -gt $After) { return $candidate }
        }
    }
}

function New-WatcherSchedule {
    param([int]$Every, [string]$At, [string]$Cron)

    $given = @(@($Every -gt 0, [bool]$At, [bool]$Cron) | Where-Object { $_ }).Count
    if ($given -ne 1) { throw 'Give exactly one of -Every <minutes>, -At <HH:mm[,HH:mm...]> or -Cron "<expression>".' }

    if ($Every -gt 0) {
        if ($Every -lt $script:MinimumEveryMinutes) { throw "-Every must be at least $($script:MinimumEveryMinutes) minutes." }
        return [pscustomobject]@{ every = $Every }
    }

    if ($At) {
        $normalized = (ConvertFrom-TimesOfDay -Text $At | ForEach-Object { '{0:hh\:mm}' -f $_ }) -join ','
        return [pscustomobject]@{ at = $normalized }
    }

    [void](ConvertFrom-CronExpression -Expression $Cron)
    return [pscustomobject]@{ cron = $Cron.Trim() }
}

function ConvertFrom-ScheduleAnswer {
    param([Parameter(Mandatory)][string]$Answer)

    $text = $Answer.Trim()
    if ($text -match '^\d+$') { return New-WatcherSchedule -Every ([int]$text) }
    if ($text -match '^\d{1,2}:\d{2}(\s*,\s*\d{1,2}:\d{2})*$') { return New-WatcherSchedule -At $text }
    return New-WatcherSchedule -Cron $text
}

function Get-NextRunTime {
    param([Parameter(Mandatory)]$Schedule, [Parameter(Mandatory)][datetime]$After)

    $names = @($Schedule.PSObject.Properties.Name)
    if ($names -contains 'every') { return $After.AddMinutes([int]$Schedule.every) }
    if ($names -contains 'at') { return Get-NextDailyTime -Times $Schedule.at -After $After }
    if ($names -contains 'cron') { return Get-NextCronTime -Expression $Schedule.cron -After $After }
    throw 'The schedule in config.json has none of every, at or cron.'
}

function Format-Schedule {
    param([Parameter(Mandatory)]$Schedule)

    $names = @($Schedule.PSObject.Properties.Name)
    if ($names -contains 'every') { return "every $($Schedule.every) minutes" }
    if ($names -contains 'at') { return "daily at $($Schedule.at)" }
    return "cron '$($Schedule.cron)'"
}

#endregion

#region Releases

function Select-WatchedRelease {
    param([object[]]$Releases, [bool]$IncludePrereleases)

    $eligible = @($Releases | Where-Object { -not $_.draft -and ($IncludePrereleases -or -not $_.prerelease) })
    if ($eligible.Count -eq 0) { return $null }
    return ($eligible | Sort-Object { [datetime]$_.published_at } -Descending | Select-Object -First 1)
}

function Select-ReleaseAsset {
    param([object[]]$Assets, [string]$Pattern)

    $matching = @($Assets | Where-Object { $_.name -like $Pattern -and $_.name -notlike '*.sha256' })
    if ($matching.Count -ne 1) {
        $names = (@($Assets) | ForEach-Object { $_.name }) -join ', '
        throw "Expected exactly one release asset matching '$Pattern', found $($matching.Count) (assets: $names)."
    }
    return $matching[0]
}

function Get-ExpectedSha256 {
    param($Asset, [string]$Sidecar)

    $fromDigest = $null
    if ($Asset.PSObject.Properties.Name -contains 'digest' -and "$($Asset.digest)" -match '^sha256:([0-9a-fA-F]{64})$') {
        $fromDigest = $Matches[1].ToLowerInvariant()
    }

    $fromSidecar = $null
    if ($Sidecar) {
        if ($Sidecar.Trim() -notmatch '^([0-9a-fA-F]{64})\b') { throw 'The .sha256 file does not start with a SHA-256 hash.' }
        $fromSidecar = $Matches[1].ToLowerInvariant()
    }

    if ($fromDigest -and $fromSidecar -and $fromDigest -ne $fromSidecar) {
        throw 'GitHub''s asset digest and the release''s .sha256 file disagree.'
    }
    if ($fromDigest) { return $fromDigest }
    if ($fromSidecar) { return $fromSidecar }
    throw 'The release has no SHA-256 to check against: no asset digest and no .sha256 file.'
}

#endregion

#region Package staging

function Test-SafeZipEntry {
    param([Parameter(Mandatory)][string]$Name)

    $normalized = $Name.Replace('\', '/')
    if ($normalized.StartsWith('/') -or $normalized -match '^[A-Za-z]:') { return $false }
    foreach ($segment in $normalized.Split('/')) {
        if ($segment -eq '..') { return $false }
    }
    return $true
}

function Get-ContentRootName {
    param([string[]]$EntryNames)

    $tops = @($EntryNames |
        Where-Object { $_ } |
        ForEach-Object { $_.Replace('\', '/').Split('/')[0] } |
        Sort-Object -Unique)
    $nested = @($EntryNames | Where-Object { $_.Replace('\', '/').Contains('/') })

    # A ZIP holding one folder (Kenshi/mods/<Mod>/, a RimWorld mod root) uploads that folder's contents.
    if ($tops.Count -eq 1 -and $nested.Count -gt 0) { return $tops[0] }
    return $null
}

function Expand-ReleaseZip {
    param([Parameter(Mandatory)][string]$ZipPath, [Parameter(Mandatory)][string]$Destination)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $root = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $names = @($zip.Entries | ForEach-Object { $_.FullName })
        foreach ($entry in $zip.Entries) {
            if (-not (Test-SafeZipEntry -Name $entry.FullName)) { throw "Unsafe path in ZIP: $($entry.FullName)" }

            $target = [System.IO.Path]::GetFullPath((Join-Path $root $entry.FullName))
            if (-not $target.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe path in ZIP: $($entry.FullName)" }

            if ($entry.FullName.EndsWith('/')) {
                [void](New-Item -ItemType Directory -Path $target -Force)
                continue
            }
            [void](New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force)
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
        }
    }
    finally {
        $zip.Dispose()
    }

    $top = Get-ContentRootName -EntryNames $names
    if ($top) { return (Join-Path $root $top) }
    return $root.TrimEnd('\', '/')
}

function ConvertTo-VdfString {
    param([string]$Text)

    return $Text.Replace('\', '\\').Replace('"', '\"').Replace("`r", '').Replace("`n", '\n')
}

function New-WorkshopVdf {
    param([long]$AppId, [long]$ItemId, [string]$ContentFolder, [string]$ChangeNote)

    # A positive item ID only ever updates an existing item; 0 would create a new one.
    if ($ItemId -le 0) { throw 'The Workshop item ID must be a positive number.' }

    $folder = ConvertTo-VdfString -Text ($ContentFolder.Replace('\', '/'))
    $note = ConvertTo-VdfString -Text $ChangeNote
    # Title, description, preview and visibility are left out so the item keeps its current values.
    return @"
"workshopitem"
{
	"appid"		"$AppId"
	"publishedfileid"		"$ItemId"
	"contentfolder"		"$folder"
	"changenote"		"$note"
}
"@
}

#endregion

#region Steam

function Get-SteamUploadResult {
    param([int]$ExitCode, [string]$Output)

    $loginPattern = 'Cached credentials not found|password:|Steam Guard|Two-factor|Invalid Password|InvalidPassword|Login Failure|AccountLogonDenied|Expired login'
    if ($Output -match $loginPattern) { return 'login-needed' }
    if ($ExitCode -eq 0 -and $Output -match 'Success\.' -and $Output -notmatch 'ERROR!') { return 'success' }
    return 'failed'
}

function Get-SteamCmdPath {
    return (Join-Path (Join-Path (Get-DataDir) 'steamcmd') 'steamcmd.exe')
}

function Install-SteamCmd {
    $path = Get-SteamCmdPath
    if (Test-Path $path) { return $path }

    $folder = Split-Path $path -Parent
    [void](New-Item -ItemType Directory -Path $folder -Force)
    $zip = Join-Path $folder 'steamcmd.zip'
    Write-Host "Downloading Valve's steamcmd into $folder"
    Invoke-WebRequest -Uri $script:SteamCmdUrl -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $folder -Force
    Remove-Item $zip

    Write-Host 'Updating steamcmd (first start downloads its files)'
    & $path '+quit' | Out-Null
    return $path
}

function Invoke-SteamLogin {
    param([Parameter(Mandatory)][string]$SteamAccount)

    $steamcmd = Install-SteamCmd
    Write-Host ''
    Write-Host "steamcmd will ask for the password of '$SteamAccount', then a Steam Guard code or a confirmation in the Steam app."
    Write-Host 'steamcmd saves the login in its own folder; Workshop Watcher never sees the password.'
    & $steamcmd '+login' $SteamAccount '+quit'
    if ($LASTEXITCODE -ne 0) { throw "steamcmd login failed (exit code $LASTEXITCODE)." }
    Write-Host 'Steam login saved.'
}

function Invoke-SteamUpload {
    param([Parameter(Mandatory)][string]$SteamAccount, [Parameter(Mandatory)][string]$VdfPath, [Parameter(Mandatory)][string]$WorkDir)

    $steamcmd = Install-SteamCmd
    $runscript = Join-Path $WorkDir 'upload.txt'
    $vdf = $VdfPath.Replace('\', '/')
    $lines = @('@ShutdownOnFailedCommand 1', '@NoPromptForPassword 1', "login $SteamAccount", "workshop_build_item `"$vdf`"", 'quit')
    Set-Content -Path $runscript -Value $lines -Encoding ASCII

    $outFile = Join-Path $WorkDir 'steamcmd-out.txt'
    $errFile = Join-Path $WorkDir 'steamcmd-err.txt'
    $process = Start-Process -FilePath $steamcmd -ArgumentList '+runscript', "`"$runscript`"" -NoNewWindow -PassThru `
        -RedirectStandardOutput $outFile -RedirectStandardError $errFile
    # Reading Handle keeps the exit code available after the process ends.
    $null = $process.Handle
    if (-not $process.WaitForExit($script:UploadTimeoutMinutes * 60 * 1000)) {
        $process.Kill()
        return [pscustomobject]@{ Result = 'failed'; Output = "steamcmd did not finish within $($script:UploadTimeoutMinutes) minutes." }
    }

    $output = (Get-Content $outFile -Raw -ErrorAction SilentlyContinue) + (Get-Content $errFile -Raw -ErrorAction SilentlyContinue)
    return [pscustomobject]@{ Result = (Get-SteamUploadResult -ExitCode $process.ExitCode -Output "$output"); Output = "$output" }
}

#endregion

#region Storage

function Get-DataDir {
    if (-not $env:LOCALAPPDATA) { throw 'Workshop Watcher runs on Windows (LOCALAPPDATA is not set).' }
    return (Join-Path $env:LOCALAPPDATA 'WorkshopWatcher')
}

function Get-ConfigPath { return (Join-Path (Get-DataDir) 'config.json') }
function Get-StatePath { return (Join-Path (Get-DataDir) 'state.json') }
function Get-TokenPath { return (Join-Path (Get-DataDir) 'github-token.dat') }
function Get-LogPath { return (Join-Path (Get-DataDir) 'watcher.log') }
function Get-InstalledScriptPath { return (Join-Path (Get-DataDir) 'WorkshopWatcher.ps1') }

function Read-JsonFile {
    param([string]$Path, $Default)

    if (-not (Test-Path $Path)) { return $Default }
    return (Get-Content $Path -Raw | ConvertFrom-Json)
}

function Write-JsonFile {
    param([string]$Path, $Value)

    [void](New-Item -ItemType Directory -Path (Split-Path $Path -Parent) -Force)
    $Value | ConvertTo-Json -Depth 8 | Set-Content -Path $Path -Encoding UTF8
}

function Get-WatcherConfig {
    $default = [pscustomobject]@{ steamAccount = ''; schedule = $null; items = @() }
    $config = Read-JsonFile -Path (Get-ConfigPath) -Default $default
    $config.items = @($config.items)
    return $config
}

function Save-WatcherConfig { param($Config) Write-JsonFile -Path (Get-ConfigPath) -Value $Config }

function Get-WatcherState { return (Read-JsonFile -Path (Get-StatePath) -Default ([pscustomobject]@{})) }
function Save-WatcherState { param($State) Write-JsonFile -Path (Get-StatePath) -Value $State }

function Get-ItemKey { param($Item) return "$($Item.repo)#$($Item.itemId)" }

function Set-ItemState {
    param($State, [string]$Key, $Value)

    if ($State.PSObject.Properties.Name -contains $Key) { $State.$Key = $Value }
    else { $State | Add-Member -NotePropertyName $Key -NotePropertyValue $Value }
}

function Get-ItemState {
    param($State, [string]$Key)

    if ($State.PSObject.Properties.Name -contains $Key) { return $State.$Key }
    return $null
}

function Get-GitHubToken {
    $path = Get-TokenPath
    if (-not (Test-Path $path)) { return $null }

    # The token file is encrypted with Windows DPAPI for this Windows user only.
    $secure = Get-Content $path -Raw | ConvertTo-SecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Write-WatcherLog {
    param([string]$Message)

    $path = Get-LogPath
    [void](New-Item -ItemType Directory -Path (Split-Path $path -Parent) -Force)
    if ((Test-Path $path) -and (Get-Item $path).Length -gt 1MB) { Move-Item $path "$path.old" -Force }

    $line = '{0:yyyy-MM-dd HH:mm:ss} {1}' -f (Get-Date), $Message
    Add-Content -Path $path -Value $line -Encoding UTF8
    Write-Host $line
}

function Show-WatcherNotification {
    param([string]$Title, [string]$Text)

    try {
        [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $nodes = $template.GetElementsByTagName('text')
        [void]$nodes.Item(0).AppendChild($template.CreateTextNode($Title))
        [void]$nodes.Item(1).AppendChild($template.CreateTextNode($Text))
        $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show([Windows.UI.Notifications.ToastNotification]::new($template))
    }
    catch {
        Write-WatcherLog "notification unavailable: $Title - $Text"
    }
}

#endregion

#region GitHub

function Get-GitHubHeaders {
    param([string]$Accept = 'application/vnd.github+json')

    $headers = @{ 'User-Agent' = "WorkshopWatcher/$($script:WatcherVersion)"; 'Accept' = $Accept; 'X-GitHub-Api-Version' = '2022-11-28' }
    $token = Get-GitHubToken
    if ($token) { $headers['Authorization'] = "Bearer $token" }
    return $headers
}

function Invoke-GitHubJson {
    param([Parameter(Mandatory)][string]$Path)

    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    return Invoke-RestMethod -Uri "https://api.github.com/$Path" -Headers (Get-GitHubHeaders) -UseBasicParsing
}

function Save-ReleaseAsset {
    param([Parameter(Mandatory)]$Asset, [Parameter(Mandatory)][string]$OutFile)

    $headers = Get-GitHubHeaders -Accept 'application/octet-stream'
    if (-not $headers.ContainsKey('Authorization')) {
        Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $OutFile -UseBasicParsing -Headers @{ 'User-Agent' = $headers['User-Agent'] }
        return
    }

    # Private repositories: ask the API for the download location, then fetch it without the token,
    # because the storage host rejects requests that still carry GitHub's Authorization header.
    $request = [System.Net.HttpWebRequest]::Create($Asset.url)
    $request.AllowAutoRedirect = $false
    $request.UserAgent = $headers['User-Agent']
    $request.Accept = 'application/octet-stream'
    $request.Headers.Add('Authorization', $headers['Authorization'])
    $response = $request.GetResponse()
    try {
        $location = $response.Headers['Location']
    }
    finally {
        $response.Close()
    }
    if (-not $location) { throw "GitHub returned no download location for $($Asset.name)." }
    Invoke-WebRequest -Uri $location -OutFile $OutFile -UseBasicParsing
}

function Get-SidecarText {
    param([object[]]$Assets, $Asset, [string]$WorkDir)

    $sidecar = @($Assets | Where-Object { $_.name -eq "$($Asset.name).sha256" })
    if ($sidecar.Count -eq 0) { return $null }

    $path = Join-Path $WorkDir 'asset.sha256'
    Save-ReleaseAsset -Asset $sidecar[0] -OutFile $path
    return (Get-Content $path -Raw)
}

#endregion

#region Watch run

function Get-LatestRelease {
    param($Item)

    # Piping unrolls the array that Windows PowerShell 5.1's Invoke-RestMethod returns as one object.
    $releases = @(Invoke-GitHubJson -Path "repos/$($Item.repo)/releases?per_page=20" | ForEach-Object { $_ })
    return Select-WatchedRelease -Releases $releases -IncludePrereleases ([bool]$Item.prereleases)
}

function Publish-WatchedItem {
    param($Config, $Item, $State, [bool]$Preview)

    $label = "$($Item.repo) -> item $($Item.itemId)"
    $release = Get-LatestRelease -Item $Item
    if (-not $release) {
        Write-WatcherLog "$label`: no eligible release yet"
        return
    }

    $key = Get-ItemKey -Item $Item
    $last = Get-ItemState -State $State -Key $key
    if ($last -and "$($last.releaseId)" -eq "$($release.id)") {
        Write-WatcherLog "$label`: $($release.tag_name) already uploaded"
        return
    }

    $work = Join-Path ([System.IO.Path]::GetTempPath()) ("WorkshopWatcher-" + [guid]::NewGuid().ToString('N'))
    [void](New-Item -ItemType Directory -Path $work -Force)
    try {
        Publish-ReleaseToWorkshop -Config $Config -Item $Item -State $State -Release $release -WorkDir $work -Preview $Preview
    }
    finally {
        Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Publish-ReleaseToWorkshop {
    param($Config, $Item, $State, $Release, [string]$WorkDir, [bool]$Preview)

    $label = "$($Item.repo) -> item $($Item.itemId)"
    $assets = @($Release.assets)
    $asset = Select-ReleaseAsset -Assets $assets -Pattern $Item.asset
    $zipPath = Join-Path $WorkDir $asset.name
    Save-ReleaseAsset -Asset $asset -OutFile $zipPath

    $expected = Get-ExpectedSha256 -Asset $asset -Sidecar (Get-SidecarText -Assets $assets -Asset $asset -WorkDir $WorkDir)
    $actual = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "$($asset.name) SHA-256 is $actual, expected $expected." }

    $content = Expand-ReleaseZip -ZipPath $zipPath -Destination (Join-Path $WorkDir 'content')
    $note = "$($Release.name)".Trim()
    if (-not $note) { $note = $Release.tag_name }
    $note = "$note`n$($Release.html_url)"
    $vdfPath = Join-Path $WorkDir 'workshop.vdf'
    Set-Content -Path $vdfPath -Value (New-WorkshopVdf -AppId $Item.appId -ItemId $Item.itemId -ContentFolder $content -ChangeNote $note) -Encoding UTF8

    if ($Preview) {
        Write-WatcherLog "$label`: dry run, would upload $($Release.tag_name) ($($asset.name), sha256 $actual) from $content"
        Get-Content $vdfPath | Write-Host
        return
    }

    Complete-WorkshopUpload -Config $Config -Item $Item -State $State -Release $Release -Sha256 $actual -VdfPath $vdfPath -WorkDir $WorkDir
}

function Complete-WorkshopUpload {
    param($Config, $Item, $State, $Release, [string]$Sha256, [string]$VdfPath, [string]$WorkDir)

    $label = "$($Item.repo) -> item $($Item.itemId)"
    Write-WatcherLog "$label`: uploading $($Release.tag_name)"
    $upload = Invoke-SteamUpload -SteamAccount $Config.steamAccount -VdfPath $VdfPath -WorkDir $WorkDir

    if ($upload.Result -eq 'login-needed') {
        Write-WatcherLog "$label`: Steam needs you to sign in again; run: WorkshopWatcher.ps1 login"
        Show-WatcherNotification -Title 'Workshop Watcher: Steam sign-in needed' -Text 'Run WorkshopWatcher.ps1 login, then the next run uploads.'
        return
    }
    if ($upload.Result -ne 'success') {
        $tail = ($upload.Output -split "`n" | Select-Object -Last 15) -join "`n"
        Write-WatcherLog "$label`: upload failed; will retry next run. steamcmd output:`n$tail"
        Show-WatcherNotification -Title 'Workshop Watcher: upload failed' -Text "$($Item.repo) $($Release.tag_name). See watcher.log."
        return
    }

    $record = [pscustomobject]@{ releaseId = $Release.id; tag = $Release.tag_name; sha256 = $Sha256; uploaded = (Get-Date).ToString('o') }
    Set-ItemState -State $State -Key (Get-ItemKey -Item $Item) -Value $record
    Save-WatcherState -State $State
    Write-WatcherLog "$label`: uploaded $($Release.tag_name)"
    Show-WatcherNotification -Title 'Workshop Watcher: uploaded' -Text "$($Item.repo) $($Release.tag_name) is on the Workshop."
}

function Invoke-WatchRun {
    param([bool]$Preview, [bool]$FromSchedule)

    $config = Get-WatcherConfig
    if ($FromSchedule) {
        try {
            [void](Update-WatcherTask -Config $config)
        }
        catch {
            Write-WatcherLog "could not schedule the next run: $($_.Exception.Message)"
        }
    }

    if (-not $config.steamAccount) { throw 'No Steam account configured. Run: WorkshopWatcher.ps1 install' }
    $lockPath = Join-Path (Get-DataDir) 'run.lock'
    $lock = [System.IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        $state = Get-WatcherState
        foreach ($item in $config.items) {
            try {
                Publish-WatchedItem -Config $config -Item $item -State $state -Preview $Preview
            }
            catch {
                Write-WatcherLog "$($item.repo) -> item $($item.itemId): $($_.Exception.Message)"
                Show-WatcherNotification -Title 'Workshop Watcher: error' -Text "$($item.repo): $($_.Exception.Message)"
            }
        }
    }
    finally {
        $lock.Dispose()
    }
}

#endregion

#region Scheduled task

function Update-WatcherTask {
    param($Config)

    if (-not $Config.schedule) { throw 'No schedule configured. Run: WorkshopWatcher.ps1 schedule -Every 360' }
    $next = Get-NextRunTime -Schedule $Config.schedule -After (Get-Date)
    $trigger = New-ScheduledTaskTrigger -Once -At $next

    $existing = Get-ScheduledTask -TaskName $script:TaskName -TaskPath $script:TaskPath -ErrorAction SilentlyContinue
    if ($existing) {
        [void](Set-ScheduledTask -TaskName $script:TaskName -TaskPath $script:TaskPath -Trigger $trigger)
        return $next
    }

    $arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Get-InstalledScriptPath)`" run -ScheduledRun"
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
    $principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    # StartWhenAvailable runs a run missed while the PC was off or asleep as soon as it is back.
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    [void](Register-ScheduledTask -TaskName $script:TaskName -TaskPath $script:TaskPath -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description 'Uploads new GitHub releases to the Steam Workshop.')
    return $next
}

function Get-WatcherTaskNextRun {
    $task = Get-ScheduledTask -TaskName $script:TaskName -TaskPath $script:TaskPath -ErrorAction SilentlyContinue
    if (-not $task) { return $null }
    return ($task | Get-ScheduledTaskInfo).NextRunTime
}

#endregion

#region Commands

function Copy-WatcherScript {
    $target = Get-InstalledScriptPath
    [void](New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force)
    if ([System.IO.Path]::GetFullPath($PSCommandPath) -ne [System.IO.Path]::GetFullPath($target)) {
        Copy-Item -Path $PSCommandPath -Destination $target -Force
    }
}

function Add-WatchedItem {
    param([string]$Repo, [long]$AppId, [long]$ItemId, [string]$Asset, [bool]$IncludePrereleases, [bool]$UploadCurrent)

    if ($Repo -notmatch '^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$') { throw "-Repo must look like owner/name, got '$Repo'." }
    if ($AppId -le 0) { throw '-AppId must be the game''s Steam app ID, for example 233860 for Kenshi or 294100 for RimWorld.' }
    if ($ItemId -le 0) { throw '-ItemId must be the number at the end of your Workshop item''s URL (?id=...).' }

    $config = Get-WatcherConfig
    $item = [pscustomobject]@{ repo = $Repo; appId = $AppId; itemId = $ItemId; asset = $Asset; prereleases = $IncludePrereleases }
    $config.items = @($config.items | Where-Object { (Get-ItemKey -Item $_) -ne (Get-ItemKey -Item $item) }) + $item
    Save-WatcherConfig -Config $config

    if ($UploadCurrent) {
        Write-Host "Added $Repo -> item $ItemId. The next run uploads its latest release."
        return
    }
    Set-ReleaseBaseline -Item $item
}

function Set-ReleaseBaseline {
    param($Item)

    # Without -UploadCurrent, the release that exists today counts as already uploaded; only later releases upload.
    $release = Get-LatestRelease -Item $Item
    if (-not $release) {
        Write-Host "Added $($Item.repo) -> item $($Item.itemId). It has no release yet; the first one will upload."
        return
    }

    $state = Get-WatcherState
    $record = [pscustomobject]@{ releaseId = $release.id; tag = $release.tag_name; sha256 = ''; uploaded = 'baseline' }
    Set-ItemState -State $state -Key (Get-ItemKey -Item $Item) -Value $record
    Save-WatcherState -State $state
    Write-Host "Added $($Item.repo) -> item $($Item.itemId). Current release $($release.tag_name) is treated as already uploaded."
}

function Remove-WatchedItem {
    param([string]$Repo, [long]$ItemId)

    $config = Get-WatcherConfig
    $before = $config.items.Count
    $config.items = @($config.items | Where-Object { -not ($_.repo -eq $Repo -and ($ItemId -le 0 -or $_.itemId -eq $ItemId)) })
    Save-WatcherConfig -Config $config
    Write-Host "Removed $($before - $config.items.Count) item(s)."
}

function Set-WatcherSchedule {
    param($Schedule)

    $config = Get-WatcherConfig
    $config.schedule = $Schedule
    Save-WatcherConfig -Config $config
    $next = Update-WatcherTask -Config $config
    Write-Host "Schedule: $(Format-Schedule -Schedule $Schedule). Next run: $next"
}

function Show-NextRuns {
    param($Schedule, [int]$Count)

    Write-Host "Next $Count runs for $(Format-Schedule -Schedule $Schedule):"
    $time = Get-Date
    for ($i = 0; $i -lt $Count; $i++) {
        $time = Get-NextRunTime -Schedule $Schedule -After $time
        Write-Host ('  {0:ddd yyyy-MM-dd HH:mm}' -f $time)
    }
}

function Read-ScheduleAnswer {
    while ($true) {
        $answer = Read-Host 'How often should it check? Minutes (360), times of day (09:00 or 07:30,19:30) or cron (0 9 * * *) [360]'
        if (-not $answer) { $answer = '360' }
        try {
            return ConvertFrom-ScheduleAnswer -Answer $answer
        }
        catch {
            Write-Host $_.Exception.Message
        }
    }
}

function Read-ItemsInteractively {
    while ((Read-Host 'Add a mod to watch now? (y/n)') -match '^[Yy]') {
        try {
            $repoAnswer = Read-Host 'GitHub repository (owner/name)'
            $appAnswer = Read-Host 'Steam app ID of the game (Kenshi 233860, RimWorld 294100)'
            $itemAnswer = Read-Host 'Workshop item ID (the number after ?id= in the item URL)'
            $assetAnswer = Read-Host 'Release asset name pattern [*.zip]'
            if (-not $assetAnswer) { $assetAnswer = '*.zip' }
            Add-WatchedItem -Repo $repoAnswer -AppId ([long]$appAnswer) -ItemId ([long]$itemAnswer) -Asset $assetAnswer -IncludePrereleases $false -UploadCurrent $false
        }
        catch {
            Write-Host $_.Exception.Message
        }
    }
}

function Invoke-Install {
    param([string]$SteamAccount, $Schedule)

    Copy-WatcherScript
    [void](Install-SteamCmd)

    $config = Get-WatcherConfig
    if ($SteamAccount) { $config.steamAccount = $SteamAccount }
    if (-not $config.steamAccount) { $config.steamAccount = Read-Host 'Steam account name you sign in with (not your profile name)' }
    Save-WatcherConfig -Config $config
    Invoke-SteamLogin -SteamAccount $config.steamAccount

    if ($Repo) { Add-WatchedItem -Repo $Repo -AppId $AppId -ItemId $ItemId -Asset $Asset -IncludePrereleases $Prereleases.IsPresent -UploadCurrent $UploadCurrent.IsPresent }
    else { Read-ItemsInteractively }

    if (-not $Schedule) { $Schedule = Read-ScheduleAnswer }
    Set-WatcherSchedule -Schedule $Schedule
    Write-Host ''
    Write-Host "Installed in $(Get-DataDir). Check it any time with:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File `"$(Get-InstalledScriptPath)`" status"
}

function Show-Status {
    $config = Get-WatcherConfig
    $state = Get-WatcherState
    Write-Host "Workshop Watcher $($script:WatcherVersion), data in $(Get-DataDir)"
    Write-Host "Steam account: $($config.steamAccount)"
    if ($config.schedule) { Write-Host "Schedule: $(Format-Schedule -Schedule $config.schedule)" }
    else { Write-Host 'Schedule: none' }
    Write-Host "Next run: $(Get-WatcherTaskNextRun)"
    Write-Host "GitHub token: $(if (Test-Path (Get-TokenPath)) { 'saved' } else { 'none (public repositories only)' })"
    Write-Host 'Watched items:'
    foreach ($item in $config.items) {
        $last = Get-ItemState -State $state -Key (Get-ItemKey -Item $item)
        $lastText = 'nothing yet'
        if ($last) { $lastText = "$($last.tag) ($($last.uploaded))" }
        Write-Host "  $($item.repo) -> app $($item.appId) item $($item.itemId), asset $($item.asset), last: $lastText"
    }
    if (Test-Path (Get-LogPath)) {
        Write-Host 'Recent log:'
        Get-Content (Get-LogPath) -Tail 10 | ForEach-Object { Write-Host "  $_" }
    }
}

function Set-GitHubTokenCommand {
    $secure = Read-Host 'Paste a fine-grained GitHub token with read-only Contents access to your private mod repositories' -AsSecureString
    [void](New-Item -ItemType Directory -Path (Get-DataDir) -Force)
    $secure | ConvertFrom-SecureString | Set-Content -Path (Get-TokenPath)
    Write-Host 'Token saved, encrypted for this Windows user.'
}

function Invoke-Uninstall {
    param([bool]$DeleteData)

    Unregister-ScheduledTask -TaskName $script:TaskName -TaskPath $script:TaskPath -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host 'Scheduled task removed.'
    if ($DeleteData) {
        Remove-Item (Get-DataDir) -Recurse -Force
        Write-Host "Deleted $(Get-DataDir), including steamcmd and its saved Steam login."
    }
}

function Show-Help {
    @"
Workshop Watcher $($script:WatcherVersion): uploads new GitHub releases of your mods to the Steam Workshop.

USAGE
  WorkshopWatcher.ps1 <command> [options]

COMMANDS
  install      Set everything up: download steamcmd, sign in to Steam once, add mods, choose a schedule.
               Options: -Account <name> -Repo/-AppId/-ItemId (as add-item) -Every/-At/-Cron (as schedule)
  login        Sign in to Steam again (run this when the watcher says Steam needs you to sign in).
  add-item     Watch a repository and update one Workshop item from its releases.
               -Repo <owner/name> -AppId <game app ID> -ItemId <Workshop item ID>
               [-Asset <name pattern, default *.zip>] [-Prereleases] [-UploadCurrent]
               Without -UploadCurrent the current release counts as already uploaded.
  remove-item  Stop watching. -Repo <owner/name> [-ItemId <id>]
  schedule     Choose when it runs; give exactly one of:
               -Every <minutes>        repeat every N minutes (at least $($script:MinimumEveryMinutes)), e.g. -Every 360
               -At <HH:mm[,HH:mm]>     every day at these 24-hour times, e.g. -At 09:00 or -At "07:30,19:30"
               -Cron "<expression>"    a cron expression, e.g. -Cron "0 9 * * 1-5"
  preview      Show the next run times for a schedule without changing anything.
               Same options as schedule, plus -Count <n> (default 5).
  run          Check now and upload anything new. -DryRun downloads and verifies but does not upload.
  status       Show the account, schedule, next run, watched items and recent log lines.
  set-token    Save a read-only GitHub token, needed only for private repositories.
  uninstall    Remove the scheduled task. -RemoveData also deletes steamcmd, the saved Steam login and settings.
  help         Show this text.

CRON EXPRESSIONS
  Five fields separated by spaces, in your PC's local time:

    minute  hour  day-of-month  month  day-of-week
    0-59    0-23  1-31          1-12   0-7 (0 and 7 are Sunday)
                                JAN-DEC SUN-SAT

  In any field:  *  every value      5  one value      1-5  a range
                 1,15  a list        */6  every 6th    9-17/2  every 2nd in a range
  When both day-of-month and day-of-week are set, a day matching either runs (standard cron).
  Shortcuts: @hourly @daily @weekly @monthly @yearly

  Examples:
    0 9 * * *        every day at 09:00
    0 */6 * * *      every 6 hours, on the hour (00:00, 06:00, 12:00, 18:00)
    30 18 * * 1-5    weekdays at 18:30
    0 8,20 * * *     08:00 and 20:00 every day
    0 12 * * SUN     Sundays at 12:00
    0 3 1 * *        03:00 on the 1st of each month

  Write a cron expression:
    1. Start from "* * * * *" (every minute).
    2. Set the minute, then the hour, for the time you want: 09:30 is "30 9".
    3. Narrow the days if you need to: "1-5" in day-of-week for weekdays.
    4. Check it with: WorkshopWatcher.ps1 preview -Cron "30 9 * * 1-5"

EXAMPLES
  WorkshopWatcher.ps1 install
  WorkshopWatcher.ps1 add-item -Repo TheIvoryDisaster/Rimshi-Skeletons -AppId 294100 -ItemId 3841311958
  WorkshopWatcher.ps1 schedule -At "07:30,19:30"
  WorkshopWatcher.ps1 preview -Cron "0 */6 * * *"
  WorkshopWatcher.ps1 run -DryRun

A run missed while the PC is off or asleep happens as soon as it is back on.
"@ | Write-Host
}

function Get-ScheduleFromOptions {
    if ($Every -gt 0 -or $At -or $Cron) { return New-WatcherSchedule -Every $Every -At $At -Cron $Cron }
    return $null
}

function Invoke-WatcherCommand {
    param([string]$Name)

    switch ($Name.ToLowerInvariant()) {
        'help' { Show-Help }
        'install' { Invoke-Install -SteamAccount $Account -Schedule (Get-ScheduleFromOptions) }
        'login' { Invoke-SteamLogin -SteamAccount (Get-WatcherConfig).steamAccount }
        'add-item' { Add-WatchedItem -Repo $Repo -AppId $AppId -ItemId $ItemId -Asset $Asset -IncludePrereleases $Prereleases.IsPresent -UploadCurrent $UploadCurrent.IsPresent }
        'remove-item' { Remove-WatchedItem -Repo $Repo -ItemId $ItemId }
        'schedule' { Set-WatcherSchedule -Schedule (New-WatcherSchedule -Every $Every -At $At -Cron $Cron) }
        'preview' { Show-NextRuns -Schedule (New-WatcherSchedule -Every $Every -At $At -Cron $Cron) -Count $Count }
        'run' { Invoke-WatchRun -Preview $DryRun.IsPresent -FromSchedule $ScheduledRun.IsPresent }
        'status' { Show-Status }
        'set-token' { Set-GitHubTokenCommand }
        'uninstall' { Invoke-Uninstall -DeleteData $RemoveData.IsPresent }
        default { throw "Unknown command '$Name'. Run: WorkshopWatcher.ps1 help" }
    }
}

#endregion

# Dot-sourcing (tests) loads the functions without running a command.
if ($MyInvocation.InvocationName -eq '.') { return }

try {
    Invoke-WatcherCommand -Name $Command
}
catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
