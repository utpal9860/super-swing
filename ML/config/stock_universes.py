"""
Stock Universe Definitions
Categorized by market cap: Large, Mid, Small (avoiding penny stocks)
"""

# Large Cap Stocks (Market Cap > ₹20,000 Cr, Top F&O stocks)
LARGE_CAP = [
    {'symbol': 'RELIANCE', 'name': 'Reliance Industries'},
    {'symbol': 'TCS', 'name': 'Tata Consultancy Services'},
    {'symbol': 'HDFCBANK', 'name': 'HDFC Bank'},
    {'symbol': 'INFY', 'name': 'Infosys'},
    {'symbol': 'ICICIBANK', 'name': 'ICICI Bank'},
    {'symbol': 'HINDUNILVR', 'name': 'Hindustan Unilever'},
    {'symbol': 'ITC', 'name': 'ITC Limited'},
    {'symbol': 'SBIN', 'name': 'State Bank of India'},
    {'symbol': 'BHARTIARTL', 'name': 'Bharti Airtel'},
    {'symbol': 'KOTAKBANK', 'name': 'Kotak Mahindra Bank'},
    {'symbol': 'LT', 'name': 'Larsen & Toubro'},
    {'symbol': 'AXISBANK', 'name': 'Axis Bank'},
    {'symbol': 'ASIANPAINT', 'name': 'Asian Paints'},
    {'symbol': 'MARUTI', 'name': 'Maruti Suzuki'},
    {'symbol': 'TITAN', 'name': 'Titan Company'},
    {'symbol': 'SUNPHARMA', 'name': 'Sun Pharmaceutical'},
    {'symbol': 'ULTRACEMCO', 'name': 'UltraTech Cement'},
    {'symbol': 'WIPRO', 'name': 'Wipro'},
    {'symbol': 'NESTLEIND', 'name': 'Nestle India'},
    {'symbol': 'HCLTECH', 'name': 'HCL Technologies'},
]

# Mid Cap Stocks (Market Cap ₹5,000-20,000 Cr, Good liquidity, Avoid penny stocks)
MID_CAP = [
    # Auto & Auto Components
    {'symbol': 'EICHERMOT', 'name': 'Eicher Motors'},
    {'symbol': 'BALKRISIND', 'name': 'Balkrishna Industries'},
    {'symbol': 'MRF', 'name': 'MRF Limited'},
    {'symbol': 'MOTHERSON', 'name': 'Motherson Sumi'},
    {'symbol': 'ASHOKLEY', 'name': 'Ashok Leyland'},
    
    # Banking & Finance
    {'symbol': 'INDUSINDBK', 'name': 'IndusInd Bank'},
    {'symbol': 'FEDERALBNK', 'name': 'Federal Bank'},
    {'symbol': 'BANKBARODA', 'name': 'Bank of Baroda'},
    {'symbol': 'CHOLAFIN', 'name': 'Cholamandalam Investment'},
    {'symbol': 'MUTHOOTFIN', 'name': 'Muthoot Finance'},
    {'symbol': 'BAJAJFINSV', 'name': 'Bajaj Finserv'},
    {'symbol': 'LICHSGFIN', 'name': 'LIC Housing Finance'},
    
    # Pharma & Healthcare
    {'symbol': 'TORNTPHARM', 'name': 'Torrent Pharmaceuticals'},
    {'symbol': 'AUROPHARMA', 'name': 'Aurobindo Pharma'},
    {'symbol': 'LUPIN', 'name': 'Lupin'},
    {'symbol': 'BIOCON', 'name': 'Biocon'},
    {'symbol': 'APOLLOHOSP', 'name': 'Apollo Hospitals'},
    {'symbol': 'DRREDDY', 'name': 'Dr. Reddys Laboratories'},
    
    # IT & Technology
    {'symbol': 'PERSISTENT', 'name': 'Persistent Systems'},
    {'symbol': 'COFORGE', 'name': 'Coforge'},
    {'symbol': 'MPHASIS', 'name': 'Mphasis'},
    {'symbol': 'LTTS', 'name': 'L&T Technology Services'},
    
    # Consumer Goods
    {'symbol': 'GODREJCP', 'name': 'Godrej Consumer Products'},
    {'symbol': 'MARICO', 'name': 'Marico'},
    {'symbol': 'DABUR', 'name': 'Dabur India'},
    {'symbol': 'COLPAL', 'name': 'Colgate-Palmolive'},
    {'symbol': 'BRITANNIA', 'name': 'Britannia Industries'},
    {'symbol': 'TATACONSUM', 'name': 'Tata Consumer Products'},
    
    # Cement & Construction
    {'symbol': 'SHREECEM', 'name': 'Shree Cement'},
    {'symbol': 'AMBUJACEM', 'name': 'Ambuja Cements'},
    {'symbol': 'ACC', 'name': 'ACC Limited'},
    {'symbol': 'GRASIM', 'name': 'Grasim Industries'},
    
    # Metals & Mining
    {'symbol': 'HINDALCO', 'name': 'Hindalco Industries'},
    {'symbol': 'VEDL', 'name': 'Vedanta'},
    {'symbol': 'JINDALSTEL', 'name': 'Jindal Steel & Power'},
    {'symbol': 'SAIL', 'name': 'SAIL'},
    
    # Energy & Power
    {'symbol': 'TATAPOWER', 'name': 'Tata Power'},
    {'symbol': 'ADANIGREEN', 'name': 'Adani Green Energy'},
    {'symbol': 'ADANIPOWER', 'name': 'Adani Power'},
    
    # Others
    {'symbol': 'PIIND', 'name': 'PI Industries'},
    {'symbol': 'SRF', 'name': 'SRF Limited'},
    {'symbol': 'PIDILITIND', 'name': 'Pidilite Industries'},
    {'symbol': 'BERGEPAINT', 'name': 'Berger Paints'},
    {'symbol': 'DIXON', 'name': 'Dixon Technologies'},
]

