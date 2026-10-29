<#
.SYNOPSIS
Lista las peticiones del buzon (peticiones/) que siguen con "Decision: pendiente" en una ref de git.

.DESCRIPTION
Lo corre la sesion de direccion al arrancar, despues de leer memory.md (meta 005, fase 4; ADR-034).
Solo lee: trae origin con "git fetch origin" (salvo -SinFetch) y lee cada peticion con
"git show <ref>:<ruta>", sin tocar el arbol de trabajo ni el indice.

Por cada peticion pendiente imprime una linea "archivo . quien . fecha . que", con la nota visible del
agente de consulta y el autor del commit que la anadio. Al final:
  Peticiones pendientes: N
  Commits nuevos en origin/main: M      (git rev-list --count HEAD..origin/main)

Codigos de salida: 0 si pudo leer la ref (aunque el fetch falle: lo dice con un AVISO y lista lo que
hay en la copia local); 1 si la ref no existe o git no responde.

Todo proceso externo lleva tope de tiempo (-TopeSegundos). El script es solo ASCII a proposito:
PowerShell 5.1 lee un .ps1 sin BOM con la pagina de codigos ANSI. La salida de git se lee como UTF-8.

.PARAMETER Ref
La ref que se lee, explicita (principio 7): origin/main al arrancar direccion; HEAD para comprobar el arbol.

.PARAMETER SinFetch
No ejecuta "git fetch origin" antes de leer.

.PARAMETER Repo
Raiz del repo. Por defecto, un nivel arriba de este script.

.PARAMETER TopeSegundos
Tope por proceso externo. Por defecto 60 (el fetch puede tardar).

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File equipo/peticiones_pendientes.ps1 -Ref origin/main

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File equipo/peticiones_pendientes.ps1 -Ref HEAD -SinFetch
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Ref,
    [switch]$SinFetch,
    [string]$Repo = '',
    [int]$TopeSegundos = 60
)

$ErrorActionPreference = 'Stop'

if ($Repo -eq '') {
    $Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
$Repo = (Resolve-Path $Repo).Path

$oAcento = [string][char]0x00F3
$punto = ' ' + [string][char]0x00B7 + ' '
$rePendiente = '^Decisi' + $oAcento + 'n:\s*pendiente'
$reQuien = '^- \*\*Qui' + [string][char]0x00E9 + 'n la pide:\*\*\s*(.+?)\.?\s*$'
$reCuando = '^- \*\*Cu' + [string][char]0x00E1 + 'ndo:\*\*\s*(.+?)\.?\s*$'
$reTitulo = '^# Petici' + $oAcento + 'n\s*\S\s*(.+?)\s*$'

function Invoke-Git {
    # git -C <Repo> -c core.quotepath=false <Argumentos>, con tope y la salida leida como UTF-8.
    # Los argumentos van tal cual en ProcessStartInfo.Arguments: "--" llega a git sin que PowerShell lo toque.
    param([string[]]$Argumentos, [int]$Tope = $TopeSegundos)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'git'
    $todos = @('-C', $Repo, '-c', 'core.quotepath=false') + $Argumentos
    $partes = foreach ($a in $todos) { if ($a -match '[\s"]') { '"' + $a.Replace('"', '\"') + '"' } else { $a } }
    $psi.Arguments = ($partes -join ' ')
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $psi.EnvironmentVariables['GIT_TERMINAL_PROMPT'] = '0'
    $p = [System.Diagnostics.Process]::Start($psi)
    $salidaT = $p.StandardOutput.ReadToEndAsync()
    $errorT = $p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit($Tope * 1000)) {
        try { $p.Kill() } catch { }
        return [pscustomobject]@{ Codigo = -1; Salida = ''; Error = "tope de $Tope s superado" }
    }
    $p.WaitForExit()
    return [pscustomobject]@{ Codigo = $p.ExitCode; Salida = $salidaT.Result; Error = $errorT.Result.Trim() }
}

function Get-Lineas([string]$texto) {
    return @($texto -split "`r?`n" | Where-Object { $_ -ne '' })
}

