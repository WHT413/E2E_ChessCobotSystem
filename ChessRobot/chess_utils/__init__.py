"""
Chess Board Detection Package

A comprehensive library for chess board detection, piece recognition,
and board state analysis using computer vision and machine learning.
"""

__version__ = "1.0.0"
__author__ = "Chess Detection Team"

# Core imports
from .detection import BoardDetector, PieceDetector
from .processing import FenConverter, GridBuilder, BoardMapper
from .visualization import ChessVisualizer, FenRenderer
from .utils import ConfigManager

__all__ = [
    "BoardDetector",
    "PieceDetector", 
    "FenConverter",
    "GridBuilder",
    "BoardMapper",
    "ChessVisualizer",
    "FenRenderer",
    "ConfigManager",
]
