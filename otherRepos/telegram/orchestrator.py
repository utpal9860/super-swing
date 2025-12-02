"""
Main orchestrator for Telegram Channel Monitor
Coordinates all modules and manages the monitoring workflow
"""
import asyncio
from telethon import events
from telethon.errors import FloodWaitError, FloodError, ChannelPrivateError
from telegram_client import TelegramChannelClient
from message_handler import MessageHandler
from data_storage import DataStorage
from analytics import Analytics
from display import Display
from rate_limiter import RateLimiter
import config


class TelegramMonitorOrchestrator:
    """Orchestrates the entire telegram monitoring system"""
    
    def __init__(self):
        self.telegram_client = TelegramChannelClient()
        self.message_handler = MessageHandler()
        self.data_storage = DataStorage()
        self.analytics = Analytics(self.data_storage)
        self.display = Display()
        self.rate_limiter = RateLimiter()
        
        self.monitoring = False
        self.channel = None
        self.last_message_time = None
        self.health_check_interval = 60  # Check connection health every 60s
    
    async def initialize(self):
        """Initialize the monitoring system"""
        print("🚀 INITIALIZING TELEGRAM MONITOR")
        print("=" * 60)
        
        # Authenticate
        await self.telegram_client.authenticate()
        
        # Get channel
        self.channel = await self.telegram_client.get_channel()
        
        if not self.channel:
            print("❌ Failed to access channel. Please check configuration.")
            return False
        
        print("\n✅ Initialization complete!")
        return True
    
    async def start_monitoring(self):
        """Start real-time monitoring with robust error handling"""
        if not self.channel:
            print("❌ Channel not initialized. Run initialize() first.")
            return
        
        print("\n" + "=" * 60)
        print("STARTING REAL-TIME CHANNEL MONITOR")
        print("=" * 60)
        print(f"Connected to: {self.channel.title}")
        print(f"Listening for new messages...")
        print("\nPress Ctrl+C to stop monitoring\n")
        
        self.monitoring = True
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        # Define event handler with rate limit protection
        @self.telegram_client.client.on(events.NewMessage(chats=self.channel))
        async def handler(event):
            """Handle new messages with flood protection"""
            try:
                # Check rate limiter
                await self.rate_limiter.wait_if_needed()
                
                message = event.message
                self.last_message_time = asyncio.get_event_loop().time()
                
                # Extract message data
                message_data = self.message_handler.extract_message_data(
                    message,
                    config.CHANNEL_NAME,
                    event.chat_id
                )
                
                # Store message
                self.data_storage.add_message(message_data)
                
                # Record successful request
                self.rate_limiter.record_request()
                
                # Display message
                print(self.display.format_message_console(message_data))
                
                # Print notification
                print(f"[OK] Message #{message.id} received ({self.data_storage.get_count()} total)\n")
                
                # Auto-save periodically
                self.data_storage.auto_save()
                
                # Reset error counter on success
                nonlocal consecutive_errors
                consecutive_errors = 0
                
            except FloodWaitError as e:
                print(f"[FLOOD WAIT] Telegram requires {e.seconds}s wait")
                self.rate_limiter.record_error(is_rate_limit=True)
                await asyncio.sleep(e.seconds + 5)
            except FloodError as e:
                print(f"[FLOOD ERROR] Too many requests: {e}")
                self.rate_limiter.record_error(is_rate_limit=True)
                await asyncio.sleep(60)
            except Exception as e:
                consecutive_errors += 1
                print(f"[ERROR] Processing message: {e}")
                self.rate_limiter.record_error(is_rate_limit=False)
                
                if consecutive_errors >= max_consecutive_errors:
                    print(f"[CRITICAL] Too many errors ({consecutive_errors}), restarting...")
                    self.monitoring = False
        
        # Start health monitoring task
        health_task = asyncio.create_task(self._monitor_health())
        
        # Keep running
        print("[ACTIVE] Monitor is running. New messages will appear below:")
        print("-" * 60 + "\n")
        
        try:
            await self.telegram_client.client.run_until_disconnected()
        except KeyboardInterrupt:
            print("\n[STOP] Keyboard interrupt detected")
        except Exception as e:
            print(f"\n[ERROR] Monitoring stopped: {e}")
        finally:
            health_task.cancel()
            await self.stop_monitoring()
    
    async def _monitor_health(self):
        """Monitor connection health and rate limiter stats"""
        while self.monitoring:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                # Print health stats
                stats = self.rate_limiter.get_stats()
                print(f"\n[HEALTH CHECK]")
                print(f"  Requests/min: {stats['requests_last_minute']}/{self.rate_limiter.max_requests_per_minute}")
                print(f"  Messages collected: {self.data_storage.get_count()}")
                print(f"  Consecutive errors: {stats['consecutive_errors']}")
                if stats['in_cooldown']:
                    print(f"  Status: IN COOLDOWN ({stats['current_backoff']}s)")
                else:
                    print(f"  Status: HEALTHY")
                print()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ERROR] Health check failed: {e}")
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        print("\n🛑 Stopping monitor...")
        self.monitoring = False
        
        # Save data before stopping
        self.data_storage.export_all()
        
        # Disconnect
        await self.telegram_client.disconnect()
        
        print(f"📊 Total messages collected: {self.data_storage.get_count()}")
        print("✅ Monitor stopped successfully!")
    
    async def fetch_recent_messages(self, limit=10):
        """Fetch recent messages from channel with rate limiting"""
        print(f"\nFetching last {limit} messages...")
        
        # Wait if rate limited
        await self.rate_limiter.wait_if_needed()
        
        try:
            messages = await self.telegram_client.get_recent_messages(limit)
            
            for msg in messages:
                message_data = self.message_handler.extract_message_data(
                    msg,
                    config.CHANNEL_NAME,
                    self.channel.id
                )
                self.data_storage.add_message(message_data)
            
            self.rate_limiter.record_request()
            print(f"[OK] Fetched {len(messages)} messages")
            return messages
            
        except FloodWaitError as e:
            print(f"[FLOOD WAIT] Need to wait {e.seconds}s")
            self.rate_limiter.record_error(is_rate_limit=True)
            await asyncio.sleep(e.seconds + 5)
            return []
        except Exception as e:
            print(f"[ERROR] {e}")
            self.rate_limiter.record_error(is_rate_limit=False)
            return []
    
    def search_messages(self, keyword, case_sensitive=False):
        """Search stored messages"""
        results = self.message_handler.search_messages(
            self.data_storage.get_all_messages(),
            keyword,
            case_sensitive
        )
        
        print(f"\n🔍 Found {len(results)} messages containing '{keyword}'")
        return results
    
    def show_analytics(self):
        """Display analytics"""
        self.analytics.print_summary()
    
    def export_data(self):
        """Export all data"""
        self.data_storage.export_all()
    
    def show_status(self):
        """Show system status"""
        self.display.print_status(
            self.telegram_client,
            self.monitoring,
            self.data_storage
        )
    
    async def list_channels(self):
        """List all available channels"""
        channels = await self.telegram_client.list_all_channels()
        
        print(f"\n📋 Found {len(channels)} channels:")
        for i, ch in enumerate(channels, 1):
            print(f"{i}. {ch['Name']} ({ch['Username']})")
        
        return channels


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """Main entry point"""
    # Create orchestrator
    orchestrator = TelegramMonitorOrchestrator()
    
    # Initialize
    if not await orchestrator.initialize():
        return
    
    # Show status
    orchestrator.show_status()
    
    # Start monitoring (this runs until interrupted)
    try:
        await orchestrator.start_monitoring()
    except KeyboardInterrupt:
        print("\n⚠️ Stopping...")
        await orchestrator.stop_monitoring()


if __name__ == "__main__":
    # Run the orchestrator
    asyncio.run(main())

