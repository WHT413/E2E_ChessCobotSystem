"""Data structures for chess analysis results."""

from typing import List, Dict, Tuple, Optional
import numpy as np
from dataclasses import dataclass


@dataclass
class DetectionResults:
    """Container for piece detection results."""
    piece_info: List[Dict]
    orig_coords: List[Dict]
    annotated_img: np.ndarray


@dataclass
class BoardResults:
    """Container for board mapping results."""
    chess_board: List[List[str]]
    conf_matrix: List[List[float]]
    conflict_pos: List[Tuple[int, int]]


@dataclass
class ProcessingResults:
    """Container for processing debug information."""
    debug_msgs: List[str]
    unmapped_dets: List[Dict]
    conflict_msgs: List[str]


@dataclass
class HomographyMapping:
    """Homography transformation data for mapping pieces."""
    homography: np.ndarray
    inv_homography: np.ndarray
    proc_size: Tuple[int, int]
    orig_dims: Tuple[int, int]


@dataclass
class VisualizationData:
    """Container for visualization data."""
    orig_img: np.ndarray
    cropped_img: np.ndarray
    grid_pts: np.ndarray
    fen_img: Optional[np.ndarray]


@dataclass
class AnalysisResults:
    """Complete chess analysis results container."""
    detection: DetectionResults
    board: BoardResults
    processing: ProcessingResults
    visualization: VisualizationData
    fen_string: str
