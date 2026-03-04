from ultralytics import YOLO
import numpy as np
import cv2
import re
import json
import chess
import chess.engine
import asyncio
from typing import Any, Dict, List, Tuple, Optional

from core.chess_mapping import ChessMapper
from core.chess_processing import ChessProcessor
from network.socket_client import TCPClient

class FEN():
    def __init__(self, id):
        self.NAME_TO_SYM: Dict[str, str] = {
            "white_pawn": "P", "white_knight": "N", "white_bishop": "B",
            "white_rook": "R", "white_queen": "Q", "white_king": "K",
            "black_pawn": "p", "black_knight": "n", "black_bishop": "b",
            "black_rook": "r", "black_queen": "q", "black_king": "k",
        }
        self.processor = ChessProcessor()
        self.mapper = ChessMapper()
        self.proc_size = self.processor.get_processing_size()

        self.checkMove, self.isValid, self.isCheck, self.isCheckmate, self.isStalemate, self.isGameover = False, False, False, False, False, False
        self.id = id
        if self.id == 1:  # Standard: Human plays White and goes first
            self.FEN_last = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
            self.side = "b"
        elif self.id == 2:  # Human plays White and goes second
            self.FEN_last = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b - - 0 1"
            self.side = "w"
        elif self.id == 3:  # Human plays Black and goes second
            self.FEN_last = "RNBQKBNR/PPPPPPPP/8/8/8/8/pppppppp/rnbqkbnr w - - 0 1"
            self.side = "b"
        elif self.id == 4:  # Human plays Black and goes first
            self.FEN_last = "RNBQKBNR/PPPPPPPP/8/8/8/8/pppppppp/rnbqkbnr b - - 0 1"
            self.side = "w"

        self.change = {}
        self.showStatus()

        self.tcp_client = None, None

        self.last_payload = None

# TCP Client Config and Publish
    def tcp_config(self, host: str, port: int):
        self.tcp_client = TCPClient(host, port)
        return self.tcp_client

    async def tcp_publish(self, tcp_client, payload: Dict[str, Any]):
        if tcp_client is not None:
            await tcp_client.send(json.dumps(payload))
            await asyncio.sleep(0)
        return

# Message processing
    def sendOutput(self, stockfish):
        fen_str = self.FEN_last
        isCheck = self.isCheck
        isCheckmate = self.isCheckmate
        isStalemate = self.isStalemate
        isGameover = self.isGameover

        board = chess.Board(self.FEN_last)
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

