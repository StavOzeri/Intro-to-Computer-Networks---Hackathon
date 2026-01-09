import socket
import struct
import consts

class Client:
    def __init__(self):
        self.server_ip = None
        self.server_port = None
        self.base_team_name = "Festigal Fantasia" 
        self.udp_socket = None
        self.tcp_socket = None
        self.my_cards = []
        self.player_full_name = ""
        self.requested_rounds = 0

    def start_client(self):
        # 1. Ask for player name ONCE (Step 3a)
        player_id = input("Enter player number (e.g. 1, 2): ")
        self.player_full_name = f"{self.base_team_name} {player_id}"
        print(f"Playing as: {self.player_full_name}")

        # Loop: Connect -> Play -> Disconnect -> Ask Rounds -> Connect...
        while True:
            # 2. Ask for rounds EVERY time (Step 3b - per new instructions)
            self.get_rounds_input()

            print("Client started, listening for offer requests...")
            
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except AttributeError:
                self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
            self.udp_socket.bind(("", consts.CLIENT_UDP_PORT))

            # Listen for UDP offers
            while True:
                data, addr = self.udp_socket.recvfrom(consts.BUFFER_SIZE)
                try:
                    cookie, msg_type, server_port, server_name_bytes = struct.unpack(consts.OFFER_PACKET_FMT, data)
                    if cookie != consts.MAGIC_COOKIE or msg_type != consts.MSG_TYPE_OFFER:
                        continue
                    
                    self.server_ip = addr[0]
                    self.server_port = server_port
                    server_name = server_name_bytes.decode('utf-8').strip('\x00')
                    
                    print(f"Received offer from {self.server_ip} ({server_name}), attempting to connect...")
                    break
                except Exception:
                    continue
            
            self.udp_socket.close()
            self.connect_and_play()

    def get_rounds_input(self):
        """Asks the user for the number of rounds."""
        while True:
            user_input = input("How many rounds do you want to play? ")
            if user_input.isdigit() and int(user_input) > 0:
                self.requested_rounds = int(user_input)
                break
            print("Invalid input, please enter a number > 0.")

    def connect_and_play(self):
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Timeout set to 10 minutes for gameplay
            self.tcp_socket.settimeout(600) 
            self.tcp_socket.connect((self.server_ip, self.server_port))
            
            # Reset cards for new game
            self.my_cards = [] 
            
            packet = struct.pack(consts.REQUEST_PACKET_FMT,
                                 consts.MAGIC_COOKIE,
                                 consts.MSG_TYPE_REQUEST,
                                 self.requested_rounds,
                                 self.player_full_name.encode('utf-8').ljust(32, b'\0'))
            self.tcp_socket.sendall(packet)
            
            self.game_loop()
            
        except socket.timeout:
            print("Connection timed out.")
        except Exception as e:
            print(f"Error connecting to server: {e}")
        finally:
            if self.tcp_socket:
                self.tcp_socket.close()
                self.tcp_socket = None

    def game_loop(self):
        wins = 0
        rounds_played = 0
        my_turn = True 
        
        while rounds_played < self.requested_rounds:
            try:
                data = self.tcp_socket.recv(struct.calcsize(consts.PAYLOAD_SERVER_FMT))
                if not data: break
                
                cookie, msg_type, result, rank, suit = struct.unpack(consts.PAYLOAD_SERVER_FMT, data)
                
                if cookie != consts.MAGIC_COOKIE or msg_type != consts.MSG_TYPE_PAYLOAD:
                    print("Error: Invalid packet received")
                    break

                if result == consts.RESULT_ROUND_NOT_OVER:
                    card_str = f"{consts.RANKS[rank]} of {consts.SUITS[suit]}"
                    
                    if my_turn:
                        print(f"Got card: {card_str}")
                        self.my_cards.append((rank, suit))
                        
                        if len(self.my_cards) < 2:
                            continue
                        
                        action = self.ask_user_move()
                        if action == 'stand':
                            my_turn = False 
                            print("Waiting for dealer's move...")
                    else:
                        print(f"Dealer played: {card_str}")

                else: # End of round
                    rounds_played += 1
                    if result == consts.RESULT_WIN:
                        print("### YOU WON! ###")
                        wins += 1
                    elif result == consts.RESULT_LOSS:
                        print("### YOU LOST... ###")
                    else:
                        print("### IT'S A TIE ###")
                    
                    print("-" * 30)
                    self.my_cards = [] 
                    my_turn = True 

            except socket.timeout:
                print("Server stopped responding (Timeout).")
                break
            except Exception as e:
                print(f"Game error: {e}")
                break
        
        print(f"Finished playing {rounds_played} rounds. Win rate: {wins}/{rounds_played}")
        print("Closing connection and looking for a new server...\n")

    def ask_user_move(self):
        current_val = self.calculate_hand_value(self.my_cards)
        print(f"Your hand value: {current_val}")
        
        # --- DOUBLE ACE CHECK (Item 2) ---
        # If value is > 21 (e.g., 22 from two aces), we return 'bust' immediately.
        # This prevents the input() prompt from appearing.
        if current_val > 21:
            print("Busted! Waiting for server result...")
            return 'bust'

        while True:
            decision = input("Choose action: (h)it or (s)tand? ").lower()
            if decision in ['h', 'hit']:
                self.send_decision("Hittt")
                return 'hit'
            elif decision in ['s', 'stand']:
                self.send_decision("Stand")
                return 'stand'
            else:
                print("Invalid input.")

    def send_decision(self, action_str):
        packet = struct.pack(consts.PAYLOAD_CLIENT_FMT,
                             consts.MAGIC_COOKIE,
                             consts.MSG_TYPE_PAYLOAD,
                             action_str.encode('utf-8'))
        self.tcp_socket.sendall(packet)

    def calculate_hand_value(self, hand):
        value = 0
        for rank, suit in hand:
            if rank == 1: value += 11 
            elif rank >= 10: value += 10
            else: value += rank
        return value

if __name__ == "__main__":
    client = Client()
    client.start_client()