# 🤖♟️ Chess Robot

> An autonomous chess-playing robot that uses computer vision to detect the board state, calculates the optimal move with Stockfish AI, and physically executes it using a Fairino FR5 robotic arm.

---

## Demo

Watch the system in action:

[▶ Demo Video](https://www.facebook.com/share/v/1afysVp6YM/)

---

## Features

- **Real-time chessboard detection** — Detects board corners and piece positions from a live camera feed using YOLOv8
- **Automatic FEN generation** — Converts camera frames into FEN notation to represent the current board state
- **AI-powered move calculation** — Integrates Stockfish engine via `python-chess` for optimal move selection
- **Physical move execution** — Commands a Fairino FR5 robot arm to move, capture, or castle pieces on the physical board
- **Player turn detection** — Uses a hand detection model to identify when the human player has finished their move
- **Full move type support** — Handles regular moves, captures, and kingside/queenside castling
- **One-click startup** — All three system components launch via a single `run.bat` script on Windows

---

## System Architecture

```
  Camera (OpenCV)
       │  frame
       ▼
┌──────────────────────┐
│     ChessRobot       │  YOLOv8 → FEN → Stockfish
│   (AI Vision Module) │
└──────────┬───────────┘
           │  best move (JSON via TCP :8080)
           ▼
┌──────────────────────┐
│   Node.js Server     │  TCP relay hub
│   (robot-chess/      │
│    backend)          │
└──────────┬───────────┘
           │  move command (JSON via TCP :8080)
           ▼
┌──────────────────────┐
│     Middleware       │  Python asyncio
│  (Robot Controller)  │
└──────────┬───────────┘
           │  Fairino RPC SDK
           ▼
┌──────────────────────┐
│   Fairino FR5 Arm    │  Physical piece movement
└──────────────────────┘
```

**Pipeline:**
1. Camera captures a frame → YOLOv8 detects board corners and piece positions
2. Detected board → converted to **FEN notation**
3. FEN is fed into **Stockfish** → best move is computed
4. Move data is sent via **TCP** to the **Node.js relay server**
5. Server forwards the command to the **Python Middleware**
6. Middleware translates chess coordinates to robot Cartesian positions and drives the **Fairino FR5 arm** to execute the move

---

## Project Structure

```
chessRobot/
├── run.bat                  # One-click startup (Windows)
├── ChessRobot/              # AI vision module (YOLOv8 + Stockfish + TCP client)
│   ├── models/              # ⚠️ Not committed — download separately (see Installation)
│   ├── core/                # Chess logic, FEN processing, display manager
│   └── network/             # TCP client
├── middleware/              # Robot arm controller (Python asyncio + Fairino SDK)
│   └── fairino/             # Fairino FR5 Python SDK
└── software/robot-chess/
    └── backend/             # Node.js TCP relay server
```

> The `frontend/` directory is **excluded from this repository** — the system runs fully without it.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Vision & Detection | YOLOv8 (Ultralytics) |
| Chess AI | Stockfish + python-chess |
| Camera Processing | OpenCV |
| Relay Server | Node.js (TCP + WebSocket) |
| Robot Control | Fairino FR5 RPC SDK (Python) |
| Middleware Runtime | Python `asyncio` |
| AI Environment | Conda (`chess_board`) |

---

## Installation

### Prerequisites
- Windows (for `run.bat`)
- [Anaconda / Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- [Node.js](https://nodejs.org/) (v18+)
- Fairino FR5 robot arm on the same LAN

---

### 1. Clone the repository
```bash
git clone https://github.com/WHT413/E2E_ChessCobotSystem
cd E2E_ChessCobotSystem
```

### 2. Set up the AI environment (Conda)
```bash
conda create -n chess_board python=3.10
conda activate chess_board
pip install ultralytics opencv-python python-chess
```

### 3. Install the Node.js backend
```bash
cd software/robot-chess/backend
npm install
```

### 4. Install the robot middleware
```bash
cd middleware
pip install fairino
```

### 5. Download Stockfish
Download from [stockfishchess.org/download](https://stockfishchess.org/download/) and note the path to `stockfish.exe`.

### 6. Download model weights

> Model weights are **not included in this repository** (~50 MB each). Download from Google Drive and place in the correct folders.

📦 **[Download Model Weights — Google Drive](https://drive.google.com/drive/folders/1eLNtKdayAk5BljaIPR_CtjFqQArMZBz5?usp=drive_link)**

| File | Place in |
|---|---|
| `best25e_2712.pt` | `ChessRobot/models/` |
| `modelCorner.pt` | `ChessRobot/models/` |
| `modelHand.pt` | `ChessRobot/models/` |
| `modelPiece.pt` | `ChessRobot/models/` |

---

## Configuration

> ⚠️ Update these hardcoded values before running.

| File | Line | Parameter | Description |
|---|---|---|---|
| `run.bat` | 4 | `WORK_DIR` | Absolute path to the project root on your machine |
| `ChessRobot/chessrobotAI.py` | 140 | `engine_path` | Full path to your `stockfish.exe` |
| `ChessRobot/chessrobotAI.py` | 153 | `VideoCapture(2)` | Camera index — use `0` or `1` for most setups |
| `ChessRobot/chessrobotAI.py` | 138 | `FEN(mode)` | Game mode: `1` = Human White first, `2–4` = other orders |
| `middleware/2025_09_30_robotic_middleware.py` | 12 | `ROBOT_IP_ADDRESS` | IP address of the Fairino FR5 arm on your LAN |

---

## Running the System

### Option A — One-click startup (recommended)
```bat
run.bat
```
Opens three terminal windows simultaneously:

| Window | Process |
|---|---|
| `SERVER JS` | Node.js relay server |
| `MIDDLEWARE` | Python robot arm controller |
| `BACKEND AI` | Python AI vision (conda `chess_board`) |

### Option B — Run components individually
```bash
# Terminal 1 — Node.js server
cd software/robot-chess/backend && node server.js

# Terminal 2 — Robot middleware
cd middleware && python 2025_09_30_robotic_middleware.py

# Terminal 3 — AI vision
conda activate chess_board
cd ChessRobot && python chessrobotAI.py
```

---

## Hardware Requirements

| Component | Specification |
|---|---|
| Robot Arm | Fairino FR5 (connected via LAN) |
| Camera | USB or IP camera, mounted directly above the board |
| Computer | Windows PC with NVIDIA GPU recommended for YOLOv8 inference |
| Chess Set | Standard-size board compatible with the trained model |

---

## Important Notes

- The Fairino FR5 and the host machine must be on the **same local network** and reachable via ping
- The camera must be **fixed and centered** above the chessboard — even slight shifts will reduce detection accuracy
- Run `run.bat` as **Administrator** if you encounter permission errors on Windows
- Large files (`*.pt` weights, test videos) are excluded from the repository via `.gitignore`

---

## Future Worko

- [ ] Web-based live game monitor (frontend integration)
- [ ] Support for promotion, en passant, and draw detection
- [ ] Auto-calibration of robot arm coordinates from camera
- [ ] Cross-platform support (Linux/macOS)
- [ ] Packaging as a standalone installable application

---

## License

This project is for educational and research purposes.
