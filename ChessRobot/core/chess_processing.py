"""
Consolidated chess processing utilities.

This module consolidates board processing, component initialization,
and FEN conversion operations into a unified processing interface.
"""

import cv2
import numpy as np
from typing import Dict, Tuple, List, Any
from random import randint

from chess_utils.utils.config import get_config
from chess_utils.detection.board_detector import BoardDetector
from chess_utils.detection.piece_detector import PieceDetector
from chess_utils.processing.fen_converter import FenConverter
from chess_utils.processing.board_mapper import BoardMapper  
from chess_utils.visualization.visualizer import ChessVisualizer
from chess_utils.visualization.fen_renderer import FenRenderer


class ChessProcessor:
    """
    Unified chess processing system that handles board detection,
    component initialization, and FEN conversion operations.
    """
    
    def __init__(self, config=None):
        """
        Initialize the chess processor with configuration.
        
        Args:
            config: Optional configuration object
        """
        self.config = config or get_config()
        self.components = None
        
    def initialize_components(self) -> Tuple[BoardDetector, PieceDetector, FenConverter, 
                                           BoardMapper, ChessVisualizer]:
        """
        Initialize all chess detection and processing components.
        
        Returns:
            Tuple of initialized components
        """
        print("Initializing chess detection components...")
        
        # Get model paths from config
        try:
            board_model_path = self.config.get_model_path('corners')
            piece_model_path = self.config.get_model_path('pieces')
            
            # Initialize detection components with proper model paths
            board_detector = BoardDetector(board_model_path)
            piece_detector = PieceDetector(piece_model_path)
        except (AttributeError, KeyError):
            # Fallback to default initialization if config methods don't exist
            print("Using default model initialization...")
            board_detector = BoardDetector()
            piece_detector = PieceDetector()
        
        # Initialize processing components
        fen_converter = FenConverter()
        board_mapper = BoardMapper()
        
        # Initialize visualization component
        chess_visualizer = ChessVisualizer()
        
        self.components = (board_detector, piece_detector, fen_converter, 
                          board_mapper, chess_visualizer)
        
        print("All components initialized successfully")
        return self.components
    
    def get_components(self) -> Tuple[BoardDetector, PieceDetector, FenConverter, 
                                    BoardMapper, ChessVisualizer]:
        """
        Get initialized components, initializing them if necessary.
        
        Returns:
            Tuple of components
        """
        if self.components is None:
            return self.initialize_components()
        return self.components
    
    def load_and_detect_board(self, img_path: str) -> Tuple[np.ndarray, Dict, np.ndarray]:
        """
        Load image and detect chessboard corners and crop the board area.
        
        Args:
            img_path: Path to input image
            
        Returns:
            Tuple of (original_image, corners, cropped_image)
            
        Raises:
            RuntimeError: If board corners cannot be detected
        """
        board_detector = self.get_components()[0]
        
        print("Loading image...")
        orig_img = board_detector.load_image(img_path)
        
        print("Detecting board corners...")
        corners = board_detector.get_corners(orig_img)
        if corners is None:
            raise RuntimeError("Could not detect all four corners of the chessboard")
        
        if hasattr(self, '_debug_corners'):
            print("Detected corners:")
            for corner_name, corner_pos in corners.items():
                print(f"  {corner_name}: {corner_pos}")
        
        print("Cropping board...")
        cropped_img = board_detector.crop_board(orig_img, corners)
        print(f"Cropped board shape: {cropped_img.shape}")
        
        return orig_img, corners, cropped_img
    
    def convert_board_to_fen(self, chess_board: List[List[str]]) -> Tuple[str, np.ndarray]:
        """
        Convert 8x8 chess board matrix to FEN notation and rendered image.
        
        Args:
            chess_board: 8x8 matrix representing board state
            
        Returns:
            Tuple of (FEN_string, FEN_image)
        """
        fen_converter = self.get_components()[2]
        
        print("Converting board to FEN notation...")
        fen_string = fen_converter.board_to_fen_string(chess_board)
        
        print("Rendering FEN visualization...")
        try:
            # Try to render FEN image if possible
            fen_renderer = FenRenderer()
            fen_img = fen_renderer.render_board_from_fen(fen_string)
        except Exception as e:
            print(f"Warning: Could not create FEN visualization: {e}")
            # Create a simple placeholder image
            fen_img = np.zeros((400, 400, 3), dtype=np.uint8)
            cv2.putText(fen_img, "FEN Render", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(fen_img, "Not Available", (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        print(f"Generated FEN: {fen_string}")
        return fen_string, fen_img
    
    def get_random_sample_image_path(self) -> str:
        """
        Get path to a random sample image for testing.
        
        Returns:
            Path to random sample image
        """
        random_id = randint(0, 10000)
        data_dir = self.config.get_resource_path('sample_data')
        img_path = f"{data_dir}/rgb_{random_id}.jpeg"
        # img_path = f"D:/Downloads/fbf6436e6847a604ad4ab319cb526467.jpg"
        return img_path
    
    def get_processing_size(self) -> Tuple[int, int]:
        """
        Get the configured processing size for board operations.
        
        Returns:
            Processing size as (width, height) tuple
        """
        return tuple(self.config.get('processing.output_size', [640, 640]))
    
    def enable_debug_output(self, enabled: bool = True) -> None:
        """
        Enable or disable debug output for processing operations.
        
        Args:
            enabled: Whether to enable debug output
        """
        self._debug_corners = enabled
        self._debug_processing = enabled

        def convert_with_reasoner(self,
                                chess_board: List[List[str]],
                                unknown_mask: List[List[bool]],
                                reasoner) -> Tuple[Dict[str, Any], np.ndarray]:
            """
            Use partial-observation reasoning (3.B) to produce a stable FEN:
            - Build partial observation from (board, unknown_mask)
            - Ask reasoner to accept unique legal move only
            - Render FEN image from the reasoner's fen output
            Return: (result_dict, fen_image)
            """
            # 1) Build partial observation
            from reasoner_wrapper import build_partial_observation
            observation = build_partial_observation(chess_board, unknown_mask)

            # 2) Query reasoner
            result = reasoner.step(observation)  # {'accepted', 'fen', 'move_san', 'capture', 'reason'}

            # 3) Render FEN image (same rendering approach as convert_board_to_fen)
            # Reuse your existing FenRenderer flow.
            # (You already create FenRenderer and call render_board_from_fen inside convert_board_to_fen)
            try:
                from chess_utils.visualization.fen_renderer import FenRenderer
                fen_img = FenRenderer().render_board_from_fen(result["fen"])
            except Exception:
                fen_img = np.zeros((400, 400, 3), dtype=np.uint8)
                cv2.putText(fen_img, "FEN Render", (50, 200),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(fen_img, "Not Available", (50, 250),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            return result, fen_img


class BoardProcessor:
    """
    Specialized processor for board detection and homography operations.
    
    This class provides focused functionality for board-related processing
    while maintaining compatibility with the existing codebase.
    """
    
    @staticmethod
    def load_detect_board(board_detector: BoardDetector, 
                         img_path: str) -> Tuple[np.ndarray, Dict, np.ndarray]:
        """
        Load image and detect board corners.
        
        Args:
            board_detector: BoardDetector instance
            img_path: Path to input image
            
        Returns:
            Tuple of (original_image, corners, cropped_image)
        """
        processor = ChessProcessor()
        processor.components = (board_detector, None, None, None, None)
        return processor.load_and_detect_board(img_path)


class FenProcessor:
    """
    Specialized processor for FEN conversion operations.
    
    This class provides focused functionality for FEN-related processing
    while maintaining compatibility with the existing codebase.
    """
    
    @staticmethod
    def convert_to_fen(fen_converter: FenConverter, 
                      chess_board: List[List[str]]) -> Tuple[str, np.ndarray]:
        """
        Convert chess board to FEN notation.
        
        Args:
            fen_converter: FenConverter instance
            chess_board: 8x8 board matrix
            
        Returns:
            Tuple of (FEN_string, FEN_image)
        """
        processor = ChessProcessor()
        processor.components = (None, None, fen_converter, None, None)
        return processor.convert_board_to_fen(chess_board)


class ComponentInitializer:
    """
    Specialized initializer for chess detection components.
    
    This class provides focused functionality for component initialization
    while maintaining compatibility with the existing codebase.
    """
    
    @staticmethod
    def init_components(config=None) -> Tuple[BoardDetector, PieceDetector, FenConverter, 
                                           BoardMapper, ChessVisualizer]:
        """
        Initialize all chess components.
        
        Args:
            config: Configuration object (optional)
            
        Returns:
            Tuple of initialized components
        """
        processor = ChessProcessor(config)
        return processor.initialize_components()


# Convenience functions for backward compatibility

def load_detect_board(board_detector: BoardDetector, 
                     img_path: str) -> Tuple[np.ndarray, Dict, np.ndarray]:
    """Backward compatibility function for board detection."""
    return BoardProcessor.load_detect_board(board_detector, img_path)


def convert_to_fen(fen_converter: FenConverter, 
                  chess_board: List[List[str]]) -> Tuple[str, np.ndarray]:
    """Backward compatibility function for FEN conversion."""
    return FenProcessor.convert_to_fen(fen_converter, chess_board)


def init_components(config=None) -> Tuple[BoardDetector, PieceDetector, FenConverter, 
                                        BoardMapper, ChessVisualizer]:
    """Backward compatibility function for component initialization."""
    return ComponentInitializer.init_components(config)
