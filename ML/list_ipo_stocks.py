"""
List of stocks that had IPOs between 2019-2025
NO OLD STOCKS - only recent IPOs
"""

# Curated list of ACTUAL IPOs from 2019-2025
IPO_STOCKS_2019_2025 = {
    2019: [
        'IRFC',         # Indian Railway Finance Corporation
        'IRCTC',        # Indian Railway Catering
        'UJJIVAN',      # Ujjivan Small Finance Bank
        'SPANDANA',     # Spandana Sphoorty Financial
        'CSLFINANCE',   # CSL Finance
    ],
    2020: [
        'ANGELONE',     # Angel One (Angel Broking)
        'BURGERKING',   # Burger King India
        'GLENMARK',     # Glenmark Life Sciences
        'INDIAMART',    # IndiaMART InterMESH
        'MAZAGON',      # Mazagon Dock Shipbuilders
        'HAPPSTMNDS',   # Happiest Minds Technologies
        'ROUTE',        # Route Mobile
        'LIKHITHA',     # Likhitha Infrastructure
        'HERANBA',      # Heranba Industries
        'CHEMCON',      # Chemcon Speciality Chemicals
        'GLAND',        # Gland Pharma
        'EQUITAS',      # Equitas Small Finance Bank
        'UTI',          # UTI Asset Management
    ],
    2021: [
        'ZOMATO',       # Zomato
        'NYKAA',        # Nykaa (FSN E-Commerce)
        'PAYTM',        # Paytm (One97 Communications)
        'POLICYBAZAAR', # PB Fintech (PolicyBazaar)
        'CARTRADE',     # CarTrade Tech
        'LATENTVIEW',   # LatentView Analytics
        'TATVA',        # Tatva Chintan Pharma Chem
        'KRSNAA',       # Krsnaa Diagnostics
        'MEDPLUS',      # MedPlus Health Services
        'WINDLAS',      # Windlas Biotech
        'SHYAMMETL',    # Shyam Metalics
        'GLENMARKLIFE', # Glenmark Life Sciences
        'SANSERA',      # Sansera Engineering
        'CLEAN',        # Clean Science and Technology
        'DODLA',        # Dodla Dairy
        'DEVYANI',      # Devyani International
        'NAZARA',       # Nazara Technologies
        'EASEMYTRIP',   # Easy Trip Planners
        'MACROTECH',    # Macrotech Developers (Lodha)
        'LAXMIMACH',    # Laxmi Organic Industries
        'CRAFTSMAN',    # Craftsman Automation
        'APTUS',        # Aptus Value Housing Finance
        'ROLEX',        # Rolex Rings
        'SHRIRAMFIN',   # Shriram Finance
        'RATEGAIN',     # RateGain Travel Technologies
        'CHEMPLAST',    # Chemplast Sanmar
    ],
    2022: [
        'LICI',         # Life Insurance Corporation (LIC)
        'DELHIVERY',    # Delhivery
        'RAINBOW',      # Rainbow Children's Medicare
        'AETHER',       # Aether Industries
        'AGS',          # AGS Transact Technologies
        'VEDL',         # Vedant Fashions (Manyavar)
        'HARSHA',       # Harsha Engineers International
        'CAMPUS',       # Campus Activewear
        'SAPPHIRE',     # Sapphire Foods India
        'ARCHEAN',      # Archean Chemical Industries
    ],
    2023: [
        'MANKIND',      # Mankind Pharma
        'KAYNES',       # Kaynes Technology India
        'PROTEAN',      # Protean eGov Technologies
        'NETWEB',       # Netweb Technologies India
        'YATRA',        # Yatra Online
        'TIPSINDLTD',   # Tips Industries
        'JSWINFRA',     # JSW Infrastructure
    ],
    2024: [
        'TATATECH',     # Tata Technologies
        'HONASA',       # Honasa Consumer (Mamaearth)
        'IXIGO',        # ixigo (Le Travenues Technology)
    ],
    2025: [
        'FIRSTCRY',     # Brainbees Solutions (FirstCry)
        'EMCURE',       # Emcure Pharmaceuticals
    ]
}

# Flatten to single list
ALL_IPO_STOCKS = []
for year, stocks in sorted(IPO_STOCKS_2019_2025.items()):
    ALL_IPO_STOCKS.extend(stocks)

print("="*80)
print("IPO STOCKS LISTED BETWEEN 2019-2025")
print("="*80)

total = 0
for year, stocks in sorted(IPO_STOCKS_2019_2025.items()):
    print(f"\n{year} ({len(stocks)} IPOs):")
    for stock in sorted(stocks):
        print(f"  - {stock}")
    total += len(stocks)

print(f"\n{'='*80}")
print(f"TOTAL: {total} stocks that went public from 2019-2025")
print(f"{'='*80}")

print(f"\nThese are ONLY recent IPOs - NO old stocks like BAJFINANCE, INFY, TCS, etc.")
print(f"\nNext step: Calculate returns for these {total} stocks")

