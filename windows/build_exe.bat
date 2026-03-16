@echo off
setlocal enabledelayedexpansion
title PhoneMic - Build EXE

echo ============================================
echo  PhoneMic - Generando EXE con PyInstaller
echo ============================================
echo.

:: ── 1. Instalar dependencias ─────────────────────────────────────────────────
echo [1/4] Instalando dependencias Python...
pip install pyinstaller sounddevice numpy pystray pillow --quiet
if errorlevel 1 (
    echo ERROR: Fallo al instalar dependencias.
    pause & exit /b 1
)

:: ── 2. Limpiar builds anteriores ─────────────────────────────────────────────
echo [2/4] Limpiando builds anteriores...
if exist dist\PhoneMic  rmdir /s /q dist\PhoneMic
if exist build          rmdir /s /q build
if exist PhoneMic.spec  del /q PhoneMic.spec

:: ── 3. PyInstaller ────────────────────────────────────────────────────────────
echo [3/4] Empaquetando con PyInstaller...
pyinstaller --onedir --noconsole --name PhoneMic ^
    --icon phonemic.ico ^
    --collect-all sounddevice ^
    --collect-all soundfile ^
    --hidden-import sounddevice ^
    --hidden-import pystray ^
    --hidden-import PIL ^
    phonemic_client.py
if errorlevel 1 (
    echo ERROR: PyInstaller fallo.
    pause & exit /b 1
)

:: ── 4. Copiar adb.exe y DLLs ─────────────────────────────────────────────────
echo [4/4] Copiando iconos y archivos ADB...
if exist phonemic.ico  copy /Y phonemic.ico  dist\PhoneMic\ >nul
if exist phonemic.png  copy /Y phonemic.png  dist\PhoneMic\ >nul

set ADB_FOUND=0

:: Buscar en la carpeta adb_files local (directo)
if exist "..\installer\adb_files\adb.exe" (
    copy /Y "..\installer\adb_files\adb.exe"          dist\PhoneMic\ >nul
    copy /Y "..\installer\adb_files\AdbWinApi.dll"    dist\PhoneMic\ >nul 2>nul
    copy /Y "..\installer\adb_files\AdbWinUsbApi.dll" dist\PhoneMic\ >nul 2>nul
    echo    Copiado desde installer\adb_files\
    set ADB_FOUND=1
)

:: Buscar en la subcarpeta platform-tools (cuando se extrae el ZIP completo)
if !ADB_FOUND!==0 if exist "..\installer\adb_files\platform-tools\adb.exe" (
    copy /Y "..\installer\adb_files\platform-tools\adb.exe"          dist\PhoneMic\ >nul
    copy /Y "..\installer\adb_files\platform-tools\AdbWinApi.dll"    dist\PhoneMic\ >nul 2>nul
    copy /Y "..\installer\adb_files\platform-tools\AdbWinUsbApi.dll" dist\PhoneMic\ >nul 2>nul
    echo    Copiado desde installer\adb_files\platform-tools\
    set ADB_FOUND=1
)

:: Buscar en Android SDK (ruta tipica)
if !ADB_FOUND!==0 if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    set PT=%LOCALAPPDATA%\Android\Sdk\platform-tools
    copy /Y "!PT!\adb.exe"          dist\PhoneMic\ >nul
    copy /Y "!PT!\AdbWinApi.dll"    dist\PhoneMic\ >nul 2>nul
    copy /Y "!PT!\AdbWinUsbApi.dll" dist\PhoneMic\ >nul 2>nul
    echo    Copiado desde Android SDK: !PT!
    set ADB_FOUND=1
)

if !ADB_FOUND!==0 (
    echo.
    echo  ADVERTENCIA: adb.exe no encontrado automaticamente.
    echo  Coloca adb.exe, AdbWinApi.dll y AdbWinUsbApi.dll en:
    echo    installer\adb_files\
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
