' AI Office Silent Launcher (Zero CMD/Terminal Window)
Option Explicit

Dim oShell, fso, strDir, pythonwPath, launcherPath

Set oShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDir = fso.GetParentFolderName(WScript.ScriptFullName)
oShell.CurrentDirectory = strDir

launcherPath = strDir & "\app\launcher.py"

' Priority 1: Project virtual environment pythonw
If fso.FileExists(strDir & "\.venv\Scripts\pythonw.exe") Then
    pythonwPath = strDir & "\.venv\Scripts\pythonw.exe"
' Priority 2: System Python 3.13 / 3.12 in LocalAppData
ElseIf fso.FileExists(oShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python313\pythonw.exe") Then
    pythonwPath = oShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python313\pythonw.exe"
ElseIf fso.FileExists(oShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe") Then
    pythonwPath = oShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe"
' Priority 3: Fallback to PATH pythonw
Else
    pythonwPath = "pythonw.exe"
End If

' Run completely hidden (0 = vbHide, False = don't wait for return)
On Error Resume Next
oShell.Run Chr(34) & pythonwPath & Chr(34) & " " & Chr(34) & launcherPath & Chr(34), 0, False
If Err.Number <> 0 Then
    MsgBox "Không thể khởi động AI Office. Vui lòng kiểm tra Python hoặc môi trường ảo (.venv). Lỗi: " & Err.Description, 16, "AI Office"
End If
