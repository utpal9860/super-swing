"""Report generation for trade results."""
import pandas as pd
import json
import logging
from pathlib import Path
from tabulate import tabulate

logger = logging.getLogger(__name__)


def write_csv(trades_df, filename):
    """
    Write trades to CSV file.
    
    Args:
        trades_df: DataFrame with trade data
        filename: Output CSV filename
    """
    try:
        trades_df.to_csv(filename, index=False)
        logger.info(f"Wrote {len(trades_df)} trades to {filename}")
        return True
    except Exception as e:
        logger.error(f"Error writing CSV: {str(e)}")
        return False


def write_json(data, filename):
    """
    Write data to JSON file.
    
    Args:
        data: Data to write (dict or list)
        filename: Output JSON filename
    """
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Wrote JSON to {filename}")
        return True
    except Exception as e:
        logger.error(f"Error writing JSON: {str(e)}")
        return False


def print_summary(stats, threshold_stats=None):
    """
    Print summary statistics to terminal.
    
    Args:
        stats: Dictionary of summary statistics
        threshold_stats: Dictionary of threshold analysis (optional)
    """
    print("\n" + "="*70)
    print("SUPERTREND ANALYSIS SUMMARY")
    print("="*70)
    
    if 'error' in stats:
        print(f"\nError: {stats['error']}")
        return
    
    # Basic stats
    print(f"\nTotal Trades: {stats.get('total_trades', 0)}")
    print(f"Total Symbols: {stats.get('total_symbols', 0)}")
    
    # Returns
    print(f"\n--- Returns ---")
    print(f"Mean Return:   {stats.get('mean_return', 0):>8.2f}%")
    print(f"Median Return: {stats.get('median_return', 0):>8.2f}%")
    print(f"Std Dev:       {stats.get('std_return', 0):>8.2f}%")
    print(f"Min Return:    {stats.get('min_return', 0):>8.2f}%")
    print(f"Max Return:    {stats.get('max_return', 0):>8.2f}%")
    print(f"Q25:           {stats.get('q25_return', 0):>8.2f}%")
    print(f"Q75:           {stats.get('q75_return', 0):>8.2f}%")
    
    # Win/Loss
    print(f"\n--- Win/Loss ---")
    print(f"Winning Trades: {stats.get('winning_trades', 0)}")
    print(f"Losing Trades:  {stats.get('losing_trades', 0)}")
    print(f"Win Rate:       {stats.get('win_rate', 0):.2f}%")
    
    # Holding period
    if stats.get('mean_weeks_held') is not None:
        print(f"\n--- Holding Period ---")
        print(f"Mean:   {stats.get('mean_weeks_held', 0):.1f} weeks")
        print(f"Median: {stats.get('median_weeks_held', 0):.1f} weeks")
        print(f"Min:    {stats.get('min_weeks_held', 0):.1f} weeks")
        print(f"Max:    {stats.get('max_weeks_held', 0):.1f} weeks")
    
    # Threshold analysis
    if threshold_stats:
        print(f"\n--- Threshold Analysis ---")
        for key, value in threshold_stats.items():
            threshold = key.replace('within_', '').replace('pct', '')
            print(f"Within ±{threshold}%: {value['count']} trades ({value['percentage']:.1f}%)")
    
    print("="*70 + "\n")


