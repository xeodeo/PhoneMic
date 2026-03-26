@echo off
setlocal enabledelayedexpansion
title PhoneMic - Build EXE
cd /d "%~dp0"

echo ============================================
echo  PhoneMic - Generando EXE con PyInstaller
echo ============================================
echo.

:: ── 1. Instalar dependencias ─────────────────────────────────────────────────
echo [1/4] Instalando dependencias Python...
pip install pyinstaller pyside6 sounddevice numpy --quiet
if errorlevel 1 (
    echo ERROR: Fallo al instalar dependencias.
    pause & exit /b 1
)

:: ── 2. Limpiar builds anteriores ─────────────────────────────────────────────
echo [2/4] Limpiando builds anteriores...
if exist "%~dp0dist\PhoneMic"  rmdir /s /q "%~dp0dist\PhoneMic"
if exist "%~dp0build"          rmdir /s /q "%~dp0build"
if exist "%~dp0PhoneMic.spec"  del /q "%~dp0PhoneMic.spec"

:: ── 3. PyInstaller ────────────────────────────────────────────────────────────
echo [3/4] Empaquetando con PyInstaller...
pyinstaller --onedir --noconsole --name PhoneMic ^
    --icon "%~dp0phonemic.ico" ^
    --collect-all sounddevice ^
    --collect-all soundfile ^
    --hidden-import sounddevice ^
    --hidden-import numpy ^
    "%~dp0main.py"
if errorlevel 1 (
    echo ERROR: PyInstaller fallo.
    pause & exit /b 1
)

:: ── 4. Copiar icono y archivos ADB ────────────────────────────────────────────
echo [4/4] Copiando icono y archivos ADB...
if exist "%~dp0phonemic.ico"  copy /Y "%~dp0phonemic.ico"  "%~dp0dist\PhoneMic\" >nul
if exist "%~dp0phonemic.png"  copy /Y "%~dp0phonemic.png"  "%~dp0dist\PhoneMic\" >nul

set ADB_FOUND=0

:: Buscar en installer\adb_files\platform-tools (estructura normal)
if exist "%~dp0..\installer\adb_files\platform-tools\adb.exe" (
    copy /Y "%~dp0..\installer\adb_files\platform-tools\adb.exe"          "%~dp0dist\PhoneMic\" >nul
    copy /Y "%~dp0..\installer\adb_files\platform-tools\AdbWinApi.dll"    "%~dp0dist\PhoneMic\" >nul 2>nul
    copy /Y "%~dp0..\installer\adb_files\platform-tools\AdbWinUsbApi.dll" "%~dp0dist\PhoneMic\" >nul 2>nul
    echo    Copiado desde installer\adb_files\platform-tools\
    set ADB_FOUND=1
)

:: Buscar directamente en installer\adb_files
if !ADB_FOUND!==0 if exist "%~dp0..\installer\adb_files\adb.exe" (
    copy /Y "%~dp0..\installer\adb_files\adb.exe"          "%~dp0dist\PhoneMic\" >nul
    copy /Y "%~dp0..\installer\adb_files\AdbWinApi.dll"    "%~dp0dist\PhoneMic\" >nul 2>nul
    copy /Y "%~dp0..\installer\adb_files\AdbWinUsbApi.dll" "%~dp0dist\PhoneMic\" >nul 2>nul
    echo    Copiado desde installer\adb_files\
    set ADB_FOUND=1
)

:: Buscar en Android SDK (ruta tipica)
if !ADB_FOUND!==0 if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    set PT=%LOCALAPPDATA%\Android\Sdk\platform-tools
    copy /Y "!PT!\adb.exe"          "%~dp0dist\PhoneMic\" >nul
    copy /Y "!PT!\AdbWinApi.dll"    "%~dp0dist\PhoneMic\" >nul 2>nul
    copy /Y "!PT!\AdbWinUsbApi.dll" "%~dp0dist\PhoneMic\" >nul 2>nul
    echo    Copiado desde Android SDK: !PT!
    set ADB_FOUND=1
)

if !ADB_FOUND!==0 (
    echo.
    echo  ADVERTENCIA: adb.exe no encontrado automaticamente.
    echo  Coloca adb.exe, AdbWinApi.dll y AdbWinUsbApi.dll en:
    echo    installer\adb_files\platform-tools\
    echo  Descargalos de: https://dl.google.com/android/repository/platform-tools-latest-windows.zip
    echo.
)

echo.
echo ============================================
echo  Listo: dist\PhoneMic\PhoneMic.exe
echo  Ahora ejecuta el script de Inno Setup para
echo  generar el instalador final.
echo ============================================
pause
