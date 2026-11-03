<#
.SYNOPSIS
Manda a la Jetson la copia sin commit de codigo/ (la copia WIP) y comprueba su sha256 (meta 007, fase 3).

.DESCRIPTION
1. Hace un tar de codigo/ con el tar.exe de Windows (bsdtar), sin .venv, __pycache__,
   .pytest_cache, historico/ (no viaja: en la Jetson se enlaza al del clon), *.nrrd ni *.dcm.
2. Lo comprueba antes de mandarlo, como lo comprobara el guardian: todo bajo codigo/, solo
   archivos y carpetas (ni enlaces), nada de lo excluido y <= 50 MB. Si algo no vale, para sin
   conectar.
3. Lo manda con `ssh <Alias> wip recibir` por la entrada estandar, con Start-Process y
   -RedirectStandardInput: en Windows PowerShell 5.1 una tuberia hacia un programa nativo pasa
   por texto y corromperia el tar (plan de la meta 007, hallazgo 6).
4. Compara el sha256 del tar con el que devuelve el guardian ("sha256 <hex>").
Borra sus temporales al terminar. Las opciones de ssh van en ~/.ssh/config, no aqui.

Codigos de salida:
  0    el guardian recibio la copia y los dos sha256 coinciden.
  2    una entrada no vale o el tar no pasa la comprobacion; no se conecto a nada.
  3    ssh o el guardian fallaron (126: negado) o los sha256 no coinciden.
  124  se paso de -TopeS: se corta ssh.

Solo ASCII (PowerShell 5.1 lee un .ps1 sin BOM con la pagina ANSI).

.PARAMETER Alias
El alias de ssh de la cuenta de los agentes, explicito: nav-jetson (o nav-jetson-lan, -cable, -ts).

.PARAMETER TopeS
El tope en segundos del envio, de 10 a 600 (el guardian corta wip recibir a los 120).

.PARAMETER Codigo
La carpeta codigo/ que se manda. Por defecto, la de este repo (la carpeta padre de linux/).

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File codigo/linux/enviar_wip.ps1 -Alias nav-jetson -TopeS 180
#>
[CmdletBinding()]
param(
    [string]$Alias = '',
    [int]$TopeS = 0,
    [string]$Codigo = ''
)

$ErrorActionPreference = 'Stop'
$MaxBytes = 50 * 1024 * 1024
$Excluidos = @('.venv', '__pycache__', '.pytest_cache', 'historico')

function Get-RutaAbsoluta([string]$ruta) {
    if ([System.IO.Path]::IsPathRooted($ruta)) { return [System.IO.Path]::GetFullPath($ruta) }
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).ProviderPath $ruta))
}

function Stop-Entrada([string]$motivo) {
    Write-Output "ERROR: $motivo"
    exit 2
}

