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
#define AppVersion   "1.3"
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
  VBCableYaExistia: Boolean;

// Compara dos strings de version "X.Y.Z". Devuelve -1, 0, o 1.
function CompareVersions(V1, V2: String): Integer;
var
  P, N1, N2: Integer;
begin
  Result := 0;
  while (Result = 0) and ((V1 <> '') or (V2 <> '')) do
  begin
    P := Pos('.', V1);
    if P > 0 then begin N1 := StrToIntDef(Copy(V1, 1, P-1), 0); V1 := Copy(V1, P+1, MaxInt); end
    else begin N1 := StrToIntDef(V1, 0); V1 := ''; end;
    P := Pos('.', V2);
    if P > 0 then begin N2 := StrToIntDef(Copy(V2, 1, P-1), 0); V2 := Copy(V2, P+1, MaxInt); end
    else begin N2 := StrToIntDef(V2, 0); V2 := ''; end;
    if N1 < N2 then Result := -1
    else if N1 > N2 then Result := 1;
  end;
end;

function IsVBCableInstalled(): Boolean;
var
  SubKey: string;
begin
  SubKey := 'SYSTEM\CurrentControlSet\Control\Class\{4d36e96c-e325-11ce-bfc1-08002be10318}';
  Result := RegKeyExists(HKLM, SubKey + '\VBAudioVACMME') or
            RegValueExists(HKLM, 'SOFTWARE\VB-Audio\Cable', 'DriverVersion');
end;

function InitializeSetup(): Boolean;
var
  InstalledVer: String;
  Cmp: Integer;
  RegKey: String;
begin
  VBCableYaExistia := IsVBCableInstalled();

  RegKey := 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\' +
            '{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}_is1';

  if RegQueryStringValue(HKLM, RegKey, 'DisplayVersion', InstalledVer) then
  begin
    Cmp := CompareVersions(InstalledVer, '{#AppVersion}');

    if Cmp = 0 then
    begin
      // Misma version instalada
      Result := MsgBox(
        'PhoneMic ' + InstalledVer + ' ya esta instalado.' + #13#10 + #13#10 +
        '¿Deseas reinstalar la misma version?',
        mbConfirmation, MB_YESNO) = IDYES;
    end
    else if Cmp > 0 then
    begin
      // Version instalada es mas nueva (downgrade)
      Result := MsgBox(
        'Tienes una version mas nueva instalada (' + InstalledVer + ').' + #13#10 +
        'Este instalador contiene la version {#AppVersion}.' + #13#10 + #13#10 +
        '¿Deseas instalar la version anterior de todas formas?',
        mbConfirmation, MB_YESNO) = IDYES;
    end
    else
    begin
      // Actualizacion disponible
      Result := MsgBox(
        'PhoneMic ' + InstalledVer + ' esta instalado.' + #13#10 +
        'Este instalador actualizara a la version {#AppVersion}.' + #13#10 + #13#10 +
        '¿Deseas actualizar?',
        mbConfirmation, MB_YESNO) = IDYES;
    end;
  end
  else
    Result := True;  // Instalacion nueva, continuar sin preguntar
end;

// Pedir reinicio solo si VB-Cable fue recien instalado
function NeedsRestart(): Boolean;
begin
  Result := WizardIsTaskSelected('vbcable') and (not VBCableYaExistia);
end;
