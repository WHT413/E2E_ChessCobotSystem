"""
FEN (Forsyth-Edwards Notation) to chess board image renderer.

This module provides functionality to convert FEN strings and board matrices
into visual chess board representations with pieces.
"""

import cv2
import numpy as np
import os
from pathlib import Path
from typing import List, Optional

from ..utils.config import get_config

class FenRenderer:
    """
    Chess board renderer that converts FEN notation to visual board images.
    """
    
    def __init__(self, resources_dir: Optional[str] = None):
        """
        Initialize the FEN renderer with paths to resources.
        
        Args:
            resources_dir: Path to resources directory. If None, uses config.
        """
        config = get_config()
        
        if resources_dir is None:
            resources_dir = config.get_resource_path('board_images')
        
        self.resources_dir = resources_dir
        self.board_img_path = os.path.join(resources_dir, "board.png")
        self.pieces_dir = config.get_resource_path('piece_images')
        
        # Load the board image
        self.board_img = cv2.imread(self.board_img_path)
        if self.board_img is None:
            raise FileNotFoundError(f"Board image not found at {self.board_img_path}")
        
        # Load piece images
        self.piece_images = self._load_piece_images()
        
        # Calculate cell size based on board dimensions
        self.board_height, self.board_width = self.board_img.shape[:2]
        self.cell_height = self.board_height // 8
        self.cell_width = self.board_width // 8
        
        # FEN piece to filename mapping
        self.fen_to_filename = {
            'K': "white-king.png",
            'Q': "white-queen.png",
            'R': "white-rook.png",
            'B': "white-bishop.png",
            'N': "white-knight.png",
            'P': "white-pawn.png",
            'k': "black-king.png",
            'q': "black-queen.png",
            'r': "black-rook.png",
            'b': "black-bishop.png",
            'n': "black-knight.png",
            'p': "black-pawn.png"
        }
    
    def _load_piece_images(self) -> dict:
        """Load all chess piece images and resize them to fit the board cells."""
        piece_images = {}
        
        if not os.path.exists(self.pieces_dir):
            raise FileNotFoundError(f"Pieces directory not found: {self.pieces_dir}")
        
        for filename in os.listdir(self.pieces_dir):
            if filename.endswith(".png") and "icon" not in filename:
                filepath = os.path.join(self.pieces_dir, filename)
                img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
                if img is not None:
                    piece_images[filename] = img
                    
        return piece_images
    
    def parse_fen(self, fen_string: str) -> List[List[str]]:
        """
        Parse FEN string and return board matrix.
        
        Args:
            fen_string: FEN string representing board position
            
        Returns:
            8x8 matrix representing the board
        """
        # Take only the piece placement part of FEN if full FEN is provided
        fen_parts = fen_string.split(' ')
        piece_placement = fen_parts[0]
        
        # Parse the FEN board representation into a 2D array
        board = []
        rows = piece_placement.split('/')
        
        for row in rows:
            board_row = []
            for char in row:
                if char.isdigit():
                    # Add empty squares
                    board_row.extend([''] * int(char))
                else:
                    # Add piece
                    board_row.append(char)
            board.append(board_row)
        
        return board
    
    def render_board_from_fen(self, fen_string: str) -> np.ndarray:
        """
        Render chess board from FEN string.
        
        Args:
            fen_string: FEN string representing board position
            
        Returns:
            Rendered board image
        """
        # Parse FEN to get board state
        board = self.parse_fen(fen_string)
        
        # Create a copy of the board image to draw on
        result = self.board_img.copy()
        
        # Place pieces on the board
        for row_idx, row in enumerate(board):
            for col_idx, piece in enumerate(row):
                if piece:
                    # Get piece image filename
                    filename = self.fen_to_filename.get(piece)
                    if filename and filename in self.piece_images:
                        # Calculate position to place piece
                        x = col_idx * self.cell_width
                        y = row_idx * self.cell_height
                        
                        # Get piece image and resize if needed
                        piece_img = self.piece_images[filename]
                        piece_h, piece_w = piece_img.shape[:2]
                        scale = min(self.cell_height / piece_h, self.cell_width / piece_w) * 0.8
                        new_size = (int(piece_w * scale), int(piece_h * scale))
                        piece_img_resized = cv2.resize(piece_img, new_size)
                        
                        # Calculate centered position
                        x_offset = x + (self.cell_width - new_size[0]) // 2
                        y_offset = y + (self.cell_height - new_size[1]) // 2
                        
                        # Handle transparency for PNG images with alpha channel
                        if piece_img_resized.shape[2] == 4:  # With alpha channel
                            alpha = piece_img_resized[:, :, 3] / 255.0
                            for c in range(3):  # RGB channels
                                result[y_offset:y_offset+new_size[1], x_offset:x_offset+new_size[0], c] = (
                                    piece_img_resized[:, :, c] * alpha + 
                                    result[y_offset:y_offset+new_size[1], x_offset:x_offset+new_size[0], c] * (1 - alpha)
                                )
                        else:  # No alpha channel
                            result[y_offset:y_offset+new_size[1], x_offset:x_offset+new_size[0]] = piece_img_resized
        
        return result
    
    def load_fen_from_matrix(self, fen_matrix: List[List[str]]) -> str:
        """
        Convert a FEN matrix to a FEN string.
        
        Args:
            fen_matrix: 8x8 matrix with FEN piece symbols
            
        Returns:
            FEN string representation
        """
        fen_rows = []
        for row in fen_matrix:
            fen_row = ""
            empty_count = 0
            
            for cell in row:
                if cell == '.' or cell == '' or cell is None:
                    empty_count += 1
                else:
                    if empty_count > 0:
                        fen_row += str(empty_count)
                        empty_count = 0
                    fen_row += cell
            
            if empty_count > 0:
                fen_row += str(empty_count)
                
            fen_rows.append(fen_row)
        
        return "/".join(fen_rows)

# Legacy class name for backward compatibility
ChessBoardRenderer = FenRenderer

# Example usage
def main():
    # Initialize renderer with path to resources
    renderer = ChessBoardRenderer(resources_dir="d:/Workspaces/chess_board/Edge/resources")
    
    # Example 1: Using a FEN string (starting position)
    # fen_string = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
    # board_img = renderer.render_board_from_fen(fen_string)
    
    # Example 2: Using a FEN matrix (similar to what's generated in test.py)
    fen_matrix = [
        ['.', '.', '.', 'q', 'k', 'b', 'n', 'r'],
        ['p', 'p', 'p', 'p', '.', 'p', 'p', 'p'],
        ['.', '.', 'n', '.', '.', '.', '.', '.'],
        ['.', '.', '.', '.', 'p', '.', '.', '.'],
        ['.', '.', 'b', '.', 'P', '.', '.', '.'],
        ['.', '.', '.', '.', '.', 'N', '.', '.'],
        ['P', 'P', 'P', 'P', '.', 'P', 'P', 'P'],
        ['R', 'N', 'B', 'Q', 'K', 'B', '.', 'R']
    ]
    fen_from_matrix = renderer.load_fen_from_matrix(fen_matrix)
    board2img = renderer.render_board_from_fen(fen_from_matrix)
    
    # Display the results
    # cv2.imshow("Starting Position", board_img)
    cv2.imshow("Position from Matrix", board2img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()