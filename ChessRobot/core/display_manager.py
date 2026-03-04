"""Display and visualization management."""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple, Optional

from chess_utils.visualization.visualizer import ChessVisualizer
from .data_structures import AnalysisResults, VisualizationData


def show_board_comparison(orig_img: np.ndarray, fen_img: Optional[np.ndarray]) -> None:
    """
    Display original image and FEN rendered board side by side.
    
    Args:
        orig_img: Original image with detected pieces
        fen_img: FEN rendered board image (optional)
    """
    def to_rgb(img):
        if img is None:
            return None
        if img.shape[2] == 4:    # RGBA
            img = img[..., :3]
        # If max pixel value is 255, assume it's an 8-bit image
        if img.shape[2] == 3 and img.dtype == np.uint8:
            # If the image is BGR, convert to RGB
            if (img[..., 0] != img[..., 2]).any():  # Heuristic, option: skip if already RGB
                return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img

    orig_rgb = to_rgb(orig_img)
    fen_rgb = to_rgb(fen_img)

    # Setup layout
    fig, axs = plt.subplots(1, 2, figsize=(14, 7), gridspec_kw={'width_ratios': [1, 1]})

    # Panel 1: Original Image
    axs[0].imshow(orig_rgb)
    axs[0].set_title("Original Image", fontsize=13)
    axs[0].axis('off')

    # Panel 2: FEN Rendered Image (if available)
    if fen_rgb is not None:
        axs[1].imshow(fen_rgb)
        axs[1].set_title("FEN Rendered Board", fontsize=13)
        axs[1].axis('off')
    else:
        axs[1].set_visible(False)

    plt.subplots_adjust(wspace=0.04, left=0.01, right=0.99, top=0.92, bottom=0.03)
    plt.show()


def process_chessboard_image(orig_img: np.ndarray,
                             annotated_img: np.ndarray,
                             img_result: np.ndarray,
                             fen_img: Optional[np.ndarray]) -> None:
    """
    Process chessboard image and update visualization data.
    Args:
        orig_img: Original image with detected pieces
        annotated_img: Image with annotations
        img_results: Comprehensive visualization
        fen_img: FEN rendered board image (optional)
    """
    def to_rgb(img):
        if img is None:
            return None
        if img.shape[2] == 4:
            img = img[..., :3]
        if img.shape[2] == 3 and img.dtype == np.uint8:
            if (img[..., 0] != img[..., 2]).any():
                return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img

    orig_rgb = to_rgb(orig_img)
    annotated_rgb = to_rgb(annotated_img)
    img_results_rgb = to_rgb(img_result)
    fen_rgb = to_rgb(fen_img)

    n_panels = 4 if fen_rgb is not None else 3
    fig, axs = plt.subplots(1, n_panels, figsize=(6 * n_panels, 6),
                           gridspec_kw={'width_ratios': [1] * n_panels})

    axs[0].imshow(orig_rgb)
    axs[0].set_title("Original Image", fontsize=13)
    axs[0].axis('off')

    axs[1].imshow(annotated_rgb)
    axs[1].set_title("Annotated Image", fontsize=13)
    axs[1].axis('off')

    axs[2].imshow(img_results_rgb)
    axs[2].set_title("Comprehensive Visualization", fontsize=13)
    axs[2].axis('off')

    if fen_rgb is not None:
        axs[3].imshow(fen_rgb)
        axs[3].set_title("FEN Rendered Board", fontsize=13)
        axs[3].axis('off')

    plt.subplots_adjust(wspace=0.04, left=0.01, right=0.99, top=0.92, bottom=0.03)
    plt.show()


def create_comp_viz(visualizer: ChessVisualizer,    
                   viz_data: VisualizationData,
                   orig_coords: List[Dict],
                   chess_board: List[List[str]],
                   conflict_pos: List[Tuple[int, int]]) -> np.ndarray:
    """
    Create comprehensive visualization.
    
    Args:
        visualizer: ChessVisualizer instance
        viz_data: Visualization data container
        orig_coords: Detections with original coordinates
        chess_board: 8x8 board representation
        conflict_pos: List of conflict cell positions
        
    Returns:
        Comprehensive visualization image
    """
    return visualizer.create_comprehensive_visualization(
        viz_data.orig_img.copy(), viz_data.grid_pts, orig_coords, chess_board,
        conflict_cells=conflict_pos, show_labels=False, show_debug=False
    )


