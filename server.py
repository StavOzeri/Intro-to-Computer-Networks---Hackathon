import socket
import threading
import time
import struct
import consts
import random

class Server:
    def __init__(self):
        """
        Setting up the server instance with necessary placeholders for network sockets
        and identification data.
        """
        self.tcp_listening_port_number = 0
        self.local_machine_ip_address = self.retrieve_network_interface_ip()
        self.udp_broadcast_sender_socket = None
        self.tcp_connection_listener_socket = None
        # Keeping the team name as requested
        self.participating_team_name = "Festigal Fantasia" 

    def retrieve_network_interface_ip(self):
        """
        We need to figure out what IP address this machine is actually using to talk
        to the outside world (like the internet), to avoid getting stuck with a
        useless localhost or WSL address.
        """
        try:
            # We create a dummy socket and try to reach a public DNS (Google)
            # just to see which network interface the OS decides to use.
            temp_socket_for_ip_check = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_socket_for_ip_check.connect(("8.8.8.8", 80))
            
            detected_ip_address = temp_socket_for_ip_check.getsockname()[0]
            temp_socket_for_ip_check.close()
            
            return detected_ip_address
        except Exception:
            # Fallback to localhost if we are completely offline
            return "127.0.0.1"

    def start_server(self):
        """
        Fires up the main TCP listener and kicks off the background thread that
        shouts our existence via UDP.
        """
        self.tcp_connection_listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Binding to port 0 lets the OS pick a free port for us
        self.tcp_connection_listener_socket.bind((self.local_machine_ip_address, 0))
        
        self.tcp_listening_port_number = self.tcp_connection_listener_socket.getsockname()[1]
        self.tcp_connection_listener_socket.listen()
        
        print(f"Server started, listening on IP address {self.local_machine_ip_address}")

        # Spinning up the UDP announcer in the background so it doesn't block the main loop
        background_broadcast_thread = threading.Thread(target=self.continuously_broadcast_availability)
        background_broadcast_thread.daemon = True 
        background_broadcast_thread.start()

        # The main infinite loop waiting for players to join via TCP
        while True:
            try:
                incoming_client_socket, incoming_client_address = self.tcp_connection_listener_socket.accept()
                print(f"New client connected from {incoming_client_address}")
                
                # Setting a generous timeout (10 mins)
                incoming_client_socket.settimeout(600)
                
                # Handling each player in their own thread so we can multitask
                dedicated_client_thread = threading.Thread(
                    target=self.manage_individual_client_session, 
                    args=(incoming_client_socket,)
                )
                dedicated_client_thread.start()
                
            except Exception as error_message:
                print(f"Error accepting client: {error_message}")

    def continuously_broadcast_availability(self):
        """
        This function runs forever in the background, sending out UDP packets
        telling everyone 'Hey, I'm here and this is my port'.
        """
        self.udp_broadcast_sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_broadcast_sender_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Explicitly binding to the WiFi interface to prevent WSL issues
        self.udp_broadcast_sender_socket.bind((self.local_machine_ip_address, 0))

        # Packing the offer message strictly according to protocol
        packed_offer_message = struct.pack(
            consts.STRUCT_PACKING_FORMAT_FOR_OFFER, 
            consts.PROTOCOL_MAGIC_COOKIE_IDENTIFIER, 
            consts.MESSAGE_TYPE_OFFER_ANNOUNCEMENT, 
            self.tcp_listening_port_number, 
            self.participating_team_name.encode('utf-8').ljust(32, b'\0')
        )

        while True:
            try:
                self.udp_broadcast_sender_socket.sendto(
                    packed_offer_message, 
                    ('<broadcast>', consts.LISTENING_UDP_PORT_FOR_CLIENT_DISCOVERY)
                )
                # Sleep for a second to avoid spamming the network too hard
                time.sleep(1) 
            except Exception as error_message:
                print(f"Error broadcasting: {error_message}")
                time.sleep(1)

    def generate_fresh_deck(self):
        new_deck_of_cards = []
        # Loop through suits (0-3) and ranks (1-13) to build a full 52 card set
        for card_suit_id in range(4):
            for card_rank_value in range(1, 14):
                new_deck_of_cards.append((card_rank_value, card_suit_id))
        
        random.shuffle(new_deck_of_cards)
        return new_deck_of_cards

    def compute_total_hand_points(self, current_hand_of_cards):
        """
        Adds up the points. Remember: Per instructions, Ace is ALWAYS 11.
        """
        accumulated_score = 0
        for rank_val, _ in current_hand_of_cards:
            if rank_val == 1: 
                accumulated_score += 11
            elif rank_val >= 10: 
                accumulated_score += 10
            else: 
                accumulated_score += rank_val
        return accumulated_score

    def transmit_game_state_packet(self, target_client_socket, card_rank, card_suit, game_result_code=consts.GAME_RESULT_INDICATOR_ROUND_STILL_ACTIVE):
        binary_payload_packet = struct.pack(
            consts.STRUCT_PACKING_FORMAT_FOR_SERVER_PAYLOAD,
            consts.PROTOCOL_MAGIC_COOKIE_IDENTIFIER,
            consts.MESSAGE_TYPE_GAME_PAYLOAD,
            game_result_code,
            card_rank,
            card_suit
        )
        target_client_socket.sendall(binary_payload_packet)

    def manage_individual_client_session(self, active_client_connection):
        connected_team_name = "Unknown"
        
        try:
            # Step 1: Handle the handshake (Request Packet)
            expected_packet_size = struct.calcsize(consts.STRUCT_PACKING_FORMAT_FOR_REQUEST)
            raw_received_bytes = active_client_connection.recv(expected_packet_size)
            
            if not raw_received_bytes or len(raw_received_bytes) != expected_packet_size:
                return

            # Breaking down the unpacked data into variables
            unpacked_request_data = struct.unpack(consts.STRUCT_PACKING_FORMAT_FOR_REQUEST, raw_received_bytes)
            received_cookie = unpacked_request_data[0]
            received_msg_type = unpacked_request_data[1]
            requested_rounds_count = unpacked_request_data[2]
            raw_team_name_bytes = unpacked_request_data[3]
            
            # Security check: Kick them out if they didn't send a proper REQUEST msg
            if received_cookie != consts.PROTOCOL_MAGIC_COOKIE_IDENTIFIER or received_msg_type != consts.MESSAGE_TYPE_GAME_REQUEST:
                print(f"Invalid handshake from client. Closing.")
                return

            connected_team_name = raw_team_name_bytes.decode('utf-8').strip('\x00')
            print(f"[{connected_team_name}] Connected. Playing {requested_rounds_count} rounds.")

            # Step 2: Loop through the requested number of rounds
            for current_round_number in range(1, requested_rounds_count + 1):
                print(f"[{connected_team_name}] --- Starting Round {current_round_number} ---")
                
                current_game_deck = self.generate_fresh_deck()
                cards_held_by_player = []
                cards_held_by_dealer = []

                # Initial Deal: Give 2 cards to player, 2 to dealer
                player_card_1 = current_game_deck.pop()
                cards_held_by_player.append(player_card_1)
                self.transmit_game_state_packet(active_client_connection, *player_card_1)
                
                player_card_2 = current_game_deck.pop()
                cards_held_by_player.append(player_card_2)
                self.transmit_game_state_packet(active_client_connection, *player_card_2)
                
                dealer_visible_card = current_game_deck.pop()
                cards_held_by_dealer.append(dealer_visible_card)
                
                dealer_hidden_card = current_game_deck.pop()
                cards_held_by_dealer.append(dealer_hidden_card)

                print(f"[{connected_team_name}] Dealer Face-Up: {consts.CARD_RANKS_MAPPING_DICTIONARY[dealer_visible_card[0]]} of {consts.CARD_SUITS_MAPPING_DICTIONARY[dealer_visible_card[1]]}")
                
                # Send the dealer's visible card to the client immediately
                self.transmit_game_state_packet(active_client_connection, *dealer_visible_card)

                # Player's Turn Loop
                did_player_bust = False
                while True:
                    # Check for "Double Ace" or just bad luck immediately
                    current_player_score = self.compute_total_hand_points(cards_held_by_player)
                    if current_player_score > 21:
                        did_player_bust = True
                        break 

                    try:
                        raw_action_data = active_client_connection.recv(struct.calcsize(consts.STRUCT_PACKING_FORMAT_FOR_CLIENT_PAYLOAD))
                    except socket.timeout:
                        print(f"[{connected_team_name}] Timed out waiting for action.")
                        return

                    if not raw_action_data: 
                        break
                    
                    # Decoding the player's decision
                    unpacked_action = struct.unpack(consts.STRUCT_PACKING_FORMAT_FOR_CLIENT_PAYLOAD, raw_action_data)
                    player_decision_string = unpacked_action[2].decode('utf-8').strip('\x00')

                    if player_decision_string == "Stand":
                        break
                    elif player_decision_string == "Hittt":
                        drawn_card = current_game_deck.pop()
                        cards_held_by_player.append(drawn_card)
                        self.transmit_game_state_packet(active_client_connection, *drawn_card)
                    else:
                        break

                # Dealer's Turn (only happens if player is still in the game)
                dealer_total_score = self.compute_total_hand_points(cards_held_by_dealer)
                
                if not did_player_bust:
                    # Show the card we were hiding
                    print(f"[{connected_team_name}] Dealer reveals hidden: {consts.CARD_RANKS_MAPPING_DICTIONARY[dealer_hidden_card[0]]} of {consts.CARD_SUITS_MAPPING_DICTIONARY[dealer_hidden_card[1]]}")
                    self.transmit_game_state_packet(active_client_connection, *dealer_hidden_card)
                    
                    # Just for logging purposes
                    dealer_hand_display = [f"{consts.CARD_RANKS_MAPPING_DICTIONARY[r]} of {consts.CARD_SUITS_MAPPING_DICTIONARY[s]}" for r, s in cards_held_by_dealer]
                    print(f"[{connected_team_name}] Dealer hand: {dealer_hand_display} (Value: {dealer_total_score})")
                    
                    # Dealer hits until 17
                    while dealer_total_score < 17:
                        dealer_new_card = current_game_deck.pop()
                        cards_held_by_dealer.append(dealer_new_card)
                        dealer_total_score = self.compute_total_hand_points(cards_held_by_dealer)
                        
                        print(f"[{connected_team_name}] Dealer draws: {consts.CARD_RANKS_MAPPING_DICTIONARY[dealer_new_card[0]]} of {consts.CARD_SUITS_MAPPING_DICTIONARY[dealer_new_card[1]]}")
                        self.transmit_game_state_packet(active_client_connection, *dealer_new_card)

                # Determine Winner Logic
                final_player_score = self.compute_total_hand_points(cards_held_by_player)
                final_round_result = consts.GAME_RESULT_INDICATOR_PLAYER_LOSS 
                
                if did_player_bust:
                    final_round_result = consts.GAME_RESULT_INDICATOR_PLAYER_LOSS
                    print(f"[{connected_team_name}] Round {current_round_number}: Player Bust! Dealer Wins.")
                
                elif dealer_total_score > 21:
                    final_round_result = consts.GAME_RESULT_INDICATOR_PLAYER_WIN
                    print(f"[{connected_team_name}] Round {current_round_number}: Dealer Bust! Player Wins.")
                
                elif final_player_score > dealer_total_score:
                    final_round_result = consts.GAME_RESULT_INDICATOR_PLAYER_WIN
                    print(f"[{connected_team_name}] Round {current_round_number}: Player ({final_player_score}) > Dealer ({dealer_total_score}). Player Wins.")
                
                elif dealer_total_score > final_player_score:
                    final_round_result = consts.GAME_RESULT_INDICATOR_PLAYER_LOSS
                    print(f"[{connected_team_name}] Round {current_round_number}: Dealer ({dealer_total_score}) > Player ({final_player_score}). Dealer Wins.")
                
                else:
                    final_round_result = consts.GAME_RESULT_INDICATOR_TIE
                    print(f"[{connected_team_name}] Round {current_round_number}: Tie ({final_player_score}).")

                # Send the final verdict to the client
                self.transmit_game_state_packet(active_client_connection, 0, 0, final_round_result)

            print(f"[{connected_team_name}] Finished playing. Closing connection.")

        except socket.timeout:
            print(f"[{connected_team_name}] Timed out.")
        except Exception as error_msg:
            print(f"[{connected_team_name}] Error handling client: {error_msg}")
        finally:
            active_client_connection.close()

if __name__ == "__main__":
    game_server_instance = Server()
    game_server_instance.start_server()