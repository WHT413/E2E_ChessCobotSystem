"""Fallback chessboard corner detector for corner re-ordering.

This module provides functionality to correctly order and label the four corners
of a chessboard, ensuring consistent orientation regardless of input order.
"""

from typing import Dict, List, Tuple, Optional
import numpy as np

# Define corner types constant
CORNER_TYPES = ["top_left", "top_right", "bottom_left", "bottom_right"]

def detect_corners_fallback(
    detections: List[Tuple[str, Tuple[float, float, float, float]]],
    board_bbox: Optional[Tuple[int, int, int, int]] = None
) -> Tuple[Dict[str, Tuple[float, float]], Dict[str, Tuple[float, float]]]:
    """
    Detect corners with fallback mechanisms.
    """
    # Original validation check
    if len(detections) != 4:  # Change to allow exactly 4 detections
        raise ValueError(f"Exactly 4 detections required, got {len(detections)}")
    
    # Process detections to standard format
    corners = {}
    for label, box in detections:
        # Convert to center point
        cx = (box[0] + box[2]) / 2
        cy = (box[1] + box[3]) / 2
        corners[label] = (cx, cy)
    
    # Try to infer missing corners if needed
    if len(corners) < 4:
        # Create a simple mapping of labels to corner types for inference
        corner_types = {
            label: "unknown" for label in corners.keys()
        }
        
        # Get frame shape from board_bbox if available
        frame_shape = None
        if board_bbox:
            frame_shape = (board_bbox[3] - board_bbox[1], board_bbox[2] - board_bbox[0])
        
        inferred_corners = infer_missing_corners(corners, corner_types, frame_shape)
        if len(inferred_corners) == 4:  # If inference was successful
            # Use inferred corners
            corners = inferred_corners
        else:
            # Still don't have 4 corners
            raise ValueError(f"Could not infer all 4 corners, only have {len(inferred_corners)}")
    
    # Order into canonical labels by spatial rules (no class assumptions)
    normalized_corners = normalize_orientation(list(corners.values()))

    square_map = {
        "bottom_left": normalized_corners["bottom_left"],
        "bottom_right": normalized_corners["bottom_right"],
        "top_left": normalized_corners["top_left"],
        "top_right": normalized_corners["top_right"],
    }
    return normalized_corners, square_map

def infer_missing_corners(corners_dict, corner_types, frame_shape):
    """Infer missing corners based on the known corners"""
    if len(corners_dict) == 4:
        return corners_dict
    
    inferred = corners_dict.copy()
    
    # Handle the case where corner_types is None
    if corner_types is None:
        # Try to guess corner types from labels if possible
        corner_types = {}
        for label in corners_dict:
            if "left" in label.lower() and "top" in label.lower():
                corner_types[label] = "top_left"
            elif "right" in label.lower() and "top" in label.lower():
                corner_types[label] = "top_right"
            elif "left" in label.lower() and "bottom" in label.lower():
                corner_types[label] = "bottom_left"
            elif "right" in label.lower() and "bottom" in label.lower():
                corner_types[label] = "bottom_right"
            elif "white" in label.lower() and "left" in label.lower():
                corner_types[label] = "top_left"
            elif "white" in label.lower() and "right" in label.lower():
                corner_types[label] = "top_right"
            elif "black" in label.lower() and "left" in label.lower():
                corner_types[label] = "bottom_left"
            elif "black" in label.lower() and "right" in label.lower():
                corner_types[label] = "bottom_right"
    
    # Map types to IDs
    type_to_id = {corner_type: corner_id for corner_id, corner_type in corner_types.items()}
    missing = [t for t in CORNER_TYPES if t not in corner_types.values()]
    
    # Case: only one corner missing
    if len(missing) == 1 and len(corners_dict) == 3:
        missing_type = missing[0]
        
        # Find appropriate corners to use for inference
        if missing_type == "top_left" and all(t in type_to_id for t in ["top_right", "bottom_left"]):
            tr = corners_dict[type_to_id["top_right"]]
            bl = corners_dict[type_to_id["bottom_left"]]
            inferred[f"inferred_{missing_type}"] = (bl[0], tr[1])
            
        elif missing_type == "top_right" and all(t in type_to_id for t in ["top_left", "bottom_right"]):
            tl = corners_dict[type_to_id["top_left"]]
            br = corners_dict[type_to_id["bottom_right"]]
            inferred[f"inferred_{missing_type}"] = (br[0], tl[1])
            
        elif missing_type == "bottom_left" and all(t in type_to_id for t in ["top_left", "bottom_right"]):
            tl = corners_dict[type_to_id["top_left"]]
            br = corners_dict[type_to_id["bottom_right"]]
            inferred[f"inferred_{missing_type}"] = (tl[0], br[1])
            
        elif missing_type == "bottom_right" and all(t in type_to_id for t in ["top_right", "bottom_left"]):
            tr = corners_dict[type_to_id["top_right"]]
            bl = corners_dict[type_to_id["bottom_left"]]
            inferred[f"inferred_{missing_type}"] = (tr[0], bl[1])
    
    # Case: two corners missing (only opposite corners detected)
    elif len(corners_dict) == 2:
        known = [t for t in CORNER_TYPES if t in corner_types.values()]
        
        if "top_left" in known and "bottom_right" in known:
            tl = corners_dict[type_to_id["top_left"]]
            br = corners_dict[type_to_id["bottom_right"]]
            inferred[f"inferred_top_right"] = (br[0], tl[1])
            inferred[f"inferred_bottom_left"] = (tl[0], br[1])
            
        elif "top_right" in known and "bottom_left" in known:
            tr = corners_dict[type_to_id["top_right"]]
            bl = corners_dict[type_to_id["bottom_left"]]
            inferred[f"inferred_top_left"] = (bl[0], tr[1])
            inferred[f"inferred_bottom_right"] = (tr[0], bl[1])
    
    return inferred

