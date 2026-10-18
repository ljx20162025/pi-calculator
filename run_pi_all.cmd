@echo off
setlocal
REM ---------------------------------------------------------------
REM Double-click launcher for pi_all.py (interactive menu version)
REM ASCII only + CRLF + absolute paths (Windows cmd safe)
REM Uses "pause > nul" with an English prompt so that no console
REM codepage (GBK / UTF-8) can garble the "press any key" message.
REM Extra args are forwarded:  run_pi_all.cmd 1 1000
REM ---------------------------------------------------------------
set "PY=C:\Users\lujinxian\.mPython\python3.8.10\python.exe"

if not exist "%PY%" (
  echo.
  echo [ERROR] Python executable not found:
  echo   %PY%
  echo.
  echo Press any key to close . . .
  pause > nul
  exit /b 1
)

if not exist "%~dp0pi_all.py" (
  echo.
  echo [ERROR] pi_all.py not found next to this script:
  echo   %~dp0pi_all.py
  echo.
  echo Press any key to close . . .
  pause > nul
  exit /b 1
)

"%PY%" "%~dp0pi_all.py" %*
set RC=%ERRORLEVEL%

if not "%RC%"=="0" (
  echo.
  echo [ERROR] Python exited with code %RC%
  echo.
  echo Press any key to close . . .
  pause > nul
  exit /b %RC%
)

echo.
echo Press any key to close . . .
pause > nul
endlocal
