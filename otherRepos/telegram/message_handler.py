"""
Message processing and data extraction
"""
import re
from datetime import datetime


class MessageHandler:
    """Handles message processing and data extraction"""
    
    @staticmethod
    def extract_links(text):
        """Extract URLs from text"""
        if not text:
            return []
        url_pattern = r'https?://[^\s]+'
        return re.findall(url_pattern, text)
    
    @staticmethod
    def extract_message_data(message, channel_name, channel_id):
        """Extract all relevant data from a message"""
        message_data = {
            'message_id': message.id,
            'channel_name': channel_name,
            'channel_id': channel_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'date': message.date.strftime('%Y-%m-%d %H:%M:%S') if message.date else None,
            'text': message.text or '',
            'media_type': None,
            'links': [],
            'views': message.views if hasattr(message, 'views') else None,
            'forwards': message.forwards if hasattr(message, 'forwards') else None,
            'is_reply': False,
            'reply_to_msg_id': None,
        }
        
        # Extract reply information
        if hasattr(message, 'reply_to') and message.reply_to:
            message_data['is_reply'] = True
            if hasattr(message.reply_to, 'reply_to_msg_id'):
                message_data['reply_to_msg_id'] = message.reply_to.reply_to_msg_id
        
        # Check for media
        if message.media:
            message_data['media_type'] = MessageHandler._get_media_type(message.media)
        
        # Extract links
        if message.text:
            message_data['links'] = MessageHandler.extract_links(message.text)
        
        return message_data
    
    @staticmethod
    def _get_media_type(media):
        """Determine media type"""
        if hasattr(media, 'photo'):
            return 'photo'
        elif hasattr(media, 'document'):
            return 'document'
        elif hasattr(media, 'video'):
            return 'video'
        elif hasattr(media, 'webpage'):
            return 'webpage'
        else:
            return 'unknown'
    
    @staticmethod
    def search_messages(messages_data, keyword, case_sensitive=False):
        """Search messages by keyword"""
        results = []
        
        for msg in messages_data:
            text = msg.get('text', '')
            if case_sensitive:
                if keyword in text:
                    results.append(msg)
            else:
                if keyword.lower() in text.lower():
                    results.append(msg)
        
        return results
    
    @staticmethod
    def filter_by_media_type(messages_data, media_type):
        """Filter messages by media type"""
        return [msg for msg in messages_data if msg.get('media_type') == media_type]
    
    @staticmethod
    def filter_by_date_range(messages_data, start_date, end_date):
        """Filter messages by date range"""
        results = []
        
        for msg in messages_data:
            msg_date = msg.get('date')
            if msg_date and start_date <= msg_date <= end_date:
                results.append(msg)
        
        return results

