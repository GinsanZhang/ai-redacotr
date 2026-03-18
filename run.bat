@echo off
chcp 65001 >nul
echo ==========================================
echo Screenshot Redactor - Cloud Vision Mode
echo ==========================================
echo.

echo [1/1] Starting program (UTF-8 mode)...
echo ==========================================
echo.

set PYTHONUTF8=1
"D:\ProgramData\anaconda3\python.exe" -u "D:\ai\aishortcut\redactor.py"

echo.
pause
