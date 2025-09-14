# Discord Ticket Bot

A comprehensive Discord bot for managing support tickets with dynamic ticket types, SLA management, and automated notifications.

## Features

- 🎫 **Dynamic Ticket Types**: Create and manage different ticket types without programming
- ⏰ **SLA Management**: Set custom SLA times for each ticket type
- 📱 **DM Notifications**: Receive direct messages when SLA deadlines are approaching
- 🎯 **Ticket Assignment**: Staff can assign tickets to themselves
- 👥 **User Management**: Add users to ticket channels
- 📊 **Statistics**: View comprehensive ticket statistics
- 🔒 **Auto-archiving**: Automatic ticket archiving when closed
- 💾 **Audit Trail**: Complete message history for each ticket

## Setup Instructions

### 1. Prerequisites
- Python 3.8 or higher
- A Discord bot token
- Administrator permissions in your Discord server

### 2. Installation

1. Clone or download this repository
2. Navigate to the `ticket-bot` directory
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```

2. Edit the `.env` file with your configuration:
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   GUILD_ID=your_guild_id_here
   ADMIN_USER_ID=your_user_id_here
   DATABASE_PATH=./data/tickets.db
   LOG_LEVEL=INFO
   LOG_FILE=./logs/bot.log
   ```

### 4. Getting Required IDs

#### Discord Bot Token:
1. Go to https://discord.com/developers/applications
2. Create a new application or select an existing one
3. Go to the "Bot" section
4. Copy the token

#### Guild ID:
1. Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
2. Right-click your server name
3. Click "Copy Server ID"

#### Your User ID:
1. In Discord, right-click your username
2. Click "Copy User ID"

### 5. Bot Permissions

Your bot needs the following permissions:
- Read Messages
- Send Messages
- Manage Channels
- Manage Roles
- Embed Links
- Use Slash Commands

Invite URL template:
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=268528656&scope=bot%20applications.commands
```

### 6. Running the Bot

```bash
python bot.py
```

## Usage

### Admin Commands

#### Create Ticket Types
```
/create_ticket_type name:"Bug Report" description:"Report bugs and issues" sla_hours:24 color:"ff0000" emoji:"🐛"
```

#### Setup Ticket Panel
```
/setup_ticket_panel channel:#support
```

#### Manage Ticket Types
```
/list_ticket_types
/delete_ticket_type name:"Bug Report"
```

#### View Statistics
```
/ticket_stats
/list_open_tickets
```

### User Commands

#### Create Tickets
```
/create_ticket
```

Or use the ticket panel setup by administrators.

### Ticket Management

Once a ticket is created, users and staff can:
- **Close tickets**: Using the "Close Ticket" button
- **Assign tickets**: Staff can assign tickets to themselves
- **Add users**: Staff can add additional users to ticket channels

## File Structure

```
ticket-bot/
├── bot.py              # Main bot file
├── database.py         # Database management
├── views.py           # Discord UI components
├── requirements.txt   # Python dependencies
├── .env.example      # Environment template
├── .gitignore        # Git ignore rules
└── README.md         # This file
```

## Database Schema

The bot uses SQLite with the following tables:
- `ticket_types`: Stores ticket type configurations
- `tickets`: Stores ticket information
- `ticket_messages`: Stores audit trail messages

## SLA Monitoring

The bot automatically:
- Monitors ticket SLA deadlines every 30 minutes
- Sends DM notifications to the admin 2 hours before deadline
- Tracks which tickets have been notified to avoid spam

## Customization

### Adding New Ticket Types
Use the `/create_ticket_type` command with these parameters:
- **name**: Unique name for the ticket type
- **description**: Description shown to users
- **sla_hours**: Hours until SLA deadline
- **color**: Hex color code (without #)
- **emoji**: Emoji to represent the ticket type

### Modifying SLA Alert Timing
Edit the `sla_monitor` task in `bot.py`:
- Change the `@tasks.loop(minutes=30)` for check frequency
- Modify `hours_before=2` in `get_tickets_near_sla()` for alert timing

## Troubleshooting

### Common Issues

1. **Bot not responding to commands**
   - Check bot permissions
   - Verify token is correct
   - Check console for error messages

2. **Database errors**
   - Ensure the `data` directory exists
   - Check file permissions

3. **SLA notifications not working**
   - Verify `ADMIN_USER_ID` is correct
   - Check bot can send DMs to the admin

### Logging

Logs are saved to the file specified in `LOG_FILE` (default: `./logs/bot.log`).
Check logs for detailed error information.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

If you need help setting up or using the bot:
1. Check this README
2. Review the logs for errors
3. Create an issue on the repository
