# ============================================================================
# TELEGRAM CHANNEL MONITOR - JUPYTER NOTEBOOK VERSION
# Monitor "All News" channel and get real-time updates
# ============================================================================

# Cell 1: Install Required Libraries
# Run this cell first (only once)
# ============================================================================
"""
!pip install telethon nest_asyncio pandas
"""

# Cell 2: Import Libraries
# ============================================================================
from telethon import TelegramClient, events
from telethon.tl.types import Channel
import asyncio
import nest_asyncio
import pandas as pd
from datetime import datetime
import json
import re
from IPython.display import display, HTML, clear_output
import warnings
warnings.filterwarnings('ignore')

# Allow nested event loops (required for Jupyter)
nest_asyncio.apply()

print("✅ Libraries imported successfully!")

# Cell 3: Configuration
# ============================================================================
# IMPORTANT: Get these from https://my.telegram.org/apps
API_ID = 33942643  # Replace with your API ID (number)
API_HASH = '865403b9c9d0db46615571d189145a97'  # Replace with your API hash (string)
PHONE_NUMBER = '+917385922115'  # Replace with your phone number (include country code)

# Channel to monitor
CHANNEL_NAME = 'BANKNIFTY NIFTY INTRADAY STOCK OPTIONS'  # You can also use @channelname format

# Session name
SESSION_NAME = 'channel_monitor'

print("✅ Configuration set!")
print(f"📱 Phone: {PHONE_NUMBER}")
print(f"📢 Channel: {CHANNEL_NAME}")

# Cell 4: Global Variables
# ============================================================================
# Store messages in memory
messages_data = []
client = None
monitoring = False

print("✅ Variables initialized!")

# Cell 5: Helper Functions
# ============================================================================

def extract_links(text):
    """Extract URLs from text"""
    if not text:
        return []
    url_pattern = r'https?://[^\s]+'
    return re.findall(url_pattern, text)

def format_message_html(message_data):
    """Format message as HTML for nice display"""
    html = f"""
    <div style="border: 2px solid #4CAF50; border-radius: 10px; padding: 15px; margin: 10px 0; background-color: #f9f9f9;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
            <span style="color: #4CAF50; font-weight: bold;">📨 New Message</span>
            <span style="color: #666; font-size: 12px;">{message_data['timestamp']}</span>
        </div>
        <div style="background-color: white; padding: 10px; border-radius: 5px; margin: 10px 0;">
            <strong>Channel:</strong> {message_data['channel_name']}<br>
            <strong>Message ID:</strong> {message_data['message_id']}<br>
            <strong>Views:</strong> {message_data.get('views', 'N/A')}
        </div>
        <div style="background-color: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0;">
            <strong>📝 Content:</strong><br>
            <p style="margin: 10px 0; white-space: pre-wrap;">{message_data['text'][:500]}</p>
        </div>
    """
    
    if message_data.get('media_type'):
        html += f"""
        <div style="background-color: #d4edda; padding: 10px; border-radius: 5px; margin: 10px 0;">
            <strong>📎 Media:</strong> {message_data['media_type']}
        </div>
        """
    
    if message_data.get('links'):
        html += f"""
        <div style="background-color: #d1ecf1; padding: 10px; border-radius: 5px; margin: 10px 0;">
            <strong>🔗 Links ({len(message_data['links'])}):</strong><br>
        """
        for link in message_data['links'][:5]:
            html += f'<a href="{link}" target="_blank">{link[:60]}...</a><br>'
        html += "</div>"
    
    html += "</div>"
    return html

def save_to_csv(filename='telegram_messages.csv'):
    """Save messages to CSV file"""
    if messages_data:
        df = pd.DataFrame(messages_data)
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"✅ Saved {len(messages_data)} messages to {filename}")
    else:
        print("⚠️ No messages to save yet")

def get_messages_dataframe():
    """Get messages as pandas DataFrame"""
    if messages_data:
        return pd.DataFrame(messages_data)
    else:
        return pd.DataFrame()

print("✅ Helper functions defined!")

# Cell 6: Authentication & Setup
# ============================================================================

async def authenticate():
    """Authenticate with Telegram"""
    global client
    
    print("🔐 Authenticating with Telegram...")
    print("=" * 60)
    
    # Create client
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    # Connect and authenticate
    await client.start(phone=PHONE_NUMBER)
    
    # Get your info
    me = await client.get_me()
    print(f"\n✅ Logged in successfully!")
    print(f"👤 Name: {me.first_name} {me.last_name or ''}")
    print(f"📱 Phone: {me.phone}")
    print(f"🆔 User ID: {me.id}")
    
    return client

