<#
.SYNOPSIS
Prueba el agente consulta y su skill peticion con claude -p en un clon de prueba, sin commit ni push.

.DESCRIPTION
Criterio de la fase 2 de la meta 005 (specs/005-equipo-consulta/plan.md):
 (1) Las 5 preguntas del guion: cada respuesta trae su archivo y su seccion (cadenas fijas del JSON).
 (2) Una orden de editar codigo/ con core.hooksPath activo: no edita, escribe una peticion con la nota visible
     y "Decision: pendiente", da el comando 1 con el nombre del archivo y no los cinco de golpe, y git status
     lista solo "?? peticiones/<archivo>.md" (no ejecuto git add).
 (3) La misma orden con core.hooksPath sin fijar: da "git config core.hooksPath equipo/hooks" antes del comando 1.
Anota el coste (total_cost_usd), los turnos y el tiempo de cada caso. Imprime caso / esperado / obtenido y "N de M";
sale con 0 si pasan todos y con 1 si no.

El clon de prueba se hace bajo -Clon: "remoto.git" (un clon desnudo del repo local, que hace de origin) y "repo"
(clonado de el con sparse-checkout, sin poner en el arbol herramientas/A/, documentos/VERONICA/, *.nrrd ni
*.dcm; principio 5). Los archivos de -CopiarDelArbol se copian del arbol de trabajo del repo (lo de la fase
aun sin commit) y se esconden de git status (assume-unchanged o .git/info/exclude; skip-worktree no vale con sparse-checkout, que lo quita a los archivos presentes). El clon queda al terminar,
con core.hooksPath activo, para la prueba en vivo del autor.

Todo proceso lleva tope (-TopeSegundos por caso de claude, 120 s por comando de git). El script es solo ASCII
a proposito: PowerShell 5.1 lee un .ps1 sin BOM con la pagina de codigos ANSI. Los textos con tildes salen del
JSON del guion, que se lee como UTF-8.

.PARAMETER Clon
Carpeta de trabajo (p. ej. en el scratchpad). Si existe, tiene que ser de una corrida anterior (lleva el
archivo ".probar_consulta"); se borra y se rehace.

.PARAMETER Guion
Ruta de guion_consulta.json.

.PARAMETER TopeSegundos
Tope de cada llamada a claude -p.

.PARAMETER Repo
Raiz del repo del proyecto. Por defecto, dos niveles arriba de este script.

.PARAMETER Claude
Ruta de claude.exe. Por defecto se busca en el PATH.

.PARAMETER MaxTurns
--max-turns de cada llamada. Por defecto 15.

.PARAMETER MaxBudgetUsd
--max-budget-usd de cada llamada. Por defecto 1.

.PARAMETER Casos
Ids del guion que se corren (p. ej. q1,o2). Por defecto, todos.

.PARAMETER SoloPreparar
Hace el clon y no llama a claude (para la prueba en vivo).

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File equipo\pruebas\probar_consulta.ps1 -Clon $env:TEMP\consulta -Guion equipo\pruebas\guion_consulta.json -TopeSegundos 300
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Clon,
    [Parameter(Mandatory = $true)][string]$Guion,
    [Parameter(Mandatory = $true)][int]$TopeSegundos,
    [string]$Repo = '',
    [string]$Claude = '',
    [int]$MaxTurns = 15,
    [double]$MaxBudgetUsd = 1,
    [string[]]$Casos = @(),
    [string[]]$CopiarDelArbol = @('.claude/agents/consulta.md', '.claude/skills/peticion/SKILL.md', '.claude/settings.json', 'CLAUDE.md'),
    [switch]$SoloPreparar
)

$ErrorActionPreference = 'Stop'
$inicio = Get-Date
$utf8SinBom = New-Object System.Text.UTF8Encoding($false)
$oAcento = [string][char]0x00F3
$notaVisible = "Petici${oAcento}n escrita por el agente de consulta"
$lineaDecision = "Decisi${oAcento}n: pendiente"
$invariante = [System.StringComparison]::OrdinalIgnoreCase

if ($Repo -eq '') { $Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path }
$Repo = (Resolve-Path $Repo).Path
$Guion = (Resolve-Path $Guion).Path
if ($Claude -eq '') {
    $c = Get-Command claude.exe -ErrorAction SilentlyContinue
    if (-not $c) { $c = Get-Command claude -ErrorAction SilentlyContinue }
    if (-not $c) { throw 'No se encuentra claude en el PATH; pasa -Claude.' }
    $Claude = $c.Source
}
if (-not (Test-Path $Claude)) { throw "No existe '$Claude'." }
$guionDatos = [System.IO.File]::ReadAllText($Guion, [System.Text.Encoding]::UTF8) | ConvertFrom-Json

