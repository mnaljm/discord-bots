@echo off
echo Setting up Discord Ticket Bot...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3.8 or higher from https://python.org
    pause
    exit /b 1
)

echo Python found!
echo.

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo Error: Failed to create virtual environment.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error: Failed to install dependencies.
    pause
    exit /b 1
)

REM Create necessary directories
echo Creating directories...
if not exist "data" mkdir data
if not exist "logs" mkdir logs

REM Copy environment file
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
    echo.
    echo Please edit the .env file with your bot configuration!
    echo You need to add:
    echo - DISCORD_TOKEN
    echo - GUILD_ID
    echo - ADMIN_USER_ID
    echo.
) else (
    echo .env file already exists.
)

echo.
echo Setup complete!
echo.
echo Next steps:
echo 1. Edit the .env file with your bot configuration
echo 2. Run: venv\Scripts\activate.bat
echo 3. Run: python bot.py
echo.
pause
