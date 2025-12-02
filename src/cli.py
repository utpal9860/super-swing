"""CLI interface for SuperTrend scanner."""
import click
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    RAW_DATA_DIR, PROCESSED_DATA_DIR, OUTPUT_DIR,
    DEFAULT_ATR_PERIOD, DEFAULT_MULTIPLIER, DEFAULT_ABS_THRESHOLD
)
from scanner.data_fetcher import fetch_weekly, load_cached, fetch_symbols_from_csv
from scanner.signal_detector import detect_signals_for_symbol
from scanner.analyser import filter_trades, compute_summary_stats
from scanner.report import generate_full_report, write_csv
from scanner.utils import setup_logging, sanitize_symbol

logger = None


@click.group()
@click.option('--log-level', default='INFO', help='Logging level (DEBUG, INFO, WARNING, ERROR)')
def cli(log_level):
    """SuperTrend Scanner CLI - Analyze weekly SuperTrend signals."""
    global logger
    logger = setup_logging(log_level)


@cli.command()
@click.option('--symbols', required=True, type=click.Path(exists=True), 
              help='Path to CSV file with symbols')
@click.option('--start', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end', required=True, help='End date (YYYY-MM-DD)')
@click.option('--tf', default='1wk', help='Timeframe (default: 1wk)')
@click.option('--refresh', is_flag=True, help='Force refresh cached data')
@click.option('--parallel', default=5, help='Number of parallel downloads')
def fetch(symbols, start, end, tf, refresh, parallel):
    """Fetch weekly OHLCV data for symbols."""
    logger.info(f"Fetching data from {start} to {end}")
    
    # Load symbols
    symbols_df = fetch_symbols_from_csv(symbols)
    if symbols_df is None:
        click.echo("Error loading symbols file", err=True)
        return
    
    click.echo(f"Fetching data for {len(symbols_df)} symbols...")
    
    success_count = 0
    failed_symbols = []
    
    def fetch_symbol(row):
        symbol = row['full_symbol']
        
        # Check cache unless refresh is requested
        if not refresh:
            cached = load_cached(symbol, RAW_DATA_DIR)
            if cached is not None:
                return symbol, True, "cached"
        
        # Fetch new data
        df = fetch_weekly(symbol, start, end, RAW_DATA_DIR)
        if df is not None:
            return symbol, True, "fetched"
        return symbol, False, "failed"
    
    # Parallel fetching
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(fetch_symbol, row): row for _, row in symbols_df.iterrows()}
        
        with click.progressbar(length=len(symbols_df), label='Fetching') as bar:
            for future in as_completed(futures):
                symbol, success, status = future.result()
                if success:
                    success_count += 1
                else:
                    failed_symbols.append(symbol)
                bar.update(1)
    
    click.echo(f"\nCompleted: {success_count}/{len(symbols_df)} symbols fetched")
    if failed_symbols:
        click.echo(f"Failed symbols: {', '.join(failed_symbols)}")


@cli.command()
@click.option('--symbols', type=click.Path(exists=True), help='Path to symbols CSV (optional, uses cached if not provided)')
@click.option('--factor', default=DEFAULT_MULTIPLIER, type=float, help='SuperTrend multiplier')
@click.option('--atr', default=DEFAULT_ATR_PERIOD, type=int, help='ATR period')
@click.option('--output', type=click.Path(), help='Output CSV file (optional)')
def compute(symbols, factor, atr, output):
    """Compute SuperTrend for cached symbols."""
    logger.info(f"Computing SuperTrend (ATR={atr}, multiplier={factor})")
    
    # Get list of symbols
    if symbols:
        symbols_df = fetch_symbols_from_csv(symbols)
        if symbols_df is None:
            click.echo("Error loading symbols file", err=True)
            return
        symbol_list = symbols_df['full_symbol'].tolist()
    else:
        # Use all cached files
        symbol_list = [f.stem for f in RAW_DATA_DIR.glob("*.csv")]
        click.echo(f"Using {len(symbol_list)} cached symbols")
    
    if not symbol_list:
        click.echo("No symbols to process", err=True)
        return
    
    computed_count = 0
    
    with click.progressbar(symbol_list, label='Computing') as bar:
        for symbol in bar:
            # Load cached data
            df = load_cached(symbol, RAW_DATA_DIR)
            if df is None:
                logger.warning(f"No cached data for {symbol}")
                continue
            
            # Compute SuperTrend
            try:
                df_st, _ = detect_signals_for_symbol(symbol, df, atr, factor)
                
                # Save processed data
                output_path = PROCESSED_DATA_DIR / f"{sanitize_symbol(symbol)}_st.csv"
                df_st.to_csv(output_path, index=False)
                computed_count += 1
            except Exception as e:
                logger.error(f"Error computing SuperTrend for {symbol}: {str(e)}")
    
    click.echo(f"\nComputed SuperTrend for {computed_count}/{len(symbol_list)} symbols")


