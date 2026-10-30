<#
.SYNOPSIS
Escanea la Jetson en solo lectura y guarda lo que imprime en un archivo del PC (meta 007, fase 1).

.DESCRIPTION
Lanza codigo/linux/escanear_jetson.sh en la Jetson por ssh, con el script por la entrada estandar:
  ssh -T -o ConnectTimeout=15 <Alias> timeout -k 5 120 bash --norc --noprofile -s
y guarda en -Salida lo que el script imprime. En la Jetson no se escribe nada: el script solo lee y
al final comprueba con find que no cambio nada en el HOME.

Usa Start-Process con -RedirectStandardInput y -RedirectStandardOutput, y no una tuberia: en
Windows PowerShell 5.1 una tuberia hacia un programa nativo pasa por texto y cambia los fines de
linea (plan de la meta 007, hallazgo 6). Los mensajes de ssh, y la pregunta por la frase de paso
de la clave si la tiene, salen en esta consola.

Lo corre el autor con su cuenta y su alias (protocolo P-1). Ningun agente lo corre.

Codigos de salida:
  0    el escaneo termino con sus 12 secciones y la linea ESCANEO_FIN.
  2    una entrada no vale (alias, salida, tope o script); no se conecto a nada.
  3    ssh salio con error o el escaneo quedo incompleto (lo recibido queda en -Salida).
  124  se paso de -TopeS: se corta ssh (lo recibido queda en -Salida).

El script es solo ASCII a proposito: PowerShell 5.1 lee un .ps1 sin BOM con la pagina ANSI.

.PARAMETER Alias
El alias de ssh de la Jetson, explicito (principio 7): el de ~/.ssh/config del autor, p. ej. yahboom.

.PARAMETER Salida
El archivo de texto donde queda el escaneo. Si existe, no se pisa: el script para.

.PARAMETER TopeS
El tope en segundos de todo el escaneo, de 60 a 900 (el plan usa 180). Al pasarlo se corta ssh.

.PARAMETER Script
El script que se manda. Por defecto, escanear_jetson.sh junto a este archivo.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File codigo/linux/escanear.ps1 -Alias yahboom -Salida "Claude outputs/fases/007/escaneo/antes.txt" -TopeS 180
#>
[CmdletBinding()]
param(
    [string]$Alias = '',
    [string]$Salida = '',
    [int]$TopeS = 0,
    [string]$Script = ''
)

$ErrorActionPreference = 'Stop'
$RemotoEscaneo = 'timeout -k 5 120 bash --norc --noprofile -s'

function Get-RutaAbsoluta([string]$ruta) {
    if ([System.IO.Path]::IsPathRooted($ruta)) { return [System.IO.Path]::GetFullPath($ruta) }
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).ProviderPath $ruta))
}

function Stop-Entrada([string]$motivo) {
    Write-Output "ERROR: $motivo"
    exit 2
}

# 1. Las entradas, antes de conectar a nada (principio 7).
if ($Alias -eq '') { Stop-Entrada 'falta -Alias (el alias de ssh de la Jetson, p. ej. yahboom).' }
if ($Alias -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
    Stop-Entrada "el alias '$Alias' no vale: solo letras, cifras, punto, guion y guion bajo, sin empezar por guion."
}
if ($Salida -eq '') { Stop-Entrada 'falta -Salida (el archivo de texto del escaneo).' }
if ($TopeS -lt 60 -or $TopeS -gt 900) { Stop-Entrada "-TopeS tiene que ir de 60 a 900 s (llego $TopeS)." }

