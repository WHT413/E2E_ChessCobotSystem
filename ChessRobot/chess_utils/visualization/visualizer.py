"""
Professional Chess Board Visualization Module

This module provides comprehensive visualization tools for chess piece detection
and board analysis with customizable styling and anti-aliased rendering.
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum

from ..utils.config import get_config

class PieceType(Enum):
    """Enumeration for chess piece types with color mapping."""
    WHITE_KING = "white_king"
    WHITE_QUEEN = "white_queen"
    WHITE_ROOK = "white_rook"
    WHITE_BISHOP = "white_bishop"
    WHITE_KNIGHT = "white_knight"
    WHITE_PAWN = "white_pawn"
    BLACK_KING = "black_king"
    BLACK_QUEEN = "black_queen"
    BLACK_ROOK = "black_rook"
    BLACK_BISHOP = "black_bishop"
    BLACK_KNIGHT = "black_knight"
    BLACK_PAWN = "black_pawn"

@dataclass
class VisualizationStyle:
    """Configuration class for all visualization parameters."""
    
    # Bounding box styles
    bbox_thickness: int = 3
    bbox_alpha: float = 0.9
    bbox_corner_radius: int = 8
    
    # Text styles
    font_face: int = cv2.FONT_HERSHEY_DUPLEX
    font_scale: float = 0.7
    font_thickness: int = 2
    text_alpha: float = 0.8
    text_outline_color: Tuple[int, int, int] = (0, 0, 0)
    text_outline_thickness: int = 3
    
    # Grid styles
    grid_color: Tuple[int, int, int] = (0, 255, 255)  # Cyan
    grid_thickness: int = 2
    grid_alpha: float = 0.6
    
    # Cell center markers
    cell_marker_radius: int = 4
    cell_marker_color: Tuple[int, int, int] = (255, 255, 255)
    cell_marker_alpha: float = 0.5
    
    # Cell highlighting
    occupied_cell_color: Tuple[int, int, int] = (0, 255, 0)  # Green
    conflict_cell_color: Tuple[int, int, int] = (0, 165, 255)  # Orange
    cell_highlight_alpha: float = 0.3
    
    # Board labels
    label_font_scale: float = 0.8
    label_color: Tuple[int, int, int] = (255, 255, 255)
    label_background_color: Tuple[int, int, int] = (0, 0, 0)
    label_alpha: float = 0.7

class ChessVisualizer:
    """
    Professional chess board visualization system with anti-aliased rendering
    and comprehensive styling options.
    """
    
    def __init__(self, style: Optional[VisualizationStyle] = None):
        """
        Initialize the visualizer with custom or default styling.
        
        Args:
            style: Custom visualization style configuration
        """
        self.style = style or VisualizationStyle()
        self.piece_colors = self._initialize_piece_colors()
        self.config = get_config()
        
    def _initialize_piece_colors(self) -> Dict[str, Tuple[int, int, int]]:
        """Initialize distinct colors for each piece type."""
        return {
            # White pieces - Blue tones
            "white_king": (255, 100, 100),     # Light red
            "white_queen": (255, 150, 100),    # Orange
            "white_rook": (255, 200, 100),     # Yellow-orange
            "white_bishop": (200, 255, 100),   # Light green
            "white_knight": (100, 255, 150),   # Cyan-green
            "white_pawn": (100, 200, 255),     # Light blue
            
            # Black pieces - Purple/Red tones
            "black_king": (128, 0, 128),       # Purple
            "black_queen": (255, 0, 128),      # Magenta
            "black_rook": (255, 0, 0),         # Red
            "black_bishop": (200, 0, 100),     # Dark magenta
            "black_knight": (150, 0, 200),     # Dark purple
            "black_pawn": (100, 0, 150),       # Dark violet
        }
    
    def _draw_rounded_rectangle(self, img: np.ndarray, pt1: Tuple[int, int], 
                               pt2: Tuple[int, int], color: Tuple[int, int, int], 
                               thickness: int, corner_radius: int) -> np.ndarray:
        """
        Draw a rounded rectangle with anti-aliasing.
        
        Args:
            img: Image to draw on
            pt1: Top-left corner
            pt2: Bottom-right corner
            color: BGR color
            thickness: Line thickness
            corner_radius: Corner radius in pixels
            
        Returns:
            Image with rounded rectangle
        """
        x1, y1 = pt1
        x2, y2 = pt2
        
        # Draw main rectangle parts
        cv2.line(img, (x1 + corner_radius, y1), (x2 - corner_radius, y1), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1 + corner_radius, y2), (x2 - corner_radius, y2), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1, y1 + corner_radius), (x1, y2 - corner_radius), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x2, y1 + corner_radius), (x2, y2 - corner_radius), color, thickness, cv2.LINE_AA)
        
        # Draw corner arcs
        cv2.ellipse(img, (x1 + corner_radius, y1 + corner_radius), (corner_radius, corner_radius), 
                   180, 0, 90, color, thickness, cv2.LINE_AA)
        cv2.ellipse(img, (x2 - corner_radius, y1 + corner_radius), (corner_radius, corner_radius), 
                   270, 0, 90, color, thickness, cv2.LINE_AA)
        cv2.ellipse(img, (x2 - corner_radius, y2 - corner_radius), (corner_radius, corner_radius), 
                   0, 0, 90, color, thickness, cv2.LINE_AA)
        cv2.ellipse(img, (x1 + corner_radius, y2 - corner_radius), (corner_radius, corner_radius), 
                   90, 0, 90, color, thickness, cv2.LINE_AA)
        
        return img
    
    def _draw_text_with_background(self, img: np.ndarray, text: str, 
                                  position: Tuple[int, int], color: Tuple[int, int, int],
                                  background_color: Tuple[int, int, int]) -> np.ndarray:
        """
        Draw text with semi-transparent background and outline.
        
        Args:
            img: Image to draw on
            text: Text to draw
            position: Text position (bottom-left corner)
            color: Text color
            background_color: Background color
            
        Returns:
            Image with text overlay
        """
        # Get text size
        text_size = cv2.getTextSize(text, self.style.font_face, 
                                   self.style.font_scale, self.style.font_thickness)[0]
        
        # Create background rectangle
        x, y = position
        padding = 8
        bg_pt1 = (x - padding, y - text_size[1] - padding)
        bg_pt2 = (x + text_size[0] + padding, y + padding)
        
        # Draw semi-transparent background
        overlay = img.copy()
        cv2.rectangle(overlay, bg_pt1, bg_pt2, background_color, -1)
        cv2.addWeighted(overlay, self.style.text_alpha, img, 1 - self.style.text_alpha, 0, img)
        
        # Draw text outline
        cv2.putText(img, text, position, self.style.font_face, self.style.font_scale,
                   self.style.text_outline_color, self.style.font_thickness + self.style.text_outline_thickness,
                   cv2.LINE_AA)
        
        # Draw main text
        cv2.putText(img, text, position, self.style.font_face, self.style.font_scale,
                   color, self.style.font_thickness, cv2.LINE_AA)
        
        return img
    
    def draw_piece_detection(self, img: np.ndarray, detection: Dict) -> np.ndarray:
        """
        Draw a single piece detection with bounding box and label.
        
        Args:
            img: Image to draw on
            detection: Detection dictionary with 'box', 'class_name', 'confidence'
            
        Returns:
            Image with piece detection visualization
        """
        x1, y1, x2, y2 = detection['box']
        class_name = detection['class_name']
        confidence = detection['confidence']
        
        # Get piece color
        piece_color = self.piece_colors.get(class_name, (255, 255, 255))
        
        # Draw rounded bounding box
        self._draw_rounded_rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)),
                                   piece_color, self.style.bbox_thickness, 
                                   self.style.bbox_corner_radius)
        
        # Prepare label text
        label_text = f"{class_name.replace('_', ' ').title()}"
        confidence_text = f"{confidence:.2f}"
        
        # Draw label with background
        label_pos = (int(x1), int(y1) - 10)
        self._draw_text_with_background(img, f"{label_text} ({confidence_text})",
                                       label_pos, piece_color, (0, 0, 0))
        
        return img
    
    def draw_all_detections(self, img: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """
        Draw all piece detections on the image.
        
        Args:
            img: Image to draw on
            detections: List of detection dictionaries
            
        Returns:
            Image with all detections visualized
        """
        result = img.copy()
        
        for detection in detections:
            result = self.draw_piece_detection(result, detection)
            
        return result
    
    def draw_grid(self, img: np.ndarray, grid_points: np.ndarray) -> np.ndarray:
        """
        Draw the chessboard grid with anti-aliased lines and transparency.
        
        Args:
            img: Image to draw on
            grid_points: 9x9x2 array of grid intersection points
            
        Returns:
            Image with grid overlay
        """
        overlay = img.copy()
        
        # Draw horizontal lines
        for row in range(9):
            pts = grid_points[row, :, :]
            for i in range(8):
                cv2.line(overlay, tuple(pts[i].astype(int)), tuple(pts[i + 1].astype(int)),
                        self.style.grid_color, self.style.grid_thickness, cv2.LINE_AA)
        
        # Draw vertical lines
        for col in range(9):
            pts = grid_points[:, col, :]
            for i in range(8):
                cv2.line(overlay, tuple(pts[i].astype(int)), tuple(pts[i + 1].astype(int)),
                        self.style.grid_color, self.style.grid_thickness, cv2.LINE_AA)
        
        # Blend with original image
        cv2.addWeighted(overlay, self.style.grid_alpha, img, 1 - self.style.grid_alpha, 0, img)
        
        return img
    
    def draw_cell_centers(self, img: np.ndarray, grid_points: np.ndarray) -> np.ndarray:
        """
        Draw small markers at the center of each cell.
        
        Args:
            img: Image to draw on
            grid_points: 9x9x2 array of grid intersection points
            
        Returns:
            Image with cell center markers
        """
        overlay = img.copy()
        
        for row in range(8):
            for col in range(8):
                # Calculate cell center
                center = ((grid_points[row, col] + grid_points[row+1, col+1]) / 2).astype(int)
                cv2.circle(overlay, tuple(center), self.style.cell_marker_radius,
                          self.style.cell_marker_color, -1, cv2.LINE_AA)
        
        # Blend with original image
        cv2.addWeighted(overlay, self.style.cell_marker_alpha, img, 1 - self.style.cell_marker_alpha, 0, img)
        
        return img
    
    def draw_cell_highlights(self, img: np.ndarray, grid_points: np.ndarray,
                           occupied_cells: List[Tuple[int, int]], 
                           conflict_cells: List[Tuple[int, int]] = None) -> np.ndarray:
        """
        Highlight occupied and conflict cells with colored overlays.
        
        Args:
            img: Image to draw on
            grid_points: 9x9x2 array of grid intersection points
            occupied_cells: List of (row, col) tuples for occupied cells
            conflict_cells: List of (row, col) tuples for cells with conflicts
            
        Returns:
            Image with cell highlights
        """
        overlay = img.copy()
        conflict_cells = conflict_cells or []
        
        # Highlight occupied cells
        for row, col in occupied_cells:
            if 0 <= row < 8 and 0 <= col < 8:
                # Get cell corners
                pts = np.array([
                    grid_points[row, col],
                    grid_points[row, col+1],
                    grid_points[row+1, col+1],
                    grid_points[row+1, col]
                ], dtype=np.int32)
                
                color = (self.style.conflict_cell_color if (row, col) in conflict_cells 
                        else self.style.occupied_cell_color)
                
                cv2.fillPoly(overlay, [pts], color)
        
        # Blend with original image
        cv2.addWeighted(overlay, self.style.cell_highlight_alpha, img, 1 - self.style.cell_highlight_alpha, 0, img)
        
        return img
    
    def draw_board_labels(self, img: np.ndarray, grid_points: np.ndarray) -> np.ndarray:
        """
        Draw rank and file labels around the board edges.
        
        Args:
            img: Image to draw on
            grid_points: 9x9x2 array of grid intersection points
            
        Returns:
            Image with board labels
        """
        files = "ABCDEFGH"
        ranks = "87654321"
        
        # Draw file labels (A-H) at bottom
        for col in range(8):
            center_x = int((grid_points[8, col, 0] + grid_points[8, col+1, 0]) / 2)
            pos = (center_x - 10, int(grid_points[8, 0, 1]) + 30)
            self._draw_text_with_background(img, files[col], pos,
                                           self.style.label_color, self.style.label_background_color)
        
        # Draw rank labels (1-8) at left
        for row in range(8):
            center_y = int((grid_points[row, 0, 1] + grid_points[row+1, 0, 1]) / 2)
            pos = (int(grid_points[0, 0, 0]) - 40, center_y + 5)
            self._draw_text_with_background(img, ranks[row], pos,
                                           self.style.label_color, self.style.label_background_color)
        
        return img
    
    def draw_debug_info(self, img: np.ndarray, grid_points: np.ndarray) -> np.ndarray:
        """
        Draw debug information including cell coordinates.
        
        Args:
            img: Image to draw on
            grid_points: 9x9x2 array of grid intersection points
            
        Returns:
            Image with debug information
        """
        for row in range(8):
            for col in range(8):
                # Calculate cell center
                center = ((grid_points[row, col] + grid_points[row+1, col+1]) / 2).astype(int)
                
                # Draw cell coordinates
                debug_text = f"({row},{col})"
                cv2.putText(img, debug_text, tuple(center - 15), cv2.FONT_HERSHEY_SIMPLEX,
                           0.4, (255, 255, 255), 1, cv2.LINE_AA)
        
        return img
    
    def create_comprehensive_visualization(self, img: np.ndarray, grid_points: np.ndarray,
                                         detections: List[Dict], board_state: List[List[str]],
                                         conflict_cells: List[Tuple[int, int]] = None,
                                         show_labels: bool = True, show_debug: bool = False) -> np.ndarray:
        """
        Create a comprehensive visualization with all elements.
        
        Args:
            img: Original image
            grid_points: 9x9x2 array of grid intersection points
            detections: List of piece detections
            board_state: 8x8 board state matrix
            conflict_cells: List of cells with mapping conflicts
            show_labels: Whether to show board labels
            show_debug: Whether to show debug information
            
        Returns:
            Fully annotated image
        """
        result = img.copy()
        
        # Find occupied cells
        occupied_cells = []
        for row in range(8):
            for col in range(8):
                if board_state[row][col] != '' and board_state[row][col] is not None:
                    occupied_cells.append((row, col))
        
        # Apply visualizations in order
        result = self.draw_grid(result, grid_points)
        result = self.draw_cell_highlights(result, grid_points, occupied_cells, conflict_cells)
        result = self.draw_cell_centers(result, grid_points)
        result = self.draw_all_detections(result, detections)
        
        if show_labels:
            result = self.draw_board_labels(result, grid_points)
            
        if show_debug:
            result = self.draw_debug_info(result, grid_points)
        
        return result

# Example usage and utility functions
def create_demo_style() -> VisualizationStyle:
    """Create a demo style with custom colors."""
    style = VisualizationStyle()
    style.grid_color = (0, 255, 128)  # Green-cyan
    style.grid_thickness = 3
    style.bbox_thickness = 4
    style.font_scale = 0.8
    return style

def create_minimal_style() -> VisualizationStyle:
    """Create a minimal style for clean presentations."""
    style = VisualizationStyle()
    style.grid_alpha = 0.4
    style.cell_marker_alpha = 0.3
    style.bbox_corner_radius = 0  # No rounded corners
    style.grid_thickness = 1
    return style
