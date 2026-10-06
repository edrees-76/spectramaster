; SpectraMaster 1.0.0 - Windows installer (Inno Setup 6.6+)
; Designer / publisher: Edrees F. Hery
;
; Build:  bash build_exe/build_installer.sh          (PyInstaller one-folder builds + this script)
;         "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\SpectraMaster.iss
;                                                    (only the installer, from an existing build)
; Input:  build_exe\dist_onedir\SpectraMaster\  (GUI: SpectraMaster.exe + _internal\)  -> {app}
;         build_exe\dist_onedir\smconvert\      (CLI: smconvert.exe + _internal\)      -> {app}\cli
; Output: installer\Output\SpectraMaster_Setup_1.0.0.exe
;
; This file is UTF-8 with BOM (Arabic custom messages).

#define AppName      "SpectraMaster"
#define AppVersion   "1.0.0"
#define AppPublisher "Edrees F. Hery"
#define AppExe       "SpectraMaster.exe"
#define ProgID       "SpectraMaster.Spectrum"
#define AppUserModel "SpectraMaster.GUI"
#define DistGui      "..\build_exe\dist_onedir\SpectraMaster"
#define DistCli      "..\build_exe\dist_onedir\smconvert"

; spectrum file types offered for association (keep in sync with ExtList in [Code])
#define ExtCount 7
#define I 0
#dim Exts[ExtCount]     {"s0", "chn", "cnf", "spe", "spc", "iec", "n42"}
#dim ExtNames[ExtCount] {"APTEC", "ORTEC CHN", "Canberra CAM / Genie-2000", "IAEA / ORTEC SPE", "ORTEC SPC", "IEC 1455", "ANSI N42.42"}

#if !FileExists(AddBackslash(SourcePath) + DistGui + "\" + AppExe)
  #error "GUI build missing - run: bash build_exe/build_installer.sh"
#endif
#if !FileExists(AddBackslash(SourcePath) + DistCli + "\smconvert.exe")
  #error "CLI build missing - run: bash build_exe/build_installer.sh"
#endif

