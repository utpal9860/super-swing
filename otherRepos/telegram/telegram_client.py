"""
Telegram client authentication and management
"""
from telethon import TelegramClient
from telethon.tl.types import Channel
from telethon.errors import FloodWaitError, FloodError
import asyncio
import config


class TelegramChannelClient:
    """Manages Telegram client connection and authentication"""
    
    def __init__(self):
        self.client = None
        self.channel = None
        self.me = None
    
    async def authenticate(self, max_retries=3):
        """Authenticate with Telegram"""
        print("🔐 Authenticating with Telegram...")
        print("=" * 60)
        
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                # Create client - Telethon handles DC migration automatically
                self.client = TelegramClient(
                    config.SESSION_NAME,
                    config.API_ID,
                    config.API_HASH,
                    timeout=30,  # Increase timeout
                    connection_retries=5,  # Auto retry connections
                    retry_delay=1  # Delay between retries
                )
                
                # Use simple start method - it handles everything
                print(f"📱 Connecting to Telegram... (attempt {retry_count + 1}/{max_retries})")
                await self.client.start(phone=config.PHONE_NUMBER)
                
                self.me = await self.client.get_me()
                print(f"\n✅ Logged in successfully!")
                print(f"👤 Name: {self.me.first_name} {self.me.last_name or ''}")
                print(f"📱 Phone: {self.me.phone}")
                print(f"🆔 User ID: {self.me.id}")
                
                return self.client
                
            except Exception as e:
                last_error = e
                retry_count += 1
                print(f"⚠️ Connection error: {e}")
                
                if retry_count < max_retries:
                    print(f"🔄 Retrying in 3 seconds...")
                    import asyncio
                    await asyncio.sleep(3)
                else:
                    print(f"\n❌ Failed after {max_retries} attempts")
                    print(f"Last error: {last_error}")
                    print("\n💡 Troubleshooting:")
                    print("   1. Check your internet connection")
                    print("   2. Try again in a few minutes")
                    print("   3. Delete session file: channel_monitor.session")
                    raise
    
    async def get_channel(self, channel_name=None):
        """Get channel entity"""
        if not channel_name:
            channel_name = config.CHANNEL_NAME
        
        try:
            self.channel = await self.client.get_entity(channel_name)
            
            if isinstance(self.channel, Channel):
                print(f"✅ Channel found: {self.channel.title}")
                print(f"   Username: @{self.channel.username if self.channel.username else 'N/A'}")
                print(f"   ID: {self.channel.id}")
                print(f"   Members: {getattr(self.channel, 'participants_count', 'N/A')}")
                return self.channel
            else:
                print("❌ Entity found but it's not a channel")
                return None
                
        except Exception as e:
            print(f"❌ Error accessing channel: {e}")
            print("\n💡 Troubleshooting:")
            print("   1. Make sure you're a member of the channel")
            print("   2. Try using the channel username (e.g., '@channelname')")
            print("   3. Check if the channel name is spelled correctly")
            return None
    
    async def list_all_channels(self):
        """List all channels user is subscribed to"""
        print("\n📋 YOUR TELEGRAM CHANNELS")
        print("=" * 60)
        
        channels_list = []
        
        async for dialog in self.client.iter_dialogs():
            if dialog.is_channel:
                entity = dialog.entity
                channels_list.append({
                    'Name': entity.title,
                    'Username': f"@{entity.username}" if entity.username else 'N/A',
                    'ID': entity.id,
                    'Members': getattr(entity, 'participants_count', 'N/A')
                })
        
        return channels_list
    
    async def get_recent_messages(self, limit=10, max_retries=3):
        """Fetch recent messages from channel with flood protection"""
        if not self.channel:
            await self.get_channel()
        
        for attempt in range(max_retries):
            try:
                messages = await self.client.get_messages(self.channel, limit=limit)
                return messages
            except FloodWaitError as e:
                wait_time = e.seconds
                print(f"[FLOOD WAIT] Telegram requires waiting {wait_time}s")
                if attempt < max_retries - 1:
                    print(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time + 5)  # Add 5s buffer
                else:
                    raise
            except Exception as e:
                print(f"Error fetching messages: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)
                else:
                    raise
        
        return []
    
    async def disconnect(self):
        """Disconnect client"""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            print("🛑 Disconnected from Telegram")
    
    def is_connected(self):
        """Check if client is connected"""
        return self.client and self.client.is_connected()