@cli.command()
@click.option('--symbols', type=click.Path(exists=True), help='Path to symbols CSV')
@click.option('--factor', default=DEFAULT_MULTIPLIER, type=float, help='SuperTrend multiplier')
@click.option('--atr', default=DEFAULT_ATR_PERIOD, type=int, help='ATR period')
@click.option('--abs-threshold', default=DEFAULT_ABS_THRESHOLD, type=float, 
              help='Absolute percentage threshold for filtering')
@click.option('--output', default='results.csv', help='Output CSV file')
@click.option('--include-open', is_flag=True, help='Include open trades')
@click.option('--parallel', default=5, help='Number of parallel computations')
def analyze(symbols, factor, atr, abs_threshold, output, include_open, parallel):
    """Analyze SuperTrend signals and find buy→sell pairs."""
    logger.info(f"Analyzing signals (ATR={atr}, multiplier={factor}, threshold={abs_threshold}%)")
    
    # Load symbols
    if symbols:
        symbols_df = fetch_symbols_from_csv(symbols)
        if symbols_df is None:
            click.echo("Error loading symbols file", err=True)
            return
        # Add sector column if available
        symbol_to_sector = dict(zip(symbols_df['full_symbol'], 
                                   symbols_df.get('sector', [None] * len(symbols_df))))
    else:
        # Use all cached files
        symbol_list = [f.stem for f in RAW_DATA_DIR.glob("*.csv")]
        symbols_df = pd.DataFrame({'full_symbol': symbol_list})
        symbol_to_sector = {}
        click.echo(f"Using {len(symbol_list)} cached symbols")
    
    if symbols_df.empty:
        click.echo("No symbols to analyze", err=True)
        return
    
    all_trades = []
    
    def analyze_symbol(row):
        symbol = row['full_symbol']
        sector = symbol_to_sector.get(symbol)
        
        # Load cached data
        df = load_cached(symbol, RAW_DATA_DIR)
        if df is None:
            return []
        
        try:
            # Detect signals
            df_st, trades = detect_signals_for_symbol(symbol, df, atr, factor, include_open)
            
            # Add sector to trades
            for trade in trades:
                trade['sector'] = sector
            
            return trades
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {str(e)}")
            return []
    
    # Parallel analysis
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(analyze_symbol, row): row for _, row in symbols_df.iterrows()}
        
        with click.progressbar(length=len(symbols_df), label='Analyzing') as bar:
            for future in as_completed(futures):
                trades = future.result()
                all_trades.extend(trades)
                bar.update(1)
    
    if not all_trades:
        click.echo("\nNo trades found", err=True)
        return
    
    # Convert to DataFrame
    trades_df = pd.DataFrame(all_trades)
    
    click.echo(f"\nTotal trades found: {len(trades_df)}")
    
    # Filter by absolute threshold
    filtered_df = trades_df.copy()
    if abs_threshold is not None:
        valid_trades = filtered_df.dropna(subset=['pct_change'])
        before_count = len(valid_trades)
        filtered_df = filtered_df[
            (filtered_df['pct_change'].isna()) | 
            (filtered_df['pct_change'].abs() < abs_threshold)
        ]
        after_count = len(filtered_df.dropna(subset=['pct_change']))
        click.echo(f"Trades with |%| < {abs_threshold}%: {after_count}/{before_count}")
    
    # Save results
    output_path = OUTPUT_DIR / output
    write_csv(filtered_df, output_path)
    click.echo(f"\nResults saved to: {output_path}")


@cli.command()
@click.option('--input', 'input_file', required=True, type=click.Path(exists=True),
              help='Input CSV file with trade results')
