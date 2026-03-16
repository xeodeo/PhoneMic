@echo off
:: Agrega adb de WoMic al PATH si existe
if exist "C:\Program Files (x86)\WOMic\adb.exe" (
    set PATH=%PATH%;C:\Program Files (x86)\WOMic
)
python "%~dp0phonemic_client.py"
