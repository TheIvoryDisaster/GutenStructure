BeforeAll {
    . (Join-Path $PSScriptRoot '..\..\tools\workshop-watcher\WorkshopWatcher.ps1')

    function New-TestRelease {
        param([long]$Id, [string]$Published, [bool]$Draft = $false, [bool]$Prerelease = $false)
        [pscustomobject]@{ id = $Id; draft = $Draft; prerelease = $Prerelease; published_at = $Published; tag_name = "v$Id" }
    }
}

Describe 'cron schedules' {
    # 2026-11-18 is a Wednesday.
    It 'runs <expression> after <after> at <expected>' -ForEach @(
        @{ expression = '0 9 * * *'; after = '2026-11-18 08:00'; expected = '2026-11-18 09:00' }
        @{ expression = '0 9 * * *'; after = '2026-11-18 09:00'; expected = '2026-11-19 09:00' }
        @{ expression = '*/30 * * * *'; after = '2026-11-18 10:05'; expected = '2026-11-18 10:30' }
        @{ expression = '0 */6 * * *'; after = '2026-11-18 13:10'; expected = '2026-11-18 18:00' }
        @{ expression = '0 12 * * SUN'; after = '2026-11-18 08:00'; expected = '2026-11-22 12:00' }
        @{ expression = '0 0 * * 7'; after = '2026-11-18 08:00'; expected = '2026-11-22 00:00' }
        @{ expression = '30 18 * * 1-5'; after = '2026-11-20 19:00'; expected = '2026-11-23 18:30' }
        @{ expression = '0 8,20 * * *'; after = '2026-11-18 08:00'; expected = '2026-11-18 20:00' }
        @{ expression = '0 0 1 * MON'; after = '2026-11-18 08:00'; expected = '2026-11-23 00:00' }
        @{ expression = '0 3 1 JAN *'; after = '2026-11-18 08:00'; expected = '2027-01-01 03:00' }
        @{ expression = '0 0 29 2 *'; after = '2026-11-18 08:00'; expected = '2028-02-29 00:00' }
        @{ expression = '@daily'; after = '2026-11-18 08:00'; expected = '2026-11-19 00:00' }
        @{ expression = '0 9-17/4 * * *'; after = '2026-11-18 09:30'; expected = '2026-11-18 13:00' }
    ) {
        $next = Get-NextCronTime -Expression $expression -After ([datetime]$after)
        $next | Should -Be ([datetime]$expected)
    }

    It 'rejects <expression>' -ForEach @(
        @{ expression = '60 * * * *' }
        @{ expression = '* 24 * * *' }
        @{ expression = '0 9 * *' }
        @{ expression = '*/0 * * * *' }
        @{ expression = '0 9 * * FUNDAY' }
        @{ expression = '5-1 * * * *' }
    ) {
        { ConvertFrom-CronExpression -Expression $expression } | Should -Throw
    }

    It 'rejects a date that never exists' {
        { Get-NextCronTime -Expression '0 0 31 2 *' -After ([datetime]'2026-11-18') } | Should -Throw '*never matches*'
    }
}

Describe 'interval and time-of-day schedules' {
    It 'repeats every N minutes' {
        $schedule = New-WatcherSchedule -Every 90
        Get-NextRunTime -Schedule $schedule -After ([datetime]'2026-11-18 10:00') | Should -Be ([datetime]'2026-11-18 11:30')
    }

    It 'refuses intervals under the minimum' {
        { New-WatcherSchedule -Every 4 } | Should -Throw
    }

    It 'runs at the next listed time of day' {
        $schedule = New-WatcherSchedule -At '19:30, 07:30'
        $schedule.at | Should -Be '07:30,19:30'
        Get-NextRunTime -Schedule $schedule -After ([datetime]'2026-11-18 08:00') | Should -Be ([datetime]'2026-11-18 19:30')
        Get-NextRunTime -Schedule $schedule -After ([datetime]'2026-11-18 19:30') | Should -Be ([datetime]'2026-11-19 07:30')
    }

    It 'refuses a bad time of day' {
        { New-WatcherSchedule -At '25:00' } | Should -Throw
    }

    It 'needs exactly one schedule option' {
        { New-WatcherSchedule } | Should -Throw
        { New-WatcherSchedule -Every 60 -At '09:00' } | Should -Throw
    }

    It 'reads an install answer as <kind>' -ForEach @(
        @{ answer = '360'; kind = 'every' }
        @{ answer = '07:30,19:30'; kind = 'at' }
        @{ answer = '0 9 * * 1-5'; kind = 'cron' }
    ) {
        $schedule = ConvertFrom-ScheduleAnswer -Answer $answer
        @($schedule.PSObject.Properties.Name) | Should -Be @($kind)
    }
}

Describe 'release selection' {
    It 'picks the newest stable release' {
        $releases = @(
            New-TestRelease -Id 1 -Published '2026-11-01T00:00:00Z'
            New-TestRelease -Id 2 -Published '2026-11-10T00:00:00Z'
            New-TestRelease -Id 3 -Published '2026-11-12T00:00:00Z' -Prerelease $true
            New-TestRelease -Id 4 -Published '2026-11-13T00:00:00Z' -Draft $true
        )
        (Select-WatchedRelease -Releases $releases -IncludePrereleases $false).id | Should -Be 2
        (Select-WatchedRelease -Releases $releases -IncludePrereleases $true).id | Should -Be 3
    }

    It 'returns nothing when there is no eligible release' {
        Select-WatchedRelease -Releases @(New-TestRelease -Id 1 -Published '2026-11-01T00:00:00Z' -Draft $true) -IncludePrereleases $false |
            Should -BeNullOrEmpty
    }

    It 'needs exactly one matching asset and ignores checksum files' {
        $assets = @([pscustomobject]@{ name = 'Mod-1.0.zip' }, [pscustomobject]@{ name = 'Mod-1.0.zip.sha256' })
        (Select-ReleaseAsset -Assets $assets -Pattern '*.zip').name | Should -Be 'Mod-1.0.zip'
        { Select-ReleaseAsset -Assets ($assets + [pscustomobject]@{ name = 'Other.zip' }) -Pattern '*.zip' } | Should -Throw
    }
}

