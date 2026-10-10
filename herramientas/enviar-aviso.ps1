<#
.SYNOPSIS
  Envía un aviso manual del observatorio a los canales públicos de ntfy (docs/avisos.md).

.DESCRIPTION
  Pregunta el país («Toda Europa» o uno concreto), el título corto, el texto en español y en
  inglés y si es una incursión en un país de la OTAN o en Moldavia (prioridad 4) o no (3).
  Enseña una vista previa y pide confirmación. Envía a drones-europe y, si hay país, también a su
  canal, con el mismo formato que los avisos automáticos: título «PAÍS · Qué pasa», Markdown, el
  logo del observatorio y el enlace a droneobservatory.eu.

  Publica como el usuario «lucas». La contraseña se lee de %USERPROFILE%\.eodi\ntfy_lucas.txt y no
  se muestra nunca. Este fichero no lleva ninguna credencial.

  Los canales salen de avisos.json, junto al script, o de configuracion\avisos.json del
  repositorio (si el script está en herramientas\).

.PARAMETER Prueba
  Envía solo a ese tema de pruebas (nunca a uno público). El tema necesita permiso temporal de
  escritura para «lucas» en el servidor; se quita después.

.PARAMETER Configuracion
  Ruta de avisos.json, si no está en ninguno de los dos sitios de siempre.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File C:\dev\avisos\enviar-aviso.ps1
