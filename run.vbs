Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = appDir
WshShell.Environment("Process")("PYTHONPATH") = ""

WshShell.Run """" & appDir & "\venv\Scripts\pythonw.exe"" main.py", 0, False

Set WshShell = Nothing
Set fso = Nothing
