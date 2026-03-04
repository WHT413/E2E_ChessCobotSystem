from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import cv2
import numpy as np
import re
from ultralytics import YOLO
import chess
import asyncio
import json
import time
import os
import chess.engine

# Project modules (must exist in your environment, same as test6.py)
from chess_utils.detection.fallback_corner_detector import (
    detect_corners_fallback,
    decide_rotation_strict,
    corners_from_detections,
)

from network.socket_client import TCPClient
from core.chess_mapping import ChessMapper
from core.chess_processing import ChessProcessor
from fixed_corners import FixedCornerDetector
from core.stockfish_wrapper import StockfishUCI
from renderFen2Img import render_fen

# Map detector class names → chess glyphs (same intent as in test6.py)
NAME_TO_SYM: Dict[str, str] = {
    "white_pawn": "P", "white_knight": "N", "white_bishop": "B",
    "white_rook": "R", "white_queen": "Q", "white_king": "K",
    "black_pawn": "p", "black_knight": "n", "black_bishop": "b",
    "black_rook": "r", "black_queen": "q", "black_king": "k",
}

############ Load Model ############
def load_models(board_path: str, piece_path: str, hand_path: str) -> Tuple[YOLO, YOLO, YOLO]:
    """Load YOLO models with basic checks."""
    bp, pp, hp = Path(board_path), Path(piece_path), Path(hand_path)
    if not bp.is_file():
        raise FileNotFoundError(f"Board model not found: {bp}")
    if not pp.is_file():
        raise FileNotFoundError(f"Piece model not found: {pp}")
    if not hp.is_file():
        raise FileNotFoundError(f"Hand model not found: {hp}")
    return YOLO(str(bp)), YOLO(str(pp)), YOLO(str(hp))

############ Recog Board ############
def checkCorners(detections, xC, yC):
    print(detections)
    detectionsN = []
    checkC = {}
    checkC["white_left"] = False
    checkC["white_right"] = False
    checkC["black_left"] = False
    checkC["black_right"] = False
    for (cN, (x1, y1, x2, y2)) in detections:
        if x1 < xC and y1 < yC:
            cN = "white_right"
        if x1 > xC and y1 < yC:
            cN = "white_left"
        if x1 < xC and y1 > yC:
            cN = "black_left"
        if x1 > xC and y1 > yC:
            cN = "black_right"
        if not checkC[cN]:
            detectionsN.append((cN, (x1, y1, x2, y2)))
            checkC[cN] = True
    print(detectionsN)
    return detectionsN

def getCornerModel(frame, board_model, conf=0.5, iou=0.5):
    board_res = board_model(frame, verbose=False)
    xMin, xMax, yMin, yMax = 10000, 0, 10000, 0
    detections, board_bbox = [], None
    for r in board_res:
        if r.boxes is None:
            continue
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        clss = r.boxes.cls.cpu().numpy()
        for (x1, y1, x2, y2), conf, cls_id in zip(boxes, confs, clss):
            cls_name = r.names[int(cls_id)]
            if x1 < xMin: xMin = x1
            if y1 < yMin: yMin = y1
            if x2 > xMax: xMax = x2
            if y2 > yMax: yMax = y2
            detections.append((cls_name, (float(x1), float(y1), float(x2), float(y2))))
            if cls_name == "board" and conf > 0.5:
                board_bbox = (int(x1), int(y1), int(x2), int(y2))

    xC = (xMin + xMax) / 2
    yC = (yMin + yMax) / 2
    detectionsN = checkCorners(detections, xC, yC)        
    corners, _ = detect_corners_fallback(detectionsN, board_bbox)
    cornersH = corners_from_detections(detectionsN)
    print(corners)
    print(cornersH)
    return corners, cornersH