@click.option('--top', default=20, type=int, help='Number of top/bottom performers to show')
@click.option('--sector-breakdown', is_flag=True, help='Include sector breakdown')
@click.option('--output-dir', type=click.Path(), help='Output directory for reports')
def report(input_file, top, sector_breakdown, output_dir):
    """Generate reports from trade results."""
    logger.info(f"Generating report from {input_file}")
    
    # Load trades
    try:
        trades_df = pd.read_csv(input_file, parse_dates=['buy_date', 'sell_date'])
    except Exception as e:
        click.echo(f"Error loading input file: {str(e)}", err=True)
        return
    
    if trades_df.empty:
        click.echo("No trades in input file", err=True)
        return
    
    # Set output directory
    if output_dir is None:
        output_dir = OUTPUT_DIR
    
    # Generate full report
    generated = generate_full_report(
        trades_df, 
        output_dir, 
        prefix="report",
        include_summary=True,
        include_sector=sector_breakdown,
        top_n=top
    )
    
    click.echo(f"\nReport generated:")
    for key, path in generated.items():
        click.echo(f"  {key}: {path}")


@cli.command()
@click.option('--symbols', required=True, type=click.Path(exists=True), help='Path to symbols CSV')
@click.option('--start', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end', required=True, help='End date (YYYY-MM-DD)')
@click.option('--atr-periods', default='7,10,14', help='Comma-separated ATR periods')
@click.option('--multipliers', default='2,3,4', help='Comma-separated multipliers')
@click.option('--output', default='backtest_results.csv', help='Output CSV file')
@click.option('--parallel', default=5, help='Number of parallel workers')
def backtest(symbols, start, end, atr_periods, multipliers, output, parallel):
    """Run parameter sweep backtest."""
    logger.info("Running backtest with parameter sweep")
    
    # Parse parameters
    atr_list = [int(x.strip()) for x in atr_periods.split(',')]
    mult_list = [float(x.strip()) for x in multipliers.split(',')]
    
    click.echo(f"Testing {len(atr_list)} ATR periods × {len(mult_list)} multipliers = {len(atr_list) * len(mult_list)} combinations")
    
    # Load symbols
    symbols_df = fetch_symbols_from_csv(symbols)
    if symbols_df is None:
        click.echo("Error loading symbols file", err=True)
        return
    
    # Fetch data first
    click.echo("Fetching data...")
    for _, row in symbols_df.iterrows():
        symbol = row['full_symbol']
        df = load_cached(symbol, RAW_DATA_DIR)
        if df is None:
            fetch_weekly(symbol, start, end, RAW_DATA_DIR)
    
    backtest_results = []
    
    # Test each combination
    total_combos = len(atr_list) * len(mult_list)
    with click.progressbar(length=total_combos, label='Backtesting') as bar:
        for atr_period in atr_list:
            for multiplier in mult_list:
                all_trades = []
                
                for _, row in symbols_df.iterrows():
                    symbol = row['full_symbol']
                    df = load_cached(symbol, RAW_DATA_DIR)
                    
                    if df is None:
                        continue
                    
                    try:
                        _, trades = detect_signals_for_symbol(symbol, df, atr_period, multiplier)
                        all_trades.extend(trades)
                    except:
                        pass
                
                if all_trades:
                    trades_df = pd.DataFrame(all_trades)
                    valid_trades = trades_df.dropna(subset=['pct_change'])
                    
                    if len(valid_trades) > 0:
                        result = {
                            'atr_period': atr_period,
                            'multiplier': multiplier,
                            'total_trades': len(valid_trades),
                            'mean_return': valid_trades['pct_change'].mean(),
                            'median_return': valid_trades['pct_change'].median(),
                            'win_rate': (len(valid_trades[valid_trades['pct_change'] > 0]) / len(valid_trades)) * 100,
                            'mean_weeks_held': valid_trades['weeks_held'].mean(),
                            'trades_below_10pct': len(valid_trades[valid_trades['pct_change'].abs() < 10])
                        }
                        backtest_results.append(result)
                
                bar.update(1)
    
    # Save results
    if backtest_results:
        results_df = pd.DataFrame(backtest_results)
        output_path = OUTPUT_DIR / output
        results_df.to_csv(output_path, index=False)
        click.echo(f"\n\nBacktest results saved to: {output_path}")
        
        # Print summary
        click.echo("\nTop 5 parameter combinations by mean return:")
        top_5 = results_df.nlargest(5, 'mean_return')
        click.echo(top_5.to_string(index=False))
    else:
        click.echo("\nNo backtest results generated", err=True)


if __name__ == '__main__':
    cli()

