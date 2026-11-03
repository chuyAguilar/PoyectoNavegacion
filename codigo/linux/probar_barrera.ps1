<#
.SYNOPSIS
Prueba la barrera de los agentes en la Jetson: 30 casos, cada uno con lo esperado (meta 007, fase 2).

.DESCRIPTION
Lanza por ssh, con el alias de los agentes, los casos de la fase 2 del plan de la meta 007:
  1-16   negados por el guardian (codigo 126): sin orden, sudo, apt-get, reboot, systemctl stop,
         nvpmodel -m, jetson_clocks, bash -c, py de un modulo fuera de la lista, --record fuera de
         ~/nav-salidas, traer con .., un metacaracter, docker, ollama, crontab y git push;
  17-20  cuatro tar malos por `wip recibir` (126) sin que cambie `wip estado`;
  21-23  negados por sshd: un reenvio -L que no llega al 22 de la Jetson, un pty (-tt) que sshd
         no da, y sftp, que no conecta;
  24     prueba-tope sale con 124 y el registro dice que duro <= 4 s;
  25     prueba-tope con el cliente matado al 1 s: despues `procesos` no deja ningun sleep;
  26-30  permitidos con 0: ayuda, info sistema, info red, procesos y registro 50.
Escribe una tabla Markdown en -Salida (barrera_<fecha>.md) y la salida de cada caso en casos\NN.txt.
Sale con 0 solo si los 30 casos dan lo esperado; con 1 si alguno no; con 2 si una entrada no vale.

Las opciones de ssh (BatchMode, IdentityFile, RequestTTY no...) van en ~/.ssh/config del autor, no
aqui; los casos 21 y 22 anaden -L y -tt a proposito. Los tar malos los fabrica
`python -m linux.tars_malos` con el venv de codigo\. Solo ASCII (PowerShell 5.1).

Lo corre el autor en el protocolo P-2 (y los agentes, con permiso, desde la fase 3).

.PARAMETER Alias
El alias de ssh de la cuenta de los agentes, explicito: nav-jetson (o nav-jetson-lan, -cable, -ts).

.PARAMETER Salida
La carpeta donde quedan la tabla y las salidas (p. ej. "Claude outputs/fases/007/barrera").

.PARAMETER TopeS
El tope en segundos de cada caso, de 10 a 300 (el plan usa 30).

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File codigo/linux/probar_barrera.ps1 -Alias nav-jetson -Salida "Claude outputs/fases/007/barrera" -TopeS 30
#>
[CmdletBinding()]
param(
    [string]$Alias = '',
    [string]$Salida = '',
    [int]$TopeS = 0
)

$ErrorActionPreference = 'Stop'

function Get-RutaAbsoluta([string]$ruta) {
    if ([System.IO.Path]::IsPathRooted($ruta)) { return [System.IO.Path]::GetFullPath($ruta) }
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).ProviderPath $ruta))
}

function Stop-Entrada([string]$motivo) {
    Write-Output "ERROR: $motivo"
    exit 2
}

# 1. Las entradas, antes de conectar a nada (principio 7).
if ($Alias -eq '') { Stop-Entrada 'falta -Alias (el alias de ssh de la cuenta de los agentes, p. ej. nav-jetson).' }
if ($Alias -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
    Stop-Entrada "el alias '$Alias' no vale: solo letras, cifras, punto, guion y guion bajo, sin empezar por guion."
}
if ($Salida -eq '') { Stop-Entrada 'falta -Salida (la carpeta de la tabla y las salidas).' }
if ($TopeS -lt 10 -or $TopeS -gt 300) { Stop-Entrada "-TopeS tiene que ir de 10 a 300 s (llego $TopeS)." }

$ssh = Get-Command 'ssh.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $ssh) { Stop-Entrada 'no se encuentra ssh.exe (el cliente OpenSSH de Windows).' }
$sftp = Get-Command 'sftp.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $sftp) { Stop-Entrada 'no se encuentra sftp.exe (viene con el cliente OpenSSH de Windows).' }
$codigoDir = Split-Path -Parent $PSScriptRoot
$python = Join-Path $codigoDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $py = Get-Command 'python.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $py) { Stop-Entrada "no esta $python ni python.exe en el PATH (hace falta para fabricar los tar malos)." }
    $python = $py.Source
}

