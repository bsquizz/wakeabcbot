# Wake ABC Inventory Telegram Bot

A Telegram bot that monitors the Wake County ABC inventory and notifies users when their desired alcoholic beverages become available.

## Features

### 🔍 Inventory Search
- Search the Wake County ABC inventory directly from Telegram
- Get detailed information including prices, sizes, and store locations
- Formatted results with emojis for easy reading

### 📝 Watchlist Management
- Add keywords to your personal watchlist
- Get automatic notifications when matching items become available
- Remove items you're no longer interested in

### 🔔 Real-time Notifications
- Periodic monitoring of inventory (every 30 minutes by default)
- Smart notifications that avoid spam (won't notify about the same item repeatedly)
- Detailed availability alerts with store locations

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and setup |
| `/help` | Show all available commands |
| `/search <query>` | Search the ABC inventory |
| `/watchlist` | View your current watchlist |
| `/add <query>` | Add keywords to watchlist |
| `/remove <query>` | Remove keywords from watchlist |
| `/clear` | Clear all entries from watchlist |

## Setup Instructions

### Prerequisites

- Python 3.12 or higher
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management
- A Telegram Bot Token (get one from [@BotFather](https://t.me/botfather))

### Installation

1. **Clone the repository:**
   ```bash
   git clone git@github.com:bsquizz/wakeabcbot.git
   cd wakeabcbot
   ```

2. **Install Poetry** (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. **Install dependencies:**
   ```bash
   poetry install
   ```

4. **Set up environment variables:**
   ```bash
   cp env.example .env
   ```

   Edit `.env` and add your bot token:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ```

5. **Test your setup (optional but recommended):**
   ```bash
   poetry run python test_setup.py
   ```

6. **Run the bot:**
   ```bash
   poetry run python run.py
   ```

## Usage Examples

### Searching for Items
```
/search whiskey
/search buffalo trace
/search tito's vodka
```

### Managing Your Watchlist
```
# Add items to watch
/add bourbon
/add "pappy van winkle"
/add hennessy

# View your watchlist
/watchlist

# Remove items
/remove bourbon
/remove vodka

# Remove all items
/clear
```

### Getting Notifications
Once you add items to your watchlist, the bot will automatically:
1. Check the inventory every 30 minutes (configurable)
2. Send you notifications when changes occur for matching items:
   - Item switches from out-of-stock to in-stock
   - Item becomes in-stock at a new store
   - Item's price drops
   - Inventory is getting very low (less than 10 items total across all stores)
   - Item goes out of stock
3. Include store locations and pricing information
4. Avoid duplicate notifications for the same items

## Architecture

### Database Schema

The bot uses SQLite with the following tables:

- **`users`** - User information and preferences
- **`watchlist`** - User watchlist keywords
- **`notifications`** - Notification history

### Monitoring System

The monitoring system:
1. Runs continuously in the background
2. Checks all unique watchlist keywords periodically
3. Compares results with previous notifications
4. Sends formatted notifications to relevant users
5. Records notifications to prevent duplicates

## Development

### Development Setup

```bash
# Clone and setup
git clone git@github.com:bsquizz/wakeabcbot.git
cd wakeabcbot
poetry install --all-groups

# Activate the virtual environment
poetry shell

# Or run commands with poetry run
poetry run python test_setup.py
```

### Running Components Separately

You can run individual components for testing:

```bash
# Run only the bot (no monitoring)
poetry run python -c "from wakeabcbot.bot import WakeABCBot; import asyncio; asyncio.run(WakeABCBot().run())"

# Run only the monitoring service
poetry run python -c "from wakeabcbot.monitor import MonitoringService; import asyncio; asyncio.run(MonitoringService().run())"
```

### Testing

To test the notification system, use the provided test script:

```bash
# Test the notification system (replace with your actual user ID)
poetry run python test_notification.py YOUR_USER_ID

# Example:
poetry run python test_notification.py 123456789
```

The test script will:
- Load your bot token from the `.env` file
- Send a test notification to the specified user ID

## Deployment


### Docker Deployment

The project includes `Dockerfile` and `docker-compose.yml` files for easy containerized deployment.

#### Using Docker Compose

1. **Set up environment variables:**
   ```bash
   cp env.example .env
   # Edit .env with your bot token
   ```

2. **Create data directory:**
   ```bash
   mkdir -p data
   ```

3. **Build and run:**
   ```bash
   docker compose up -d
   ```

#### Using Docker directly

```bash
# Build the image
docker build -t wakeabcbot:latest .

# Create directory for data volume
mkdir -p ./data

# Run the container
docker run -d \
  --name wakeabcbot \
  -e TELEGRAM_BOT_TOKEN=your_token_here \
  -e DATABASE_PATH=/app/data/wakeabcbot.db \
  -v ./data:/app/data \
  --restart unless-stopped \
  wakeabcbot
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This bot is not affiliated with Wake County ABC. It's an unofficial tool created to help customers find available products. Please respect the ABC website's terms of service and use the bot responsibly.
