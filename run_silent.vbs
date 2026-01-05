' 静默运行Python脚本，不显示终端窗口
Set WshShell = CreateObject("WScript.Shell")

' 获取脚本所在目录
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' 切换到脚本目录并运行Python
WshShell.Run "cmd /c cd /d """ & scriptDir & """ && python plan.py", 0, True

' 参数说明:
' 第二个参数 0 = 隐藏窗口
' 第三个参数 True = 等待执行完成