def normalize_board(raw_board: List[List[str]]) -> List[List[str]]:
    """Convert mapper's board names to glyph grid with '.' for empty."""
    out: List[List[str]] = []
    for r in range(8):
        row_chars: List[str] = []
        for c in range(8):
            name = raw_board[r][c]
            row_chars.append(NAME_TO_SYM.get(name, ".") if name else ".")
        if len(row_chars) != 8:
            raise ValueError(f"Row {r} width != 8")
        out.append(row_chars)
    if len(out) != 8:
        raise ValueError("Board height != 8")
    return out

############ Recog Hand ############
def is_hand_in_area(hand_box: List[float], area: Tuple[float, float, float, float]) -> bool:
        """Check if hand bounding box overlaps with board area."""
        if area is None:
            return False
        
        x1, y1, x2, y2 = hand_box
        ax_min, ay_min, ax_max, ay_max = area
        
        # Check if rectangles overlap
        return not (x2 < ax_min or x1 > ax_max or y2 < ay_min or y1 > ay_max)

def detect_hand(frame: np.ndarray, hand_model: YOLO, cornersH: Dict[str, tuple[float, float]]) -> bool:
    """Check whether hand is in board"""
    results = hand_model(frame, conf=0.5, iou=0.5)
    hand_in_board = False
    board_area = None

    if cornersH: 
        board_area = calculate_board_area_with_offset(cornersH)

    for result in results:
        if result.boxes is None:
            continue
        
        boxes = result.boxes.xyxy.cpu().numpy()
        scores = result.boxes.conf.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy()

        for box, score, cls in zip(boxes, scores, classes):
            # Check if hand is in board area
            if board_area and is_hand_in_area(box, board_area):
                hand_in_board = True
    return hand_in_board

############ Recog Piece ############
def detect_pieces(img: np.ndarray, piece_model: YOLO) -> List[Dict[str, Any]]:
    """Run piece detector and return a list of detection dicts."""
    results = piece_model(img, conf=0.50, iou=0.5, verbose=False)
    pieces: List[Dict[str, Any]] = []
    for r in results:
        if r.boxes is None:
            continue
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        clss = r.boxes.cls.cpu().numpy()
        for (x1, y1, x2, y2), conf, cls_id in zip(boxes, confs, clss):
            pieces.append({
                "class_name": r.names[int(cls_id)],
                "confidence": float(conf),
                "box": [int(x1), int(y1), int(x2), int(y2)],
            })

    return pieces
    
def calculate_board_area_with_offset(cornersH: Dict[str, tuple[float, float]]) -> Tuple[float, float, float, float]:
    """Calculate board area with offset for hand detection."""
    if not cornersH or len(cornersH) < 4:
        return None
    offset_percentage = 0.2

    # Get all corner coordinates
    coords = list(cornersH.values())
    x_coords = [coord[0] for coord in coords]
    y_coords = [coord[1] for coord in coords]
    
    # Find bounding box
    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)
    
    # Add offset
    width = x_max - x_min
    height = y_max - y_min
    
    x_offset = int(width * offset_percentage)
    y_offset = int(height * offset_percentage)
    
    return (
        max(0, x_min - x_offset),
        max(0, y_min - y_offset),
        x_max + x_offset,
        y_max + y_offset
    )

