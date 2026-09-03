' Local ASR Windows Silent Background Launcher (No CMD popup)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

PythonwPath = ScriptDir & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(PythonwPath) Then
    MsgBox "Loi: Khong tim thay moi truong ao .venv!" & vbCrLf & vbCrLf & _
           "Vui long chay tep 'setup_windows.bat' truoc de cai dat he thong.", _
           vbCritical, "Local ASR Error"
    WScript.Quit 1
End If

Cmd = """" & PythonwPath & """ """ & ScriptDir & "\main.py"" --service all"

' 0 = Hide window completely, False = continue execution without blocking
WshShell.CurrentDirectory = ScriptDir
WshShell.Run Cmd, 0, False
