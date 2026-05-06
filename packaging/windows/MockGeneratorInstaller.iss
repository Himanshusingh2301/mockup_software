; Mock Generator Windows Installer (Inno Setup)
; Build prerequisites:
; 1) Run packaging\windows\build-backend-exe.bat
; 2) Build frontend: cd mockup-tool-frontend && npm run build
; 3) Open this .iss in Inno Setup and Compile.

#define AppName "Mock Generator"
#define AppVersion "1.0.0"
#define AppPublisher "Mock Generator"
#define AppExe "launcher\\start-mockgenerator.bat"

[Setup]
AppId={{6D2A9A6D-5B54-4B3F-B305-77A3A8AB5F39}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\\Mock Generator
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=MockGeneratorInstaller
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Backend packaged executable output (from PyInstaller --onedir)
Source: "..\\..\\backend\\dist\\mockgenerator-backend\\*"; DestDir: "{app}\\backend"; Flags: recursesubdirs createallsubdirs ignoreversion

; Frontend static build
Source: "..\\..\\mockup-tool-frontend\\dist\\*"; DestDir: "{app}\\frontend\\dist"; Flags: recursesubdirs createallsubdirs ignoreversion

; Launch scripts
Source: "start-mockgenerator.bat"; DestDir: "{app}\\launcher"; Flags: ignoreversion
Source: "stop-mockgenerator.bat"; DestDir: "{app}\\launcher"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\\{#AppName}"; Filename: "{app}\\{#AppExe}"
Name: "{group}\\{#AppName}"; Filename: "{app}\\{#AppExe}"
Name: "{group}\\Stop {#AppName}"; Filename: "{app}\\launcher\\stop-mockgenerator.bat"
Name: "{group}\\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[UninstallDelete]
; Fully remove user runtime data as requested
Type: filesandordirs; Name: "{localappdata}\\MockGenerator\\data"

[Run]
Filename: "{app}\\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
