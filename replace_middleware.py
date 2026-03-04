import os
import re

file_path = 'd:\\Workspaces\\25_10_16 chessRobot\\middleware\\2025_09_30_robotic_middleware.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    'MQTT publisher client toàn cục': 'Global MQTT publisher client',
    'Khởi tạo MQTT publisher': 'Initialize MQTT publisher',
    'Tạo message với format status yêu cầu': 'Create message with requested status format',
    'Publish feedback với format status': 'Publish feedback with status format',
    'Publish result với format status': 'Publish result with status format',
    'Publish status với format status': 'Publish status with status format',
    'Các vị trí đã định nghĩa': 'Defined positions',
    'so lan an': 'capture count',
    'Các tham số robot': 'Robot parameters',
    'Di chuyển tới vị trí quân địch (trên cao)': 'Move to enemy piece position (above)',
    'Hạ xuống để gắp quân địch': 'Lower to grip enemy piece',
    'Gắp quân địch': 'Grip enemy piece',
    'Nâng quân địch lên và di chuyển về vị trí cũ': 'Lift enemy piece and move back to previous position',
    'Di chuyển và thả quân địch vào nghĩa địa (trên cao)': 'Move and release enemy piece to graveyard (above)',
    'Hạ xuống thả quân địch': 'Lower to release enemy piece',
    'Thả quân địch': 'Release enemy piece',
    'Nâng lên khỏi nghĩa địa': 'Lift out of graveyard',
    'Di chuyển đến vị trí quân mình (trên cao)': 'Move to own piece position (above)',
    'Hạ xuống gắp quân mình': 'Lower to grip own piece',
    'Gắp quân mình': 'Grip own piece',
    'Nâng quân mình lên': 'Lift own piece',
    'Di chuyển đến vị trí đích (trên cao)': 'Move to target position (above)',
    'Hạ xuống thả quân mình': 'Lower to release own piece',
    'Thả quân mình': 'Release own piece',
    'Quay về home': 'Return to home',
    'di chuyen den quan can gap (tren cao)': 'move to piece to grip (above)',
    'gap quan minh': 'grip own piece',
    'nang quan minh len': 'lift own piece',
    'di chuyen den vi tri dich (tren cao)': 'move to target position (above)',
    'ha xuong tha quan minh': 'lower to release own piece',
    'nang len khoi ban co': 'lift above chessboard',
    'quay ve home': 'return to home',
    'toi cho quan King': 'go to King piece position',
    'gap quan King': 'grip King piece',
    'Nâng quân king lên': 'Lift King piece',
    'di chuyen den c1 hoac c8 tren cao': 'move to c1 or c8 (above)',
    'Hạ xuống thả quân': 'Lower to release piece',
    'Di chuyển đến vị trí quân Rook (trên cao)': 'Move to Rook piece position (above)',
    'Hạ xuống gắp quân Rook': 'Lower to grip Rook piece',
    'Nâng quân Rook lên': 'Lift Rook piece',
    'Di chuyển đến vị trí d1 hoac d8 (tren cao)': 'Move to d1 or d8 (above)',
    'Hạ xuống thả quân Rook': 'Lower to release Rook piece',
    'Nâng lên khỏi bàn cờ': 'Lift above chessboard',
    'Khởi tạo publisher': 'Initialize publisher',
    'Đảm bảo dữ liệu đã được gửi đi': 'Ensure data has been sent',
    'Đọc phản hồi': 'Read response',
    'Nhận được:': 'Received:',
    'Đóng kết nối.': 'Close connection.',
    'Message không phải move command, bỏ qua:': 'Message is not move command, skipping:',
}

for vi, en in replacements.items():
    content = content.replace(vi, en)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done replacing in middleware")
