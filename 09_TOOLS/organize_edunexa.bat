@echo off
chcp 65001 >nul
echo ========================================
echo   EDUNEXA File Organizer
echo   (CORE + DEVELOPING)
echo ========================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python नहीं मिला।
    pause
    exit /b 1
)

python "%~dp0organize_edunexa.py"

echo.
echo हो गया! EDUNEXA फोल्डर चेक करें।
echo CORE = स्थिर कोड | DEVELOPING = प्रयोग
pause
