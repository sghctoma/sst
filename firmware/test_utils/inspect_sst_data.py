#!/usr/bin/env python3
import argparse
import struct
import os

# Chunk type names from firmware/src/fw/sst.h
CHUNK_TYPES = {
    0x00: "RATES",
    0x01: "TRAVEL",
    0x02: "MARKER",
    0x03: "IMU",
    0x04: "IMU_META",
    0x05: "GPS",
}

# Record sizes in bytes (from sst.h)
RECORD_SIZES = {
    0x00: 3,   # samplerate_record: uint8_t type + uint16_t rate (packed)
    0x01: 4,   # travel_record: 2 * uint16_t
    0x02: 0,   # marker: zero-length payload
    0x03: 12,  # imu_record: 6 * int16_t
    0x04: 9,   # imu_meta_record: uint8_t + float + float (packed)
    0x05: 46,  # gps_record: see sst.h for full layout
}


def parse_sst(path):
    with open(path, "rb") as f:
        # Header: Magic(3), Version(1), Padding(4), Timestamp(8)
        header_fmt = "<3sB4xq"
        header_size = struct.calcsize(header_fmt)
        data = f.read(header_size)
        if len(data) != header_size:
            print("Error reading header")
            return None

        magic, version, timestamp = struct.unpack(header_fmt, data)
        if magic != b"SST":
            print(f"Invalid magic: {magic}")
            return None

        print(f"SST Version: {version}")
        print(f"Timestamp: {timestamp}")
        print()

        # Track chunk counts, record counts, and sample rates
        chunk_counts = {}
        record_counts = {}
        sample_rates = {}

        chunk_header_fmt = "<BH"  # Type(1), Length(2)

        while True:
            chunk_header_data = f.read(3)
            if not chunk_header_data:
                break

            if len(chunk_header_data) < 3:
                print("Incomplete chunk header")
                break

            chunk_type, chunk_len = struct.unpack(chunk_header_fmt, chunk_header_data)
            chunk_body = f.read(chunk_len)

            if len(chunk_body) != chunk_len:
                print("Incomplete chunk body")
                break

            # Count this chunk type
            chunk_counts[chunk_type] = chunk_counts.get(chunk_type, 0) + 1

            # Count records within chunk
            record_size = RECORD_SIZES.get(chunk_type)
            if record_size is not None:
                if record_size == 0:
                    # Marker chunks count as 1 record each
                    num_records = 1
                elif chunk_len > 0:
                    num_records = chunk_len // record_size
                else:
                    num_records = 0
                record_counts[chunk_type] = record_counts.get(chunk_type, 0) + num_records

            # Parse sample rates from RATES chunk
            if chunk_type == 0x00:  # RATES
                num_entries = chunk_len // 3
                for i in range(num_entries):
                    rtype, rrate = struct.unpack_from("<BH", chunk_body, i * 3)
                    type_name = CHUNK_TYPES.get(rtype, f"0x{rtype:02X}")
                    sample_rates[type_name] = rrate

        # Print chunk summary with record counts
        print("Chunks found:")
        for chunk_type, count in sorted(chunk_counts.items()):
            type_name = CHUNK_TYPES.get(chunk_type, f"0x{chunk_type:02X}")
            records = record_counts.get(chunk_type, 0)
            print(f"  {type_name} (0x{chunk_type:02X}): {count} chunks, {records} records")

        # Print sample rates
        if sample_rates:
            print()
            print("Sample rates:")
            for type_name, rate in sample_rates.items():
                print(f"  {type_name}: {rate} Hz")

        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect SST file structure")
    parser.add_argument("file", help="Path to binary SST file")
    args = parser.parse_args()
    if os.path.exists(args.file):
        parse_sst(args.file)
    else:
        print(f"File not found: {args.file}")
