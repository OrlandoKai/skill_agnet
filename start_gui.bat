@echo off
title Skill Agent Baseline GUI
cd /d D:\123pan\back\workbench\Agent-skill\skill_agent_baseline

if not exist ".\.venv\Scripts\python.exe" (
    echo [ERROR] Cannot find .venv\Scripts\python.exe
    echo Please create the virtual environment and install dependencies first.
    pause
    exit /b 1
)

echo Starting Skill Agent Baseline GUI...
echo.
echo If the browser does not open automatically, visit:
echo http://127.0.0.1:8501
echo.

.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.fileWatcherType none

echo.
echo Streamlit has stopped. Check the messages above for errors.
pause
