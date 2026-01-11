import socket
import struct
import consts

class Client:
    def __init__(self):
        """
        Initializing the client state variables.
        """
        self.target_server_ip = None
        self.target_server_port = None
        self.base_team_name_string = "Festigal Fantasia" 
        self.udp_listening_socket = None
        self.tcp_game_socket = None
        self.cards_currently_held = []
        self.full_player_display_name = ""
        self.number_of_rounds_requested = 0

    def start_client(self):
        """
        This is where it all begins. We get the name once, then loop forever looking for games.
        """
        self.prompt_user_for_identification()

        while True:
            # We ask for rounds count inside the loop now per new instructions
            self.prompt_user_for_desired_rounds()

            print("Client started, listening for offer requests...")
            
            self.udp_listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # Need REUSEPORT to allow multiple clients on one machine if needed
                self.udp_listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except AttributeError:
                # Fallback for Windows which uses REUSEADDR
                self.udp_listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
            self.udp_listening_socket.bind(("", consts.LISTENING_UDP_PORT_FOR_CLIENT_DISCOVERY))

            # Infinite loop to catch a valid offer packet
            while True:
                raw_udp_data, sender_address_tuple = self.udp_listening_socket.recvfrom(consts.NETWORK_BUFFER_SIZE_IN_BYTES)
                
                try:
                    # Unpack the offer to see if it's legit
                    unpacked_offer = struct.unpack(consts.STRUCT_PACKING_FORMAT_FOR_OFFER, raw_udp_data)
                    cookie_val = unpacked_offer[0]
                    msg_type_val = unpacked_offer[1]
                    server_tcp_port = unpacked_offer[2]
                    server_name_bytes = unpacked_offer[3]

                    if cookie_val != consts.PROTOCOL_MAGIC_COOKIE_IDENTIFIER or msg_type_val != consts.MESSAGE_TYPE_OFFER_ANNOUNCEMENT:
                        continue
                    
                    self.target_server_ip = sender_address_tuple[0]
                    self.target_server_port = server_tcp_port
                    decoded_server_name = server_name_bytes.decode('utf-8').strip('\x00')
                    
                    print(f"Received offer from {self.target_server_ip} ({decoded_server_name}), attempting to connect...")
                    break
                except Exception:
                    continue
            
            # Close UDP since we found our match
            self.udp_listening_socket.close()
            
            # Move on to the TCP part
            self.establish_tcp_connection_and_start_session()

    def prompt_user_for_identification(self):
        """Simple input for the name suffix."""
        id_suffix = input("Enter player number (e.g. 1, 2): ")
        self.full_player_display_name = f"{self.base_team_name_string} {id_suffix}"
        print(f"Playing as: {self.full_player_display_name}")

    def prompt_user_for_desired_rounds(self):
        """Ensures we get a valid integer for rounds."""
        while True:
            user_input_str = input("How many rounds do you want to play? ")
            if user_input_str.isdigit() and int(user_input_str) > 0:
                self.number_of_rounds_requested = int(user_input_str)
                break
            print("Invalid input, please enter a number > 0.")

    def establish_tcp_connection_and_start_session(self):
        try:
            self.tcp_game_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 10 minutes timeout to allow human thinking time
            self.tcp_game_socket.settimeout(600) 
            self.tcp_game_socket.connect((self.target_server_ip, self.target_server_port))
            
            # Wipe the hand clean for a fresh start
            self.cards_currently_held = [] 
            
            # Build the request packet
            binary_request_packet = struct.pack(
                consts.STRUCT_PACKING_FORMAT_FOR_REQUEST,
                consts.PROTOCOL_MAGIC_COOKIE_IDENTIFIER,
                consts.MESSAGE_TYPE_GAME_REQUEST,
                self.number_of_rounds_requested,
                self.full_player_display_name.encode('utf-8').ljust(32, b'\0')
            )
            self.tcp_game_socket.sendall(binary_request_packet)
            
            self.main_gameplay_execution_loop()
            
        except socket.timeout:
            print("Connection timed out.")
        except Exception as conn_error:
            print(f"Error connecting to server: {conn_error}")
        finally:
            if self.tcp_game_socket:
                self.tcp_game_socket.close()
                self.tcp_game_socket = None

    def main_gameplay_execution_loop(self):
        total_wins_counter = 0
        rounds_completed_counter = 0
        is_it_my_turn = True 
        
        # New flag to manage the reveal of the dealer's first card
        has_dealer_visible_card_been_shown = False

        while rounds_completed_counter < self.number_of_rounds_requested:
            try:
                incoming_payload = self.tcp_game_socket.recv(struct.calcsize(consts.STRUCT_PACKING_FORMAT_FOR_SERVER_PAYLOAD))
                if not incoming_payload: 
                    break
                
                # Unpacking the server's message
                unpacked_payload = struct.unpack(consts.STRUCT_PACKING_FORMAT_FOR_SERVER_PAYLOAD, incoming_payload)
                payload_cookie = unpacked_payload[0]
                payload_type = unpacked_payload[1]
                payload_result = unpacked_payload[2]
                card_rank_val = unpacked_payload[3]
                card_suit_val = unpacked_payload[4]
                
                if payload_cookie != consts.PROTOCOL_MAGIC_COOKIE_IDENTIFIER or payload_type != consts.MESSAGE_TYPE_GAME_PAYLOAD:
                    print("Error: Invalid packet received")
                    break

                if payload_result == consts.GAME_RESULT_INDICATOR_ROUND_STILL_ACTIVE:
                    formatted_card_string = f"{consts.CARD_RANKS_MAPPING_DICTIONARY[card_rank_val]} of {consts.CARD_SUITS_MAPPING_DICTIONARY[card_suit_val]}"
                    
                    if is_it_my_turn:
                        # Case 1: Initial deal (first two cards are mine)
                        if len(self.cards_currently_held) < 2:
                            print(f"Got card: {formatted_card_string}")
                            self.cards_currently_held.append((card_rank_val, card_suit_val))
                        
                        # Case 2: I have 2 cards, so this next one must be the dealer's visible card
                        elif not has_dealer_visible_card_been_shown:
                            print(f"Dealer's Face-Up Card: {formatted_card_string}")
                            has_dealer_visible_card_been_shown = True
                            
                            # Only NOW do we ask the user what to do
                            user_decision = self.get_player_decision_input()
                            if user_decision == 'stand':
                                is_it_my_turn = False 
                                print("Waiting for dealer's move...")
                        
                        # Case 3: Normal hit during the game
                        else:
                            print(f"Got card: {formatted_card_string}")
                            self.cards_currently_held.append((card_rank_val, card_suit_val))
                            
                            user_decision = self.get_player_decision_input()
                            if user_decision == 'stand':
                                is_it_my_turn = False 
                                print("Waiting for dealer's move...")

                    else:
                        # If it's not my turn, the server is sending me dealer's cards
                        print(f"Dealer played: {formatted_card_string}")

                else: 
                    # This means the round is over
                    rounds_completed_counter += 1
                    
                    if payload_result == consts.GAME_RESULT_INDICATOR_PLAYER_WIN:
                        print("### YOU WON! ###")
                        total_wins_counter += 1
                    elif payload_result == consts.GAME_RESULT_INDICATOR_PLAYER_LOSS:
                        print("### YOU LOST... ###")
                    else:
                        print("### IT'S A TIE ###")
                    
                    print("-" * 30)
                    # Prepare for next round
                    self.cards_currently_held = [] 
                    is_it_my_turn = True 
                    has_dealer_visible_card_been_shown = False # Reset flag

            except socket.timeout:
                print("Server stopped responding (Timeout).")
                break
            except Exception as game_error:
                print(f"Game error: {game_error}")
                break
        
        print(f"Finished playing {rounds_completed_counter} rounds. Win rate: {total_wins_counter}/{rounds_completed_counter}")
        print("Closing connection and looking for a new server...\n")

    def get_player_decision_input(self):
        """
        Logic to handle Hit or Stand input, including auto-bust detection.
        """
        current_hand_value = self.calculate_current_hand_points(self.cards_currently_held)
        print(f"Your hand value: {current_hand_value}")
        
        # If we have 22 (double ace) or more, we bust immediately.
        if current_hand_value > 21:
            return 'bust'

        while True:
            raw_input = input("Choose action: (h)it or (s)tand? ").lower()
            if raw_input in ['h', 'hit']:
                self.transmit_decision_packet("Hittt")
                return 'hit'
            elif raw_input in ['s', 'stand']:
                self.transmit_decision_packet("Stand")
                return 'stand'
            else:
                print("Invalid input.")

    def transmit_decision_packet(self, action_string):
        binary_decision_packet = struct.pack(
            consts.STRUCT_PACKING_FORMAT_FOR_CLIENT_PAYLOAD,
            consts.PROTOCOL_MAGIC_COOKIE_IDENTIFIER,
            consts.MESSAGE_TYPE_GAME_PAYLOAD,
            action_string.encode('utf-8')
        )
        self.tcp_game_socket.sendall(binary_decision_packet)

    def calculate_current_hand_points(self, hand_list):
        current_score = 0
        for r_val, s_val in hand_list:
            if r_val == 1: 
                current_score += 11 
            elif r_val >= 10: 
                current_score += 10
            else: 
                current_score += r_val
        return current_score

if __name__ == "__main__":
    game_client_instance = Client()
    game_client_instance.start_client()