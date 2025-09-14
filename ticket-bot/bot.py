import discord
from discord.ext import commands, tasks
import asyncio
import logging
import os
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv

from database import DatabaseManager
from views import TicketTypeView, TicketControlView

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv('LOG_FILE', 'bot.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class TicketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.db = DatabaseManager(os.getenv('DATABASE_PATH', './data/tickets.db'))
        self.admin_user_id = int(os.getenv('ADMIN_USER_ID', 0))
    
    async def setup_hook(self):
        """Setup hook called when bot is starting"""
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db.db_path), exist_ok=True)
        
        # Initialize database
        await self.db.initialize()
        
        # Define persistent views
        class TicketPanelView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
            
            @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="create_ticket_panel")
            async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                bot = interaction.client
                ticket_types = await bot.db.get_ticket_types()
                
                if not ticket_types:
                    await interaction.response.send_message("❌ No ticket types available! Contact an admin.", ephemeral=True)
                    return
                
                view = TicketTypeView(ticket_types)
                
                embed = discord.Embed(
                    title="🎫 Create Support Ticket",
                    description="Please select the type of ticket you want to create:",
                    color=0x3447003
                )
                
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        # Add persistent views for existing tickets
        self.add_view(TicketControlView())  # For ticket control buttons
        self.add_view(TicketPanelView())    # For ticket creation panels
        
        # Start SLA monitoring task
        self.sla_monitor.start()
        
        logger.info("Bot setup completed")
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    @tasks.loop(minutes=30)  # Check every 30 minutes
    async def sla_monitor(self):
        """Monitor SLA deadlines and send notifications"""
        try:
            # Get tickets approaching SLA deadline (within 2 hours)
            tickets = await self.db.get_tickets_near_sla(hours_before=2)
            
            for ticket in tickets:
                # Send DM to admin
                if self.admin_user_id:
                    try:
                        admin_user = await self.fetch_user(self.admin_user_id)
                        
                        embed = discord.Embed(
                            title="⚠️ SLA Alert",
                            description=f"Ticket #{ticket['ticket_number']} is approaching its SLA deadline!",
                            color=0xff9900,
                            timestamp=datetime.fromisoformat(ticket['sla_deadline'])
                        )
                        embed.add_field(name="Title", value=ticket['title'], inline=False)
                        embed.add_field(name="Type", value=ticket['type_name'], inline=True)
                        embed.add_field(name="Creator", value=f"<@{ticket['creator_id']}>", inline=True)
                        embed.add_field(name="Channel", value=f"<#{ticket['channel_id']}>", inline=True)
                        embed.set_footer(text=f"Ticket ID: {ticket['id']}")
                        
                        await admin_user.send(embed=embed)
                        
                        # Mark as notified
                        await self.db.mark_sla_notified(ticket['id'])
                        
                        logger.info(f"SLA alert sent for ticket {ticket['ticket_number']}")
                        
                    except Exception as e:
                        logger.error(f"Failed to send SLA alert for ticket {ticket['ticket_number']}: {e}")
        
        except Exception as e:
            logger.error(f"Error in SLA monitor: {e}")
    
    @sla_monitor.before_loop
    async def before_sla_monitor(self):
        """Wait until bot is ready before starting SLA monitor"""
        await self.wait_until_ready()

# Initialize bot
bot = TicketBot()

