@echo off
:: Buscar adb.exe: junto al script > WoMic > Android SDK > PATH
if exist "%~dp0adb.exe" (
    set PATH=%PATH%;%~dp0
) else if exist "C:\Program Files (x86)\WOMic\adb.exe" (
    set PATH=%PATH%;C:\Program Files (x86)\WOMic
) else if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    set PATH=%PATH%;%LOCALAPPDATA%\Android\Sdk\platform-tools
)
python "%~dp0phonemic_client.py"
