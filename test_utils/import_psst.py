#!/usr/bin/env python3

import argparse
import base64
import os
import requests


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "psst_file",
        help="PSST file path")
    parser.add_argument(
        "token",
        help="API token")
    parser.add_argument(
        "-a", "--http-api",
        default='http://localhost:5000/api',
        help="HTTP API URL")
    parser.add_argument(
        "-k", "--insecure",
        action='store_true',
        help="Allow insecure server connections")
    cmd_args = parser.parse_args()

    with open(cmd_args.psst_file, 'br') as f:
        psst_data = f.read()

    session = dict(
        name=os.path.basename(cmd_args.psst_file),
        description=f'imported from {cmd_args.psst_file}',
        data=base64.b64encode(psst_data).decode('ascii')
    )

    resp = requests.put(
        cmd_args.gosst_api + '/session/psst',
        headers={'Authorization': f'Bearer {cmd_args.token}'},
        json=session,
        verify=not cmd_args.insecure)