$Salida = Get-RutaAbsoluta $Salida
$carpetaCasos = Join-Path $Salida 'casos'
New-Item -ItemType Directory -Force -Path $carpetaCasos | Out-Null
$marca = Get-Date -Format 'yyyyMMdd_HHmmss'
$tabla = Join-Path $Salida "barrera_$marca.md"
$vacio = Join-Path $carpetaCasos 'vacio.txt'
[System.IO.File]::WriteAllBytes($vacio, [byte[]]@())

Write-Output "Probando la barrera por '$Alias' (tope $TopeS s por caso) con $($ssh.Source)"
Write-Output "  salida: $Salida"

# 2. Lanzar un programa con tope y recoger su salida.
# Start-Process de PowerShell 5.1 junta -ArgumentList con espacios y no cita nada: una ruta con un
# espacio llega partida (P-2, 2026-11-02: con -Salida "Claude outputs/...", tars_malos recibio
# 'outputs\fases\...' suelto y paro). Cada argumento se cita con las reglas de CommandLineToArgvW
# y se pasa una sola cadena, como recomienda la ayuda de Start-Process.
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

function Invoke-Proceso {
    param(
        [string]$Exe,
        [string[]]$Argumentos,
        [string]$Entrada,
        [int]$Tope,
        [int]$MatarA = 0,
        [string]$Carpeta = ''
    )
    $out = Join-Path $carpetaCasos 'tmp_out.txt'
    $err = Join-Path $carpetaCasos 'tmp_err.txt'
    if ($Entrada -eq '') { $Entrada = $vacio }
    if ($Carpeta -eq '') { $Carpeta = (Get-Location).ProviderPath }
    $reloj = [System.Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process -FilePath $Exe -ArgumentList (ConvertTo-LineaArgumentos $Argumentos) -RedirectStandardInput $Entrada `
        -RedirectStandardOutput $out -RedirectStandardError $err -WorkingDirectory $Carpeta -NoNewWindow -PassThru
    $null = $p.Handle   # PowerShell 5.1: sin tomar el handle, ExitCode queda vacio
    $matado = $false
    $porTope = $false
    if ($MatarA -gt 0) {
        if (-not $p.WaitForExit($MatarA * 1000)) { try { $p.Kill() } catch { }; $matado = $true }
    } elseif (-not $p.WaitForExit($Tope * 1000)) {
        try { $p.Kill() } catch { }
        $porTope = $true
    }
    $null = $p.WaitForExit(5000)
    $p.WaitForExit()
    $reloj.Stop()
    # -2: el cliente se mato a proposito (caso 25); -1: se paso del tope y se corto.
    $codigo = if ($matado) { -2 } elseif ($porTope) { -1 } else { $p.ExitCode }
    $stdout = ''
    $stderr = ''
    if (Test-Path -LiteralPath $out) { $stdout = [System.IO.File]::ReadAllText($out) }
    if (Test-Path -LiteralPath $err) { $stderr = [System.IO.File]::ReadAllText($err) }
    return @{ Codigo = $codigo; Stdout = $stdout; Stderr = $stderr; Segundos = [math]::Round($reloj.Elapsed.TotalSeconds, 2); Matado = $matado }
}

function Invoke-Ssh([string[]]$Argumentos, [string]$Entrada = '', [int]$MatarA = 0) {
    return Invoke-Proceso -Exe $ssh.Source -Argumentos $Argumentos -Entrada $Entrada -Tope $TopeS -MatarA $MatarA
}

$casos = New-Object System.Collections.ArrayList
function Add-Caso([int]$N, [string]$Nombre, [string]$Esperado, [string]$Obtenido, [bool]$Pasa, $R) {
    $archivo = Join-Path $carpetaCasos ("{0:D2}.txt" -f $N)
    $texto = "caso $N`: $Nombre`nesperado: $Esperado`nobtenido: $Obtenido`npasa: $Pasa`n"
    if ($null -ne $R) {
        $texto += "codigo: $($R.Codigo)  segundos: $($R.Segundos)`n--- stdout ---`n$($R.Stdout)`n--- stderr ---`n$($R.Stderr)`n"
    }
    [System.IO.File]::WriteAllText($archivo, $texto)
    $null = $casos.Add(@{ N = $N; Nombre = $Nombre; Esperado = $Esperado; Obtenido = $Obtenido; Pasa = $Pasa })
    $marcaPasa = if ($Pasa) { 'si' } else { 'NO' }
    Write-Output ("  [{0,2}] {1,-4} {2}" -f $N, $marcaPasa, $Nombre)
}

# 3. Los casos.
# 1: sin orden.
$r = Invoke-Ssh @($Alias)
Add-Caso 1 'ssh sin orden' 'codigo 126' "codigo $($r.Codigo)" ($r.Codigo -eq 126) $r

# 2-16: negados por el guardian.
$negados = @(
    'sudo true', 'apt-get install x', 'reboot', 'systemctl stop ollama', 'nvpmodel -m 0', 'jetson_clocks',
    'bash -c id', 'py wip os', 'py wip tracker --record /etc/x', 'traer ../../etc/passwd', 'info "red; id"',
    'docker ps', 'ollama list', 'crontab -l', 'git push'
)
$n = 2
foreach ($orden in $negados) {
    $r = Invoke-Ssh @($Alias, $orden)
    Add-Caso $n $orden 'codigo 126' "codigo $($r.Codigo)" ($r.Codigo -eq 126) $r
    $n += 1
}

# 17-20: cuatro tar malos por wip recibir, sin que cambie wip estado.
$carpetaTars = Join-Path $carpetaCasos 'tars'
$fabrica = Invoke-Proceso -Exe $python -Argumentos @('-m', 'linux.tars_malos', '--destino', $carpetaTars) -Entrada '' -Tope 60 -Carpeta $codigoDir
if ($fabrica.Codigo -ne 0) { Write-Output "ERROR: no se pudieron fabricar los tar malos: $($fabrica.Stderr)"; exit 2 }
$estado0 = Invoke-Ssh @($Alias, 'wip estado')
foreach ($nombre in @('padre', 'absoluta', 'enlace', 'nrrd')) {
    $tar = Join-Path $carpetaTars "$nombre.tar"
    if (-not (Test-Path -LiteralPath $tar)) { Write-Output "ERROR: no se fabrico $tar."; exit 2 }
    $r = Invoke-Ssh @($Alias, 'wip recibir') -Entrada $tar
    $estado1 = Invoke-Ssh @($Alias, 'wip estado')
    $igual = ($estado1.Stdout -eq $estado0.Stdout) -and ($estado1.Codigo -eq $estado0.Codigo)
    Add-Caso $n "wip recibir con el tar '$nombre'" 'codigo 126 y wip estado igual' "codigo $($r.Codigo), estado igual: $igual" (($r.Codigo -eq 126) -and $igual) $r
    $n += 1
}

# 21: reenvio -L: aunque el cliente abra el 9999, por el no llega el saludo del sshd de la Jetson.
$pL = Start-Process -FilePath $ssh.Source -ArgumentList (ConvertTo-LineaArgumentos @('-o', 'ClearAllForwardings=no', '-L', '9999:127.0.0.1:22', $Alias, 'prueba-tope')) `
    -RedirectStandardInput $vacio -RedirectStandardOutput (Join-Path $carpetaCasos 'tmp_out.txt') `
    -RedirectStandardError (Join-Path $carpetaCasos 'tmp_err.txt') -NoNewWindow -PassThru
$null = $pL.Handle
Start-Sleep -Milliseconds 1500
$saludo = ''
$conecto = $false
try {
    $cliente = New-Object System.Net.Sockets.TcpClient
    $intento = $cliente.BeginConnect('127.0.0.1', 9999, $null, $null)
    if ($intento.AsyncWaitHandle.WaitOne(1500) -and $cliente.Connected) {
        $conecto = $true
        $flujo = $cliente.GetStream()
        $flujo.ReadTimeout = 2000
        $buffer = New-Object byte[] 256
        try { $leidos = $flujo.Read($buffer, 0, 256); $saludo = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $leidos) } catch { $saludo = '' }
    }
    $cliente.Close()
} catch { $saludo = '' }
if (-not $pL.WaitForExit($TopeS * 1000)) { try { $pL.Kill() } catch { } }
$rL = @{ Codigo = $pL.ExitCode; Stdout = [System.IO.File]::ReadAllText((Join-Path $carpetaCasos 'tmp_out.txt')); Stderr = [System.IO.File]::ReadAllText((Join-Path $carpetaCasos 'tmp_err.txt')); Segundos = 0 }
$sinTunel = -not ($saludo -match 'SSH-')
Add-Caso 21 'ssh -L 9999:127.0.0.1:22 (reenvio)' 'sin saludo SSH por el 9999' "conecto al 9999: $conecto; saludo: '$($saludo.Trim())'" $sinTunel $rL

