; Trade Quest V2 - Windows installer (Phase D).
;
; Compiles the VERIFIED Phase C PyInstaller --onedir bundle
; (dist-desktop\TradeQuest) into a single per-machine setup executable.
;
; Build (from the project root):
;   "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" /Q packaging\TradeQuest.iss
;
; HARD RULE enforced by this script: user data lives in %LOCALAPPDATA%\TradeQuest
; and is NEVER created, seeded, migrated or deleted by the installer or the
; uninstaller. The application owns that directory entirely.

#define AppName "Trade Quest"
#define AppShortName "TradeQuest"
#define AppVersion "2.0.0"
#define AppExeName "TradeQuest.exe"
#define AppPublisher "Trade Quest"

[Setup]
AppId={{7B4C1E90-2A6D-4F51-9C3E-TQ2V2-BUILD-D2}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist-installer
OutputBaseFilename=TradeQuest-{#AppVersion}-win-x64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; x64 target
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=
; No network access at install time (no WebView2 bootstrapper download).
DisableDirPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; \
    GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
; The complete verified Phase C onedir bundle, internal layout preserved.
Source: "..\dist-desktop\TradeQuest\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; \
    Filename: "{app}\{#AppExeName}"; \
    WorkingDir: "{app}"; \
    Comment: "Trade Quest - local trading journal"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; \
    WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Launch after install. WorkingDir is the app dir so the process never depends
; on an inherited current directory; frozen asset/data paths are absolute anyway.
Filename: "{app}\{#AppExeName}"; \
    Description: "Launch {#AppName}"; \
    WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; ONLY inside the installation directory. There is deliberately NO entry for
; %LOCALAPPDATA%\TradeQuest - user data and backups must survive uninstall.
Type: filesandordirs; Name: "{app}"

[Code]
function WebView2Installed: Boolean;
var
  Key: String;
  Version: String;
begin
  Result := False;
  Key := 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Version := '';
  if RegQueryStringValue(HKLM, Key, 'pv', Version) and (Version <> '') then
  begin
    Result := True;
    Exit;
  end;
  Version := '';
  if RegQueryStringValue(HKCU, Key, 'pv', Version) then
    Result := (Version <> '');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not WebView2Installed) then
    MsgBox(
      'Trade Quest needs the Microsoft Edge WebView2 Runtime to show its window.' + #13#10 +
      'It was not detected on this computer.' + #13#10#13#10 +
      'Install it from https://developer.microsoft.com/microsoft-edge/webview2/' + #13#10 +
      'then start Trade Quest again.' + #13#10#13#10 +
      'Your journal is not affected.',
      mbInformation, MB_OK);
end;