; PhoneMic - Script de instalador para Inno Setup 6
; Descarga Inno Setup (gratis): https://jrsoftware.org/isdl.php
;
; ANTES DE COMPILAR:
;   1. Ejecuta windows\build_exe.bat  (genera windows\dist\PhoneMic\)
;   2. Asegurate de tener installer\adb_files\platform-tools\adb.exe
;   3. Asegurate de tener installer\vbcable\VBCABLE_Setup_x64.exe
;   4. Abre este archivo en Inno Setup y pulsa Build > Compile (Ctrl+F9)
;   5. El instalador queda en installer\Output\PhoneMic_Setup.exe

#define AppName      "PhoneMic"
#define AppVersion   "1.0"
#define AppPublisher "PhoneMic"
#define AppExe       "PhoneMic.exe"
#define DistDir      "..\windows\dist\PhoneMic"
#define AdbDir       "adb_files\platform-tools"
#define VBCableDir   "vbcable"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=Output
OutputBaseFilename=PhoneMic_Setup
SetupIconFile=pngwing.com.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0
; Instalador pide admin una sola vez (necesario para driver VB-Cable).
; La app arranca sin UAC despues.
PrivilegesRequired=admin
RestartIfNeededByRun=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";   Description: "Crear icono en el &Escritorio";  GroupDescription: "Iconos adicionales:"
Name: "startmenuicon"; Description: "Crear icono en el &Menu Inicio"; GroupDescription: "Iconos adicionales:"
Name: "vbcable";       Description: "Instalar VB-Cable (microfono virtual para Discord/Zoom/OBS)"; GroupDescription: "Componentes adicionales:"; Flags: checkedonce

[Files]
; App principal (PyInstaller --onedir)
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; APK de Android (queda en carpeta de instalacion para instalar con ADB)
Source: "..\android\app\build\outputs\apk\debug\app-debug.apk"; DestDir: "{app}"; DestName: "PhoneMic.apk"; Flags: ignoreversion skipifsourcedoesntexist

; ADB bundleado
Source: "{#AdbDir}\adb.exe";          DestDir: "{app}"; Flags: ignoreversion
Source: "{#AdbDir}\AdbWinApi.dll";    DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#AdbDir}\AdbWinUsbApi.dll"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; VB-Cable - todos los archivos del driver deben estar juntos
Source: "{#VBCableDir}\*"; DestDir: "{tmp}\vbcable"; Flags: deleteafterinstall recursesubdirs; Tasks: vbcable

[Icons]
Name: "{autodesktop}\{#AppName}";       Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{group}\{#AppName}";             Filename: "{app}\{#AppExe}"; Tasks: startmenuicon
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"

[Run]
; Instalar VB-Cable silenciosamente (si el usuario lo eligio)
Filename: "{tmp}\vbcable\VBCABLE_Setup_x64.exe"; Parameters: "/S"; \
  WorkingDir: "{tmp}\vbcable"; \
  StatusMsg: "Instalando VB-Cable (requiere permisos de administrador)..."; \
  Flags: waituntilterminated; Tasks: vbcable; \
  Check: not IsVBCableInstalled

; Abrir la app al terminar
Filename: "{app}\{#AppExe}"; Description: "Iniciar {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]

var
  VBCableYaExistia: Boolean;  // true si VB-Cable estaba instalado ANTES de esta instalacion

// Detecta si VB-Cable ya esta instalado buscando el dispositivo en el registro
function IsVBCableInstalled(): Boolean;
var
  SubKey: string;
begin
  SubKey := 'SYSTEM\CurrentControlSet\Control\Class\{4d36e96c-e325-11ce-bfc1-08002be10318}';
  Result := RegKeyExists(HKLM, SubKey + '\VBAudioVACMME') or
            RegValueExists(HKLM, 'SOFTWARE\VB-Audio\Cable', 'DriverVersion');
end;

function InitializeSetup(): Boolean;
begin
  VBCableYaExistia := IsVBCableInstalled();
  Result := True;
end;

// Inno Setup llama esta funcion para saber si hay que reiniciar al terminar
function NeedsRestart(): Boolean;
begin
  // Pedir reinicio solo si VB-Cable fue recien instalado (no existia antes)
  Result := WizardIsTaskSelected('vbcable') and (not VBCableYaExistia);
end;
