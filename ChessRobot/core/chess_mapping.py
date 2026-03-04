"""
Unified chess piece mapping and coordinate transformation module.

This module consolidates all piece-to-cell mapping logic, coordinate transformations,
and board space operations into a single, cohesive module.
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from chess_utils.detection.piece_detector import PieceDetector
from chess_utils.detection.board_detector import BoardDetector


@dataclass
class HomographyMapping:
    """Homography transformation data for mapping pieces."""
    homography: np.ndarray
    inv_homography: np.ndarray
    proc_size: Tuple[int, int]
    orig_dims: Tuple[int, int]


@dataclass
class MappingResult:
    """Result of piece mapping operation."""
    chess_board: List[List[str]]
    conf_matrix: List[List[float]]
    debug_msgs: List[str]
    unmapped_pieces: List[Dict]
    conflict_msgs: List[str]
    conflict_positions: List[Tuple[int, int]]


class ChessMapper:
    """
    Unified chess piece mapping system with bottom-center reference point mapping.
    
    This class handles all coordinate transformations and piece-to-cell mapping
    operations using homography-based transformations.
    """
    
    def __init__(self):
        """Initialize the chess mapper."""
        self.debug_enabled = False
        
    def detect_pieces_on_original(self, piece_detector: PieceDetector, 
                                 orig_img: np.ndarray) -> Tuple[List[Dict], np.ndarray]:
        """
        Detect chess pieces directly on original input image.
        
        Args:
            piece_detector: PieceDetector instance
            orig_img: Original full-resolution input image
            
        Returns:
            Tuple of (piece_detections, annotated_image)
        """
        if self.debug_enabled:
            print("Detecting chess pieces on original image...")
        
        # Use original image directly for detection
        results = piece_detector.detect_pieces(orig_img)
        annotated_img, piece_info = piece_detector.process_detections(results, orig_img)
        
        if self.debug_enabled:
            print(f"Detected {len(piece_info)} pieces:")
            for detection in piece_info:
                print(f"  {detection['class_name']}: confidence {detection['confidence']:.2f}")
        
        return piece_info, annotated_img
    
    def create_homography_mapping(self, corners: Dict, 
                                 orig_img: np.ndarray,
                                 proc_size: Tuple[int, int]) -> Tuple[HomographyMapping, np.ndarray]:
        """
        Create homography mapping data for coordinate transformation.
        
        Args:
            corners: Board corner positions from detection
            orig_img: Original input image
            proc_size: Target board processing size (width, height)
            
        Returns:
            Tuple of (HomographyMapping, grid_points)
        """
        if self.debug_enabled:
            print("Creating homography mapping...")
        
        # Define destination points in normalized board space
        dst_pts = np.array([
            [0, 0], [proc_size[0], 0],
            [proc_size[0], proc_size[1]], [0, proc_size[1]]
        ], dtype=np.float32)
        
        # Source points from detected corners
        src_pts = np.array([
            corners['top_left'], corners['top_right'],
            corners['bottom_right'], corners['bottom_left']
        ], dtype=np.float32)
        
        # Create forward and inverse homography matrices
        homography, _ = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC)
        inv_homography, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC)
        
        # Create mapping data structure
        mapping_data = HomographyMapping(
            homography=homography,
            inv_homography=inv_homography,
            proc_size=proc_size,
            orig_dims=orig_img.shape[:2]
        )
        
        # Generate grid points for visualization
        grid_pts = self._generate_visualization_grid(homography, proc_size)
        
        return mapping_data, grid_pts
    
    def map_pieces_to_board_space(self, piece_detections: List[Dict], 
                                 homography_data: HomographyMapping) -> List[Dict]:
        """
        Map piece detections from original image to board coordinate space.
        
        Uses bottom-center of bounding box as reference point for accurate mapping.
        
        Args:
            piece_detections: List of piece detection dictionaries
            homography_data: Homography transformation data
            
        Returns:
            List of pieces with board space coordinates
        """
        if self.debug_enabled:
            print("Mapping piece coordinates to board space...")
        
        mapped_pieces = []
        
        for detection in piece_detections:
            try:
                # Get bottom-center of bounding box as reference point
                bottom_center = self._get_piece_bottom_center(detection['box'])
                
                # Transform to board space using inverse homography
                board_coords = self._transform_point_to_board_space(
                    bottom_center, homography_data.inv_homography
                )
                
                # Create mapped piece data
                mapped_piece = {
                    'class_name': detection['class_name'],
                    'confidence': detection['confidence'],
                    'orig_box': detection['box'],
                    'bottom_center': bottom_center,
                    'board_coords': board_coords,
                    'board_size': homography_data.proc_size
                }
                mapped_pieces.append(mapped_piece)
                
            except Exception as e:
                if self.debug_enabled:
                    print(f"Warning: Failed to map {detection['class_name']}: {e}")
                continue
        
        if self.debug_enabled:
            print(f"Successfully mapped {len(mapped_pieces)} pieces to board space")
        
        return mapped_pieces
    
    def assign_pieces_to_cells(self, mapped_pieces: List[Dict], rotation: int = 0) -> MappingResult:
        """
        Assign mapped pieces to 8x8 board cells with conflict resolution.
        
        Args:
            mapped_pieces: List of pieces with board space coordinates
            
        Returns:
            MappingResult containing board state and debug information
        """
        if self.debug_enabled:
            print("Assigning pieces to 8x8 board cells...")
        
        # Initialize board state
        chess_board = [['' for _ in range(8)] for _ in range(8)]
        conf_matrix = [[0.0 for _ in range(8)] for _ in range(8)]
        debug_msgs = []
        unmapped_pieces = []
        conflict_msgs = []
        conflict_positions = []
        
        for piece in mapped_pieces:
            try:
                # Calculate cell indices from board coordinates
                cell_row, cell_col = self._board_coords_to_cell_indices(
                    piece['board_coords'], piece['board_size']
                )
                # Thêm bước xoay chỉ số nếu cần
                cell_row, cell_col = self._rotate_cell_indices(cell_row, cell_col, rotation)
                
                # Validate cell indices
                if self._are_valid_cell_indices(cell_row, cell_col):
                    self._assign_piece_to_cell(
                        piece, cell_row, cell_col, chess_board, conf_matrix,
                        debug_msgs, conflict_msgs, conflict_positions
                    )
                else:
                    # Piece is outside valid board area
                    self._handle_out_of_bounds_piece(
                        piece, cell_row, cell_col, unmapped_pieces, debug_msgs
                    )
                    
            except Exception as e:
                if self.debug_enabled:
                    print(f"Error processing piece {piece['class_name']}: {e}")
                unmapped_pieces.append({
                    'class_name': piece['class_name'],
                    'confidence': piece['confidence'],
                    'reason': f'Processing error: {e}'
                })
        
        # Print summary
        if self.debug_enabled:
            total_pieces = sum(1 for row in chess_board for cell in row if cell)
            print(f"Mapped {total_pieces} pieces to board")
            print(f"Found {len(conflict_msgs)} conflicts, {len(unmapped_pieces)} unmapped pieces")
        
        return MappingResult(
            chess_board=chess_board,
            conf_matrix=conf_matrix,
            debug_msgs=debug_msgs,
            unmapped_pieces=unmapped_pieces,
            conflict_msgs=conflict_msgs,
            conflict_positions=conflict_positions
        )
    
    def create_display_coordinates(self, mapped_pieces: List[Dict]) -> List[Dict]:
        """
        Create display coordinates for visualization overlay.
        
        Args:
            mapped_pieces: Pieces with board coordinates
            
        Returns:
            List of pieces with display coordinates (uses original boxes)
        """
        display_coords = []
        for piece in mapped_pieces:
            display_coords.append({
                'class_name': piece['class_name'],
                'confidence': piece['confidence'],
                'box': piece['orig_box']
            })
        return display_coords
    
    def _get_piece_bottom_center(self, bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
        """
        Get bottom-center point of bounding box as piece reference point.
        
        Args:
            bbox: Bounding box (x1, y1, x2, y2)
            
        Returns:
            Bottom-center coordinates (x, y)
        """
        x1, y1, x2, y2 = bbox
        bottom_center_x = (x1 + x2) / 2.0
        bottom_center_y = float(y2)  # Use bottom edge
        return (bottom_center_x, bottom_center_y)
    
    def _transform_point_to_board_space(self, point: Tuple[float, float], 
                                       inv_homography: np.ndarray) -> Tuple[float, float]:
        """
        Transform a point from original image to board space.
        
        Args:
            point: Point coordinates in original image
            inv_homography: Inverse homography matrix
            
        Returns:
            Point coordinates in board space
        """
        point_array = np.array([[[point[0], point[1]]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(point_array, inv_homography)
        return (float(transformed[0, 0, 0]), float(transformed[0, 0, 1]))
    
    def _board_coords_to_cell_indices(self, board_coords: Tuple[float, float], 
                                     board_size: Tuple[int, int]) -> Tuple[int, int]:
        """
        Convert board coordinates to cell indices.
        
        Args:
            board_coords: Coordinates in board space
            board_size: Board dimensions (width, height)
            
        Returns:
            Cell indices (row, col)
        """
        board_x, board_y = board_coords
        board_width, board_height = board_size
        
        # Calculate cell dimensions
        cell_width = board_width / 8.0
        cell_height = board_height / 8.0
        
        # Convert to cell indices
        cell_col = int(board_x / cell_width)
        cell_row = int(board_y / cell_height)
        
        return (cell_row, cell_col)
    
    def _are_valid_cell_indices(self, row: int, col: int) -> bool:
        """
        Check if cell indices are within valid 8x8 board range.
        
        Args:
            row: Row index
            col: Column index
            
        Returns:
            True if indices are valid
        """
        return 0 <= row < 8 and 0 <= col < 8
    
    def _assign_piece_to_cell(self, piece: Dict, row: int, col: int,
                             chess_board: List[List[str]], conf_matrix: List[List[float]],
                             debug_msgs: List[str], conflict_msgs: List[str],
                             conflict_positions: List[Tuple[int, int]]) -> None:
        """
        Assign a piece to a specific cell with conflict resolution.
        
        Args:
            piece: Piece data
            row: Target row
            col: Target column
            chess_board: Board state matrix
            conf_matrix: Confidence matrix
            debug_msgs: Debug message list
            conflict_msgs: Conflict message list
            conflict_positions: Conflict position list
        """
        class_name = piece['class_name']
        confidence = piece['confidence']
        board_x, board_y = piece['board_coords']
        
        # Log mapping
        debug_msgs.append(
            f"{class_name} at board ({board_x:.1f}, {board_y:.1f}) -> cell ({row}, {col})"
        )
        
        # Check for conflicts
        if chess_board[row][col] != '':
            existing_piece = chess_board[row][col]
            existing_conf = conf_matrix[row][col]
            
            # Log conflict
            conflict_msg = (
                f"Cell ({row},{col}): {existing_piece} (conf: {existing_conf:.2f}) "
                f"vs {class_name} (conf: {confidence:.2f})"
            )
            conflict_msgs.append(conflict_msg)
            conflict_positions.append((row, col))
            
            # Keep higher confidence piece
            if confidence > existing_conf:
                chess_board[row][col] = class_name
                conf_matrix[row][col] = confidence
                debug_msgs.append(f"Replaced with higher confidence {class_name}")
        else:
            # Assign to empty cell
            chess_board[row][col] = class_name
            conf_matrix[row][col] = confidence
    
    def _handle_out_of_bounds_piece(self, piece: Dict, attempted_row: int, attempted_col: int,
                                   unmapped_pieces: List[Dict], debug_msgs: List[str]) -> None:
        """
        Handle piece that maps outside valid board boundaries.
        
        Args:
            piece: Piece data
            attempted_row: Attempted row assignment
            attempted_col: Attempted column assignment
            unmapped_pieces: List to store unmapped pieces
            debug_msgs: Debug message list
        """
        board_x, board_y = piece['board_coords']
        
        unmapped_piece = {
            'class_name': piece['class_name'],
            'confidence': piece['confidence'],
            'board_coords': piece['board_coords'],
            'attempted_cell': (attempted_row, attempted_col),
            'reason': f'Outside board bounds [0-7, 0-7]'
        }
        unmapped_pieces.append(unmapped_piece)
        
        debug_msgs.append(
            f"Unmapped {piece['class_name']}: board pos ({board_x:.1f}, {board_y:.1f}) "
            f"-> invalid cell ({attempted_row}, {attempted_col})"
        )
    
    def _generate_visualization_grid(self, homography: np.ndarray, 
                                   proc_size: Tuple[int, int]) -> np.ndarray:
        """
        Generate grid points for visualization overlay.
        
        Args:
            homography: Forward homography matrix
            proc_size: Board processing size
            
        Returns:
            Grid points in original image coordinates
        """
        grid_points = []
        cell_width = proc_size[0] / 8.0
        cell_height = proc_size[1] / 8.0
        
        for row in range(9):
            for col in range(9):
                x_coord = col * cell_width
                y_coord = row * cell_height
                grid_points.append([x_coord, y_coord])
        
        grid_array = np.array(grid_points, dtype=np.float32).reshape(-1, 1, 2)
        transformed_grid = cv2.perspectiveTransform(grid_array, homography)
        
        return transformed_grid.reshape(9, 9, 2)
    
    def _rotate_cell_indices(self, row: int, col: int, angle: int) -> Tuple[int, int]:
        """Xoay chỉ số row, col theo góc angle (0, 90, 180, 270)."""
        if angle == 0:
            return row, col
        elif angle == 90:
            return col, 7 - row
        elif angle == 180:
            return 7 - row, 7 - col
        elif angle == 270:
            return 7 - col, row
        else:
            raise ValueError(f"Unsupported rotation angle: {angle}")

def detect_pieces_on_original_image(piece_detector: PieceDetector, 
                                   orig_img: np.ndarray) -> Tuple[List[Dict], np.ndarray]:
    """Convenience function for piece detection on original image."""
    mapper = ChessMapper()
    return mapper.detect_pieces_on_original(piece_detector, orig_img)

def create_homography_transformation(corners: Dict, orig_img: np.ndarray, 
                                    proc_size: Tuple[int, int]) -> Tuple[HomographyMapping, np.ndarray]:
    """Convenience function for homography creation."""
    mapper = ChessMapper()
    return mapper.create_homography_mapping(corners, orig_img, proc_size)

def map_pieces_with_bottom_center_reference(piece_detections: List[Dict], 
                                           homography_data: HomographyMapping) -> List[Dict]:
    """Convenience function for piece mapping using bottom-center reference."""
    mapper = ChessMapper()
    return mapper.map_pieces_to_board_space(piece_detections, homography_data)

def assign_mapped_pieces_to_board(mapped_pieces: List[Dict]) -> MappingResult:
    """Convenience function for piece-to-cell assignment."""
    mapper = ChessMapper()
    return mapper.assign_pieces_to_cells(mapped_pieces)
