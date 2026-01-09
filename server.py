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
        self.team_name = "BlackjackMasters" 

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

    # --- Game Logic Helpers ---

    def create_deck(self):
        """Creates a shuffled deck of 52 cards (Rank 1-13, Suit 0-3)"""
        deck = []
        for suit in range(4):
            for rank in range(1, 14):
                deck.append((rank, suit))
        random.shuffle(deck)
        return deck

    def calculate_hand_value(self, hand):
        [cite_start]"""Calculates the value of a hand according to Blackjack rules [cite: 32-35]"""
        value = 0
        aces = 0
        for rank, suit in hand:
            if rank == 1: # Ace
                aces += 1
                value += 11
            elif rank >= 10: # Face cards (10, J, Q, K)
                value += 10
            else: # Number cards
                value += rank
        
        # Adjust Aces if bust (change from 11 to 1)
        while value > 21 and aces > 0:
            value -= 10
            aces -= 1
        return value

    def send_card(self, client_socket, rank, suit, result_code=consts.RESULT_ROUND_NOT_OVER):
        [cite_start]"""Helper to pack and send a payload message [cite: 123-125]"""
        packet = struct.pack(consts.PAYLOAD_SERVER_FMT,
                             consts.MAGIC_COOKIE,
                             consts.MSG_TYPE_PAYLOAD,
                             result_code,
                             rank,
                             suit)
        client_socket.sendall(packet)

    def handle_client(self, client_socket):
        try:
            # 1. Handshake (Receive Request)
            request_size = struct.calcsize(consts.REQUEST_PACKET_FMT)
            data = client_socket.recv(request_size)
            if not data or len(data) != request_size: return

            cookie, msg_type, num_rounds, team_name_bytes = struct.unpack(consts.REQUEST_PACKET_FMT, data)
            if cookie != consts.MAGIC_COOKIE or msg_type != consts.MSG_TYPE_REQUEST: return

            client_name = team_name_bytes.decode('utf-8').strip('\x00')
            print(f"Received request from team: {client_name}, playing {num_rounds} rounds")

            # 2. Play Rounds
            player_wins = 0
            
            for round_num in range(1, num_rounds + 1):
                print(f"--- Starting Round {round_num} vs {client_name} ---")
                deck = self.create_deck()
                player_hand = []
                dealer_hand = []

                # [cite_start]Initial Deal: 2 cards each [cite: 40-46]
                # Deal to player (send immediately)
                c1 = deck.pop(); player_hand.append(c1); self.send_card(client_socket, *c1)
                c2 = deck.pop(); player_hand.append(c2); self.send_card(client_socket, *c2)
                
                # Deal to dealer (hidden)
                d1 = deck.pop(); dealer_hand.append(d1)
                d2 = deck.pop(); dealer_hand.append(d2) 
                
                # [cite_start]Player Turn [cite: 47-53]
                player_bust = False
                while True:
                    player_val = self.calculate_hand_value(player_hand)
                    if player_val > 21:
                        player_bust = True
                        break # Bust!

                    # Wait for player decision
                    # Receive Packet: Cookie(4), Type(1), Decision(5)
                    data = client_socket.recv(struct.calcsize(consts.PAYLOAD_CLIENT_FMT))
                    if not data: break
                    
                    _, _, decision_bytes = struct.unpack(consts.PAYLOAD_CLIENT_FMT, data)
                    decision = decision_bytes.decode('utf-8').strip('\x00')

                    if decision == "Stand":
                        break
                    [cite_start]elif decision == "Hittt": # Note: "Hittt" per protocol spec [cite: 122]
                        new_card = deck.pop()
                        player_hand.append(new_card)
                        self.send_card(client_socket, *new_card)
                    else:
                        print(f"Unknown decision: {decision}")
                        break

                # [cite_start]Dealer Turn [cite: 54-63]
                dealer_val = self.calculate_hand_value(dealer_hand)
                if not player_bust:
                    # Logic: Hit if < 17
                    while dealer_val < 17:
                        new_card = deck.pop()
                        dealer_hand.append(new_card)
                        dealer_val = self.calculate_hand_value(dealer_hand)

                # [cite_start]Determine Winner [cite: 64-71]
                player_val = self.calculate_hand_value(player_hand)
                result = consts.RESULT_LOSS # Default
                
                if player_bust:
                    result = consts.RESULT_LOSS
                    print(f"Round {round_num}: Player Bust! Dealer Wins.")
                elif dealer_val > 21:
                    result = consts.RESULT_WIN
                    player_wins += 1
                    print(f"Round {round_num}: Dealer Bust! Player Wins.")
                elif player_val > dealer_val:
                    result = consts.RESULT_WIN
                    player_wins += 1
                    print(f"Round {round_num}: Player > Dealer. Player Wins.")
                elif dealer_val > player_val:
                    result = consts.RESULT_LOSS
                    print(f"Round {round_num}: Dealer > Player. Dealer Wins.")
                else:
                    result = consts.RESULT_TIE
                    print(f"Round {round_num}: Tie.")

                # [cite_start]Send Round Result (Using a dummy card 0,0 since round is over) [cite: 73]
                self.send_card(client_socket, 0, 0, result)

            print(f"Finished playing with {client_name}. Closing connection.")

        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()

if __name__ == "__main__":
    server = Server()
    server.start_server()