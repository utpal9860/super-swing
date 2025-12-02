"""
Analytics and statistics for collected messages
"""
import pandas as pd


class Analytics:
    """Provides analytics and statistics for messages"""
    
    def __init__(self, data_storage):
        self.storage = data_storage
    
    def get_basic_stats(self):
        """Get basic statistics"""
        df = self.storage.get_dataframe()
        
        if df.empty:
            return None
        
        stats = {
            'total_messages': len(df),
            'date_range': {
                'start': df['timestamp'].min(),
                'end': df['timestamp'].max()
            },
            'total_views': df['views'].sum(),
            'average_views': df['views'].mean(),
            'max_views': df['views'].max(),
            'messages_with_media': df['media_type'].notna().sum(),
            'messages_with_links': sum(1 for links in df['links'] if len(links) > 0)
        }
        
        return stats
    
    def get_media_stats(self):
        """Get media type statistics"""
        df = self.storage.get_dataframe()
        
        if df.empty:
            return {}
        
        media_counts = df['media_type'].value_counts().to_dict()
        return media_counts
    
    def get_link_stats(self):
        """Get link statistics"""
        df = self.storage.get_dataframe()
        
        if df.empty:
            return None
        
        total_links = sum(len(links) for links in df['links'])
        msgs_with_links = sum(1 for links in df['links'] if len(links) > 0)
        
        stats = {
            'total_links': total_links,
            'messages_with_links': msgs_with_links,
            'avg_links_per_message': total_links / len(df) if len(df) > 0 else 0
        }
        
        return stats
    
    def get_top_messages(self, n=5, sort_by='views'):
        """Get top N messages by views"""
        df = self.storage.get_dataframe()
        
        if df.empty:
            return []
        
        if sort_by == 'views':
            top_messages = df.nlargest(n, 'views')
        else:
            top_messages = df.head(n)
        
        return top_messages.to_dict('records')
    
    def get_time_distribution(self):
        """Get message distribution over time"""
        df = self.storage.get_dataframe()
        
        if df.empty:
            return {}
        
        df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
        hourly_counts = df['hour'].value_counts().sort_index().to_dict()
        
        return hourly_counts
    
    def print_summary(self):
        """Print comprehensive summary"""
        print("\n📊 MESSAGE ANALYTICS")
        print("=" * 60)
        
        stats = self.get_basic_stats()
        
        if not stats:
            print("⚠️ No data available yet!")
            return
        
        # Basic stats
        print(f"\n📈 Basic Statistics:")
        print(f"   Total Messages: {stats['total_messages']:,}")
        print(f"   Date Range: {stats['date_range']['start']} to {stats['date_range']['end']}")
        print(f"   Total Views: {stats['total_views']:,.0f}")
        print(f"   Average Views: {stats['average_views']:.0f}")
        print(f"   Max Views: {stats['max_views']:,.0f}")
        print(f"   Messages with Media: {stats['messages_with_media']}")
        print(f"   Messages with Links: {stats['messages_with_links']}")
        
        # Media stats
        print(f"\n📎 Media Statistics:")
        media_stats = self.get_media_stats()
        for media_type, count in media_stats.items():
            if media_type:
                print(f"   {media_type}: {count}")
        
        # Links stats
        link_stats = self.get_link_stats()
        if link_stats:
            print(f"\n🔗 Links Statistics:")
            print(f"   Total Links: {link_stats['total_links']}")
            print(f"   Messages with Links: {link_stats['messages_with_links']}")
            print(f"   Avg Links/Message: {link_stats['avg_links_per_message']:.2f}")
        
        # Most viewed messages
        print(f"\n🏆 Top 5 Most Viewed Messages:")
        top_messages = self.get_top_messages(5)
        for msg in top_messages:
            print(f"   ID {msg['message_id']}: {msg['views']:,} views")
            print(f"      {msg['text'][:80]}...")
            print()