def resize_for_display(img: np.ndarray, size: Tuple[int, int] = (800, 800)) -> np.ndarray:
    """
    Resize image for display.
    
    Args:
        img: Input image
        size: Target size (width, height)
        
    Returns:
        Resized image
    """
    return cv2.resize(img, size)


def show_analysis_windows(comp_viz: np.ndarray,
                         cropped_img: np.ndarray,
                         fen_img: Optional[np.ndarray]) -> None:
    """
    Display analysis result windows.
    
    Args:
        comp_viz: Comprehensive visualization image
        cropped_img: Cropped board image
        fen_img: FEN rendered board image (optional)
    """
    # Resize for display
    display_size = (800, 800)
    comp_viz_resized = resize_for_display(comp_viz, display_size)
    cropped_resized = resize_for_display(cropped_img, display_size)
    
    cv2.imshow("Comprehensive Analysis", comp_viz_resized)
    cv2.imshow("Cropped Board with Detections", cropped_resized)
    
    if fen_img is not None:
        cv2.imshow("FEN Rendered Board", fen_img)


def display_results(results: AnalysisResults,
                   visualizer: ChessVisualizer,
                   show: bool = False) -> Tuple[np.ndarray, Optional[np.ndarray]]: 
    """
    Display all visualization results.
    
    Args:
        results: Complete analysis results container
        visualizer: ChessVisualizer instance
    """
    print("\nDisplaying results...")
    
    # Create comprehensive visualization
    comp_viz = create_comp_viz(
        visualizer,
        results.visualization,
        results.detection.orig_coords,
        results.board.chess_board,
        results.board.conflict_pos
    )
    
    if show:
        # Show all windows
        show_analysis_windows(
            comp_viz,
            results.visualization.cropped_img,
            results.visualization.fen_img
        )

    return comp_viz, results.visualization.fen_img


def print_detection_summary(piece_info: List[Dict], unmapped_dets: List[Dict]) -> None:
    """
    Print detection summary information.
    
    Args:
        piece_info: List of all piece detections
        unmapped_dets: List of detections that couldn't be mapped
    """
    print(f"\nSummary:")
    print(f"  Total detections: {len(piece_info)}")
    print(f"  Successfully mapped: {len(piece_info) - len(unmapped_dets)}")
    print(f"  Unmapped detections: {len(unmapped_dets)}")


def print_conflict_info(conflict_msgs: List[str]) -> None:
    """
    Print cell conflict information.
    
    Args:
        conflict_msgs: List of cell conflict messages
    """
    if conflict_msgs:
        print(f"\nCell conflicts:")
        for conflict_msg in conflict_msgs:
            print(f"    {conflict_msg}")


def print_debug_info(debug_msgs: List[str]) -> None:
    """
    Print debug information.
    
    Args:
        debug_msgs: List of debug messages
    """
    if debug_msgs:
        print(f"\nDebug log:")
        for log_entry in debug_msgs[:10]:  # Limit debug output
            print(f"    {log_entry}")
        if len(debug_msgs) > 10:
            print(f"    ... and {len(debug_msgs) - 10} more debug messages")


def print_unmapped_info(unmapped_dets: List[Dict]) -> None:
    """
    Print unmapped detection information.
    
    Args:
        unmapped_dets: List of detections that couldn't be mapped
    """
    if unmapped_dets:
        print(f"\nUnmapped detections:")
        for detection in unmapped_dets:
            if 'error' in detection:
                print(f"    {detection['class_name']} (conf: {detection['confidence']:.2f}) - Error: {detection['error']}")
            else:
                print(f"    {detection['class_name']} (conf: {detection['confidence']:.2f}) - Attempted: {detection.get('attempted_cell', 'N/A')}")


def print_summary(results: AnalysisResults) -> None:
    """
    Print processing summary and debug information.
    
    Args:
        results: Complete analysis results container
    """
    # Print detection summary
    print_detection_summary(results.detection.piece_info, results.processing.unmapped_dets)
    print(f"  Cell conflicts: {len(results.processing.conflict_msgs)}")
    
    # Print detailed information
    print_debug_info(results.processing.debug_msgs)
    print_conflict_info(results.processing.conflict_msgs)
    print_unmapped_info(results.processing.unmapped_dets)