if ($Script -eq '') { $Script = Join-Path $PSScriptRoot 'escanear_jetson.sh' }
$Script = Get-RutaAbsoluta $Script
if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) { Stop-Entrada "no existe el script $Script." }
$bytes = [System.IO.File]::ReadAllBytes($Script)
if ($bytes.Length -eq 0) { Stop-Entrada "el script $Script esta vacio." }
foreach ($b in $bytes) {
    if ($b -eq 13) {
        Stop-Entrada ("el script $Script tiene fines de linea CRLF y bash no lo correria. " +
            '.gitattributes lo fija en LF: vuelve a sacarlo con git checkout -- codigo/linux/escanear_jetson.sh.')
    }
    if ($b -gt 127) { Stop-Entrada "el script $Script tiene caracteres que no son ASCII." }
}

$Salida = Get-RutaAbsoluta $Salida
if (Test-Path -LiteralPath $Salida) { Stop-Entrada "ya existe $Salida y no se pisa: usa otro nombre o borralo tu." }

$ssh = Get-Command 'ssh.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $ssh) { Stop-Entrada 'no se encuentra ssh.exe (el cliente OpenSSH de Windows).' }

# 2. El escaneo, con tope.
$carpeta = Split-Path -Parent $Salida
if (-not (Test-Path -LiteralPath $carpeta)) { New-Item -ItemType Directory -Force -Path $carpeta | Out-Null }

$argumentos = @('-T', '-o', 'ConnectTimeout=15', $Alias, $RemotoEscaneo)
Write-Output "Escaneando $Alias en solo lectura (tope $TopeS s) con $($ssh.Source)"
Write-Output "  script: $Script"
Write-Output "  salida: $Salida"
$reloj = [System.Diagnostics.Stopwatch]::StartNew()
$p = Start-Process -FilePath $ssh.Source -ArgumentList $argumentos -RedirectStandardInput $Script `
    -RedirectStandardOutput $Salida -NoNewWindow -PassThru
$null = $p.Handle   # PowerShell 5.1: sin tomar el handle, ExitCode queda vacio al terminar
if (-not $p.WaitForExit($TopeS * 1000)) {
    try { $p.Kill() } catch { }
    try { $null = $p.WaitForExit(5000) } catch { }
    Write-Output "ERROR: el escaneo paso de $TopeS s y se corto ssh. Lo recibido queda en $Salida."
    exit 124
}
$p.WaitForExit()
$reloj.Stop()
$codigo = $p.ExitCode

# 3. Lo que llego.
$texto = ''
if (Test-Path -LiteralPath $Salida) { $texto = [System.IO.File]::ReadAllText($Salida) }
$lineas = @($texto -split "`r?`n")
$secciones = @($lineas | Where-Object { $_ -match '^=== \[(\d+)/12\] ' } | ForEach-Object {
    [void]($_ -match '^=== \[(\d+)/12\] '); [int]$Matches[1] } | Sort-Object -Unique)
$fin = @($lineas | Where-Object { $_ -like 'ESCANEO_FIN *' }) | Select-Object -Last 1
# Ojo: en PowerShell las variables no distinguen mayusculas; llamarla "topes" pisaria el parametro
# [int] TopeS y pararia al convertir el texto (P-1, 2026-10-29). Lo comprueba test_escaneo_jetson.py.
$lineaTopes = @($lineas | Where-Object { $_ -like 'TOPES:*' }) | Select-Object -Last 1
$find = @($lineas | Where-Object { $_ -like 'find: *' }) | Select-Object -Last 1

Write-Output ''
Write-Output ("Escaneo de {0}: {1:N1} s de reloj, ssh salio con {2}" -f $Alias, $reloj.Elapsed.TotalSeconds, $codigo)
Write-Output "Secciones: $($secciones.Count) de 12"
if ($fin) { Write-Output $fin } else { Write-Output 'ESCANEO_FIN: no llego (el escaneo quedo incompleto)' }
if ($lineaTopes) { Write-Output $lineaTopes }
if ($find) { Write-Output $find } else { Write-Output 'find: no llego la comprobacion final' }
Write-Output "Salida: $Salida ($($lineas.Count) lineas)"

if ($codigo -ne 0 -or $secciones.Count -ne 12 -or -not $fin) { exit 3 }
exit 0
