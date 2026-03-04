import logging
import asyncio
import json
from datetime import datetime
from fairino import Robot
# from amqtt.client import MQTTClient
# from amqtt.mqtt.constants import QOS_1
# import websockets


CELL_LENGTH = 40
ROBOT_IP_ADDRESS = '192.168.58.2'
# ROBOT_IP_ADDRESS = '192.168.1.129'

# MQTT_ENDPOINT = 'mqtt://admin:123456@100.99.22.52:5552/'

# MQTT_ENDPOINT = 'mqtt://127.0.0.1:1883'
# MQTT_ENDPOINT = 'mqtt://10.17.0.238:1883' 
# tcp_ip = '10.17.0.238'
tcp_ip = 'localhost'
robot = Robot.RPC(ROBOT_IP_ADDRESS)
robot.SetSpeed(40)

# MQTT publisher client toàn cục
publisher_client = None
black_index = 0
white_index = 0

# async def init_publisher():
#     """Khởi tạo MQTT publisher"""
#     global publisher_client
#     if publisher_client is None:
#         publisher_client = MQTTClient()
#         await publisher_client.connect(MQTT_ENDPOINT)
#         print("Publisher connected to MQTT broker")


# def create_status_message(goal_id, step, step_details, progress, estimated_time, position_info):
#     """Tạo message với format status yêu cầu"""
#     return {
#         "goal_id": goal_id,
#         "header": {
#             "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
#         },
#         "current_step": step,
#         "step_details": step_details,
#         "progress": progress,
#         "estimated_time_remaining": estimated_time,
#         "current_position": position_info
#     }


# async def pub_feedback(goal_id, step, step_details, progress, estimated_time, position_info, qos=QOS_1):
    # """Publish feedback với format status"""
    # global publisher_client
    # if publisher_client is None:
    #     await init_publisher()

    # status_message = create_status_message(goal_id, step, step_details, progress, estimated_time, position_info)

    # try:
    #     await publisher_client.publish('/robot/move_piece/feedback',
    #                                    json.dumps(status_message).encode('utf-8'),
    #                                    qos=qos)
    #     print(f"Published feedback: {step} - {step_details}")
    # except Exception as e:
    #     print(f"Error publishing feedback: {e}")


# async def pub_result(goal_id, step, step_details, progress, estimated_time, position_info, qos=QOS_1):
#     """Publish result với format status"""
#     global publisher_client
#     if publisher_client is None:
#         await init_publisher()

#     status_message = create_status_message(goal_id=goal_id, step=step, step_details=step_details, progress=progress,
# #                                            estimated_time=estimated_time, position_info=position_info)

#     try:
#         await publisher_client.publish('/robot/move_piece/result',
#                                        json.dumps(status_message).encode('utf-8'),
#                                        qos=qos)
#         print(f"Published result: {step} - {step_details}")
#     except Exception as e:
#         print(f"Error publishing result: {e}")


def convert_chessboard_to_robot(piece, position):

    # Parse position
    if len(position) != 2:
        raise ValueError("Position must be in format like 'a1', 'h8'")

    file_char = position[0].lower()  # a-h
    rank_char = position[1]  # 1-8

    # if rank_char == 8:
    #     rank_char = 1
    # elif rank_char == 7:
    #     rank_char = 2
    # elif rank_char == 6:
    #     rank_char = 3
    # elif rank_char == 5:
    #     rank_char = 4
    # elif rank_char == 4:
    #     rank_char = 5
    # elif rank_char == 3:
    #     rank_char = 6
    # elif rank_char == 2:
    #     rank_char = 7
    # Convert file (a-h) to column number (0-7)
    if file_char < 'a' or file_char > 'h':
        raise ValueError("File must be between 'a' and 'h'")
    file_num = ord(file_char) - ord('a')

    # Convert rank (1-8) to row number (0-7)
    try:
        rank_num = int(rank_char) - 1
        if rank_num < 0 or rank_num > 7:
            raise ValueError("Rank must be between 1 and 8")
    except ValueError:
        raise ValueError("Rank must be a number between 1 and 8")

    # Calculate x, y coordinates
    # Each cell is 40x40, center is at 20,20 offset from corner
    cell_size = 40
    cell_center_offset = cell_size // 2  # 20

    # a1 -> (20, 20), a2 -> (20, 60), a3 -> (20, 100), etc.
    # So x = file * 40 + 20, y = rank * 40 + 20
    x = file_num * cell_size + cell_center_offset
    y = rank_num * cell_size + cell_center_offset

    # Get Z coordinate based on piece type
    def split_piece_types(piece_str):
        if "_" in piece_str:
            color, piece_type = piece_str.split("_")
            return piece_type
        else:
            # If no underscore, assume it's just the piece type
            return "unknown", piece_str

    piece_type = split_piece_types(piece)

    def piece_type_to_z(ptype):
        mapping = {
            "pawn": 22,
            "rook": 27,
            "king": 42,
            "bishop": 30,
            "knight": 25,
            "queen": 43,
        }
        return mapping.get(ptype.lower(), 25)  # default height if unknown

    z = piece_type_to_z(piece_type)

    return x, y, z


