import os
import cv2

PIECE_FILES = {
    "P": "white-pawn.png", "N": "white-knight.png", "B": "white-bishop.png", "R": "white-rook.png", "Q": "white-queen.png", "K": "white-king.png",
    "p": "black-pawn.png", "n": "black-knight.png", "b": "black-bishop.png", "r": "black-rook.png", "q": "black-queen.png", "k": "black-king.png",
}

def load_board(assets_dir, size=800):
    bg = cv2.imread(os.path.join(assets_dir, "board.png"))
    return cv2.resize(bg, (size, size))

def load_piece(sym, assets_dir, size):
    path = os.path.join(assets_dir, "pieces", PIECE_FILES[sym])
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    return cv2.resize(img, (size, size))

def draw_piece(out, piece, x, y):
    if piece.shape[2] == 4:  # if alpha channel exists
        a = piece[:, :, 3:4].astype(float) / 255.0
        rgb = piece[:, :, :3].astype(float)
        roi = out[y:y+piece.shape[0], x:x+piece.shape[1]].astype(float)
        out[y:y+piece.shape[0], x:x+piece.shape[1]] = (a * rgb + (1 - a) * roi).astype("uint8")
    else:
        out[y:y+piece.shape[0], x:x+piece.shape[1]] = piece

def render_fen(fen, assets_dir="resources", size=640, win_name="Chess Board"):
    out = load_board(assets_dir, size)
    cell = size // 8
    rows = fen.split()[0].split("/")
    for r, row in enumerate(rows):
        c = 0
        for ch in row:
            if ch.isdigit():
                c += int(ch)
            else:
                piece = load_piece(ch, assets_dir, cell)
                draw_piece(out, piece, c * cell, r * cell)
                c += 1
    return out
