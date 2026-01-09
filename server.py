import socket
import threading
import time
import struct
import consts
import random

class Server:
    def __init__(self):
        self.server_port = 0
        self.server_ip = self.get_local_ip()
        self.udp_socket = None
        self.tcp_socket = None
        self.team_name = "Festigal Fantasia" 

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start_server(self):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind((self.server_ip, 0))
        self.server_port = self.tcp_socket.getsockname()[1]
        self.tcp_socket.listen()
        
        print(f"Server started, listening on IP address {self.server_ip}")

        broadcast_thread = threading.Thread(target=self.broadcast_offers)
        broadcast_thread.daemon = True 
        broadcast_thread.start()

        while True:
            try:
                client_socket, client_address = self.tcp_socket.accept()
                print(f"New client connected from {client_address}")
                
                # Timeout of 10 minutes for gameplay
                client_socket.settimeout(600)
                
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_thread.start()
            except Exception as e:
                print(f"Error accepting client: {e}")

    def broadcast_offers(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        packet = struct.pack(consts.OFFER_PACKET_FMT, 
                             consts.MAGIC_COOKIE, 
                             consts.MSG_TYPE_OFFER, 
                             self.server_port, 
                             self.team_name.encode('utf-8').ljust(32, b'\0'))

        while True:
            try:
                self.udp_socket.sendto(packet, ('<broadcast>', consts.CLIENT_UDP_PORT))
                time.sleep(1) 
            except Exception as e:
                print(f"Error broadcasting: {e}")
                time.sleep(1)

    def create_deck(self):
        deck = []
        for suit in range(4):
            for rank in range(1, 14):
                deck.append((rank, suit))
        random.shuffle(deck)
        return deck

    def calculate_hand_value(self, hand):
        """Ace is strictly 11 points."""
        value = 0
        for rank, suit in hand:
            if rank == 1: value += 11
            elif rank >= 10: value += 10
            else: value += rank
        return value

    def send_card(self, client_socket, rank, suit, result_code=consts.RESULT_ROUND_NOT_OVER):
        packet = struct.pack(consts.PAYLOAD_SERVER_FMT,
                             consts.MAGIC_COOKIE,
                             consts.MSG_TYPE_PAYLOAD,
                             result_code,
                             rank,
                             suit)
        client_socket.sendall(packet)

    def handle_client(self, client_socket):
        client_name = "Unknown"
        
        try:
            # 1. Handshake (Receive Request)
            request_size = struct.calcsize(consts.REQUEST_PACKET_FMT)
            data = client_socket.recv(request_size)
            if not data or len(data) != request_size: return

            cookie, msg_type, num_rounds, team_name_bytes = struct.unpack(consts.REQUEST_PACKET_FMT, data)
            
            # --- SECURITY CHECK (Item 3) ---
            # If the first message isn't a REQUEST, disconnect immediately.
            if cookie != consts.MAGIC_COOKIE or msg_type != consts.MSG_TYPE_REQUEST:
                print(f"Invalid handshake from client. Closing.")
                return

            client_name = team_name_bytes.decode('utf-8').strip('\x00')
            print(f"[{client_name}] Connected. Playing {num_rounds} rounds.")

            # 2. Play Rounds
            for round_num in range(1, num_rounds + 1):
                print(f"[{client_name}] --- Starting Round {round_num} ---")
                deck = self.create_deck()
                player_hand = []
                dealer_hand = []

                # Initial Deal
                c1 = deck.pop(); player_hand.append(c1); self.send_card(client_socket, *c1)
                c2 = deck.pop(); player_hand.append(c2); self.send_card(client_socket, *c2)
                
                d1 = deck.pop(); dealer_hand.append(d1)
                d2 = deck.pop(); dealer_hand.append(d2) 

                print(f"[{client_name}] Dealer Face-Up: {consts.RANKS[d1[0]]} of {consts.SUITS[d1[1]]}")

                # Player Turn
                player_bust = False
                while True:
                    # --- DOUBLE ACE CHECK (Item 2) ---
                    # This check runs immediately. If Hand > 21 (e.g. 2 Aces = 22), 
                    # it sets bust=True and breaks immediately, skipping any input waiting.
                    player_val = self.calculate_hand_value(player_hand)
                    if player_val > 21:
                        player_bust = True
                        break 

                    try:
                        data = client_socket.recv(struct.calcsize(consts.PAYLOAD_CLIENT_FMT))
                    except socket.timeout:
                        print(f"[{client_name}] Timed out waiting for action.")
                        return

                    if not data: break
                    
                    _, _, decision_bytes = struct.unpack(consts.PAYLOAD_CLIENT_FMT, data)
                    decision = decision_bytes.decode('utf-8').strip('\x00')

                    if decision == "Stand":
                        break
                    elif decision == "Hittt":
                        new_card = deck.pop()
                        player_hand.append(new_card)
                        self.send_card(client_socket, *new_card)
                    else:
                        break

                # Dealer Turn
                dealer_val = self.calculate_hand_value(dealer_hand)
                
                if not player_bust:
                    print(f"[{client_name}] Dealer reveals hidden: {consts.RANKS[d2[0]]} of {consts.SUITS[d2[1]]}")
                    self.send_card(client_socket, *d2)
                    
                    d_hand_str = [f"{consts.RANKS[r]} of {consts.SUITS[s]}" for r, s in dealer_hand]
                    print(f"[{client_name}] Dealer hand: {d_hand_str} (Value: {dealer_val})")
                    
                    while dealer_val < 17:
                        new_card = deck.pop()
                        dealer_hand.append(new_card)
                        dealer_val = self.calculate_hand_value(dealer_hand)
                        print(f"[{client_name}] Dealer draws: {consts.RANKS[new_card[0]]} of {consts.SUITS[new_card[1]]}")
                        self.send_card(client_socket, *new_card)

                # Determine Winner
                player_val = self.calculate_hand_value(player_hand)
                result = consts.RESULT_LOSS 
                
                if player_bust:
                    result = consts.RESULT_LOSS
                    print(f"[{client_name}] Round {round_num}: Player Bust! Dealer Wins.")
                elif dealer_val > 21:
                    result = consts.RESULT_WIN
                    print(f"[{client_name}] Round {round_num}: Dealer Bust! Player Wins.")
                elif player_val > dealer_val:
                    result = consts.RESULT_WIN
                    print(f"[{client_name}] Round {round_num}: Player ({player_val}) > Dealer ({dealer_val}). Player Wins.")
                elif dealer_val > player_val:
                    result = consts.RESULT_LOSS
                    print(f"[{client_name}] Round {round_num}: Dealer ({dealer_val}) > Player ({player_val}). Dealer Wins.")
                else:
                    result = consts.RESULT_TIE
                    print(f"[{client_name}] Round {round_num}: Tie ({player_val}).")

                self.send_card(client_socket, 0, 0, result)

            print(f"[{client_name}] Finished playing. Closing connection.")

        except socket.timeout:
            print(f"[{client_name}] Timed out.")
        except Exception as e:
            print(f"[{client_name}] Error handling client: {e}")
        finally:
            client_socket.close()

if __name__ == "__main__":
    server = Server()
    server.start_server()