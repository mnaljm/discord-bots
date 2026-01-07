import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def initialize(self):
        """Initialize the database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Create ticket_types table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    sla_hours INTEGER NOT NULL DEFAULT 24,
                    color INTEGER DEFAULT 3447000,
                    emoji TEXT DEFAULT '🎫',
                    access_role_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create tickets table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_number TEXT UNIQUE NOT NULL,
                    type_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    creator_id INTEGER NOT NULL,
                    assignee_id INTEGER,
                    channel_id INTEGER,
                    status TEXT DEFAULT 'open',
                    priority TEXT DEFAULT 'medium',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    sla_deadline TIMESTAMP,
                    sla_notified BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (type_id) REFERENCES ticket_types (id)
                )
            """)
            
            # Create ticket_messages table for audit trail
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    message_type TEXT DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ticket_id) REFERENCES tickets (id)
                )
            """)
            
            # Ensure new columns exist for older DBs
            async with db.execute("PRAGMA table_info(ticket_types)") as cursor:
                cols = await cursor.fetchall()
                col_names = [c[1] for c in cols]
                if 'access_role_id' not in col_names:
                    await db.execute("ALTER TABLE ticket_types ADD COLUMN access_role_id TEXT")

            await db.commit()
            logger.info("Database initialized successfully")
    
    async def create_ticket_type(self, name: str, description: str, sla_hours: int, 
                                color: int = 3447000, emoji: str = '🎫', access_role_id: str = None) -> bool:
        """Create a new ticket type"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO ticket_types (name, description, sla_hours, color, emoji, access_role_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, description, sla_hours, color, emoji, access_role_id))
                await db.commit()
                logger.info(f"Created ticket type: {name}")
                return True
        except aiosqlite.IntegrityError:
            logger.warning(f"Ticket type {name} already exists")
            return False
    
    async def get_ticket_types(self) -> List[Dict]:
        """Get all ticket types"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM ticket_types ORDER BY name") as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
    
    async def get_ticket_type(self, type_id: int) -> Optional[Dict]:
        """Get a specific ticket type by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM ticket_types WHERE id = ?", (type_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
    
    async def create_ticket(self, ticket_number: str, type_id: int, title: str, 
                           description: str, creator_id: int, channel_id: int,
                           priority: str = 'medium') -> int:
        """Create a new ticket"""
        # Get SLA hours for the ticket type
        ticket_type = await self.get_ticket_type(type_id)
        sla_hours = ticket_type.get('sla_hours', 24) if ticket_type else 24
        if sla_hours and sla_hours > 0:
            sla_deadline = datetime.now() + timedelta(hours=sla_hours)
        else:
            sla_deadline = None
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO tickets (ticket_number, type_id, title, description, creator_id, 
                                   channel_id, priority, sla_deadline)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (ticket_number, type_id, title, description, creator_id, channel_id, 
                  priority, sla_deadline))
            ticket_id = cursor.lastrowid
            await db.commit()
            
            # Add creation message to audit trail
            await self.add_ticket_message(ticket_id, creator_id, 
                                        f"Ticket created: {title}", "system")
            
            logger.info(f"Created ticket {ticket_number} with ID {ticket_id}")
            return ticket_id
    
    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Dict]:
        """Get ticket by channel ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT t.*, tt.name as type_name, tt.emoji, tt.color
                FROM tickets t
                JOIN ticket_types tt ON t.type_id = tt.id
                WHERE t.channel_id = ? AND t.status != 'closed'
            """, (channel_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None

    async def get_ticket_by_channel_any(self, channel_id: int) -> Optional[Dict]:
        """Get ticket by channel ID regardless of status"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT t.*, tt.name as type_name, tt.emoji, tt.color
                FROM tickets t
                JOIN ticket_types tt ON t.type_id = tt.id
                WHERE t.channel_id = ?
            """, (channel_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
    
    async def get_ticket_by_number(self, ticket_number: str) -> Optional[Dict]:
        """Get ticket by ticket number"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT t.*, tt.name as type_name, tt.emoji, tt.color
                FROM tickets t
                JOIN ticket_types tt ON t.type_id = tt.id
                WHERE t.ticket_number = ?
            """, (ticket_number,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
    
    async def update_ticket_status(self, ticket_id: int, status: str, user_id: int):
        """Update ticket status"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tickets 
                SET status = ?, updated_at = CURRENT_TIMESTAMP,
                    closed_at = CASE WHEN ? = 'closed' THEN CURRENT_TIMESTAMP ELSE closed_at END
                WHERE id = ?
            """, (status, status, ticket_id))
            await db.commit()
            
            # Add status change to audit trail
            await self.add_ticket_message(ticket_id, user_id, 
                                        f"Status changed to: {status}", "system")
    
    async def assign_ticket(self, ticket_id: int, assignee_id: int, user_id: int):
        """Assign ticket to a user"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tickets 
                SET assignee_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (assignee_id, ticket_id))
            await db.commit()
            
            # Add assignment to audit trail
            await self.add_ticket_message(ticket_id, user_id, 
                                        f"Ticket assigned to <@{assignee_id}>", "system")
    
    async def add_ticket_message(self, ticket_id: int, user_id: int, message: str, 
                                message_type: str = 'user'):
        """Add a message to the ticket audit trail"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO ticket_messages (ticket_id, user_id, message, message_type)
                VALUES (?, ?, ?, ?)
            """, (ticket_id, user_id, message, message_type))
            await db.commit()
    
    async def get_tickets_near_sla(self, hours_before: int = 2) -> List[Dict]:
        """Get tickets that are approaching their SLA deadline"""
        deadline = datetime.now() + timedelta(hours=hours_before)
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT t.*, tt.name as type_name
                FROM tickets t
                JOIN ticket_types tt ON t.type_id = tt.id
                WHERE t.status IN ('open', 'in_progress') 
                AND t.sla_deadline <= ?
                AND t.sla_notified = FALSE
            """, (deadline,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
    
    async def mark_sla_notified(self, ticket_id: int):
        """Mark that SLA notification has been sent for a ticket"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tickets 
                SET sla_notified = TRUE
                WHERE id = ?
            """, (ticket_id,))
            await db.commit()
    
    async def get_open_tickets(self) -> List[Dict]:
        """Get all open tickets"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT t.*, tt.name as type_name, tt.emoji
                FROM tickets t
                JOIN ticket_types tt ON t.type_id = tt.id
                WHERE t.status IN ('open', 'in_progress')
                ORDER BY t.created_at DESC
            """, ) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
    
    async def get_ticket_stats(self) -> Dict:
        """Get ticket statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get total tickets
            async with db.execute("SELECT COUNT(*) FROM tickets") as cursor:
                total = (await cursor.fetchone())[0]
            
            # Get open tickets
            async with db.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('open', 'in_progress')") as cursor:
                open_count = (await cursor.fetchone())[0]
            
            # Get closed tickets
            async with db.execute("SELECT COUNT(*) FROM tickets WHERE status = 'closed'") as cursor:
                closed_count = (await cursor.fetchone())[0]
            
            # Get overdue tickets
            async with db.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('open', 'in_progress') AND sla_deadline < ?", (datetime.now(),)) as cursor:
                overdue_count = (await cursor.fetchone())[0]
            
            return {
                'total': total,
                'open': open_count,
                'closed': closed_count,
                'overdue': overdue_count
            }
    
    async def delete_ticket_type(self, type_id: int) -> bool:
        """Delete a ticket type if no tickets are using it"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if any tickets use this type
            async with db.execute("SELECT COUNT(*) FROM tickets WHERE type_id = ?", (type_id,)) as cursor:
                count = (await cursor.fetchone())[0]
            
            if count > 0:
                return False
            
            await db.execute("DELETE FROM ticket_types WHERE id = ?", (type_id,))
            await db.commit()
            return True

    async def delete_ticket(self, ticket_id: int) -> bool:
        """Delete a ticket and its messages"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM ticket_messages WHERE ticket_id = ?", (ticket_id,))
            await db.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
            await db.commit()
            return True
