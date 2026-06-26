; Inno Setup — Vibe Coding Assistant (Windows) — Etap W4
; Buduje Setup.exe z folderu onedir (dist\Vibe Coding Assistant\).
; Wywołanie (z korzenia repo):  iscc /DAppVersion=1.0.12 packaging\windows\installer.iss
; Zwykle robi to packaging\windows\build-windows.ps1.
;
; KLUCZOWE DECYZJE:
;  • Instalacja PER-UŻYTKOWNIK ({localappdata}\Programs) + PrivilegesRequired=lowest
;    → samo-aktualizacja działa CICHO, bez okna UAC/administratora.
;  • CloseApplications=yes → przy aktualizacji Inno zamyka działającą aplikację
;    (Restart Manager) i podmienia pliki, nawet jeśli była uruchomiona.
;  • [Run] bez skipifsilent → po cichej aktualizacji instalator sam wznawia program.
;  • Zadanie „nodecli" ([Tasks] + [Code]) — opcjonalne dociągnięcie Node.js
;    (oficjalny MSI z nodejs.org, wersja LTS odczytana z dist/index.json)
;    i Claude Code (npm install -g). Pokazywane tylko, gdy czegoś brakuje.
;    Przy CICHEJ samo-aktualizacji (/VERYSILENT) nigdy się nie uruchamia
;    (w trybie silent strona wpReady nie istnieje → NodeMsiReady zostaje False).
;  • Plik MUSI być UTF-8 Z BOM — bez BOM Inno czyta go jako ANSI i polskie
;    znaki w komunikatach [Code] zamieniają się w krzaki.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "Vibe Coding Assistant"
#define AppExe "Vibe Coding Assistant.exe"
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
OutputBaseFilename=VibeCodingAssistant-Setup-{#AppVersion}
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
; Doinstalowanie wymaganych dodatków. Pokazywane TYLKO, gdy brakuje Node.js lub
; Claude Code (Check). Domyślnie zaznaczone — laik klika Dalej i ma komplet.
Name: "nodecli"; Description: "Pobierz i zainstaluj Node.js + Claude Code (wymagane do działania programu)"; GroupDescription: "Dodatki wymagane do działania:"; Check: NodeCliMissing

[InstallDelete]
; Przy AKTUALIZACJI wyczyść stary zestaw plików PyInstallera PRZED wgraniem nowego.
; PyInstaller (onedir) trzyma biblioteki w podfolderze "_internal"; między wersjami
; zestaw plików potrafi się różnić, a kopiowanie nowych NIE usuwa starych →
; „mieszanka" niepasujących bibliotek wywala start. Czyścimy folder programu, ale
; NIE dane użytkownika (te są w %USERPROFILE%\.claude-voice-assistant, poza {app}).
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\*.dll"
Type: files; Name: "{app}\*.pyd"

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

[Code]
{ ===== Zadanie „nodecli": dociągnięcie Node.js + Claude Code =====
  Przebieg: wpReady → pobierz dist/index.json → ustal najnowsze LTS → pobierz
  oficjalny MSI → (ssPostInstall) msiexec /passive (tu Windows pokaże JEDNO okno
  UAC — Node.js instaluje się dla całego systemu, to normalne) → npm install -g
  @anthropic-ai/claude-code. Każde niepowodzenie jest ŁAGODNE: komunikat
  i instalacja programu idzie dalej — kreator w aplikacji poprowadzi ręcznie. }

var
  DownloadPage: TDownloadWizardPage;
  NodeMsiReady: Boolean;   { MSI pobrane i czeka w katalogu tymczasowym }

{ Czy komenda jest w PATH użytkownika (`where`)? Łapie KAŻDY sposób instalacji:
  oficjalny MSI, winget, chocolatey, nvm-windows, scoop… — nie tylko domyślny
  katalog Program Files. }
function CommandOnPath(const Cmd: String): Boolean;
var
  R: Integer;
begin
  Result := Exec(ExpandConstant('{cmd}'), '/c where ' + Cmd + ' >nul 2>&1',
    '', SW_HIDE, ewWaitUntilTerminated, R) and (R = 0);
end;

function NodeJsPresent(): Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf64}\nodejs\node.exe'))
    or FileExists(ExpandConstant('{commonpf}\nodejs\node.exe'))
    or CommandOnPath('node');
end;

function ClaudeCliPresent(): Boolean;
begin
  Result := FileExists(ExpandConstant('{userappdata}\npm\claude.cmd'))
    or FileExists(ExpandConstant('{userappdata}\npm\claude'))
    or CommandOnPath('claude');
end;

