' AI Office Silent Launcher (Zero CMD/Terminal Window)
Set oShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDir = fso.GetParentFolderName(WScript.ScriptFullName)
oShell.CurrentDirectory = strDir

pythonwPath = strDir & "\.venv\Scripts\pythonw.exe"
launcherPath = strDir & "\app\launcher.py"

If fso.FileExists(pythonwPath) Then
    ' Run completely hidden (0 = vbHide, False = don't wait)
    oShell.Run Chr(34) & pythonwPath & Chr(34) & " " & Chr(34) & launcherPath & Chr(34), 0, False
Else
    MsgBox "Môi trường AI Office (.venv) chưa được cài đặt. Vui lòng kiểm tra lại thư mục.", 16, "AI Office"
End If