############ Get FEN ############
def image_to_fen(img_path: str, board_model: YOLO, piece_model: YOLO, turn: str = "w") -> str:
    """
    Single-image pipeline (test6 style):
    - detect board/corners
    - detect pieces
    - homography mapping
    - assign to cells with rotation
    - build FEN board part and append placeholders for the rest fields
    """
    processor = ChessProcessor()
    mapper = ChessMapper()
    proc_size = processor.get_processing_size()

    frame = cv2.imread(img_path)
    if frame is None:
        raise FileNotFoundError(f"Cannot read image: {img_path}")
    frame = cv2.resize(frame, (640, 480))

    confC = 0.5
    iouC = 0.5
    cornersH, corners = getCornerModel(frame, confC, iouC)
    print(cornersH)
    print(corners)
    #corners = getCornerFix()

    if corners is None:
        raise RuntimeError("Corners not found")

    # Pieces
    pieces = detect_pieces(piece_model, frame)

    # Homography and mapping
    H, _grid = mapper.create_homography_mapping(cornersH, frame, proc_size)
    mapped = mapper.map_pieces_to_board_space(pieces, H)

    # Orientation and cell assignment
    
    #angle_rotation = decide_rotation_strict(label_corners)
    angle_rotation = decide_rotation_strict(corners)
    mapping_result = mapper.assign_pieces_to_cells(mapped, rotation=angle_rotation)
    
    # print(f"[DEBUG] Mapping result: {mapping_result}")

    # Normalize to glyphs and build FEN
    cand_board = normalize_board(mapping_result.chess_board)
    fen_board = board_to_fen_board(cand_board)
    fen_full = f"{fen_board} {turn} - - 0 1"
    # print(f"[DEBUG] FEN: {fen_full}")
    return fen_full

def _compress_row_to_fen(row_chars: List[str]) -> str:
    """Compress '.' runs to digits to produce a FEN row."""
    fen_row, run = [], 0
    for ch in row_chars:
        if ch == ".":
            run += 1
        else:
            if run:
                fen_row.append(str(run))
                run = 0
            fen_row.append(ch)
    if run:
        fen_row.append(str(run))
    return "".join(fen_row)

def board_to_fen_board(board_chars: List[List[str]]) -> str:
    """Convert 8x8 glyph grid to FEN board part."""
    if len(board_chars) != 8 or any(len(r) != 8 for r in board_chars):
        raise ValueError("Invalid board size")
    rows = [_compress_row_to_fen(row) for row in board_chars]
    return "/".join(rows)

def getPiece(board, sq):
    board = board
    piece = board.piece_at(sq)
    if piece != None:
        return piece.symbol()
    return ""

def getMoveFromFen(fen: str, timeLimit=0.1  ):
    # fen = fen.replace("b ", "w ")
    # Load Stockfish engine
    engine_path = "/home/student/bin/stockfish/stockfish/stockfish"
    engine = chess.engine.SimpleEngine.popen_uci(engine_path)

    # Start analysis
    board = chess.Board(fen)
    limit = chess.engine.Limit(time=timeLimit)
    result = engine.analyse(board, limit)

    # Get best move
    bestmove = result["pv"][0]

    # Close engine
    engine.quit()
    
    return bestmove.uci()

def getMove(fen: str):
    board = chess.Board(fen)
    return board.legal_moves

def checkChange(fen1: str, fen2: str):
    change = []
    board1 = chess.Board(fen1)
    board2 = chess.Board(fen2)
    for c in ["a", "b", "c", "d", "e", "f", "g", "h"]:
        for i in range(1, 9):
            sq = str(c) + str(i)
            square = chess.parse_square(sq)
            piece1 = getPiece(board1, square)
            piece2 = getPiece(board2, square)
            if piece1 != piece2:
                change.append((sq, piece1, piece2))

    return len(change), change