def print_trades_table(trades_df, title="Trades", max_rows=20):
    """
    Print trades in a formatted table.
    
    Args:
        trades_df: DataFrame with trade data
        title: Table title
        max_rows: Maximum number of rows to display
    """
    if trades_df.empty:
        print(f"\n{title}: No trades to display")
        return
    
    print(f"\n{title} (showing {min(len(trades_df), max_rows)} of {len(trades_df)})")
    print("-" * 100)
    
    # Select columns to display
    display_cols = ['symbol', 'buy_date', 'buy_price', 'sell_date', 'sell_price', 'pct_change', 'weeks_held']
    available_cols = [col for col in display_cols if col in trades_df.columns]
    
    # Format the dataframe for display
    df_display = trades_df[available_cols].head(max_rows).copy()
    
    # Format numeric columns
    if 'buy_price' in df_display.columns:
        df_display['buy_price'] = df_display['buy_price'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    if 'sell_price' in df_display.columns:
        df_display['sell_price'] = df_display['sell_price'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    if 'pct_change' in df_display.columns:
        df_display['pct_change'] = df_display['pct_change'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
    if 'weeks_held' in df_display.columns:
        df_display['weeks_held'] = df_display['weeks_held'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "")
    
    # Format dates
    if 'buy_date' in df_display.columns:
        df_display['buy_date'] = pd.to_datetime(df_display['buy_date']).dt.strftime('%Y-%m-%d')
    if 'sell_date' in df_display.columns:
        df_display['sell_date'] = pd.to_datetime(df_display['sell_date']).dt.strftime('%Y-%m-%d')
    
    print(tabulate(df_display, headers='keys', tablefmt='simple', showindex=False))
    print()


def print_sector_analysis(sector_stats):
    """
    Print sector-wise analysis.
    
    Args:
        sector_stats: Dictionary of sector statistics
    """
    if not sector_stats:
        return
    
    print("\n" + "="*70)
    print("SECTOR ANALYSIS")
    print("="*70 + "\n")
    
    # Convert to DataFrame for nice formatting
    sector_df = pd.DataFrame.from_dict(sector_stats, orient='index')
    sector_df = sector_df.sort_values('mean_return', ascending=False)
    
    # Format columns
    display_df = sector_df.copy()
    display_df['mean_return'] = display_df['mean_return'].apply(lambda x: f"{x:.2f}%")
    display_df['median_return'] = display_df['median_return'].apply(lambda x: f"{x:.2f}%")
    display_df['win_rate'] = display_df['win_rate'].apply(lambda x: f"{x:.1f}%")
    if 'mean_weeks_held' in display_df.columns:
        display_df['mean_weeks_held'] = display_df['mean_weeks_held'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "")
    
    print(tabulate(display_df, headers='keys', tablefmt='simple'))
    print()


def print_profit_loss_buckets(bucket_stats):
    """
    Print profit/loss bucket analysis.
    
    Args:
        bucket_stats: Dictionary with profit/loss bucket statistics
    """
    if not bucket_stats:
        return
    
    print("\n" + "="*70)
    print("PROFIT/LOSS BUCKET ANALYSIS")
    print("="*70)
    
    if 'summary' in bucket_stats:
        summary = bucket_stats['summary']
        print(f"\nTotal Trades: {summary['total_trades']}")
        print(f"Profitable: {summary['total_profits']} ({summary['profit_percentage']:.1f}%)")
        print(f"Losses: {summary['total_losses']} ({summary['loss_percentage']:.1f}%)")
        if summary['total_neutral'] > 0:
            print(f"Neutral: {summary['total_neutral']}")
    
    # Profit buckets table
    if 'profit_buckets' in bucket_stats and bucket_stats['profit_buckets']:
        print("\n--- PROFIT DISTRIBUTION ---")
        profit_data = []
        for bucket, data in bucket_stats['profit_buckets'].items():
            profit_data.append({
                'Range': bucket,
                'Count': data['count'],
                '% of Total': f"{data['percentage_of_total']:.1f}%",
                '% of Profits': f"{data['percentage_of_profits']:.1f}%"
            })
        
        print(tabulate(profit_data, headers='keys', tablefmt='grid'))
    
    # Loss buckets table
    if 'loss_buckets' in bucket_stats and bucket_stats['loss_buckets']:
        print("\n--- LOSS DISTRIBUTION ---")
        loss_data = []
        for bucket, data in bucket_stats['loss_buckets'].items():
            loss_data.append({
                'Range': bucket,
                'Count': data['count'],
                '% of Total': f"{data['percentage_of_total']:.1f}%",
                '% of Losses': f"{data['percentage_of_losses']:.1f}%"
            })
        
        print(tabulate(loss_data, headers='keys', tablefmt='grid'))
    
    print("="*70 + "\n")


def generate_full_report(trades_df, output_dir, prefix="supertrend", 
                        include_summary=True, include_sector=True, include_buckets=True, top_n=20):
    """
    Generate complete report with CSV, JSON, and terminal output.
    
    Args:
        trades_df: DataFrame with all trade data
        output_dir: Output directory
        prefix: Filename prefix
        include_summary: Include summary statistics
        include_sector: Include sector analysis
        include_buckets: Include profit/loss bucket analysis
        top_n: Number of top/bottom performers to show
        
    Returns:
        dict: Paths to generated files
    """
    from .analyser import (compute_summary_stats, analyze_by_sector, 
                          threshold_analysis, get_top_performers, profit_loss_buckets)
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated_files = {}
    
    # Write main trades CSV
    trades_csv = output_dir / f"{prefix}_trades.csv"
    if write_csv(trades_df, trades_csv):
        generated_files['trades_csv'] = str(trades_csv)
    
    # Compute statistics
    stats = compute_summary_stats(trades_df)
    threshold_stats = threshold_analysis(trades_df)
    bucket_stats = profit_loss_buckets(trades_df) if include_buckets else {}
    
    # Write summary JSON
    summary_json = output_dir / f"{prefix}_summary.json"
    summary_data = {
        'statistics': stats,
        'threshold_analysis': threshold_stats
    }
    
    if include_buckets and bucket_stats:
        summary_data['bucket_analysis'] = bucket_stats
    
    if include_sector and 'sector' in trades_df.columns:
        sector_stats = analyze_by_sector(trades_df)
        summary_data['sector_analysis'] = sector_stats
    
    if write_json(summary_data, summary_json):
        generated_files['summary_json'] = str(summary_json)
    
    # Print to terminal
    if include_summary:
        print_summary(stats, threshold_stats)
    
    # Print bucket analysis
    if include_buckets and bucket_stats:
        print_profit_loss_buckets(bucket_stats)
    
    # Print top/bottom performers
    if not trades_df.empty and 'pct_change' in trades_df.columns:
        top_performers = get_top_performers(trades_df, top_n=top_n, ascending=False)
        bottom_performers = get_top_performers(trades_df, top_n=top_n, ascending=True)
        
        print_trades_table(top_performers, f"Top {top_n} Performers", max_rows=top_n)
        print_trades_table(bottom_performers, f"Bottom {top_n} Performers", max_rows=top_n)
    
    # Print sector analysis
    if include_sector and 'sector' in trades_df.columns:
        sector_stats = analyze_by_sector(trades_df)
        print_sector_analysis(sector_stats)
    
    return generated_files

