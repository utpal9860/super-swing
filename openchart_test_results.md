# OpenChart Library Test Results

## Summary

**YES, OpenChart CAN fetch historical option OHLC data from NSE!**

## Test Results

### ✅ What Works:
1. **Library Installation**: Successfully installed and imported
2. **Master Data Download**: Can download NSE and NFO master data (84,790 NFO symbols)
3. **Option Symbol Search**: Can find option symbols in NFO exchange
4. **Historical Data API**: NSE API returns historical OHLC data for options

### 📊 Test Data Retrieved:
For `PRESTIGE25DEC1680CE` (PRESTIGE 30 Dec 2025 CE 1680.00):
- **4 days of historical data** (Dec 2-5, 2025)
- **OHLC data available**: Open, High, Low, Close, Volume
- **Data format**: JSON with arrays for timestamps, open, high, low, close, volume

**Sample Data:**
```
Date       | Open  | High | Low   | Close | Volume
-----------|-------|------|-------|-------|--------
2025-12-02 | 38.65 | 48.9 | 37.6  | 40.7  | 15,300
2025-12-03 | 40.7  | 40.7 | 31.25 | 34.65 | 38,700
2025-12-04 | 32.0  | 44.25| 31.0  | 40.9  | 70,650
2025-12-05 | 46.35 | 61.0 | 44.55 | 53.35 | 3,736,800
```

**Key Finding**: The high on Dec 5 was **61.0**, which matches your observation!

### ⚠️ Current Issue:
The `openchart` library's `process_historical_data()` function expects a different data format than what the API returns. The API returns:
```json
{
  "s": "Ok",
  "t": [timestamps],
  "o": [opens],
  "h": [highs],
  "l": [lows],
  "c": [closes],
  "v": [volumes]
}
```

But the library expects:
```json
[
  [status, timestamp, open, high, low, close, volume],
  ...
]
```

## Recommendation

**OpenChart IS FEASIBLE** for fetching historical option OHLC data, but we need to:

1. **Fix the data processing function** in `openchart/utils.py` to handle the actual API response format
2. **OR create a custom wrapper** that processes the API response correctly
3. **Integrate it into the EOD monitor** to fetch historical OHLC from trade entry date to today

## Next Steps

1. Modify `openchart/utils.py` to handle the correct API response format
2. Test with multiple option symbols and date ranges
3. Integrate into `webapp/api/eod_monitor.py` to replace the current manual tracking approach
4. Use it to fetch historical OHLC data from trade entry date to current date
5. Calculate max_high and min_low across all days since entry

## Code Example (Working)

```python
from openchart import NSEData
from datetime import datetime, timedelta
import json

nse = NSEData()
nse.download()

# Find option symbol
option = nse.nfo_data[nse.nfo_data['Symbol'] == 'PRESTIGE25DEC1680CE'].iloc[0]

# Fetch historical data
end_date = datetime.now()
start_date = end_date - timedelta(days=10)

payload = {
    'exch': 'D',  # NFO
    'instrType': 'D',  # Derivatives
    'scripCode': int(option['ScripCode']),
    'ulToken': int(option['ScripCode']),
    'fromDate': int(start_date.timestamp()),
    'toDate': int(end_date.timestamp()),
    'timeInterval': '1',
    'chartPeriod': 'D',
    'chartStart': 0
}

nse.session.get('https://www.nseindia.com', timeout=5)
response = nse.session.post(
    'https://charting.nseindia.com//Charts/symbolhistoricaldata/',
    data=json.dumps(payload),
    timeout=15
)

data = response.json()
# Process: data['t'] = timestamps, data['h'] = highs, data['l'] = lows, etc.
```

