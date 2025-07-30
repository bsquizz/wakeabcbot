#!/bin/bash

# Wake ABC Telegram Bot Runner Script
# This script starts the bot with proper error handling and logging

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Wake ABC Telegram Bot${NC}"
echo "=========================="

# Check if Python 3.12+ is available
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.12"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}Error: Python 3.12 or higher is required. Found: $python_version${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. Please copy .env.example to .env and configure it.${NC}"
    echo "cp .env.example .env"
    exit 1
fi

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}Error: Poetry is not installed. Please install Poetry first:${NC}"
    echo "curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

# Install/update dependencies
echo -e "${GREEN}Installing dependencies with Poetry...${NC}"
poetry install

# Run the bot
echo -e "${GREEN}Starting Wake ABC Telegram Bot...${NC}"
echo "Press Ctrl+C to stop the bot"
echo ""

poetry run python run.py
