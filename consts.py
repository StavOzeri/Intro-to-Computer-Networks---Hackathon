"""
consts.py
This file contains constants and protocol definitions for the Blackjack game.
Defining constants here avoids hard-coding values in the logic files.
"""

# Networking Constants

# The UDP port the client listens on (Hardcoded per assignment instructions)
LISTENING_UDP_PORT_FOR_CLIENT_DISCOVERY = 13122 

# The magic cookie constant (4 bytes) used to validate packets
PROTOCOL_MAGIC_COOKIE_IDENTIFIER = 0xabcddcba 

# Buffer size for receiving packets (in bytes)
NETWORK_BUFFER_SIZE_IN_BYTES = 1024 

# Message Types

# Identifier for the Server Offer packet (UDP)
MESSAGE_TYPE_OFFER_ANNOUNCEMENT = 0x2

# Identifier for the Client Request packet (TCP)
MESSAGE_TYPE_GAME_REQUEST = 0x3

# Identifier for Payload packets (Game moves/results)
MESSAGE_TYPE_GAME_PAYLOAD = 0x4

# Protocol Structure Formats (using struct library notation)
# I = unsigned int (4 bytes), B = unsigned char (1 byte), H = unsigned short (2 bytes), s = string

# Offer Packet Format: Cookie(4), Type(1), Port(2), Name(32)
STRUCT_PACKING_FORMAT_FOR_OFFER = '>IBH32s' 

# Request Packet Format: Cookie(4), Type(1), Rounds(1), Name(32)
STRUCT_PACKING_FORMAT_FOR_REQUEST = '>IBB32s'

# Client Payload Format (Decision): Cookie(4), Type(1), Decision(5 chars)
STRUCT_PACKING_FORMAT_FOR_CLIENT_PAYLOAD = '>IB5s'

# Server Payload Format (Card/Result): Cookie(4), Type(1), Result(1), Rank(2), Suit(1)
STRUCT_PACKING_FORMAT_FOR_SERVER_PAYLOAD = '>IBBHB' 

# Game Logic Constants

# Result codes indicating the state of the round
GAME_RESULT_INDICATOR_ROUND_STILL_ACTIVE = 0x0
GAME_RESULT_INDICATOR_TIE = 0x1
GAME_RESULT_INDICATOR_PLAYER_LOSS = 0x2
GAME_RESULT_INDICATOR_PLAYER_WIN = 0x3

# Suits mapping for display purposes
CARD_SUITS_MAPPING_DICTIONARY = {
    0: 'Hearts',
    1: 'Diamonds',
    2: 'Clubs',
    3: 'Spades'
}

# Ranks mapping for display (11, 12, 13 are J, Q, K)
CARD_RANKS_MAPPING_DICTIONARY = {
    1: 'Ace', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 
    8: '8', 9: '9', 10: '10', 11: 'Jack', 12: 'Queen', 13: 'King'
}