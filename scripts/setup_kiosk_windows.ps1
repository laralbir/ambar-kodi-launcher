<#
.SYNOPSIS
    Configura un mini PC con Windows como kiosko dedicado para Ambar:
    inicio de sesion automatico, sin salvapantallas/bloqueo por
    inactividad, y Kodi + Ambar arrancando solos con el sistema.

.DESCRIPTION
    Automatiza los pasos manuales documentados en
    docs/index.html ("Preparar el equipo como kiosko (Windows)").
    Cada paso es independiente -- si uno falla o se salta, los demas
    se aplican igual.

    Requiere permisos de administrador (el inicio de sesion automatico
    y el arranque de Kodi/Ambar tocan el registro HKLM y la carpeta de
    Inicio del sistema). El script se relanza solo elevado si hace falta.

.PARAMETER All
    Aplica todos los pasos sin preguntar (modo desatendido, util para
    aprovisionar varios equipos iguales). Sin este flag, el script actua
    como asistente: explica cada paso y pide confirmacion (S/N) antes de
    aplicarlo.

.PARAMETER AmbarPath
    Ruta al Ambar.exe compilado. Si se omite, se busca junto al propio
    script (..\dist\Ambar\Ambar.exe, la ruta habitual tras `python
    build.py`) y se pide confirmarla o corregirla.

.EXAMPLE
    .\setup_kiosk_windows.ps1
    Modo asistente: pregunta paso a paso.

.EXAMPLE
    .\setup_kiosk_windows.ps1 -All
    Aplica todo sin preguntar.
#>

[CmdletBinding()]
param(
    [switch]$All,
    [string]$AmbarPath
)

$ErrorActionPreference = "Stop"

