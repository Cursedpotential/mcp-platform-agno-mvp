@echo off
REM grc — thin Windows wrapper around grc.py (uv-managed python)
REM Byline: Claude Code - Sonnet - 2026-07-19
setlocal
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%grc.py" %*
endlocal
