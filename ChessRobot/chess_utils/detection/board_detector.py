"""
Chess board detection and corner extraction module.

This module provides functionality for detecting chess board corners
and cropping the board from images using YOLO object detection.
"""

import cv2
import numpy as np
from ultralytics import YOLO
from typing import Dict, Tuple, Optional
from pathlib import Path

from ..utils.config import get_config
from .fallback_corner_detector import detect_corners_fallback

class BoardDetector:
    """
    Chess board detection and cropping using YOLO corner detection.
    
    This class handles:
    - Loading corner detection model
    - Detecting four corners of a chess board
    - Cropping and perspective correction of the board
    """
    
    def __init__(self, model_path: Optional[str] = None, output_size: Tuple[int, int] = None):
        """
        Initialize the board detector.
        
        Args:
            model_path: Path to YOLO corner detection model. If None, uses config.
            output_size: Output size for cropped board. If None, uses config.
        """
        config = get_config()
        
        if model_path is None:
            model_path = config.get_model_path('corners')
        
        if output_size is None:
            output_size = tuple(config.get('processing.output_size', [640, 640]))
        
        self.model = YOLO(model_path)
        self.output_size = output_size

    def load_image(self, image_path: str) -> np.ndarray:
        """
        Load an image from file path.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Loaded image as numpy array
            
        Raises:
            ValueError: If image cannot be loaded
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Error loading image from {image_path}")
        return img

    def get_corners(self, img: np.ndarray) -> Optional[Dict[str, Tuple[int, int]]]:
        """
        Detect the four corners of a chess board in the image.
        
        Args:
            img: Input image
            
        Returns:
            Dictionary with corner positions or None if detection fails
            Format: {'top_left': (x, y), 'top_right': (x, y), 
                    'bottom_right': (x, y), 'bottom_left': (x, y)}
        """
        results = self.model(img, verbose=False)
        corners: Dict[str, Tuple[int, int]] = {}
        if results and hasattr(results[0], "boxes"):
            boxes = results[0].boxes.xyxy.cpu().numpy()
            scores = results[0].boxes.conf.cpu().numpy()
            classes = results[0].boxes.cls.cpu().numpy()

            # Mapping from class ID to corner name
            class2corner = {
                0: "white_left",
                1: "white_right",
                2: "black_left",
                3: "black_right",
            }

            confidence_threshold = get_config().get(
                "models.corners.confidence_threshold", 0.5
            )

            for box, score, cls in zip(boxes, scores, classes):
                if score > confidence_threshold and int(cls) in class2corner:
                    x1, y1, x2, y2 = box
                    # Use center of bounding box as corner position
                    x, y = int((x1 + x2) / 2), int((y1 + y2) / 2)
                    corners[class2corner[int(cls)]] = (x, y)

        # If the model fails to detect all four corners, fall back to
        # the classical corner detector inspired by chesscog.
        if len(corners) != 4:
            print("Falling back to classical corner detector...")
            return detect_corners_fallback(img)

        return corners

    def crop_board(self, img: np.ndarray, corners: Dict[str, Tuple[int, int]]) -> np.ndarray:
        """
        Crop and perspective-correct the chess board using detected corners.
        
        Args:
            img: Original image
            corners: Dictionary with four corner positions
            
        Returns:
            Cropped and perspective-corrected board image
        """
        # Source points from detected corners
        pts_src = np.float32([
            corners['top_left'],
            corners['top_right'],
            corners['bottom_right'],
            corners['bottom_left']
        ])
        
        # Destination points for perspective correction
        pts_dst = np.float32([
            [0, 0],
            [self.output_size[0] - 1, 0],
            [self.output_size[0] - 1, self.output_size[1] - 1],
            [0, self.output_size[1] - 1]
        ])
        
        # Compute perspective transformation matrix
        M = cv2.getPerspectiveTransform(pts_src, pts_dst)
        
        # Apply perspective transformation
        result = cv2.warpPerspective(img, M, self.output_size)
        
        return result
 