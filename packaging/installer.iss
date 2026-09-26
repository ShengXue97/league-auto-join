; League Remote installer (Inno Setup 6). Built by build.py, which passes /DAppVersion=x.y.z
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F3C2A8E-9B41-4D6A-A7E2-5C1B8D0F4E7A}
AppName=League Remote
AppVersion={#AppVersion}
AppVerName=League Remote {#AppVersion}
AppPublisher=League Remote (fan project)
DefaultDirName={autopf}\League Remote
DefaultGroupName=League Remote
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=LeagueRemote-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\LeagueRemote.exe
UninstallDisplayName=League Remote
VersionInfoVersion={#AppVersion}
VersionInfoProductName=League Remote
VersionInfoDescription=League Remote setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; admin: install to Program Files and allow the phone to connect (firewall rule)
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force

[Tasks]
Name: "startup"; Description: "Start League Remote when I log in to Windows (recommended)"
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "publicnet"; Description: "Also allow my phone to connect on networks Windows calls ""Public"" (less safe - only if your home Wi-Fi is set to Public and you can't change it)"; Flags: unchecked

[Files]
Source: "..\dist\LeagueRemote\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\League Remote"; Filename: "{app}\LeagueRemote.exe"
Name: "{group}\Uninstall League Remote"; Filename: "{uninstallexe}"
Name: "{autodesktop}\League Remote"; Filename: "{app}\LeagueRemote.exe"; Tasks: desktopicon

[Run]
; let the phone reach the control page on home networks only (Private), never on public Wi-Fi
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""League Remote"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""League Remote"" dir=in action=allow program=""{app}\LeagueRemote.exe"" enable=yes profile=private"; Flags: runhidden; Tasks: not publicnet
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""League Remote"" dir=in action=allow program=""{app}\LeagueRemote.exe"" enable=yes profile=private,public"; Flags: runhidden; Tasks: publicnet
Filename: "{app}\LeagueRemote.exe"; Parameters: "--install-startup"; Flags: runhidden runasoriginaluser; Tasks: startup
Filename: "{app}\LeagueRemote.exe"; Parameters: "--show-setup"; Description: "Start League Remote and set up my phone"; Flags: postinstall nowait skipifsilent runasoriginaluser
; one-click updates install silently: start the new version again afterwards
Filename: "{app}\LeagueRemote.exe"; Flags: nowait runasoriginaluser; Check: WizardSilent

[UninstallRun]
Filename: "{app}\LeagueRemote.exe"; Parameters: "--stop"; Flags: runhidden; RunOnceId: "StopApp"
Filename: "{app}\LeagueRemote.exe"; Parameters: "--uninstall-startup"; Flags: runhidden; RunOnceId: "RemoveStartup"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""League Remote"""; Flags: runhidden; RunOnceId: "RemoveFirewallRule"

[Messages]
FinishedLabel=League Remote is installed.%n%nIt runs in the notification area: look for the gold bell icon near the clock (click the ^ arrow if you don't see it). Right-click it any time to open the control page or the phone setup.%n%nThe phone setup page opens in your browser when you click Finish.

[Code]
// Stop a running League Remote before replacing its files (updates).
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  if FileExists(ExpandConstant('{app}\LeagueRemote.exe')) then
    Exec(ExpandConstant('{app}\LeagueRemote.exe'), '--stop', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