# 22: pty forzado (-tt): sshd no lo da (PermitTTY no), o el guardian lo niega.
$r = Invoke-Ssh @('-tt', $Alias, 'ayuda')
$sinPty = ($r.Stderr -match 'PTY allocation request failed') -or ($r.Codigo -eq 126)
Add-Caso 22 'ssh -tt ayuda (pty)' "'PTY allocation request failed' o codigo 126" "codigo $($r.Codigo); stderr: $($r.Stderr.Trim())" $sinPty $r

# 23: sftp no conecta (ForceCommand sustituye al subsistema y el guardian lo niega).
$lote = Join-Path $carpetaCasos 'sftp_lote.txt'
[System.IO.File]::WriteAllText($lote, "ls`n")
$r = Invoke-Proceso -Exe $sftp.Source -Argumentos @('-b', $lote, $Alias) -Entrada '' -Tope $TopeS
Add-Caso 23 'sftp -b ls' 'codigo != 0' "codigo $($r.Codigo)" ($r.Codigo -ne 0) $r

# 24: prueba-tope sale con 124 y el registro dice <= 4 s.
$r = Invoke-Ssh @($Alias, 'prueba-tope')
$reg = Invoke-Ssh @($Alias, 'registro 1')
$duracion = -1
$ordenReg = ''
$codigoReg = -1
try {
    $json = ($reg.Stdout.Trim() -split "`r?`n" | Select-Object -Last 1) | ConvertFrom-Json
    $duracion = [double]$json.duracion_s
    $ordenReg = [string]$json.orden
    $codigoReg = [int]$json.codigo
} catch { }
$pasa24 = ($r.Codigo -eq 124) -and ($ordenReg -eq 'prueba-tope') -and ($codigoReg -eq 124) -and ($duracion -ge 0) -and ($duracion -le 4)
Add-Caso 24 'prueba-tope (tope de 3 s)' 'codigo 124; registro: prueba-tope, 124, duracion_s <= 4' "codigo $($r.Codigo) en $($r.Segundos) s; registro: '$ordenReg', $codigoReg, $duracion s" $pasa24 $r

