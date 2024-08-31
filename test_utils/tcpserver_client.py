#!/usr/bin/env python3

import argparse
import binascii
import socket
import struct


STATUS_FILE_REQUESTED = 3
STATUS_HEADER_OK = 4
STATUS_FILE_RECEIVED = 5
STATUS_FINISHED = 6
STATUS_FILE_TRASHED = 10


def recvall(sock, n):
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data


def request_file(cmd_args):
    # send SST file request
    client_socket.send(struct.pack(
        '<II', STATUS_FILE_REQUESTED, cmd_args.file))

    # receivce size
    size_data = client_socket.recv(8)
    total_size = struct.unpack('<Q', size_data)[0]

    # send header ok
    client_socket.send(int.to_bytes(STATUS_HEADER_OK, 4, 'little'))

    data = recvall(client_socket, total_size)

    if cmd_args.file == 0:
        board_id = binascii.hexlify(bytearray(data[:8]))
        sample_rate = struct.unpack('<H', data[8:10])[0]
        print(f"Board ID: {board_id} | Sample rate: {sample_rate}")
        for f in struct.iter_unpack('<9sQQ', data[10:]):
            print(f)
    else:
        path = cmd_args.output
        if path is None:
            path = f'{cmd_args.file:05}.SST'
        with open(path, 'wb') as f:
            f.write(data)

    # send file received
    client_socket.send(int.to_bytes(STATUS_FILE_RECEIVED, 4, 'little'))

    if cmd_args.close:
        client_socket.send(int.to_bytes(STATUS_FINISHED, 4, 'little'))


def trash_file(cmd_args):
    # send SST file request
    client_socket.send(struct.pack(
        '<Ii', STATUS_FILE_REQUESTED, -cmd_args.file))

    # wait for server to acknowledge file deletion
    _ = recvall(client_socket, 4)

    # send file received to close connection
    client_socket.send(int.to_bytes(STATUS_FILE_RECEIVED, 4, 'little'))

    if cmd_args.close:
        client_socket.send(int.to_bytes(STATUS_FINISHED, 4, 'little'))


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
parser.add_argument(
    "-t", "--trash",
    action='store_true',
    help="Trash the file instead of requesting it")
cmd_args = parser.parse_args()

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((cmd_args.address, cmd_args.port))
if cmd_args.trash:
    trash_file(cmd_args)
else:
    request_file(cmd_args)
