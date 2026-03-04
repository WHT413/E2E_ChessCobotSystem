"""
FEN (Forsyth-Edwards Notation) conversion utilities.

This module provides functionality for converting between different
representations of chess board states and FEN notation.
"""

from typing import List, Dict, Any
from ..utils.config import get_config

class FenConverter:
    """
    Utility class for FEN notation conversions and operations.
    """
    
    def __init__(self):
        """Initialize the FEN converter with piece mapping from config."""
        self.fen_mapping = get_config().get_fen_mapping()
    
    def board_to_fen_matrix(self, board: List[List[str]]) -> List[List[str]]:
        """
        Convert board state matrix to FEN symbol matrix.
        
        Args:
            board: 8x8 matrix with piece class names
            
        Returns:
            8x8 matrix with FEN symbols
        """
        fen_board = []
        for row in board:
            fen_row = []
            for cell in row:
                if cell == '' or cell is None:
                    fen_row.append('.')
                else:
                    fen_symbol = self.fen_mapping.get(cell, '?')
                    fen_row.append(fen_symbol)
            fen_board.append(fen_row)
        return fen_board
    
    def fen_matrix_to_string(self, fen_matrix: List[List[str]]) -> str:
        """
        Convert FEN matrix to FEN string notation.
        
        Args:
            fen_matrix: 8x8 matrix with FEN symbols
            
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
    
    def fen_string_to_matrix(self, fen_string: str) -> List[List[str]]:
        """
        Parse FEN string to matrix representation.
        
        Args:
            fen_string: FEN string
            
        Returns:
            8x8 matrix with FEN symbols
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
                    board_row.extend(['.'] * int(char))
                else:
                    # Add piece
                    board_row.append(char)
            board.append(board_row)
        
        return board
    
    def board_to_fen_string(self, board: List[List[str]]) -> str:
        """
        Convert board state matrix directly to FEN string.
        
        Args:
            board: 8x8 matrix with piece class names
            
        Returns:
            FEN string representation
        """
        fen_matrix = self.board_to_fen_matrix(board)
        return self.fen_matrix_to_string(fen_matrix)
    
    def validate_fen(self, fen_string: str) -> bool:
        """
        Validate FEN string format.
        
        Args:
            fen_string: FEN string to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            matrix = self.fen_string_to_matrix(fen_string)
            # Check if we got exactly 8 rows
            if len(matrix) != 8:
                return False
            # Check if each row has exactly 8 cells
            for row in matrix:
                if len(row) != 8:
                    return False
            return True
        except:
            return False
    
    def get_piece_counts(self, board: List[List[str]]) -> Dict[str, int]:
        """
        Count pieces on the board.
        
        Args:
            board: 8x8 matrix with piece class names
            
        Returns:
            Dictionary with piece counts
        """
        counts = {}
        for row in board:
            for cell in row:
                if cell and cell != '':
                    counts[cell] = counts.get(cell, 0) + 1
        return counts
