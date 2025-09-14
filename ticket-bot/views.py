import discord
from discord.ext import commands
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class TicketTypeSelect(discord.ui.Select):
    def __init__(self, ticket_types: List[Dict]):
        options = []
        for ticket_type in ticket_types[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=ticket_type['name'],
                description=ticket_type['description'][:100] if ticket_type['description'] else "No description",
                emoji=ticket_type['emoji'],
                value=str(ticket_type['id'])
            ))
        
        super().__init__(placeholder="Select a ticket type...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        # Create modal for ticket creation
        modal = TicketCreationModal(int(self.values[0]))
        await interaction.response.send_modal(modal)

class TicketTypeView(discord.ui.View):
    def __init__(self, ticket_types: List[Dict]):
        super().__init__(timeout=300)
        self.add_item(TicketTypeSelect(ticket_types))

class TicketCreationModal(discord.ui.Modal):
    def __init__(self, type_id: int):
        super().__init__(title="Create New Ticket")
        self.type_id = type_id
        
        self.title_input = discord.ui.TextInput(
            label="Ticket Title",
            placeholder="Brief description of your issue...",
            required=True,
            max_length=100
        )
        
        self.description_input = discord.ui.TextInput(
            label="Description",
            placeholder="Detailed description of your issue...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        
        self.priority_input = discord.ui.TextInput(
            label="Priority (low/medium/high/urgent)",
            placeholder="medium",
            required=False,
            max_length=10
        )
        
        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.priority_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Get the bot instance from the interaction
        bot = interaction.client
        
        # Validate priority
        priority = self.priority_input.value.lower() if self.priority_input.value else 'medium'
        if priority not in ['low', 'medium', 'high', 'urgent']:
            priority = 'medium'
        
        try:
            # Generate ticket number
            import time
            ticket_number = f"TK-{int(time.time())}"
            
            # Get ticket type info
            ticket_type = await bot.db.get_ticket_type(self.type_id)
            if not ticket_type:
                await interaction.response.send_message("❌ Invalid ticket type!", ephemeral=True)
                return
            
            # Create ticket category and channel
            guild = interaction.guild
            category_name = f"🎫 {ticket_type['name']} Tickets"
            
            # Find or create category
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                category = await guild.create_category(category_name)
                # Set permissions for the category
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
                }
                await category.edit(overwrites=overwrites)
            
            # Create ticket channel
            channel_name = f"{ticket_type['emoji']}-{ticket_number.lower()}"
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
            }
            
            channel = await guild.create_text_channel(
                channel_name, 
                category=category,
                overwrites=overwrites,
                topic=f"Ticket: {self.title_input.value} | Creator: {interaction.user.mention}"
            )
            
            # Create ticket in database
            ticket_id = await bot.db.create_ticket(
                ticket_number=ticket_number,
                type_id=self.type_id,
                title=self.title_input.value,
                description=self.description_input.value,
                creator_id=interaction.user.id,
                channel_id=channel.id,
                priority=priority
            )
            
            # Create ticket embed
            embed = discord.Embed(
                title=f"{ticket_type['emoji']} Ticket #{ticket_number}",
                description=self.description_input.value,
                color=ticket_type['color']
            )
            embed.add_field(name="📋 Title", value=self.title_input.value, inline=False)
            embed.add_field(name="👤 Creator", value=interaction.user.mention, inline=True)
            embed.add_field(name="🏷️ Type", value=ticket_type['name'], inline=True)
            embed.add_field(name="⚡ Priority", value=priority.title(), inline=True)
            embed.add_field(name="📅 Created", value=f"<t:{int(time.time())}:F>", inline=True)
            embed.add_field(name="⏰ SLA Deadline", value=f"<t:{int((time.time() + ticket_type['sla_hours'] * 3600))}:R>", inline=True)
            embed.set_footer(text=f"Ticket ID: {ticket_id}")
            
            # Create control buttons
            view = TicketControlView(ticket_id)
            
            # Send initial message to ticket channel
            await channel.send(f"👋 Welcome {interaction.user.mention}! Your ticket has been created.", embed=embed, view=view)
            
            # Respond to the user
            await interaction.response.send_message(
                f"✅ Ticket created successfully! Check {channel.mention}",
                ephemeral=True
            )
            
            logger.info(f"Ticket {ticket_number} created by {interaction.user} in {channel}")
            
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            await interaction.response.send_message(
                f"❌ Error creating ticket: {str(e)}",
                ephemeral=True
            )