############################## 
    def normalBoard(self, raw_board: List[List[str]]) -> List[List[str]]:
        out: List[List[str]] = []
        for r in range(8):
            row_chars: List[str] = []
            for c in range(8):
                name = raw_board[r][c]
                row_chars.append(self.NAME_TO_SYM.get(name, ".") if name else ".")
            if len(row_chars) != 8:
                raise ValueError(f"Row {r} width != 8")
            out.append(row_chars)
        if len(out) != 8:
            raise ValueError("Board height != 8")
        return out

    def compressRow2FEN(self, row_chars: List[str]) -> str:
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

    def Board2FEN(self, board_chars: List[List[str]]) -> str:
        if len(board_chars) != 8 or any(len(r) != 8 for r in board_chars):
            raise ValueError("Invalid board size")
        rows = [self.compressRow2FEN(row) for row in board_chars]
        return "/".join(rows)

    def changeSide(self):
        if self.side == "w":
            self.side = "b"
        else:
            self.side = "w" 
        return

    def getPiece(self, board, sq):
        piece = board.piece_at(sq)
        if piece != None:
            return piece.symbol()
        return ""

    def getMoves(self):
        board = chess.Board(self.FEN_last)
        return board.legal_moves

    def isMove(self, sq1, piece11, piece12, sq2, piece21, piece22):
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
        
        if (piece12 == "" and piece21 == "" and 
            ((piece11 in ["K", "Q"] and piece22 in ["K", "Q"]) or
            (piece11 in ["k", "q"] and piece22 in ["k", "q"]))
            ):
            return 3  # Move Recog Error
        if (piece11 == "" and piece22 == "" and 
            ((piece12 in ["K", "Q"] and piece21 in ["K", "Q"]) or
            (piece12 in ["k", "q"] and piece21 in ["k", "q"]))
            ):
            return 5  # Move Recog Error
        
        if (piece11 == "" and piece21 == "" and 
            ((piece12 in ["K", "Q"] and piece22 in ["K", "Q"]) or
            (piece12 in ["k", "q"] and piece22 in ["k", "q"]))
            ):
            return 4  # Attack Recog Error
        if (piece22 == "" and 
            ((piece12 in ["K", "Q"] and piece21 in ["K", "Q"]) or
            (piece12 in ["k", "q"] and piece21 in ["k", "q"]))
            ):
            return 6  # Attack Recog Error
        if (piece21 == "" and
            ((piece11 in ["K", "Q"] and piece22 in ["K", "Q"]) or
            (piece11 in ["k", "q"] and piece22 in ["k", "q"]))
            ):
           return 8  # Attack Recog Error
        if (piece12 == "" and
            ((piece11 in ["K", "Q"] and piece22 in ["K", "Q"]) or
            (piece11 in ["k", "q"] and piece22 in ["k", "q"]))
            ):
           return 10  # Attack Recog Error
        return 0

    def getChange(self, fen: str):
        change = []
        board = chess.Board(self.FEN_last)
        boardN = chess.Board(fen)
        for c in ["a", "b", "c", "d", "e", "f", "g", "h"]:
            for i in range(1, 9):
                sq = str(c) + str(i)
                square = chess.parse_square(sq)
                piece = self.getPiece(board, square)
                pieceN = self.getPiece(boardN, square)
                if piece != pieceN:
                    change.append((sq, piece, pieceN))
        return len(change), change
    
    def checkChange(self, fen: str):
        lC, change = self.getChange(fen)
        self.change = {0: [], 1: [], 2: []}
        check = {}
        for i in range(lC):
            if i in check:
                continue
            (sqI, pieceI, pieceIN) = change[i]
            check[i] = 1
            state = 0
            for j in range(lC):
                if j not in check:
                    (sqJ, pieceJ, pieceJN) = change[j]
                    mv = self.isMove(sqI, pieceI, pieceIN, sqJ, pieceJ, pieceJN)
                    if mv == 1:
                        self.change[1].append((sqI, pieceI, pieceIN, sqJ, pieceJ, pieceJN))
                        check[j] = 1
                        state = 1
                        break
                    elif mv == 2:
                        self.change[2].append((sqI, pieceI, pieceIN, sqJ, pieceJ, pieceJN))
                        check[j] = 1
                        state = 1
                        break
            if state == 0:
                self.change[0].append((sqI, pieceI, pieceIN))

        return

    def checkLegalMove(self, sqI, sqJ, moves):
        move1 = chess.Move.from_uci(sqI + sqJ)
        move2 = chess.Move.from_uci(sqJ + sqI)
        if move1 in moves:
            print("Legal Move: " + str(move1))
            return True
        elif move2 in moves:
            print("Legal Move: " + str(move2))
            return True
        else:
            print("Illegal Move: " + str(move1))
            return False

    def checkQueenKing(self, fen: str):
        board = chess.Board(self.FEN_last)
        boardN = chess.Board(fen)
        nQ, nK, nq, nk = 0, 0, 0, 0
        for c in ["a", "b", "c", "d", "e", "f", "g", "h"]:
            for i in range(1, 9):
                sq = str(c) + str(i)
                square = chess.parse_square(sq)
                pieceN = self.getPiece(boardN, square)
                if pieceN == "Q":
                    nQ += 1
                if pieceN == "K":
                    nK += 1
                if pieceN == "q":
                    nq += 1
                if pieceN == "k":
                    nk += 1
        if (((nK > 1 or nk > 1) and (nQ == 0 or nq == 0)) or 
            ((nK == 0 or nk == 0) and (nQ > 1 or nq > 1))
            ):
            print("Error: More than one King and missing Queen")        
            for c in ["a", "b", "c", "d", "e", "f", "g", "h"]:
                for i in range(1, 9):
                    sq = str(c) + str(i)
                    square = chess.parse_square(sq)
                    piece = self.getPiece(board, square)
                    pieceN = self.getPiece(boardN, square)
                    if piece != pieceN:
                        if piece in ["K", "k", "Q", "q"] and pieceN in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sq), chess.Piece.from_symbol(piece))
                            print("Fix: " + sq + " " + pieceN + " to " + piece)

        return boardN.fen()

    def checkRecog(self, fen: str):
        fenC = self.checkQueenKing(fen)
        board = chess.Board(self.FEN_last)
        boardN = chess.Board(fenC)
        for c in ["a", "b", "c", "d", "e", "f", "g", "h"]:
            for i in range(1, 9):
                sq = str(c) + str(i)
                square = chess.parse_square(sq)
                piece = self.getPiece(board, square)
                pieceN = self.getPiece(boardN, square)
                if piece != pieceN:
                    if ((piece in ["K", "Q", "B", "P", "N", "R"] and pieceN in ["K", "Q", "B", "P", "N", "R"]) or
                       (piece in ["k", "q", "b", "p", "n", "r"] and pieceN in ["k", "q", "b", "p", "n", "r"])):
                        boardN.set_piece_at(chess.parse_square(sq), chess.Piece.from_symbol(piece))
                        print("Fix: " + sq + " " + pieceN + " to " + piece)
        return boardN.fen()

    def getFigure(self, fen: str):
        fenF = re.match(r'(.*?) ', fen).group(1)
        return fenF

    def getFEN(self, frame, cornersH, hand, piece):
        FEN_new = None
        try:
            if cornersH is None:
                raise RuntimeError("Corners not found")
            handBoard = hand.detectHand(frame, cornersH)
            if handBoard:
                return None

            pieces = piece.detectPieces(frame)
            H, _grid = self.mapper.create_homography_mapping(cornersH, frame, self.proc_size)
            mapped = self.mapper.map_pieces_to_board_space(pieces, H)
            mapping_result = self.mapper.assign_pieces_to_cells(mapped)

            cand_board = self.normalBoard(mapping_result.chess_board)
            FEN_board = self.Board2FEN(cand_board)

            FEN_new = f"{FEN_board} {self.side} - - 0 1"
            print(f"[DEBUG] Detected FEN: {FEN_new}")
        except Exception as e:
            print("FEN detection error:", e)
        return FEN_new

    def checkFEN(self, fen: str):
        checkMove = False
        moves = self.getMoves()
        fenC = self.checkRecog(fen)
        print("[DEBUG] After checking check recog error, fen2:", fenC)

        lC, change = self.getChange(fenC)
        print("[DEBUG] Detected changes:", change)
        boardN = chess.Board(fenC)
        check = {}
        for i in range(lC):
            if i in check:
                continue
            (sqI, pieceI, pieceIN) = change[i]
            check[i] = 1
            state = 0
            # Check Move and Attack
            for j in range(lC):
                if j not in check:
                    (sqJ, pieceJ, pieceJN) = change[j]
                    mv = self.isMove(sqI, pieceI, pieceIN, sqJ, pieceJ, pieceJN)
                    if mv == 1:
                        print("Move: " + str(change[i]) + " - " + str(change[j]))
                        checkMove = self.checkLegalMove(sqI, sqJ, moves)
                        check[j] = 1
                        state = 1
                        break
                    elif mv == 3:
                        print("Move Recog Err 3: " + str(change[i]) + " - " + str(change[j]))
                        checkMove = self.checkLegalMove(sqI, sqJ, moves)
                        if pieceI in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqJ), chess.Piece.from_symbol(pieceI))
                        elif pieceJ in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqI), chess.Piece.from_symbol(pieceJ))
                        check[j] = 1
                        state = 1
                        break
                    elif mv == 5:
                        print("Move Recog Err 5: " + str(change[i]) + " - " + str(change[j]))
                        checkMove = self.checkLegalMove(sqI, sqJ, moves)
                        if pieceI in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqJ), chess.Piece.from_symbol(pieceI))
                        elif pieceJ in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqI), chess.Piece.from_symbol(pieceJ))
                        check[j] = 1
                        state = 1
                        break
                    elif mv == 2:
                        print("Attack: " + str(change[i]) + " - " + str(change[j]))
                        checkMove = self.checkLegalMove(sqI, sqJ, moves)
                        check[j] = 1
                        state = 1
                        break
                    elif mv == 4:
                        print("Attack Recog Err 4: " + str(change[i]) + " - " + str(change[j]))
                        checkMove = self.checkLegalMove(sqI, sqJ, moves)
                        if pieceI in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqJ), chess.Piece.from_symbol(pieceI))
                        elif pieceJ in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqI), chess.Piece.from_symbol(pieceJ))
                        check[j] = 1
                        state = 1
                        break
                    elif mv == 6:
                        print("Attack Recog Err 6: " + str(change[i]) + " - " + str(change[j]))
                        checkMove = self.checkLegalMove(sqI, sqJ, moves)
                        if pieceI in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqJ), chess.Piece.from_symbol(pieceI))
                        elif pieceJ in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqI), chess.Piece.from_symbol(pieceJ))
                        check[j] = 1
                        state = 1
                        break
                    elif mv == 8:
                        print("Attack Recog Err 8: " + str(change[i]) + " - " + str(change[j]))
                        checkMove = self.checkLegalMove(sqI, sqJ, moves)
                        if pieceI in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqJ), chess.Piece.from_symbol(pieceI))
                        elif pieceJ in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqI), chess.Piece.from_symbol(pieceJ))
                        check[j] = 1
                        state = 1
                        break
                    elif mv == 10:
                        print("Attack Recog Err 10: " + str(change[i]) + " - " + str(change[j]))
                        checkMove = self.checkLegalMove(sqI, sqJ, moves)
                        if pieceI in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqJ), chess.Piece.from_symbol(pieceI))
                        elif pieceJ in ["K", "k", "Q", "q"]:
                            boardN.set_piece_at(chess.parse_square(sqI), chess.Piece.from_symbol(pieceJ))
                        check[j] = 1
                        state = 1
                        break
            # Check Missing
            if state == 0:
                if pieceIN == "":
                    print("Missing: " + str(change[i]))
                    boardN.set_piece_at(chess.parse_square(sqI), chess.Piece.from_symbol(pieceI))
                else:
                    print("Recog Err: " + str(change[i]))
                    boardN.set_piece_at(chess.parse_square(sqI), chess.Piece.from_symbol(pieceIN))

        fenN = boardN.fen()
        self.checkChange(fenN)
        print(self.change)
        return fenN, checkMove

    async def updateFEN(self, fen: str, stockfish, tcp_client):
        FEN_check, self.checkMove = self.checkFEN(fen)
        payload = {}
        count = 0

        FEN_lastF = self.getFigure(self.FEN_last)
        FEN_checkF = self.getFigure(FEN_check)
        check = True
        if len(self.change[0]) > 1 or len(self.change[1]) > 1 or len(self.change[2]) > 1:
            check = False
            if len(self.change[0]) == 0 and len(self.change[2]) == 0 and len(self.change[1]) == 2:
                (sq1, piece1, piece1N, sq2, piece2, piece2N) = self.change[1][0]
                (sq3, piece3, piece3N, sq4, piece4, piece4N) = self.change[1][1]
                if ((piece1 in ["K", "k", "R", "r"] or piece2 in ["K", "k", "R", "r"]) and 
                    (piece3 in ["K", "k", "R", "r"] or piece4 in ["K", "k", "R", "r"])):
                    print("Castling detected, FEN updated.")
                    check = True            
            if not check:
                print("Multiple changes detected, FEN not updated.")
        elif not self.checkMove:
            check = False
            print("No valid move detected, FEN not updated.")

        if FEN_checkF != FEN_lastF and check:
            self.FEN_last = FEN_check
            self.changeSide()
            self.showStatus()

            if self.side == "w":
                payload = self.sendOutput(stockfish)
            elif self.side == "b":
                payload = {"fen_str": self.FEN_last}
                # payload = self.sendOutput(stockfish)
            if payload != self.last_payload:
                await self.tcp_publish(tcp_client, payload)
            else:
                print("Same payload, not sending.")

            self.last_payload = payload
            
        return

    def showStatus(self):
        board = chess.Board(self.FEN_last)
        self.isValid = board.is_valid()
        self.isCheck = board.is_check()
        self.isCheckmate = board.is_checkmate()
        self.isStalemate = board.is_stalemate()
        self.isGameover = board.is_game_over()
        print('')
        print("Board:")
        print(board)
        print('')
        print("Is valid:", board.is_valid())
        print("Is check:", board.is_check())
        print("Is checkmate:", board.is_checkmate())
        print("Is stalemate:", board.is_stalemate())
        print("Is game over:", board.is_game_over())
        print("Legal moves:", list(board.legal_moves))
        print('')
        return


