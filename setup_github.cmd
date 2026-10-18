@echo off
setlocal
REM ---------------------------------------------------------------
REM Prepare this project as a git repo, push it to GitHub, and
REM then trigger the GitHub Actions Android APK build.
REM
REM Just double-click this file.
REM A browser window may open once for you to authorize GitHub.
REM
REM ASCII only + CRLF, absolute-path safe.
REM
REM IMPORTANT - two traps handled below:
REM
REM  1] Never put bare parentheses inside an "if ( ... )" block.
REM     cmd treats them as block delimiters and the whole script
REM     dies instantly with NO error message. Use brackets instead.
REM
REM  2] On this machine the "git" on PATH is a disabled QClaw shim,
REM     so we must PREPEND the real git directory to PATH. Just
REM     storing the path in a variable is NOT enough: the GitHub
REM     CLI spawns its own "git" and looks it up on PATH.
REM ---------------------------------------------------------------
cd /d "%~dp0"

echo.
echo === 1/5 Locating git.exe ===

set "GIT_EXE=C:\Users\lujinxian\.workbuddy\binaries\PortableGit\versions\1.3.0\cmd\git.exe"
if not exist "%GIT_EXE%" set "GIT_EXE=C:\Program Files\Git\cmd\git.exe"
if not exist "%GIT_EXE%" set "GIT_EXE=C:\Program Files\Git\bin\git.exe"
if not exist "%GIT_EXE%" set "GIT_EXE=git"

"%GIT_EXE%" --version
if errorlevel 1 (
  echo.
  echo [ERROR] git is not usable.
  echo Install Git for Windows from https://git-scm.com/
  echo.
  pause
  exit /b 1
)

REM --- Put the real git first on PATH -------------------------------
REM Get the directory part of GIT_EXE via the ~dp modifier on a
REM "file" style expansion, which works for a plain path string too.
for %%I in ("%GIT_EXE%") do set "GIT_DIR=%%~dpI"
REM Strip the trailing backslash so the PATH entry stays clean.
if "%GIT_DIR:~-1%"=="\" set "GIT_DIR=%GIT_DIR:~0,-1%"

set "PATH=%GIT_DIR%;%PATH%"

echo.
echo     PATH now starts with: %GIT_DIR%
echo     Verifying that plain "git" resolves correctly:
git --version
if errorlevel 1 (
  echo.
  echo [ERROR] "git" still resolves to a broken shim.
  echo.
  pause
  exit /b 1
)

echo.
echo === 2/5 Locating GitHub CLI ===

set "GH_EXE=C:\Program Files\GitHub CLI\gh.exe"
if not exist "%GH_EXE%" set "GH_EXE=%LOCALAPPDATA%\Microsoft\WinGet\Links\gh.exe"
if not exist "%GH_EXE%" set "GH_EXE=%LOCALAPPDATA%\Microsoft\WinGet\Packages\GitHub.cli\gh.exe"
if not exist "%GH_EXE%" set "GH_EXE=gh"

"%GH_EXE%" --version
if errorlevel 1 (
  echo.
  echo GitHub CLI not found. Trying to install it with winget...
  echo - accept any UAC prompt that appears
  echo.
  winget install --id GitHub.cli --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo.
    echo [ERROR] Could not install the GitHub CLI automatically.
    echo Install it manually from https://cli.github.com/
    echo then run this script again.
    echo.
    pause
    exit /b 1
  )
  echo.
  echo GitHub CLI installed.
)

REM Make gh's own directory visible on PATH too, so anything gh
REM spawns can find it the same way we just did for git.
for %%I in ("%GH_EXE%") do set "GH_DIR=%%~dpI"
if "%GH_DIR:~-1%"=="\" set "GH_DIR=%GH_DIR:~0,-1%"
if not "%GH_DIR%"=="" set "PATH=%GH_DIR%;%PATH%"

echo.
echo === 3/5 Sign in to GitHub ===

"%GH_EXE%" auth status
if not errorlevel 1 (
  echo.
  echo     Already signed in - skipping the browser step.
  goto :SIGNED_IN
)

echo A browser window will open - follow the prompts to authorize.
echo A one-time code is printed below; paste it into the browser.
echo.
"%GH_EXE%" auth login --web --git-protocol https
if not errorlevel 1 goto :SIGNED_IN