def checkQueenKing(fen1: str, fen2: str):
    board1 = chess.Board(fen1)
    board2 = chess.Board(fen2)
    nQ1, nK1, nq1, nk1 = 0, 0, 0, 0
    nQ2, nK2, nq2, nk2 = 0, 0, 0, 0
    for c in ["a", "b", "c", "d", "e", "f", "g", "h"]:
        for i in range(1, 9):
            sq = str(c) + str(i)
            square = chess.parse_square(sq)
            piece1 = getPiece(board1, square)
            piece2 = getPiece(board2, square)
            if piece1 == "Q":
                nQ1 += 1
            if piece1 == "K":
                nK1 += 1
            if piece1 == "q":
                nq1 += 1
            if piece1 == "k":
                nk1 += 1
            if piece2 == "Q":
                nQ2 += 1
            if piece2 == "K":
                nK2 += 1
            if piece2 == "q":
                nq2 += 1
            if piece2 == "k":
                nk2 += 1
    if (((nK1 >= 2 or nk1 >= 2) and (nQ1 == 0 or nq1 == 0)) or ((nK2 >= 2 or nk2 >= 2) and (nQ2 == 0 or nq2 == 0)) or
        ((nK1 == 0 or nk1 == 0) or (nQ1 >= 2 or nq1 >= 2)) or ((nK2 == 0 or nk2 == 0) or (nQ2 >= 2 or nq2 >= 2))
        ):
        print("Error: More than one King or missing Queen")        
        for c in ["a", "b", "c", "d", "e", "f", "g", "h"]:
            for i in range(1, 9):
                sq = str(c) + str(i)
                square = chess.parse_square(sq)
                piece1 = getPiece(board1, square)
                piece2 = getPiece(board2, square)
                if piece1 != piece2:
                    if piece1 in ["K", "k", "Q", "q"] and piece2 in ["K", "k", "Q", "q"]:
                        board2.set_piece_at(chess.parse_square(sq), chess.Piece.from_symbol(piece1))
                        print("Fix: " + sq + " " + piece2 + " to " + piece1)

    return board2.fen()

def checkRecogErr(fen1: str, fen2: str):
    fenC = checkQueenKing(fen1, fen2)
    board1 = chess.Board(fen1)
    board2 = chess.Board(fenC)
    for c in ["a", "b", "c", "d", "e", "f", "g", "h"]:
        for i in range(1, 9):
            sq = str(c) + str(i)
            square = chess.parse_square(sq)
            piece1 = getPiece(board1, square)
            piece2 = getPiece(board2, square)
            if piece1 != piece2:
                if ((piece1 in ["K", "Q", "B", "P", "N", "R"] and piece2 in ["K", "Q", "B", "P", "N", "R"]) or
                   (piece1 in ["k", "q", "b", "p", "n", "r"] and piece2 in ["k", "q", "b", "p", "n", "r"])):
                    board2.set_piece_at(chess.parse_square(sq), chess.Piece.from_symbol(piece1))
                    print("Fix: " + sq + " " + piece2 + " to " + piece1)
    fenC = board2.fen()
    return fenC


def isMove(sq1, piece11, piece12, sq2, piece21, piece22):
    if (piece12 == "" and piece21 == "" and piece11 == piece22):
        return 1  # Move
    if (piece11 == "" and piece22 == "" and piece12 == piece21):
        return 1  # Move
    
    if (piece11 == "" and piece22 == piece12 and piece21 == ""):
        return 2  # Attack
    if (piece22 == "" and piece12 == piece21):
        return 2  # Attack
    if (piece12 == "" and piece11 == piece22):
        return 2  # Attack
    
    if (piece11 == "" and piece22 == "" and 
        (piece11 in ["K", "Q"] and piece22 in ["K", "Q"]) or
        (piece11 in ["k", "q"] and piece22 in ["k", "q"])
        ):
        return 3  # Move Recog Error
    if (piece11 == "" and piece22 == "" and 
        (piece12 in ["K", "Q"] and piece21 in ["K", "Q"]) or
        (piece12 in ["k", "q"] and piece21 in ["k", "q"])
        ):
        return 3  # Move Recog Error
    
    if (piece11 == "" and piece21 == "" and 
        (piece12 in ["K", "Q"] and piece22 in ["K", "Q"]) or
        (piece12 in ["k", "q"] and piece22 in ["k", "q"])
        ):
        return 4  # Attack Recog Error
    if (piece22 == "" and 
        (piece12 in ["K", "Q"] and piece21 in ["K", "Q"]) or
        (piece12 in ["k", "q"] and piece21 in ["k", "q"])
        ):
        return 4  # Attack Recog Error
    if (piece12 == "" and
        (piece11 in ["K", "Q"] and piece22 in ["K", "Q"]) or
        (piece11 in ["k", "q"] and piece22 in ["k", "q"])
        ):
       return 4  # Attack Recog Error
    return 0

