"""
Grid overlay generation utilities.

This module provides functionality for generating and manipulating
grid overlays on chess board images.
"""

import cv2
import numpy as np
from typing import Tuple, List, Optional, Union

class GridBuilder:
    """
    Utility class for creating grid overlays on chess board images.
    """
    
    def __init__(self):
        """Initialize the grid builder."""
        pass
    
    def create_grid_overlay(
        self,
        image_shape: Tuple[int, int],
        grid_size: Tuple[int, int] = (8, 8),
        line_color: Tuple[int, int, int] = (0, 255, 0),
        line_thickness: int = 2,
        alpha: float = 0.7
    ) -> np.ndarray:
        """
        Create a grid overlay image.
        
        Args:
            image_shape: (height, width) of the target image
            grid_size: (rows, cols) for the grid
            line_color: RGB color for grid lines
            line_thickness: Thickness of grid lines
            alpha: Transparency for overlay
            
        Returns:
            Grid overlay image
        """
        height, width = image_shape
        rows, cols = grid_size
        
        # Create transparent overlay
        overlay = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Calculate grid spacing
        row_spacing = height // rows
        col_spacing = width // cols
        
        # Draw horizontal lines
        for i in range(1, rows):
            y = i * row_spacing
            cv2.line(overlay, (0, y), (width, y), line_color, line_thickness)
        
        # Draw vertical lines
        for i in range(1, cols):
            x = i * col_spacing
            cv2.line(overlay, (x, 0), (x, height), line_color, line_thickness)
        
        return overlay
    
    def apply_grid_overlay(
        self,
        image: np.ndarray,
        grid_size: Tuple[int, int] = (8, 8),
        line_color: Tuple[int, int, int] = (0, 255, 0),
        line_thickness: int = 2,
        alpha: float = 0.7
    ) -> np.ndarray:
        """
        Apply grid overlay to an image.
        
        Args:
            image: Input image
            grid_size: (rows, cols) for the grid
            line_color: RGB color for grid lines
            line_thickness: Thickness of grid lines
            alpha: Transparency for overlay
            
        Returns:
            Image with grid overlay applied
        """
        height, width = image.shape[:2]
        
        # Create grid overlay
        overlay = self.create_grid_overlay(
            (height, width), grid_size, line_color, line_thickness
        )
        
        # Blend with original image
        result = cv2.addWeighted(image, 1 - alpha, overlay, alpha, 0)
        
        return result
    
    def get_grid_coordinates(
        self,
        image_shape: Tuple[int, int],
        grid_size: Tuple[int, int] = (8, 8)
    ) -> List[List[Tuple[int, int, int, int]]]:
        """
        Get coordinates for each grid cell.
        
        Args:
            image_shape: (height, width) of the image
            grid_size: (rows, cols) for the grid
            
        Returns:
            2D list of (x1, y1, x2, y2) coordinates for each cell
        """
        height, width = image_shape
        rows, cols = grid_size
        
        row_spacing = height // rows
        col_spacing = width // cols
        
        grid_coords = []
        for i in range(rows):
            row_coords = []
            for j in range(cols):
                x1 = j * col_spacing
                y1 = i * row_spacing
                x2 = x1 + col_spacing
                y2 = y1 + row_spacing
                row_coords.append((x1, y1, x2, y2))
            grid_coords.append(row_coords)
        
        return grid_coords
    
    def get_cell_center(
        self,
        row: int,
        col: int,
        image_shape: Tuple[int, int],
        grid_size: Tuple[int, int] = (8, 8)
    ) -> Tuple[int, int]:
        """
        Get center coordinates of a specific grid cell.
        
        Args:
            row: Row index (0-based)
            col: Column index (0-based)
            image_shape: (height, width) of the image
            grid_size: (rows, cols) for the grid
            
        Returns:
            (x, y) center coordinates
        """
        height, width = image_shape
        rows, cols = grid_size
        
        row_spacing = height // rows
        col_spacing = width // cols
        
        center_x = col * col_spacing + col_spacing // 2
        center_y = row * row_spacing + row_spacing // 2
        
        return (center_x, center_y)
    
    def draw_cell_labels(
        self,
        image: np.ndarray,
        grid_size: Tuple[int, int] = (8, 8),
        font_scale: float = 0.5,
        font_color: Tuple[int, int, int] = (255, 255, 255),
        font_thickness: int = 1
    ) -> np.ndarray:
        """
        Draw chess notation labels on grid cells.
        
        Args:
            image: Input image
            grid_size: (rows, cols) for the grid
            font_scale: Scale of the font
            font_color: RGB color for text
            font_thickness: Thickness of text
            
        Returns:
            Image with cell labels
        """
        result = image.copy()
        height, width = image.shape[:2]
        rows, cols = grid_size
        
        # Chess notation
        files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        ranks = ['8', '7', '6', '5', '4', '3', '2', '1']
        
        for i in range(rows):
            for j in range(cols):
                if j < len(files) and i < len(ranks):
                    # Get cell center
                    center_x, center_y = self.get_cell_center(
                        i, j, (height, width), grid_size
                    )
                    
                    # Create label
                    label = f"{files[j]}{ranks[i]}"
                    
                    # Get text size for centering
                    text_size = cv2.getTextSize(
                        label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness
                    )[0]
                    
                    text_x = center_x - text_size[0] // 2
                    text_y = center_y + text_size[1] // 2
                    
                    cv2.putText(
                        result, label, (text_x, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale,
                        font_color, font_thickness
                    )
        
        return result
    
    def highlight_cells(
        self,
        image: np.ndarray,
        cells: List[Tuple[int, int]],
        grid_size: Tuple[int, int] = (8, 8),
        highlight_color: Tuple[int, int, int] = (255, 255, 0),
        alpha: float = 0.3
    ) -> np.ndarray:
        """
        Highlight specific grid cells.
        
        Args:
            image: Input image
            cells: List of (row, col) tuples to highlight
            grid_size: (rows, cols) for the grid
            highlight_color: RGB color for highlighting
            alpha: Transparency for highlight
            
        Returns:
            Image with highlighted cells
        """
        result = image.copy()
        height, width = image.shape[:2]
        
        # Create overlay for highlights
        overlay = np.zeros_like(image)
        
        grid_coords = self.get_grid_coordinates((height, width), grid_size)
        
        for row, col in cells:
            if 0 <= row < len(grid_coords) and 0 <= col < len(grid_coords[0]):
                x1, y1, x2, y2 = grid_coords[row][col]
                cv2.rectangle(overlay, (x1, y1), (x2, y2), highlight_color, -1)
        
        # Blend with original image
        result = cv2.addWeighted(result, 1 - alpha, overlay, alpha, 0)
        
        return result
