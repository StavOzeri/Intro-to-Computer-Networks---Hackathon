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
        self.my_cards = []

    def start_client(self):
        print("Client started, listening for offer requests...")
        
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
        self.udp_socket.bind(("", consts.CLIENT_UDP_PORT))

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

        self.connect_to_server()

    def connect_to_server(self):
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.connect((self.server_ip, self.server_port))
            
            user_input = input("How many rounds do you want to play? ")
            if not user_input.isdigit(): 
                print("Invalid input, defaulting to 1 round.")
                num_rounds = 1
            else:
                num_rounds = int(user_input)

            packet = struct.pack(consts.REQUEST_PACKET_FMT,
                                 consts.MAGIC_COOKIE,
                                 consts.MSG_TYPE_REQUEST,
                                 num_rounds,
                                 self.team_name.encode('utf-8').ljust(32, b'\0'))
            self.tcp_socket.sendall(packet)
            
            # --- Game Loop ---
            self.play_game(num_rounds)
            
        except Exception as e:
            print(f"Error connecting to server: {e}")
        finally:
            if self.tcp_socket:
                self.tcp_socket.close()

    def play_game(self, rounds):
        """
        Main loop handling the incoming cards and user decisions
        """
        wins = 0
        rounds_played = 0
        
        # We process messages until we finish the requested rounds
        while rounds_played < rounds:
            try:
                # Receive payload from server
                data = self.tcp_socket.recv(struct.calcsize(consts.PAYLOAD_SERVER_FMT))
                if not data: break
                
                cookie, msg_type, result, rank, suit = struct.unpack(consts.PAYLOAD_SERVER_FMT, data)
                
                if cookie != consts.MAGIC_COOKIE or msg_type != consts.MSG_TYPE_PAYLOAD:
                    print("Error: Invalid packet received")
                    break

                # Case 1: Round is ongoing (We got a card)
                if result == consts.RESULT_ROUND_NOT_OVER:
                    card_str = f"{consts.RANKS[rank]} of {consts.SUITS[suit]}"
                    print(f"Got card: {card_str}")
                    self.my_cards.append((rank, suit))
                    
                    # After receiving a card, we (the user) need to decide only if we have 2+ cards
                    # (Logic: If we just got a card, the server is waiting for our move unless we busted)
                    # Simple Check: Ask user for move
                    self.ask_user_move()

                # Case 2: Round Ended (Win/Loss/Tie)
                else:
                    rounds_played += 1
                    if result == consts.RESULT_WIN:
                        print("### YOU WON! ###")
                        wins += 1
                    elif result == consts.RESULT_LOSS:
                        print("### YOU LOST... ###")
                    else:
                        print("### IT'S A TIE ###")
                    
                    print("-" * 30)
                    self.my_cards = [] # Reset hand for next round

            except Exception as e:
                print(f"Game error: {e}")
                break

        print(f"Finished playing {rounds_played} rounds. Win rate: {wins}/{rounds_played}")

    def ask_user_move(self):
        """
        Asks the user for input and sends it to the server
        """
        # Calculate current sum to show user
        current_val = self.calculate_hand_value(self.my_cards)
        print(f"Your hand value: {current_val}")
        
        if current_val > 21:
            print("Busted! Waiting for server result...")
            return # Cannot play if busted

        while True:
            decision = input("Choose action: (h)it or (s)tand? ").lower()
            if decision in ['h', 'hit']:
                self.send_decision("Hittt") # Protocol requires "Hittt" (5 chars)
                break
            elif decision in ['s', 'stand']:
                self.send_decision("Stand")
                break
            else:
                print("Invalid input.")

    def send_decision(self, action_str):
        packet = struct.pack(consts.PAYLOAD_CLIENT_FMT,
                             consts.MAGIC_COOKIE,
                             consts.MSG_TYPE_PAYLOAD,
                             action_str.encode('utf-8'))
        self.tcp_socket.sendall(packet)

    def calculate_hand_value(self, hand):
        """Duplicate logic to show user their score locally"""
        value = 0
        aces = 0
        for rank, suit in hand:
            if rank == 1: aces += 1; value += 11
            elif rank >= 10: value += 10
            else: value += rank
        while value > 21 and aces > 0:
            value -= 10; aces -= 1
        return value

if __name__ == "__main__":
    client = Client()
    client.start_client()