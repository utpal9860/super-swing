"""
YOLOv8 Chart Pattern Detection Integration
Detects complex chart patterns using computer vision
Complements TA-Lib candlestick patterns
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from typing import List, Dict, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

from utils.logger import setup_logger

logger = setup_logger("yolov8_patterns")

# Try to import dependencies
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    logger.warning("ultralytics not installed. YOLOv8 patterns unavailable.")
    YOLO_AVAILABLE = False

class YOLOv8PatternDetector:
    """
    Detects chart patterns using YOLOv8 computer vision
    
    Patterns detected:
    - Head and Shoulders (Top/Bottom)
    - M_Head (Double Top)
    - W_Bottom (Double Bottom)
    - Triangle
    - StockLine (Trendlines)
    """
    
    # Model from: https://huggingface.co/foduucom/stockmarket-pattern-detection-yolov8
    MODEL_PATH = "foduucom/stockmarket-pattern-detection-yolov8"
    
    PATTERN_CLASSES = [
        'Head and shoulders bottom',
        'Head and shoulders top', 
        'M_Head',
        'StockLine',
        'Triangle',
        'W_Bottom'
    ]
    
    def __init__(self, model_path: str = None):
        """
        Initialize YOLOv8 pattern detector
        
        Args:
            model_path: Path to YOLOv8 model (defaults to HuggingFace model)
        """
        if not YOLO_AVAILABLE:
            raise ImportError(
                "YOLOv8 patterns require: pip install ultralytics mss opencv-python"
            )
        
        self.model_path = model_path or self.MODEL_PATH
        self.model = None
        logger.info("YOLOv8 Pattern Detector initialized")
    
    def load_model(self):
        """Load YOLOv8 model"""
        try:
            logger.info(f"Loading YOLOv8 model from {self.model_path}...")
            self.model = YOLO(self.model_path)
            logger.info("YOLOv8 model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLOv8 model: {e}")
            raise
    
    def create_chart_image(
        self,
        df,
        ticker: str,
        save_path: Path = None
    ) -> Path:
        """
        Create a candlestick chart image from OHLCV data
        
        Args:
            df: DataFrame with OHLCV data
            ticker: Stock ticker
            save_path: Where to save chart image
        
        Returns:
            Path to saved chart image
        """
        if save_path is None:
            save_path = Path(f"temp_chart_{ticker}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
        
        # Create candlestick chart
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot candlesticks
        for idx, row in df.iterrows():
            color = 'green' if row['close'] >= row['open'] else 'red'
            
            # Candlestick body
            ax.plot([idx, idx], [row['low'], row['high']], color='black', linewidth=0.5)
            ax.plot([idx, idx], [row['open'], row['close']], color=color, linewidth=2)
        
        # Formatting
        ax.set_title(f"{ticker} - Candlestick Chart", fontsize=14, fontweight='bold')
        ax.set_xlabel("Date")
        ax.set_ylabel("Price")
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Chart image saved to {save_path}")
        return save_path
    
    def detect_patterns(self, image_path: Path) -> List[Dict]:
        """
        Detect chart patterns in an image
        
        Args:
            image_path: Path to chart image
        
        Returns:
            List of detected patterns with confidence scores
        """
        if self.model is None:
            self.load_model()
        
        logger.info(f"Detecting patterns in {image_path}...")
        
        # Run YOLOv8 detection
        results = self.model(image_path, save=False)
        
        detections = []
        
        if results and results[0].boxes:
            boxes = results[0].boxes
            
            for i in range(len(boxes)):
                class_id = int(boxes.cls[i].item())
                confidence = float(boxes.conf[i].item())
                bbox = boxes.xyxy[i].tolist()  # [x1, y1, x2, y2]
                
                pattern_name = self.PATTERN_CLASSES[class_id]
                
                detection = {
                    'pattern_type': pattern_name,
                    'confidence': confidence,
                    'bbox': bbox,
                    'class_id': class_id
                }
                
                detections.append(detection)
                logger.info(f"Detected: {pattern_name} (confidence: {confidence:.2%})")
        
        logger.info(f"Found {len(detections)} patterns")
        return detections
    
    def scan_stock_for_chart_patterns(
        self,
        ticker: str,
        df,
        min_confidence: float = 0.5
    ) -> List[Dict]:
        """
        Complete workflow: Create chart → Detect patterns
        
        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data
            min_confidence: Minimum confidence threshold
        
        Returns:
            List of detected chart patterns
        """
        # Create chart image
        chart_path = self.create_chart_image(df, ticker)
        
        # Detect patterns
        detections = self.detect_patterns(chart_path)
        
        # Filter by confidence
        filtered = [
            d for d in detections 
            if d['confidence'] >= min_confidence
        ]
        
        # Add metadata
        for detection in filtered:
            detection['ticker'] = ticker
            detection['detection_date'] = datetime.now().strftime('%Y-%m-%d')
            detection['detection_method'] = 'YOLOv8'
        
        # Clean up temp file
        if chart_path.exists():
            chart_path.unlink()
        
        return filtered

def integrate_yolov8_with_talib(
    ticker: str,
    df,
    talib_patterns: List[Dict],
    yolov8_detector: YOLOv8PatternDetector = None
) -> Dict:
    """
    Integrate YOLOv8 chart patterns with TA-Lib candlestick patterns
    
    Args:
        ticker: Stock ticker
        df: DataFrame with OHLCV data
        talib_patterns: List of TA-Lib detected patterns
        yolov8_detector: YOLOv8 detector instance
    
    Returns:
        Combined pattern analysis
    """
    if yolov8_detector is None:
        yolov8_detector = YOLOv8PatternDetector()
    
    # Detect chart patterns with YOLOv8
    chart_patterns = yolov8_detector.scan_stock_for_chart_patterns(ticker, df)
    
    # Combine results
    combined = {
        'ticker': ticker,
        'detection_date': datetime.now().strftime('%Y-%m-%d'),
        'talib_patterns': talib_patterns,
        'chart_patterns': chart_patterns,
        'total_patterns': len(talib_patterns) + len(chart_patterns),
        'has_confluence': len(talib_patterns) > 0 and len(chart_patterns) > 0
    }
    
    logger.info(f"{ticker}: {len(talib_patterns)} TA-Lib + {len(chart_patterns)} YOLOv8 patterns")
    
    return combined

if __name__ == "__main__":
    print("YOLOv8 Chart Pattern Detection")
    print("="*50)
    print("Patterns detected:")
    for i, pattern in enumerate(YOLOv8PatternDetector.PATTERN_CLASSES, 1):
        print(f"  {i}. {pattern}")
    print("\nSource: https://huggingface.co/foduucom/stockmarket-pattern-detection-yolov8")

