"""
Performance tracking for models and trading signals
Monitors model accuracy and triggers retraining when needed
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from database.schema import get_connection
from utils.logger import setup_logger

logger = setup_logger("performance_tracker")

class PerformanceTracker:
    """
    Tracks performance of ML models and trading signals
    Monitors degradation and triggers retraining
    """
    
    def __init__(self):
        """Initialize performance tracker"""
        self.db_conn = None
        logger.info("Performance Tracker initialized")
    
    def track_signal_performance(self, days_lookback: int = 30) -> Dict:
        """
        Track performance of generated signals
        
        Args:
            days_lookback: Number of days to look back
        
        Returns:
            Dictionary with performance metrics
        """
        logger.info(f"Tracking signal performance for last {days_lookback} days...")
        
        conn = get_connection()
        query = f'''
            SELECT 
                s.ticker,
                s.signal_date,
                s.entry_price,
                s.success_probability,
                s.expected_gain_pct,
                o.target_hit,
                o.stop_hit,
                o.gain_loss_pct
            FROM trading_signals s
            LEFT JOIN pattern_outcomes o ON s.pattern_id = o.pattern_id
            WHERE s.signal_date >= date('now', '-{days_lookback} days')
            AND s.status = 'COMPLETED'
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            logger.warning("No completed signals found")
            return {}
        
        # Calculate metrics
        total_signals = len(df)
        successful_signals = df['target_hit'].sum()
        failed_signals = df['stop_hit'].sum()
        
        win_rate = successful_signals / total_signals if total_signals > 0 else 0
        avg_gain = df['gain_loss_pct'].mean()
        
        # Model accuracy
        predicted_success = df['success_probability'] >= 0.6
        actual_success = df['target_hit'] == 1
        model_accuracy = (predicted_success == actual_success).mean()
        
        metrics = {
            'total_signals': total_signals,
            'successful_signals': successful_signals,
            'failed_signals': failed_signals,
            'win_rate': win_rate,
            'avg_gain': avg_gain,
            'model_accuracy': model_accuracy,
            'tracking_period_days': days_lookback,
        }
        
        logger.info(f"Performance Metrics:")
        logger.info(f"  Win Rate: {win_rate:.2%}")
        logger.info(f"  Avg Gain: {avg_gain:.2f}%")
        logger.info(f"  Model Accuracy: {model_accuracy:.2%}")
        
        return metrics
    
    def check_model_drift(self, baseline_accuracy: float = 0.65) -> bool:
        """
        Check if model performance has drifted
        
        Args:
            baseline_accuracy: Expected baseline accuracy
        
        Returns:
            True if model needs retraining
        """
        metrics = self.track_signal_performance(days_lookback=30)
        
        if not metrics:
            return False
        
        current_accuracy = metrics.get('model_accuracy', 1.0)
        
        # Check if accuracy dropped significantly
        if current_accuracy < baseline_accuracy * 0.85:  # 15% drop
            logger.warning(f"Model drift detected! Accuracy: {current_accuracy:.2%} (baseline: {baseline_accuracy:.2%})")
            return True
        
        logger.info(f"Model performance stable: {current_accuracy:.2%}")
        return False
    
    def analyze_pattern_performance(self) -> pd.DataFrame:
        """
        Analyze performance by pattern type
        
        Returns:
            DataFrame with pattern-level metrics
        """
        logger.info("Analyzing pattern performance...")
        
        conn = get_connection()
        query = '''
            SELECT 
                p.pattern_type,
                COUNT(*) as total_occurrences,
                SUM(CASE WHEN o.target_hit = 1 THEN 1 ELSE 0 END) as successes,
                AVG(o.gain_loss_pct) as avg_gain,
                AVG(o.actual_holding_days) as avg_holding_days
            FROM patterns p
            LEFT JOIN pattern_outcomes o ON p.pattern_id = o.pattern_id
            WHERE p.validation_status = 'VALID'
            GROUP BY p.pattern_type
            HAVING total_occurrences >= 5
            ORDER BY successes DESC
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df.empty:
            df['win_rate'] = df['successes'] / df['total_occurrences']
            logger.info(f"\nPattern Performance Analysis:")
            logger.info(df.to_string(index=False))
        
        return df
    
    def generate_performance_report(self) -> Dict:
        """
        Generate comprehensive performance report
        
        Returns:
            Dictionary with full performance report
        """
        logger.info("="*60)
        logger.info("GENERATING PERFORMANCE REPORT")
        logger.info("="*60)
        
        report = {}
        
        # Overall signal performance
        report['signal_performance'] = self.track_signal_performance(days_lookback=30)
        
        # Pattern-level analysis
        report['pattern_performance'] = self.analyze_pattern_performance()
        
        # Model drift check
        report['needs_retraining'] = self.check_model_drift()
        
        # Save report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = Path(f"ML/data/performance_report_{timestamp}.txt")
        
        with open(report_file, 'w') as f:
            f.write("ML PATTERN TRADING SYSTEM - PERFORMANCE REPORT\n")
            f.write("="*60 + "\n")
            f.write(f"Generated: {datetime.now()}\n\n")
            
            f.write("SIGNAL PERFORMANCE (Last 30 Days)\n")
            f.write("-"*60 + "\n")
            for key, value in report['signal_performance'].items():
                f.write(f"{key}: {value}\n")
            
            f.write("\nPATTERN PERFORMANCE\n")
            f.write("-"*60 + "\n")
            if not report['pattern_performance'].empty:
                f.write(report['pattern_performance'].to_string(index=False))
            
            f.write(f"\n\nRECOMMENDATION\n")
            f.write("-"*60 + "\n")
            if report['needs_retraining']:
                f.write("⚠️  MODEL RETRAINING RECOMMENDED\n")
            else:
                f.write("✓  Models performing well, no retraining needed\n")
        
        logger.info(f"Report saved to {report_file}")
        
        return report

if __name__ == "__main__":
    tracker = PerformanceTracker()
    report = tracker.generate_performance_report()
    
    print("\n" + "="*60)
    print("PERFORMANCE SUMMARY")
    print("="*60)
    print(f"Win Rate: {report['signal_performance'].get('win_rate', 0):.2%}")
    print(f"Avg Gain: {report['signal_performance'].get('avg_gain', 0):.2f}%")
    print(f"Needs Retraining: {'YES' if report['needs_retraining'] else 'NO'}")
    print("="*60)

