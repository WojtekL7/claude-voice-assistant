; Inno Setup — Claude Voice Assistant (Windows) — Etap W4
; Buduje Setup.exe z folderu onedir (dist\Claude Voice Assistant\).
; Wywołanie (z korzenia repo):  iscc /DAppVersion=1.0.12 packaging\windows\installer.iss
; Zwykle robi to packaging\windows\build-windows.ps1.
;
; KLUCZOWE DECYZJE:
;  • Instalacja PER-UŻYTKOWNIK ({localappdata}\Programs) + PrivilegesRequired=lowest
;    → samo-aktualizacja działa CICHO, bez okna UAC/administratora.
;  • CloseApplications=yes → przy aktualizacji Inno zamyka działającą aplikację
;    (Restart Manager) i podmienia pliki, nawet jeśli była uruchomiona.
;  • [Run] bez skipifsilent → po cichej aktualizacji instalator sam wznawia program.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "Claude Voice Assistant"
#define AppExe "Claude Voice Assistant.exe"
#define Publisher "Fulfillment Polska"
; {#SourcePath} = katalog tego .iss (packaging\windows); korzeń repo = dwa wyżej.
#define ProjectRoot AddBackslash(SourcePath) + "..\.."

[Setup]
; AppId STAŁY (GUID) — pozwala Inno rozpoznać instalację przy aktualizacji. NIE zmieniać.
AppId={{B8E7C2A1-5F3D-4A6B-9C1E-7D2F4A8B6C90}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#ProjectRoot}\dist
OutputBaseFilename=ClaudeVoiceAssistant-Setup-{#AppVersion}
SetupIconFile={#ProjectRoot}\src\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Aktualizacja działającej aplikacji: zamknij ją i podmień pliki (Restart Manager).
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Cała zawartość folderu onedir z PyInstallera.
Source: "{#ProjectRoot}\dist\{#AppName}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; Po instalacji uruchom program. BEZ skipifsilent — dzięki temu po CICHEJ
; samo-aktualizacji (/SILENT) instalator sam wznawia aplikację.
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall
