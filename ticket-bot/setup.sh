#!/bin/bash

echo "Setting up Discord Ticket Bot..."
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    echo "Please install Python 3.8 or higher."
    exit 1
fi

echo "Python found!"
echo

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment."
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies."
    exit 1
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p data
mkdir -p logs

# Copy environment file
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo
    echo "Please edit the .env file with your bot configuration!"
    echo "You need to add:"
    echo "- DISCORD_TOKEN"
    echo "- GUILD_ID"
    echo "- ADMIN_USER_ID"
    echo
else
    echo ".env file already exists."
fi

echo
echo "Setup complete!"
echo
echo "Next steps:"
echo "1. Edit the .env file with your bot configuration"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python bot.py"
echo
