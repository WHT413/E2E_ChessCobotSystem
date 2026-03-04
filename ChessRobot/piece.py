from ultralytics import YOLO
import numpy as np
import cv2

from typing import Any, Dict, List, Tuple, Optional

class Piece():
    def __init__(self, path):
        self.model = YOLO(path)
        self.label = {}
        self.label["white_pawn"] = "P"
        self.label["black_pawn"] = "p"
        self.label["white_knight"] = "N"
        self.label["black_knight"] = "n"
        self.label["white_bishop"] = "B"
        self.label["black_bishop"] = "b"
        self.label["white_rook"] = "R"
        self.label["black_rook"] = "r"
        self.label["white_queen"] = "Q"
        self.label["black_queen"] = "q"
        self.label["white_king"] = "K"
        self.label["black_king"] = "k"

    def changeName(self, name):
        if name in self.label.keys():
            name = self.label[name]
        return name

    def detectPieces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        results = self.model(frame, conf=0.50, iou=0.5, verbose=False)
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

    def visualizePieces(self, frame: np.ndarray, pieces: List[Dict[str, Any]]) -> np.ndarray:
        vis = frame.copy()
        for det in pieces:
            x1, y1, x2, y2 = map(int, det["box"])
            cls_name = self.changeName(det["class_name"])
            conf = det["confidence"]
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 1)
            label = f"{cls_name} {conf:.2f}"
            cv2.putText(vis, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        return vis

    def processFrame(self, frame):
        frame = cv2.resize(frame, (640, 480))
        frame = cv2.rotate(frame, cv2.ROTATE_180)

        frame_vis = frame.copy()
        frame_vis = self.visualizePieces(frame_vis, self.detectPieces(frame))
        cv2.imshow("Detections", frame_vis)
        return frame

