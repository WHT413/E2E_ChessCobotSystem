import cv2
import numpy as np
from ultralytics import YOLO

class ChessboardCropper:
    def __init__(self, model_path, output_size=(640, 640)):
        self.model = YOLO(model_path)
        self.output_size = output_size

    def load_image(self, image_path):
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Error loading image from {image_path}")
        return img

    def get_corners(self, img):
        results = self.model(img, verbose=False)
        if not results or not hasattr(results[0], 'boxes'):
            return None
        boxes = results[0].boxes.xyxy.cpu().numpy()
        scores = results[0].boxes.conf.cpu().numpy()
        classes = results[0].boxes.cls.cpu().numpy()
        class2corner = {0: 'top_left', 1: 'top_right', 2: 'bottom_right', 3: 'bottom_left'}
        corners = {}
        for box, score, cls in zip(boxes, scores, classes):
            if score > 0.5 and int(cls) in class2corner:
                x1, y1, x2, y2 = box
                x, y = int((x1 + x2) / 2), int((y1 + y2) / 2)
                corners[class2corner[int(cls)]] = (x, y)
        if len(corners) != 4:
            return None
        return corners

    def crop_board(self, img, corners):
        pts_src = np.float32([
            corners['top_left'],
            corners['top_right'],
            corners['bottom_right'],
            corners['bottom_left']
        ])
        pts_dst = np.float32([
            [0, 0],
            [self.output_size[0] - 1, 0],
            [self.output_size[0] - 1, self.output_size[1] - 1],
            [0, self.output_size[1] - 1]
        ])
        M = cv2.getPerspectiveTransform(pts_src, pts_dst)
        result = cv2.warpPerspective(img, M, self.output_size)
        return result
 