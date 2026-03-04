"""Results builder for chess analysis pipeline."""

import numpy as np
from typing import List, Dict, Tuple, Optional

from .data_structures import (
    AnalysisResults, DetectionResults, BoardResults, 
    ProcessingResults, VisualizationData
)


class ResultsBuilder:
    """Builder pattern for constructing AnalysisResults."""
    
    def __init__(self):
        self.reset()
    
    def reset(self) -> 'ResultsBuilder':
        """Reset builder to initial state."""
        self._detection_data = {}
        self._board_data = {}
        self._processing_data = {}
        self._viz_data = {}
        self._fen_string = ""
        return self
    
    def with_detection_data(self,
                           piece_info: List[Dict],
                           orig_coords: List[Dict],
                           annotated_img: np.ndarray) -> 'ResultsBuilder':
        """Add detection results data."""
        self._detection_data = {
            'piece_info': piece_info,
            'orig_coords': orig_coords,
            'annotated_img': annotated_img
        }
        return self
    
    def with_board_data(self,
                       chess_board: List[List[str]],
                       conf_matrix: List[List[float]],
                       conflict_pos: List[Tuple[int, int]]) -> 'ResultsBuilder':
        """Add board mapping results data."""
        self._board_data = {
            'chess_board': chess_board,
            'conf_matrix': conf_matrix,
            'conflict_pos': conflict_pos
        }
        return self
    
    def with_processing_data(self,
                            debug_msgs: List[str],
                            unmapped_dets: List[Dict],
                            conflict_msgs: List[str]) -> 'ResultsBuilder':
        """Add processing debug data."""
        self._processing_data = {
            'debug_msgs': debug_msgs,
            'unmapped_dets': unmapped_dets,
            'conflict_msgs': conflict_msgs
        }
        return self
    
    def with_viz_data(self,
                     orig_img: np.ndarray,
                     cropped_img: np.ndarray,
                     grid_pts: np.ndarray,
                     fen_img: Optional[np.ndarray]) -> 'ResultsBuilder':
        """Add visualization data."""
        self._viz_data = {
            'orig_img': orig_img,
            'cropped_img': cropped_img,
            'grid_pts': grid_pts,
            'fen_img': fen_img
        }
        return self
    
    def with_fen_string(self, fen_string: str) -> 'ResultsBuilder':
        """Add FEN string."""
        self._fen_string = fen_string
        return self
    
    def build(self) -> AnalysisResults:
        """Build the final AnalysisResults object."""
        detection = DetectionResults(**self._detection_data)
        board = BoardResults(**self._board_data)
        processing = ProcessingResults(**self._processing_data)
        visualization = VisualizationData(**self._viz_data)
        
        return AnalysisResults(
            detection=detection,
            board=board,
            processing=processing,
            visualization=visualization,
            fen_string=self._fen_string
        )
