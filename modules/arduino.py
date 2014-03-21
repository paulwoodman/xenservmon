# -*- coding: utf-8 -*-
"""
Created on Tue Sep 11 12:09:33 2012

@author: sean.mackedie
"""

import glob, time, serial

def find_arduino():
    glist = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    port = 'FAIL'
    for p in glist:
        ser = serial.Serial(p, 9600)
        ser.readline()
        time.sleep(1)
        if ser.readline() == 'ARD-SYN\r\n':
            port = p
            break
    return port


def cmd_send(cmd, port):
    cmd_recvd = False
    cmd_complete = False
    invalid = False
    error = False
    ser = serial.Serial(port, 9600)
    ser.readline()
    time.sleep(1)
    if ser.readline() == 'ARD-SYN\r\n':
        ser.write(cmd)
        count = 0
        while (count <=30):
            x = ser.readline()
            if x == 'ARD-ACK\r\n':
                cmd_recvd = True
            elif x == 'ARD-FIN\r\n':
                cmd_complete = True
                break
            elif x == 'ARD-RST\r\n':
                invalid = True
                break
            time.sleep(1)
            count += 1
    elif ser.readline() == 'ARD-RST\r\n':
        invalid = True
    else:
        error = True
    return cmd_recvd, cmd_complete, invalid, error