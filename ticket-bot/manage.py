"""
Utility script for managing the Discord Ticket Bot
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager

load_dotenv()

class BotManager:
    def __init__(self):
        self.db = DatabaseManager(os.getenv('DATABASE_PATH', './data/tickets.db'))
    
    async def initialize_db(self):
        """Initialize the database"""
        await self.db.initialize()
        print("✅ Database initialized successfully!")
    
    async def create_default_ticket_types(self):
        """Create some default ticket types"""
        default_types = [
            {
                'name': 'Bug Report',
                'description': 'Report bugs and technical issues',
                'sla_hours': 24,
                'color': 0xFF0000,
                'emoji': '🐛'
            },
            {
                'name': 'Feature Request',
                'description': 'Request new features or improvements',
                'sla_hours': 72,
                'color': 0x00FF00,
                'emoji': '💡'
            },
            {
                'name': 'General Support',
                'description': 'General questions and support',
                'sla_hours': 48,
                'color': 0x0099FF,
                'emoji': '❓'
            },
            {
                'name': 'Account Issues',
                'description': 'Problems with your account',
                'sla_hours': 12,
                'color': 0xFF9900,
                'emoji': '👤'
            },
            {
                'name': 'Urgent',
                'description': 'Critical issues requiring immediate attention',
                'sla_hours': 4,
                'color': 0x990000,
                'emoji': '🚨'
            }
            ,
            {
                'name': 'Access to IRL',
                'description': 'Request access to IRL events or channels',
                'sla_hours': 0,
                'color': 0x6A5ACD,
                'emoji': '🛂',
                'access_role_id': '1395560393325154447'
            }
        ]
        
        for ticket_type in default_types:
            success = await self.db.create_ticket_type(**ticket_type)
            if success:
                print(f"✅ Created ticket type: {ticket_type['name']}")
            else:
                print(f"⚠️ Ticket type already exists: {ticket_type['name']}")
    
    async def show_stats(self):
        """Show database statistics"""
        stats = await self.db.get_ticket_stats()
        ticket_types = await self.db.get_ticket_types()
        
        print("\n📊 Database Statistics:")
        print(f"  Total Tickets: {stats['total']}")
        print(f"  Open Tickets: {stats['open']}")
        print(f"  Closed Tickets: {stats['closed']}")
        print(f"  Overdue Tickets: {stats['overdue']}")
        print(f"  Ticket Types: {len(ticket_types)}")
        
        if ticket_types:
            print("\n🎫 Ticket Types:")
            for tt in ticket_types:
                print(f"  {tt['emoji']} {tt['name']} - {tt['sla_hours']}h SLA")
    
    async def cleanup_old_tickets(self, days: int = 30):
        """Clean up old closed tickets (placeholder for future implementation)"""
        print(f"🧹 Cleanup feature not implemented yet (would clean tickets older than {days} days)")

async def main():
    print("🎫 Discord Ticket Bot Manager")
    print("=" * 40)
    
    if len(sys.argv) < 2:
        print("Usage: python manage.py <command>")
        print("\nAvailable commands:")
        print("  init          - Initialize database")
        print("  create-types  - Create default ticket types")
        print("  stats         - Show database statistics")
        print("  cleanup       - Clean up old tickets")
        return
    
    command = sys.argv[1].lower()
    manager = BotManager()
    
    try:
        if command == 'init':
            await manager.initialize_db()
        
        elif command == 'create-types':
            await manager.initialize_db()
            await manager.create_default_ticket_types()
        
        elif command == 'stats':
            await manager.show_stats()
        
        elif command == 'cleanup':
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            await manager.cleanup_old_tickets(days)
        
        else:
            print(f"❌ Unknown command: {command}")
    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
