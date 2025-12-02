"""
Quick test script - Run IPO analysis locally
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'ipo_analysis'))

from ipo_analyzer import IPOAnalyzer, get_ipo_stocks_from_period

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

print("="*80)
print("IPO BUY-AND-HOLD ANALYSIS - TEST RUN")
print("="*80)

# Fetch all stocks
print("\n1. Fetching stock list...")
tickers = get_ipo_stocks_from_period(2019, 2025)
print(f"   Found {len(tickers)} stocks to check")

# Analyze
print("\n2. Analyzing (filtering for 2019-2025 listings)...")
analyzer = IPOAnalyzer(investment_per_stock=15000)
df = analyzer.analyze_multiple_stocks(tickers, start_year=2019, end_year=2025)

if df.empty:
    print("\nNo stocks found")
    sys.exit(1)

print(f"\nFound {len(df)} stocks listed between 2019-2025\n")

# Show results
print("="*80)
print("TOP 10 PERFORMERS (by CAGR)")
print("="*80)
top10 = df.head(10)
for idx, row in top10.iterrows():
    print(f"{idx+1:2d}. {row['ticker']:15s} | Listed: {row['listing_date']} | CAGR: {row['cagr']:6.2f}% | Return: {row['return_pct']:8.1f}%")

# Portfolio summary
print("\n" + "="*80)
print("PORTFOLIO SUMMARY")
print("="*80)
summary = analyzer.get_portfolio_summary(df)
print(f"Total Stocks:     {summary['num_stocks']}")
print(f"Total Invested:   Rs.{summary['total_invested']:,.0f}")
print(f"Current Value:    Rs.{summary['total_current_value']:,.0f}")
print(f"Total Return:     {summary['total_return_pct']:.1f}%")
print(f"Portfolio CAGR:   {summary['portfolio_cagr']:.2f}%")
print(f"Portfolio XIRR:   {summary['portfolio_xirr']:.2f}%")
print(f"Win Rate:         {summary['win_rate']:.1f}%")

print("\n" + "="*80)
print("Analysis complete! CSV saved to: ipo_results.csv")
print("="*80)

# Save CSV
df.to_csv('ipo_results.csv', index=False)

