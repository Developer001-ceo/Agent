$ProgressPreference = 'SilentlyContinue'
$ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
try {
    $r = Invoke-WebRequest -Uri 'https://customerconnect.omnissa.com/downloads/info/slug/desktop_enduser_computing/vmware_horizon_clients/horizon_8' -UseBasicParsing -TimeoutSec 30 -Headers @{'User-Agent' = $ua}
} catch {
    Write-Output ("FETCH-FAILED: " + $_.Exception.Message)
    exit 1
}
$pat = 'https://[^\s"''<>]+?\.exe'
$m = [regex]::Matches($r.Content, $pat) | ForEach-Object { $_.Value } | Sort-Object -Unique
if ($m) {
    Write-Output "EXE-LINKS:"
    $m | ForEach-Object { Write-Output $_ }
} else {
    Write-Output ("NO-EXE-LINKS page-bytes=" + $r.Content.Length)
    # dump any download3/omnissa URLs as a fallback clue
    [regex]::Matches($r.Content, 'https://[^\s"''<>]+') | ForEach-Object { $_.Value } |
        Where-Object { $_ -match 'download|\.exe|\.msi' } | Sort-Object -Unique | Select-Object -First 15
}
