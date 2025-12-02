"""
Display and formatting functions
"""


class Display:
    """Handles display formatting for messages"""
    
    @staticmethod
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
    
    @staticmethod
    def format_message_console(message_data):
        """Format message for console display"""
        output = []
        output.append("=" * 60)
        output.append(f"📨 Message #{message_data['message_id']}")
        output.append(f"⏰ {message_data['timestamp']}")
        output.append("-" * 60)
        output.append(f"📝 Text: {message_data['text'][:200]}")
        
        if message_data.get('media_type'):
            output.append(f"📎 Media: {message_data['media_type']}")
        
        if message_data.get('links'):
            output.append(f"🔗 Links: {len(message_data['links'])}")
        
        output.append(f"👁️ Views: {message_data.get('views', 'N/A')}")
        output.append("=" * 60)
        
        return "\n".join(output)
    
    @staticmethod
    def print_status(client, monitoring, storage):
        """Print monitoring status"""
        print("\n" + "=" * 60)
        print("📊 MONITORING STATUS")
        print("=" * 60)
        
        print(f"\n🔐 Authentication:")
        print(f"   Status: {'✅ Connected' if client.is_connected() else '❌ Disconnected'}")
        
        print(f"\n📢 Monitoring:")
        print(f"   Status: {'🟢 Active' if monitoring else '🔴 Inactive'}")
        
        print(f"\n📊 Data:")
        print(f"   Messages Collected: {storage.get_count()}")
        
        if storage.get_count() > 0:
            df = storage.get_dataframe()
            print(f"   Latest Message: {df['timestamp'].max()}")
            print(f"   Total Views: {df['views'].sum():,.0f}")
        
        print("\n" + "=" * 60)