@bot.tree.command(name="create_ticket_type", description="Create a new ticket type (Admin only)")
async def create_ticket_type(interaction: discord.Interaction, 
                           name: str, 
                           description: str, 
                           sla_hours: int,
                           color: str = "3447003",
                           emoji: str = "🎫"):
    """Create a new ticket type"""
    
    # Check if user is admin
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can create ticket types!", ephemeral=True)
        return
    
    try:
        # Convert color hex to int
        color_int = int(color, 16) if isinstance(color, str) else color
    except ValueError:
        color_int = 3447003  # Default blue
    
    success = await bot.db.create_ticket_type(name, description, sla_hours, color_int, emoji)
    
    if success:
        embed = discord.Embed(
            title="✅ Ticket Type Created",
            description=f"**{emoji} {name}** has been created successfully!",
            color=color_int
        )
        embed.add_field(name="Description", value=description, inline=False)
        embed.add_field(name="SLA Hours", value=f"{sla_hours} hours", inline=True)
        embed.add_field(name="Color", value=f"#{color}", inline=True)
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"Ticket type '{name}' created by {interaction.user}")
    else:
        await interaction.response.send_message(f"❌ Ticket type '{name}' already exists!", ephemeral=True)

@bot.tree.command(name="list_ticket_types", description="List all ticket types")
async def list_ticket_types(interaction: discord.Interaction):
    """List all available ticket types"""
    
    ticket_types = await bot.db.get_ticket_types()
    
    if not ticket_types:
        await interaction.response.send_message("❌ No ticket types found! Ask an admin to create some.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🎫 Available Ticket Types",
        description="Here are all the available ticket types:",
        color=0x3447003
    )
    
    for ticket_type in ticket_types:
        embed.add_field(
            name=f"{ticket_type['emoji']} {ticket_type['name']}",
            value=f"{ticket_type['description']}\n⏰ SLA: {ticket_type['sla_hours']} hours",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="create_ticket", description="Create a new support ticket")
async def create_ticket(interaction: discord.Interaction):
    """Create a new support ticket"""
    
    ticket_types = await bot.db.get_ticket_types()
    
    if not ticket_types:
        await interaction.response.send_message("❌ No ticket types available! Contact an admin.", ephemeral=True)
        return
    
    view = TicketTypeView(ticket_types)
    
    embed = discord.Embed(
        title="🎫 Create Support Ticket",
        description="Please select the type of ticket you want to create:",
        color=0x3447003
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="ticket_stats", description="Show ticket statistics (Admin only)")
async def ticket_stats(interaction: discord.Interaction):
    """Show ticket statistics"""
    
    # Check if user has manage_channels permission
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You don't have permission to view ticket statistics!", ephemeral=True)
        return
    
    stats = await bot.db.get_ticket_stats()
    
    embed = discord.Embed(
        title="📊 Ticket Statistics",
        color=0x3447003,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="📈 Total Tickets", value=stats['total'], inline=True)
    embed.add_field(name="🟢 Open Tickets", value=stats['open'], inline=True)
    embed.add_field(name="🔒 Closed Tickets", value=stats['closed'], inline=True)
    embed.add_field(name="🔴 Overdue Tickets", value=stats['overdue'], inline=True)
    
    # Calculate resolution rate
    if stats['total'] > 0:
        resolution_rate = (stats['closed'] / stats['total']) * 100
        embed.add_field(name="✅ Resolution Rate", value=f"{resolution_rate:.1f}%", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="list_open_tickets", description="List all open tickets (Staff only)")
async def list_open_tickets(interaction: discord.Interaction):
    """List all open tickets"""
    
    # Check if user has manage_channels permission
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ Only staff members can view all open tickets!", ephemeral=True)
        return
    
    tickets = await bot.db.get_open_tickets()
    
    if not tickets:
        embed = discord.Embed(
            title="🎫 Open Tickets",
            description="No open tickets found! 🎉",
            color=0x00ff00
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title="🎫 Open Tickets",
        description=f"Found {len(tickets)} open ticket(s):",
        color=0x3447003
    )
    
    for ticket in tickets[:10]:  # Limit to 10 tickets to avoid embed limits
        created_time = int(time.mktime(datetime.fromisoformat(ticket['created_at']).timetuple()))
        
        embed.add_field(
            name=f"{ticket['emoji']} #{ticket['ticket_number']}",
            value=(f"**{ticket['title']}**\n"
                  f"Type: {ticket['type_name']}\n"
                  f"Creator: <@{ticket['creator_id']}>\n"
                  f"Created: <t:{created_time}:R>\n"
                  f"Channel: <#{ticket['channel_id']}>"),
            inline=True
        )
    
    if len(tickets) > 10:
        embed.set_footer(text=f"Showing 10 of {len(tickets)} tickets")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="delete_ticket_type", description="Delete a ticket type (Admin only)")
