"""
consts.py
This file contains constants and protocol definitions for the Blackjack game.
Defining constants here avoids hard-coding values in the logic files.
"""

# Networking Constants
# The UDP port the client listens on (Hardcoded per assignment instructions)
CLIENT_UDP_PORT = 13122 
# The magic cookie constant (4 bytes)
MAGIC_COOKIE = 0xabcddcba 
# Buffer size for receiving packets
BUFFER_SIZE = 1024 

# Message Types
MSG_TYPE_OFFER = 0x2
MSG_TYPE_REQUEST = 0x3
MSG_TYPE_PAYLOAD = 0x4

# Protocol Structure Formats (using struct library notation)
# I = unsigned int (4 bytes), B = unsigned char (1 byte), H = unsigned short (2 bytes), s = string
# Offer: Cookie(4), Type(1), Port(2), Name(32)
OFFER_PACKET_FMT = '>IBH32s' 

# Request: Cookie(4), Type(1), Rounds(1), Name(32)
REQUEST_PACKET_FMT = '>IBB32s'

# Payload (Client sends Decision): Cookie(4), Type(1), Decision(5 - "Hittt" or "Stand")
PAYLOAD_CLIENT_FMT = '>IB5s'

# Payload (Server sends Card/Result): Cookie(4), Type(1), Result(1), CardRank(2), CardSuit(1)
# Note: The assignment describes Card Value as 3 bytes total (Rank 2 bytes + Suit 1 byte)
PAYLOAD_SERVER_FMT = '>IBBHB' 

# Game Logic Constants
# Result codes
RESULT_ROUND_NOT_OVER = 0x0
RESULT_TIE = 0x1
RESULT_LOSS = 0x2
RESULT_WIN = 0x3

# Suits mapping for display
SUITS = {
    0: 'Hearts',
    1: 'Diamonds',
    2: 'Clubs',
    3: 'Spades'
}

# Ranks mapping for display (11, 12, 13 are J, Q, K)
RANKS = {
    1: 'Ace', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 
    8: '8', 9: '9', 10: '10', 11: 'Jack', 12: 'Queen', 13: 'King'
}