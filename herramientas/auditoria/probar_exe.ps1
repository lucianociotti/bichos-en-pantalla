# Prueba de humo del .exe, AISLADA: usa TEMP y LOCALAPPDATA propios, así que no toca tus ajustes ni
# una copia que tengas abierta. Lo lanza, mira ventanas, red y procesos hijos, muestra el log y lo cierra
# (solo a las copias que lanzó, identificadas por su ruta).
#   powershell -File herramientas\auditoria\probar_exe.ps1 -Exe dist\tienda\exe\BichosPantalla.exe [-Espera 14]
# OJO: durante unos segundos van a cruzar bichos por tu pantalla.
param([Parameter(Mandatory = $true)][string]$Exe, [int]$Espera = 14)

$Exe = (Resolve-Path $Exe).Path
$iso = Join-Path ([IO.Path]::GetTempPath()) ("bichos_prueba_" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Force "$iso\tmp", "$iso\local" | Out-Null
$bak = @{ T = $env:TEMP; M = $env:TMP; L = $env:LOCALAPPDATA }
$env:TEMP = "$iso\tmp"; $env:TMP = "$iso\tmp"; $env:LOCALAPPDATA = "$iso\local"
Start-Process $Exe -ArgumentList '--ya' | Out-Null
$env:TEMP = $bak.T; $env:TMP = $bak.M; $env:LOCALAPPDATA = $bak.L
Start-Sleep -Seconds $Espera

Add-Type -AssemblyName UIAutomationClient -ErrorAction SilentlyContinue
$mios = @(Get-CimInstance Win32_Process -Filter "Name='$([IO.Path]::GetFileName($Exe))'" | Where-Object { $_.ExecutablePath -eq $Exe })
$ids = @($mios | ForEach-Object { $_.ProcessId })
"procesos del .exe: $($ids.Count)"
$vent = foreach ($id in $ids) {
    $cond = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty, [int]$id)
    foreach ($x in [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children, $cond)) {
        $t = $x.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition) |
            Where-Object { $_.Current.Name } | Select-Object -First 3 | ForEach-Object { $_.Current.Name }
        "'$($x.Current.Name)': $($t -join ' | ')"
    }
}
"ventanas (la del bicho es 'BichosPantalla' sin texto; un diálogo de error traería texto): $(($vent | Select-Object -Unique) -join ' // ')"
$tcp = @(Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $ids -contains $_.OwningProcess }).Count
$udp = @(Get-NetUDPEndpoint -ErrorAction SilentlyContinue | Where-Object { $ids -contains $_.OwningProcess }).Count
"conexiones de red: TCP $tcp, UDP $udp   (esperado: 0 y 0)"
$hijos = Get-CimInstance Win32_Process | Where-Object { $ids -contains $_.ParentProcessId -and $ids -notcontains $_.ProcessId }
"otros programas lanzados: $(if ($hijos) { ($hijos | ForEach-Object { $_.Name }) -join ',' } else { 'ninguno' })   (esperado: ninguno)"
$lg = "$iso\local\BichosPantalla\bichos.log"
"--- log:"
if (Test-Path $lg) {
    Get-Content $lg -Encoding UTF8 | Where-Object { $_ -notmatch ' DEBUG ' } | Select-Object -First 12 |
        ForEach-Object { "  " + $_.Substring(0, [math]::Min(165, $_.Length)) }
} else { "  (sin log: no arrancó bien)" }

foreach ($id in $ids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
Remove-Item $iso -Recurse -Force -ErrorAction SilentlyContinue