def normalize_orientation(
    points: List[Tuple[float, float]]
) -> Dict[str, Tuple[float, float]]:
    """
    Re-label 4 points -> {top_left, top_right, bottom_left, bottom_right} using geometry only.
    Rules:
      1) Split by Y to get top-2 and bottom-2.
      2) Within each pair, split by X to get left/right.
      3) Validate convexity (simple cross-product sign).
    """
    if len(points) != 4:
        raise ValueError(f"Expected 4 points, got {len(points)}")

    # Sort by Y (top to bottom)
    y_sorted = sorted(points, key=lambda p: p[1])
    top_two = y_sorted[:2]
    bottom_two = y_sorted[2:]

    # Within each row, sort by X (left to right)
    top_left, top_right = sorted(top_two, key=lambda p: p[0])
    bottom_left, bottom_right = sorted(bottom_two, key=lambda p: p[0])

    # Convexity check: cross(top_left->top_right, top_left->bottom_left) should indicate a proper corner
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])

    # Basic non-degeneracy: diagonals should not intersect at endpoints, area > 0
    area2 = abs(cross(top_left, top_right, bottom_left)) + abs(cross(bottom_right, bottom_left, top_right))
    if area2 == 0:
        raise ValueError("Degenerate quadrilateral (collinear points)")

    return {
        "top_left": top_left,
        "top_right": top_right,
        "bottom_left": bottom_left,
        "bottom_right": bottom_right,
    }

def corners_from_detections(
    detections: list[tuple[str, tuple[float, float, float, float]]]
) -> dict[str, tuple[float, float]]:
    """Build label -> (x, y) using box centers."""
    out = {}
    for lab, (x1, y1, x2, y2) in detections:
        if lab in {"black_right", "black_left", "white_left", "white_right"}:
            out[lab] = ((x1 + x2) * 0.5, (y1 + y2) * 0.5)
    # Simple sanity check
    if set(out) != {"black_right", "black_left", "white_left", "white_right"}:
        raise ValueError(f"Missing labels, got: {sorted(out)}")
    return out

def decide_rotation_strict(corner_by_label: dict[str, tuple[float, float]]) -> int:
    """Return 0/90/180/270 only if full 4/4 match."""
    # Early guard: reject if someone passed position->point by mistake
    if set(corner_by_label) == {"top_left","top_right","bottom_left","bottom_right"}:
        raise ValueError("Expected label->(x,y); got position->(x,y).")

    items = sorted(corner_by_label.items(), key=lambda kv: kv[1][1])
    top = sorted(items[:2], key=lambda kv: kv[1][0])
    bot = sorted(items[2:], key=lambda kv: kv[1][0])

    observed = {
        "top_left":  top[0][0],
        "top_right": top[1][0],
        "bottom_left": bot[0][0],
        "bottom_right": bot[1][0],
    }

    expected0 = {
        "top_left": "white_right",
        "top_right": "white_left",
        "bottom_left": "black_left",
        "bottom_right": "black_right",
    }

    pos_cycle = ("top_left", "top_right", "bottom_right", "bottom_left")
    def rotate_pos(p: str, angle: int) -> str:
        if angle == 0: return p
        steps = {90: 1, 180: 2, 270: 3}[angle]
        i = pos_cycle.index(p)
        return pos_cycle[(i + steps) % 4]

    def expected_at(angle: int) -> dict[str, str]:
        return {rotate_pos(pos, angle): lab for pos, lab in expected0.items()}

    for angle in (0, 90, 180, 270):
        exp_map = expected_at(angle)
        if all(observed[p] == exp_map[p] for p in ("top_left","top_right","bottom_left","bottom_right")):
            return angle
        
    

    raise ValueError(f"No rotation matches exactly. Observed={observed}. Expected@0={expected0}.")