# async def pub_status(step, step_details, progress, estimated_time, position_info, qos=QOS_1, goal_id=None):
#     """Publish status với format status"""
#     global publisher_client
#     if publisher_client is None:
#         await init_publisher()

#     status_message = create_status_message(goal_id, step, step_details, progress, estimated_time, position_info)

#     try:
#         await publisher_client.publish('/robot/status',
#                                        json.dumps(status_message).encode('utf-8'),
#                                        qos=qos)
#         print(f"Published status: {step} - {step_details}")
#     except Exception as e:
#         print(f"Error publishing status: {e}")



def split_piece_color(piece_str):
    color, piece_type = piece_str.split("_")
    return color

async def attack_async(from_piece, _from, to_piece, to, goal_id=None):

    global black_index, white_index
    """Async version of attack function"""
    board_height = 19

    x1, y1, z1 = convert_chessboard_to_robot(from_piece, _from)  # Returns (20, 20, 43)
    x2, y2, z2 = convert_chessboard_to_robot(to_piece, to)
    print(from_piece, x1, y1, z1)
    print(to_piece, x2, y2, z2)
 
    # Các vị trí đã định nghĩa
    p0 = [160, 160, 250, -179.000, -0.964, -139.097]
    p1 = [x2, y2, 140, -179.000, -0.964, -139.097]
    p2 = [x2, y2, z2, -179.000, -0.964, -139.097]
    print("so lan an ",white_index)
    print("so lan an ",black_index)
    if split_piece_color(to_piece) == 'white':
        p3 = [380, 20 + ((white_index % 8) * CELL_LENGTH), 140, -179.000, -0.964, -139.097]
        p4 = [380, 20 + ((white_index % 8) * CELL_LENGTH), z2 - board_height, -179.000, -0.964, -139.097]
        white_index += 1
    else:
        p3 = [420, 20 + ((black_index % 8) * CELL_LENGTH), 140, -179.000, -0.964, -139.097]
        p4 = [420, 20 + ((black_index % 8) * CELL_LENGTH), z2 - board_height, -179.000, -0.964, -139.097]
        black_index += 1


    p5 = [x1, y1, 140, -179.000, -0.964, -139.097]
    p6 = [x1, y1, z1, -179.000, -0.964, -139.097]
    p7 = [x2, y2, z1, -179.000, -0.964, -139.097]

    # Các tham số robot
    gripper_id = 1
    gripper_max_time = 30000
    gripper_block = 1
    tool_id = 1
    user = 1
    vel = 100.0
    blendR = 0.0

    print("Starting attack sequence...")

    # await pub_feedback(goal_id=goal_id, step="preparing", step_details="moving_to_home_position", progress=0.05,
                    #    estimated_time=14.0, position_info={"moving_to": "home", "purpose": "preparation"})
    robot.MoveL(desc_pos=p0, tool=tool_id, user=user, vel=vel, blendR=blendR)
    error = robot.MoveGripper(gripper_id, 0, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

    # 2. Di chuyển tới vị trí quân địch (trên cao)
    # await pub_feedback(goal_id=goal_id, step="approaching_target", step_details="navigating_to_enemy_piece",
                    #    progress=0.15, estimated_time=12.0,
                    #    position_info={"moving_to": f"enemy_position_{to_piece}", "purpose": "approach_capture"})
    robot.MoveL(desc_pos=p1, tool=tool_id, user=user, vel=vel, blendR=blendR)
    # # 3. Hạ xuống để gắp quân địch
    # await pub_feedback(goal_id=goal_id, step="capturing", step_details="lowering_to_capture_piece", progress=0.25,
                    #    estimated_time=10.0,
                    #    position_info={"moving_to": f"enemy_position_{to_piece}", "purpose": "capture_enemy_piece"})
    robot.MoveL(desc_pos=p2, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)

    # # 4. Gắp quân địch
    # await pub_feedback(goal_id=goal_id, step="capturing", step_details="gripping_enemy_piece", progress=0.35,
                    #    estimated_time=8.0,
                    #    position_info={"moving_to": f"enemy_position_{to_piece}", "purpose": "grip_enemy_piece"})
    error = robot.MoveGripper(gripper_id, 80, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

    # # 5. Nâng quân địch lên và di chuyển về vị trí cũ
    # await pub_feedback(goal_id=goal_id, step="removing_captured_piece", step_details="lifting_captured_piece",
                    #    progress=0.40, estimated_time=7.0,
                    #    position_info={"moving_to": f"enemy_position_{to_piece}", "purpose": "lift_captured_piece"})
    robot.MoveL(desc_pos=p1, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # # # 6. Di chuyển và thả quân địch vào nghĩa địa (trên cao)
    # # await pub_feedback(goal_id=goal_id, step="removing_captured_piece", step_details="moving_to_disposal_area",
    #                    progress=0.50, estimated_time=6.0,
    #                    position_info={"moving_to": "disposal_area", "purpose": "move_to_disposal"})
    robot.MoveL(desc_pos=p3, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # # 7. Hạ xuống thả quân địch
    # await pub_feedback(goal_id=goal_id, step="removing_captured_piece", step_details="placing_in_disposal_area",
                    #    progress=0.55, estimated_time=5.0,
                    #    position_info={"moving_to": "disposal_area", "purpose": "dispose_captured_piece"})
    robot.MoveL(desc_pos=p4, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)

    # # 8. Thả quân địch
    # await pub_feedback(goal_id=goal_id, step="removing_captured_piece", step_details="releasing_captured_piece",
                    #    progress=0.60, estimated_time=4.5,
                    #    position_info={"moving_to": "disposal_area", "purpose": "release_captured_piece"})
    error = robot.MoveGripper(gripper_id, 0, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

    # # 9. Nâng lên khỏi nghĩa địa
    # await pub_feedback(goal_id=goal_id, step="preparing_own_piece", step_details="lifting_from_disposal", progress=0.65,
                    #    estimated_time=4.0,
                    #    position_info={"moving_to": "disposal_area", "purpose": "lift_from_disposal"})
    rtn = robot.MoveL(desc_pos=p3, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # # 11. Di chuyển đến vị trí quân mình (trên cao)
    # await pub_feedback(goal_id=goal_id, step="moving_own_piece", step_details="approaching_own_piece", progress=0.75,
                    #    estimated_time=3.0,
                    #    position_info={"moving_to": f"own_position_{from_piece}", "purpose": "approach_own_piece"})
    robot.MoveL(desc_pos=p5, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # # 12. Hạ xuống gắp quân mình
    # await pub_feedback(goal_id=goal_id, step="moving_own_piece", step_details="lowering_to_own_piece", progress=0.80,
                    #    estimated_time=2.5,
                    #    position_info={"moving_to": f"own_position_{from_piece}", "purpose": "lower_to_own_piece"})
    robot.MoveL(desc_pos=p6, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)

    # # 13. Gắp quân mình
    # await pub_feedback(goal_id=goal_id, step="moving_own_piece", step_details="gripping_own_piece", progress=0.85,
                    #    estimated_time=2.0,
                    #    position_info={"moving_to": f"own_position_{from_piece}", "purpose": "grip_own_piece"})
    error = robot.MoveGripper(gripper_id, 80, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

    # # 14. Nâng quân mình lên
    # await pub_feedback(goal_id=goal_id, step="moving_own_piece", step_details="lifting_own_piece", progress=0.87,
                    #    estimated_time=1.8,
                    #    position_info={"moving_to": f"own_position_{from_piece}", "purpose": "lift_own_piece"})
    rtn = robot.MoveL(desc_pos=p5, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # 15. Di chuyển đến vị trí đích (trên cao)
    # await pub_feedback(goal_id=goal_id, step="placing_own_piece", step_details="moving_to_destination", progress=0.90,
                    #    estimated_time=1.5,
                    #    position_info={"moving_to": "destination_square", "purpose": "approach_destination"})
    rtn = robot.MoveL(desc_pos=p1, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # 16. Hạ xuống thả quân mình
    # await pub_feedback(goal_id=goal_id, step="placing_own_piece", step_details="lowering_to_destination", progress=0.95,
                    #    estimated_time=1.0,
                    #    position_info={"moving_to": "destination_square", "purpose": "lower_to_destination"})
    rtn = robot.MoveL(desc_pos=p7, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)

    # 17. Thả quân mình
    # await pub_feedback(goal_id=goal_id, step="placing_own_piece", step_details="placing_piece_at_destination",
                    #    progress=0.98, estimated_time=0.5,
                    #    position_info={"moving_to": "destination_square", "purpose": "place_own_piece"})
    error = robot.MoveGripper(gripper_id, 0, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

    # 18. Quay về home
    # await pub_result(goal_id=goal_id, step="move_completed", step_details="attack_sequence_finished", progress=1.0,
                    #  estimated_time=0.0, position_info={"moving_to": "home", "purpose": "move_complete"})
    rtn = robot.MoveL(desc_pos=p0, tool=tool_id, user=user, vel=vel, blendR=blendR)

    robot.ServoMoveStart()
    print("Attack sequence completed!")
    return

async def move_async(from_piece, _from, to_piece, to, goal_id=None):
    """Async version of move function"""
    x1, y1, z1 = convert_chessboard_to_robot(from_piece, _from) 
    x2, y2, z2 = convert_chessboard_to_robot("none_none", to)

    # Các vị trí đã định nghĩa
    p0 = [160, 160, 250, -179.000, -0.964, -139.097]
    p1 = [x1, y1, 140, -179.000, -0.964, -139.097]
    p2 = [x1, y1, z1, -179.000, -0.964, -139.097]
    p3 = [x2, y2, 140, -179.000, -0.964, -139.097]
    p4 = [x2, y2, z1, -179.000, -0.964, -139.097]

    # Các tham số robot
    gripper_id = 1
    gripper_max_time = 30000
    gripper_block = 1
    tool_id = 1
    user = 1
    vel = 100.0
    blendR = 0.0

    print("Starting attack sequence...")

    # await pub_feedback(goal_id=goal_id, step="preparing", step_details="moving_to_home_position", progress=0.05,
                    #    estimated_time=14.0, position_info={"moving_to": "home", "purpose": "preparation"})
    robot.MoveL(desc_pos=p0, tool=tool_id, user=user, vel=vel, blendR=blendR)
    error = robot.MoveGripper(gripper_id, 0, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

    # 1. di chuyen den quan can gap (tren cao)
    # await pub_feedback(goal_id=goal_id, step=f"moving_{from_piece}", step_details=f"approaching_{from_piece}", progress=0.75,
                    #    estimated_time=3.0,
                    #    position_info={"moving_to": f"{to}", "purpose": f"approach_{from_piece}"})
    robot.MoveL(desc_pos=p1, tool=tool_id, user=user, vel=vel, blendR=blendR) 
    # 2. gap quan minh
    # await pub_feedback(goal_id=goal_id, step=f"moving_{from_piece}", step_details=f"lowering_to_{from_piece}", progress=0.80,
                    #    estimated_time=2.5,
                    #    position_info={"moving_to": f"{to}", "purpose": f"lower_to_{from_piece}"})
    robot.MoveL(desc_pos=p2, tool=tool_id, user=user, vel=50, blendR= -1, blendMode = 1)
    # await pub_feedback(goal_id=goal_id, step=f"moving_{from_piece}", step_details=f"gripping_{from_piece}", progress=0.85,
                    #    estimated_time=2.0,
                    #    position_info={"moving_to": f"own_position_{from_piece}", "purpose": f"grip_{from_piece}"})
    error = robot.MoveGripper(gripper_id, 80, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

    # 3. nang quan minh len
    # await pub_feedback(goal_id=goal_id, step=f"moving_{from_piece}", step_details=f"lifting_{from_piece}", progress=0.87,
                    #    estimated_time=1.8,
                    #    position_info={"moving_to": f"{to}", "purpose": f"lift_{from_piece}"})
    rtn = robot.MoveL(desc_pos=p1, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # 4. di chuyen den vi tri dich (tren cao)
    # await pub_feedback(goal_id=goal_id, step=f"placing_{from_piece}", step_details= f"moving_to_{to}", progress=0.90,
                    #    estimated_time=1.5,
                    #    position_info={"moving_to": f"{to}", "purpose": f"approach_{from_piece}"})
    rtn = robot.MoveL(desc_pos=p3, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # 5. ha xuong tha quan minh
    # await pub_feedback(goal_id=goal_id, step=f"placing_{from_piece}", step_details=f"lowering_to_{to}", progress=0.95,
                    #    estimated_time=1.0,
                    #    position_info={"moving_to": f"{to}", "purpose": f"lower_to_{to}"})
    rtn = robot.MoveL(desc_pos=p4, tool=tool_id, user=user, vel=50, blendR= -1, blendMode = 1)
    # await pub_feedback(goal_id=goal_id, step=f"placing_{from_piece}", step_details=f"placing_piece_at_{to}",
                    #    progress=0.98, estimated_time=0.5,
                    #    position_info={"moving_to": f"{to}", "purpose": f"place_{from_piece}_at_{to}"})
    error = robot.MoveGripper(gripper_id, 0, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

    # 6. nang len khoi ban co
    # await pub_feedback(goal_id=goal_id, step="finalizing", step_details=f"lifting_from_{to}", progress=0.99,
                    #    estimated_time=0.2,
                    #    position_info={"moving_to": f"{to}", "purpose": f"lift_from_{to}"})
    rtn = robot.MoveL(desc_pos=p3, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # 7. quay ve home
    # await pub_result(goal_id=goal_id, step="move_completed", step_details="move_sequence_finished", progress=1.0,
                    #  estimated_time=0.0, position_info={"moving_to": "home", "purpose": "move_complete"})
    rtn = robot.MoveL(desc_pos=p0, tool=tool_id, user=user, vel=vel, blendR=blendR)

    robot.ServoMoveStart()
    print("Move sequence completed!")
    return

async def kingside_castle_async(from_piece, _from, to_piece, to, goal_id=None):


    x1, y1, z1 = convert_chessboard_to_robot(from_piece, _from)  
    x2, y2, z2 = convert_chessboard_to_robot(to_piece, to)
    print(from_piece, x1, y1, z1)
    print(to_piece, x2, y2, z2)

    """Async version of castle function"""
    # Các vị trí đã định nghĩa
    p0 = [160, 160, 250, -179.000, -0.964, -139.097]
    
    if split_piece_color(from_piece) == 'white':
        p1 = [x1, y1, 140 , -179.000, -0.964, -139.097]
        p2 = [x1, y1, z1, -179.000, -0.964, -139.097]
        p3 = [260, 20, 140, -179.000, -0.964, -139.097]
        p4 = [260, 20, z1, -179.000, -0.964, -139.097]
        p5 = [x2, y2, 140, -179.000, -0.964, -139.097]
        p6 = [x2, y2, z2, -179.000, -0.964, -139.097]
        p7 = [220, 20, 140, -179.000, -0.964, -139.097]
        p8 = [220, 20, z2, -179.000, -0.964, -139.097]
        king_position = "g1"
        rook_position = "f1"
    else:
        p1 = [x1, y1, 140 , -179.000, -0.964, -139.097]
        p2 = [x1, y1, z1, -179.000, -0.964, -139.097]
        p3 = [260, 300, 140, -179.000, -0.964, -139.097]
        p4 = [260, 300, z1, -179.000, -0.964, -139.097]
        p5 = [x2, y2, 140, -179.000, -0.964, -139.097]
        p6 = [x2, y2, z2, -179.000, -0.964, -139.097]
        p7 = [220, 300, 140, -179.000, -0.964, -139.097]
        p8 = [220, 300, z2, -179.000, -0.964, -139.097]
        king_position = "g8"
        rook_position = "f8"
    print(rook_position)
    print(king_position)
    # Các tham số robot
    gripper_id = 1
    gripper_max_time = 30000
    gripper_block = 1
    tool_id = 1
    user = 1
    vel = 100.0
    blendR = 0.0

    print("Starting castle sequence...")

    # await pub_feedback(goal_id=goal_id, step="preparing", step_details="moving_to_home_position", progress=0.05,
                        # estimated_time=14.0, position_info={"moving_to": "home", "purpose": "preparation"})
    robot.MoveL(desc_pos=p0, tool=tool_id, user=user, vel=vel, blendR=blendR)
    error = robot.MoveGripper(gripper_id, 0, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

        # 2. toi cho quan King
    # await pub_feedback(goal_id=goal_id, step="approaching_target", step_details="navigating_to_King_piece",
                        # progress=0.15, estimated_time=12.0,
                        # position_info={"moving_to": "King_position", "purpose": "approach_capture"})
    robot.MoveL(desc_pos=p1, tool=tool_id, user=user, vel=vel, blendR=blendR)
        # # 3. gap quan King
    # await pub_feedback(goal_id=goal_id, step="capturing", step_details="lowering_to_King_piece", progress=0.25,
                        # estimated_time=10.0,
                        # position_info={"moving_to": "King_position_", "purpose": "capture_King_piece"})
    robot.MoveL(desc_pos=p2, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)
    # await pub_feedback(goal_id=goal_id, step="capturing", step_details="gripping_King_piece", progress=0.35,
                        # estimated_time=8.0,
                        # position_info={"moving_to": "King_position_", "purpose": "grip_King_piece"})
    error = robot.MoveGripper(gripper_id, 80, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)
        # # 5. Nâng quân king lên
    # await pub_feedback(goal_id=goal_id, step="moving_King_piece", step_details="lifting_King_piece",
                        # progress=0.40, estimated_time=7.0,
                        # position_info={"moving_to": "King_position_", "purpose": "lift_King_piece"})
    robot.MoveL(desc_pos=p1, tool=tool_id, user=user, vel=vel, blendR=blendR)

        # 6. di chuyen den c1 hoac c8 tren cao
    # await pub_feedback(goal_id=goal_id, step="moving_King_piece", step_details=f"moving_to_{king_position}",
                        # progress=0.50, estimated_time=6.0,
                        # position_info={"moving_to": f"{king_position}", "purpose": "move_to_disposal"})
    robot.MoveL(desc_pos=p3, tool=tool_id, user=user, vel=vel, blendR=blendR)

        # # 7. Hạ xuống thả quân 
    # await pub_feedback(goal_id=goal_id, step="moving_King_piece", step_details=f"placing_in_{king_position}",
                        # progress=0.55, estimated_time=5.0,
                        # position_info={"moving_to": f"{king_position}", "purpose": "lowering_King_piece"})
    robot.MoveL(desc_pos=p4, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)
    # await pub_feedback(goal_id=goal_id, step="moving_King_piece", step_details="releasing_King_piece",
                        # progress=0.60, estimated_time=4.5,
                        # position_info={"moving_to": f"{king_position}", "purpose": "release_King_piece"})
    error = robot.MoveGripper(gripper_id, 0, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)
    # await pub_feedback(goal_id=goal_id, step="preparing_Rook_piece", step_details=f"waiting_from_{king_position}", progress=0.65,
                        # estimated_time=4.0,
                        # position_info={"moving_to": f"{rook_position}", "purpose": "prepare_for_Rook_piece"})
    rtn = robot.MoveL(desc_pos=p3, tool=tool_id, user=user, vel=vel, blendR=blendR)

        # # 11. Di chuyển đến vị trí quân Rook (trên cao)
    # await pub_feedback(goal_id=goal_id, step="moving_Rook_piece", step_details="approaching_Rook_piece", progress=0.75,
                        # estimated_time=3.0,
                        # position_info={"moving_to": f"{rook_position}", "purpose": "approach_Rook_piece"})
    robot.MoveL(desc_pos=p5, tool=tool_id, user=user, vel=vel, blendR=blendR)

        # # 12. Hạ xuống gắp quân Rook
    # await pub_feedback(goal_id=goal_id, step="moving_Rook_piece", step_details="lowering_to_Rook_piece", progress=0.80,
                        # estimated_time=2.5,
                        # position_info={"moving_to": f"{rook_position}", "purpose": "lower_to_Rook_piece"})
    robot.MoveL(desc_pos=p6, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)
    # await pub_feedback(goal_id=goal_id, step="moving_Rook_piece", step_details="gripping_Rook_piece", progress=0.85,
                        # estimated_time=2.0,
                        # position_info={"moving_to": f"{rook_position}", "purpose": "grip_Rook_piece"})
    error = robot.MoveGripper(gripper_id, 80, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

        # # 13. Nâng quân Rook lên
    # await pub_feedback(goal_id=goal_id, step="moving_Rook_piece", step_details="lifting_Rook_piece", progress=0.87,
                        # estimated_time=1.8,
                        # position_info={"moving_to": f"{rook_position}", "purpose": "lift_Rook_piece"})
    rtn = robot.MoveL(desc_pos=p5, tool=tool_id, user=user, vel=vel, blendR=blendR)

        # 15. Di chuyển đến vị trí d1 hoac d8 (tren cao)
    # await pub_feedback(goal_id=goal_id, step="placing_Rook_piece", step_details=f"moving_to_{rook_position}", progress=0.90,
                        # estimated_time=1.5,
                        # position_info={"moving_to": f"{rook_position}", "purpose": f"approach_{rook_position}"})
    rtn = robot.MoveL(desc_pos=p7, tool=tool_id, user=user, vel=vel, blendR=blendR)

        # 16. Hạ xuống thả quân Rook
    # await pub_feedback(goal_id=goal_id, step="placing_Rook_piece", step_details=f"lowering_to_{rook_position}", progress=0.95,
                        # estimated_time=1.0,
                        # position_info={"moving_to": f"{rook_position}", "purpose": f"lower_to_{rook_position}"})
    rtn = robot.MoveL(desc_pos=p8, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)
    # await pub_feedback(goal_id=goal_id, step="placing_Rook_piece", step_details=f"placing_piece_at_{rook_position}",
                        # progress=0.98, estimated_time=0.5,
                        # position_info={"moving_to": f"{rook_position}", "purpose": "place_Rook_piece"})
    error = robot.MoveGripper(gripper_id, 0, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

        # 18. Nâng lên khỏi bàn cờ
    # await pub_feedback(goal_id=goal_id, step="finalizing", step_details=f"lifting_from_{rook_position}", progress=0.99,
                        # estimated_time=0.2,
                        # position_info={"moving_to": f"{rook_position}", "purpose": f"lift_from_{rook_position}"})
    rtn = robot.MoveL(desc_pos=p7, tool=tool_id, user=user, vel=vel, blendR=blendR)

        # 19. Quay về home
    # await pub_result(goal_id=goal_id, step="castle_completed", step_details="castle_sequence_finished", progress=1.0,
                        # estimated_time=0.0, position_info={"moving_to": "home", "purpose": "castle_complete"})
    rtn = robot.MoveL(desc_pos=p0, tool=tool_id, user=user, vel=vel, blendR=blendR)

    robot.ServoMoveStart()
    print("Castle sequence completed!")
    return

async def queenside_castle_async(from_piece, _from, to_piece, to, goal_id=None):


    x1, y1, z1 = convert_chessboard_to_robot(from_piece, _from)  
    x2, y2, z2 = convert_chessboard_to_robot(to_piece, to)
    print(from_piece, x1, y1, z1)
    print(to_piece, x2, y2, z2)

    """Async version of castle function"""
    # Các vị trí đã định nghĩa
    p0 = [160, 160, 250, -179.000, -0.964, -139.097]
    
    if split_piece_color(from_piece) == 'white':
        p1 = [x1, y1, 140 , -179.000, -0.964, -139.097]
        p2 = [x1, y1, z1, -179.000, -0.964, -139.097]
        p3 = [100, 20, 140, -179.000, -0.964, -139.097]
        p4 = [100, 20, z1, -179.000, -0.964, -139.097]
        p5 = [x2, y2, 140, -179.000, -0.964, -139.097]
        p6 = [x2, y2, z2, -179.000, -0.964, -139.097]
        p7 = [140, 20, 140, -179.000, -0.964, -139.097]
        p8 = [140, 20, z2, -179.000, -0.964, -139.097]
        king_position = "c1"
        rook_position = "d1" 
    else:
        p1 = [x1, y1, 140 , -179.000, -0.964, -139.097]
        p2 = [x1, y1, z1, -179.000, -0.964, -139.097]
        p3 = [100, 300, 140, -179.000, -0.964, -139.097]
        p4 = [100, 300, z1, -179.000, -0.964, -139.097]
        p5 = [x2, y2, 140, -179.000, -0.964, -139.097]
        p6 = [x2, y2, z2, -179.000, -0.964, -139.097]
        p7 = [140, 300, 140, -179.000, -0.964, -139.097]
        p8 = [140, 300, z2, -179.000, -0.964, -139.097]
        king_position = "c8"
        rook_position = "d8"

    # Các tham số robot
    gripper_id = 1
    gripper_max_time = 30000
    gripper_block = 1
    tool_id = 1
    user = 1
    vel = 100.0
    blendR = 0.0

    print("Starting attack sequence...")

    # await pub_feedback(goal_id=goal_id, step="preparing", step_details="moving_to_home_position", progress=0.05,
                    #    estimated_time=14.0, position_info={"moving_to": "home", "purpose": "preparation"})
    robot.MoveL(desc_pos=p0, tool=tool_id, user=user, vel=vel, blendR=blendR)
    error = robot.MoveGripper(gripper_id, 0, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

    # 2. toi cho quan King
    # await pub_feedback(goal_id=goal_id, step="approaching_target", step_details="navigating_to_King_piece",
                    #    progress=0.15, estimated_time=12.0,
                    #    position_info={"moving_to": "King_position", "purpose": "approach_capture"})
    robot.MoveL(desc_pos=p1, tool=tool_id, user=user, vel=vel, blendR=blendR)
    # # 3. gap quan King
    # await pub_feedback(goal_id=goal_id, step="capturing", step_details="lowering_to_King_piece", progress=0.25,
                    #    estimated_time=10.0,
                    #    position_info={"moving_to": "King_position_", "purpose": "capture_King_piece"})
    robot.MoveL(desc_pos=p2, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)
    # await pub_feedback(goal_id=goal_id, step="capturing", step_details="gripping_King_piece", progress=0.35,
                    #    estimated_time=8.0,
                    #    position_info={"moving_to": "King_position_", "purpose": "grip_King_piece"})
    error = robot.MoveGripper(gripper_id, 80, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)
    # # 5. Nâng quân king lên
    # await pub_feedback(goal_id=goal_id, step="moving_King_piece", step_details="lifting_King_piece",
                    #    progress=0.40, estimated_time=7.0,
                    #    position_info={"moving_to": "King_position_", "purpose": "lift_King_piece"})
    robot.MoveL(desc_pos=p1, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # 6. di chuyen den c1 hoac c8 tren cao
    # await pub_feedback(goal_id=goal_id, step="moving_King_piece", step_details=f"moving_to_{king_position}",
                    #    progress=0.50, estimated_time=6.0,
                    #    position_info={"moving_to": f"{king_position}", "purpose": "move_to_disposal"})
    robot.MoveL(desc_pos=p3, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # # 7. Hạ xuống thả quân 
    # await pub_feedback(goal_id=goal_id, step="moving_King_piece", step_details=f"placing_in_{king_position}",
                    #    progress=0.55, estimated_time=5.0,
                    #    position_info={"moving_to": f"{king_position}", "purpose": "lowering_King_piece"})
    robot.MoveL(desc_pos=p4, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)
    # await pub_feedback(goal_id=goal_id, step="moving_King_piece", step_details="releasing_King_piece",
                    #    progress=0.60, estimated_time=4.5,
                    #    position_info={"moving_to": f"{king_position}", "purpose": "release_King_piece"})
    error = robot.MoveGripper(gripper_id, 0, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)
    # await pub_feedback(goal_id=goal_id, step="preparing_Rook_piece", step_details=f"waiting_from_{king_position}", progress=0.65,
                    #    estimated_time=4.0,
                    #    position_info={"moving_to": f"{rook_position}", "purpose": "prepare_for_Rook_piece"})
    rtn = robot.MoveL(desc_pos=p3, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # # 11. Di chuyển đến vị trí quân Rook (trên cao)
    # await pub_feedback(goal_id=goal_id, step="moving_Rook_piece", step_details="approaching_Rook_piece", progress=0.75,
                    #    estimated_time=3.0,
                    #    position_info={"moving_to": f"{rook_position}", "purpose": "approach_Rook_piece"})
    robot.MoveL(desc_pos=p5, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # # 12. Hạ xuống gắp quân Rook
    # await pub_feedback(goal_id=goal_id, step="moving_Rook_piece", step_details="lowering_to_Rook_piece", progress=0.80,
                    #    estimated_time=2.5,
                    #    position_info={"moving_to": f"{rook_position}", "purpose": "lower_to_Rook_piece"})
    robot.MoveL(desc_pos=p6, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)
    # await pub_feedback(goal_id=goal_id, step="moving_Rook_piece", step_details="gripping_Rook_piece", progress=0.85,
                    #    estimated_time=2.0,
                    #    position_info={"moving_to": f"{rook_position}", "purpose": "grip_Rook_piece"})
    error = robot.MoveGripper(gripper_id, 80, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

    # # 13. Nâng quân Rook lên
    # await pub_feedback(goal_id=goal_id, step="moving_Rook_piece", step_details="lifting_Rook_piece", progress=0.87,
                    #    estimated_time=1.8,
                    #    position_info={"moving_to": f"{rook_position}", "purpose": "lift_Rook_piece"})
    rtn = robot.MoveL(desc_pos=p5, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # 15. Di chuyển đến vị trí d1 hoac d8 (tren cao)
    # await pub_feedback(goal_id=goal_id, step="placing_Rook_piece", step_details=f"moving_to_{rook_position}", progress=0.90,
                    #    estimated_time=1.5,
                    #    position_info={"moving_to": f"{rook_position}", "purpose": f"approach_{rook_position}"})
    rtn = robot.MoveL(desc_pos=p7, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # 16. Hạ xuống thả quân Rook
    # await pub_feedback(goal_id=goal_id, step="placing_Rook_piece", step_details=f"lowering_to_{rook_position}", progress=0.95,
                    #    estimated_time=1.0,
                    #    position_info={"moving_to": f"{rook_position}", "purpose": f"lower_to_{rook_position}"})
    rtn = robot.MoveL(desc_pos=p8, tool=tool_id, user=user, vel=50, blendR=-1, blendMode = 1)
    # await pub_feedback(goal_id=goal_id, step="placing_Rook_piece", step_details=f"placing_piece_at_{rook_position}",
                    #    progress=0.98, estimated_time=0.5,
                    #    position_info={"moving_to": f"{rook_position}", "purpose": "place_Rook_piece"})
    error = robot.MoveGripper(gripper_id, 0, 50, 50, gripper_max_time, gripper_block, 0, 0, 0, 0)

    # 18. Nâng lên khỏi bàn cờ
    # await pub_feedback(goal_id=goal_id, step="finalizing", step_details="lifting_from_{rook_position}", progress=0.99,
                    #    estimated_time=0.2,
                    #    position_info={"moving_to": f"{rook_position}", "purpose": f"lift_from_{rook_position}"})
    rtn = robot.MoveL(desc_pos=p7, tool=tool_id, user=user, vel=vel, blendR=blendR)

    # 19. Quay về home
    # await pub_result(goal_id=goal_id, step="castle_completed", step_details="castle_sequence_finished", progress=1.0,
                    #  estimated_time=0.0, position_info={"moving_to": "home", "purpose": "castle_complete"})
    rtn = robot.MoveL(desc_pos=p0, tool=tool_id, user=user, vel=vel, blendR=blendR)

    robot.ServoMoveStart()
    print("Castle sequence completed!")
    return
# logger = logging.getLogger(__name__)


# def handle_goal(payload: bytes):
#     print("Goal received:", payload)


# def handle_cancel(payload: bytes):
#     print("Cancel received:", payload)


# async def sub_robot_topics():
#     # Khởi tạo publisher
#     await init_publisher()

#     C = MQTTClient()

#     await C.connect(MQTT_ENDPOINT)
#     await C.subscribe([
#         ('robot/move_piece/goal', QOS_1),
# #         # ('/robot/move_piece/cancel', QOS_1),
        
        
#     ])
# tcp_ip = '100.99.22.52'
tcp = 'localhost'
# tcp = '127.0.0.1'

async def tcp_client():
    reader, writer = await asyncio.open_connection(tcp_ip, 8080)
    # reader, writer = await asyncio.open_connection(tcp_ip, 3000)

    identify_message = {
        "type": "robot_identify",
        "robot_id": "chess_robot_middleware"
    }
         
    writer.write(json.dumps(identify_message).encode('utf-8') + b'\n')   
    await writer.drain() # Đảm bảo dữ liệu đã được gửi đi
        
        # Đọc phản hồi
        # data = await reader.read(1024)
        # print(f"Nhận được: {data.decode('utf-8')}")
        # await asyncio.sleep(10)

        # print("🔌 Đóng kết nối.")
        # writer.close()
        # await writer.wait_closed()

   
    while True:
        
        data = await reader.read(1024)
        print(f"Nhận được: {data}")
        payload = json.loads(data)
        if not payload.get('move'):
            print(f"Message không phải move command, bỏ qua: {payload}")
            continue
        from_piece = payload.get('move').get('from_piece')
        _from = payload.get('move').get('from')
        to_piece = payload.get('move').get('to_piece')
        to = payload.get('move').get('to')
        goal_id = payload.get('goal_id')
        type = payload.get('move').get('type')

        if type == 'attack':
            result = await attack_async(from_piece, _from, to_piece, to, goal_id)
            print("result:", result)
        elif type == 'move':
            result = await move_async(from_piece, _from, to_piece,to, goal_id)
            print("result:", result)
        elif type == 'castle':
            if to == 'h1' or to == 'h8':
                result = await kingside_castle_async(from_piece, _from, to_piece, to, goal_id)
                print("kingside_castle result:", result)
            else:
                result = await queenside_castle_async(from_piece, _from, to_piece, to, goal_id)
                print("queenside_castle result:", result)
            # robot.CloseRPC()
            # if topic == '/robot/move_piece/goal':
            #     handle_goal(payload)
            # elif topic == '/robot/move_piece/cancel':
            #     handle_cancel(payload)
            # print("%d:  %s => %s" % (i, topic, payload))

    robot.CloseRPC()
    # writer.close()
    # await writer.wait_closed()



if __name__ == '__main__':
    formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    # asyncio.get_event_loop().run_until_complete(sub_robot_topics())
    asyncio.run(tcp_client())
