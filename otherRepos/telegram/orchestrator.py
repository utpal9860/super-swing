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
from signal_parser import parse_signal
from reply_parser import parse_reply_instruction
from nse_options import get_option_ltp
from datetime import datetime, timezone
import config
import requests
import asyncio


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
        self.channels = None
        if hasattr(config, "CHANNELS") and isinstance(getattr(config, "CHANNELS"), list) and config.CHANNELS:
            self.channels = await self.telegram_client.get_channels(config.CHANNELS)
            if not self.channels:
                print("❌ Failed to access any channels from CHANNELS. Please check configuration.")
                return False
            print(f"\n✅ Initialization complete! Subscribed channels: {len(self.channels)}")
        else:
            self.channel = await self.telegram_client.get_channel()
            if not self.channel:
                print("❌ Failed to access channel. Please check configuration.")
                return False
            print("\n✅ Initialization complete!")
        # Optional: bootstrap with recent messages for visibility
        try:
            recent = await self.telegram_client.get_recent_messages(limit=5)
            if recent:
                print("\n[BOOTSTRAP] Showing recent messages:")
                for m in recent:
                    text = (getattr(m, "message", None) or "").strip()
                    posted_dt = getattr(m, "date", None)
                    if posted_dt and posted_dt.tzinfo is None:
                        posted_dt = posted_dt.replace(tzinfo=timezone.utc)
                    received_dt = datetime.now(timezone.utc)
                    lag = None
                    if posted_dt:
                        lag = max(0.0, (received_dt - posted_dt).total_seconds())
                    if not text:
                        continue
                    parsed = parse_signal(text)
                    if parsed:
                        sym = parsed["symbol"]; strike = parsed["strike"]; otyp = parsed["option_type"]
                        trig = parsed["trigger_type"]; trig_px = parsed["trigger_price"]
                        lag_txt = f" | Lag: {lag:.1f}s" if isinstance(lag, (int, float)) else ""
                        print(f"  [SIGNAL]{lag_txt} {sym} {int(strike)} {otyp} {trig} {trig_px}")
                    elif getattr(config, "DEBUG_PRINT_NON_MATCHING", False):
                        lag_txt = f" | Lag: {lag:.1f}s" if isinstance(lag, (int, float)) else ""
                        print(f"  [SKIP]{lag_txt} {text[:140]}")
        except Exception as e:
            print(f"[BOOTSTRAP] Error fetching recent messages: {e}")
        return True
    
    async def start_monitoring(self):
        """Start real-time monitoring with robust error handling"""
        if not (self.channel or self.channels):
            print("❌ Channel(s) not initialized. Run initialize() first.")
            return
        
        print("\n" + "=" * 60)
        print("STARTING REAL-TIME CHANNEL MONITOR")
        print("=" * 60)
        if self.channels:
            print(f"Connected to {len(self.channels)} channels")
        else:
            print(f"Connected to: {self.channel.title}")
        print(f"Listening for new messages...")
        print("\nPress Ctrl+C to stop monitoring\n")
        
        self.monitoring = True
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        # Define event handler with rate limit protection
        @self.telegram_client.client.on(events.NewMessage(chats=(self.channels or self.channel)))
        async def handler(event):
            """Handle new messages with flood protection"""
            try:
                # Check rate limiter
                await self.rate_limiter.wait_if_needed()
                
                message = event.message
                self.last_message_time = asyncio.get_event_loop().time()
                
                # Extract message data
                # Resolve channel name for logging
                try:
                    chat = await event.get_chat()
                    channel_name = getattr(chat, "title", None) or getattr(chat, "username", None) or str(event.chat_id)
                except Exception:
                    channel_name = str(event.chat_id)
                message_data = self.message_handler.extract_message_data(message, channel_name, event.chat_id)
                # Timestamp diagnostics: posted vs received
                try:
                    posted_dt = getattr(message, "date", None)
                    if posted_dt and posted_dt.tzinfo is None:
                        # assume UTC if tz-naive
                        posted_dt = posted_dt.replace(tzinfo=timezone.utc)
                    received_dt = datetime.now(timezone.utc)
                    if posted_dt:
                        lag_seconds = max(0.0, (received_dt - posted_dt).total_seconds())
                    else:
                        lag_seconds = None
                    message_data["posted_at"] = posted_dt.isoformat() if posted_dt else None
                    message_data["received_at"] = received_dt.isoformat()
                    message_data["lag_seconds"] = lag_seconds
                except Exception:
                    pass
                # Ignore media-only messages
                if message.media and not (message.text and message.text.strip()):
                    return

                # Check if this is a reply message with modification instructions
                if message_data.get("is_reply") and message_data.get("reply_to_msg_id"):
                    reply_instruction = parse_reply_instruction(message_data.get("text", ""))
                    if reply_instruction:
                        # This is a reply with a trade modification instruction
                        async def handle_reply_modification():
                            try:
                                instruction = reply_instruction["action"]
                                reply_to_msg_id = message_data["reply_to_msg_id"]
                                channel_id = event.chat_id
                                
                                # Forward to webapp API
                                if config.WEBAPP_POST_ENABLED:
                                    payload = {
                                        "message_id": reply_to_msg_id,
                                        "channel_id": channel_id,
                                        "instruction": instruction
                                    }
                                    headers = {}
                                    if getattr(config, "WEBAPP_API_KEY", ""):
                                        headers["X-API-Key"] = f"{config.WEBAPP_API_KEY}"
                                    elif getattr(config, "WEBAPP_AUTH_TOKEN", ""):
                                        headers["Authorization"] = f"Bearer {config.WEBAPP_AUTH_TOKEN}"
                                    
                                    def _post():
                                        r = requests.post(
                                            f"{config.WEBAPP_API_URL}/api/trades/modify_from_reply",
                                            json=payload,
                                            headers=headers,
                                            timeout=10
                                        )
                                        return r.status_code, (r.text[:200] if hasattr(r, "text") else "")
                                    
                                    resp_status, resp_body = await asyncio.to_thread(_post)
                                    message_data["reply_modification_status"] = resp_status
                                    print(f"[REPLY-MODIFY] {instruction.upper()} -> {resp_status} | Reply to msg {reply_to_msg_id}")
                                    if resp_status == 200:
                                        print(f"[REPLY-MODIFY] ✅ Successfully {instruction} trade for message {reply_to_msg_id}")
                                    else:
                                        print(f"[REPLY-MODIFY] ❌ Failed to {instruction} trade: {resp_body}")
                            except Exception as e:
                                message_data["reply_modification_error"] = str(e)
                                print(f"[REPLY-MODIFY] Error: {e}")
                        
                        asyncio.create_task(handle_reply_modification())
                        # Continue processing (store message, etc.)
                
                # Attempt to parse structured signal
                parsed = parse_signal(message_data.get("text", ""))
                if parsed:
                    # Attach parsed signal immediately; fetch/post in background to avoid blocking event loop
                    message_data["signal"] = parsed
                    # Normalize common symbol typos/aliases before downstream lookups
                    SYMBOL_NORMALIZATION = {
                        "ASHOKLE": "ASHOKLEY",
                        "ASHOK-LY": "ASHOKLEY",
                    }
                    normalized_symbol = SYMBOL_NORMALIZATION.get(parsed["symbol"], parsed["symbol"])
                    parsed["symbol"] = normalized_symbol
                    async def fetch_and_forward():
                        try:
                            ltp, resolved_expiry = await asyncio.to_thread(
                                get_option_ltp,
                                parsed["symbol"],
                                parsed["strike"],
                                parsed["option_type"],
                                parsed.get("expiry_month"),
                            )
                            message_data["option_ltp"] = ltp
                            message_data["expiry_resolved"] = resolved_expiry
                            # Optional: forward to webapp as paper trade
                            if config.WEBAPP_POST_ENABLED:
                                try:
                                    payload = {
                                        "action": parsed["action"],
                                        "symbol": parsed["symbol"],
                                        "strike": parsed["strike"],
                                        "option_type": parsed["option_type"],
                                        "trigger_type": parsed["trigger_type"],
                                        "trigger_price": parsed["trigger_price"],
                                        "targets": parsed.get("targets"),
                                        "stop_loss_text": parsed.get("stop_loss"),
                                        "expiry_month": parsed.get("expiry_month"),
                                        "quantity": 1,
                                        "notes": f"From channel {config.CHANNEL_NAME}",
                                        "telegram_message_id": message.id,
                                        "telegram_channel_id": event.chat_id,
                                        "telegram_channel_name": channel_name
                                    }
                                    # Route to a specific user if configured
                                    for_user = getattr(config, "WEBAPP_FOR_USER_USERNAME", "")
                                    if for_user:
                                        payload["for_username"] = for_user
                                    headers = {}
                                    if getattr(config, "WEBAPP_API_KEY", ""):
                                        headers["X-API-Key"] = f"{config.WEBAPP_API_KEY}"
                                    elif getattr(config, "WEBAPP_AUTH_TOKEN", ""):
                                        headers["Authorization"] = f"Bearer {config.WEBAPP_AUTH_TOKEN}"
                                    def _post():
                                        r = requests.post(
                                            f"{config.WEBAPP_API_URL}/api/trades/create_from_signal",
                                            json=payload,
                                            headers=headers,
                                            timeout=10
                                        )
                                        return r.status_code, (r.text[:200] if hasattr(r, "text") else "")
                                    resp_status, resp_body = await asyncio.to_thread(_post)
                                    message_data["webapp_post_status"] = resp_status
                                    if getattr(config, "DEBUG_PRINT_NON_MATCHING", False) or True:
                                        print(f"[POST]/api/trades/create_from_signal -> {resp_status} {('[..]' if resp_body else '')}")
                                except Exception as e:
                                    message_data["webapp_post_error"] = str(e)
                            # Print an update line once LTP arrives
                            sym = parsed["symbol"]; strike = parsed["strike"]; otyp = parsed["option_type"]
                            trig = parsed["trigger_type"]; trig_px = parsed["trigger_price"]
                            exp = message_data.get("expiry_resolved") or parsed.get("expiry_month") or "-"
                            lag = message_data.get("lag_seconds"); lag_txt = f" | Lag: {lag:.1f}s" if isinstance(lag, (int, float)) else ""
                            print(f"[SIGNAL-UPDATE]{lag_txt} {sym} {int(strike)} {otyp} {trig} {trig_px} | LTP: {ltp if ltp is not None else 'N/A'} | Exp: {exp}")
                        except Exception as e:
                            message_data["option_ltp_error"] = str(e)
                    asyncio.create_task(fetch_and_forward())
                else:
                    # Skip messages that do not match the desired pattern
                    if getattr(config, "DEBUG_PRINT_NON_MATCHING", False):
                        txt = (message_data.get("text") or "").strip().replace("\n", " ")
                        if txt:
                            lag = message_data.get("lag_seconds")
                            posted_iso = message_data.get("posted_at") or "-"
                            received_iso = message_data.get("received_at") or "-"
                            lag_txt = f" | Lag: {lag:.1f}s" if isinstance(lag, (int, float)) else ""
                            print(f"[SKIP]{lag_txt} | Sent: {posted_iso} | Recv: {received_iso} | {txt[:140]}")
                    return

                # Store message
                self.data_storage.add_message(message_data)
                
                # Record successful request
                self.rate_limiter.record_request()
                
                # Display message
                if parsed:
                    # Print a concise line for parsed signals
                    sym = parsed["symbol"]
                    strike = parsed["strike"]
                    otyp = parsed["option_type"]
                    trig = parsed["trigger_type"]
                    trig_px = parsed["trigger_price"]
                    ltp = message_data.get("option_ltp")  # may be None initially
                    exp = message_data.get("expiry_resolved") or parsed.get("expiry_month") or "-"
                    lag = message_data.get("lag_seconds")
                    posted_iso = message_data.get("posted_at") or "-"
                    received_iso = message_data.get("received_at") or "-"
                    lag_txt = f" | Lag: {lag:.1f}s" if isinstance(lag, (int, float)) else ""
                    print(f"[SIGNAL]{lag_txt} | Sent: {posted_iso} | Recv: {received_iso} | {sym} {int(strike)} {otyp} {trig} {trig_px} | LTP: {ltp if ltp is not None else 'pending'} | Exp: {exp}")
                else:
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