def getNextFEN(fen1: str, fen2: str):
    checkMove = 0
    moves = getMove(fen1)
    fenC = checkRecogErr(fen1, fen2)
    print("[DEBUG] After checking check recog error, fen2:", fenC)

    lC, change = checkChange(fen1, fenC)
    print("[DEBUG] Detected changes:", change)
    boardN = chess.Board(fenC)
    check = {}
    for i in range(lC):
        if i in check:
            continue
        (sq, piece1, piece2) = change[i]
        check[i] = 1
        state = 0
        # Check Move and Attack
        for j in range(lC):
            if j not in check:
                (sqN, piece1N, piece2N) = change[j]
                mv = isMove(sq, piece1, piece2, sqN, piece1N, piece2N)
                #mvS = chess.Move.from_uci(sq + sqN)
                if mv == 1:
                    print("Move: " + str(change[i]) + " - " + str(change[j]))
                    move1 = chess.Move.from_uci(sq + sqN)
                    move2 = chess.Move.from_uci(sqN + sq)
                    if move1 in moves:
                        print("Legal Move: " + str(move1))
                    elif move2 in moves:
                        print("Legal Move: " + str(move2))
                    else:
                        print("Illegal Move: " + str(move1))
                        checkMove = 1
                    check[j] = 1
                    state = 1
                    break
                elif mv == 3:
                    print("Move Recog Err: " + str(change[i]) + " - " + str(change[j]))
                    move1 = chess.Move.from_uci(sq + sqN)
                    move2 = chess.Move.from_uci(sqN + sq)
                    if move1 in moves:
                        print("Legal Move: " + str(move1))
                    elif move2 in moves:
                        print("Legal Move: " + str(move2))
                    else:
                        print("Illegal Move: " + str(move1))
                        checkMove = 1
                    boardN.set_piece_at(chess.parse_square(sqN), chess.Piece.from_symbol(piece1))
                    check[j] = 1
                    state = 1
                    break
                elif mv == 2:
                    print("Attack: " + str(change[i]) + " - " + str(change[j]))
                    move1 = chess.Move.from_uci(sq + sqN)
                    move2 = chess.Move.from_uci(sqN + sq)
                    if move1 in moves:
                        print("Legal Move: " + str(move1))
                    elif move2 in moves:
                        print("Legal Move: " + str(move2))
                    else:
                        print("Illegal Move: " + str(move1))
                        checkMove = 1

                    check[j] = 1
                    state = 1
                    break
                elif mv == 4:
                    print("Attack Recog Err: " + str(change[i]) + " - " + str(change[j]))
                    move1 = chess.Move.from_uci(sq + sqN)
                    move2 = chess.Move.from_uci(sqN + sq)
                    if move1 in moves:
                        print("Legal Move: " + str(move1))
                    elif move2 in moves:
                        print("Legal Move: " + str(move2))
                    else:
                        print("Illegal Move: " + str(move1))
                        checkMove = 1
                    boardN.set_piece_at(chess.parse_square(sqN), chess.Piece.from_symbol(piece1))
                    check[j] = 1
                    state = 1
                    break
        # Check Missing
        if state == 0:
            if piece2 == "":
                print("Missing: " + str(change[i]))
                boardN.set_piece_at(chess.parse_square(sq), chess.Piece.from_symbol(piece1))
            else:
                print("Recog Err: " + str(change[i]))
                boardN.set_piece_at(chess.parse_square(sq), chess.Piece.from_symbol(piece2))

    fenN = boardN.fen()
    return fenN, checkMove

