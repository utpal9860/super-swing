"""
Test script for IPO Buy-and-Hold Analysis
Verifies calculations and data fetching work correctly
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'ipo_analysis'))

from ipo_analyzer import IPOAnalyzer
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Fix Windows console encoding issues
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def test_single_stock():
    """Test analysis for a single stock"""
    print("\n" + "="*80)
    print("TEST 1: Single Stock Analysis (INFY)")
    print("="*80)
    
    analyzer = IPOAnalyzer(investment_per_stock=15000)
    result = analyzer.analyze_single_stock('INFY')
    
    if result:
        print(f"\n✓ Analysis successful for INFY")
        print(f"  Company: {result['company_name']}")
        print(f"  Listing Date: {result['listing_date']}")
        print(f"  Listing Price: Rs.{result['listing_price']:.2f}")
        print(f"  Current Price: Rs.{result['current_price']:.2f}")
        print(f"  Invested: Rs.{result['invested_amount']:,.2f}")
        print(f"  Current Value: Rs.{result['current_value']:,.2f}")
        print(f"  Return: {result['return_pct']:.2f}%")
        print(f"  CAGR: {result['cagr']:.2f}%")
        print(f"  XIRR: {result['xirr']:.2f}%")
        print(f"  Years Held: {result['years_held']:.2f}")
        print(f"  Status: {result['status']}")
        
        # Validate calculations
        assert result['current_value'] > 0, "Current value should be positive"
        assert result['years_held'] > 0, "Years held should be positive"
        assert -100 <= result['cagr'] <= 10000, f"CAGR {result['cagr']}% seems unrealistic"
        
        print(f"\n✓ Calculations validated")
        return True
    else:
        print(f"\n✗ Analysis failed for INFY")
        return False


def test_multiple_stocks():
    """Test analysis for multiple stocks"""
    print("\n" + "="*80)
    print("TEST 2: Multiple Stocks Analysis")
    print("="*80)
    
    # Test with small list of reliable stocks
    test_stocks = ['INFY', 'TCS', 'RELIANCE', 'HDFCBANK', 'ICICIBANK']
    
    analyzer = IPOAnalyzer(investment_per_stock=15000)
    df = analyzer.analyze_multiple_stocks(test_stocks, start_year=1990, end_year=2025)
    
    if not df.empty:
        print(f"\n✓ Analysis successful for {len(df)} stocks")
        print(f"\nResults Summary:")
        print(f"  Stocks analyzed: {len(df)}")
        print(f"  Profitable: {len(df[df['status'] == 'PROFIT'])}")
        print(f"  Loss-making: {len(df[df['status'] == 'LOSS'])}")
        
        print(f"\nTop 3 Performers (by CAGR):")
        top3 = df.nlargest(3, 'cagr')
        for idx, row in top3.iterrows():
            print(f"  {row['ticker']:10s} - {row['cagr']:7.2f}% CAGR")
        
        # Validate
        assert df['cagr'].min() >= -100, "Minimum CAGR too low"
        assert df['cagr'].max() <= 10000, "Maximum CAGR unrealistically high"
        assert df['years_held'].min() > 0, "Years held should be positive"
        
        print(f"\n✓ Calculations validated")
        return True
    else:
        print(f"\n✗ Analysis failed - no results")
        return False


def test_portfolio_summary():
    """Test portfolio-level metrics"""
    print("\n" + "="*80)
    print("TEST 3: Portfolio Summary")
    print("="*80)
    
    test_stocks = ['INFY', 'TCS', 'RELIANCE', 'HDFCBANK']
    
    analyzer = IPOAnalyzer(investment_per_stock=15000)
    df = analyzer.analyze_multiple_stocks(test_stocks, start_year=2000, end_year=2025)
    
    if not df.empty:
        summary = analyzer.get_portfolio_summary(df)
        
        print(f"\n✓ Portfolio summary generated")
        print(f"\nPortfolio Metrics:")
        print(f"  Total Invested: Rs.{summary['total_invested']:,.2f}")
        print(f"  Current Value: Rs.{summary['total_current_value']:,.2f}")
        print(f"  Total Return: {summary['total_return_pct']:.2f}%")
        print(f"  Portfolio CAGR: {summary['portfolio_cagr']:.2f}%")
        print(f"  Portfolio XIRR: {summary['portfolio_xirr']:.2f}%")
        print(f"  Win Rate: {summary['win_rate']:.2f}%")
        print(f"  Best Stock: {summary['best_stock']} ({summary['best_return']:.2f}% CAGR)")
        print(f"  Worst Stock: {summary['worst_stock']} ({summary['worst_return']:.2f}% CAGR)")
        
        # Validate
        assert summary['total_invested'] > 0, "Total invested should be positive"
        assert summary['portfolio_cagr'] >= -100, "Portfolio CAGR too low"
        assert summary['portfolio_cagr'] <= 1000, "Portfolio CAGR unrealistically high"
        assert 0 <= summary['win_rate'] <= 100, "Win rate should be 0-100%"
        
        print(f"\n✓ Portfolio metrics validated")
        return True
    else:
        print(f"\n✗ Portfolio summary failed")
        return False


def test_ticker_formats():
    """Test different ticker formats"""
    print("\n" + "="*80)
    print("TEST 4: Ticker Format Handling")
    print("="*80)
    
    test_cases = [
        ('INFY', 'Plain ticker'),
        ('SBIN', 'SBI corrected ticker'),
        ('TATAMOTORS', 'Multi-word ticker'),
        ('TCS', 'Short ticker')
    ]
    
    analyzer = IPOAnalyzer(investment_per_stock=15000)
    passed = 0
    failed = 0
    
    for ticker, description in test_cases:
        print(f"\nTesting: {ticker} ({description})")
        result = analyzer.analyze_single_stock(ticker)
        
        if result:
            print(f"  ✓ Success - CAGR: {result['cagr']:.2f}%")
            passed += 1
        else:
            print(f"  ✗ Failed to fetch data")
            failed += 1
    
    print(f"\nTicker Format Test Results:")
    print(f"  Passed: {passed}/{len(test_cases)}")
    print(f"  Failed: {failed}/{len(test_cases)}")
    
    return passed > 0


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("IPO BUY-AND-HOLD ANALYSIS - TEST SUITE")
    print("="*80)
    
    tests = [
        ("Single Stock Analysis", test_single_stock),
        ("Multiple Stocks Analysis", test_multiple_stocks),
        ("Portfolio Summary", test_portfolio_summary),
        ("Ticker Format Handling", test_ticker_formats)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST RESULTS SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nOverall: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed! IPO analysis is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed. Review errors above.")
        return 1


if __name__ == '__main__':
    exit(main())

