<#
.SYNOPSIS
Prueba los hooks del buzon de peticiones (equipo/hooks) sin hacer ningun commit ni push.

.DESCRIPTION
Cinco bloques, los del criterio de la fase 1 de la meta 005 (specs/005-equipo-consulta/plan.md):
 (1) revisar_peticiones.sh con 8 listas de cambios: 1 pasa y 7 se rechazan, cada una con su mensaje.
 (2) pre-commit en un repo temporal bajo -Trabajo (git init, core.hooksPath, git add, sin commit): 3 casos.
 (3) pre-push con lineas de stdin armadas con commits del historial real del repo (solo lectura): 3 casos.
 (4) La sintaxis de este script (parser de PowerShell) y la de los tres sh (sh -n): 0 errores.
 (5) Los cinco comandos de "Como se envia" de peticiones/README.md no llevan el separador "--" suelto,
     ni "&&", ni "$", ni "\".
Imprime caso / esperado / obtenido y, al final, "N de M". Sale con codigo 0 si pasan todos, 1 si no.
Todo proceso externo lleva tope de tiempo (-TopeSegundos). El script es solo ASCII a proposito: PowerShell 5.1
lee un .ps1 sin BOM con la pagina de codigos ANSI.

La entrada estandar de cada hook va por un archivo temporal y una redireccion del sh, no por
Process.StandardInput: en .NET Framework ese StreamWriter escribe un BOM UTF-8 nada mas crearse, y el hook
leeria "<BOM>A" en vez de "A".

.PARAMETER Trabajo
Carpeta de trabajo (p. ej. el scratchpad). Dentro crea y borra "probar_hooks/".

.PARAMETER Repo
Raiz del repo del proyecto. Por defecto, dos niveles arriba de este script.

.PARAMETER Sh
Ruta de sh.exe. Por defecto se busca en el PATH y, si no, junto al git de Git for Windows (usr\bin\sh.exe).

.PARAMETER TopeSegundos
Tope por proceso externo. Por defecto 60.

.PARAMETER LocalOid
Commit del historial real que hace de "lo local" en el bloque (3). Por defecto c252259 (cierre de la meta 004).

.PARAMETER RemoteOid
Commit del historial real que hace de "lo remoto" en el bloque (3). Por defecto 354afe4; entre el y LocalOid
hay cambios en docs/, specs/ y memory.md.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File equipo\pruebas\probar_hooks.ps1 -Trabajo $env:TEMP\hooks
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Trabajo,
    [string]$Repo = '',
    [string]$Sh = '',
    [int]$TopeSegundos = 60,
    [string]$LocalOid = 'c252259',
    [string]$RemoteOid = '354afe4'
)

$ErrorActionPreference = 'Stop'
$inicio = Get-Date

if ($Repo -eq '') {
    $Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}
$Repo = (Resolve-Path $Repo).Path
$hooks = Join-Path $Repo 'equipo\hooks'
$readme = Join-Path $Repo 'peticiones\README.md'

if ($Sh -eq '') {
    $cmd = Get-Command sh.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $Sh = $cmd.Source
    } else {
        $git = (Get-Command git.exe -ErrorAction SilentlyContinue)
        if (-not $git) { throw 'No se encuentra git.exe en el PATH.' }
        $raizGit = Split-Path (Split-Path $git.Source -Parent) -Parent
        $Sh = Join-Path $raizGit 'usr\bin\sh.exe'
    }
}
if (-not (Test-Path $Sh)) { throw "No se encuentra sh.exe (buscado en '$Sh'). Instala Git for Windows o pasa -Sh." }

$utf8SinBom = New-Object System.Text.UTF8Encoding($false)
$oAcento = [string][char]0x00F3
$lineaDecision = "Decisi${oAcento}n: pendiente"
$tab = [string][char]9

$base = Join-Path $Trabajo 'probar_hooks'
if (Test-Path $base) { Remove-Item -Recurse -Force $base }
New-Item -ItemType Directory -Force -Path $base | Out-Null
$archivoEntrada = Join-Path $base 'entrada.txt'