def getFENnewO(frame, corner_detector, hand_model, piece_model, mapper, proc_size, FEN_last):
    FEN_new = None
    try:
        # new_fen = frame_to_fen(frame, board_model, piece_model, hand_model)
        # cornersH, corners = getCornerModel(frame, board_model, confC, iouC)
        cornersH = corner_detector.get_corners(frame)
        print(cornersH)
        #_, cornersH = getCornerModel(frame, corner_detector)
        if cornersH is None:
            raise RuntimeError("Corners not found")
        hand_in_board = detect_hand(frame, hand_model, cornersH)
        if hand_in_board:
            return None
            #print("[DEBUG] Hand detected, using the previous fen")

        pieces = detect_pieces(frame, piece_model)
        H, _grid = mapper.create_homography_mapping(cornersH, frame, proc_size)
        mapped = mapper.map_pieces_to_board_space(pieces, H)
        # angle_rotation = decide_rotation_strict(corners)
        mapping_result = mapper.assign_pieces_to_cells(mapped)
        # mapping_result = mapper.assign_pieces_to_cells(mapped, rotation=angle_rotation)
        cand_board = normalize_board(mapping_result.chess_board)
        FEN_board = board_to_fen_board(cand_board)

        board=chess.Board(FEN_last)

        side = "w" if board.turn == chess.WHITE else "b"
        FEN_new = f"{FEN_board} {side} - - 0 1"
        print(f"[DEBUG] Detected FEN: {FEN_new}")
    except Exception as e:
        print("FEN detection error:", e)
    return FEN_new

def getFENnew(frame, cornersH, hand_model, piece_model, mapper, proc_size, FEN_last):
    FEN_new = None
    try:
        if cornersH is None:
            raise RuntimeError("Corners not found")
        hand_in_board = detect_hand(frame, hand_model, cornersH)
        if hand_in_board:
            return None

        pieces = detect_pieces(frame, piece_model)
        H, _grid = mapper.create_homography_mapping(cornersH, frame, proc_size)
        mapped = mapper.map_pieces_to_board_space(pieces, H)
        mapping_result = mapper.assign_pieces_to_cells(mapped)
        cand_board = normalize_board(mapping_result.chess_board)
        FEN_board = board_to_fen_board(cand_board)

        board=chess.Board(FEN_last)

        side = "w" if board.turn == chess.WHITE else "b"
        FEN_new = f"{FEN_board} {side} - - 0 1"
        print(f"[DEBUG] Detected FEN: {FEN_new}")
    except Exception as e:
        print("FEN detection error:", e)
    return FEN_new

def getFigure(fen: str):
    fenF = re.match(r'(.*?) ', fen).group(1)
    return fenF

def changeState(fen: str):
    if " w " in fen:
        fen = fen.replace(" w ", " b ")
        print("convert w to b", fen)
    elif " b " in fen:
        fen = fen.replace(" b ", " w ")
        print("convert b to w", fen)
    return fen

############ Play Chess ############
def showStatus(fen: str):
    board = chess.Board(fen)
    print('')
    print("Board:")
    print(board)
    print('')
    print("Is valid:", board.is_valid())
    print("Is check:", board.is_check())
    print("Is checkmate:", board.is_checkmate())
    print("Is stalemate:", board.is_stalemate())
    print("Is insufficient material:", board.is_insufficient_material())
    print("Is game over:", board.is_game_over())
    print("Legal moves:", list(board.legal_moves))
    print('')
    return

