@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

:: ── Detectar ADB ──────────────────────────────────────────────────────────
set ADB=adb
if exist "%~dp0installer\adb_files\platform-tools\adb.exe" (
    set "ADB=%~dp0installer\adb_files\platform-tools\adb.exe"
) else if exist "C:\Program Files (x86)\WOMic\adb.exe" (
    set "ADB=C:\Program Files (x86)\WOMic\adb.exe"
) else if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
)

:: ── Detectar Inno Setup ───────────────────────────────────────────────────
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if not defined ISCC where ISCC.exe >nul 2>&1 && set "ISCC=ISCC.exe"

:MENU
cls
title PhoneMic - Dev Menu
echo.
echo  ============================================
echo    PhoneMic - Menu de desarrollo
echo  ============================================
echo.
echo    1. Instalar APK en el telefono (USB)
echo    2. Compilar todo  (APK + EXE + Instalador)
echo    3. Compilar solo APK
echo    4. Compilar solo EXE
echo    5. Instalar dependencias Python
echo    6. Salir
echo.
echo  ============================================
echo.
choice /C 123456 /N /M "  Elige una opcion [1-6]: "
if errorlevel 6 goto :EOF
if errorlevel 5 goto INSTALAR_DEPS
if errorlevel 4 goto SOLO_EXE
if errorlevel 3 goto SOLO_APK
if errorlevel 2 goto TODO
if errorlevel 1 goto INSTALAR_APK

:: ─────────────────────────────────────────────────────────────────────────
:INSTALAR_APK
cls
echo.
echo  [Instalar APK en el telefono]
echo.
set APK=%~dp0android\app\build\outputs\apk\debug\app-debug.apk
if not exist "%APK%" (
    echo  ERROR: APK no encontrado en:
    echo  %APK%
    echo.
    echo  Compila el APK primero ^(opcion 2 o 3^).
    echo.
    pause & goto MENU
)
echo  Buscando dispositivo...
"%ADB%" devices
echo.
echo  Instalando APK...
"%ADB%" install -r "%APK%"
if errorlevel 1 (
    echo.
    echo  ERROR: No se pudo instalar. Verifica que el telefono
    echo  este conectado y tenga depuracion USB activa.
) else (
    echo.
    echo  APK instalado correctamente.
)
echo.
pause & goto MENU

:: ─────────────────────────────────────────────────────────────────────────
:TODO
cls
echo.
echo  [Compilar todo: APK + EXE + Instalador]
echo.

call :BUILD_APK
if errorlevel 1 goto FIN_ERROR

call :BUILD_EXE
if errorlevel 1 goto FIN_ERROR

call :BUILD_INSTALLER
if errorlevel 1 goto FIN_ERROR

echo.
echo  ============================================
echo    Build completado exitosamente!
echo.
echo    APK:        android\app\build\outputs\apk\debug\app-debug.apk
echo    EXE:        windows\dist\PhoneMic\PhoneMic.exe
echo    Instalador: installer\Output\PhoneMic_Setup.exe
echo  ============================================
echo.
pause & goto MENU

:: ─────────────────────────────────────────────────────────────────────────
:SOLO_APK
cls
echo.
echo  [Compilar solo APK]
echo.
call :BUILD_APK
if errorlevel 1 goto FIN_ERROR
echo.
echo  APK listo: android\app\build\outputs\apk\debug\app-debug.apk
echo.
pause & goto MENU

:: ─────────────────────────────────────────────────────────────────────────
:SOLO_EXE
cls
echo.
echo  [Compilar solo EXE]
echo.
call :BUILD_EXE
if errorlevel 1 goto FIN_ERROR
echo.
echo  EXE listo: windows\dist\PhoneMic\PhoneMic.exe
echo.
pause & goto MENU

:: ─────────────────────────────────────────────────────────────────────────
:FIN_ERROR
echo.
echo  El proceso termino con errores. Revisa los mensajes de arriba.
echo.
pause & goto MENU

:: ─────────────────────────────────────────────────────────────────────────
:INSTALAR_DEPS
cls
echo.
echo  [Instalar dependencias Python]
echo.
pip install -r "%~dp0windows\requirements.txt"
if errorlevel 1 (
    echo.
    echo  ERROR: Fallo al instalar algunas dependencias.
    echo  Verifica que Python y pip esten instalados.
) else (
    echo.
    echo  Todas las dependencias instaladas correctamente.
)
echo.
pause & goto MENU

:: ═════════════════════════════════════════════════════════════════════════
:: Subrutinas de build
:: ═════════════════════════════════════════════════════════════════════════

:BUILD_APK
echo  Compilando APK...
cd /d "%~dp0android"
call gradlew.bat assembleDebug
if errorlevel 1 (
    echo  ERROR: Fallo al compilar APK.
    cd /d "%~dp0"
    exit /b 1
)
cd /d "%~dp0"
exit /b 0

:BUILD_EXE
echo  Compilando EXE con PyInstaller...
cd /d "%~dp0windows"
pyinstaller -y --onedir --noconsole --name PhoneMic ^
    --icon "%~dp0windows\phonemic.ico" ^
    --add-data "%~dp0windows\phonemic.ico;." ^
    --add-data "%~dp0windows\phonemic.png;." ^
    --collect-all PySide6 ^
    --collect-all sounddevice ^
    --collect-all soundfile ^
    --hidden-import numpy ^
    "%~dp0windows\main.py"
if errorlevel 1 (
    echo  ERROR: PyInstaller fallo.
    cd /d "%~dp0"
    exit /b 1
)
echo  Copiando ADB al dist...
copy /Y "%~dp0windows\phonemic.ico"  "%~dp0windows\dist\PhoneMic\" >nul
copy /Y "%~dp0windows\phonemic.png"  "%~dp0windows\dist\PhoneMic\" >nul
copy /Y "%~dp0installer\adb_files\platform-tools\adb.exe"          "%~dp0windows\dist\PhoneMic\" >nul
copy /Y "%~dp0installer\adb_files\platform-tools\AdbWinApi.dll"    "%~dp0windows\dist\PhoneMic\" >nul 2>nul
copy /Y "%~dp0installer\adb_files\platform-tools\AdbWinUsbApi.dll" "%~dp0windows\dist\PhoneMic\" >nul 2>nul
cd /d "%~dp0"
exit /b 0

:BUILD_INSTALLER
echo  Compilando instalador con Inno Setup...
if not defined ISCC (
    echo  ERROR: Inno Setup 6 no encontrado.
    exit /b 1
)
"%ISCC%" "%~dp0installer\phonemic_setup.iss"
if errorlevel 1 (
    echo  ERROR: Fallo al compilar instalador.
    exit /b 1
)
exit /b 0