function ConvertTo-RutaSh([string]$ruta) {
    # C:\a\b -> C:/a/b (el sh de Git for Windows lo entiende tal cual)
    return $ruta.Replace('\', '/')
}

function Invoke-Proceso {
    param(
        [string]$Exe,
        [string[]]$Argumentos,
        [string]$Cwd,
        [int]$Tope = 60
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Exe
    $partes = foreach ($a in $Argumentos) { if ($a -match '[\s"]') { '"' + $a.Replace('"', '\"') + '"' } else { $a } }
    $psi.Arguments = ($partes -join ' ')
    $psi.WorkingDirectory = $Cwd
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $p = [System.Diagnostics.Process]::Start($psi)
    $salidaT = $p.StandardOutput.ReadToEndAsync()
    $errorT = $p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit($Tope * 1000)) {
        try { $p.Kill() } catch { }
        return [pscustomobject]@{ Codigo = -1; Salida = "(tope de $Tope s superado)" }
    }
    $p.WaitForExit()
    $texto = ($salidaT.Result + $errorT.Result).Trim()
    return [pscustomobject]@{ Codigo = $p.ExitCode; Salida = $texto }
}

function Invoke-Sh {
    # Corre "/bin/sh <Script> <Argumentos>" en <Cwd> con <Entrada> como entrada estandar (vacia si no se da).
    param(
        [string]$Script,
        [string[]]$Argumentos = @(),
        [string]$Cwd,
        [string]$Entrada = '',
        [int]$Tope = 60
    )
    [System.IO.File]::WriteAllText($archivoEntrada, $Entrada, $utf8SinBom)
    $args2 = ($Argumentos | ForEach-Object { "'" + $_ + "'" }) -join ' '
    $orden = "exec /bin/sh '$Script' $args2 < '$(ConvertTo-RutaSh $archivoEntrada)'"
    return Invoke-Proceso -Exe $Sh -Argumentos @('-c', $orden) -Cwd $Cwd -Tope $Tope
}

$resultados = New-Object System.Collections.ArrayList
function Anota([string]$bloque, [string]$caso, [string]$esperado, [string]$obtenido, [bool]$ok) {
    $null = $resultados.Add([pscustomobject]@{ Bloque = $bloque; Caso = $caso; Esperado = $esperado; Obtenido = $obtenido; OK = $ok })
    $marca = if ($ok) { 'OK   ' } else { 'FALLA' }
    Write-Host ("[{0}] {1} | {2} | esperado: {3} | obtenido: {4}" -f $marca, $bloque, $caso, $esperado, $obtenido)
}

function Resumen-Salida([string]$texto) {
    if ($texto -eq '') { return '(sin salida)' }
    $primera = ($texto -split "`n")[0].Trim()
    if ($primera.Length -gt 110) { $primera = $primera.Substring(0, 110) + '...' }
    return $primera
}

Write-Host "probar_hooks.ps1 - repo: $Repo"
Write-Host "sh: $Sh"
Write-Host ''

# ---------------------------------------------------------------- (1) revisar_peticiones.sh
Write-Host '(1) revisar_peticiones.sh con 8 listas'
$revisar = ConvertTo-RutaSh (Join-Path $hooks 'revisar_peticiones.sh')
$listas = @(
    @{ Caso = 'A peticiones/2026-10-28-kike-x.md';            Lineas = @("A${tab}peticiones/2026-10-28-kike-x.md");          Codigo = 0; Mensaje = '' },
    @{ Caso = 'A codigo/x.py';                                Lineas = @("A${tab}codigo/x.py");                              Codigo = 1; Mensaje = 'codigo/x.py: solo se pueden enviar peticiones nuevas' },
    @{ Caso = 'M peticiones/y.md';                            Lineas = @("M${tab}peticiones/y.md");                          Codigo = 1; Mensaje = 'peticiones/y.md: una peticion enviada no se modifica ni se borra' },
    @{ Caso = 'D peticiones/y.md';                            Lineas = @("D${tab}peticiones/y.md");                          Codigo = 1; Mensaje = 'peticiones/y.md: una peticion enviada no se modifica ni se borra' },
    @{ Caso = 'A peticiones/README.md';                       Lineas = @("A${tab}peticiones/README.md");                     Codigo = 1; Mensaje = 'peticiones/README.md: ese archivo es del proyecto' },
    @{ Caso = 'M peticiones/_plantilla.md';                   Lineas = @("M${tab}peticiones/_plantilla.md");                 Codigo = 1; Mensaje = 'peticiones/_plantilla.md: ese archivo es del proyecto' },
    @{ Caso = 'A peticiones/x.txt';                           Lineas = @("A${tab}peticiones/x.txt");                         Codigo = 1; Mensaje = 'peticiones/x.txt: una peticion es un archivo .md' },
    @{ Caso = 'A peticiones/ok.md + M docs/BACKLOG.md';       Lineas = @("A${tab}peticiones/ok.md", "M${tab}docs/BACKLOG.md"); Codigo = 1; Mensaje = 'docs/BACKLOG.md: solo se pueden enviar peticiones nuevas' }
)
foreach ($l in $listas) {
    $entrada = ($l.Lineas -join "`n") + "`n"
    $r = Invoke-Sh -Script $revisar -Cwd $Repo -Entrada $entrada -Tope $TopeSegundos
    $ok = ($r.Codigo -eq $l.Codigo) -and ($l.Mensaje -eq '' -or $r.Salida.Contains($l.Mensaje))
    if ($l.Codigo -eq 0) { $ok = $ok -and ($r.Salida -eq '') }
    if ($l.Caso -like '*ok.md*') { $ok = $ok -and (-not $r.Salida.Contains('peticiones/ok.md')) }
    Anota '1' $l.Caso ("codigo {0}{1}" -f $l.Codigo, $(if ($l.Mensaje) { ', mensaje con "' + $l.Mensaje + '"' } else { ', sin salida' })) ("codigo {0}: {1}" -f $r.Codigo, (Resumen-Salida $r.Salida)) $ok
}
Write-Host ''

# ---------------------------------------------------------------- (2) pre-commit en un repo temporal
Write-Host '(2) pre-commit en un repo temporal (git init, core.hooksPath, git add, sin commit)'
$repoTmp = Join-Path $base 'repo'
New-Item -ItemType Directory -Force -Path $repoTmp | Out-Null
& git -C $repoTmp init -q -b main
if ($LASTEXITCODE -ne 0) { throw 'git init fallo en el repo temporal.' }
New-Item -ItemType Directory -Force -Path (Join-Path $repoTmp 'equipo') | Out-Null
Copy-Item -Recurse -Force $hooks (Join-Path $repoTmp 'equipo\hooks')
& git -C $repoTmp config core.hooksPath equipo/hooks
& git -C $repoTmp config core.autocrlf false
New-Item -ItemType Directory -Force -Path (Join-Path $repoTmp 'peticiones') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $repoTmp 'codigo') | Out-Null