############ Run ############  
def buildMoveEventFrom(fen1: str, fen2: str) -> dict:
    b1 = chess.Board(fen1)
    b2 = chess.Board(fen2)

    moves = list(b1.legal_moves)
    found = None
    for mv in moves:
        b1.push(mv)
        if b1.board_fen() == b2.board_fen():
            found = mv
            b1.pop()
            break
        b1.pop()
    if found is None:
        print(f"No matching move found between:\n{fen1}\n{fen2}")
        return {}
    mv = found

    # Determine move type
    if b1.is_castling(mv):
        mv_type = "castle"
    elif b1.is_capture(mv) or b1.is_en_passant(mv):
        mv_type = "attack"
    else:
        mv_type = "move"

    from_sq, to_sq = mv.from_square, mv.to_square
    from_piece = b1.piece_at(from_sq)
    to_piece = b1.piece_at(to_sq)
    san = b1.san(mv)
    # Push to check for check
    b1.push(mv)
    results_in_check = b1.is_check()

    def piece_label(p):
        if p is None:
            return None
        color = "white" if p.color == chess.WHITE else "black"
        names = {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen", 6: "king"}
        return f"{color}_{names[p.piece_type]}"

    side = "w" if b1.turn == chess.WHITE else "b"
    board_fen_after_move = b1.board_fen()
    updated_fen = f"{board_fen_after_move} {side} - - 0 1"

    return {
        "fen_str": board_fen_after_move,
        "move": {
            "type": mv_type,
            "from": chess.square_name(from_sq),
            "to": chess.square_name(to_sq),
            "from_piece": piece_label(from_piece),
            "to_piece": piece_label(to_piece),
            "notation": san,
            "results_in_check": results_in_check,
            "updated_fen": updated_fen
        }
    }

def buildMoveEventFromStockfish(fen: str, engineSF, timeLimit=0.5) -> dict:
    """Get best move from Stockfish and format it like buildMoveEventFrom"""
    # Start analysis
    board = chess.Board(fen)
    print(board)
    limit = chess.engine.Limit(time=timeLimit)
    print(fen)
    result = engineSF.analyse(board, limit)

    white_fen = fen

    # Get best move
    bestmove = result["pv"][0]
    
    # Determine move type
    if board.is_castling(bestmove):
        mv_type = "castle"
    elif board.is_capture(bestmove) or board.is_en_passant(bestmove):
        mv_type = "attack"
    else:
        mv_type = "move"
    
    from_sq, to_sq = bestmove.from_square, bestmove.to_square
    from_piece = board.piece_at(from_sq)
    to_piece = board.piece_at(to_sq)
    san = board.san(bestmove)
    side = "w" if board.turn == chess.WHITE else "b"

    # Make the move to get the updated position
    board.push(bestmove)
    results_in_check = board.is_check()
    
    # Get updated FEN
    board_fen = board.board_fen()
    updated_fen = f"{board_fen} {side} - - 0 1"
    
    def piece_label(p):
        if p is None:
            return None
        color = "white" if p.color == chess.WHITE else "black"
        names = {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen", 6: "king"}
        return f"{color}_{names[p.piece_type]}"
    
    return {
        "fen_str": white_fen,
        "move": {
            "type": mv_type,
            "from": chess.square_name(from_sq),
            "to": chess.square_name(to_sq),
            "from_piece": piece_label(from_piece),
            "to_piece": piece_label(to_piece),
            "notation": san,
            "results_in_check": results_in_check
        }
    }

async def sendStockfishMove(current_fen: str):
    """Send Stockfish's best move to server"""
    tcp_client = TCPClient(host="127.0.0.1", port=8080)
    await tcp_client.connect()
    
    # Identify as AI client
    ai_identity = {
        "type": "ai_identify",
        "ai_id": "stockfish_ai"
    }
    await tcp_client.send(json.dumps(ai_identity))
    print("AI identified with server:", ai_identity)
    
    try:
        # Get Stockfish's best move
        move_event = buildMoveEventFromStockfish(current_fen, timeLimit=0.5)
        
        # Send to server
        await tcp_client.send(json.dumps(move_event))
        print("Sent Stockfish move:", move_event)
        
    except Exception as e:
        print(f"Error getting Stockfish move: {e}")
    
    await tcp_client.close()

def visualizePieces(frame: np.ndarray, pieces: List[Dict[str, Any]]) -> np.ndarray:
    """Draw piece detections on frame for debugging."""
    vis = frame.copy()
    for det in pieces:
        x1, y1, x2, y2 = map(int, det["box"])
        cls_name = det["class_name"]
        conf = det["confidence"]
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 1)
        label = f"{cls_name} {conf:.2f}"
        cv2.putText(vis, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 255, 0), 1)
    return vis
    
