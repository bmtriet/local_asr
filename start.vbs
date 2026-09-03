' Local ASR Windows Silent Background Launcher (No CMD popup)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

PythonwPath = ScriptDir & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(PythonwPath) Then
    PythonwPath = "pythonw.exe"
End If

Cmd = """" & PythonwPath & """ """ & ScriptDir & "\main.py"" --service all"

' 0 = Hide window completely, False = continue execution without blocking
WshShell.CurrentDirectory = ScriptDir
WshShell.Run Cmd, 0, False