$fecha = Get-Date -Format 'yyyy-MM-dd'
$plantillaOk = "> Peticion escrita por el agente de consulta para Prueba (prueba), el $fecha.`n`n# Peticion - prueba del hook`n`n## Que se pide`n`nNada: es una prueba.`n`n## Decision del autor`n`n$lineaDecision`n"
$plantillaSin = "> Peticion escrita por el agente de consulta para Prueba (prueba), el $fecha.`n`n# Peticion - prueba del hook sin decision`n`n## Que se pide`n`nNada: es una prueba.`n"

function Probar-PreCommit([string]$caso, [string]$relativo, [string]$contenido, [int]$codigoEsperado, [string]$mensaje) {
    $destino = Join-Path $repoTmp ($relativo.Replace('/', '\'))
    [System.IO.File]::WriteAllText($destino, $contenido, $utf8SinBom)
    & git -C $repoTmp add $relativo
    if ($LASTEXITCODE -ne 0) { throw "git add fallo para $relativo" }
    $r = Invoke-Sh -Script 'equipo/hooks/pre-commit' -Cwd $repoTmp -Tope $TopeSegundos
    & git -C $repoTmp reset -q
    Remove-Item -Force $destino
    $ok = ($r.Codigo -eq $codigoEsperado) -and ($mensaje -eq '' -or $r.Salida.Contains($mensaje))
    Anota '2' $caso ("codigo {0}{1}" -f $codigoEsperado, $(if ($mensaje) { ', mensaje con "' + $mensaje + '"' } else { '' })) ("codigo {0}: {1}" -f $r.Codigo, (Resumen-Salida $r.Salida)) $ok
}

Probar-PreCommit "peticion nueva con '$lineaDecision'" "peticiones/$fecha-prueba-hook.md" $plantillaOk 0 ''
Probar-PreCommit 'archivo fuera de peticiones/ (codigo/x.py)' 'codigo/x.py' "print('x')`n" 1 'codigo/x.py: solo se pueden enviar peticiones nuevas'
Probar-PreCommit "peticion nueva sin la linea '$lineaDecision'" "peticiones/$fecha-prueba-sin-decision.md" $plantillaSin 1 'le falta la linea'
Write-Host ''

# ---------------------------------------------------------------- (3) pre-push con el historial real
Write-Host '(3) pre-push con lineas de stdin armadas con commits del historial real (solo lectura)'
$localFull = (& git -C $Repo rev-parse --verify "$LocalOid^{commit}").Trim()
$remoteFull = (& git -C $Repo rev-parse --verify "$RemoteOid^{commit}").Trim()
if (-not $localFull -or -not $remoteFull) { throw "No se resuelven $LocalOid o $RemoteOid en $Repo." }
$ceros = '0' * 40
$remotoFalso = 'https://example.invalid/prueba.git'

$casos3 = @(
    @{ Caso = "rango $RemoteOid..$LocalOid (toca docs/ y specs/)"; Linea = "refs/heads/main $localFull refs/heads/main $remoteFull`n"; Mensaje = 'solo se pueden enviar peticiones nuevas' },
    @{ Caso = '(delete) de una rama remota';                       Linea = "(delete) $ceros refs/heads/main $remoteFull`n";           Mensaje = 'no se borran ramas' },
    @{ Caso = 'remote-oid en ceros (usa origin/main..)';           Linea = "refs/heads/main $localFull refs/heads/main $ceros`n";     Mensaje = '' }
)
foreach ($c in $casos3) {
    $r = Invoke-Sh -Script 'equipo/hooks/pre-push' -Argumentos @('origin', $remotoFalso) -Cwd $Repo -Entrada $c.Linea -Tope $TopeSegundos
    $ok = ($r.Codigo -eq 1) -and ($r.Salida -ne '') -and ($c.Mensaje -eq '' -or $r.Salida.Contains($c.Mensaje))
    Anota '3' $c.Caso ("codigo 1{0}" -f $(if ($c.Mensaje) { ', mensaje con "' + $c.Mensaje + '"' } else { ', con mensaje' })) ("codigo {0}: {1}" -f $r.Codigo, (Resumen-Salida $r.Salida)) $ok
}
Write-Host ''

# ---------------------------------------------------------------- (4) sintaxis
Write-Host '(4) sintaxis: este script con el parser de PowerShell y los tres sh con sh -n'
$tokens = $null; $errores = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile($PSCommandPath, [ref]$tokens, [ref]$errores)
$nErr = if ($errores) { $errores.Count } else { 0 }
Anota '4' 'probar_hooks.ps1 (parser de PowerShell)' '0 errores' "$nErr errores" ($nErr -eq 0)
foreach ($f in @('revisar_peticiones.sh', 'pre-commit', 'pre-push')) {
    $r = Invoke-Proceso -Exe $Sh -Argumentos @('-n', (ConvertTo-RutaSh (Join-Path $hooks $f))) -Cwd $Repo -Tope $TopeSegundos
    Anota '4' "$f (sh -n)" 'codigo 0' ("codigo {0}: {1}" -f $r.Codigo, (Resumen-Salida $r.Salida)) ($r.Codigo -eq 0)
}
Write-Host ''

# ---------------------------------------------------------------- (5) los cinco comandos del README
Write-Host '(5) los cinco comandos de "Como se envia" en peticiones/README.md'
$lineasReadme = [System.IO.File]::ReadAllLines($readme, $utf8SinBom)
$dentro = $false
$comandos = @()
foreach ($linea in $lineasReadme) {
    if ($linea -match '^## C.mo se env.a') { $dentro = $true; continue }
    if ($dentro -and $linea -match '^## ') { break }
    if ($dentro -and $linea -match '^(\d)\. `([^`]+)`') { $comandos += $Matches[2] }
}
Anota '5' 'hay exactamente cinco comandos numerados' '5' "$($comandos.Count)" ($comandos.Count -eq 5)
$n = 0
foreach ($cmdo in $comandos) {
    $n++
    $malo = @()
    if ($cmdo -match '(^|\s)--(\s|$)') { $malo += 'separador --' }
    if ($cmdo.Contains('&&')) { $malo += '&&' }
    if ($cmdo.Contains('$')) { $malo += '$' }
    if ($cmdo.Contains('\')) { $malo += '\' }
    $obt = if ($malo.Count -eq 0) { 'limpio' } else { 'lleva ' + ($malo -join ', ') }
    Anota '5' ("comando {0}: {1}" -f $n, $cmdo) 'sin separador --, &&, $ ni \' $obt ($malo.Count -eq 0)
}
Write-Host ''

# ---------------------------------------------------------------- total
if (Test-Path $base) { Remove-Item -Recurse -Force $base }
$total = $resultados.Count
$pasan = @($resultados | Where-Object { $_.OK }).Count
$segundos = [math]::Round(((Get-Date) - $inicio).TotalSeconds, 1)
Write-Host ("Bloques: (1) {0} de 8, (2) {1} de 3, (3) {2} de 3, (4) {3} de 4, (5) {4} de 6" -f `
    @($resultados | Where-Object { $_.Bloque -eq '1' -and $_.OK }).Count, `
    @($resultados | Where-Object { $_.Bloque -eq '2' -and $_.OK }).Count, `
    @($resultados | Where-Object { $_.Bloque -eq '3' -and $_.OK }).Count, `
    @($resultados | Where-Object { $_.Bloque -eq '4' -and $_.OK }).Count, `
    @($resultados | Where-Object { $_.Bloque -eq '5' -and $_.OK }).Count)
Write-Host ("{0} de {1} en {2} s" -f $pasan, $total, $segundos)
if ($pasan -eq $total) { exit 0 } else { exit 1 }
