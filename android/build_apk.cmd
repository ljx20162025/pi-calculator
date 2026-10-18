@echo off
setlocal
REM ---------------------------------------------------------------
REM Build an Android APK from main.py using Buildozer inside Docker.
REM
REM REQUIREMENT: Docker Desktop must be running first.
REM   Start "Docker Desktop" from Start menu, wait until the whale
REM   icon in the tray reports "Docker Desktop running",
REM   then double-click this file.
REM
REM The very first build downloads the Android SDK + NDK (~3-5 GB)
REM and typically takes 20-60 minutes. Later builds are much
REM faster because the toolchain is cached in .buildozer/.
REM ASCII only + CRLF, absolute-path safe.
REM ---------------------------------------------------------------
set "IMAGE=kivy/buildozer"
cd /d "%~dp0"

echo.
echo === 1/3 Checking Docker daemon ===
docker info >nul 2>&1
if errorlevel 1 (
  echo.
  echo [ERROR] Docker daemon is not running.
  echo.
  echo Please start Docker Desktop, wait until it reports
  echo "Docker Desktop running", then run this script again.
  echo.
  pause
  exit /b 1
)
echo     Docker is up.

echo.
echo === 2/3 Pulling %IMAGE% ===
echo     First time this may take several minutes.
docker pull %IMAGE%
if errorlevel 1 (
  echo.
  echo [ERROR] Failed to pull image %IMAGE%
  echo.
  pause
  exit /b 1
)

echo.
echo === 3/3 Building APK ===
echo     Output will appear in: %cd%\bin
echo.
docker run --rm -v "%cd%:/home/user/hostcwd" %IMAGE% -v android debug
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
  echo [OK] Build succeeded. The APK is in:
  echo      %cd%\bin
) else (
  echo [ERROR] Build failed with code %RC%
  echo Read the log above; the real cause is usually near the end.
)
echo.
pause
endlocal
