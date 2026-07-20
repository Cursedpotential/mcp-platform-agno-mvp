@echo off
REM oc — thin Windows wrapper around oc.py (uv-managed python)
REM Byline: Claude Code - Sonnet - 2026-07-20
setlocal
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%oc.py" %*
endlocal
