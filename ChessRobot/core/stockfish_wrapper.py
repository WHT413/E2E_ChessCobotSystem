import subprocess
import threading
import queue
import time
from typing import Optional, List, Dict

class StockfishUCI:
    """
    Minimal UCI controller for Stockfish.
    - Start/stop the engine
    - Send 'position' (with FEN and optional moves)
    - Run 'go' (by movetime or depth)
    - Parse 'bestmove' and basic 'info score'
    """

    def __init__(self, engine_path: str = "stockfish", start_timeout_s: float = 5.0):
        self.engine_path = engine_path
        self.start_timeout_s = start_timeout_s
        self.proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._out_q: "queue.Queue[str]" = queue.Queue()
        self._running = False

    def start(self) -> None:
        """Start the engine process and initialize UCI."""
        if self.proc is not None:
            return
        self.proc = subprocess.Popen(
            [self.engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1
        )
        self._running = True
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

        self.send("uci")
        self._wait_for("uciok", timeout=self.start_timeout_s)
        self.send("isready")
        self._wait_for("readyok", timeout=self.start_timeout_s)

    def close(self) -> None:
        """Gracefully stop the engine."""
        if self.proc is None:
            return
        try:
            self.send("quit")
        except Exception:
            pass
        try:
            self.proc.wait(timeout=1.0)
        except Exception:
            self.proc.kill()
        self._running = False
        self.proc = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def send(self, cmd: str) -> None:
        """Send a single UCI command line to the engine."""
        if self.proc is None or self.proc.stdin is None:
            raise RuntimeError("Engine is not running")
        self.proc.stdin.write((cmd + "\n").encode())
        self.proc.stdin.flush()

    def set_options(self, options: Dict[str, str]) -> None:
        """Set UCI options like Threads, Hash, Contempt, etc."""
        for k, v in options.items():
            self.send(f"setoption name {k} value {v}")
        self.send("isready")
        self._wait_for("readyok", timeout=self.start_timeout_s)

    def position_fen(self, fen: str, moves: Optional[List[str]] = None) -> None:
        """
        Set the engine position from a FEN and optional subsequent moves.
        Example:
          position_fen("rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2", moves=["e7e5"])
        """
        if moves:
            moves_str = " ".join(moves)
            self.send(f"position fen {fen} moves {moves_str}")
        else:
            self.send(f"position fen {fen}")

    def position_startpos(self, moves: Optional[List[str]] = None) -> None:
        """
        Set the engine position from the standard initial position with optional moves.
        Example:
          position_startpos(["e2e4", "e7e5", "g1f3"])
        """
        if moves:
            moves_str = " ".join(moves)
            self.send(f"position startpos moves {moves_str}")
        else:
            self.send("position startpos")

    def go(self,
           movetime_ms: Optional[int] = None,
           depth: Optional[int] = None,
           wtime_ms: Optional[int] = None,
           btime_ms: Optional[int] = None,
           winc_ms: Optional[int] = None,
           binc_ms: Optional[int] = None,
           stop_token: str = "bestmove",
           timeout_s: float = 10.0) -> Dict[str, Optional[str]]:
        """
        Run a search with either movetime or depth (or time controls).
        Returns a dict with bestmove, ponder, and last seen score (cp or mate).
        """
        if movetime_ms is None and depth is None and wtime_ms is None and btime_ms is None:
            movetime_ms = 1000

        parts = ["go"]
        if depth is not None:
            parts += ["depth", str(depth)]
        if movetime_ms is not None:
            parts += ["movetime", str(movetime_ms)]
        if wtime_ms is not None:
            parts += ["wtime", str(wtime_ms)]
        if btime_ms is not None:
            parts += ["btime", str(btime_ms)]
        if winc_ms is not None:
            parts += ["winc", str(winc_ms)]
        if binc_ms is not None:
            parts += ["binc", str(binc_ms)]

        self.send(" ".join(parts))

        bestmove = None
        ponder = None
        score_cp = None
        score_mate = None
        deadline = time.time() + timeout_s

        while time.time() < deadline:
            line = self._get_line(timeout=0.05)
            if not line:
                continue

            # Parse incremental "info" for score
            if line.startswith("info"):
                # Example: "info depth 14 score cp 23 ..." or "info depth 20 score mate 3 ..."
                toks = line.split()
                for i in range(len(toks) - 1):
                    if toks[i] == "score" and (i + 2) < len(toks):
                        kind = toks[i + 1]
                        val = toks[i + 2]
                        if kind == "cp":
                            try:
                                score_cp = int(val)
                            except Exception:
                                pass
                        elif kind == "mate":
                            try:
                                score_mate = int(val)
                            except Exception:
                                pass

            # Stop condition
            if line.startswith("bestmove"):
                # Example: "bestmove e2e4 ponder e7e5"
                parts2 = line.split()
                if len(parts2) >= 2:
                    bestmove = parts2[1]
                if len(parts2) >= 4 and parts2[2] == "ponder":
                    ponder = parts2[3]
                break

        return {
            "bestmove": bestmove,
            "ponder": ponder,
            "score_cp": score_cp,
            "score_mate": score_mate
        }

    # Internal reader

    def _reader_loop(self):
        """Background thread that reads engine stdout and enqueues lines."""
        assert self.proc is not None and self.proc.stdout is not None
        while self._running:
            line = self.proc.stdout.readline()
            if not line:
                break
            try:
                s = line.decode(errors="ignore").strip()
            except Exception:
                s = str(line).strip()
            self._out_q.put(s)

    def _get_line(self, timeout: float = 0.0) -> Optional[str]:
        """Pop one line from the stdout queue."""
        try:
            return self._out_q.get(timeout=timeout)
        except queue.Empty:
            return None

    def _wait_for(self, token: str, timeout: float = 5.0) -> None:
        """Wait until a line equals the token."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self._get_line(timeout=0.05)
            if line and line == token:
                return
        raise TimeoutError(f"Timeout waiting for: {token}")
