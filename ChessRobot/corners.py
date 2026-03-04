from ultralytics import YOLO
import numpy as np
import cv2

from typing import Dict, List, Tuple

class Corner():
    def __init__(self, path, ratio):
        self.model = YOLO(path)
        self.ratio = ratio

    def processFrame(self, frame):
        frame = cv2.resize(frame, (640, 480))
        frame = cv2.rotate(frame, cv2.ROTATE_180)
        
        height, width = frame.shape[:2]
        print(width, height)
        new_width = int(width * self.ratio)
        new_height = int(height * self.ratio)

        dim = (new_width, new_height)
        frame = cv2.resize(frame, dim)
        return frame

    def centerCorner(self, x1: int, y1: int, x2: int, y2: int) -> Tuple[int, int]:
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def normalCorners1(self, xC, yC, corners) -> Dict[str, Tuple[int, int]]:
        # BL ####### TL #
        #               #
        #               #
        #               #
        #               #
        #               #
        #               #
        # BR ####### TR #
        if len(corners) < 4:
            return None
        cornersN = {}
        for pos in corners:
            (x, y) = pos
            label = ""
            if x < xC and y < yC:
                label = "bottom_left"
            elif x < xC and y > yC:
                label = "bottom_right"
            elif x > xC and y < yC:
                label = "top_left"
            elif x > xC and y > yC:
                label = "top_right"
            if label != "":
                cornersN[label] = pos
        cornersR = ["top_left", "top_right", "bottom_left", "bottom_right"]
        # print(1)
        if all(corner in cornersN for corner in cornersR):
            return cornersN
        else:
            return None

    def normalCorners2(self, xC, yC, corners) -> Dict[str, Tuple[int, int]]:
        # TL ####### BL #
        #               #
        #               #
        #               #
        #               #
        #               #
        #               #
        # TR ####### BR #
        if len(corners) < 4:
            return None
        cornersN = {}
        for pos in corners:
            (x, y) = pos
            label = ""
            if x < xC and y < yC:
                label = "top_right"
            elif x < xC and y > yC:
                label = "top_left"
            elif x > xC and y < yC:
                label = "bottom_right"
            elif x > xC and y > yC:
                label = "bottom_left"
            if label != "":
                cornersN[label] = pos
        cornersR = ["top_left", "top_right", "bottom_left", "bottom_right"]
        # print(2)
        if all(corner in cornersN for corner in cornersR):
            return cornersN
        else:
            return None
        
    def hardcodeCorners(self, corners) -> Dict[str, Tuple[int, int]]:
        # if len(corners) != 4:
        #     return None
        labels = ["top_left", "top_right", "bottom_left", "bottom_right"]
        return {label: pos for label, pos, in zip(labels, corners)}
        


    def getCorners(self, frame: np.ndarray, id) -> Dict[str, Tuple[int, int]]:
        detected_corners = []
        
        # return self.hardcodeCorners(detected_corners)
        xC = int(300 / self.ratio)
        yC = int(250 / self.ratio)
        frame = self.processFrame(frame)
        results = self.model(frame, conf=0.5, iou=0.5)
        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            scores = result.boxes.conf.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy()

            for box, score, cls in zip(boxes, scores, classes):
                x1, y1, x2, y2 = map(int, box)
                cornerP = self.centerCorner(int(x1 / self.ratio), int(y1 / self.ratio), int(x2 / self.ratio), int(y2 / self.ratio))
                detected_corners.append(cornerP)
                
        print(detected_corners)
        # print(f"Detect lens of conrners: {len(detected_corners)}")
        # if len(detected_corners) == 4:
        #     return self.hardcodeCorners(detected_corners)

        # detected_corners = [(558, 382), (96, 378), (487, 85), (165, 83)]

        # detected_boxes = [
        #     [119, 59, 179, 119],    
        #     [444, 56, 503, 115],
        #     [54, 363, 114, 421],
        #     [518, 354, 580, 413],
        # ]
        # detected_corners = [
        #     self.centerCorner(x1, y1, x2, y2)
        #     for x1, y1, x2, y2 in detected_boxes
        # ]

        # Show 4 corners was detected by detected_corners
        # labels = ["top_left", "top_right", "bottom_left", "bottom_right"]
        # for (x, y), label in zip(detected_corners, labels):
        #     cv2.circle(frame, (x, y), 8, (0, 0, 255), -1)
        #     cv2.putText(frame, label, (x+10, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
        # cv2.imshow("Detected Corners", frame)
        # cv2.waitKey(1)

        if id == 1:
            # print(1)
            return self.normalCorners1(xC, yC, detected_corners) if len(detected_corners) >= 4 else None
        else:   
            # print(2)
            return self.normalCorners2(xC, yC, detected_corners) if len(detected_corners) >= 4 else None