class TicketControlView(discord.ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.ticket_id = ticket_id
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot = interaction.client
        ticket = await bot.db.get_ticket_by_channel(interaction.channel.id)
        
        if not ticket:
            await interaction.response.send_message("❌ Ticket not found!", ephemeral=True)
            return
        
        # Check permissions - only creator or admins can close
        if interaction.user.id != ticket['creator_id'] and not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ You don't have permission to close this ticket!", ephemeral=True)
            return
        
        # Confirm closure
        view = ConfirmCloseView(self.ticket_id)
        await interaction.response.send_message(
            "⚠️ Are you sure you want to close this ticket?",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Assign to Me", style=discord.ButtonStyle.secondary, emoji="👤")
    async def assign_to_me(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot = interaction.client
        
        # Check if user has manage_channels permission (staff)
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Only staff members can assign tickets!", ephemeral=True)
            return
        
        await bot.db.assign_ticket(self.ticket_id, interaction.user.id, interaction.user.id)
        
        embed = discord.Embed(
            title="🎯 Ticket Assigned",
            description=f"This ticket has been assigned to {interaction.user.mention}",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed)
    
    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, emoji="➕")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check permissions
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Only staff members can add users to tickets!", ephemeral=True)
            return
        
        modal = AddUserModal()
        await interaction.response.send_modal(modal)

class ConfirmCloseView(discord.ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=60)
        self.ticket_id = ticket_id
    
    @discord.ui.button(label="Yes, Close", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot = interaction.client
        
        # Update ticket status
        await bot.db.update_ticket_status(self.ticket_id, 'closed', interaction.user.id)
        
        # Create closure embed
        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"This ticket has been closed by {interaction.user.mention}",
            color=0xff0000,
            timestamp=discord.utils.utcnow()
        )
        
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        
        # Archive channel after 30 seconds
        import asyncio
        await asyncio.sleep(30)
        
        try:
            # Rename channel to indicate closure
            await interaction.channel.edit(name=f"closed-{interaction.channel.name}")
            
            # Move to archive category or delete after some time
            guild = interaction.guild
            archive_category = discord.utils.get(guild.categories, name="📁 Ticket Archive")
            if not archive_category:
                archive_category = await guild.create_category("📁 Ticket Archive")
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
                }
                await archive_category.edit(overwrites=overwrites)
            
            await interaction.channel.edit(category=archive_category)
            
        except Exception as e:
            logger.error(f"Error archiving ticket channel: {e}")
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Ticket closure cancelled.", embed=None, view=None)

class AddUserModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Add User to Ticket")
        
        self.user_input = discord.ui.TextInput(
            label="User ID or Mention",
            placeholder="Enter user ID or @mention",
            required=True
        )
        
        self.add_item(self.user_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parse user input
        user_input = self.user_input.value.strip()
        
        # Try to get user
        user = None
        if user_input.startswith('<@') and user_input.endswith('>'):
            # It's a mention
            user_id = user_input[2:-1]
            if user_id.startswith('!'):
                user_id = user_id[1:]
            try:
                user = await interaction.guild.fetch_member(int(user_id))
            except:
                pass
        else:
            # Try as user ID
            try:
                user = await interaction.guild.fetch_member(int(user_input))
            except:
                pass
        
        if not user:
            await interaction.response.send_message("❌ User not found!", ephemeral=True)
            return
        
        # Add user to channel
        try:
            await interaction.channel.set_permissions(
                user, 
                read_messages=True, 
                send_messages=True
            )
            
            embed = discord.Embed(
                title="👤 User Added",
                description=f"{user.mention} has been added to this ticket by {interaction.user.mention}",
                color=0x00ff00
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error adding user: {str(e)}", ephemeral=True)
