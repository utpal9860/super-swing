"""
Update IPO list with manually added stocks
"""

# Read existing list
with open('ipo_stocks_2019_2025_complete.txt', 'r') as f:
    existing = set(line.strip() for line in f if line.strip())

print(f"Existing stocks: {len(existing)}")

# Read additions
try:
    with open('ADD_MISSING_IPOS_HERE.txt', 'r') as f:
        new_stocks = set()
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith('#'):
                new_stocks.add(line.upper())
    
    print(f"New stocks to add: {len(new_stocks)}")
    
    # Combine
    all_stocks = sorted(existing.union(new_stocks))
    
    print(f"Total stocks: {len(all_stocks)}")
    
    # Save
    with open('ipo_stocks_2019_2025_complete.txt', 'w') as f:
        for stock in all_stocks:
            f.write(f"{stock}\n")
    
    print(f"\nUpdated list saved!")
    print(f"Added {len(new_stocks)} new stocks")
    
except FileNotFoundError:
    print("ADD_MISSING_IPOS_HERE.txt not found")

