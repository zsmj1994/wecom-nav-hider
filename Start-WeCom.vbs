Option Explicit
Dim fs, shell, folder, python, script
Set fs = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
script = fs.BuildPath(folder, "launch.ps1")
shell.Run "pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & script & Chr(34), 0, False