# Small Cap Stocks (Market Cap ₹1,000-5,000 Cr, High growth potential)
SMALL_CAP = [
    # Auto & Components
    {'symbol': 'SONACOMS', 'name': 'Sona BLW Precision'},
    {'symbol': 'ENDURANCE', 'name': 'Endurance Technologies'},
    {'symbol': 'SUPRAJIT', 'name': 'Suprajit Engineering'},
    
    # Chemicals & Materials
    {'symbol': 'CLEAN', 'name': 'Clean Science & Technology'},
    {'symbol': 'AAVAS', 'name': 'Aavas Financiers'},
    {'symbol': 'FINEORG', 'name': 'Fine Organic Industries'},
    {'symbol': 'ALKYLAMINE', 'name': 'Alkyl Amines Chemicals'},
    
    # Engineering & Capital Goods
    {'symbol': 'KEI', 'name': 'KEI Industries'},
    {'symbol': 'CESC', 'name': 'CESC Limited'},
    {'symbol': 'SYMPHONY', 'name': 'Symphony Limited'},
    {'symbol': 'POLYCAB', 'name': 'Polycab India'},
    
    # Consumer & Retail
    {'symbol': 'TRENT', 'name': 'Trent Limited'},
    {'symbol': 'JUBLFOOD', 'name': 'Jubilant Foodworks'},
    {'symbol': 'RELAXO', 'name': 'Relaxo Footwears'},
    {'symbol': 'VBL', 'name': 'Varun Beverages'},
    
    # Healthcare
    {'symbol': 'LALPATHLAB', 'name': 'Dr. Lal PathLabs'},
    {'symbol': 'METROPOLIS', 'name': 'Metropolis Healthcare'},
    {'symbol': 'THYROCARE', 'name': 'Thyrocare Technologies'},
    
    # IT & Services
    {'symbol': 'ROUTE', 'name': 'Route Mobile'},
    {'symbol': 'HFCL', 'name': 'HFCL Limited'},
    {'symbol': 'HAPPSTMNDS', 'name': 'Happiest Minds Technologies'},
    
    # NBFC & Finance
    {'symbol': 'CANBK', 'name': 'Canara Bank'},
    {'symbol': 'PNB', 'name': 'Punjab National Bank'},
    {'symbol': 'IIFLWAM', 'name': 'IIFL Wealth Management'},
    
    # Specialty Sectors
    {'symbol': 'APARINDS', 'name': 'Apar Industries'},
    {'symbol': 'TIINDIA', 'name': 'Tube Investments of India'},
    {'symbol': 'CHAMBLFERT', 'name': 'Chambal Fertilizers'},
    {'symbol': 'DEEPAKNTR', 'name': 'Deepak Nitrite'},
]

