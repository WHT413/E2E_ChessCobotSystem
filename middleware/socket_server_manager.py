import socket
import threading
import json
from datetime import datetime

class SocketServer:
    def __init__(self, host='localhost', port=3000):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = []
        self.running = False

    def start_server(self):
        """Start the socket server"""
        try:
            # Create socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to address and port
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            self.running = True
            print(f"🚀 Server started on {self.host}:{self.port}")
            print("📡 Waiting for connections...")
            
            while self.running:
                try:
                    # Accept client connection
                    client_socket, address = self.server_socket.accept()
                    print(f"🔗 New connection from {address}")
                    
                    # Store client info
                    client_info = {
                        'socket': client_socket,
                        'address': address,
                        'connected_at': datetime.now()
                    }
                    self.clients.append(client_info)
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        print(f"❌ Socket error: {e}")
                    
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
        finally:
            self.close_server()
   
    def handle_middleware(self, client_socket, address):
        try:
            while self.running:
                # Receive data from client
                # data = client_socket.recv(1024)
                # message = data.decode('utf-8')
                # print(f"📨 Received from {address}: {message}")
                
                # data = await reader.read(1024)
                
                # payload = json.loads(data)
                # Process the message
                command = input("Enter command to send to client (type 'exit' to quit): ")
                if command.strip().lower() == 'exit':
                    break
                response = self.process_message(command)
                response_str = json.dumps(response)
                client_socket.send(response_str.encode('utf-8'))
                # self.send_command_to_client(client_socket)
                

                # response = self.process_message(message, address)
                
                # Send response back to client
                # client_socket.send(response.encode('utf-8'))
                print(f"📤 Sent to {address}: {response}")
                
        except socket.error as e:
            print(f"❌ Client {address} error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error with client {address}: {e}")
        finally:
            # Clean up client connection
            self.remove_client(client_socket, address)
            client_socket.close()
            print(f"🔌 Connection closed for {address}")

    def handle_client(self, client_socket, address):
        """Handle individual client connection"""
        try:
            data = client_socket.recv(1024)
            payload = json.loads(data.decode('utf-8'))
            print(payload)
            sender = 'middleware'
            if sender == 'middleware':
                self.handle_middleware(client_socket, address)
            command = input("Enter command to send to client (type 'exit' to quit): ")
            response = self.process_message(command)
            response_str = json.dumps(response)
            client_socket.send(response_str.encode('utf-8'))
        except socket.error as e:
            print(f"❌ Client {address} error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error with client {address}: {e}")
        # finally:
        #     # Clean up client connection
        #     self.remove_client(client_socket, address)
        #     client_socket.close()
        #     print(f"🔌 Connection closed for {address}")

    def process_message(self, command):
        """Process received message and generate response"""
        # timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        parts = command.strip().split(" ")
        
        response ={ 

    "goal_id": "attack_001",
            "header": {
                "timestamp": "2025-09-08T14:25:00Z"
            },
            "move": {
                "type": parts[0], # "attack", "move", "castle"
                "from": parts[2], # e.g., "d1"
                "to":  parts[4],   # e.g., "f7"
                "from_piece": parts[1], # e.g., "white_bishop"
                "to_piece": parts[3],
                "notation": "Qd1xf7+",
                "results_in_check": True,
                # "from_offset": [-20, 0], 
                # "to_offset": [20, 0],
                # "from_corners": [[192, 448], [256, 448], [256, 512], [192, 512]], # top left, top right, bottom right, bottom left
                # "to_corners": [[320, 64], [384, 64], [384, 128], [320, 128]] # top left, top right, bottom right, bottom left
                # "from_corners": [[40, 0], [0, 0], [0, 0], [0, 0]], # top left, top right, bottom right, bottom left
                # "to_corners": [[40, 0], [0, 0], [0, 0], [0,0 ]] # top left, top right, bottom right, bottom left
            }
    }

        # You can add more sophisticated message processing here
        # For example, JSON parsing, command handling, etc.
        
        return response
        
      

        # You can add more sophisticated message processing here
        # For example, JSON parsing, command handling, etc.
        
    def remove_client(self, client_socket, address):
        """Remove client from clients list"""
        self.clients = [client for client in self.clients 
                       if client['address'] != address]

    # def broadcast_message(self, message):
    #     """Send message to all connected clients"""
    #     disconnected_clients = []
        
    #     for client_info in self.clients:
    #         try:
    #             client_info['socket'].send(message.encode('utf-8'))
    #         except socket.error:
    #             disconnected_clients.append(client_info)
        
    #     # Remove disconnected clients
    #     for client_info in disconnected_clients:
    #         self.remove_client(client_info['socket'], client_info['address'])

    def get_connected_clients(self):
        """Get list of connected clients"""
        return [(client['address'], client['connected_at']) 
                for client in self.clients]

    def close_server(self):
        """Close the server and all client connections"""
        self.running = False
        
        # Close all client connections
        for client_info in self.clients:
            try:
                client_info['socket'].close()
            except:
                pass
        
        # Close server socket
        if self.server_socket:
            self.server_socket.close()
        
        print("🛑 Server stopped")

def main():
    # Create and start server
    server = SocketServer(host='127.0.0.1', port=3000)
    
    try:
        server.start_server()
    except KeyboardInterrupt:
        print("\n⏹️  Server shutdown requested...")
        server.close_server()

if __name__ == "__main__":
    main()
