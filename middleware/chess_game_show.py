"""
Smart Chess Game Show - OpenCV Only Implementation
==================================================
A complete chess vision system with:
- 3 YOLO models (corners, pieces, obstacles)
- A-B-C-D Protocol for robust chess logic
- OpenCV-only UI (no Pygame/PyQt/Tkinter)

Author: Antigravity AI
"""

import cv2
import numpy as np
import chess
import chess.engine
from ultralytics import YOLO
from pathlib import Path
from collections import deque
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from dataclasses import dataclass
import time
import threading
import json
import asyncio
try:
    from socket_client import TCPClient
except ImportError:
    # Fallback/Mock if file is missing during dev? 
    # Or just fail since user provided it.
    pass

# =============================================================================
# NETWORK CLIENT
# =============================================================================

class ChessNetwork:
    """
    Wrapper for Async TCP Client to run in a background thread.
    Handles payload construction and sending.
    """
    def __init__(self, host="127.0.0.1", port=8080):
        self.loop = asyncio.new_event_loop()
        self.client = TCPClient(host, port)
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        # Schedule connection and identification
        asyncio.run_coroutine_threadsafe(self.connect_and_identify(), self.loop)
        
    async def connect_and_identify(self):
        """Connect to server and send identity handshake."""
        try:
            await self.client.connect()
            ai_identity = {
            "type": "ai_identify",
            "ai_id": "chess_vision_ai"
            }
            await self.client.send(json.dumps(ai_identity))
            print(f"[NETWORK] AI identified with server: {ai_identity}")
        except Exception as e:
            print(f"[NETWORK ERROR] Connection failed: {e}")

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        
    def send_best_move(self, board: chess.Board, move: chess.Move, fen: str):
        """Build and send the move payload."""
        try:
            payload = self._build_payload(board, move, fen)
            msg = json.dumps(payload)
            # Fire and forget
            asyncio.run_coroutine_threadsafe(self.client.send(msg), self.loop)
        except Exception as e:
            print(f"[NETWORK ERROR] Failed to send move: {e}")

    def _build_payload(self, board: chess.Board, move: chess.Move, fen: str) -> dict:
        """Construct the specific JSON payload requested."""
        
        # Analyze move
        from_sq = move.from_square
        to_sq = move.to_square
        
        from_piece = board.piece_at(from_sq)
        to_piece = board.piece_at(to_sq) # Target piece (if capture)
        
        # Determine Move Type
        mv_type = "move"
        if board.is_capture(move):
            mv_type = "attack"
        
        # Helper for piece label
        def piece_label(p: Optional[chess.Piece]) -> str:
            if p is None:
                return "None"
            color = "white" if p.color == chess.WHITE else "black"
            return f"{color}_{chess.piece_name(p.piece_type)}"

        if board.is_castling(move):
            mv_type = "castle"
            # Middleware Logic: Expects 'to' to be the Rook's square, and 'to_piece' to be the Rook.
            # Kingside: e1->g1 (White), e8->g8 (Black). Rook at h1/h8.
            # Queenside: e1->c1 (White), e8->c8 (Black). Rook at a1/a8.
            
            is_kingside = chess.square_file(to_sq) == 6 # g-file
            is_white = board.turn # board.turn is the side TO MOVE. Wait, move is already passed.
            # board.piece_at(from_sq) gives the piece moving.
            p = board.piece_at(from_sq)
            if p:
                 is_white = (p.color == chess.WHITE)
                 rank = 0 if is_white else 7
                 if is_kingside:
                     to_sq = chess.square(7, rank) # h1 or h8
                 else:
                     to_sq = chess.square(0, rank) # a1 or a8
                 
                 # Set to_piece as Rook
                 to_piece = chess.Piece(chess.ROOK, p.color)

        if move.promotion:
            mv_type = "promotion"
            
        # Check status
        results_in_check = board.gives_check(move)
        
        # SAN (Standard Algebraic Notation) - needs full context
        san = board.san(move)
            
        data = {
            "fen_str": fen,
            "move": {
                "type": mv_type,
                "from": chess.square_name(from_sq).lower(),
                "to": chess.square_name(to_sq).lower(),
                "from_piece": piece_label(from_piece).lower(),
                "to_piece": piece_label(to_piece).lower(),
                "notation": san,
                "results_in_check": results_in_check
            }
        }
        return data

    def close(self):
        asyncio.run_coroutine_threadsafe(self.client.close(), self.loop)

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

# YOLO class name to python-chess symbol mapping
NAME_TO_SYM: Dict[str, str] = {
    "white_pawn": "P", "white_knight": "N", "white_bishop": "B",
    "white_rook": "R", "white_queen": "Q", "white_king": "K",
    "black_pawn": "p", "black_knight": "n", "black_bishop": "b",
    "black_rook": "r", "black_queen": "q", "black_king": "k",
}

# Reverse mapping: symbol to piece image filename
SYM_TO_FILE: Dict[str, str] = {
    "P": "white-pawn.png", "N": "white-knight.png", "B": "white-bishop.png",
    "R": "white-rook.png", "Q": "white-queen.png", "K": "white-king.png",
    "p": "black-pawn.png", "n": "black-knight.png", "b": "black-bishop.png",
    "r": "black-rook.png", "q": "black-queen.png", "k": "black-king.png",
}

# Board orientation: 0=normal, 1=90°CW, 2=180°, 3=270°CW
BOARD_ORIENTATION: int = 0

# UI Configuration
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
BOARD_SIZE = 480  # Digital twin size
SQUARE_SIZE = BOARD_SIZE // 8  # 60px per square
DASHBOARD_HEIGHT = 240
TOTAL_WIDTH = CAMERA_WIDTH * 2  # 1280
TOTAL_HEIGHT = CAMERA_HEIGHT + DASHBOARD_HEIGHT  # 720

# Detection thresholds
CORNER_MERGE_DISTANCE = 30  # pixels
CORNER_DRIFT_THRESHOLD = 10  # pixels for lazy matrix recalc
MOTION_THRESHOLD = 25
STABLE_FRAMES_REQUIRED = 5

# Colors (BGR)
COLOR_GREEN = (0, 255, 0)
COLOR_RED = (0, 0, 255)
COLOR_BLUE = (255, 0, 0)
COLOR_YELLOW = (0, 255, 255)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_ORANGE = (0, 165, 255)
COLOR_DARK_BG = (30, 30, 30)

# Paths
BASE_DIR = Path(__file__).parent
RESOURCES_DIR = BASE_DIR / "resources"
MODELS_DIR = BASE_DIR / "models"
STOCKFISH_PATH = r"stockfish/stockfish-windows-x86-64-avx2.exe"  


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Detection:
    """Single detection from YOLO model."""
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    center: Tuple[int, int]
    anchor: Tuple[int, int]  # Bottom-center for pieces


@dataclass
class GameState:
    """Current game state."""
    state: str  # "WAITING" or "STABLE"
    fen: str
    last_move: Optional[str]
    warning: Optional[str]
    turn: str  # "white" or "black"


# =============================================================================
# STOCKFISH WRAPPER
# =============================================================================

class StockfishWrapper:
    """
    Wrapper for Stockfish engine using python-chess.
    Handles process management and move generation.
    """
    
    def __init__(self, engine_path: str, skill_level: int = 20):
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(engine_path)
            # Configure skill level (approx 2700 ELO at level 20)
            self.engine.configure({"Skill Level": skill_level})
            print(f"[INFO] Stockfish initialized from {engine_path}")
        except Exception as e:
            print(f"[ERROR] Failed to load Stockfish: {e}")
            self.engine = None
            
    def get_best_move(self, fen: str, time_limit: float = 1.0) -> Optional[chess.Move]:
        """Get best move from engine."""
        if not self.engine:
            return None
        
        try:
            board = chess.Board(fen)
            limit = chess.engine.Limit(time=time_limit)
            result = self.engine.play(board, limit)
            return result.move
        except Exception as e:
            print(f"[ERROR] Stockfish error: {e}")
            return None
            
    def close(self):
        """Clean up engine process."""
        if self.engine:
            self.engine.quit()
            self.engine = None
            print("[INFO] Stockfish engine closed")
            
    def __del__(self):
        self.close()


# =============================================================================
# RESOURCE LOADER
# =============================================================================

