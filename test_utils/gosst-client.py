#!/usr/bin/env python3

import argparse
import os
import socket
import sys
import uuid


parser = argparse.ArgumentParser()
parser.add_argument(
    "sst_file",
    help="SST file path")
parser.add_argument(
    "board_id",
    help="Pico board identifier")
parser.add_argument(
    "-a", "--address",
    default='localhost',
    help="Server address")
parser.add_argument(
    "-p", "--port",
    type=int,
    default=557,
    help="Server port")
cmd_args = parser.parse_args()

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((cmd_args.address, cmd_args.port))

sst_size = os.path.getsize(cmd_args.sst_file)
with open(cmd_args.sst_file, 'rb') as f:
    sst_data = f.read()
sst_name = os.path.basename(cmd_args.sst_file).encode()

# send the header
header = (b'ID' + bytes.fromhex(cmd_args.board_id) +
          sst_size.to_bytes(8, 'little', signed=False) +
          sst_name)
client_socket.send(header)

# wait for header response
response = client_socket.recv(1)[0]
if response != 4:
    print("header was not accepted!")
    sys.exit(-1)

# send SST data
client_socket.send(sst_data)
response = client_socket.recv(1)[0]
if response != 6:
    print("session could not be imported!")
    sys.exit(-1)

response = client_socket.recv(16)
id = uuid.UUID(bytes=response)
print(id)

client_socket.close()
