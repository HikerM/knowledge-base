#define AppName "Personal Knowledge Base"
#define AppVersion "2.0.0-rc.2"
#define AppPublisher "HikerM"
#define AppExeName "pkb-gui.exe"
#define RepoRoot AddBackslash(SourcePath) + "..\..\..\"
#define DistDir RepoRoot + "dist\pkb-gui"
#define IconPath RepoRoot + "assets\app-icon\app-icon.ico"

[Setup]
AppId={{D9D36F92-61D6-46BB-9E0E-BCA3DBDA7E5B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\PersonalKnowledgeBase
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#RepoRoot}packaging\installer\output
OutputBaseFilename=PersonalKnowledgeBase-Setup-v2.0.0-rc.2
SetupIconFile={#IconPath}
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion=2.0.0.2
VersionInfoVersion=2.0.0.2
UsePreviousAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Excludes: "_internal\PySide6\qml\Qt\labs\assetdownloader\objects-Debug\*"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Personal Knowledge Base"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Personal Knowledge Base"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,Personal Knowledge Base}"; Flags: nowait postinstall skipifsilent
