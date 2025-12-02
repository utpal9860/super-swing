"""
Data storage and export functions
"""
import pandas as pd
import json
import config


class DataStorage:
    """Handles data storage and export operations"""
    
    def __init__(self):
        self.messages_data = []
    
    def add_message(self, message_data):
        """Add a message to storage"""
        self.messages_data.append(message_data)
    
    def get_all_messages(self):
        """Get all stored messages"""
        return self.messages_data
    
    def get_dataframe(self):
        """Get messages as pandas DataFrame"""
        if self.messages_data:
            return pd.DataFrame(self.messages_data)
        else:
            return pd.DataFrame()
    
    def save_to_csv(self, filename=None):
        """Save messages to CSV file"""
        if not filename:
            filename = config.CSV_OUTPUT
        
        if self.messages_data:
            df = pd.DataFrame(self.messages_data)
            df.to_csv(filename, index=False, encoding='utf-8')
            print(f"✅ Saved {len(self.messages_data)} messages to {filename}")
            return True
        else:
            print("⚠️ No messages to save yet")
            return False
    
    def save_to_json(self, filename=None):
        """Save messages to JSON file"""
        if not filename:
            filename = config.JSON_OUTPUT
        
        if self.messages_data:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.messages_data, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved {len(self.messages_data)} messages to {filename}")
            return True
        else:
            print("⚠️ No messages to save yet")
            return False
    
    def save_to_excel(self, filename=None):
        """Save messages to Excel file"""
        if not filename:
            filename = config.EXCEL_OUTPUT
        
        if self.messages_data:
            try:
                df = pd.DataFrame(self.messages_data)
                df.to_excel(filename, index=False, engine='openpyxl')
                print(f"✅ Saved {len(self.messages_data)} messages to {filename}")
                return True
            except ImportError:
                print("⚠️ Excel export requires openpyxl: pip install openpyxl")
                return False
        else:
            print("⚠️ No messages to save yet")
            return False
    
    def export_all(self):
        """Export to all formats (CSV, JSON, Excel)"""
        print("\n💾 EXPORTING DATA TO ALL FORMATS")
        print("=" * 60)
        
        if not self.messages_data:
            print("⚠️ No data to export yet!")
            return
        
        self.save_to_csv()
        self.save_to_json()
        self.save_to_excel()
        
        print("\n✅ Export complete!")
    
    def auto_save(self, threshold=None):
        """Auto-save if threshold is reached"""
        if not threshold:
            threshold = config.AUTO_SAVE_INTERVAL
        
        if len(self.messages_data) % threshold == 0 and len(self.messages_data) > 0:
            self.save_to_csv()
            print(f"🔄 Auto-saved at {len(self.messages_data)} messages")
    
    def clear_data(self):
        """Clear all stored messages"""
        count = len(self.messages_data)
        self.messages_data = []
        print(f"🗑️ Cleared {count} messages from memory")
    
    def get_count(self):
        """Get count of stored messages"""
        return len(self.messages_data)