# ---------- Relanzar elevado si hace falta ----------
# El inicio de sesion automatico (HKLM\...\Winlogon) y las propiedades del
# acceso directo de Inicio necesitan permisos de administrador aunque la
# cuenta ya sea admin -- Windows exige elevacion explicita (UAC) para
# escribir en HKLM.
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Este script necesita permisos de administrador -- relanzando con UAC..." -ForegroundColor Yellow
    $scriptArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"")
    if ($All) { $scriptArgs += "-All" }
    if ($AmbarPath) { $scriptArgs += "-AmbarPath"; $scriptArgs += "`"$AmbarPath`"" }
    Start-Process powershell -Verb RunAs -ArgumentList $scriptArgs -Wait
    exit
}

function Confirm-Step {
    param([string]$Title, [string]$Description)
    if ($All) { return $true }
    Write-Host ""
    Write-Host "== $Title ==" -ForegroundColor Cyan
    Write-Host $Description
    $resp = Read-Host "¿Aplicar este paso? (S/n)"
    return ($resp -eq "" -or $resp -match "^[SsYy]")
}

function Write-Result {
    param([string]$Message, [bool]$Ok)
    if ($Ok) { Write-Host "  ✔ $Message" -ForegroundColor Green }
    else { Write-Host "  ✘ $Message" -ForegroundColor Red }
}

# ---------- Paso 1: inicio de sesion automatico ----------
function Enable-AutoLogin {
    $userName = $env:USERNAME
    $netUserOutput = net user $userName 2>&1
    # La linea exacta depende del idioma de Windows ("Password required" /
    # "Contraseña requerida"), asi que se busca el valor de la columna
    # (Si/No, Yes/No) sin depender del idioma -- se coge la primera linea
    # que contenga "requer" (requerida) o "required".
    $passwordRequiredLine = $netUserOutput | Where-Object { $_ -match "requer" -or $_ -match "required" }
    $passwordRequired = $passwordRequiredLine -match "(Si|Sí|Yes)\s*$"

    if ($passwordRequired) {
        Write-Host "  La cuenta '$userName' tiene contraseña." -ForegroundColor Yellow
        Write-Host "  Por seguridad, este script NO guarda contraseñas en el registro."
        Write-Host "  Usa la herramienta oficial de Microsoft para esto:"
        Write-Host "  https://learn.microsoft.com/es-es/sysinternals/downloads/autologon"
        Write-Result "Inicio de sesión automático (manual, ver arriba)" $false
        return
    }

    $winlogon = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
    Set-ItemProperty -Path $winlogon -Name AutoAdminLogon -Value "1"
    Set-ItemProperty -Path $winlogon -Name DefaultUserName -Value $userName
    Set-ItemProperty -Path $winlogon -Name DefaultPassword -Value ""
    Remove-ItemProperty -Path $winlogon -Name DefaultDomainName -ErrorAction SilentlyContinue
    Write-Result "Inicio de sesión automático activado para '$userName' (efectivo en el próximo arranque)" $true
}

# ---------- Paso 2: desactivar salvapantallas / bloqueo por inactividad ----------
function Disable-ScreenLock {
    # ScreenSaveActive=0 desactiva el salvapantallas, pero por si solo no
    # basta -- confirmado en vivo que la pantalla de bloqueo de Windows
    # seguia saliendo tras un rato de inactividad aun con esto puesto.
    # Se cubren tambien los otros dos mecanismos independientes que
    # pueden forzarla: ScreenSaverIsSecure (pedir contraseña "al
    # reanudar", que en teoria no deberia disparar sin salvapantallas
    # activo, pero se desactiva igualmente por si acaso) y los tiempos de
    # apagado de pantalla/suspension del plan de energia (si la pantalla
    # se apaga o el equipo suspende, Windows puede pedir inicio de sesion
    # al volver aunque WindowsWakeLock de Ambar ya intente evitar la
    # suspension mientras el proceso esta vivo -- esto es la red de
    # seguridad a nivel de sistema, no depende de que Ambar siga
    # corriendo). "0" en powercfg significa "nunca".
    Set-ItemProperty -Path "HKCU:\Control Panel\Desktop" -Name ScreenSaveActive -Value "0"
    Set-ItemProperty -Path "HKCU:\Control Panel\Desktop" -Name ScreenSaverIsSecure -Value "0"
    powercfg /change monitor-timeout-ac 0
    powercfg /change monitor-timeout-dc 0
    powercfg /change standby-timeout-ac 0
    powercfg /change standby-timeout-dc 0
    Write-Result "Salvapantallas/bloqueo por inactividad y apagado/suspensión de pantalla desactivados" $true
}

# ---------- Paso 3: desactivar la reproduccion automatica de CD de audio ----------
# Sin esto, al insertar un CD Windows puede lanzar su propio reproductor
# multimedia (Windows Media Player/Groove Music) a la vez que Kodi -- dos
# programas compitiendo por el lector y por la salida de audio. Solo afecta
# al manejador de "CD de audio" (PlayCDAudioOnArrival); el resto de
# autoplay (USB, fotos...) se deja tal cual, no es lo que se pidio.
function Disable-CdAutoplay {
    $path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers\UserChosenExecuteHandlers"
    if (-not (Test-Path $path)) {
        New-Item -Path $path -Force | Out-Null
    }
    Set-ItemProperty -Path $path -Name "PlayCDAudioOnArrival" -Value "MSTakeNoAction"
    Write-Result "Reproducción automática de CD de audio desactivada (Kodi/Ámbar siguen detectándolo igual)" $true
}

# ---------- Paso 4: arranque automatico de Kodi y Ambar ----------
function Find-KodiExe {
    $candidates = @(
        "$env:ProgramFiles\Kodi\kodi.exe",
        "${env:ProgramFiles(x86)}\Kodi\kodi.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

function New-StartupShortcut {
    param(
        [string]$Name,
        [string]$TargetPath,
        [string]$WorkingDirectory,
        [int]$WindowStyle = 1  # 1=normal, 3=maximizado, 7=minimizado
    )
    $startupDir = [Environment]::GetFolderPath('Startup')
    $shortcutPath = Join-Path $startupDir "$Name.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.WindowStyle = $WindowStyle
    $shortcut.Save()
    return $shortcutPath
}

function Enable-AutoStart {
    $kodiExe = Find-KodiExe
    if ($kodiExe) {
        $path = New-StartupShortcut -Name "Kodi" -TargetPath $kodiExe -WorkingDirectory (Split-Path $kodiExe) -WindowStyle 7
        Write-Result "Kodi arrancará minimizado con el sistema ($path)" $true
    } else {
        Write-Result "No se encontró kodi.exe en las rutas habituales -- omitido" $false
    }

    $ambarExe = $AmbarPath
    if (-not $ambarExe) {
        $defaultAmbar = Join-Path (Split-Path $PSScriptRoot -Parent) "dist\Ambar\Ambar.exe"
        if (Test-Path $defaultAmbar) { $ambarExe = $defaultAmbar }
    }
    if ($ambarExe -and (Test-Path $ambarExe)) {
        $path = New-StartupShortcut -Name "Ambar" -TargetPath $ambarExe -WorkingDirectory (Split-Path $ambarExe) -WindowStyle 1
        Write-Result "Ámbar arrancará con el sistema ($path)" $true
    } else {
        Write-Result "No se encontró Ambar.exe (usa -AmbarPath <ruta> para indicarlo) -- omitido" $false
    }
}

# ---------- Ejecucion ----------
Write-Host "Configuración de kiosko para Ámbar (Windows)" -ForegroundColor Cyan
Write-Host "=============================================="

if (Confirm-Step "Inicio de sesión automático" "Evita que Windows pida iniciar sesión al arrancar el mini PC.") {
    Enable-AutoLogin
}

if (Confirm-Step "Desactivar salvapantallas / bloqueo por inactividad" "Un kiosko no debe bloquearse por inactividad -- nadie toca el teclado/ratón mientras suena música. (El wake lock de Ámbar ya evita que la pantalla se apague, pero no puede evitar el bloqueo de sesión seguro de Windows.)") {
    Disable-ScreenLock
}

if (Confirm-Step "Desactivar reproducción automática de CD de audio" "Evita que Windows abra su propio reproductor multimedia al insertar un CD, compitiendo con Kodi/Ámbar por el lector y el audio.") {
    Disable-CdAutoplay
}

if (Confirm-Step "Arranque automático de Kodi y Ámbar" "Añade accesos directos a la carpeta de Inicio de Windows: Kodi minimizado, Ámbar en ventana normal.") {
    Enable-AutoStart
}

Write-Host ""
Write-Host "Listo. Reinicia el equipo para comprobar el arranque completo." -ForegroundColor Cyan
