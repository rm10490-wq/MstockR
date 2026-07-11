@echo off
REM ============================================================
REM  Signal Desk - stop the servers
REM  NOTE: this stops ALL python.exe and node.exe processes on
REM  this machine, not just Signal Desk's. If you run other
REM  Python/Node apps, close the two "Signal Desk" windows
REM  manually instead of using this script.
REM ============================================================

echo Stopping Signal Desk servers...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM node.exe   >nul 2>&1
echo Done.
timeout /t 2 >nul
