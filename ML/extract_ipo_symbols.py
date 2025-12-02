"""
Extract all IPO stock symbols from CSV
"""
import csv
import re

symbols = set()
excluded = []

with open('IPO-2019.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    headers = next(reader)  # Skip header
    
    for row in reader:
        if len(row) < 8:
            continue
        
        company = row[0].strip()
        symbol = row[3].strip()
        listing_date = row[7].strip()
        
        # Skip if no symbol or no listing date
        if not symbol or symbol == '-' or listing_date == '-':
            excluded.append(f"{company} ({symbol}) - No listing/Not listed")
            continue
        
        # Skip FPOs (Follow-on Public Offerings)
        if 'FPO' in symbol or 'FPO' in company:
            excluded.append(f"{company} - FPO (not IPO)")
            continue
        
        # Skip withdrawn issues
        if 'Withdrawn' in company:
            excluded.append(f"{company} - Withdrawn")
            continue
        
        # Clean symbol
        symbol = symbol.upper().strip()
        
        # Remove any special characters
        symbol = re.sub(r'[^A-Z0-9]', '', symbol)
        
        if symbol and len(symbol) > 1:
            symbols.add(symbol)

# Sort symbols
symbols = sorted(list(symbols))

print("="*80)
print(f"EXTRACTED {len(symbols)} IPO SYMBOLS FROM CSV")
print("="*80)

# Save to file
with open('ipo_stocks_2019_2025_complete.txt', 'w') as f:
    for symbol in symbols:
        f.write(f"{symbol}\n")

print(f"\nSaved to: ipo_stocks_2019_2025_complete.txt")

# Show sample
print(f"\nFirst 30 symbols:")
for i, symbol in enumerate(symbols[:30], 1):
    print(f"  {i:3d}. {symbol}")

print(f"\n... and {len(symbols) - 30} more")

# Show excluded
print(f"\nExcluded {len(excluded)} entries:")
for item in excluded[:10]:
    print(f"  - {item}")
if len(excluded) > 10:
    print(f"  ... and {len(excluded) - 10} more")

print(f"\n{'='*80}")
print(f"FINAL COUNT: {len(symbols)} IPO stocks ready for analysis")
print(f"{'='*80}")

