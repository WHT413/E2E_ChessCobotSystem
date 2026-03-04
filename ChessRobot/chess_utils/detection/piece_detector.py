"""
Chess piece detection module using YOLO object detection.

This module provides functionality for detecting and classifying
chess pieces in images with confidence scoring and visualization.
"""

import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Dict, Tuple, Optional

from ..utils.config import get_config

class PieceDetector:
    """
    Chess piece detection using YOLO model.
    Detects and visualizes chess pieces in images.
    """
    
    # Chess piece class names
    CLASS_NAMES = [
        "white_king", "white_queen", "white_rook", "white_bishop", 
        "white_knight", "white_pawn", "black_king", "black_queen", 
        "black_rook", "black_bishop", "black_knight", "black_pawn"
    ]
    
    def __init__(self, model_path: Optional[str] = None, 
                 conf_threshold: Optional[float] = None, 
                 output_size: Optional[Tuple[int, int]] = None):
        """
        Initialize the chess piece detector.
        
        Args:
            model_path: Path to the YOLO model weights. If None, uses config.
            conf_threshold: Confidence threshold for detections. If None, uses config.
            output_size: Size for output visualization. If None, uses config.
        """
        config = get_config()
        
        if model_path is None:
            model_path = config.get_model_path('pieces')
        
        if conf_threshold is None:
            conf_threshold = config.get('models.pieces.confidence_threshold', 0.5)
            
        if output_size is None:
            output_size = tuple(config.get('processing.output_size', [640, 640]))
        
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.output_size = output_size
    
    def load_image(self, image_path: str) -> np.ndarray:
        """
        Load an image from file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Loaded image as numpy array
            
        Raises:
            ValueError: If image cannot be loaded
        """
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Error loading image from {image_path}")
        return image
    
    def detect_pieces(self, image: np.ndarray) -> List:
        """
        Detect chess pieces in the image.
        
        Args:
            image: Input image
            
        Returns:
            YOLO detection results
        """
        return self.model(image)
    
    def process_detections(self, results: List, image: np.ndarray) -> Tuple[np.ndarray, List[Dict]]:
        """
        Process detection results and annotate image.
        
        Args:
            results: YOLO detection results
            image: Image to annotate
            
        Returns:
            Tuple of (annotated_image, detected_pieces_list)
        """
        detected_pieces = []
        annotated_image = image.copy()
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                conf = box.conf[0].cpu().numpy()
                if conf < self.conf_threshold:
                    continue  # Skip low confidence detections
                
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
                
                class_id = int(box.cls[0].cpu().numpy())
                class_name = self.CLASS_NAMES[class_id]
                
                # Draw bounding box and label
                cv2.rectangle(annotated_image, (x1, y1), (x2, y2), (150, 0, 200), 3)
                
                piece_info = {
                    'class_name': class_name,
                    'confidence': float(conf),
                    'box': (x1, y1, x2, y2)
                }
                detected_pieces.append(piece_info)
                
        return annotated_image, detected_pieces
    
    def visualize(self, image: np.ndarray, window_name: str = "Chess Pieces Detection"):
        """
        Resize and display the image.
        
        Args:
            image: Image to display
            window_name: Name of the display window
        """
        resized_image = cv2.resize(image, self.output_size)
        cv2.imshow(window_name, resized_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    def run(self, image_path: str) -> List[Dict]:
        """
        Run the complete detection pipeline on an image.
        
        Args:
            image_path: Path to the image
            
        Returns:
            List of detected pieces with their information
        """
        # Load image
        image = self.load_image(image_path)
        
        # Detect pieces
        results = self.detect_pieces(image)
        
        # Process and visualize
        annotated_image, detected_pieces = self.process_detections(results, image)
        
        # Display results
        self.visualize(annotated_image)
        
        # Print detection info
        for piece in detected_pieces:
            print(f"Class name: {piece['class_name']}, Conf: {piece['confidence']:.2f}")
            
        return detected_pieces