echo.
echo [WARN] Browser sign-in did not complete.
echo.
echo Alternative: use a Personal Access Token instead.
echo   1. Open https://github.com/settings/tokens
echo   2. Generate a classic token with scopes: repo, workflow
echo   3. Paste it below - the input stays hidden on screen only
echo      in the sense that cmd echoes it, so treat it as private.
echo.
echo Press Enter with an empty line to skip and abort.
echo.
set "GH_TOKEN_INPUT="
set /p GH_TOKEN_INPUT=Paste token here:

if not defined GH_TOKEN_INPUT (
  echo.
  echo [ERROR] GitHub sign-in failed or was cancelled.
  echo.
  pause
  exit /b 1
)

echo %GH_TOKEN_INPUT%| "%GH_EXE%" auth login --with-token
if errorlevel 1 (
  echo.
  echo [ERROR] Token sign-in failed.
  echo Check that the token has the "repo" and "workflow" scopes.
  echo.
  pause
  exit /b 1
)

:SIGNED_IN
REM Capture the account login so we can build the remote URL later.
set "GH_USER="
"%GH_EXE%" api user --jq .login > "%TEMP%\pi_gh_user.txt" 2>nul
if exist "%TEMP%\pi_gh_user.txt" set /p GH_USER=<"%TEMP%\pi_gh_user.txt"
del "%TEMP%\pi_gh_user.txt" >nul 2>&1

echo.
if defined GH_USER (
  echo     Signed in as: %GH_USER%
) else (
  echo     Signed in - but could not read the account name.
)

echo.
echo === 4/5 Git identity - used for the commit message ===
set "GIT_NAME="
set "GIT_EMAIL="
set /p GIT_NAME=Name  :
set /p GIT_EMAIL=Email :
if not defined GIT_NAME set GIT_NAME=Pi Calculator User
if not defined GIT_EMAIL set GIT_EMAIL=noreply@example.com

git config user.name "%GIT_NAME%"
git config user.email "%GIT_EMAIL%"

git add -A
git commit -m "Add Kivy pi calculator - recursive + factorial - for Android build"
if errorlevel 1 (
  echo [WARN] Nothing committed - maybe there was nothing new to record.
)

echo.
echo === 5/5 Create the remote repo and push ===
git branch -M main

"%GH_EXE%" repo view pi-calculator >nul 2>&1
if not errorlevel 1 (
  echo.
  echo     A repo named pi-calculator already exists on your account.
  echo     Adding it as the remote and pushing instead of creating it.
  set "REPO_URL="
  "%GH_EXE%" repo view pi-calculator --json url --jq .url > "%TEMP%\pi_repo_url.txt" 2>nul
  if exist "%TEMP%\pi_repo_url.txt" set /p REPO_URL=<"%TEMP%\pi_repo_url.txt"
  del "%TEMP%\pi_repo_url.txt" >nul 2>&1
  if not defined REPO_URL (
    echo [ERROR] Could not determine the existing repo URL.
    pause
    exit /b 1
  )
  echo     Remote: %REPO_URL%.git
  git remote remove origin >nul 2>&1
  git remote add origin %REPO_URL%.git
  if errorlevel 1 (
    echo.
    echo [ERROR] Could not add the remote.
    echo.
    pause
    exit /b 1
  )
  git push -u origin main
  if errorlevel 1 (
    echo.
    echo [ERROR] Push failed.
    echo.
    pause
    exit /b 1
  )
) else (
  "%GH_EXE%" repo create pi-calculator --public --source=. --remote=origin --push
  if errorlevel 1 (
    echo.
    echo [ERROR] Create or push failed.
    echo.
    pause
    exit /b 1
  )
)

echo.
echo === Triggering the APK build ===
"%GH_EXE%" workflow run build-apk.yml
if errorlevel 1 (
  echo.
  echo [WARN] Could not trigger the build from the CLI.
  echo Open GitHub in a browser, go to the Actions tab,
  echo pick "Build Android APK", then click Run workflow.
) else (
  echo.
  echo     Build queued. It usually takes 20-30 minutes.
  echo     Watch it at: https://github.com/actions
  echo     When it finishes, download the APK from Artifacts.
)

echo.
pause
endlocal
