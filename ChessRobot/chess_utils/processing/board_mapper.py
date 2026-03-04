"""
Board mapping and coordinate transformation utilities.

This module provides functionality for mapping between different
coordinate systems used in chess board analysis.
"""

from typing import List, Tuple, Dict, Optional
import numpy as np

class BoardMapper:
    """
    Utility class for mapping between different board coordinate systems.
    """
    
    def __init__(self, board_size: Tuple[int, int] = (8, 8)):
        """
        Initialize the board mapper.
        
        Args:
            board_size: (rows, cols) size of the chess board
        """
        self.board_size = board_size
        self.rows, self.cols = board_size
    
    def pixel_to_board_coordinates(
        self,
        pixel_x: int,
        pixel_y: int,
        image_shape: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Convert pixel coordinates to board coordinates.
        
        Args:
            pixel_x: X coordinate in pixels
            pixel_y: Y coordinate in pixels
            image_shape: (height, width) of the image
            
        Returns:
            (row, col) board coordinates
        """
        height, width = image_shape
        
        # Calculate cell dimensions
        cell_height = height / self.rows
        cell_width = width / self.cols
        
        # Convert to board coordinates
        row = int(pixel_y // cell_height)
        col = int(pixel_x // cell_width)
        
        # Clamp to valid range
        row = max(0, min(row, self.rows - 1))
        col = max(0, min(col, self.cols - 1))
        
        return (row, col)
    
    def board_to_pixel_coordinates(
        self,
        row: int,
        col: int,
        image_shape: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Convert board coordinates to pixel coordinates (center of cell).
        
        Args:
            row: Row index (0-based)
            col: Column index (0-based)
            image_shape: (height, width) of the image
            
        Returns:
            (x, y) pixel coordinates of cell center
        """
        height, width = image_shape
        
        # Calculate cell dimensions
        cell_height = height / self.rows
        cell_width = width / self.cols
        
        # Calculate center coordinates
        center_x = int(col * cell_width + cell_width / 2)
        center_y = int(row * cell_height + cell_height / 2)
        
        return (center_x, center_y)
    
    def chess_notation_to_coordinates(self, notation: str) -> Tuple[int, int]:
        """
        Convert chess notation (e.g., 'e4') to board coordinates.
        
        Args:
            notation: Chess notation string (e.g., 'e4', 'a1')
            
        Returns:
            (row, col) board coordinates
        """
        if len(notation) != 2:
            raise ValueError(f"Invalid chess notation: {notation}")
        
        file_char = notation[0].lower()
        rank_char = notation[1]
        
        # Convert file (a-h) to column (0-7)
        if 'a' <= file_char <= 'h':
            col = ord(file_char) - ord('a')
        else:
            raise ValueError(f"Invalid file: {file_char}")
        
        # Convert rank (1-8) to row (7-0, because rank 1 is bottom row)
        if '1' <= rank_char <= '8':
            row = 8 - int(rank_char)
        else:
            raise ValueError(f"Invalid rank: {rank_char}")
        
        return (row, col)
    
    def coordinates_to_chess_notation(self, row: int, col: int) -> str:
        """
        Convert board coordinates to chess notation.
        
        Args:
            row: Row index (0-based)
            col: Column index (0-based)
            
        Returns:
            Chess notation string (e.g., 'e4')
        """
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise ValueError(f"Invalid coordinates: ({row}, {col})")
        
        # Convert column to file (0-7 -> a-h)
        file_char = chr(ord('a') + col)
        
        # Convert row to rank (0-7 -> 8-1)
        rank_char = str(8 - row)
        
        return file_char + rank_char
    
    def get_cell_bounds(
        self,
        row: int,
        col: int,
        image_shape: Tuple[int, int]
    ) -> Tuple[int, int, int, int]:
        """
        Get pixel bounds of a board cell.
        
        Args:
            row: Row index (0-based)
            col: Column index (0-based)
            image_shape: (height, width) of the image
            
        Returns:
            (x1, y1, x2, y2) pixel bounds
        """
        height, width = image_shape
        
        # Calculate cell dimensions
        cell_height = height / self.rows
        cell_width = width / self.cols
        
        # Calculate bounds
        x1 = int(col * cell_width)
        y1 = int(row * cell_height)
        x2 = int((col + 1) * cell_width)
        y2 = int((row + 1) * cell_height)
        
        return (x1, y1, x2, y2)
    
    def get_adjacent_cells(self, row: int, col: int) -> List[Tuple[int, int]]:
        """
        Get coordinates of adjacent cells (8-connected).
        
        Args:
            row: Row index (0-based)
            col: Column index (0-based)
            
        Returns:
            List of (row, col) coordinates of adjacent cells
        """
        adjacent = []
        
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                
                new_row = row + dr
                new_col = col + dc
                
                if (0 <= new_row < self.rows and 0 <= new_col < self.cols):
                    adjacent.append((new_row, new_col))
        
        return adjacent
    
    def get_king_moves(self, row: int, col: int) -> List[Tuple[int, int]]:
        """
        Get possible king moves from a position.
        
        Args:
            row: Row index (0-based)
            col: Column index (0-based)
            
        Returns:
            List of (row, col) coordinates of possible moves
        """
        return self.get_adjacent_cells(row, col)
    
    def get_knight_moves(self, row: int, col: int) -> List[Tuple[int, int]]:
        """
        Get possible knight moves from a position.
        
        Args:
            row: Row index (0-based)
            col: Column index (0-based)
            
        Returns:
            List of (row, col) coordinates of possible moves
        """
        knight_deltas = [
            (-2, -1), (-2, 1), (-1, -2), (-1, 2),
            (1, -2), (1, 2), (2, -1), (2, 1)
        ]
        
        moves = []
        for dr, dc in knight_deltas:
            new_row = row + dr
            new_col = col + dc
            
            if (0 <= new_row < self.rows and 0 <= new_col < self.cols):
                moves.append((new_row, new_col))
        
        return moves
    
    def get_line_moves(
        self,
        row: int,
        col: int,
        directions: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """
        Get possible line moves (rook, bishop, queen) from a position.
        
        Args:
            row: Row index (0-based)
            col: Column index (0-based)
            directions: List of (dr, dc) direction vectors
            
        Returns:
            List of (row, col) coordinates of possible moves
        """
        moves = []
        
        for dr, dc in directions:
            # Move in this direction until hitting board edge
            new_row, new_col = row + dr, col + dc
            
            while (0 <= new_row < self.rows and 0 <= new_col < self.cols):
                moves.append((new_row, new_col))
                new_row += dr
                new_col += dc
        
        return moves
    
    def get_rook_moves(self, row: int, col: int) -> List[Tuple[int, int]]:
        """Get possible rook moves from a position."""
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        return self.get_line_moves(row, col, directions)
    
    def get_bishop_moves(self, row: int, col: int) -> List[Tuple[int, int]]:
        """Get possible bishop moves from a position."""
        directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        return self.get_line_moves(row, col, directions)
    
    def get_queen_moves(self, row: int, col: int) -> List[Tuple[int, int]]:
        """Get possible queen moves from a position."""
        directions = [
            (0, 1), (0, -1), (1, 0), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]
        return self.get_line_moves(row, col, directions)
    
    def is_valid_coordinate(self, row: int, col: int) -> bool:
        """
        Check if coordinates are valid for this board.
        
        Args:
            row: Row index (0-based)
            col: Column index (0-based)
            
        Returns:
            True if coordinates are valid
        """
        return 0 <= row < self.rows and 0 <= col < self.cols
    
    def get_board_notation_map(self) -> Dict[Tuple[int, int], str]:
        """
        Get mapping from coordinates to chess notation.
        
        Returns:
            Dictionary mapping (row, col) to notation strings
        """
        notation_map = {}
        
        for row in range(self.rows):
            for col in range(self.cols):
                notation = self.coordinates_to_chess_notation(row, col)
                notation_map[(row, col)] = notation
        
        return notation_map
