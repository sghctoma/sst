#!/usr/bin/env python3

import argparse
import binascii
import socket
import struct


def recvall(sock, n):
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data


parser = argparse.ArgumentParser()
parser.add_argument(
    "-a", "--address",
    default='localhost',
    help="Server address")
parser.add_argument(
    "-p", "--port",
    type=int,
    default=1557,
    help="Server port")
parser.add_argument(
    "-f", "--file",
    type=int,
    default=0,
    help="File identifier (0: directory info, >0: SST file)")
parser.add_argument(
    "-o", "--output",
    help="Output file (if downloading SST)")
parser.add_argument(
    "-c", "--close",
    action='store_true',
    help="Send close TCP server command when finished")
cmd_args = parser.parse_args()

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((cmd_args.address, cmd_args.port))

# send SSt file request
client_socket.send(struct.pack('<II', 3, cmd_args.file))

# receivce size
size_data = client_socket.recv(8)
total_size = struct.unpack('<Q', size_data)[0]

# send header ok
client_socket.send(int.to_bytes(4, 4, 'little'))

data = recvall(client_socket, total_size)

if cmd_args.file == 0:
    board_id = binascii.hexlify(bytearray(data[:8]))
    sample_rate = struct.unpack('<H', data[8:10])[0]
    for f in struct.iter_unpack('<9sQQ', data[10:]):
        print(f)
else:
    path = cmd_args.output
    if path is None:
        path = f'{cmd_args.file:05}.SST'
    with open(path, 'wb') as f:
        f.write(data)

# send file received
client_socket.send(int.to_bytes(5, 4, 'little'))

if cmd_args.close:
    client_socket.send(int.to_bytes(6, 4, 'little'))