[Setup]
AppId={{3500E10C-056E-4CF9-8DAB-B040495FDF42}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright=© 2026 {#AppPublisher}
AppComments=Gamma-spectrum file conversion, viewing and analysis
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExe}
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoProductTextVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoCopyright=© 2026 {#AppPublisher}
VersionInfoDescription={#AppName} {#AppVersion} Setup
; --- all users, 64-bit, Program Files
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
DisableDirPage=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
ChangesAssociations=yes
ChangesEnvironment=yes
CloseApplications=yes
; --- languages: the user chooses at start, English is preselected
ShowLanguageDialog=yes
LanguageDetectionMethod=none
; --- look
WizardStyle=modern
SetupIconFile=..\spectramaster\gui\spectramaster.ico
WizardImageFile=images\wizard_164x314.bmp,images\wizard_192x386.bmp,images\wizard_246x459.bmp,images\wizard_273x556.bmp,images\wizard_328x604.bmp,images\wizard_355x700.bmp,images\wizard_410x797.bmp
WizardSmallImageFile=images\wizard_small_55x55.bmp,images\wizard_small_64x68.bmp,images\wizard_small_83x80.bmp,images\wizard_small_92x97.bmp,images\wizard_small_110x106.bmp,images\wizard_small_119x123.bmp,images\wizard_small_138x140.bmp
WizardImageBackColor=clWhite
; --- output
OutputDir=Output
OutputBaseFilename=SpectraMaster_Setup_{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl";           LicenseFile: "LICENSE_en.txt"
Name: "arabic";  MessagesFile: "compiler:Languages\Arabic.isl";  LicenseFile: "LICENSE_ar.txt"

[Messages]
english.FinishedLabel=Setup has finished installing [name] on your computer. The application may be launched by selecting the installed shortcuts.%n%nTip: to pin SpectraMaster to the taskbar, open the Start menu, right-click SpectraMaster and choose "Pin to taskbar" (or right-click its taskbar button while it is running).
arabic.FinishedLabel=اكتمل معالج التثبيت من تثبيت [name] على جهازك. يمكن تشغيل البرنامج من الاختصارات المثبّتة.%n%nتلميح: لتثبيت SpectraMaster على شريط المهام افتح قائمة ابدأ، وانقر بزر الفأرة الأيمن على SpectraMaster، واختر "التثبيت على شريط المهام" (أو انقر بالزر الأيمن على زره في شريط المهام أثناء تشغيله).

[CustomMessages]
english.TypeFull=Full installation
english.TypeCompact=Compact installation (program and manuals)
english.TypeCustom=Custom installation
english.CompMain=Main program (SpectraMaster)
english.CompCli=Command-line tool smconvert
english.CompManuals=User manuals (English and Arabic, PDF)
english.CompSamples=Sample spectra
english.GroupCli=Command-line tool:
english.TaskPath=Add smconvert to the system PATH
english.GroupAssoc=File associations:
english.TaskAssoc=Open spectrum files with SpectraMaster (also adds "Open with SpectraMaster")
english.AssocExt=%1 files (%2)
english.ProgIdName=Gamma spectrum
english.ManualEN=User Manual (English)
english.ManualAR=User Manual (Arabic)
english.ReleaseNotes=Release Notes
english.SampleSpectra=Sample Spectra
english.ViewReleaseNotes=View release notes
english.AskDeleteData=Do you also want to delete your SpectraMaster data and settings?%n%n  %1%n  (archive index, efficiency curves, QC tracks ...)%n  HKEY_CURRENT_USER\Software\SpectraMaster (settings)%n%nChoose "No" to keep them for a later installation.
english.AppDescription=Gamma-spectrum file conversion, viewing and analysis

arabic.TypeFull=تثبيت كامل
arabic.TypeCompact=تثبيت محدود (البرنامج والأدلة)
arabic.TypeCustom=تثبيت مخصص
arabic.CompMain=البرنامج الرئيسي (SpectraMaster)
arabic.CompCli=أداة سطر الأوامر smconvert
arabic.CompManuals=أدلة المستخدم (الإنجليزية والعربية، PDF)
arabic.CompSamples=أطياف نموذجية
arabic.GroupCli=أداة سطر الأوامر:
arabic.TaskPath=إضافة smconvert إلى متغير PATH للنظام
arabic.GroupAssoc=ربط أنواع الملفات:
arabic.TaskAssoc=فتح ملفات الأطياف باستخدام SpectraMaster (ويضيف أيضًا "فتح باستخدام SpectraMaster")
arabic.AssocExt=ملفات %1 (%2)
arabic.ProgIdName=طيف أشعة جاما
arabic.ManualEN=دليل المستخدم (الإنجليزية)
arabic.ManualAR=دليل المستخدم (العربية)
arabic.ReleaseNotes=ملاحظات الإصدار
arabic.SampleSpectra=أطياف نموذجية
arabic.ViewReleaseNotes=عرض ملاحظات الإصدار
arabic.AskDeleteData=هل تريد أيضًا حذف بيانات SpectraMaster وإعداداته؟%n%n  %1%n  (فهرس الأرشيف، منحنيات الكفاءة، سجلات مراقبة الجودة ...)%n  HKEY_CURRENT_USER\Software\SpectraMaster (الإعدادات)%n%nاختر "لا" للاحتفاظ بها لتثبيت لاحق.
arabic.AppDescription=تحويل ملفات أطياف أشعة جاما وعرضها وتحليلها

[Types]
Name: "full";    Description: "{cm:TypeFull}"
Name: "compact"; Description: "{cm:TypeCompact}"
Name: "custom";  Description: "{cm:TypeCustom}"; Flags: iscustom

[Components]
Name: "main";    Description: "{cm:CompMain}";    Types: full compact custom; Flags: fixed
Name: "cli";     Description: "{cm:CompCli}";     Types: full
Name: "manuals"; Description: "{cm:CompManuals}"; Types: full compact
Name: "samples"; Description: "{cm:CompSamples}"; Types: full

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "clipath";     Description: "{cm:TaskPath}";          GroupDescription: "{cm:GroupCli}"; Components: cli
Name: "assoc";       Description: "{cm:TaskAssoc}";         GroupDescription: "{cm:GroupAssoc}"
#sub EmitAssocTask
Name: "assoc\{#Exts[I]}"; Description: "{cm:AssocExt,.{#Exts[I]},{#ExtNames[I]}}"
#endsub
#for {I = 0; I < ExtCount; I++} EmitAssocTask

[Files]
; main program: one-folder PyInstaller build (the LGPL Qt / SpecUtils libraries stay replaceable files)
Source: "{#DistGui}\*"; DestDir: "{app}"; Components: main; Flags: ignoreversion recursesubdirs createallsubdirs
; command-line tool in its own sub-folder with its own _internal (never shares files with the GUI)
Source: "{#DistCli}\*"; DestDir: "{app}\cli"; Components: cli; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE_en.txt";       DestDir: "{app}"; Components: main; Flags: ignoreversion
Source: "LICENSE_ar.txt";       DestDir: "{app}"; Components: main; Flags: ignoreversion
Source: "RELEASE_NOTES_en.txt"; DestDir: "{app}"; Components: main; Flags: ignoreversion
Source: "RELEASE_NOTES_ar.txt"; DestDir: "{app}"; Components: main; Flags: ignoreversion
Source: "licenses\*";           DestDir: "{app}\licenses"; Components: main; Flags: ignoreversion
; manuals: found by Help > User Manual via spectramaster.gui.manual.docs_dir() ({app}\docs)
Source: "..\docs\SpectraMaster_User_Manual_EN.pdf"; DestDir: "{app}\docs"; Components: manuals; Flags: ignoreversion
Source: "..\docs\SpectraMaster_User_Manual_AR.pdf"; DestDir: "{app}\docs"; Components: manuals; Flags: ignoreversion
Source: "Samples\*"; DestDir: "{app}\Samples"; Components: samples; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; files of an older build that the new one no longer contains (keeps _internal consistent on upgrade)
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\cli\_internal"

[Icons]
Name: "{group}\{#AppName}";            Filename: "{app}\{#AppExe}"; AppUserModelID: "{#AppUserModel}"; Comment: "{cm:AppDescription}"
Name: "{group}\{cm:ManualEN}";         Filename: "{app}\docs\SpectraMaster_User_Manual_EN.pdf"; Components: manuals
Name: "{group}\{cm:ManualAR}";         Filename: "{app}\docs\SpectraMaster_User_Manual_AR.pdf"; Components: manuals
Name: "{group}\{cm:ReleaseNotes}";     Filename: "{app}\RELEASE_NOTES_en.txt"; Languages: english
Name: "{group}\{cm:ReleaseNotes}";     Filename: "{app}\RELEASE_NOTES_ar.txt"; Languages: arabic
Name: "{group}\{cm:SampleSpectra}";    Filename: "{app}\Samples"; Components: samples
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";      Filename: "{app}\{#AppExe}"; AppUserModelID: "{#AppUserModel}"; Comment: "{cm:AppDescription}"; Tasks: desktopicon

[Registry]
; ---- ProgID SpectraMaster.Spectrum (ours alone -> the whole key is removed on uninstall)
Root: HKA; Subkey: "Software\Classes\{#ProgID}"; ValueType: string; ValueName: ""; ValueData: "{cm:ProgIdName}"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\{#ProgID}"; ValueType: string; ValueName: "FriendlyTypeName"; ValueData: "{cm:ProgIdName}"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\{#ProgID}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"",0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\{#ProgID}\shell"; ValueType: string; ValueName: ""; ValueData: "open"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\{#ProgID}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assoc
; ---- Applications\SpectraMaster.exe ("Open with" list entry; ours alone)
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"",0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assoc
; ---- Default Apps (Settings > Apps > Default apps) registration
Root: HKA; Subkey: "Software\{#AppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\{#AppName}\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#AppName}"; Tasks: assoc
Root: HKA; Subkey: "Software\{#AppName}\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "{cm:AppDescription}"; Tasks: assoc
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#AppName}"; ValueData: "Software\{#AppName}\Capabilities"; Flags: uninsdeletevalue; Tasks: assoc
; ---- per extension: OpenWithProgids + SupportedTypes + Capabilities (only OUR value names are
;      removed on uninstall; the extension key itself only if nothing else is left in it).
;      The extension's default value (= which program opens it) is set / restored in [Code].
#sub EmitExtRegistry
Root: HKA; Subkey: "Software\Classes\.{#Exts[I]}"; Flags: uninsdeletekeyifempty; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.{#Exts[I]}\OpenWithProgids"; ValueType: string; ValueName: "{#ProgID}"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".{#Exts[I]}"; ValueData: ""; Tasks: assoc
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".{#Exts[I]}"; ValueData: "{#ProgID}"; Tasks: assoc
#endsub
#for {I = 0; I < ExtCount; I++} EmitExtRegistry
; ---- App Paths: "SpectraMaster" works in Win+R and from any command prompt
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#AppExe}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#AppExe}"; ValueType: string; ValueName: "Path"; ValueData: "{app}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\RELEASE_NOTES_en.txt"; Description: "{cm:ViewReleaseNotes}"; Flags: postinstall shellexec skipifsilent nowait unchecked; Languages: english
Filename: "{app}\RELEASE_NOTES_ar.txt"; Description: "{cm:ViewReleaseNotes}"; Flags: postinstall shellexec skipifsilent nowait unchecked; Languages: arabic

[Code]
const
  ProgID = '{#ProgID}';
  BackupValue = 'SpectraMaster.PreviousProgID';
  EnvKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';
  StateKey = 'Software\{#AppName}\Installer';
  PathValue = 'AddedToPath';

var
  ExtList: TArrayOfString;
  DeleteUserData: Boolean;

procedure InitExtList;
begin
  { keep in sync with Exts[] at the top of this script }
  SetArrayLength(ExtList, 7);
  ExtList[0] := 's0';
  ExtList[1] := 'chn';
  ExtList[2] := 'cnf';
  ExtList[3] := 'spe';
  ExtList[4] := 'spc';
  ExtList[5] := 'iec';
  ExtList[6] := 'n42';
end;

{ ------------------------------------------------------------------ PATH (system) }

function NormDir(S: String): String;
begin
  Result := Trim(S);
  StringChangeEx(Result, '"', '', True);
  while (Length(Result) > 3) and (Result[Length(Result)] = '\') do
    SetLength(Result, Length(Result) - 1);
  Result := Lowercase(Result);
end;

{ Splits the PATH value at ';' and returns it without the entries equal to Dir.
  Found = True if at least one entry was dropped. Other entries are kept byte for byte. }
function PathWithout(Path, Dir: String; var Found: Boolean): String;
var
  Rest, Item, Target: String;
  P: Integer;
begin
  Result := '';
  Found := False;
  Target := NormDir(Dir);
  Rest := Path;
  while True do
  begin
    P := Pos(';', Rest);
    if P > 0 then
    begin
      Item := Copy(Rest, 1, P - 1);
      Delete(Rest, 1, P);
    end else
      Item := Rest;
    if (Target <> '') and (NormDir(Item) = Target) then
      Found := True
    else if (Item <> '') or (P > 0) then
    begin
      if Result <> '' then Result := Result + ';';
      Result := Result + Item;
    end;
    if P = 0 then Break;
  end;
end;

procedure AddToPath(Dir: String);
var
  Path: String;
  Found: Boolean;
begin
  if not RegQueryStringValue(HKLM, EnvKey, 'Path', Path) then Path := '';
  PathWithout(Path, Dir, Found);
  if not Found then
  begin
    if (Path <> '') and (Path[Length(Path)] <> ';') then Path := Path + ';';
    Path := Path + Dir;
    if RegWriteExpandStringValue(HKLM, EnvKey, 'Path', Path) then
      Log('PATH: added ' + Dir)
    else
      Log('PATH: could not add ' + Dir);
  end else
    Log('PATH: already contains ' + Dir);
  { remember that the entry is ours, so that only it is removed again }
  RegWriteStringValue(HKLM, StateKey, PathValue, Dir);
end;

procedure RemoveOurPathEntry;
var
  Path, Dir, NewPath: String;
  Found: Boolean;
begin
  if not RegQueryStringValue(HKLM, StateKey, PathValue, Dir) then Exit;
  if RegQueryStringValue(HKLM, EnvKey, 'Path', Path) then
  begin
    NewPath := PathWithout(Path, Dir, Found);
    if Found then
    begin
      RegWriteExpandStringValue(HKLM, EnvKey, 'Path', NewPath);
      Log('PATH: removed ' + Dir);
    end;
  end;
  RegDeleteValue(HKLM, StateKey, PathValue);
end;

{ ------------------------------------------------------------------ default program per extension }

{ Makes SpectraMaster the default program for .Ext, remembering the previous ProgID. }
procedure ClaimExtension(Ext: String);
var
  Key, Prev: String;
begin
  Key := 'Software\Classes\.' + Ext;
  if RegQueryStringValue(HKA, Key, '', Prev) and (Prev <> '') and (Prev <> ProgID) then
    RegWriteStringValue(HKA, Key, BackupValue, Prev);
  RegWriteStringValue(HKA, Key, '', ProgID);
end;

{ Undoes ClaimExtension, but only if the extension still points to us (never touches an
  association that another program has taken over in the meantime). }
procedure ReleaseExtension(Ext: String);
var
  Key, Cur, Prev: String;
begin
  Key := 'Software\Classes\.' + Ext;
  if RegQueryStringValue(HKA, Key, '', Cur) and (Cur = ProgID) then
  begin
    if RegQueryStringValue(HKA, Key, BackupValue, Prev) and (Prev <> '') and
       RegKeyExists(HKA, 'Software\Classes\' + Prev) then
      RegWriteStringValue(HKA, Key, '', Prev)
    else
      RegDeleteValue(HKA, Key, '');
  end;
  RegDeleteValue(HKA, Key, BackupValue);
end;

procedure ApplyAssociations;
var
  I: Integer;
begin
  for I := 0 to GetArrayLength(ExtList) - 1 do
    if WizardIsTaskSelected('assoc\' + ExtList[I]) then
      ClaimExtension(ExtList[I])
    else
      ReleaseExtension(ExtList[I]);   { re-install with the task switched off }
end;

procedure ReleaseAllExtensions;
var
  I: Integer;
begin
  for I := 0 to GetArrayLength(ExtList) - 1 do
    ReleaseExtension(ExtList[I]);
end;

{ ------------------------------------------------------------------ setup events }

function InitializeSetup(): Boolean;
begin
  InitExtList;
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    ApplyAssociations;
    if WizardIsComponentSelected('cli') and WizardIsTaskSelected('clipath') then
      AddToPath(ExpandConstant('{app}\cli'))
    else
      RemoveOurPathEntry;             { re-install without the PATH task / without smconvert }
  end;
end;

{ ------------------------------------------------------------------ uninstall events }

function InitializeUninstall(): Boolean;
begin
  InitExtList;
  DeleteUserData := False;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  DataDir := ExpandConstant('{userappdata}\{#AppName}');
  if CurUninstallStep = usUninstall then
  begin
    { ask first (default button = No = keep the data); silent uninstalls always keep it }
    DeleteUserData := SuppressibleMsgBox(FmtMessage(CustomMessage('AskDeleteData'), [DataDir]),
                                         mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES;
    ReleaseAllExtensions;
    RemoveOurPathEntry;
  end
  else if CurUninstallStep = usPostUninstall then
  begin
    if DeleteUserData then
    begin
      if DirExists(DataDir) then
        DelTree(DataDir, True, True, True);
      RegDeleteKeyIncludingSubkeys(HKCU, 'Software\{#AppName}');
    end;
  end;
end;

