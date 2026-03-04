from __future__ import annotations

import os
import cv2
import numpy as np
import re
import asyncio

import chess
import chess.engine
from pathlib import Path
import json
import threading
from typing import Any, Dict, List, Tuple, Optional

from ultralytics import YOLO

from corners import Corner
from piece import Piece
from hand import Hand
from fen import FEN
from stockfish import Stockfish
from network.socket_client import TCPClient
from renderFen2Img import render_fen

def getCorners(cam, corner):
    cornersH = []
    while True:
        ok, frame = cam.read()
        if not ok:
            break
        cornersH = corner.getCorners(frame, 2)
        if cornersH is not None:
            print("Corners found:", cornersH)
            break
    return cornersH

def sendOutput(fen, stockfish):
    fen_str = fen.FEN_last
    isCheck = fen.isCheck
    isCheckmate = fen.isCheckmate
    isStalemate = fen.isStalemate
    isGameover = fen.isGameover

    board = chess.Board(fen.FEN_last)
    limit = chess.engine.Limit(time=0.1)
    result = stockfish.analyse(board, limit)

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

    # Make the move to get the updated position
    board.push(bestmove)
    results_in_check = board.is_check()
    
    def piece_label(p):
        if p is None:
            return None
        color = "white" if p.color == chess.WHITE else "black"
        names = {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen", 6: "king"}
        return f"{color}_{names[p.piece_type]}"
    
    return {
        "fen_str": fen_str,
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

async def playChess(cam, cornersH, hand, piece, fen, stockfish, tcp_client):
    while True:
        ok, frame = cam.read()
        if not ok:
            break  
        # Process Frame
        frame = piece.processFrame(frame)
        cv2.imshow("Chess Stream", frame)

        # Get FEN new
        FEN_new = fen.getFEN(frame, cornersH, hand, piece)
        if FEN_new is None:
            continue
        await fen.updateFEN(FEN_new, stockfish, tcp_client)
        renderFen = render_fen(fen.FEN_last)

        if fen.isCheck:
            print("Current state is check")
        if fen.isCheckmate:
            print("Current state is checkmate")
            break
        if fen.isStalemate:
            print("Current state is stalemate")
            break
        if fen.isGameover:
            print("Current state is game over")
            break

        if fen.side == "w":
            print("Robot moves")
        else:
            print("Human moves")

        cv2.imshow("Chess board", renderFen)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            tcp_client.close()
            break
    return

async def main():
    piece = Piece("models/best25e_2712.pt")
    hand = Hand("models/modelHand.pt")
    # standard size 640, 480
    # rate = 640 / width
    corner = Corner("models/modelCorner.pt", 1)

    # 1 - Human plays White and goes first
    # 2 - Human plays White and goes second
    # 3 - Human plays Black and goes second
    # 4 - Human plays Black and goes first
    fen = FEN(1)

    engine_path = r"D:\Workspaces\chess - Copy\stockfish\stockfish-windows-x86-64-avx2.exe"
    stockfish = chess.engine.SimpleEngine.popen_uci(engine_path)

    tcp_client = TCPClient(host="127.0.0.1", port=8080)
    await tcp_client.connect()

    ai_identity = {
       "type": "ai_identify",
       "ai_id": "chess_vision_ai"
    }
    await tcp_client.send(json.dumps(ai_identity))    
    print("AI identified with server:", ai_identity)

    cam = cv2.VideoCapture(2)
    # cam = cv2.VideoCapture("test/video2.mp4")
    
    ##### Get Corners
    cornersH = getCorners(cam, corner)

    ##### Play Chess
    await playChess(cam, cornersH, hand, piece, fen, stockfish, tcp_client)

    cam.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    asyncio.run(main())

