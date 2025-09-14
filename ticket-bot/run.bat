@echo off
echo Starting Discord Ticket Bot...
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found!
    echo Please run setup.bat first.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if .env file exists
if not exist ".env" (
    echo Error: .env file not found!
    echo Please copy .env.example to .env and configure it.
    pause
    exit /b 1
)

REM Create directories if they don't exist
if not exist "data" mkdir data
if not exist "logs" mkdir logs

REM Start the bot
echo Starting bot...
python bot.py

pause