# Run authentication
print("Starting authentication...")
print("⚠️ You may need to enter a code sent to your Telegram app")
print("-" * 60)

client = await authenticate()


# Cell 7: List Available Channels (Optional)
# ============================================================================

async def list_all_channels():
    """List all channels you're subscribed to"""
    print("\n📋 YOUR TELEGRAM CHANNELS")
    print("=" * 60)
    
    channels_list = []
    
    async for dialog in client.iter_dialogs():
        if dialog.is_channel:
            entity = dialog.entity
            channels_list.append({
                'Name': entity.title,
                'Username': f"@{entity.username}" if entity.username else 'N/A',
                'ID': entity.id,
                'Members': getattr(entity, 'participants_count', 'N/A')
            })
    
    df = pd.DataFrame(channels_list)
    display(df)
    
    return df

# Uncomment the line below to see all your channels
await list_all_channels()

print("✅ Ready to list channels (uncomment the last line to see them)")

# Cell 8: Test Channel Access
# ============================================================================

async def test_channel_access():
    """Test if we can access the channel"""
    print(f"\n🔍 Testing access to channel: '{CHANNEL_NAME}'")
    print("=" * 60)
    
    try:
        channel = await client.get_entity(CHANNEL_NAME)
        
        if isinstance(channel, Channel):
            print(f"✅ Channel found!")
            print(f"\n📢 Channel Details:")
            print(f"   Name: {channel.title}")
            print(f"   Username: @{channel.username if channel.username else 'N/A'}")
            print(f"   ID: {channel.id}")
            print(f"   Members: {getattr(channel, 'participants_count', 'N/A')}")
            
            # Get latest message
            messages = await client.get_messages(channel, limit=1)
            if messages:
                print(f"\n📝 Latest message preview:")
                print(f"   Date: {messages[0].date}")
                print(f"   Text: {messages[0].text[:100] if messages[0].text else '[Media]'}...")
            
            return channel
        else:
            print("❌ Entity found but it's not a channel")
            return None
            
    except Exception as e:
        print(f"❌ Error accessing channel: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Make sure you're a member of the channel")
        print("   2. Try using the channel username (e.g., '@allnews')")
        print("   3. Check if the channel name is spelled correctly")
        return None

# Test channel access
# channel = await test_channel_access()

# Cell 9: Fetch Recent Messages (Optional)
# ============================================================================

async def get_recent_messages(limit=10):
    """Fetch and display recent messages from the channel"""
    print(f"\n📥 Fetching last {limit} messages from '{CHANNEL_NAME}'...")
    print("=" * 60)
    
    try:
        channel = await client.get_entity(CHANNEL_NAME)
        messages = await client.get_messages(channel, limit=limit)
        
        recent_data = []
        
        for msg in messages:
            msg_data = {
                'ID': msg.id,
                'Date': msg.date.strftime('%Y-%m-%d %H:%M:%S') if msg.date else 'N/A',
                'Text': msg.text[:100] if msg.text else '[No text/Media only]',
                'Views': msg.views if hasattr(msg, 'views') else 'N/A',
                'Has_Media': 'Yes' if msg.media else 'No'
            }
            recent_data.append(msg_data)
        
        df = pd.DataFrame(recent_data)
        display(df)
        
        return messages
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

# Uncomment to fetch recent messages
# recent_msgs = await get_recent_messages(10)

print("✅ Ready to fetch recent messages (uncomment the last line)")

# Cell 10: Start Real-time Monitoring
# ============================================================================