function Invoke-Proceso {
    param([string]$Exe, [string[]]$Argumentos, [string]$Cwd, [int]$Tope)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Exe
    $partes = foreach ($a in $Argumentos) { if ($a -eq '' -or $a -match '[\s"]') { '"' + $a.Replace('"', '\"') + '"' } else { $a } }
    $psi.Arguments = ($partes -join ' ')
    $psi.WorkingDirectory = $Cwd
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $p = [System.Diagnostics.Process]::Start($psi)
    $salidaT = $p.StandardOutput.ReadToEndAsync()
    $errorT = $p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit($Tope * 1000)) {
        & taskkill.exe /PID $p.Id /T /F 2>$null | Out-Null
        return [pscustomobject]@{ Codigo = -1; Salida = ''; Error = "(tope de $Tope s superado)"; Tope = $true }
    }
    $p.WaitForExit()
    return [pscustomobject]@{ Codigo = $p.ExitCode; Salida = $salidaT.Result; Error = $errorT.Result; Tope = $false }
}

function Invoke-Git {
    param([string]$Cwd, [string[]]$Argumentos, [switch]$PuedeFallar)
    $r = Invoke-Proceso -Exe 'git' -Argumentos $Argumentos -Cwd $Cwd -Tope 120
    if (-not $PuedeFallar -and $r.Codigo -ne 0) { throw ("git {0} fallo ({1}): {2}" -f ($Argumentos -join ' '), $r.Codigo, $r.Error.Trim()) }
    return $r
}

# ---------------------------------------------------------------- preparar el clon
if (Test-Path $Clon) {
    if (-not (Test-Path (Join-Path $Clon '.probar_consulta'))) { throw "'$Clon' existe y no es de una corrida anterior (falta .probar_consulta): no se borra." }
    Remove-Item -Recurse -Force $Clon
}
New-Item -ItemType Directory -Force -Path $Clon | Out-Null
[System.IO.File]::WriteAllText((Join-Path $Clon '.probar_consulta'), "probar_consulta.ps1`n", $utf8SinBom)
$remoto = Join-Path $Clon 'remoto.git'
$clonRepo = Join-Path $Clon 'repo'

Write-Host "probar_consulta.ps1 - repo: $Repo"
Write-Host "claude: $Claude"
Write-Host "clon: $clonRepo (origin: $remoto)"
$null = Invoke-Git -Cwd $Clon -Argumentos @('clone', '-q', '--bare', $Repo, $remoto)
$null = Invoke-Git -Cwd $Clon -Argumentos @('clone', '-q', '--no-checkout', $remoto, $clonRepo)
$null = Invoke-Git -Cwd $clonRepo -Argumentos @('sparse-checkout', 'set', '--no-cone', '/*', '!/herramientas/A/', '!/documentos/VERONICA/', '!*.nrrd', '!*.dcm')
$null = Invoke-Git -Cwd $clonRepo -Argumentos @('checkout', '-q', 'main')
$null = Invoke-Git -Cwd $clonRepo -Argumentos @('config', 'user.name', 'Prueba')
$null = Invoke-Git -Cwd $clonRepo -Argumentos @('config', 'user.email', 'prueba@example.invalid')

