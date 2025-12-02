"""
Complete ML Pattern Trading Workflow
Runs the entire pipeline from pattern detection to signal generation
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import argparse
from datetime import datetime

from database.schema import create_database
from pattern_detection.scanner import run_pattern_scan
from training.train_pipeline import run_training_pipeline
from signal_generator import MLSignalGenerator
from performance.tracker import PerformanceTracker
from utils.logger import setup_logger

logger = setup_logger("workflow")

def setup_system():
    """Initialize database and folders"""
    logger.info("Setting up ML Pattern Trading System...")
    create_database()
    logger.info("Setup complete!")

def scan_patterns(universe="FNO", lookback=730, recent=30):
    """Scan for patterns"""
    logger.info("\n" + "="*60)
    logger.info("PHASE 1: PATTERN DETECTION")
    logger.info("="*60 + "\n")
    
    patterns = run_pattern_scan(
        universe_type=universe,
        lookback_days=lookback,
        recent_patterns_days=recent,
        save_to_db=True
    )
    
    return patterns

def review_patterns():
    """Launch review interface"""
    logger.info("\n" + "="*60)
    logger.info("PHASE 2: MANUAL REVIEW")
    logger.info("="*60 + "\n")
    logger.info("Starting review interface...")
    logger.info("Access at http://localhost:5000")
    logger.info("Review detected patterns and label them as valid/invalid")
    logger.info("")
    logger.info("After reviewing 500-1000 patterns, proceed to training.")
    logger.info("")
    
    from review_interface.app import app
    app.run(debug=False, host='0.0.0.0', port=5000)

def train_models():
    """Train ML models"""
    logger.info("\n" + "="*60)
    logger.info("PHASE 3: ML MODEL TRAINING")
    logger.info("="*60 + "\n")
    
    models = run_training_pipeline()
    return models

def generate_signals(universe="FNO"):
    """Generate trading signals"""
    logger.info("\n" + "="*60)
    logger.info("PHASE 4: SIGNAL GENERATION")
    logger.info("="*60 + "\n")
    
    generator = MLSignalGenerator()
    generator.load_models()
    signals = generator.run(universe_type=universe)
    
    return signals

def track_performance():
    """Track system performance"""
    logger.info("\n" + "="*60)
    logger.info("PHASE 5: PERFORMANCE TRACKING")
    logger.info("="*60 + "\n")
    
    tracker = PerformanceTracker()
    report = tracker.generate_performance_report()
    
    return report

def main():
    """Main workflow orchestrator"""
    parser = argparse.ArgumentParser(
        description="ML Pattern Trading System - Complete Workflow"
    )
    parser.add_argument(
        "phase",
        choices=["setup", "scan", "review", "train", "signals", "performance", "all"],
        help="Which phase to run"
    )
    parser.add_argument(
        "--universe",
        type=str,
        default="FNO",
        choices=["FNO", "NIFTY50", "NIFTY100"],
        help="Stock universe"
    )
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("ML PATTERN TRADING SYSTEM")
    logger.info("="*60)
    logger.info(f"Phase: {args.phase.upper()}")
    logger.info(f"Universe: {args.universe}")
    logger.info(f"Started: {datetime.now()}")
    logger.info("="*60 + "\n")
    
    if args.phase == "setup":
        setup_system()
    
    elif args.phase == "scan":
        scan_patterns(universe=args.universe)
    
    elif args.phase == "review":
        review_patterns()
    
    elif args.phase == "train":
        train_models()
    
    elif args.phase == "signals":
        generate_signals(universe=args.universe)
    
    elif args.phase == "performance":
        track_performance()
    
    elif args.phase == "all":
        # Run complete workflow
        logger.info("Running COMPLETE workflow...")
        logger.info("This will take several hours for first run.\n")
        
        # Phase 1: Setup
        setup_system()
        
        # Phase 2: Scan
        scan_patterns(universe=args.universe)
        
        # Phase 3: Review (user interaction required)
        logger.info("\n⚠️  MANUAL REVIEW REQUIRED")
        logger.info("Please run: python run_complete_workflow.py review")
        logger.info("Review 500-1000 patterns before proceeding to training.\n")
        
        # Phases 4-6 require reviewed data
        logger.info("After review, run remaining phases:")
        logger.info("  python run_complete_workflow.py train")
        logger.info("  python run_complete_workflow.py signals")
        logger.info("  python run_complete_workflow.py performance")
    
    logger.info("\n" + "="*60)
    logger.info("WORKFLOW COMPLETE!")
    logger.info("="*60)

if __name__ == "__main__":
    main()

