#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Lex Mint"
#define AppPublisher "Lex Mint"
#define AppExeName "start_lex_mint.bat"
#define AppStopExeName "stop_lex_mint.bat"

[Setup]
AppId={{F6A6BE77-2F23-4F95-AD66-9D296C15D042}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Lex Mint
DefaultGroupName=Lex Mint
UninstallDisplayIcon={app}\backend\lex_mint_backend.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
OutputBaseFilename=lex-mint-setup-{#AppVersion}
OutputDir={#InstallerOutputDir}
SetupLogging=yes
DisableDirPage=no
DisableProgramGroupPage=no
ChangesAssociations=no
CloseApplications=force
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Lex Mint"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Stop Lex Mint"; Filename: "{app}\{#AppStopExeName}"
Name: "{group}\Uninstall Lex Mint"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Lex Mint"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Lex Mint"; Flags: nowait postinstall skipifsilent shellexec

[UninstallRun]
Filename: "{app}\{#AppStopExeName}"; RunOnceId: "StopLexMint"; Flags: runhidden shellexec skipifdoesntexist
