@echo off
setlocal enabledelayedexpansion
title PhoneMic - Build completo (APK + EXE + Instalador)
cd /d "%~dp0"

echo ================================================
echo   PhoneMic - Build completo
echo ================================================
echo.

:: ── 1. APK ────────────────────────────────────────
echo [1/4] Compilando APK Android...
cd /d "%~dp0android"
call gradlew.bat assembleDebug
if errorlevel 1 (
    echo ERROR: Fallo al compilar APK.
    pause & exit /b 1
)
echo    APK: android\app\build\outputs\apk\debug\app-debug.apk
echo.

:: ── 2. EXE ────────────────────────────────────────
echo [2/4] Compilando EXE Windows...
cd /d "%~dp0windows"
py -3.12 -m PyInstaller -y --onedir --noconsole --name PhoneMic ^
    --icon "%~dp0windows\phonemic.ico" ^
    --add-data "%~dp0windows\phonemic.ico;." ^
    --add-data "%~dp0windows\phonemic.png;." ^
    --collect-all sounddevice ^
    --collect-all soundfile ^
    --collect-binaries PySide6 ^
    --collect-binaries shiboken6 ^
    --hidden-import PySide6.QtWidgets ^
    --hidden-import PySide6.QtCore ^
    --hidden-import PySide6.QtGui ^
    --hidden-import numpy ^
    "%~dp0windows\main.py"
if errorlevel 1 (
    echo ERROR: PyInstaller fallo.
    pause & exit /b 1
)

:: ── 3. Copiar ADB e iconos al dist ───────────────
echo [3/4] Copiando ADB e iconos al dist...
copy /Y "%~dp0windows\phonemic.ico"  "%~dp0windows\dist\PhoneMic\" >nul
copy /Y "%~dp0windows\phonemic.png"  "%~dp0windows\dist\PhoneMic\" >nul
copy /Y "%~dp0installer\adb_files\platform-tools\adb.exe"          "%~dp0windows\dist\PhoneMic\" >nul
copy /Y "%~dp0installer\adb_files\platform-tools\AdbWinApi.dll"    "%~dp0windows\dist\PhoneMic\" >nul 2>nul
copy /Y "%~dp0installer\adb_files\platform-tools\AdbWinUsbApi.dll" "%~dp0windows\dist\PhoneMic\" >nul 2>nul

:: Copiar shiboken6.abi3.dll al directorio PySide6 del dist (PyInstaller no lo encuentra solo)
for /f "tokens=*" %%S in ('python -c "import shiboken6;print(shiboken6.__path__[0])" 2^>nul') do set "_SHIB=%%S"
if defined _SHIB if exist "%_SHIB%\shiboken6.abi3.dll" (
    if exist "%~dp0windows\dist\PhoneMic\_internal\PySide6" (
        copy /Y "%_SHIB%\shiboken6.abi3.dll" "%~dp0windows\dist\PhoneMic\_internal\PySide6\" >nul
        echo    shiboken6.abi3.dll copiada a _internal\PySide6\
    ) else if exist "%~dp0windows\dist\PhoneMic\PySide6" (
        copy /Y "%_SHIB%\shiboken6.abi3.dll" "%~dp0windows\dist\PhoneMic\PySide6\" >nul
        echo    shiboken6.abi3.dll copiada a PySide6\
    )
)
echo    Archivos copiados correctamente.
echo.

:: ── 4. Instalador ─────────────────────────────────
echo [4/4] Compilando instalador con Inno Setup...
cd /d "%~dp0"

:: Detectar Inno Setup 6 en ubicaciones comunes
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if not defined ISCC where ISCC.exe >nul 2>&1 && set "ISCC=ISCC.exe"
if not defined ISCC (
    echo ERROR: Inno Setup 6 no encontrado.
    echo Descargalo desde https://jrsoftware.org/isdl.php
    pause & exit /b 1
)
"%ISCC%" "%~dp0installer\phonemic_setup.iss"
if errorlevel 1 (
    echo ERROR: Fallo al compilar instalador.
    pause & exit /b 1
)
echo.

echo ================================================
echo   Build completado exitosamente!
echo.
echo   APK:        android\app\build\outputs\apk\debug\app-debug.apk
echo   EXE:        windows\dist\PhoneMic\PhoneMic.exe
echo   Instalador: installer\Output\PhoneMic_Setup.exe
echo ================================================
pause