async def start_monitoring():
    """Start monitoring the channel for new messages"""
    global monitoring, messages_data
    
    print("\n" + "=" * 60)
    print("🚀 STARTING REAL-TIME CHANNEL MONITOR")
    print("=" * 60)
    
    try:
        # Get channel entity
        channel = await client.get_entity(CHANNEL_NAME)
        print(f"✅ Connected to: {channel.title}")
        print(f"👂 Listening for new messages...")
        print("\n⚠️ To stop monitoring, run the 'Stop Monitoring' cell\n")
        
        monitoring = True
        
        # Define event handler
        @client.on(events.NewMessage(chats=channel))
        async def handler(event):
            """Handle new messages"""
            try:
                message = event.message
                
                # Extract message data
                message_data = {
                    'message_id': message.id,
                    'channel_name': CHANNEL_NAME,
                    'channel_id': event.chat_id,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'date': message.date.strftime('%Y-%m-%d %H:%M:%S') if message.date else None,
                    'text': message.text or '',
                    'media_type': None,
                    'links': [],
                    'views': message.views if hasattr(message, 'views') else None,
                    'forwards': message.forwards if hasattr(message, 'forwards') else None,
                }
                
                # Check for media
                if message.media:
                    if hasattr(message.media, 'photo'):
                        message_data['media_type'] = 'photo'
                    elif hasattr(message.media, 'document'):
                        message_data['media_type'] = 'document'
                    elif hasattr(message.media, 'video'):
                        message_data['media_type'] = 'video'
                    elif hasattr(message.media, 'webpage'):
                        message_data['media_type'] = 'webpage'
                
                # Extract links
                if message.text:
                    message_data['links'] = extract_links(message.text)
                
                # Store message
                messages_data.append(message_data)
                
                # Display formatted message
                display(HTML(format_message_html(message_data)))
                
                # Print simple notification
                print(f"✅ Message #{message.id} received and stored ({len(messages_data)} total)")
                
            except Exception as e:
                print(f"❌ Error processing message: {e}")
        
        # Keep running
        print("🟢 Monitor is active. New messages will appear below:")
        print("-" * 60 + "\n")
        
        # Run until stopped
        await client.run_until_disconnected()
        
    except Exception as e:
        print(f"❌ Error starting monitor: {e}")
        monitoring = False

# Start monitoring (this will run continuously)
await start_monitoring()

# Cell 11: Stop Monitoring
# ============================================================================

async def stop_monitoring():
    """Stop the monitoring"""
    global monitoring
    
    if client and client.is_connected():
        monitoring = False
        await client.disconnect()
        print("🛑 Monitoring stopped!")
        print(f"📊 Total messages collected: {len(messages_data)}")
    else:
        print("⚠️ Monitor is not running")

# Run this cell to stop monitoring
# await stop_monitoring()

print("ℹ️ Run this cell to stop monitoring")

# Cell 12: View Collected Messages
# ============================================================================

def view_messages():
    """Display all collected messages as a DataFrame"""
    print(f"\n📊 COLLECTED MESSAGES: {len(messages_data)}")
    print("=" * 60)
    
    if messages_data:
        df = get_messages_dataframe()
        
        # Show summary
        print(f"\n📈 Summary:")
        print(f"   Total Messages: {len(df)}")
        print(f"   With Links: {df['links'].apply(lambda x: len(x) > 0).sum()}")
        print(f"   With Media: {df['media_type'].notna().sum()}")
        print(f"   Average Views: {df['views'].mean():.0f}")
        
        # Display DataFrame
        print("\n📋 Messages Table:")
        display(df[['message_id', 'timestamp', 'text', 'views', 'media_type']].head(20))
        
        return df
    else:
        print("⚠️ No messages collected yet. Start monitoring first!")
        return None

# View collected messages
# df = view_messages()

print("ℹ️ Run this cell to view collected messages")

# Cell 13: Export Data
# ============================================================================

