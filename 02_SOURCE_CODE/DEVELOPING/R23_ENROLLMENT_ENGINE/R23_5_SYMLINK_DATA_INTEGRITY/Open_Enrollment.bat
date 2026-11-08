@echo off
cd /d "%~dp0"
py -c "import tkinter; root=tkinter.Tk(); root.update(); root.destroy(); print('TK_WINDOW_OK')"
if errorlevel 1 goto missing
py "%~dp0open_launcher.py"
goto end
:missing
echo TK_MISSING. Do not remove the current Python. Write this message on the feedback form and stop.
pause
:end