class ResourceLoader:
    """Load and manage chess piece images and board background."""
    
    def __init__(self, resources_dir: Path):
        self.resources_dir = resources_dir
        self.pieces_dir = resources_dir / "pieces"
        self.board_img: Optional[np.ndarray] = None
        self.piece_images: Dict[str, np.ndarray] = {}
        
    def load_all(self) -> bool:
        """Load board and all piece images."""
        try:
            # Load board background
            board_path = self.resources_dir / "board.png"
            self.board_img = cv2.imread(str(board_path))
            if self.board_img is None:
                print(f"[ERROR] Cannot load board: {board_path}")
                return False
            # Resize to target size
            self.board_img = cv2.resize(self.board_img, (BOARD_SIZE, BOARD_SIZE))
            
            # Load piece images with alpha channel
            for sym, filename in SYM_TO_FILE.items():
                piece_path = self.pieces_dir / filename
                img = cv2.imread(str(piece_path), cv2.IMREAD_UNCHANGED)
                if img is None:
                    print(f"[WARNING] Cannot load piece: {piece_path}")
                    continue
                # Resize to square size
                img = cv2.resize(img, (SQUARE_SIZE, SQUARE_SIZE))
                self.piece_images[sym] = img
                
            print(f"[INFO] Loaded {len(self.piece_images)} piece images")
            return True
            
        except Exception as e:
            print(f"[ERROR] ResourceLoader failed: {e}")
            return False
    
    def get_board_copy(self) -> np.ndarray:
        """Return a copy of the board image."""
        return self.board_img.copy() if self.board_img is not None else np.zeros((BOARD_SIZE, BOARD_SIZE, 3), dtype=np.uint8)
    
    def get_piece(self, symbol: str) -> Optional[np.ndarray]:
        """Get piece image by symbol."""
        return self.piece_images.get(symbol)


def overlay_transparent(bg: np.ndarray, overlay: np.ndarray, x: int, y: int) -> np.ndarray:
    """
    Overlay a transparent PNG image onto a background.
    Uses alpha channel as mask for proper blending.
    
    Args:
        bg: Background image (BGR, 3 channels)
        overlay: Overlay image (BGRA, 4 channels with alpha)
        x, y: Top-left position for overlay
        
    Returns:
        Modified background image
    """
    if overlay is None or bg is None:
        return bg
        
    h, w = overlay.shape[:2]
    bg_h, bg_w = bg.shape[:2]
    
    # Boundary checks
    if x < 0 or y < 0 or x + w > bg_w or y + h > bg_h:
        # Clip overlay to fit
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(bg_w, x + w), min(bg_h, y + h)
        ox1, oy1 = x1 - x, y1 - y
        ox2, oy2 = ox1 + (x2 - x1), oy1 + (y2 - y1)
        if ox2 <= ox1 or oy2 <= oy1:
            return bg
        overlay = overlay[oy1:oy2, ox1:ox2]
        x, y = x1, y1
        h, w = overlay.shape[:2]
    
    # Check if overlay has alpha channel
    if overlay.shape[2] < 4:
        # No alpha, just copy
        bg[y:y+h, x:x+w] = overlay[:, :, :3]
        return bg
    
    # Extract alpha channel and normalize to 0-1
    alpha = overlay[:, :, 3].astype(np.float32) / 255.0
    alpha_3ch = np.stack([alpha] * 3, axis=-1)
    
    # Extract BGR channels from overlay
    overlay_bgr = overlay[:, :, :3].astype(np.float32)
    bg_region = bg[y:y+h, x:x+w].astype(np.float32)
    
    # Alpha blending: out = alpha * fg + (1 - alpha) * bg
    blended = alpha_3ch * overlay_bgr + (1 - alpha_3ch) * bg_region
    bg[y:y+h, x:x+w] = blended.astype(np.uint8)
    
    return bg


# =============================================================================
# CORNER DETECTOR (Protocol A)
# =============================================================================

