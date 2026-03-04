from ultralytics import YOLO
import numpy as np
import cv2

from typing import Dict, List, Tuple

class Hand():
    def __init__(self, path):
        self.model = YOLO(path)

    def calBoardArea(self, cornersH: Dict[str, tuple[float, float]]) -> Tuple[float, float, float, float]:
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
        
        return (max(0, x_min - x_offset), max(0, y_min - y_offset), x_max + x_offset, y_max + y_offset)

    def isHand(self, handBox: List[float], area: Tuple[float, float, float, float]) -> bool:
        if area is None:
            return False
        
        x1, y1, x2, y2 = handBox
        ax_min, ay_min, ax_max, ay_max = area
        return not (x2 < ax_min or x1 > ax_max or y2 < ay_min or y1 > ay_max)

    def detectHand(self, frame: np.ndarray, cornersH: Dict[str, tuple[float, float]]) -> bool:
        results = self.model(frame, conf=0.5, iou=0.5)
        handBoard = False
        boardArea = None

        if cornersH: 
            boardArea = self.calBoardArea(cornersH)

        for result in results:
            if result.boxes is None:
                continue 
            boxes = result.boxes.xyxy.cpu().numpy()
            scores = result.boxes.conf.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy()
            for box, score, cls in zip(boxes, scores, classes):
                if boardArea and self.isHand(box, boardArea):
                    handBoard = True
        return handBoard
   
