; Builds KaraokeMaker-Setup.exe: a small setup program to share.
;   iscc /DAppVersion=0.2.0 /DPythonInstaller=python-3.13.x-amd64.exe installer\karaoke-maker.iss
;
; It installs Karaoke Maker for the current user (no administrator needed),
; installs Python 3.13 from the bundled python.org installer if the PC
; doesn't have it, makes the shortcuts, then runs Install.bat to download the
; AI tools and models (about 5 GB) in a window that shows its progress.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef PythonInstaller
  #error Pass /DPythonInstaller=<path to python-3.13.x-amd64.exe>
#endif

[Setup]
AppId={{5C8A1E2D-7B34-4F6A-9D21-0E4B7C3A9F10}
AppName=Karaoke Maker
AppVersion={#AppVersion}
AppPublisher=Deano
DefaultDirName={autopf}\Karaoke Maker
DefaultGroupName=Karaoke Maker
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=KaraokeMaker-Setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\karaoke.ico
UninstallDisplayIcon={app}\karaoke.ico
WizardStyle=modern

[Messages]
WelcomeLabel2=This installs Karaoke Maker, which makes MP3+CDG karaoke tracks (and MP4 videos) from songs with vocals.%n%nAfter the files are copied, the AI tools and models it needs are downloaded: about 5 GB, which takes 15-30 minutes on a good connection. You'll need about 8 GB of free disk space.

[Tasks]
Name: "desktopicon"; Description: "Put a Karaoke Maker icon on the desktop"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\karaoke_maker\*.py"; DestDir: "{app}\karaoke_maker"; Flags: ignoreversion
Source: "..\karaoke.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\setup_gpu.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Install.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Make Karaoke.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Create Desktop Shortcut.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PythonInstaller}"; DestDir: "{tmp}"; DestName: "python-installer.exe"; Flags: deleteafterinstall

[Icons]
Name: "{group}\Karaoke Maker"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-m karaoke_maker.gui"; WorkingDir: "{app}"; IconFilename: "{app}\karaoke.ico"
Name: "{group}\Repair Karaoke Maker (download the AI tools again)"; Filename: "{app}\Install.bat"; WorkingDir: "{app}"; IconFilename: "{app}\karaoke.ico"
Name: "{group}\Uninstall Karaoke Maker"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Karaoke Maker"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-m karaoke_maker.gui"; WorkingDir: "{app}"; IconFilename: "{app}\karaoke.ico"; Tasks: desktopicon

[Run]
Filename: "{tmp}\python-installer.exe"; Parameters: "/quiet InstallAllUsers=0 Include_launcher=1 InstallLauncherAllUsers=0 Include_test=0 Include_doc=0 Shortcuts=0 AssociateFiles=0 PrependPath=0"; StatusMsg: "Installing Python 3.13 (needed by the AI tools)..."; Check: NeedsPython
Filename: "{cmd}"; Parameters: "/c ""{app}\Install.bat"" auto"; WorkingDir: "{app}"; StatusMsg: "Downloading the AI tools and models (about 5 GB). Progress shows in the black window: please leave it open..."; Flags: waituntilterminated
Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: "-m karaoke_maker.gui"; WorkingDir: "{app}"; Description: "Open Karaoke Maker now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\karaoke_maker\__pycache__"
Type: files; Name: "{app}\settings.json"
Type: files; Name: "{app}\error-log.txt"

[Code]
function HasPython313(Root: Integer): Boolean;
var
  Path: String;
begin
  Result := RegQueryStringValue(Root, 'Software\Python\PythonCore\3.13\InstallPath', '', Path)
            and FileExists(AddBackslash(Path) + 'python.exe');
end;

function NeedsPython(): Boolean;
begin
  Result := not (HasPython313(HKEY_CURRENT_USER) or HasPython313(HKEY_LOCAL_MACHINE));
end;