def export_data():
    """Export messages to different formats"""
    print("\n💾 EXPORTING DATA")
    print("=" * 60)
    
    if not messages_data:
        print("⚠️ No data to export yet!")
        return
    
    # Export to CSV
    save_to_csv('telegram_messages.csv')
    
    # Export to JSON
    with open('telegram_messages.json', 'w', encoding='utf-8') as f:
        json.dump(messages_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved to telegram_messages.json")
    
    # Export to Excel (if openpyxl is installed)
    try:
        df = get_messages_dataframe()
        df.to_excel('telegram_messages.xlsx', index=False)
        print(f"✅ Saved to telegram_messages.xlsx")
    except:
        print("⚠️ Excel export requires openpyxl: pip install openpyxl")
    
    print("\n✅ Export complete!")

# Export data
# export_data()

print("ℹ️ Run this cell to export collected data")

# Cell 14: Search Messages
# ============================================================================

def search_messages(keyword, case_sensitive=False):
    """Search messages by keyword"""
    print(f"\n🔍 SEARCHING FOR: '{keyword}'")
    print("=" * 60)
    
    if not messages_data:
        print("⚠️ No messages to search yet!")
        return None
    
    df = get_messages_dataframe()
    
    if case_sensitive:
        mask = df['text'].str.contains(keyword, na=False)
    else:
        mask = df['text'].str.contains(keyword, case=False, na=False)
    
    results = df[mask]
    
    print(f"✅ Found {len(results)} messages containing '{keyword}'")
    
    if len(results) > 0:
        display(results[['message_id', 'timestamp', 'text', 'views']])
    
    return results

# Search for specific keyword
# results = search_messages('breaking', case_sensitive=False)

print("ℹ️ Run this cell to search messages")

# Cell 15: Analytics & Statistics
# ============================================================================

def show_analytics():
    """Display analytics of collected messages"""
    print("\n📊 MESSAGE ANALYTICS")
    print("=" * 60)
    
    if not messages_data:
        print("⚠️ No data available yet!")
        return
    
    df = get_messages_dataframe()
    
    # Basic stats
    print(f"\n📈 Basic Statistics:")
    print(f"   Total Messages: {len(df)}")
    print(f"   Date Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"   Total Views: {df['views'].sum():,.0f}")
    print(f"   Average Views: {df['views'].mean():.0f}")
    print(f"   Max Views: {df['views'].max():,.0f}")
    
    # Media stats
    print(f"\n📎 Media Statistics:")
    media_counts = df['media_type'].value_counts()
    for media_type, count in media_counts.items():
        if media_type:
            print(f"   {media_type}: {count}")
    
    # Links stats
    total_links = sum(len(links) for links in df['links'])
    msgs_with_links = sum(1 for links in df['links'] if len(links) > 0)
    print(f"\n🔗 Links Statistics:")
    print(f"   Total Links: {total_links}")
    print(f"   Messages with Links: {msgs_with_links}")
    
    # Most viewed messages
    print(f"\n🏆 Top 5 Most Viewed Messages:")
    top_messages = df.nlargest(5, 'views')[['message_id', 'views', 'text']]
    for idx, row in top_messages.iterrows():
        print(f"   ID {row['message_id']}: {row['views']:,} views")
        print(f"      {row['text'][:80]}...")
        print()

# Show analytics
# show_analytics()

print("ℹ️ Run this cell to view analytics")

# Cell 16: Send to Your API (Optional)
# ============================================================================

def send_to_api(message_data, api_url):
    """
    Send message data to your application's API
    
    Args:
        message_data: Dictionary containing message information
        api_url: Your API endpoint URL
    """
    import requests
    
    try:
        response = requests.post(
            api_url,
            json=message_data,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            print(f"✅ Message #{message_data['message_id']} sent to API")
            return True
        else:
            print(f"⚠️ API returned status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending to API: {e}")
        return False

def send_all_to_api(api_url):
    """Send all collected messages to your API"""
    print(f"\n📤 SENDING MESSAGES TO API: {api_url}")
    print("=" * 60)
    
    if not messages_data:
        print("⚠️ No messages to send!")
        return
    
    success_count = 0
    
    for msg in messages_data:
        if send_to_api(msg, api_url):
            success_count += 1
    
    print(f"\n✅ Successfully sent {success_count}/{len(messages_data)} messages")

# Example usage:
# send_all_to_api('https://your-api.com/webhook')

print("ℹ️ Configure and run this cell to send data to your API")

# Cell 17: Quick Status Check
# ============================================================================

def status_check():
    """Quick status of the monitoring system"""
    print("\n" + "=" * 60)
    print("📊 MONITORING STATUS")
    print("=" * 60)
    
    print(f"\n🔐 Authentication:")
    print(f"   Status: {'✅ Connected' if client and client.is_connected() else '❌ Disconnected'}")
    print(f"   Phone: {PHONE_NUMBER}")
    
    print(f"\n📢 Channel:")
    print(f"   Name: {CHANNEL_NAME}")
    print(f"   Monitoring: {'🟢 Active' if monitoring else '🔴 Inactive'}")
    
    print(f"\n📊 Data:")
    print(f"   Messages Collected: {len(messages_data)}")
    
    if messages_data:
        df = get_messages_dataframe()
        print(f"   Latest Message: {df['timestamp'].max()}")
        print(f"   Total Views: {df['views'].sum():,.0f}")
    
    print("\n" + "=" * 60)

# Check status
status_check()

# ============================================================================
# QUICK START GUIDE
# ============================================================================