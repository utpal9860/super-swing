"""
Parse IPO CSV files and extract stock symbols
"""
import csv
import glob

all_symbols = set()

# Find all IPO CSV files
csv_files = glob.glob('IPO-*.csv')

print(f"Found {len(csv_files)} CSV files")

for csv_file in csv_files:
    print(f"\nProcessing: {csv_file}")
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            count = 0
            for row in reader:
                symbol = row.get('Symbol', '').strip()
                
                # Skip if no symbol or symbol is "-"
                if symbol and symbol != '-':
                    all_symbols.add(symbol)
                    count += 1
            
            print(f"  Extracted {count} symbols")
    
    except Exception as e:
        print(f"  Error: {e}")

# Load existing list
try:
    with open('ipo_stocks_2019_2025_complete.txt', 'r') as f:
        existing = set(line.strip() for line in f if line.strip())
    print(f"\nExisting stocks: {len(existing)}")
except:
    existing = set()
    print(f"\nNo existing file found")

# Combine
all_stocks = sorted(existing.union(all_symbols))

print(f"New stocks from CSV: {len(all_symbols)}")
print(f"Total after merge: {len(all_stocks)}")
print(f"Added: {len(all_stocks) - len(existing)} new stocks")

# Save
with open('ipo_stocks_2019_2025_complete.txt', 'w') as f:
    for stock in all_stocks:
        f.write(f"{stock}\n")

print(f"\nUpdated list saved to: ipo_stocks_2019_2025_complete.txt")

# Show sample of new additions
new_additions = sorted(all_symbols - existing)
if new_additions:
    print(f"\nNew additions (showing first 20):")
    for i, stock in enumerate(new_additions[:20], 1):
        print(f"  {i}. {stock}")
    if len(new_additions) > 20:
        print(f"  ... and {len(new_additions) - 20} more")

