@echo off
REM ============================================================
REM  Signal Desk - one-click launcher
REM  Double-click this file to start the backend + frontend
REM  and open the dashboard in your browser.
REM ============================================================

set "ROOT=%~dp0"

REM --- MySQL password enables auto-persistence to the 'stockdash' database.
REM     Edit it here if your MySQL root password changes.
REM     (Leave it blank to run without writing to MySQL.)
set "MYSQL_PASSWORD=Rahul@123"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"

echo.
echo   Starting Signal Desk...
echo   - Backend  (FastAPI)  http://127.0.0.1:8000
echo   - Frontend (Vite)     http://localhost:5173
echo.

REM Each server opens in its own window (close the window to stop that server).
start "Signal Desk - Backend"  /D "%ROOT%backend"  cmd /k python -m uvicorn main:app --host 127.0.0.1 --port 8000
start "Signal Desk - Frontend" /D "%ROOT%frontend" cmd /k npm run dev

echo   Waiting for the servers to come up...
timeout /t 7 /nobreak >nul

start "" http://localhost:5173/

echo.
echo   Done. Two terminal windows are now running the servers.
echo   Close those windows (or run stop.bat) to shut everything down.
echo.
timeout /t 4 >nul