$salidaOriginal = $null
try { $salidaOriginal = [Console]::OutputEncoding; [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }

try {
    Write-Output "Peticiones del buzon en $Ref (repo: $Repo)"

    if (-not $SinFetch) {
        $f = Invoke-Git -Argumentos @('fetch', 'origin')
        if ($f.Codigo -ne 0) {
            $motivo = if ($f.Error) { @(Get-Lineas $f.Error)[0] } else { "codigo $($f.Codigo)" }
            Write-Output "AVISO: git fetch origin no funciono ($motivo). La lista es la de la ultima copia local de $Ref."
        }
    }

    # ^{tree}: vale cualquier commit o arbol (las pruebas leen un arbol hecho con write-tree, sin commit).
    $v = Invoke-Git -Argumentos @('rev-parse', '--verify', '--quiet', "$Ref^{tree}")
    if ($v.Codigo -ne 0) {
        Write-Output "ERROR: la ref '$Ref' no existe en $Repo."
        exit 1
    }
    $oid = 'arbol ' + @(Get-Lineas $v.Salida)[0].Substring(0, 7)
    $vc = Invoke-Git -Argumentos @('rev-parse', '--verify', '--quiet', "$Ref^{commit}")
    if ($vc.Codigo -eq 0) { $oid = @(Get-Lineas $vc.Salida)[0].Substring(0, 7) }

    $ls = Invoke-Git -Argumentos @('ls-tree', '-r', '--name-only', $Ref, 'peticiones')
    if ($ls.Codigo -ne 0) {
        Write-Output "ERROR: git ls-tree fallo sobre $Ref ($($ls.Error))."
        exit 1
    }
    $rutas = @(Get-Lineas $ls.Salida | Where-Object {
        $_ -like 'peticiones/*.md' -and $_ -ne 'peticiones/README.md' -and $_ -ne 'peticiones/_plantilla.md'
    })

    $pendientes = 0
    foreach ($ruta in $rutas) {
        $s = Invoke-Git -Argumentos @('show', "${Ref}:$ruta")
        if ($s.Codigo -ne 0) {
            Write-Output "AVISO: no se pudo leer $ruta en $Ref ($($s.Error))."
            continue
        }
        $lineas = @($s.Salida -split "`r?`n")
        $esPendiente = @($lineas | Where-Object { $_ -match $rePendiente }).Count -gt 0
        if (-not $esPendiente) { continue }
        $pendientes++

        $quien = '(sin "Quien la pide")'; $cuando = '(sin fecha)'; $que = '(sin titulo)'; $nota = ''
        foreach ($l in $lineas) {
            if ($nota -eq '' -and $l -match '^>\s*(.+?)\s*$') { $nota = $Matches[1] }
            if ($l -match $reQuien) { $quien = $Matches[1] }
            if ($l -match $reCuando) { $cuando = $Matches[1] }
            if ($l -match $reTitulo) { $que = $Matches[1] }
        }
        $a = Invoke-Git -Argumentos @('log', '--diff-filter=A', '--format=%an <%ae>, %ad', '--date=short', $Ref, '--', $ruta)
        $enviada = (Get-Lineas $a.Salida | Select-Object -Last 1)
        if (-not $enviada) { $enviada = '(no se encontro el commit que la anadio)' }

        $nombre = $ruta.Substring('peticiones/'.Length)
        Write-Output ('- ' + $nombre + $punto + $quien + $punto + $cuando + $punto + $que)
        if ($nota -ne '') { Write-Output ('    nota: ' + $nota) }
        Write-Output ('    enviada en el commit de: ' + $enviada)
    }
    if ($rutas.Count -eq 0) { Write-Output '(no hay peticiones: solo README.md y _plantilla.md)' }

    Write-Output ''
    Write-Output "Peticiones en $Ref ($oid): $($rutas.Count)"
    Write-Output "Peticiones pendientes: $pendientes"

    $o = Invoke-Git -Argumentos @('rev-parse', '--verify', '--quiet', 'origin/main^{commit}')
    if ($o.Codigo -ne 0) {
        Write-Output 'Commits nuevos en origin/main: (no hay origin/main en esta copia)'
    } else {
        $c = Invoke-Git -Argumentos @('rev-list', '--count', 'HEAD..origin/main')
        $m = if ($c.Codigo -eq 0) { @(Get-Lineas $c.Salida)[0].Trim() } else { '(no se pudo contar)' }
        Write-Output "Commits nuevos en origin/main: $m"
    }
    exit 0
}
finally {
    if ($null -ne $salidaOriginal) { try { [Console]::OutputEncoding = $salidaOriginal } catch { } }
}
