#!/usr/bin/env python3

import msgpack
import sys

from psst import Telemetry, dataclass_from_dict


sst_file = sys.argv[1]
with open(sst_file, 'rb') as f:
    sst_packed = f.read()

sst_data = msgpack.unpackb(sst_packed)
telemetry = dataclass_from_dict(Telemetry, sst_data)

print(telemetry.Front.Present)
print(telemetry.Rear.Present)
