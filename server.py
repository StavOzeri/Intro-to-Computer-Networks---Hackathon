import socket
import threading
import time
import struct
import consts  
import random

class Server:
    def __init__(self):
        # Initialize basic data
        self.server_port = 0  # TCP port will be chosen automatically
        self.server_ip = self.get_local_ip()  # Solve WSL IP issue
        self.udp_socket = None
        self.tcp_socket = None
        
        # Team name (padded to 32 bytes later) [cite: 109]
        self.team_name = "BlackjackMasters" 

    def get_local_ip(self):
        """
        Helper to find the real IP address connected to the internet,
        bypassing WSL/Virtual adapters issues.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start_server(self):
        """
        Main server loop
        """
        # 1. Setup TCP socket
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind((self.server_ip, 0)) # Bind to any available port
        self.server_port = self.tcp_socket.getsockname()[1]
        self.tcp_socket.listen()
        
        print(f"Server started, listening on IP address {self.server_ip}") # [cite: 77]

        # 2. Start UDP Broadcast in a separate thread
        broadcast_thread = threading.Thread(target=self.broadcast_offers)
        broadcast_thread.daemon = True 
        broadcast_thread.start()

        # 3. Accept TCP connections
        while True:
            try:
                client_socket, client_address = self.tcp_socket.accept()
                print(f"New client connected from {client_address}")
                # Handle client in a separate thread [cite: 18]
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_thread.start()
            except Exception as e:
                print(f"Error accepting client: {e}")

    def broadcast_offers(self):
        """
        Sends UDP broadcast offers every 1 second [cite: 79]
        """
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Pack the offer message [cite: 103-110]
        packet = struct.pack(consts.OFFER_PACKET_FMT, 
                             consts.MAGIC_COOKIE, 
                             consts.MSG_TYPE_OFFER, 
                             self.server_port, 
                             self.team_name.encode('utf-8').ljust(32, b'\0')) # Pad name to 32 bytes

        while True:
            try:
                self.udp_socket.sendto(packet, ('<broadcast>', consts.CLIENT_UDP_PORT))
                time.sleep(1) 
            except Exception as e:
                print(f"Error broadcasting: {e}")
                time.sleep(1)

    def handle_client(self, client_socket):
        """
        Handles the game flow with a single client
        """
        try:
            request_size = struct.calcsize(consts.REQUEST_PACKET_FMT)
            data = client_socket.recv(request_size)
            
            if not data or len(data) != request_size:
                return

            # Unpack request [cite: 111-117]
            cookie, msg_type, num_rounds, team_name_bytes = struct.unpack(consts.REQUEST_PACKET_FMT, data)
            
            if cookie != consts.MAGIC_COOKIE or msg_type != consts.MSG_TYPE_REQUEST:
                return

            client_name = team_name_bytes.decode('utf-8').strip('\x00')
            print(f"Received request from team: {client_name}, playing {num_rounds} rounds")

            # TODO: Game logic implementation here (Deal cards, loops)
            
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()

if __name__ == "__main__":
    server = Server()
    server.start_server()