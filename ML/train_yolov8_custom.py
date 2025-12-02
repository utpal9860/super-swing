"""
Train YOLOv8 on your custom chart pattern images
Requires: 500+ labeled images with bounding boxes
"""
from ultralytics import YOLO
import os

# Your dataset structure should be:
# dataset/
#   train/
#     images/
#     labels/  (YOLO format: class x_center y_center width height)
#   val/
#     images/
#     labels/

def train_custom_yolov8(data_yaml_path, epochs=50, imgsz=640):
    """
    Train YOLOv8 on your chart images
    
    Args:
        data_yaml_path: Path to dataset.yaml defining classes and paths
        epochs: Training epochs (50-100 for 500 images)
        imgsz: Image size (640 or 1280)
    """
    # Load pretrained model
    model = YOLO('yolov8n.pt')  # nano - fastest
    
    # Train
    results = model.train(
        data=data_yaml_path,
        epochs=epochs,
        imgsz=imgsz,
        patience=10,
        batch=16,
        project='chart_pattern_detector',
        name='custom_patterns'
    )
    
    return model

# Example dataset.yaml content:
"""
path: /path/to/dataset
train: train/images
val: val/images

names:
  0: trendline_breakout
  1: support_resistance
  2: triangle
  3: head_shoulders
  4: double_bottom
  5: channel
"""

if __name__ == '__main__':
    # Install first: pip install ultralytics
    
    # Create dataset.yaml with your classes
    # Label your 500 images using LabelImg or Roboflow
    # Then train:
    # model = train_custom_yolov8('dataset.yaml', epochs=100)
    
    print("Setup required:")
    print("1. Install: pip install ultralytics")
    print("2. Label images: Use LabelImg or Roboflow")
    print("3. Split: 80% train, 20% val")
    print("4. Update dataset.yaml path")
    print("5. Run training")