#>
param(
  [string]$Prueba = "",
  [string]$Configuracion = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Esperar-Cierre {
  Write-Host ""
  Read-Host "Pulsa Intro para cerrar" | Out-Null
}

function Sin-Tildes([string]$texto) {
  $descompuesto = $texto.Normalize([Text.NormalizationForm]::FormD)
  $letras = $descompuesto.ToCharArray() | Where-Object {
    [Globalization.CharUnicodeInfo]::GetUnicodeCategory($_) -ne [Globalization.UnicodeCategory]::NonSpacingMark
  }
  return (-join $letras).ToLowerInvariant().Trim()
}

function Preguntar([string]$pregunta, [int]$maximo) {
  while ($true) {
    $respuesta = (Read-Host $pregunta).Trim()
    if ($respuesta -eq "") {
      Write-Host "  No puede quedar vacío." -ForegroundColor Yellow
      continue
    }
    if ($respuesta.Length -gt $maximo) {
      Write-Host "  Demasiado largo: $($respuesta.Length) caracteres, como mucho $maximo." -ForegroundColor Yellow
      continue
    }
    return $respuesta
  }
}

try {
  # --- Configuración -----------------------------------------------------------------------
  $candidatas = @()
  if ($Configuracion -ne "") { $candidatas += $Configuracion }
  $candidatas += (Join-Path $PSScriptRoot "avisos.json")
  $candidatas += (Join-Path (Split-Path $PSScriptRoot -Parent) "configuracion\avisos.json")
  $ruta = $candidatas | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($null -eq $ruta) { throw "No encuentro avisos.json (probé: $($candidatas -join ', '))." }
  $texto = [IO.File]::ReadAllText($ruta, [Text.Encoding]::UTF8)
  $config = $texto | ConvertFrom-Json
  $servidor = $config.servidor.TrimEnd("/")
  $europa = $config.general.tema

  $paises = @()
  foreach ($propiedad in $config.paises.PSObject.Properties) {
    $paises += [pscustomobject]@{
      Codigo = $propiedad.Name
      Tema   = $propiedad.Value.tema
      Es     = $propiedad.Value.es
      En     = $propiedad.Value.en
    }
  }
  $paises = @($paises | Sort-Object { Sin-Tildes $_.Es })
  $publicos = @($europa) + @($paises | ForEach-Object { $_.Tema })

  if ($Prueba -ne "" -and ($publicos -contains $Prueba -or $Prueba -eq "general")) {
    throw "El modo de prueba no admite un canal público ($Prueba)."
  }

  $ficheroClave = Join-Path $env:USERPROFILE ".eodi\ntfy_lucas.txt"
  if (-not (Test-Path $ficheroClave)) { throw "Falta la contraseña de lucas en $ficheroClave." }

  Write-Host ""
  Write-Host "ENVIAR UN AVISO DEL OBSERVATORIO" -ForegroundColor Cyan
  if ($Prueba -ne "") { Write-Host "Modo de prueba: solo al tema $Prueba" -ForegroundColor Yellow }
  Write-Host ""

  # --- País ------------------------------------------------------------------------------------
  Write-Host "  0. Toda Europa"
  for ($i = 0; $i -lt $paises.Count; $i++) {
    Write-Host ("{0,3}. {1}" -f ($i + 1), $paises[$i].Es)
  }
  $pais = $null
  while ($true) {
    $respuesta = (Read-Host "País: número o nombre (Intro = Toda Europa)").Trim()
    if ($respuesta -eq "" -or $respuesta -eq "0") { break }
    $numero = 0
    if ([int]::TryParse($respuesta, [ref]$numero) -and $numero -ge 1 -and $numero -le $paises.Count) {
      $pais = $paises[$numero - 1]
      break
    }
    $buscado = Sin-Tildes $respuesta
    $hallados = @($paises | Where-Object { (Sin-Tildes $_.Es).StartsWith($buscado) -or (Sin-Tildes $_.En).StartsWith($buscado) })
    if ($hallados.Count -eq 1) {
      $pais = $hallados[0]
      break
    }
    if ($hallados.Count -gt 1) {
      Write-Host "  Hay varios: $(($hallados | ForEach-Object { $_.Es }) -join ', '). Escribe más." -ForegroundColor Yellow
    } else {
      Write-Host "  No encuentro ese país." -ForegroundColor Yellow
    }
  }

  # --- Textos ----------------------------------------------------------------------------------
  $titulo = Preguntar "Título corto (qué pasa, en español)" 80
  $textoEs = Preguntar "Texto en español" 1500
  $textoEn = Preguntar "Texto en inglés" 1500
  $otan = ""
  while ($otan -notin @("s", "n")) {
    $otan = (Read-Host "¿Es una incursión en un país de la OTAN o en Moldavia? (s/n)").Trim().ToLowerInvariant()
  }
  $prioridad = if ($otan -eq "s") { 4 } else { 3 }

  $prefijo = if ($null -eq $pais) { "EUROPA" } else { $pais.Es.ToUpperInvariant() }
  $tituloAviso = "$prefijo · $titulo"
  $mensaje = "$textoEs`n`n$textoEn`n`n[droneobservatory.eu]($($config.sitio))"
  $temas = if ($Prueba -ne "") { @($Prueba) } elseif ($null -eq $pais) { @($europa) } else { @($europa, $pais.Tema) }

  # --- Vista previa ----------------------------------------------------------------------------
  Write-Host ""
  Write-Host "VISTA PREVIA" -ForegroundColor Cyan
  Write-Host "Canales:   $($temas -join ', ')"
  Write-Host "Prioridad: $prioridad $(if ($prioridad -eq 4) { '(alta)' } else { '(normal)' })"
  Write-Host "Título:    $tituloAviso"
  Write-Host "Mensaje:"
  Write-Host $mensaje
  Write-Host "Al tocarlo: $($config.sitio)"
  Write-Host ""
  $confirmar = (Read-Host "¿Enviar? Escribe s para enviar").Trim().ToLowerInvariant()
  if ($confirmar -ne "s") {
    Write-Host "No se ha enviado nada."
    Esperar-Cierre
    exit 0
  }

  # --- Envío -----------------------------------------------------------------------------------
  # La contraseña se lee aquí y solo va en la cabecera de autorización; no se escribe en pantalla.
  $clave = ([IO.File]::ReadAllText($ficheroClave)).Trim()
  $credencial = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("lucas:$clave"))
  $clave = $null
  $cabeceras = @{ Authorization = "Basic $credencial" }
  $fallos = 0
  foreach ($tema in $temas) {
    $cuerpo = [ordered]@{
      topic    = $tema
      title    = $tituloAviso
      message  = $mensaje
      markdown = $true
      priority = $prioridad
      icon     = $config.icono
      click    = $config.sitio
    } | ConvertTo-Json -Compress
    try {
      $respuesta = Invoke-RestMethod -Method Post -Uri $servidor -Headers $cabeceras `
        -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($cuerpo)) -TimeoutSec 20
      Write-Host "Enviado a $tema (id $($respuesta.id))." -ForegroundColor Green
    } catch {
      $fallos++
      $estado = ""
      if ($_.Exception.Response) { $estado = " (HTTP $([int]$_.Exception.Response.StatusCode))" }
      Write-Host "No se pudo enviar a $tema$estado." -ForegroundColor Red
    }
  }
  $credencial = $null
  if ($fallos -gt 0) {
    Write-Host "Ha fallado $fallos envío(s). Vuelve a ejecutarlo solo si no ha salido a ningún canal, o envíalo a mano desde $servidor." -ForegroundColor Red
    Esperar-Cierre
    exit 1
  }
  Esperar-Cierre
  exit 0
} catch {
  Write-Host ""
  Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
  Esperar-Cierre
  exit 1
}
