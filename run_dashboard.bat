@echo off
title VEIL -- Ownership Intelligence
echo Starting VEIL -- Ownership Intelligence Dashboard...
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python virtual environment not found at .venv\Scripts\python.exe
    echo Create it with: python -m venv .venv
    pause
    exit /b 1
)

if not exist ".env" (
    echo ERROR: .env file is missing from the project root.
    echo The dashboard needs COMPANIES_HOUSE_API_KEY, NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD.
    echo Restore your .env file or create one from your saved credentials, then run this again.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run dashboard/app.py
pause