# 25: el cliente muere al 1 s y el guardian para el grupo: procesos no deja ningun sleep.
$r = Invoke-Ssh @($Alias, 'prueba-tope') -MatarA 1
Start-Sleep -Seconds 2
$procesos = Invoke-Ssh @($Alias, 'procesos')
$sinSleep = ($procesos.Codigo -eq 0) -and -not ($procesos.Stdout -match 'sleep 30')
Add-Caso 25 'prueba-tope con el cliente matado al 1 s' 'procesos con 0 y sin "sleep 30"' "cliente matado: $($r.Matado); procesos codigo $($procesos.Codigo); sleep 30: $($procesos.Stdout -match 'sleep 30')" ($sinSleep -and $r.Matado) $procesos

# 26-30: permitidos.
$n = 26
foreach ($orden in @('ayuda', 'info sistema', 'info red', 'procesos', 'registro 50')) {
    $r = Invoke-Ssh @($Alias, $orden)
    Add-Caso $n $orden 'codigo 0' "codigo $($r.Codigo)" ($r.Codigo -eq 0) $r
    $n += 1
}

# 4. La tabla.
$pasan = @($casos | Where-Object { $_.Pasa }).Count
$lineas = @("# Barrera de los agentes: probar_barrera.ps1 por '$Alias', $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')", '',
    "Casos: $pasan de $($casos.Count). Tope por caso: $TopeS s. Salidas en casos\NN.txt.", '',
    '| # | Caso | Esperado | Obtenido | Pasa |', '|---|---|---|---|---|')
foreach ($c in $casos) {
    $p = if ($c.Pasa) { 'si' } else { 'NO' }
    $lineas += "| $($c.N) | $($c.Nombre -replace '\|', '\|') | $($c.Esperado -replace '\|', '\|') | $(($c.Obtenido -replace '\|', '\|') -replace "`r?`n", ' ') | $p |"
}
[System.IO.File]::WriteAllLines($tabla, $lineas)
Write-Output ''
Write-Output "Casos: $pasan de $($casos.Count)"
Write-Output "Tabla: $tabla"
if ($pasan -eq $casos.Count) { exit 0 }
exit 1