async def delete_ticket_type(interaction: discord.Interaction, name: str):
    """Delete a ticket type"""
    
    # Check if user is admin
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can delete ticket types!", ephemeral=True)
        return
    
    # Find ticket type by name
    ticket_types = await bot.db.get_ticket_types()
    ticket_type = None
    for tt in ticket_types:
        if tt['name'].lower() == name.lower():
            ticket_type = tt
            break
    
    if not ticket_type:
        await interaction.response.send_message(f"❌ Ticket type '{name}' not found!", ephemeral=True)
        return
    
    # Try to delete
    success = await bot.db.delete_ticket_type(ticket_type['id'])
    
    if success:
        embed = discord.Embed(
            title="✅ Ticket Type Deleted",
            description=f"Ticket type **{ticket_type['name']}** has been deleted successfully!",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed)
        logger.info(f"Ticket type '{name}' deleted by {interaction.user}")
    else:
        await interaction.response.send_message(
            f"❌ Cannot delete ticket type '{name}' because it has existing tickets!",
            ephemeral=True
        )

@bot.tree.command(name="setup_ticket_panel", description="Setup the ticket creation panel (Admin only)")
async def setup_ticket_panel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Setup a persistent ticket creation panel"""
    
    # Check if user is admin
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can setup ticket panels!", ephemeral=True)
        return
    
    target_channel = channel or interaction.channel
    
    ticket_types = await bot.db.get_ticket_types()
    
    if not ticket_types:
        await interaction.response.send_message("❌ No ticket types found! Create some ticket types first.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🎫 Support Ticket System",
        description=(
            "Need help? Create a support ticket by clicking the button below!\n\n"
            "**How it works:**\n"
            "1️⃣ Click 'Create Ticket'\n"
            "2️⃣ Select your issue type\n"
            "3️⃣ Fill out the form\n"
            "4️⃣ Wait for our team to respond\n\n"
            "Our team will respond according to the SLA for your ticket type."
        ),
        color=0x3447003
    )
    
    embed.add_field(
        name="📋 Available Ticket Types",
        value="\n".join([f"{tt['emoji']} **{tt['name']}** - {tt['sla_hours']}h SLA" for tt in ticket_types]),
        inline=False
    )
    
    embed.set_footer(text="Click the button below to get started!")
    
    # Use the same persistent view class
    class TicketPanelView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
        
        @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="create_ticket_panel")
        async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            ticket_types = await bot.db.get_ticket_types()
            
            if not ticket_types:
                await interaction.response.send_message("❌ No ticket types available! Contact an admin.", ephemeral=True)
                return
            
            view = TicketTypeView(ticket_types)
            
            embed = discord.Embed(
                title="🎫 Create Support Ticket",
                description="Please select the type of ticket you want to create:",
                color=0x3447003
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    view = TicketPanelView()
    # Note: Don't add to bot again as it's already persistent
    
    await target_channel.send(embed=embed, view=view)
    
    if channel:
        await interaction.response.send_message(f"✅ Ticket panel setup in {channel.mention}!", ephemeral=True)
    else:
        await interaction.response.send_message("✅ Ticket panel setup in this channel!", ephemeral=True)

# Error handler
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Handle application command errors"""
    logger.error(f"Command error: {error}")
    
    if interaction.response.is_done():
        await interaction.followup.send(f"❌ An error occurred: {str(error)}", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ An error occurred: {str(error)}", ephemeral=True)

# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        exit(1)
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        exit(1)