Describe 'checksums' {
    BeforeAll {
        $hash = 'a' * 64
        $other = 'b' * 64
    }

    It 'uses the GitHub asset digest' {
        Get-ExpectedSha256 -Asset ([pscustomobject]@{ digest = "sha256:$hash" }) -Sidecar $null | Should -Be $hash
    }

    It 'uses a .sha256 file' {
        Get-ExpectedSha256 -Asset ([pscustomobject]@{ name = 'Mod.zip' }) -Sidecar "$($hash.ToUpper())  Mod.zip`n" | Should -Be $hash
    }

    It 'refuses when the digest and the file disagree' {
        { Get-ExpectedSha256 -Asset ([pscustomobject]@{ digest = "sha256:$hash" }) -Sidecar "$other  Mod.zip" } | Should -Throw
    }

    It 'refuses when there is nothing to check against' {
        { Get-ExpectedSha256 -Asset ([pscustomobject]@{ digest = $null }) -Sidecar $null } | Should -Throw
    }
}

Describe 'package staging' {
    It 'treats <name> as safe: <safe>' -ForEach @(
        @{ name = 'Mod/About/About.xml'; safe = $true }
        @{ name = 'Mod/../evil.dll'; safe = $false }
        @{ name = '..\evil.dll'; safe = $false }
        @{ name = '/etc/evil'; safe = $false }
        @{ name = 'C:/Windows/evil.dll'; safe = $false }
    ) {
        Test-SafeZipEntry -Name $name | Should -Be $safe
    }

    It 'uploads the single top folder of a ZIP' {
        Get-ContentRootName -EntryNames @('RimshiSkeletons/', 'RimshiSkeletons/About/About.xml') | Should -Be 'RimshiSkeletons'
    }

    It 'uploads the ZIP root when it holds several entries' {
        Get-ContentRootName -EntryNames @('About/About.xml', 'Defs/Things.xml', 'LoadFolders.xml') | Should -BeNullOrEmpty
    }

    It 'extracts only inside the destination' {
        $work = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $work | Out-Null
        try {
            Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
            $zipPath = Join-Path $work 'mod.zip'
            $zip = [System.IO.Compression.ZipFile]::Open($zipPath, 'Create')
            $writer = New-Object System.IO.StreamWriter($zip.CreateEntry('Mod/About/About.xml').Open())
            $writer.Write('<ModMetaData/>')
            $writer.Dispose()
            $zip.Dispose()

            $content = Expand-ReleaseZip -ZipPath $zipPath -Destination (Join-Path $work 'content')
            (Split-Path $content -Leaf) | Should -Be 'Mod'
            Test-Path (Join-Path $content 'About/About.xml') | Should -BeTrue
        }
        finally {
            Remove-Item $work -Recurse -Force
        }
    }

    It 'writes an update-only VDF with escaped text' {
        $vdf = New-WorkshopVdf -AppId 294100 -ItemId 3841311958 -ContentFolder 'C:\Temp\Mod' -ChangeNote "Say `"hi`"`nline 2"
        $vdf | Should -Match '"publishedfileid"\s+"3841311958"'
        $vdf | Should -Match '"contentfolder"\s+"C:/Temp/Mod"'
        $vdf | Should -Match ([regex]::Escape('"Say \"hi\"\nline 2"'))
        $vdf | Should -Not -Match 'title|description|visibility|previewfile'
    }

    It 'refuses item ID 0, which would create a new item' {
        { New-WorkshopVdf -AppId 294100 -ItemId 0 -ContentFolder 'C:\Mod' -ChangeNote 'x' } | Should -Throw
    }
}

Describe 'upload state' {
    It 'reads and writes items on an empty state, as on a first run' {
        $state = [pscustomobject]@{}
        Get-ItemState -State $state -Key 'owner/repo#1' | Should -BeNullOrEmpty
        Set-ItemState -State $state -Key 'owner/repo#1' -Value 'v1'
        Set-ItemState -State $state -Key 'owner/repo#1' -Value 'v2'
        Get-ItemState -State $state -Key 'owner/repo#1' | Should -Be 'v2'
    }
}

Describe 'steamcmd results' {
    It 'reads <case> as <result>' -ForEach @(
        @{ case = 'success'; exit = 0; output = "Logging in using cached credentials.`nUploading content...`nSuccess."; result = 'success' }
        @{ case = 'expired login'; exit = 5; output = 'Cached credentials not found.'; result = 'login-needed' }
        @{ case = 'guard prompt'; exit = 5; output = 'Steam Guard code:'; result = 'login-needed' }
        @{ case = 'error'; exit = 0; output = "ERROR! Failed to update workshop item (Access Denied).`nSuccess."; result = 'failed' }
        @{ case = 'non-zero exit'; exit = 8; output = 'Success.'; result = 'failed' }
    ) {
        Get-SteamUploadResult -ExitCode $exit -Output $output | Should -Be $result
    }
}