# Start-Process de PowerShell 5.1 junta -ArgumentList con espacios y no cita nada: cada argumento
# se cita con las reglas de CommandLineToArgvW (como en probar_barrera.ps1).
function ConvertTo-LineaArgumentos([string[]]$Argumentos) {
    $partes = foreach ($a in $Argumentos) {
        if ($a -ne '' -and $a -notmatch '[\s"]') { $a; continue }
        $sb = New-Object System.Text.StringBuilder
        [void]$sb.Append('"')
        $barras = 0
        foreach ($c in $a.ToCharArray()) {
            if ($c -eq [char]'\') { $barras += 1; continue }
            if ($c -eq [char]'"') { [void]$sb.Append('\' * (2 * $barras + 1)) } else { [void]$sb.Append('\' * $barras) }
            [void]$sb.Append($c)
            $barras = 0
        }
        [void]$sb.Append('\' * (2 * $barras))
        [void]$sb.Append('"')
        $sb.ToString()
    }
    return ($partes -join ' ')
}

function Invoke-ConTope([string]$Exe, [string[]]$Argumentos, [string]$Entrada, [string]$Out, [string]$Err, [int]$Tope) {
    $p = Start-Process -FilePath $Exe -ArgumentList (ConvertTo-LineaArgumentos $Argumentos) -RedirectStandardInput $Entrada `
        -RedirectStandardOutput $Out -RedirectStandardError $Err -NoNewWindow -PassThru
    $null = $p.Handle   # PowerShell 5.1: sin tomar el handle, ExitCode queda vacio al terminar
    if (-not $p.WaitForExit($Tope * 1000)) {
        try { $p.Kill() } catch { }
        try { $null = $p.WaitForExit(5000) } catch { }
        return -1
    }
    $p.WaitForExit()
    return $p.ExitCode
}

# 1. Las entradas, antes de conectar a nada (principio 7).
if ($Alias -eq '') { Stop-Entrada 'falta -Alias (el alias de ssh de la cuenta de los agentes, p. ej. nav-jetson).' }
if ($Alias -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
    Stop-Entrada "el alias '$Alias' no vale: solo letras, cifras, punto, guion y guion bajo, sin empezar por guion."
}
if ($TopeS -lt 10 -or $TopeS -gt 600) { Stop-Entrada "-TopeS tiene que ir de 10 a 600 s (llego $TopeS)." }
if ($Codigo -eq '') { $Codigo = Split-Path -Parent $PSScriptRoot }
$Codigo = Get-RutaAbsoluta $Codigo
if (-not (Test-Path -LiteralPath $Codigo -PathType Container)) { Stop-Entrada "no existe la carpeta $Codigo." }
if ((Split-Path -Leaf $Codigo) -ne 'codigo') { Stop-Entrada "la carpeta tiene que llamarse codigo (llego $Codigo)." }
$padre = Split-Path -Parent $Codigo

$tar = Join-Path $env:SystemRoot 'System32\tar.exe'
if (-not (Test-Path -LiteralPath $tar -PathType Leaf)) { Stop-Entrada "no esta $tar (el bsdtar de Windows 10/11)." }
$ssh = Get-Command 'ssh.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $ssh) { Stop-Entrada 'no se encuentra ssh.exe (el cliente OpenSSH de Windows).' }

$marca = Get-Date -Format 'yyyyMMdd_HHmmss'
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) "nav_wip_$marca`_$PID"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$archivo = Join-Path $tmp 'codigo.tar'
$out = Join-Path $tmp 'out.txt'
$err = Join-Path $tmp 'err.txt'
$vacio = Join-Path $tmp 'vacio.txt'
[System.IO.File]::WriteAllBytes($vacio, [byte[]]@())

function Stop-Todo([int]$codigo) {
    try { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction Stop } catch { }
    exit $codigo
}

# 2. El tar, sin lo que no viaja.
$argsTar = @('-c', '-f', $archivo, '-C', $padre)
foreach ($e in $Excluidos) { $argsTar += @('--exclude', $e) }
$argsTar += @('--exclude', '*.nrrd', '--exclude', '*.dcm', 'codigo')
$rc = Invoke-ConTope $tar $argsTar $vacio $out $err 120
if ($rc -ne 0) {
    Write-Output "ERROR: tar.exe salio con $rc al empaquetar $Codigo"
    Write-Output ([System.IO.File]::ReadAllText($err))
    Stop-Todo 2
}

# 3. La comprobacion, antes de mandarlo (la misma regla que guardian._comprobar_miembro).
$rcN = Invoke-ConTope $tar @('-t', '-f', $archivo) $vacio $out $err 60
$nombres = @([System.IO.File]::ReadAllLines($out) | Where-Object { $_ -ne '' })
$rcV = Invoke-ConTope $tar @('-t', '-v', '-f', $archivo) $vacio $out $err 60
$detalle = @([System.IO.File]::ReadAllLines($out) | Where-Object { $_ -ne '' })
if ($rcN -ne 0 -or $rcV -ne 0 -or $nombres.Count -ne $detalle.Count -or $nombres.Count -eq 0) {
    Write-Output "ERROR: no se pudo listar el tar ($rcN, $rcV; $($nombres.Count) nombres, $($detalle.Count) lineas)."
    Stop-Todo 2
}
$malos = New-Object System.Collections.ArrayList
for ($i = 0; $i -lt $nombres.Count; $i++) {
    $n = $nombres[$i].TrimEnd('/')
    $partes = @($n -split '/')
    $tipo = $detalle[$i].Substring(0, 1)
    if ($partes[0] -ne 'codigo') { [void]$malos.Add("fuera de codigo/: $n"); continue }
    if ($partes -contains '..') { [void]$malos.Add("con '..': $n"); continue }
    if ($tipo -ne '-' -and $tipo -ne 'd') { [void]$malos.Add("no es archivo ni carpeta ($tipo): $n"); continue }
    $bajo = $n.ToLowerInvariant()
    if ($bajo.EndsWith('.nrrd') -or $bajo.EndsWith('.dcm')) { [void]$malos.Add("datos de paciente: $n"); continue }
    foreach ($e in $Excluidos) {
        if (@($partes | Select-Object -Skip 1) -contains $e) { [void]$malos.Add("$e/ no viaja: $n"); break }
    }
}
$bytes = (Get-Item -LiteralPath $archivo).Length
if ($bytes -gt $MaxBytes) { [void]$malos.Add("el tar pesa $bytes bytes (maximo $MaxBytes)") }
if ($malos.Count -gt 0) {
    Write-Output "ERROR: el tar no pasa la comprobacion ($($malos.Count)); no se manda:"
    $malos | Select-Object -First 20 | ForEach-Object { Write-Output "  $_" }
    Stop-Todo 2
}
$shaLocal = (Get-FileHash -LiteralPath $archivo -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Output ("Copia WIP: {0} miembros, {1:N2} MB, sha256 {2}" -f $nombres.Count, ($bytes / 1MB), $shaLocal)

# 4. El envio, con tope.
Write-Output "Mandando por '$Alias' (wip recibir, tope $TopeS s) con $($ssh.Source)"
$reloj = [System.Diagnostics.Stopwatch]::StartNew()
$rc = Invoke-ConTope $ssh.Source @($Alias, 'wip recibir') $archivo $out $err $TopeS
$reloj.Stop()
$stdout = ''
$stderr = ''
if (Test-Path -LiteralPath $out) { $stdout = [System.IO.File]::ReadAllText($out) }
if (Test-Path -LiteralPath $err) { $stderr = [System.IO.File]::ReadAllText($err) }
if ($rc -eq -1) {
    Write-Output "ERROR: el envio paso de $TopeS s y se corto ssh."
    Stop-Todo 124
}
Write-Output ("ssh salio con {0} en {1:N1} s" -f $rc, $reloj.Elapsed.TotalSeconds)
if ($stderr.Trim() -ne '') { Write-Output ("stderr: " + $stderr.Trim()) }
if ($rc -ne 0) {
    if ($rc -eq 126) { Write-Output 'NEGADO por el guardian: no se rodea; se dice en el reporte.' }
    Stop-Todo 3
}
$shaRemoto = ''
if ($stdout -match '(?m)^sha256 ([0-9a-f]{64})\s*$') { $shaRemoto = $Matches[1] }
Write-Output "sha256 local:  $shaLocal"
Write-Output "sha256 Jetson: $shaRemoto"
if ($shaRemoto -ne $shaLocal) {
    Write-Output 'ERROR: los sha256 no coinciden.'
    Stop-Todo 3
}
Write-Output 'sha256: coinciden'
Stop-Todo 0