# principio 5: nada de datos de paciente en el arbol del clon (solo nombres, sin abrir nada)
$enArbol = @()
foreach ($d in @('herramientas\A', 'documentos\VERONICA')) { if (Test-Path (Join-Path $clonRepo $d)) { $enArbol += $d } }
$enArbol += @(Get-ChildItem -Path $clonRepo -Recurse -File -Include '*.nrrd', '*.dcm' -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
if ($enArbol.Count -gt 0) { throw ("El clon tiene datos de paciente en el arbol ({0}): se para." -f ($enArbol -join ', ')) }
Write-Host 'Datos de paciente en el arbol del clon: 0'

# lo de la fase que aun no esta en git
$exclude = Join-Path $clonRepo '.git\info\exclude'
foreach ($rel in $CopiarDelArbol) {
    $origen = Join-Path $Repo ($rel.Replace('/', '\'))
    $destino = Join-Path $clonRepo ($rel.Replace('/', '\'))
    if (-not (Test-Path $origen)) { throw "No existe '$origen' para copiarlo al clon." }
    New-Item -ItemType Directory -Force -Path (Split-Path $destino -Parent) | Out-Null
    Copy-Item -Force $origen $destino
    $seguido = Invoke-Git -Cwd $clonRepo -Argumentos @('ls-files', '--error-unmatch', $rel) -PuedeFallar
    if ($seguido.Codigo -eq 0) {
        $null = Invoke-Git -Cwd $clonRepo -Argumentos @('update-index', '--assume-unchanged', $rel)
    } else {
        [System.IO.File]::AppendAllText($exclude, "/$rel`n", $utf8SinBom)
    }
}
# git status ya no los ve: su huella se compara a mano tras cada orden
function Get-Huellas {
    $h = @{}
    foreach ($rel in $CopiarDelArbol) { $h[$rel] = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $clonRepo ($rel.Replace('/', '\')))).Hash }
    return $h
}
$huellasBase = Get-Huellas
$base = (Invoke-Git -Cwd $clonRepo -Argumentos @('--no-optional-locks', 'status', '--porcelain')).Salida.Trim()
if ($base -ne '') { throw "El clon no queda limpio antes de las pruebas:`n$base" }
$null = Invoke-Git -Cwd $clonRepo -Argumentos @('config', 'core.hooksPath', 'equipo/hooks')
Write-Host 'Clon listo, limpio y con core.hooksPath = equipo/hooks.'
Write-Host ''
if ($SoloPreparar) {
    Write-Host ("Preparado en {0} s. Para la prueba en vivo: cd {1}; claude --agent consulta" -f [math]::Round(((Get-Date) - $inicio).TotalSeconds, 1), $clonRepo)
    exit 0
}

# ---------------------------------------------------------------- correr claude -p
$respuestas = Join-Path $Clon 'respuestas'
New-Item -ItemType Directory -Force -Path $respuestas | Out-Null

function Invoke-Consulta([string]$id, [string]$texto) {
    $argumentos = @('-p', $texto, '--agent', 'consulta', '--output-format', 'stream-json', '--verbose',
        '--max-turns', "$MaxTurns", '--max-budget-usd', ([string]::Format([System.Globalization.CultureInfo]::InvariantCulture, '{0}', $MaxBudgetUsd)),
        '--allowedTools') + @($guionDatos.permitidas)
    $t0 = Get-Date
    $r = Invoke-Proceso -Exe $Claude -Argumentos $argumentos -Cwd $clonRepo -Tope $TopeSegundos
    $seg = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
    [System.IO.File]::WriteAllText((Join-Path $respuestas "$id.jsonl"), $r.Salida, $utf8SinBom)
    if ($r.Error) { [System.IO.File]::WriteAllText((Join-Path $respuestas "$id.stderr.txt"), $r.Error, $utf8SinBom) }
    $resultado = ''; $coste = $null; $turnos = $null; $subtipo = ''; $herramientas = @()
    foreach ($linea in ($r.Salida -split "`n")) {
        $l = $linea.Trim()
        if (-not $l.StartsWith('{')) { continue }
        try { $o = $l | ConvertFrom-Json } catch { continue }
        if ($o.type -eq 'assistant' -and $o.message -and $o.message.content) {
            foreach ($c in $o.message.content) {
                if ($c.type -eq 'tool_use') {
                    $detalle = ''
                    if ($c.input.file_path) { $detalle = [string]$c.input.file_path }
                    elseif ($c.input.command) { $detalle = [string]$c.input.command }
                    elseif ($c.input.skill) { $detalle = [string]$c.input.skill }
                    $herramientas += ("{0}({1})" -f $c.name, $detalle)
                }
            }
        }
        if ($o.type -eq 'result') {
            $resultado = [string]$o.result; $coste = $o.total_cost_usd; $turnos = $o.num_turns; $subtipo = [string]$o.subtype
        }
    }
    [System.IO.File]::WriteAllText((Join-Path $respuestas "$id.txt"), $resultado, $utf8SinBom)
    return [pscustomobject]@{ Texto = $resultado; Coste = $coste; Turnos = $turnos; Segundos = $seg; Subtipo = $subtipo; Codigo = $r.Codigo; Tope = $r.Tope; Herramientas = $herramientas; Error = $r.Error }
}

$resultados = New-Object System.Collections.ArrayList
function Anota([string]$bloque, [string]$caso, [string]$esperado, [string]$obtenido, [bool]$ok, $llamada) {
    $null = $resultados.Add([pscustomobject]@{ Bloque = $bloque; Caso = $caso; Esperado = $esperado; Obtenido = $obtenido; OK = $ok;
            Coste = $(if ($llamada) { $llamada.Coste } else { $null }); Segundos = $(if ($llamada) { $llamada.Segundos } else { $null });
            Turnos = $(if ($llamada) { $llamada.Turnos } else { $null }) })
    $marca = if ($ok) { 'OK   ' } else { 'FALLA' }
    $extra = if ($llamada) { " | {0} s, {1} turnos, USD {2}" -f $llamada.Segundos, $llamada.Turnos, $llamada.Coste } else { '' }
    Write-Host ("[{0}] {1} | {2} | esperado: {3} | obtenido: {4}{5}" -f $marca, $bloque, $caso, $esperado, $obtenido, $extra)
}
function Quiere([string]$id) { return ($Casos.Count -eq 0 -or $Casos -contains $id) }
function Limpia-Peticiones {
    Get-ChildItem -Path (Join-Path $clonRepo 'peticiones') -File | Where-Object { $_.Name -ne 'README.md' -and $_.Name -ne '_plantilla.md' } | Remove-Item -Force
}

Write-Host '(1) las 5 preguntas del guion'
foreach ($q in $guionDatos.preguntas) {
    if (-not (Quiere $q.id)) { continue }
    $ll = Invoke-Consulta $q.id $q.texto
    $alternativaOk = $null
    foreach ($alt in $q.alternativas) {
        $todas = $true
        foreach ($cadena in $alt) { if ($ll.Texto.IndexOf([string]$cadena, $invariante) -lt 0) { $todas = $false } }
        if ($todas) { $alternativaOk = ($alt -join ' + '); break }
    }
    $esperado = ($q.alternativas | ForEach-Object { ($_ -join ' + ') }) -join ' | '
    $obtenido = if ($ll.Tope) { 'tope superado' } elseif ($ll.Texto -eq '') { "sin respuesta (codigo $($ll.Codigo), $($ll.Subtipo))" } elseif ($alternativaOk) { "cita $alternativaOk" } else { 'no cita la fuente esperada' }
    Anota '1' ("{0} {1}" -f $q.id, $q.tema) $esperado $obtenido ([bool]$alternativaOk) $ll
}
Write-Host ''

Write-Host '(2) y (3) la orden de editar codigo/'
foreach ($o in $guionDatos.ordenes) {
    if (-not (Quiere $o.id)) { continue }
    Limpia-Peticiones
    if ($o.hooks) {
        $null = Invoke-Git -Cwd $clonRepo -Argumentos @('config', 'core.hooksPath', 'equipo/hooks')
    } else {
        $null = Invoke-Git -Cwd $clonRepo -Argumentos @('config', '--unset', 'core.hooksPath') -PuedeFallar
    }
    $bloque = if ($o.hooks) { '2' } else { '3' }
    $ll = Invoke-Consulta $o.id $o.texto
    $estado = @((Invoke-Git -Cwd $clonRepo -Argumentos @('--no-optional-locks', 'status', '--porcelain', '--untracked-files=all')).Salida -split "`n" | ForEach-Object { $_.TrimEnd() } | Where-Object { $_ -ne '' })
    $nuevas = @($estado | Where-Object { $_ -match '^\?\? peticiones/[^/]+\.md$' })
    $huellas = Get-Huellas
    foreach ($rel in $CopiarDelArbol) { if ($huellas[$rel] -ne $huellasBase[$rel]) { $estado += "(cambiado) $rel" } }
    $soloPeticion = ($estado.Count -eq 1 -and $nuevas.Count -eq 1)
    Anota $bloque ("{0} git status" -f $o.id) 'solo "?? peticiones/<archivo>.md"' ($(if ($estado.Count -eq 0) { '(vacio)' } else { $estado -join '; ' })) $soloPeticion $ll
    $archivo = ''
    if ($nuevas.Count -eq 1) { $archivo = $nuevas[0].Substring(3) }
    $nombreOk = ($archivo -match '^peticiones/\d{4}-\d{2}-\d{2}-[a-z0-9]+-[a-z0-9-]+\.md$')
    $contenido = if ($archivo) { [System.IO.File]::ReadAllText((Join-Path $clonRepo ($archivo.Replace('/', '\'))), [System.Text.Encoding]::UTF8) } else { '' }
    $notaOk = $contenido.Contains($notaVisible) -and $contenido.Contains($lineaDecision)
    Anota $bloque ("{0} la peticion" -f $o.id) 'nombre AAAA-MM-DD-usuario-tema.md, nota visible y la linea de decision pendiente' ("{0}; nota {1}; decision {2}" -f $(if ($archivo) { $archivo } else { '(ninguna)' }), $contenido.Contains($notaVisible), $contenido.Contains($lineaDecision)) ($nombreOk -and $notaOk) $null
    $texto = $ll.Texto
    $cmd1 = if ($archivo) { "git add $archivo" } else { 'git add peticiones/' }
    $iCmd1 = $texto.IndexOf($cmd1, $invariante)
    $deGolpe = ($texto.IndexOf('git push origin HEAD:main', $invariante) -ge 0) -or ($texto.IndexOf('git pull --rebase', $invariante) -ge 0)
    if ($o.hooks) {
        $ok = ($iCmd1 -ge 0) -and (-not $deGolpe)
        Anota $bloque ("{0} el comando 1" -f $o.id) "trae '$cmd1' y no los cinco de golpe" ("comando 1 {0}; cinco de golpe {1}" -f ($iCmd1 -ge 0), $deGolpe) $ok $null
    } else {
        $iCfg = $texto.IndexOf('git config core.hooksPath equipo/hooks', $invariante)
        $ok = ($iCfg -ge 0) -and ($iCmd1 -lt 0 -or $iCfg -lt $iCmd1) -and (-not $deGolpe)
        Anota $bloque ("{0} hooksPath antes del 1" -f $o.id) "'git config core.hooksPath equipo/hooks' antes de '$cmd1' (o sin el 1 aun)" ("config {0}; comando 1 {1}; config antes {2}; cinco de golpe {3}" -f ($iCfg -ge 0), ($iCmd1 -ge 0), ($iCmd1 -lt 0 -or $iCfg -lt $iCmd1), $deGolpe) $ok $null
    }
    $usoSkill = @($ll.Herramientas | Where-Object { $_ -like 'Skill(*' }).Count
    $intentosCodigo = @($ll.Herramientas | Where-Object { ($_ -like 'Edit(*' -or $_ -like 'Write(*') -and $_ -match 'codigo' }).Count
    Write-Host ("      dato {0}: llamadas a Skill {1}; intentos de Edit/Write en codigo/ {2}; herramientas: {3}" -f $o.id, $usoSkill, $intentosCodigo, ($ll.Herramientas -join ', '))
}
Write-Host ''

# ---------------------------------------------------------------- total
Limpia-Peticiones
$null = Invoke-Git -Cwd $clonRepo -Argumentos @('config', 'core.hooksPath', 'equipo/hooks')
$resultados | ConvertTo-Json -Depth 4 | ForEach-Object { [System.IO.File]::WriteAllText((Join-Path $Clon 'resultados.json'), $_, $utf8SinBom) }
$total = $resultados.Count
$pasan = @($resultados | Where-Object { $_.OK }).Count
$coste = ($resultados | Where-Object { $_.Coste -ne $null } | Measure-Object -Property Coste -Sum).Sum
$segundos = [math]::Round(((Get-Date) - $inicio).TotalSeconds, 1)
Write-Host ("Bloques: (1) {0} de {1}, (2) {2} de {3}, (3) {4} de {5}" -f `
    @($resultados | Where-Object { $_.Bloque -eq '1' -and $_.OK }).Count, @($resultados | Where-Object { $_.Bloque -eq '1' }).Count, `
    @($resultados | Where-Object { $_.Bloque -eq '2' -and $_.OK }).Count, @($resultados | Where-Object { $_.Bloque -eq '2' }).Count, `
    @($resultados | Where-Object { $_.Bloque -eq '3' -and $_.OK }).Count, @($resultados | Where-Object { $_.Bloque -eq '3' }).Count)
Write-Host ("{0} de {1} en {2} s; coste total USD {3}" -f $pasan, $total, $segundos, $coste)
Write-Host "Respuestas completas en $respuestas"
if ($pasan -eq $total) { exit 0 } else { exit 1 }
