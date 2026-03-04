# webrtc_stream.py
# Purpose: Provide a reusable WebRTC streamer that streams frames provided by another module.
# Notes:
# - Comments are in English as requested.
# - This module does NOT open any camera. It only streams frames you push into it.
# - Thread-safe: you can call .send(frame) from another thread (e.g., your OpenCV loop).

import asyncio
import threading
from typing import Optional

import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.signaling import TcpSocketSignaling

try:
    from av import VideoFrame
except Exception as e:
    raise RuntimeError("PyAV (av) is required. Install with: pip install av") from e


class ExternalVideoTrack(VideoStreamTrack):
    """
    A VideoStreamTrack that pulls frames from an asyncio.Queue.
    Frames must be numpy ndarray (H, W, 3) in BGR or RGB.
    """

    def __init__(self, frame_queue: "asyncio.Queue[np.ndarray]"):
        super().__init__()
        self._queue = frame_queue

    async def recv(self) -> VideoFrame:
        # Block until a frame is available
        frame = await self._queue.get()
        pts, time_base = await self.next_timestamp()

        # Accept both BGR and RGB; convert to RGB if needed.
        # Heuristic: assume BGR by default.
        # If your upstream is already RGB, set 'already_rgb=True' in the sender and skip conversion.
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise RuntimeError("Frame must be uint8 HxWx3 ndarray")

        # Convert BGR->RGB (safe default)
        # If upstream already sent RGB, skip this conversion in the sender.
        rgb = frame[:, :, ::-1].copy()  # cheap BGR->RGB

        vf = VideoFrame.from_ndarray(rgb, format="rgb24")
        vf.pts = pts
        vf.time_base = time_base
        return vf


class WebRTCStreamer:
    """
    Public API:
      - start(signaling_host, signaling_port): start WebRTC offerer in a background thread.
      - send(frame, already_rgb=False, drop_old=True): enqueue a frame for streaming.
      - stop(): stop streaming and cleanup.

    Design:
      - A background asyncio event loop runs the WebRTC stack.
      - Frames are pushed into an asyncio.Queue using loop.call_soon_threadsafe for thread safety.
    """

    def __init__(self, queue_size: int = 2):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

        self._pc: Optional[RTCPeerConnection] = None
        self._signaling: Optional[TcpSocketSignaling] = None

        self._queue_size = max(1, queue_size)
        self._frame_queue: Optional["asyncio.Queue[np.ndarray]"] = None

    # ----------------- Public API -----------------
    def start(self, signaling_host: str, signaling_port: int) -> None:
        """
        Start the WebRTC streaming in a background thread.
        """
        if self._thread and self._thread.is_alive():
            return  # already running

        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._run_loop_thread,
            args=(signaling_host, signaling_port),
            daemon=True,
        )
        self._thread.start()

    def send(self, frame: np.ndarray, already_rgb: bool = False, drop_old: bool = True) -> None:
        """
        Enqueue a frame for streaming.
        - frame: ndarray(H, W, 3) uint8 (BGR or RGB).
        - already_rgb: if True, treat input as RGB and do NOT convert in track (optional optimization).
                       If you set this True, also modify ExternalVideoTrack to skip conversion.
        - drop_old: if True and the queue is full, drop the oldest frame to keep latency low.
        """
        if self._loop is None or self._frame_queue is None:
            return  # not started yet

        # Copy frame to avoid upstream buffer reuse issues
        f = frame.copy()

        def _enqueue():
            try:
                # Keep queue small to minimize latency
                if drop_old and self._frame_queue.full():
                    # Drop one oldest frame
                    self._frame_queue.get_nowait()
                self._frame_queue.put_nowait(f)
            except asyncio.QueueFull:
                # If still full, drop this frame
                pass

        # Thread-safe enqueue
        try:
            self._loop.call_soon_threadsafe(_enqueue)
        except RuntimeError:
            # Loop may be closing; ignore
            pass

    def stop(self) -> None:
        """
        Stop streaming and cleanup resources.
        """
        self._stop_evt.set()
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(asyncio.create_task, self._async_close())
            except RuntimeError:
                pass

        if self._thread:
            self._thread.join(timeout=3.0)
        self._thread = None
        self._loop = None

    # ----------------- Internal -----------------
    def _run_loop_thread(self, host: str, port: int) -> None:
        asyncio.run(self._async_main(host, port))

    async def _async_main(self, host: str, port: int) -> None:
        self._loop = asyncio.get_running_loop()
        self._frame_queue = asyncio.Queue(maxsize=self._queue_size)

        self._pc = RTCPeerConnection()
        self._signaling = TcpSocketSignaling(host, port)

        # Attach outbound track
        video_track = ExternalVideoTrack(self._frame_queue)
        self._pc.addTrack(video_track)

        # Connect signaling and exchange SDP
        await self._signaling.connect()
        offer = await self._pc.createOffer()
        await self._pc.setLocalDescription(offer)
        await self._signaling.send(self._pc.localDescription)

        answer = await self._signaling.receive()
        if not isinstance(answer, RTCSessionDescription):
            raise RuntimeError("Invalid answer received from signaling")
        await self._pc.setRemoteDescription(answer)

        # Keep the loop alive until stop is requested or signaling ends
        stop_task = asyncio.create_task(self._wait_for_stop())
        sig_task = asyncio.create_task(self._signaling.receive())  # completes when peer says BYE

        done, pending = await asyncio.wait(
            {stop_task, sig_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()

        await self._async_close()

    async def _wait_for_stop(self) -> None:
        while not self._stop_evt.is_set():
            await asyncio.sleep(0.05)

    async def _async_close(self) -> None:
        # Close WebRTC and signaling gracefully
        try:
            if self._pc and self._pc.connectionState != "closed":
                await self._pc.close()
        except Exception:
            pass
        try:
            if self._signaling:
                await self._signaling.close()
        except Exception:
            pass