{ Check zadania „nodecli" — pokazuj tylko, gdy realnie czegoś brakuje. }
function NodeCliMissing(): Boolean;
begin
  Result := (not NodeJsPresent()) or (not ClaudeCliPresent());
end;

procedure InitializeWizard();
begin
  NodeMsiReady := False;
  DownloadPage := CreateDownloadPage(
    'Pobieranie dodatków', 'Pobieram Node.js (wymagany do działania programu)…', nil);
end;

{ Z nodejs.org/dist/index.json wyciągnij wersję najnowszego LTS (np. 'v22.17.1').
  Plik jest posortowany od najnowszych wydań, a pole "lts" ma wartość tekstową
  (nazwę linii LTS) tylko we wpisach LTS — pierwsze '"lts":"' wskazuje więc
  najnowsze LTS; wersja to ostatnie '"version":"' przed tym miejscem. }
function ResolveLtsVersion(const JsonPath: String): String;
var
  S: AnsiString;
  Head: String;
  PLts, P, Q, Found, VEnd: Integer;
begin
  Result := '';
  if not LoadStringFromFile(JsonPath, S) then Exit;
  Head := Copy(String(S), 1, 30000);  { LTS jest w pierwszych wpisach }
  PLts := Pos('"lts":"', Head);
  if PLts = 0 then Exit;
  Found := 0;
  P := 1;
  repeat
    Q := Pos('"version":"', Copy(Head, P, PLts - P));
    if Q > 0 then begin
      Found := P + Q - 1;
      P := Found + Length('"version":"');
    end;
  until Q = 0;
  if Found = 0 then Exit;
  P := Found + Length('"version":"');
  VEnd := P;
  while (VEnd <= Length(Head)) and (Head[VEnd] <> '"') do
    VEnd := VEnd + 1;
  Result := Copy(Head, P, VEnd - P);
  { Sanity: 'v' + cyfra; cokolwiek innego = nie ryzykuj zlepionego URL-a. }
  if (Length(Result) < 2) or (Result[1] <> 'v') then
    Result := '';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Ver: String;
begin
  Result := True;
  if (CurPageID <> wpReady) or (not WizardIsTaskSelected('nodecli')) then Exit;
  if NodeJsPresent() then Exit;  { brakowało tylko claude — npm zrobi swoje w ssPostInstall }
  DownloadPage.Clear;
  DownloadPage.Add('https://nodejs.org/dist/index.json', 'node-index.json', '');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
      Ver := ResolveLtsVersion(ExpandConstant('{tmp}\node-index.json'));
      if Ver = '' then
        RaiseException('nie udało się ustalić wersji LTS');
      DownloadPage.Clear;
      DownloadPage.Add(
        'https://nodejs.org/dist/' + Ver + '/node-' + Ver + '-x64.msi',
        'nodejs-lts.msi', '');
      DownloadPage.Download;
      NodeMsiReady := True;
    except
      MsgBox('Nie udało się pobrać Node.js (sprawdź internet).' + #13#10
        + 'Instalacja programu będzie kontynuowana — po pierwszym uruchomieniu '
        + 'kreator w aplikacji poprowadzi przez instalację dodatków.',
        mbInformation, MB_OK);
    end;
  finally
    DownloadPage.Hide;
  end;
end;

procedure InstallNodeAndClaude();
var
  R: Integer;
  NpmPath, NpmArgs: String;
begin
  { 1) Node.js z pobranego MSI (pomijane, gdy już jest — np. brakowało tylko claude). }
  if (not NodeJsPresent()) and NodeMsiReady then begin
    if (not Exec('msiexec.exe',
        '/i "' + ExpandConstant('{tmp}\nodejs-lts.msi') + '" /passive /norestart',
        '', SW_SHOW, ewWaitUntilTerminated, R)) or (R <> 0) then begin
      MsgBox('Instalacja Node.js nie powiodła się (kod ' + IntToStr(R) + ').' + #13#10
        + 'Po uruchomieniu programu kreator poprowadzi przez instalację ręczną.',
        mbInformation, MB_OK);
      Exit;
    end;
  end;
  { 2) Claude Code przez npm. Najpierw pełna ścieżka do npm.cmd (PATH tego
       procesu nie zna jeszcze świeżo zainstalowanego Node.js); gdy Node był
       zainstalowany wcześniej w niestandardowym miejscu (nvm/scoop/winget) —
       npm z PATH. }
  NpmPath := ExpandConstant('{commonpf64}\nodejs\npm.cmd');
  if not FileExists(NpmPath) then
    NpmPath := ExpandConstant('{commonpf}\nodejs\npm.cmd');
  if FileExists(NpmPath) then
    NpmArgs := '/c ""' + NpmPath + '" install -g @anthropic-ai/claude-code"'
  else if CommandOnPath('npm') then
    NpmArgs := '/c npm install -g @anthropic-ai/claude-code'
  else begin
    MsgBox('Nie znaleziono npm po instalacji Node.js.' + #13#10
      + 'Po uruchomieniu programu kreator poprowadzi przez instalację ręczną.',
      mbInformation, MB_OK);
    Exit;
  end;
  if Exec(ExpandConstant('{cmd}'), NpmArgs,
      '', SW_SHOW, ewWaitUntilTerminated, R) and (R = 0) then
    MsgBox('Node.js i Claude Code zostały zainstalowane. ✓' + #13#10#13#10
      + 'Po uruchomieniu programu wpisz w terminalu „claude” i naciśnij Enter, '
      + 'aby się zalogować.', mbInformation, MB_OK)
  else
    MsgBox('Claude Code nie zainstalował się automatycznie (kod ' + IntToStr(R) + ').'
      + #13#10 + 'Po uruchomieniu programu kreator poprowadzi przez instalację ręczną.',
      mbInformation, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep <> ssPostInstall then Exit;
  { Tylko świadoma, interaktywna instalacja z zaznaczonym zadaniem. Przy cichej
    samo-aktualizacji NodeMsiReady=False i (zwykle) wszystko już jest. }
  if not WizardIsTaskSelected('nodecli') then Exit;
  if NodeJsPresent() and ClaudeCliPresent() then Exit;
  if (not NodeJsPresent()) and (not NodeMsiReady) then Exit;  { pobieranie padło }
  InstallNodeAndClaude();
end;
