import socket
import struct
import consts

class Client:
    def __init__(self):
        self.server_ip = None
        self.server_port = None
        self.team_name = "BestClientEver"
        self.udp_socket = None
        self.tcp_socket = None

    def start_client(self):
        print("Client started, listening for offer requests...") # [cite: 86]
        
        # 1. Listen for UDP offers
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Allow multiple clients on the same machine 
        try:
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            # On Windows SO_REUSEPORT might not exist, use SO_REUSEADDR
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
        self.udp_socket.bind(("", consts.CLIENT_UDP_PORT)) # Listen on port 13122 [cite: 138]

        # Wait for an offer
        while True:
            data, addr = self.udp_socket.recvfrom(consts.BUFFER_SIZE)
            
            # Try to unpack the offer [cite: 103-110]
            try:
                cookie, msg_type, server_port, server_name_bytes = struct.unpack(consts.OFFER_PACKET_FMT, data)
                
                if cookie != consts.MAGIC_COOKIE or msg_type != consts.MSG_TYPE_OFFER:
                    continue # Ignore invalid packets
                
                self.server_ip = addr[0] # The IP comes from the sender address
                self.server_port = server_port
                server_name = server_name_bytes.decode('utf-8').strip('\x00')
                
                print(f"Received offer from {self.server_ip}, attempting to connect...") # [cite: 87]
                break # Found a server, stop listening
                
            except Exception:
                continue

        # 2. Connect via TCP
        self.connect_to_server()

    def connect_to_server(self):
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.connect((self.server_ip, self.server_port)) # [cite: 89]
            
            # Ask user for rounds [cite: 83]
            num_rounds = int(input("How many rounds do you want to play? "))
            
            # Send Request Packet [cite: 111-117]
            packet = struct.pack(consts.REQUEST_PACKET_FMT,
                                 consts.MAGIC_COOKIE,
                                 consts.MSG_TYPE_REQUEST,
                                 num_rounds,
                                 self.team_name.encode('utf-8').ljust(32, b'\0'))
            
            self.tcp_socket.sendall(packet) # Note: 'sendall' ensures all data is sent
            
            # TODO: Enter Game Loop (Receive cards, send decisions)
            
        except Exception as e:
            print(f"Error connecting to server: {e}")
        finally:
            if self.tcp_socket:
                self.tcp_socket.close()

if __name__ == "__main__":
    client = Client()
    client.start_client()