# Registrerer KITOS-synkronisering som Windows Task Scheduler opgave.
# Kør én gang som administrator:
#   Right-click -> "Kør som administrator" i PowerShell
#   .\setup_scheduler.ps1

$TaskName    = "KITOS SharePoint Sync"
$Description = "Nattlig synkronisering af KITOS-data til SharePoint (MTM systemer)"
$ScriptPath  = "C:\Users\azmda0l\Source\Aktivtsystem_ejerskab\run_sync.bat"
$RunAt       = "02:00"   # Kl. 02:00 om natten

# Slet eksisterende opgave hvis den findes
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Gammel opgave slettet."
}

# Definer trigger (dagligt kl. 02:00)
$Trigger = New-ScheduledTaskTrigger -Daily -At $RunAt

# Definer hvad der køres
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$ScriptPath`"" `
    -WorkingDirectory "C:\Users\azmda0l\Source\Aktivtsystem_ejerskab"

# Indstillinger: kør selvom bruger ikke er logget ind, forsøg igen ved fejl
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 15) `
    -StartWhenAvailable

# Registrér opgaven — kører under den aktuelle bruger
Register-ScheduledTask `
    -TaskName    $TaskName `
    -Description $Description `
    -Trigger     $Trigger `
    -Action      $Action `
    -Settings    $Settings `
    -RunLevel    Highest `
    -Force

Write-Host ""
Write-Host "Opgave registreret: '$TaskName'"
Write-Host "Korer dagligt kl. $RunAt"
Write-Host ""
Write-Host "Verificer i Task Scheduler: taskschd.msc"
Write-Host "Test-kørsel nu:  Start-ScheduledTask -TaskName '$TaskName'"