@echo off
title PhoneMic - Instalador
echo ===================================
echo   PhoneMic Client - Instalacion
echo ===================================
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado.
    echo Descarga Python desde https://python.org
    pause
    exit /b 1
)

echo [OK] Python encontrado
echo.
echo Instalando dependencias...
pip install pyaudio >nul 2>&1
if errorlevel 1 (
    echo [WARN] pyaudio fallo. Intentando con pipwin...
    pip install pipwin >nul 2>&1
    pipwin install pyaudio >nul 2>&1
)

echo [OK] Dependencias instaladas
echo.

:: Verificar ADB
where adb >nul 2>&1
if errorlevel 1 (
    echo [WARN] adb.exe no esta en el PATH.
    echo.
    echo Opciones:
    echo  1. Instala Android SDK Platform Tools
    echo  2. Copia adb.exe en esta carpeta: %~dp0
    echo.
    echo Buscando adb en ubicaciones conocidas...
    if exist "%~dp0adb.exe" (
        set PATH=%PATH%;%~dp0
        echo [OK] Usando adb local (junto al script)
    ) else if exist "C:\Program Files (x86)\WOMic\adb.exe" (
        set PATH=%PATH%;C:\Program Files (x86)\WOMic
        echo [OK] Usando adb de WoMic
    ) else if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
        set PATH=%PATH%;%LOCALAPPDATA%\Android\Sdk\platform-tools
        echo [OK] Usando adb de Android SDK
    ) else (
        echo [WARN] adb.exe no encontrado. Copia adb.exe en: %~dp0
    )
)

echo.
echo Iniciando PhoneMic Client...
echo.
python "%~dp0phonemic_client.py"
pause