# Combined universes for easy selection
STOCK_UNIVERSES = {
    # Test
    'test': LARGE_CAP[:3],
    
    # By market cap
    'large_cap': LARGE_CAP,
    'mid_cap': MID_CAP,
    'small_cap': SMALL_CAP,
    
    # Mixed universes
    'mid_and_small': MID_CAP + SMALL_CAP,
    'all_caps': LARGE_CAP + MID_CAP + SMALL_CAP,
    
    # Sector-focused (from mid/small caps)
    'auto_mid_small': [s for s in MID_CAP + SMALL_CAP if any(x in s['name'].upper() for x in ['AUTO', 'EICHER', 'MOTHER', 'ENDURANCE'])],
    'pharma_mid_small': [s for s in MID_CAP + SMALL_CAP if any(x in s['name'].upper() for x in ['PHARMA', 'LAB', 'BIO', 'HEALTH', 'HOSPITAL'])],
    'it_mid_small': [s for s in MID_CAP + SMALL_CAP if any(x in s['name'].upper() for x in ['TECH', 'SYSTEM', 'SOFTWARE', 'MINDS', 'COFORGE'])],
    
    # Legacy (for backward compatibility)
    'fno_top10': LARGE_CAP[:10],
    'fno_top20': LARGE_CAP,
    'nifty50_top25': LARGE_CAP,
}

# Metadata
UNIVERSE_INFO = {
    'test': {'label': 'Test (3 stocks)', 'description': 'Quick test with top 3 large caps'},
    'large_cap': {'label': 'Large Cap', 'description': '₹20,000+ Cr market cap, high liquidity'},
    'mid_cap': {'label': 'Mid Cap', 'description': '₹5,000-20,000 Cr market cap, good growth potential'},
    'small_cap': {'label': 'Small Cap', 'description': '₹1,000-5,000 Cr market cap, high growth potential'},
    'mid_and_small': {'label': 'Mid + Small Cap', 'description': 'Combined mid and small caps for swing trading'},
    'all_caps': {'label': 'All Market Caps', 'description': 'Complete universe across all market caps'},
    'auto_mid_small': {'label': 'Auto (Mid/Small)', 'description': 'Auto sector mid and small caps'},
    'pharma_mid_small': {'label': 'Pharma (Mid/Small)', 'description': 'Pharma sector mid and small caps'},
    'it_mid_small': {'label': 'IT (Mid/Small)', 'description': 'IT sector mid and small caps'},
    'fno_top10': {'label': 'F&O Top 10', 'description': 'Top 10 F&O stocks (large cap)'},
    'fno_top20': {'label': 'F&O Top 20', 'description': 'Top 20 F&O stocks (large cap)'},
    'nifty50_top25': {'label': 'Nifty 50 Top 25', 'description': 'Top 25 Nifty 50 stocks'},
}


def get_universe(name: str):
    """Get stock universe by name"""
    return STOCK_UNIVERSES.get(name, STOCK_UNIVERSES['test'])


def get_universe_info(name: str):
    """Get universe metadata"""
    return UNIVERSE_INFO.get(name, {'label': name, 'description': 'Custom universe'})


def list_universes():
    """List all available universes"""
    return list(STOCK_UNIVERSES.keys())


# Example usage
if __name__ == '__main__':
    print("="*80)
    print("STOCK UNIVERSE DEFINITIONS")
    print("="*80)
    
    for name, universe in STOCK_UNIVERSES.items():
        info = get_universe_info(name)
        print(f"\n{info['label']} ({name})")
        print(f"  {info['description']}")
        print(f"  Stocks: {len(universe)}")
        if len(universe) <= 5:
            for stock in universe:
                print(f"    - {stock['symbol']}: {stock['name']}")

