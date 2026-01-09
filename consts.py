"""
consts.py
This file contains constants and protocol definitions for the Blackjack game.
Defining constants here avoids hard-coding values in the logic files.
"""

# Networking Constants
# The UDP port the client listens on (Hardcoded per assignment instructions) [cite: 138]
CLIENT_UDP_PORT = 13122 
# The magic cookie constant (4 bytes) [cite: 104]
MAGIC_COOKIE = 0xabcddcba 
# Buffer size for receiving packets
BUFFER_SIZE = 1024 

# Message Types [cite: 106, 114, 121]
MSG_TYPE_OFFER = 0x2
MSG_TYPE_REQUEST = 0x3
MSG_TYPE_PAYLOAD = 0x4

# Protocol Structure Formats (using struct library notation)
# I = unsigned int (4 bytes), B = unsigned char (1 byte), H = unsigned short (2 bytes), s = string
# Offer: Cookie(4), Type(1), Port(2), Name(32) [cite: 103-110]
OFFER_PACKET_FMT = '>IBH32s' 

# Request: Cookie(4), Type(1), Rounds(1), Name(32) [cite: 111-117]
REQUEST_PACKET_FMT = '>IBB32s'

# Payload (Client sends Decision): Cookie(4), Type(1), Decision(5 - "Hittt" or "Stand") [cite: 122]
PAYLOAD_CLIENT_FMT = '>IB5s'

# Payload (Server sends Card/Result): Cookie(4), Type(1), Result(1), CardRank(2), CardSuit(1)
# Note: The assignment describes Card Value as 3 bytes total (Rank 2 bytes + Suit 1 byte) [cite: 123-125]
PAYLOAD_SERVER_FMT = '>IBBHB' 

# Game Logic Constants
# Result codes [cite: 123]
RESULT_ROUND_NOT_OVER = 0x0
RESULT_TIE = 0x1
RESULT_LOSS = 0x2
RESULT_WIN = 0x3