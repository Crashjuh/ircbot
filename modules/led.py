from modules import Module
import urllib
import http
import logging
from datetime import datetime
import socket

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
        self.color = [0x00, 0xFF, 0x00]

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
    def write_text(self, x, y, text):
        packet = bytearray([self.write_line])
        packet.append(x)
        packet.append(y)
        packet.append(self.brightness)
        packet.extend(map(ord, text))
        packet.append(0x00)

        self.setcolor(self.color)
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

    def cmd_led(self, raw_args, source, **kwargs):
        """ !led <message>: put message on led matrix board"""
        for y, s in enumerate(chunks(raw_args, 21)):
            self.ledboard.write_text(0, y, s)

    def cmd_led_clear(self, **kwargs):
        """ !led_clear: clears the ledboard """
        self.ledboard.clear()

    def cmd_time(self, **kwargs):
        """ !time: put current time on led matrix board"""
        self.ledboard.clear()
        self.ledboard.write_text(0, 3, '{:%H:%M:%S}'.format(datetime.now()).center(21))

    def send_welcome(self, user):
        self.ledboard.clear()
        self.ledboard.write_text(0, 0, "Welcome @space:".center(21))
        self.ledboard.write_text(0, 2, user.center(21))
        self.ledboard.write_text(0, 7, '{:%H:%M:%S}'.format(datetime.now()))