class CornerDetector:
    """
    Detect and process board corners using YOLO model.
    Implements Protocol A: Filter, Merge, Order, Lazy Matrix.
    """
    
    def __init__(self, model_path: Path, orientation: int = 0):
        self.model = YOLO(str(model_path))
        self.orientation = orientation
        self.cached_corners: Optional[List[Tuple[int, int]]] = None
        self.cached_matrix: Optional[np.ndarray] = None
        self.dst_points = np.float32([
            [0, 0],              # TL
            [BOARD_SIZE, 0],     # TR
            [BOARD_SIZE, BOARD_SIZE],  # BR
            [0, BOARD_SIZE]      # BL
        ])
        
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run corner detection on frame."""
        results = self.model(frame, verbose=False)
        detections = []
        
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                cls_id = int(boxes.cls[i].cpu().numpy())
                cls_name = self.model.names[cls_id]
                
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                w, h = int(x2 - x1), int(y2 - y1)
                
                detections.append(Detection(
                    class_name=cls_name,
                    confidence=conf,
                    bbox=(int(x1), int(y1), w, h),
                    center=(cx, cy),
                    anchor=(cx, cy)  # For corners, anchor is center
                ))
                
        return detections
    
    def filter_merge_corners(self, detections: List[Detection]) -> List[Tuple[int, int]]:
        """
        [A1] Filter and merge nearby corner detections.
        Uses Euclidean distance clustering (<30px) and takes top-4 by confidence.
        """
        if not detections:
            return []
        
        # Sort by confidence descending
        sorted_dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
        
        merged: List[Tuple[int, int]] = []
        used = set()
        
        for det in sorted_dets:
            if len(merged) >= 4:
                break
                
            cx, cy = det.center
            
            # Check if too close to existing point
            too_close = False
            for mx, my in merged:
                dist = np.sqrt((cx - mx) ** 2 + (cy - my) ** 2)
                if dist < CORNER_MERGE_DISTANCE:
                    too_close = True
                    break
            
            if not too_close:
                merged.append((cx, cy))
                
        return merged
    
    def order_corners(self, points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        [A2] Order corners as TL, TR, BR, BL.
        Uses centroid-based sorting.
        """
        if len(points) != 4:
            return points
        
        pts = np.array(points, dtype=np.float32)
        
        # Find centroid
        centroid = pts.mean(axis=0)
        
        # Calculate angles from centroid
        angles = np.arctan2(pts[:, 1] - centroid[1], pts[:, 0] - centroid[0])
        
        # Sort by angle to get clockwise ordering starting from TL
        # TL should have negative x and negative y relative to centroid (angle ~ -135°)
        sorted_indices = np.argsort(angles)
        sorted_pts = pts[sorted_indices]
        
        # Rearrange to TL, TR, BR, BL
        # The point with smallest sum (x+y) is TL
        sums = sorted_pts[:, 0] + sorted_pts[:, 1]
        diffs = sorted_pts[:, 0] - sorted_pts[:, 1]
        
        tl_idx = np.argmin(sums)
        br_idx = np.argmax(sums)
        tr_idx = np.argmax(diffs)
        bl_idx = np.argmin(diffs)
        
        ordered = [
            tuple(sorted_pts[tl_idx].astype(int)),
            tuple(sorted_pts[tr_idx].astype(int)),
            tuple(sorted_pts[br_idx].astype(int)),
            tuple(sorted_pts[bl_idx].astype(int)),
        ]
        
        return ordered
    
    def rotate_for_orientation(self, corners: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        [A3] Rotate corners list based on BOARD_ORIENTATION.
        Uses deque.rotate to shift the order.
        This ensures Digital Twin is upright even if camera is rotated.
        """
        if len(corners) != 4:
            return corners
        d = deque(corners)  # [TL, TR, BR, BL]
        d.rotate(-self.orientation)  # Shift by orientation
        return list(d)
    
    def detect_orientation_by_scoring(self, frame: np.ndarray, piece_mapper, target_board: chess.Board) -> int:
        """
        [DETERMINISTIC V2] Detect orientation by matching against Standard Start Position.
        
        Algorithm: "Reverse-Calibration"
        1. Assume Logic Board is Master (Standard Start FEN).
        2. Iterate rotation 0..3.
        3. Match Vision Piece at Square vs Logic Piece at Square.
        4. Scoring:
        - Match (Type & Color): +1
        - Mismatch (Empty vs Occupied): -1
        - Conflict (Wrong Type/Color): -5
        """
        # print(">>> ACTIVATING FORCED START CALIBRATION PROTOCOL...")
        
        best_orientation = 0
        best_score = -9999
        
        scores = []
        original_orientation = self.orientation
        
        for test_orient in range(4):
            # 1. Hypothesis
            self.orientation = test_orient
            self.cached_matrix = None
            
            # 2. Map Vision
            matrix, corners = self.process_frame(frame)
            if matrix is None:
                continue
            
            _, positions = piece_mapper.process_frame(frame, matrix)
            
            # 3. Calculate Matching Score against target_board
            score = 0
            
            # Check all 64 squares
            for square in chess.SQUARES:
                col = chess.square_file(square)
                row = 7 - chess.square_rank(square)
                
                # Logic Truth
                logic_piece = target_board.piece_at(square)
                logic_sym = logic_piece.symbol() if logic_piece else None
                
                # Vision Candidate
                vision_sym = positions.get((col, row))
                
                if logic_sym and vision_sym:
                    if logic_sym == vision_sym:
                        score += 1  # Perfect Match
                    else:
                        score -= 5  # Conflict (e.g. Pawn vs Rook)
                elif logic_sym and not vision_sym:
                    # Logic says piece, Vision says empty
                    score -= 1  # Mismatch (Missing piece)
                elif not logic_sym and vision_sym:
                    # Logic says empty, Vision says piece (Ghost)
                    # For start position, E4/D4 etc must be empty.
                    score -= 2  # Stronger penalty for ghosts in empty zone
            
            scores.append((test_orient, score))
            
            if score > best_score:
                best_score = score
                best_orientation = test_orient
        
        # Restore Winner
        self.orientation = best_orientation
        self.cached_matrix = None
        
        print(f"[REVERSE-CAL] Scores: {scores}")
        print(f"[REVERSE-CAL] Winner: Rotation {best_orientation} ({best_orientation*90} deg) Score: {best_score}")
        
        return best_orientation

    # Alias for backward compatibility if needed, or just update the caller
    def auto_detect_orientation(self, frame: np.ndarray, piece_mapper) -> int:
        return self.detect_orientation_by_scoring(frame, piece_mapper)
    
    def get_perspective_matrix(self, corners: List[Tuple[int, int]], force: bool = False) -> Optional[np.ndarray]:
        """
        [A4] Get perspective transform matrix.
        Uses lazy calculation - only recalculates if drift > threshold.
        """
        if len(corners) != 4:
            return self.cached_matrix
        
        # Check if we need to recalculate
        if not force and self.cached_corners is not None and self.cached_matrix is not None:
            max_drift = 0
            for (cx, cy), (ox, oy) in zip(corners, self.cached_corners):
                drift = np.sqrt((cx - ox) ** 2 + (cy - oy) ** 2)
                max_drift = max(max_drift, drift)
            
            if max_drift < CORNER_DRIFT_THRESHOLD:
                return self.cached_matrix
        
        # Calculate new matrix
        src_points = np.float32(corners)
        self.cached_matrix = cv2.getPerspectiveTransform(src_points, self.dst_points)
        self.cached_corners = corners.copy()
        
        return self.cached_matrix
    
    def process_frame(self, frame: np.ndarray) -> Tuple[Optional[np.ndarray], List[Tuple[int, int]]]:
        """
        Full corner processing pipeline.
        Returns (perspective_matrix, ordered_corners).
        """
        detections = self.detect(frame)
        corners = self.filter_merge_corners(detections)
        
        if len(corners) != 4:
            return self.cached_matrix, corners
        
        ordered = self.order_corners(corners)
        rotated = self.rotate_for_orientation(ordered)
        matrix = self.get_perspective_matrix(rotated)
        
        return matrix, ordered  # Return original ordered for visualization


# =============================================================================
# PIECE MAPPER (Protocol B)
# =============================================================================

class PieceMapper:
    """
    Detect and map chess pieces to board positions.
    Implements Protocol B: Bottom-Center Anchor, Grid Mapping.
    """
    
    def __init__(self, model_path: Path):
        self.model = YOLO(str(model_path))
        
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run piece detection on frame."""
        results = self.model(frame, verbose=False)
        detections = []
        
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                cls_id = int(boxes.cls[i].cpu().numpy())
                cls_name = self.model.names[cls_id]
                
                w, h = int(x2 - x1), int(y2 - y1)
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                
                # [B1] Bottom-center anchor - CRITICAL
                anchor_x = int((x1 + x2) / 2)
                anchor_y = int(y2)  # Bottom of bounding box
                
                detections.append(Detection(
                    class_name=cls_name,
                    confidence=conf,
                    bbox=(int(x1), int(y1), w, h),
                    center=(cx, cy),
                    anchor=(anchor_x, anchor_y)
                ))
                
        return detections
    
    def map_to_grid(self, anchor: Tuple[int, int], matrix: np.ndarray) -> Optional[Tuple[int, int]]:
        """
        [B2] Map anchor point to grid position (col, row).
        Uses perspective transform to map to 8x8 grid.
        """
        if matrix is None:
            return None
        
        # Transform point
        pt = np.array([[[anchor[0], anchor[1]]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(pt, matrix)
        tx, ty = transformed[0][0]
        
        # Map to grid (0-7, 0-7)
        col = int(tx // SQUARE_SIZE)
        row = int(ty // SQUARE_SIZE)
        
        # Clamp to valid range
        col = max(0, min(7, col))
        row = max(0, min(7, row))
        
        return (col, row)
    
    def build_position_dict(self, detections: List[Detection], matrix: np.ndarray) -> Dict[Tuple[int, int], str]:
        """
        Build dictionary mapping grid positions to piece symbols.
        Uses NAME_TO_SYM for conversion.
        """
        positions: Dict[Tuple[int, int], str] = {}
        
        for det in detections:
            # Get symbol from class name
            symbol = NAME_TO_SYM.get(det.class_name)
            if symbol is None:
                continue
            
            # Map to grid
            grid_pos = self.map_to_grid(det.anchor, matrix)
            if grid_pos is None:
                continue
            
            # Handle conflicts - keep highest confidence
            if grid_pos in positions:
                # Could implement conflict resolution here
                pass
            else:
                positions[grid_pos] = symbol
                
        return positions
    
    def process_frame(self, frame: np.ndarray, matrix: np.ndarray) -> Tuple[List[Detection], Dict[Tuple[int, int], str]]:
        """
        Full piece processing pipeline.
        Returns (detections, position_dict).
        """
        detections = self.detect(frame)
        positions = self.build_position_dict(detections, matrix)
        return detections, positions


# =============================================================================
# OBSTACLE DETECTOR (Protocol C)
# =============================================================================

class ObstacleDetector:
    """
    Detect hands and cobots to determine game state.
    Implements Protocol C: State Machine, Motion Filter.
    """
    
    def __init__(self, model_path: Path):
        self.model = YOLO(str(model_path))
        self.prev_frame: Optional[np.ndarray] = None
        self.stable_counter: int = 0
        
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run obstacle detection on frame."""
        results = self.model(frame, verbose=False)
        detections = []
        
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                cls_id = int(boxes.cls[i].cpu().numpy())
                cls_name = self.model.names[cls_id]
                
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                w, h = int(x2 - x1), int(y2 - y1)
                
                detections.append(Detection(
                    class_name=cls_name,
                    confidence=conf,
                    bbox=(int(x1), int(y1), w, h),
                    center=(cx, cy),
                    anchor=(cx, cy)
                ))
                
        return detections
    
    def check_motion(self, frame: np.ndarray) -> bool:
        """
        Check if there's significant motion in the frame.
        Uses cv2.absdiff for motion detection.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if self.prev_frame is None:
            self.prev_frame = gray
            return True  # First frame, assume motion
        
        # Calculate absolute difference
        diff = cv2.absdiff(self.prev_frame, gray)
        thresh = cv2.threshold(diff, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
        
        # Count non-zero pixels
        motion_pixels = cv2.countNonZero(thresh)
        total_pixels = frame.shape[0] * frame.shape[1]
        motion_ratio = motion_pixels / total_pixels
        
        self.prev_frame = gray
        
        # If more than 1% motion, consider it moving
        return motion_ratio > 0.01
    
class ObstacleDetector:
    """
    Protocol C: Obstacle Detection
    Detects hands/cobots to manage game state (WAITING vs STABLE).
    Uses 'Interaction Zone' logic to ignore obstacles outside the board area.
    """
    
    def __init__(self, model_path: str):
        self.model = YOLO(model_path, verbose=False)
        self.prev_frame = None
        self.stable_counter = 0
        self.last_zone = None
        
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run YOLO inference."""
        results = self.model(frame, verbose=False)
        detections = []
        
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                cls_id = int(boxes.cls[i].cpu().numpy())
                cls_name = self.model.names[cls_id]
                
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                w, h = int(x2 - x1), int(y2 - y1)
                
                detections.append(Detection(
                    class_name=cls_name,
                    confidence=conf,
                    bbox=(int(x1), int(y1), w, h),
                    center=(cx, cy),
                    anchor=(cx, cy)
                ))
                
        return detections
    
    def get_interaction_zone(self, corners: List[Tuple[int, int]], margin: int = 20) -> List[Tuple[int, int]]:
        """
        Calculate valid interaction zone (Trapezoid) around the board.
        Expands the board corners by a margin to catch hands hovering near edges.
        """
        if len(corners) != 4:
            return []
            
        points = np.array(corners, dtype=np.float32)
        centroid = np.mean(points, axis=0)
        
        expanded = []
        for point in points:
            vector = point - centroid
            # Expand by margin pixels (approximate vector scaling)
            # Assuming ~300px radius, margin 20px is ~1.07x
            scale = 1.0 + (margin / 200.0) 
            new_point = centroid + vector * scale
            expanded.append(tuple(new_point.astype(int)))
            
        return expanded
    
    def check_intersection(self, detection: Detection, zone: List[Tuple[int, int]], frame_shape: Tuple[int, int]) -> bool:
        """Check if detection bbox intersects with the zone polygon."""
        if not zone:
            return True # Fallback: if no zone, assume true
            
        # Create mask for zone
        h, w = frame_shape[:2]
        zone_mask = np.zeros((h, w), dtype=np.uint8)
        zone_pts = np.array(zone, dtype=np.int32).reshape((-1, 1, 2))
        cv2.fillConvexPoly(zone_mask, zone_pts, 255)
        
        # Create mask for detection box
        box_mask = np.zeros((h, w), dtype=np.uint8)
        x, y, bw, bh = detection.bbox
        cv2.rectangle(box_mask, (x, y), (x + bw, y + bh), 255, -1)
        
        # Check overlap
        overlap = cv2.bitwise_and(zone_mask, box_mask)
        return cv2.countNonZero(overlap) > 0

    def check_motion(self, frame: np.ndarray) -> bool:
        """Check for significant motion in the frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if self.prev_frame is None:
            self.prev_frame = gray
            return True
        
        diff = cv2.absdiff(self.prev_frame, gray)
        thresh = cv2.threshold(diff, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
        
        motion_pixels = cv2.countNonZero(thresh)
        motion_ratio = motion_pixels / (frame.shape[0] * frame.shape[1])
        
        self.prev_frame = gray
        return motion_ratio > 0.01
    
    def get_state(self, frame: np.ndarray, corners: List[Tuple[int, int]] = None) -> Tuple[str, List[Detection]]:
        """
        Determine current state based on Intersecting Obstacles.
        """
        raw_obstacles = self.detect(frame)
        
        # Filter: Only care about obstacles touching the Interaction Zone
        interfering_obstacles = []
        
        if corners and len(corners) == 4:
            self.last_zone = self.get_interaction_zone(corners)
            for obs in raw_obstacles:
                if self.check_intersection(obs, self.last_zone, frame.shape):
                    interfering_obstacles.append(obs)
        else:
            # If board not found yet, any obstacle is interference
            interfering_obstacles = raw_obstacles
            self.last_zone = []
        
        has_motion = self.check_motion(frame)
        
        # Logic: If interfering obstacles -> WAITING
        if interfering_obstacles:
            self.stable_counter = 0
            return "WAITING", interfering_obstacles
            
        if has_motion:
            self.stable_counter = 0
            return "WAITING", []
        
        self.stable_counter += 1
        if self.stable_counter >= STABLE_FRAMES_REQUIRED:
            return "STABLE", []
            
        return "WAITING", []


# =============================================================================
# CHESS LOGIC (Protocol D)
# =============================================================================

class ChessLogic:
    """
    Chess game logic using python-chess.
    Implements Protocol D: Inference, Validation, Auto-Correct, Occlusion.
    """
    
    def __init__(self):
        self.board = chess.Board()
        self.prev_positions: Dict[Tuple[int, int], str] = {}
        self.last_move: Optional[chess.Move] = None
        
    def positions_to_fen(self, positions: Dict[Tuple[int, int], str]) -> str:
        """Convert position dict to FEN board part."""
        rows = []
        for row in range(8):
            row_str = ""
            empty_count = 0
            for col in range(8):
                piece = positions.get((col, row))
                if piece:
                    if empty_count > 0:
                        row_str += str(empty_count)
                        empty_count = 0
                    row_str += piece
                else:
                    empty_count += 1
            if empty_count > 0:
                row_str += str(empty_count)
            rows.append(row_str)
        return "/".join(rows)
    
    def fen_to_positions(self, fen: str) -> Dict[Tuple[int, int], str]:
        """Convert FEN board part to position dict."""
        positions = {}
        rows = fen.split("/")
        for row, row_str in enumerate(rows):
            col = 0
            for char in row_str:
                if char.isdigit():
                    col += int(char)
                else:
                    positions[(col, row)] = char
                    col += 1
        return positions
    
    # [D1-D4 methods replaced by new Logic Supremacy update() method]
    
    def board_to_positions(self) -> Dict[Tuple[int, int], str]:
        """Convert current python-chess board to position dict."""
        positions = {}
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                col = chess.square_file(square)
                row = 7 - chess.square_rank(square)
                positions[(col, row)] = piece.symbol()
        return positions

    def update(self, detected_positions: Dict[Tuple[int, int], str]) -> Tuple[bool, Optional[str]]:
        """
        [LOGIC SUPREMACY] Update game state using STRICT "Moves Only" Policy.
        
        The Board is the Source of Truth. It is NEVER directly modified based on Vision.
        It is ONLY modified via `board.push(move)`.
        
        Cases:
        A. Movement: Vision sees Piece X move A->B. Legal. -> Push Move.
        B. Capture: Vision sees Piece Y move to occupied Z. Legal. -> Push Move.
        C. Occlusion: Vision sees Empty at occupied A. No Legal Move. -> DO NOTHING. (Piece stays).
        """
        # Diagnostic: Strict Turn Enforcement
        # print(f">>> ACTIVATING FULL STATE & TURN ENFORCEMENT PROTOCOL... (Turn: {'WHITE' if self.board.turn else 'BLACK'})")

        # 1. Build Vision Bitboard (Occupancy Only)
        vision_bb = 0
        for (col, row), _ in detected_positions.items():
            rank = 7 - row
            file_idx = col
            square = chess.square(file_idx, rank)
            vision_bb |= (1 << square)
            
        # 2. Score "No Move" (Null Hypothesis)
        # This represents "Camera Glitch / Occlusion / Ghosting"
        # If we do nothing, how many bits mismatch?
        current_bb = self.board.occupied
        null_mistakes = bin(current_bb ^ vision_bb).count('1')
        
        # 3. Score All Legal Moves
        # STRICT TURN ENFORCEMENT: self.board.legal_moves ONLY generates moves for the active color.
        # This automatically filters out "Black piece moving during White's turn".
        best_move = None
        min_mistakes = 999
        candidate_moves = []
        
        for move in self.board.legal_moves:
            # Heuristic: Source square must be EMPTY in vision (piece left source)
            if (vision_bb & (1 << move.from_square)):
                continue
                
            # Heuristic: Destination must be OCCUPIED in vision (piece arrived)
            # (Exception: En Passant - handled implicitly or by bitboard check? 
            # In En Passant, Pawn lands on empty square in terms of *Board*, but Vision sees a pawn there.
            # So vision_bb bit IS set. So this check holds.)
            if not (vision_bb & (1 << move.to_square)):
                continue
            
            # Simulate
            self.board.push(move)
            predicted_bb = self.board.occupied
            
            # Calculate Hamming Distance
            diff = predicted_bb ^ vision_bb
            mistakes = bin(diff).count('1')
            
            self.board.pop()
            
            if mistakes < min_mistakes:
                min_mistakes = mistakes
                candidate_moves = [move]
            elif mistakes == min_mistakes:
                candidate_moves.append(move)
        
        # 4. Strict Threshold Policy
        # "If it didn't move, and it wasn't eaten, it is NOT gone."
        # A valid move must be significantly better than "No Move".
        # A Move usually fixes at least 2 bits (Source 1->0, Dest 0->1).
        # So min_mistakes must be < null_mistakes.
        
        if not candidate_moves:
            return True, None
            
        if min_mistakes >= null_mistakes:
            # The "Move" explanation is worse or equal to "Glitch/Occlusion" explanation.
            # Pivot to "Occlusion" (Case C) - Do Not Update Logic.
            return True, None
            
        # 5. Tie-breaking (Ambiguity Resolution)
        final_move = candidate_moves[0]
        
        if len(candidate_moves) > 1:
            print(f"[LOGIC] Ambiguity: {candidate_moves}")
            # Check Promotion
            promotions = [m for m in candidate_moves if m.promotion]
            if promotions:
                target_sq = promotions[0].to_square
                t_col, t_row = chess.square_file(target_sq), 7 - chess.square_rank(target_sq)
                detected_sym = detected_positions.get((t_col, t_row))
                
                if detected_sym:
                    det_type = detected_sym.upper()
                    # Map K/Q/R/B/N/P to promotion constants
                    # (Simplified check: Q is most common, check others if needed)
                    for p_move in promotions:
                        if (p_move.promotion == chess.QUEEN and det_type == 'Q') or \
                        (p_move.promotion == chess.ROOK and det_type == 'R') or \
                        (p_move.promotion == chess.BISHOP and det_type == 'B') or \
                        (p_move.promotion == chess.KNIGHT and det_type == 'N'):
                            final_move = p_move
                            break
                            
        # 6. Execute (Update Truth)
        move_san = self.board.san(final_move)
        self.board.push(final_move)
        self.last_move = final_move
        # Synchronize prev_positions (for debug/history only, not used for inference anymore)
        self.prev_positions = self.board_to_positions()
        
        print(f"[FEN] {self.board.fen()}")

        return True, move_san

    
    def get_fen(self) -> str:
        """Get current FEN string."""
        return self.board.fen()
    
    def get_turn(self) -> str:
        """Get current turn."""
        return "white" if self.board.turn else "black"
    
    def reset(self):
        """Reset board to starting position."""
        self.board = chess.Board()
        self.prev_positions = {}
        self.last_move = None
    
    def set_fen(self, fen: str):
        """Set board position from FEN."""
        try:
            self.board = chess.Board(fen)
            self.prev_positions = {}
            self.last_move = None
            return True
        except:
            return False
    
    def sanitize_detections(self, detected_positions: Dict[Tuple[int, int], str]) -> Dict[Tuple[int, int], str]:
        """
        [LOGIC SUPREMACY] Sanitize vision detections using python-chess as source of truth.
        
        Rules:
        1. Filter out duplicate kings (max 1 per color)
        2. If Vision != Logic at a square, trust Logic
        3. Ghost pieces (detected but not in logic) are removed
        4. Missing pieces (in logic but not detected) are preserved
        
        Returns: Sanitized position dictionary matching logic state
        """
        if not self.is_calibrated:
            # Not calibrated yet, just filter duplicates
            return self._filter_duplicate_pieces(detected_positions)
        
        # Get expected state from python-chess (source of truth)
        expected = {}
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                col = chess.square_file(square)
                row = 7 - chess.square_rank(square)
                expected[(col, row)] = piece.symbol()
        
        # Return the expected state - Logic is always correct
        # Vision is only used for move detection, not for rendering
        return expected
    
    def _filter_duplicate_pieces(self, positions: Dict[Tuple[int, int], str]) -> Dict[Tuple[int, int], str]:
        """Filter duplicate kings and queens (chess rules: max 1 king per side)."""
        result = positions.copy()
        
        # Count kings per color
        white_king_positions = [pos for pos, sym in positions.items() if sym == 'K']
        black_king_positions = [pos for pos, sym in positions.items() if sym == 'k']
        
        # Keep only first king of each color
        if len(white_king_positions) > 1:
            print(f"[SANITIZE] Removing {len(white_king_positions) - 1} duplicate white king(s)")
            for pos in white_king_positions[1:]:
                del result[pos]
        
        if len(black_king_positions) > 1:
            print(f"[SANITIZE] Removing {len(black_king_positions) - 1} duplicate black king(s)")
            for pos in black_king_positions[1:]:
                del result[pos]
        
        return result
    
    def sync_from_vision(self, detected_positions: Dict[Tuple[int, int], str]) -> bool:
        """
        [INITIAL CALIBRATION] Sync internal board state with detected positions.
        Called automatically at startup to initialize the board.
        """
        # Filter duplicates first
        sanitized = self._filter_duplicate_pieces(detected_positions)
        
        # Build FEN from sanitized positions
        fen_board = self.positions_to_fen(sanitized)
        full_fen = f"{fen_board} w KQkq - 0 1"
        
        try:
            test_board = chess.Board(full_fen)
            # Validate: must have exactly 1 king per side
            white_kings = len([sq for sq in chess.SQUARES if test_board.piece_at(sq) and test_board.piece_at(sq).symbol() == 'K'])
            black_kings = len([sq for sq in chess.SQUARES if test_board.piece_at(sq) and test_board.piece_at(sq).symbol() == 'k'])
            
            if white_kings != 1 or black_kings != 1:
                print(f"[SYNC ERROR] Invalid king count: W={white_kings}, B={black_kings}")
                return False
            
            self.board = test_board
            self.prev_positions = sanitized.copy()
            self.last_move = None
            self.is_calibrated = True
            print(f"[SYNC] Board synced: {fen_board}")
            return True
        except Exception as e:
            print(f"[SYNC ERROR] {e}")
            return False
    
    @property
    def is_calibrated(self) -> bool:
        """Check if board has been calibrated."""
        return getattr(self, '_is_calibrated', False)
    
    @is_calibrated.setter
    def is_calibrated(self, value: bool):
        self._is_calibrated = value


# =============================================================================
# CHESS BOARD RENDERER
# =============================================================================

class ChessBoardRenderer:
    """Render digital twin chess board using OpenCV."""
    
    def __init__(self, resources: ResourceLoader):
        self.resources = resources
        
    def render(self, board: chess.Board) -> np.ndarray:
        """Render board with pieces."""
        img = self.resources.get_board_copy()
        
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                col = chess.square_file(square)
                row = 7 - chess.square_rank(square)  # Flip for display
                
                x = col * SQUARE_SIZE
                y = row * SQUARE_SIZE
                
                piece_img = self.resources.get_piece(piece.symbol())
                if piece_img is not None:
                    overlay_transparent(img, piece_img, x, y)
        
        return img
    
    def render_with_highlight(self, board: chess.Board, last_move: Optional[chess.Move]) -> np.ndarray:
        """Render board with last move highlighted."""
        img = self.render(board)
        
        if last_move:
            # Highlight from square
            from_col = chess.square_file(last_move.from_square)
            from_row = 7 - chess.square_rank(last_move.from_square)
            from_x, from_y = from_col * SQUARE_SIZE, from_row * SQUARE_SIZE
            
            # Highlight to square
            to_col = chess.square_file(last_move.to_square)
            to_row = 7 - chess.square_rank(last_move.to_square)
            to_x, to_y = to_col * SQUARE_SIZE, to_row * SQUARE_SIZE
            
            # Draw highlight rectangles
            overlay = img.copy()
            cv2.rectangle(overlay, (from_x, from_y), (from_x + SQUARE_SIZE, from_y + SQUARE_SIZE), COLOR_YELLOW, -1)
            cv2.rectangle(overlay, (to_x, to_y), (to_x + SQUARE_SIZE, to_y + SQUARE_SIZE), COLOR_YELLOW, -1)
            cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)
        
        return img


# =============================================================================
# UI COMPOSITOR
# =============================================================================

class UICompositor:
    """
    Compose the final UI with camera feed, digital twin, and dashboard.
    Layout: 1280x720
    - Left: Camera (640x480)
    - Right: Digital Twin (480x480 centered)
    - Bottom: Dashboard (1280x240)
    """
    
    def __init__(self):
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = 0.7
        self.font_thickness = 2
        
    def draw_text_with_bg(self, img: np.ndarray, text: str, pos: Tuple[int, int], 
                        fg_color: Tuple[int, int, int], bg_color: Tuple[int, int, int]):
        """Draw text with background box."""
        (w, h), baseline = cv2.getTextSize(text, self.font, self.font_scale, self.font_thickness)
        x, y = pos
        cv2.rectangle(img, (x - 5, y - h - 5), (x + w + 5, y + baseline + 5), bg_color, -1)
        cv2.putText(img, text, pos, self.font, self.font_scale, fg_color, self.font_thickness)
        
    def annotate_camera(self, frame: np.ndarray, corners: List[Tuple[int, int]],
                        pieces: List[Detection], obstacles: List[Detection],
                        state: str, interaction_zone: List[Tuple[int, int]] = None) -> np.ndarray:
        """Annotate camera frame with detections."""
        annotated = frame.copy()
        
        # Draw interaction zone (Smart ROI)
        if interaction_zone and len(interaction_zone) > 0:
            pts = np.array(interaction_zone, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(annotated, [pts], True, (255, 255, 0), 2) # Cyan
        
        # Draw corner points
        for i, (cx, cy) in enumerate(corners):
            cv2.circle(annotated, (cx, cy), 8, COLOR_GREEN, -1)
            cv2.putText(annotated, f"C{i}", (cx + 10, cy), self.font, 0.5, COLOR_GREEN, 2)
        
        # Draw corner polygon
        if len(corners) == 4:
            pts = np.array(corners, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(annotated, [pts], True, COLOR_GREEN, 2)
        
        # Draw piece detections
        for det in pieces:
            x, y, w, h = det.bbox
            color = COLOR_WHITE if det.class_name.startswith("white") else COLOR_BLUE
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            
            # Draw anchor point (bottom-center)
            ax, ay = det.anchor
            cv2.circle(annotated, (ax, ay), 4, COLOR_ORANGE, -1)
            
            # Draw label
            label = f"{NAME_TO_SYM.get(det.class_name, '?')}"
            cv2.putText(annotated, label, (x, y - 5), self.font, 0.5, color, 2)
        
        # Draw obstacle detections
        for det in obstacles:
            x, y, w, h = det.bbox
            cv2.rectangle(annotated, (x, y), (x + w, y + h), COLOR_RED, 3)
            cv2.putText(annotated, det.class_name.upper(), (x, y - 10), self.font, 0.7, COLOR_RED, 2)
        
        # Draw state border
        border_color = COLOR_RED if state == "WAITING" else COLOR_GREEN
        cv2.rectangle(annotated, (0, 0), (annotated.shape[1] - 1, annotated.shape[0] - 1), border_color, 4)
        
        return annotated
    
    def render_dashboard(self, state: str, last_move: Optional[str], 
                        fen: str, turn: str, warning: Optional[str]) -> np.ndarray:
        """Render the dashboard panel."""
        dashboard = np.full((DASHBOARD_HEIGHT, TOTAL_WIDTH, 3), COLOR_DARK_BG, dtype=np.uint8)
        
        # Draw separator line
        cv2.line(dashboard, (0, 0), (TOTAL_WIDTH, 0), COLOR_WHITE, 2)
        
        y_offset = 50
        
        # State indicator
        state_color = COLOR_RED if state == "WAITING" else COLOR_GREEN
        cv2.circle(dashboard, (40, y_offset), 15, state_color, -1)
        cv2.putText(dashboard, f"State: {state}", (70, y_offset + 7), 
                    self.font, 0.8, COLOR_WHITE, 2)
        
        # Turn indicator
        turn_text = f"Turn: {turn.upper()}"
        cv2.putText(dashboard, turn_text, (300, y_offset + 7), 
                    self.font, 0.8, COLOR_WHITE, 2)
        
        # Last move
        move_text = f"Last Move: {last_move or 'None'}"
        cv2.putText(dashboard, move_text, (500, y_offset + 7), 
                    self.font, 0.8, COLOR_YELLOW if last_move else COLOR_WHITE, 2)
        
        # FEN (Full)
        cv2.putText(dashboard, f"FEN: {fen}", (40, y_offset + 60), 
                    self.font, 0.5, (150, 150, 150), 1)

        # Warning
        if warning:
            cv2.putText(dashboard, f"WARNING: {warning}", (40, y_offset + 100), 
                        self.font, 0.7, COLOR_RED, 2)
        
        # Controls help
        controls = "Controls: [Q] Quit | [R] Reset (Re-Calibrate)"
        cv2.putText(dashboard, controls, (40, DASHBOARD_HEIGHT - 30), 
                    self.font, 0.5, (100, 100, 100), 1)
        
        return dashboard
    
    def compose(self, camera_frame: np.ndarray, board_img: np.ndarray,
                corners: List[Tuple[int, int]], pieces: List[Detection],
                obstacles: List[Detection], game_state: GameState,
                interaction_zone: List[Tuple[int, int]] = None) -> np.ndarray:
        """Compose the final UI frame."""
        # Create composite canvas
        canvas = np.zeros((TOTAL_HEIGHT, TOTAL_WIDTH, 3), dtype=np.uint8)
        
        # Annotate camera frame
        annotated_camera = self.annotate_camera(
            camera_frame, corners, pieces, obstacles, game_state.state, interaction_zone
        )
        
        # Place camera on left (640x480)
        canvas[0:CAMERA_HEIGHT, 0:CAMERA_WIDTH] = annotated_camera
        
        # Place board on right (480x480 centered in 640x480 area)
        board_x_offset = CAMERA_WIDTH + (CAMERA_WIDTH - BOARD_SIZE) // 2  # Center horizontally
        board_y_offset = (CAMERA_HEIGHT - BOARD_SIZE) // 2  # Center vertically
        board_resized = cv2.resize(board_img, (BOARD_SIZE, BOARD_SIZE))
        
        # Fill right panel background
        canvas[0:CAMERA_HEIGHT, CAMERA_WIDTH:TOTAL_WIDTH] = COLOR_DARK_BG
        
        # Place board
        canvas[board_y_offset:board_y_offset + BOARD_SIZE, 
            board_x_offset:board_x_offset + BOARD_SIZE] = board_resized
        
        # Draw border around board
        border_color = COLOR_RED if game_state.state == "WAITING" else COLOR_GREEN
        cv2.rectangle(canvas, 
                    (board_x_offset - 2, board_y_offset - 2),
                    (board_x_offset + BOARD_SIZE + 2, board_y_offset + BOARD_SIZE + 2),
                    border_color, 2)
        
        # Render and place dashboard
        dashboard = self.render_dashboard(
            game_state.state, game_state.last_move,
            game_state.fen, game_state.turn, game_state.warning
        )
        canvas[CAMERA_HEIGHT:TOTAL_HEIGHT, 0:TOTAL_WIDTH] = dashboard
        
        return canvas

# =============================================================================
# INTERACTIVE GAME (Mode A)
# =============================================================================


class InteractiveGame:
    """
    Mode A: Human vs AI (Interactive UI).
    Manages the game state, user input, and Stockfish moves.
    Uses proper UICompositor with a blacked-out camera feed.
    """
    
    def __init__(self, stockfish: StockfishWrapper, resources: ResourceLoader):
        self.stockfish = stockfish
        self.resources = resources
        self.board = chess.Board()
        self.renderer = ChessBoardRenderer(resources)
        self.compositor = UICompositor()
        self.network = ChessNetwork() # Default localhost:8080
        
        # State
        self.selected_square: Optional[int] = None
        self.human_side = chess.WHITE
        self.last_move: Optional[chess.Move] = None
        self.game_over = False
        self.ai_thinking = False
        self.warning = None
        self.ai_move_ready = False
        self.ai_move_result = None
        self.ai_move_result = None
        self.paused = False # [PAUSE STATE]
        
        # [WHITE HINT STATE]
        self.white_hint: Optional[chess.Move] = None
        self.hint_calculating = False
        
        # UI Layout Constants (derived from UICompositor logic)
        self.BOARD_OFFSET_X = CAMERA_WIDTH + (CAMERA_WIDTH - BOARD_SIZE) // 2  # 720
        self.BOARD_OFFSET_Y = (CAMERA_HEIGHT - BOARD_SIZE) // 2  # 0
        
    def handle_click(self, x: int, y: int):
        """Handle mouse clicks for move input."""
        if self.game_over or self.board.turn != self.human_side:
            return
            
        # Translate global click to board local coordinates
        board_x = x - self.BOARD_OFFSET_X
        board_y = y - self.BOARD_OFFSET_Y
        
        # Check if click is within board area
        if not (0 <= board_x < BOARD_SIZE and 0 <= board_y < BOARD_SIZE):
            return
            
        col = board_x // SQUARE_SIZE
        row = 7 - (board_y // SQUARE_SIZE)
        
        if not (0 <= col < 8 and 0 <= row < 8):
            return
            
        square = chess.square(col, row)
        
        if self.selected_square is None:
            # Select
            piece = self.board.piece_at(square)
            if piece and piece.color == self.human_side:
                self.selected_square = square
        else:
            # Move
            move = chess.Move(self.selected_square, square)
            
            # Auto-promote to Queen for simplicity
            if self.board.piece_at(self.selected_square).piece_type == chess.PAWN:
                if chess.square_rank(square) in [0, 7]:
                    move = chess.Move(self.selected_square, square, promotion=chess.QUEEN)
            
            if move in self.board.legal_moves:
                self.board.push(move)
                self.last_move = move
                self.selected_square = None
                self.warning = None
            else:
                # Change selection?
                piece = self.board.piece_at(square)
                if piece and piece.color == self.human_side:
                    self.selected_square = square
                else:
                    self.selected_square = None
                    # self.warning = "Invalid Move"
                    
    def update(self):
        """Update game state (AI move)."""
        if self.paused:
            return

        if self.board.is_game_over():
            self.game_over = True
            return
            
        # Check if AI move is ready
        if hasattr(self, 'ai_move_ready') and self.ai_move_ready:
            if self.ai_move_result:
                print(f"[AI] Move found: {self.ai_move_result}")
                if self.ai_move_result in self.board.legal_moves:
                    
                    # [NETWORK] Send move BEFORE pushing to board (so we capture state)
                    self.network.send_best_move(self.board, self.ai_move_result, self.board.fen())
                    
                    self.board.push(self.ai_move_result)
                    self.last_move = self.ai_move_result
                    self.warning = None
                else:
                    print(f"[AI] Generated illegal move: {self.ai_move_result}")
            
            self.ai_thinking = False
            self.ai_move_ready = False
            self.ai_move_result = None

        if self.board.turn != self.human_side and not self.ai_thinking:
            # Start AI Thread
            self.ai_thinking = True
            
            # [WHITE HINT] Reset hint state for next turn
            self.white_hint = None
            self.hint_calculating = False
            
            self.ai_move_ready = False
            self.ai_move_result = None
            
            # Capture FEN for the thread
            current_fen = self.board.fen()
            
            def think_task():
                try:
                    move = self.stockfish.get_best_move(current_fen)
                    self.ai_move_result = move
                except Exception as e:
                    print(f"[AI THREAD ERROR] {e}")
                    self.ai_move_result = None
                finally:
                    self.ai_move_ready = True
                    
            threading.Thread(target=think_task, daemon=True).start()

        # [WHITE HINT LOGIC]
        if self.board.turn == self.human_side and not self.hint_calculating and self.white_hint is None:
            self.hint_calculating = True
            current_fen = self.board.fen()
            
            def hint_task():
                try:
                    # Request max strength hint
                    move = self.stockfish.get_best_move(current_fen, time_limit=0.5)
                    self.white_hint = move
                    # print(f"[HINT] Best move for White: {move}")
                except Exception as e:
                    print(f"[HINT ERROR] {e}")
                finally:
                    self.hint_calculating = False
            
            threading.Thread(target=hint_task, daemon=True).start()
            
    def render(self) -> np.ndarray:
        """Render the game board using Global UI Compositor."""
        # 1. Create Black Screen for Camera Area
        black_frame = np.zeros((CAMERA_HEIGHT, CAMERA_WIDTH, 3), dtype=np.uint8)
        
        # Add Text to Black Screen
        cv2.putText(black_frame, "INTERACTIVE MODE", (50, 200), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, COLOR_GREEN, 2)
        cv2.putText(black_frame, "HUMAN VS STOCKFISH", (50, 260), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_WHITE, 2)
        cv2.putText(black_frame, "Click Board to Play", (50, 320), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_YELLOW, 1)

        # 2. Render Digital Twin
        board_img = self.renderer.render_with_highlight(self.board, self.last_move)
        
        # Draw selection
        if self.selected_square is not None:
            x = chess.square_file(self.selected_square) * SQUARE_SIZE
            y = (7 - chess.square_rank(self.selected_square)) * SQUARE_SIZE
            cv2.rectangle(board_img, (x, y), (x + SQUARE_SIZE, y + SQUARE_SIZE), COLOR_GREEN, 3)
            
        # [WHITE HINT RENDER]
        if self.white_hint:
            # Draw Blue Arrow for Hint
            start_sq = self.white_hint.from_square
            end_sq = self.white_hint.to_square
            
            x1 = chess.square_file(start_sq) * SQUARE_SIZE + SQUARE_SIZE // 2
            y1 = (7 - chess.square_rank(start_sq)) * SQUARE_SIZE + SQUARE_SIZE // 2
            x2 = chess.square_file(end_sq) * SQUARE_SIZE + SQUARE_SIZE // 2
            y2 = (7 - chess.square_rank(end_sq)) * SQUARE_SIZE + SQUARE_SIZE // 2
            
            cv2.arrowedLine(board_img, (x1, y1), (x2, y2), (255, 0, 0), 5, tipLength=0.3)
            self.warning = f"HINT: {self.white_hint}"
            
        # 3. Create Game State for Dashboard
        turn_str = "white" if self.board.turn == chess.WHITE else "black"
        state_str = "THINKING" if self.ai_thinking else "YOUR TURN"
        if self.game_over:
            state_str = "GAME OVER"
        
        # Using the GameState dataclass expected by UICompositor
        # Using self.board.fen() is simple
        current_state = GameState(
            state="STABLE", # Green border
            fen=self.board.fen(),
            last_move=str(self.last_move) if self.last_move else None,
            warning=state_str if not self.warning else self.warning,
            turn=turn_str
        )
        
        # 4. Compose
        composite = self.compositor.compose(
            black_frame, board_img, 
            [], [], [], # No corners, pieces, obstacles
            current_state
        )
        
        # [PAUSE OVERLAY]
        if self.paused:
            overlay = composite.copy()
            cv2.rectangle(overlay, (0, 0), (TOTAL_WIDTH, TOTAL_HEIGHT), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, composite, 0.3, 0, composite)
            cv2.putText(composite, "GAME PAUSED", (TOTAL_WIDTH//2 - 150, TOTAL_HEIGHT//2), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)
        
        return composite

    def run(self):
        """Main loop for Interactive Mode."""
        window_name = "Interactive Chess (Human vs Stockfish)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        # cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        
        def mouse_callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                self.handle_click(x, y)
                
        cv2.setMouseCallback(window_name, mouse_callback)
        cv2.resizeWindow(window_name, TOTAL_WIDTH, TOTAL_HEIGHT)
        
        print(">>> STARTING INTERACTIVE MODE (Human vs Stockfish)...")
        
        while True:
            self.update()
            try:
                frame = self.render()
                cv2.imshow(window_name, frame)
            except Exception as e:
                print(f"Render Error: {e}")
                break
            
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q') or key == ord('Q'): # ESC or Q
                break
            elif key == ord('r'):
                self.board.reset()
                self.game_over = False
                self.last_move = None
            elif key == 32: # SPACE
                self.paused = not self.paused
                print(f"[INFO] Game {'PAUSED' if self.paused else 'RESUMED'}")
                
        cv2.destroyWindow(window_name)

# =============================================================================
# MAIN CHESS SYSTEM
# =============================================================================

class ChessSystem:
    """
    Master orchestrator for the chess game show system.
    Integrates all components and runs the main loop.
    """
    
    def __init__(self, source: str = "0"):
        self.source = source
        
        # Initialize components
        self.resources = ResourceLoader(RESOURCES_DIR)
        self.corner_detector = CornerDetector(MODELS_DIR / "modelCorner.pt", BOARD_ORIENTATION)
        self.piece_mapper = PieceMapper(MODELS_DIR / "best25e_2712.pt")
        self.obstacle_detector = ObstacleDetector(MODELS_DIR / "modelHand.pt")
        self.chess_logic = ChessLogic()
        self.board_renderer: Optional[ChessBoardRenderer] = None
        self.ui_compositor = UICompositor()
        
        # State
        self.current_state = GameState(
            state="WAITING",
            fen=self.chess_logic.get_fen(),
            last_move=None,
            warning=None,
            turn="white"
        )
        
        # Video capture
        self.cap: Optional[cv2.VideoCapture] = None
        
        # Stockfish
        self.stockfish = StockfishWrapper(STOCKFISH_PATH)
        self.pending_ai_move: Optional[chess.Move] = None

        # Network
        self.network = ChessNetwork()
        
        # Pause State & Caching
        self.paused = False
        self.corners_locked = False # [CORNER LOCK]
        self.last_corners: List[Tuple[int, int]] = []
        self.last_matrix = None # [CORNER LOCK]
        self.last_pieces: List[Detection] = []
        self.last_obstacles: List[Detection] = []
        self.last_frame: Optional[np.ndarray] = None # [PAUSE FREEZE]
        
    def initialize(self) -> bool:
        """Initialize all resources and models."""
        print("[INFO] Initializing Chess System...")
        
        # Load resources
        if not self.resources.load_all():
            print("[ERROR] Failed to load resources")
            return False
        
        self.board_renderer = ChessBoardRenderer(self.resources)
        
        # Initialize video capture
        if self.source.isdigit():
            self.cap = cv2.VideoCapture(int(self.source))
        else:
            self.cap = cv2.VideoCapture(self.source)
        
        if not self.cap.isOpened():
            print(f"[ERROR] Cannot open video source: {self.source}")
            return False
        
        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        
        # Auto-calibration state
        self.is_auto_calibrated = False
        self.calibration_attempts = 0
        self.max_calibration_attempts = 10
        
        print("[INFO] Chess System initialized successfully")
        print("[INFO] Waiting for auto-calibration...")
        return True
    
    def perform_auto_calibration(self, frame: np.ndarray) -> bool:
        """
        [AUTOMATIC] Perform deterministic calibration against Standard Start Board.
        
        Steps:
        1. Detect corners.
        2. Detect optimal orientation by matching Vision against Logic Board (Standard FEN).
        3. Lock Calibration.
        """
        self.calibration_attempts += 1
        print(f"[AUTO-CAL] Attempt {self.calibration_attempts}/{self.max_calibration_attempts}")
        
        # Step 1: Try to detect corners
        matrix, corners = self.corner_detector.process_frame(frame)
        if matrix is None or len(corners) < 4:
            print("[AUTO-CAL] Cannot detect 4 corners yet...")
            return False
        
        # Step 2: Auto-detect orientation against STANDARD BOARD
        # effectively "Reverse-Calibration"
        best_orient = self.corner_detector.detect_orientation_by_scoring(
            frame, 
            self.piece_mapper, 
            target_board=self.chess_logic.board  # The Source of Truth
        )
        
        # Step 3: Lock it
        self.is_auto_calibrated = True
        self.chess_logic.is_calibrated = True
        
        # Update State
        self.current_state.warning = None
        self.current_state.fen = self.chess_logic.get_fen() # Should be standard start
        
        print("[AUTO-CAL] ✓ Calibration successful! Orientation Locked.")
        print("[AUTO-CAL] System assumes Standard Starting Position.")
        return True
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process a single frame through the entire pipeline."""
        # Resize to expected dimensions
        frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT))
        
        # [PAUSE LOGIC]
        if self.paused:
            # Use frozen frame if available, else current
            display_frame = self.last_frame if self.last_frame is not None else frame
            display_frame = display_frame.copy() # Ensure we don't modify the cache
            
            # Draw PAUSED overlay
            overlay = display_frame.copy()
            cv2.rectangle(overlay, (0, 0), (CAMERA_WIDTH, CAMERA_HEIGHT), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, display_frame, 0.3, 0, display_frame) # Darken
            
            cv2.putText(display_frame, "SYSTEM PAUSED", (180, 240), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
            
            # Use cached values to maintain UI state
            corners = self.last_corners
            pieces = self.last_pieces
            obstacles = self.last_obstacles
            
            matrix = None # Don't re-compute
            state = self.current_state.state # Keep state
            
            # Override frame for composition
            frame = display_frame
            
        else:
            # --- NORMAL PROCESSING ---
            self.last_frame = frame.copy() # [PAUSE FREEZE] Update cache
            
            # AUTO-CALIBRATION: Run automatically if not calibrated
            if not self.is_auto_calibrated:
                if self.calibration_attempts < self.max_calibration_attempts:
                    self.current_state.state = "CALIBRATING"
                    self.current_state.warning = f"CALIBRATING... PLEASE RESET BOARD ({self.calibration_attempts}/{self.max_calibration_attempts})"
                    self.perform_auto_calibration(frame)
                else:
                    self.current_state.warning = "Auto-cal failed. Press R to reset."
            
            # Protocol A: Corner detection
            if not self.corners_locked:
                matrix, corners = self.corner_detector.process_frame(frame)
                # Only lock if we successfully found corners
                if corners and len(corners) == 4 and matrix is not None:
                    self.last_corners = corners
                    self.last_matrix = matrix
                    self.corners_locked = True
                    # print("[INFO] Corners LOCKED")
            else:
                # Use cached corners/matrix
                corners = self.last_corners
                matrix = self.last_matrix
            
            # Protocol C: Obstacle detection (Smart ROI)
            state, obstacles = self.obstacle_detector.get_state(frame, corners)
            self.last_obstacles = obstacles # Cache
            
            # Only process game logic if calibrated
            if self.is_auto_calibrated:
                self.current_state.state = state
            
            # Protocol B: Piece detection (only if stable and corners found)
            pieces = []
            positions = {}
            
            if matrix is not None:
                pieces, positions = self.piece_mapper.process_frame(frame, matrix)
                self.last_pieces = pieces # Cache
                
                # Protocol D: Chess logic (only when stable AND calibrated)
                if state == "STABLE" and positions and self.is_auto_calibrated:
                    success, move_san = self.chess_logic.update(positions)
                    if move_san:
                        self.current_state.last_move = move_san
                        print(f"[MOVE] {move_san}")
                    
                    if not success:
                        self.current_state.warning = "Invalid move detected"
                    else:
                        self.current_state.warning = None
        
        # Update state
        self.current_state.fen = self.chess_logic.get_fen()
        self.current_state.turn = self.chess_logic.get_turn()
        
        # LOGIC SUPREMACY: Digital Twin renders from python-chess state, NOT raw vision
        board_img = self.board_renderer.render_with_highlight(
            self.chess_logic.board,  # This is the source of truth
            self.chess_logic.last_move
        )
        
        # [STOCKFISH] Logic Branching & Arrow Rendering
        if self.current_state.turn == "black" and self.is_auto_calibrated:
            if not self.pending_ai_move:
                # Get suggestion (using short time to maintain FPS)
                self.pending_ai_move = self.stockfish.get_best_move(self.current_state.fen, time_limit=0.1)
                if self.pending_ai_move:
                    print(f"[STOCKFISH] Suggested Move: {self.pending_ai_move}")
                    
                    # [NETWORK] Send suggestion immediately
                    self.network.send_best_move(self.chess_logic.board, self.pending_ai_move, self.chess_logic.get_fen())
        else:
            self.pending_ai_move = None
            
        if self.pending_ai_move:
            # Update warning/status to show user what to do
            self.current_state.warning = f"AI SUGGESTS: {self.pending_ai_move}"
        
        # Compose final UI
        composite = self.ui_compositor.compose(
            frame, board_img, corners, pieces, obstacles, self.current_state,
            interaction_zone=self.obstacle_detector.last_zone
        )
        
        return composite
    
    def handle_key(self, key: int) -> bool:
        """Handle keyboard input. Returns False to quit."""
        if key == ord('q') or key == ord('Q'):
            return False
        elif key == ord('r') or key == ord('R'):
            # Reset and re-calibrate
            self.chess_logic.reset()
            self.chess_logic.is_calibrated = False
            self.is_auto_calibrated = False
            self.calibration_attempts = 0
            self.current_state.last_move = None
            self.current_state.warning = None
            self.corners_locked = False # [CORNER LOCK] FORCE RETRY
            print("[INFO] Board reset - will re-calibrate")
        elif key == 32: # SPACE
            self.paused = not self.paused
            if not self.paused:
                self.corners_locked = False # [CORNER LOCK] Unlock on Resume
                print("[INFO] Game RESUMED - Refinding corners...")
            else:
                print("[INFO] Game PAUSED")
        return True
    
    def run(self):
        """Main loop."""
        if not self.initialize():
            return
        
        window_name = "Smart Chess Game Show"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, TOTAL_WIDTH, TOTAL_HEIGHT)
        
        print("[INFO] Starting main loop. Press 'Q' to quit.")
        
        fps_counter = 0
        fps_start = time.time()
        fps = 0
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    # Loop video if it ends
                    if not self.source.isdigit():
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        break
                
                # Process frame
                composite = self.process_frame(frame)
                
                # FPS calculation
                fps_counter += 1
                if time.time() - fps_start >= 1.0:
                    fps = fps_counter
                    fps_counter = 0
                    fps_start = time.time()
                
                # Draw FPS
                cv2.putText(composite, f"FPS: {fps}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_GREEN, 2)
                
                # Display
                cv2.imshow(window_name, composite)
                
                # Handle input
                key = cv2.waitKey(1) & 0xFF
                if not self.handle_key(key):
                    break
                    
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources."""
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Chess System shutdown complete")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Smart Chess Game Show - OpenCV Only")
    parser.add_argument("--source", type=str, default="0", 
                        help="Video source: camera index (0) or video file path")
    parser.add_argument("--orientation", type=int, default=0, choices=[0, 1, 2, 3],
                        help="Board orientation: 0=0°, 1=90°, 2=180°, 3=270°")
    args = parser.parse_args()
    
    global BOARD_ORIENTATION
    BOARD_ORIENTATION = args.orientation
    
    system = ChessSystem(source=args.source)
    system.run()


if __name__ == "__main__":
    print(">>> INTEGRATING STOCKFISH FOR DUAL-MODE DEPLOYMENT...")
    print("Select Mode:")
    print("1. Interactive Mode (Human vs Stockfish UI)")
    print("2. Vision Mode (Physical Board with Stockfish)")
    
    # Default to 2 for now or ask input? 
    # Since this is a specialized system, I'll use input() but with a timeout if possible?
    # Or just input() since it's a script.
    
    try:
        # Simple input with specific prompt
        mode = input("Select Mode (1/2) [Default: 2]: ").strip()
    except:
        mode = "2" # Handle non-interactive start
        
    if mode == "1":
        # Interactive Mode
        # Need to init resources manually
        wrapper = StockfishWrapper(STOCKFISH_PATH)
        loader = ResourceLoader(RESOURCES_DIR)
        if loader.load_all():
            game = InteractiveGame(wrapper, loader)
            game.run()
        else:
            print("[ERROR] Could not load resources for Interactive Mode.")
    else:
        # Vision Mode (Default)
        main()
