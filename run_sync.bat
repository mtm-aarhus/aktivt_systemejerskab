@echo off
REM Nattekørsel — KITOS til SharePoint synkronisering
REM Registreres i Windows Task Scheduler (se data/SharePoint_Lister_Setup.md)

set PROJECT_DIR=C:\Users\azmda0l\Source\Aktivtsystem_ejerskab

cd /d "%PROJECT_DIR%"

REM Aktiver Python virtual environment
call "%PROJECT_DIR%\venv\Scripts\activate.bat"

REM Kør synkronisering — output logges til logs\sync.log
python -m src.main >> "%PROJECT_DIR%\logs\sync.log" 2>&1

REM Deaktivér venv
call deactivate

exit /b %ERRORLEVEL%
