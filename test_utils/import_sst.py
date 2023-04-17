#!/usr/bin/env python3

import argparse
import base64
import getpass
import os
import requests


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "sst_file",
        help="SST file path")
    parser.add_argument(
        "user",
        help="Username")
    parser.add_argument(
        "setup",
        type=int,
        help="Setup ID")
    parser.add_argument(
        "-s", "--server",
        default='http://localhost:5000/',
        help="HTTP server URL")
    cmd_args = parser.parse_args()

    login_data = dict(
        username=cmd_args.user,
        password=getpass.getpass('password: ')
    )
    resp = requests.post(f'{cmd_args.server}/auth/login', json=login_data)
    rj = resp.json()
    if 'access_token' not in rj:
        print("[ERR] login failed")
        os.exit(-1)
    token = resp.json()['access_token']

    with open(cmd_args.sst_file, 'br') as f:
        sst_data = f.read()

    session = dict(
        name=os.path.basename(cmd_args.sst_file),
        description=f'imported from {cmd_args.sst_file}',
        setup=cmd_args.setup,
        data=base64.b64encode(sst_data).decode('ascii')
    )

    resp = requests.put(
        cmd_args.server + '/api/session',
        headers={'Authorization': f'Bearer {token}'},
        json=session)
    print(resp.json())
