#!/usr/bin/env python3

import argparse
import base64
import os
import requests


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "sst_file",
        help="SST file path")
    parser.add_argument(
        "setup",
        type=int,
        help="Setup ID")
    parser.add_argument(
        "token",
        help="API token")
    parser.add_argument(
        "-a", "--gosst-api",
        default='http://localhost:8080',
        help="gosst HTTP API URL")
    cmd_args = parser.parse_args()

    with open(cmd_args.sst_file, 'br') as f:
        sst_data = f.read()

    session = dict(
        name=os.path.basename(cmd_args.sst_file),
        description=f'imported from {cmd_args.sst_file}',
        setup=cmd_args.setup,
        data=base64.b64encode(sst_data).decode('ascii')
    )

    resp = requests.put(
        cmd_args.gosst_api + '/session',
        headers={'X-Token': cmd_args.token},
        json=session)
    print(resp.json())