def processFrame(frame, piece_model):
    frame = cv2.resize(frame, (640, 480))
    frame = cv2.rotate(frame, cv2.ROTATE_180)

    frame_vis = frame.copy()
    frame_vis = visualizePieces(frame_vis, detect_pieces(frame, piece_model))
    cv2.imshow("Detections", frame_vis)

    return frame

async def main():
    BOARD_MODEL = "best_50e_2s_0.08_t.pt"
    PIECE_MODEL = "pieces_fintuning.pt"
    HAND_MODEL = "best_50e_hand_t.pt"

    engine_path = "/home/student/bin/stockfish/stockfish/stockfish"
    engineSF = chess.engine.SimpleEngine.popen_uci(engine_path)

    board_model, piece_model, hand_model = load_models(BOARD_MODEL, PIECE_MODEL, HAND_MODEL)
    corner_detector = FixedCornerDetector(BOARD_MODEL, detection_frames=5)
    processor = ChessProcessor()
    mapper = ChessMapper()
    proc_size = processor.get_processing_size()
    confC = 0.5
    iouC = 0.5

    cam = cv2.VideoCapture(1)
    # cam = cv2.VideoCapture("2025-10-03 17-19-26.mp4")
    #tcp_client = TCPClient(host="127.0.0.1", port=8080)
    #await tcp_client.connect()

    # Identify as AI client
    #ai_identity = {
    #    "type": "ai_identify",
    #    "ai_id": "chess_vision_ai"
    #}
    #await tcp_client.send(json.dumps(ai_identity))    
    #print("AI identified with server:", ai_identity)

    countF = 0

    ##### Get Corners
    cornersH = []
    while True:
        ok, frame = cam.read()
        if not ok:
            break  
        frame = processFrame(frame, piece_model)
        cornersH = corner_detector.get_corners(frame)
        if cornersH is not None:
            print("Corners found:", cornersH)
            break
    print("Using corners:", cornersH)

    ##### Main Loop
    FEN_last = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
    FEN_out = None
    FEN_new = None
    payload = None
    while True:
        ok, frame = cam.read()
        if not ok:
            break  
        # Process Frame
        frame = processFrame(frame, piece_model)
        cv2.imshow("Chess Stream", frame)

        # Get FEN new
        FEN_new = getFENnew(frame, cornersH, hand_model, piece_model, mapper, proc_size, FEN_last)
        if FEN_new is None:
            continue
                
        if FEN_out is None:
            FEN_out = FEN_last
        FEN_out, cMove = getNextFEN(FEN_last, FEN_new)

        if cMove == 1:
            print("State 1: Illegal move or multiple changes")
                
        # Check difference FENout vs FENlast
        FEN_outF = getFigure(FEN_out)
        print(f"FEN_outF: {FEN_outF}")
        FEN_lastF = getFigure(FEN_last)
        print(f"FEN_lastF: {FEN_lastF}")
        if FEN_outF != FEN_lastF:
            print(f"FEN_out: {FEN_out}")
            FEN_SF = changeState(FEN_out)
            showStatus(FEN_SF)
            FEN_last = FEN_SF

            #StockFish(FEN_out) -> Message
            if " b "  in FEN_SF:
                messages = buildMoveEventFromStockfish(FEN_SF, engineSF, timeLimit=0.5)
                payload = messages
                print("[DEBUG] messages output for SF:", messages)
            elif " w " in FEN_SF:
                payload = {"fen_str": FEN_out}
                print("[DEBUG] messages output for Player:", payload)
            
            # Send (FEN_out, Message) to Software
            #await tcp_client.send(json.dumps(payload))
            print("Sent to server:", payload)

        renderFen = render_fen(FEN_last)
        cv2.imshow("Chess board", renderFen)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    #await tcp_client.close()
    cam.release()
    cv2.destroyAllWindows()
    engineSF.quit()

if __name__ == "__main__":
    asyncio.run(main())