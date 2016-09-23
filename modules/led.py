import http
import urllib
import logging
from modules import Module
from datetime import datetime

import socket
from textwrap import wrap

def chunks(l, n):
    """
    yields chunks of a list.
    """
    for i in range(0, len(l), n):
        yield l[i:i + n]

class LedBoard(object):
    def __init__(self, dest='megamatrix', port=1337):
        self.target = (dest, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.write_out = 0x01
        self.clear_matrix = 0x02
        self.compat_color = 0x32

        self.write_line = 0x20
        self.write_line_abs = 0x21
        
        self.brightness = 0xFF

        self.clear()

    """ packet: [self.clear_matrix] """
    def clear(self):
        self.sock.sendto(bytearray([self.clear_matrix]), self.target)

    """ packet: [self.write_line_abs][x][y][brightness][text][0x00] """
    def write_text_abs(self, x, y, text):
        packet = bytearray([self.write_line_abs])
        packet.append(x)
        packet.append(y)
        packet.append(self.brightness)
        packet.extend(map(ord, text))
        packet.append(0x00)

        self.setcolor(self.color)
        self.sock.sendto(packet, self.target)
        self.writeout()

    """ packet: [self.write_line][x][y][brightness][text][0x00] """
    def write_text(self, x, y, color, text):
        packet = bytearray([self.write_line])
        packet.append(x)
        packet.append(y)
        packet.append(self.brightness)
        packet.extend(map(ord, text))
        packet.append(0x00)

        self.setcolor(color)
        self.sock.sendto(packet, self.target)
        self.writeout()

    """ packet: [self.write_out] """
    def writeout(self):
        self.sock.sendto(bytearray([self.write_out]), self.target)

    """ packet: [self.compat_color][r][g][b] """
    def setcolor(self, color):
        packet = bytearray([self.compat_color])
        packet.extend(bytearray(color))
        self.sock.sendto(packet, self.target)


class led(Module):
    ledboard = LedBoard()
    color = [0x00, 0xFF, 0x00]
    color_names = {
        "red" : [0xFF, 0x00, 0x00],
        "green" : [0x00, 0xFF, 0x00],
        "blue" : [0x00, 0x00, 0xFF],
        "black" : [0, 0, 0],
        "yellow" : [255, 255, 0],
        "purple" : [255, 0, 255],
        "cyan" : [0, 255, 255],
        "white" : [255, 255, 255],
        "ffaa5e": [0xFF, 0xAA, 0x5E]
    }

    """
        takes a list of lines and prints them line by line.
        taking into account word lengths. and movinging them from line to line,
        as to not seperate words in the middle on some border. 
    """
    def write_text_lines(self, x, y, color, text):
        for yo, line in enumerate(text):
            self.ledboard.write_text(x, y + yo, color, line)

    def cmd_led(self, raw_args, source, **kwargs):
        self.ledboard.clear()
        self.write_text_lines(0, 0, self.color, wrap(raw_args, 21))

    def cmd_led_clear(self, **kwargs):
        """ !led_clear: clears the ledboard """
        self.ledboard.clear()

    def cmd_time(self, **kwargs):
        """ !time: put current time on led matrix board"""
        self.ledboard.clear()
        self.ledboard.write_text(0, 3, self.color, '{:%H:%M:%S}'.format(datetime.now()).center(21))

    def send_welcome(self, user):
        self.ledboard.clear()
        self.ledboard.write_text(0, 0, self.color, "Welcome @space:".center(21))
                
        """ deal with long names. """
        nicklines = wrap(user, 21)
        nicklines = [line.center(21) for line in nicklines]
        """ also color names according to if they contain a bit of color naming. """
        nickcolor = self.color
        for key in self.color_names:
            if key.lower() in user.lower():
                nickcolor = self.color_names[key]
        self.write_text_lines(0, 2, nickcolor, nicklines)

        self.ledboard.write_text(0, 7, self.color, '{:%H:%M:%S}'.format(datetime.now()))
