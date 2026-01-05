#!/usr/bin/env python3
"""
Extract GPS data from SST files and create GPX files.

SST File Format (v4 TLV):
- 16-byte header: Magic[3] + Version[1] + Padding[4] + Timestamp[8]
- Chunks: Type[1] + Length[2] + Payload[Length]
- GPS chunk type: 0x05

GPX output includes:
- Standard GPX 1.1: lat, lon, ele, time, fix, sat
- Garmin extensions: speed, course
- Custom SST extension: epe2d, epe3d
"""

import argparse
import struct
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

# SST constants
SST_MAGIC = b"SST"
SST_VERSION = 4
CHUNK_TYPE_GPS = 0x05

# GPS record struct layout (packed):
# uint32_t date       @ 0   (4 bytes)
# uint32_t time_ms    @ 4   (4 bytes)
# double latitude     @ 8   (8 bytes)
# double longitude    @ 16  (8 bytes)
# float altitude      @ 24  (4 bytes)
# float speed         @ 28  (4 bytes)
# float heading       @ 32  (4 bytes)
# uint8_t fix_mode    @ 36  (1 byte)
# uint8_t satellites  @ 37  (1 byte)
# float epe_2d        @ 38  (4 bytes)
# float epe_3d        @ 42  (4 bytes)
# Total: 46 bytes
GPS_RECORD_FORMAT = "<IIddfffBBff"
GPS_RECORD_SIZE = struct.calcsize(GPS_RECORD_FORMAT)  # Should be 46

# GPX namespaces
NS_GPX = "http://www.topografix.com/GPX/1/1"
NS_GPXTPX = "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
NS_SST = "http://sst.telemetry/gpx/1"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"


@dataclass
class GpsRecord:
    date: int  # YYYYMMDD
    time_ms: int  # milliseconds since midnight UTC
    latitude: float
    longitude: float
    altitude: float
    speed: float
    heading: float
    fix_mode: int  # 0=none, 1=2D, 2=3D
    satellites: int
    epe_2d: float
    epe_3d: float

    def to_datetime(self) -> datetime | None:
        """Convert date and time_ms to datetime object."""
        if self.date == 0:
            return None
        year = self.date // 10000
        month = (self.date // 100) % 100
        day = self.date % 100
        hours = self.time_ms // 3600000
        minutes = (self.time_ms // 60000) % 60
        seconds = (self.time_ms // 1000) % 60
        milliseconds = self.time_ms % 1000
        try:
            return datetime(
                year, month, day, hours, minutes, seconds, milliseconds * 1000, tzinfo=timezone.utc
            )
        except ValueError:
            return None

    def fix_string(self) -> str:
        """Convert fix_mode to GPX fix string."""
        return {0: "none", 1: "2d", 2: "3d"}.get(self.fix_mode, "none")

    def is_valid(self) -> bool:
        """Check if this record has valid position data."""
        return (
            self.fix_mode > 0
            and self.latitude != 0.0
            and self.longitude != 0.0
            and -90 <= self.latitude <= 90
            and -180 <= self.longitude <= 180
        )


def parse_sst_header(f: BinaryIO) -> tuple[int, int]:
    """Parse SST file header. Returns (version, timestamp)."""
    header = f.read(16)
    if len(header) < 16:
        raise ValueError("File too short for SST header")

    magic = header[:3]
    if magic != SST_MAGIC:
        raise ValueError(f"Invalid SST magic: {magic!r}, expected {SST_MAGIC!r}")

    version = header[3]
    if version != SST_VERSION:
        raise ValueError(f"Unsupported SST version: {version}, expected {SST_VERSION}")

    timestamp = struct.unpack("<q", header[8:16])[0]
    return version, timestamp


def parse_gps_chunk(data: bytes) -> list[GpsRecord]:
    """Parse GPS chunk payload into list of GpsRecord."""
    records = []
    offset = 0
    while offset + GPS_RECORD_SIZE <= len(data):
        values = struct.unpack_from(GPS_RECORD_FORMAT, data, offset)
        records.append(
            GpsRecord(
                date=values[0],
                time_ms=values[1],
                latitude=values[2],
                longitude=values[3],
                altitude=values[4],
                speed=values[5],
                heading=values[6],
                fix_mode=values[7],
                satellites=values[8],
                epe_2d=values[9],
                epe_3d=values[10],
            )
        )
        offset += GPS_RECORD_SIZE
    return records


def extract_gps_records(sst_path: Path) -> tuple[list[GpsRecord], int]:
    """Extract all GPS records from SST file. Returns (records, timestamp)."""
    records = []

    with open(sst_path, "rb") as f:
        version, timestamp = parse_sst_header(f)

        while True:
            chunk_header = f.read(3)
            if len(chunk_header) < 3:
                break

            chunk_type = chunk_header[0]
            chunk_length = struct.unpack("<H", chunk_header[1:3])[0]

            if chunk_type == CHUNK_TYPE_GPS:
                payload = f.read(chunk_length)
                if len(payload) < chunk_length:
                    break
                records.extend(parse_gps_chunk(payload))
            else:
                f.seek(chunk_length, 1)

    return records, timestamp


def create_gpx(records: list[GpsRecord], session_timestamp: int) -> Element:
    """Create GPX XML element from GPS records."""
    # Register namespaces to avoid ns0/ns1 prefixes
    from xml.etree.ElementTree import register_namespace

    register_namespace("", NS_GPX)
    register_namespace("gpxtpx", NS_GPXTPX)
    register_namespace("sst", NS_SST)
    register_namespace("xsi", NS_XSI)

    gpx = Element(
        "gpx",
        {
            "version": "1.1",
            "creator": "SST Telemetry",
            "xmlns": NS_GPX,
            "xmlns:gpxtpx": NS_GPXTPX,
            "xmlns:sst": NS_SST,
            "xmlns:xsi": NS_XSI,
            "xsi:schemaLocation": f"{NS_GPX} http://www.topografix.com/GPX/1/1/gpx.xsd",
        },
    )

    # Metadata
    metadata = SubElement(gpx, "metadata")
    session_dt = datetime.fromtimestamp(session_timestamp, tz=timezone.utc)
    SubElement(metadata, "time").text = session_dt.isoformat()
    SubElement(metadata, "desc").text = "GPS track extracted from SST telemetry file"

    # Track
    trk = SubElement(gpx, "trk")
    SubElement(trk, "name").text = f"SST Session {session_dt.strftime('%Y-%m-%d %H:%M')}"
    SubElement(trk, "type").text = "cycling"

    trkseg = SubElement(trk, "trkseg")

    valid_count = 0
    for record in records:
        if not record.is_valid():
            continue

        valid_count += 1
        trkpt = SubElement(
            trkseg,
            "trkpt",
            {"lat": f"{record.latitude:.7f}", "lon": f"{record.longitude:.7f}"},
        )

        # Standard GPX elements
        SubElement(trkpt, "ele").text = f"{record.altitude:.1f}"

        dt = record.to_datetime()
        if dt:
            SubElement(trkpt, "time").text = dt.isoformat()

        SubElement(trkpt, "fix").text = record.fix_string()
        SubElement(trkpt, "sat").text = str(record.satellites)

        # Extensions
        extensions = SubElement(trkpt, "extensions")

        # Garmin TrackPointExtension
        gpxtpx_ext = SubElement(extensions, f"{{{NS_GPXTPX}}}TrackPointExtension")
        SubElement(gpxtpx_ext, f"{{{NS_GPXTPX}}}speed").text = f"{record.speed:.2f}"
        SubElement(gpxtpx_ext, f"{{{NS_GPXTPX}}}course").text = f"{record.heading:.1f}"

        # SST custom extension for EPE values
        sst_ext = SubElement(extensions, f"{{{NS_SST}}}SstExtension")
        SubElement(sst_ext, f"{{{NS_SST}}}epe2d").text = f"{record.epe_2d:.2f}"
        SubElement(sst_ext, f"{{{NS_SST}}}epe3d").text = f"{record.epe_3d:.2f}"

    print(f"Processed {len(records)} GPS records, {valid_count} valid points", file=sys.stderr)
    return gpx


def main():
    parser = argparse.ArgumentParser(
        description="Extract GPS data from SST files and create GPX files"
    )
    parser.add_argument("sst_file", type=Path, help="Input SST file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output GPX file (default: same name with .gpx extension)",
    )
    parser.add_argument(
        "--stdout", action="store_true", help="Write GPX to stdout instead of file"
    )
    args = parser.parse_args()

    if not args.sst_file.exists():
        print(f"Error: SST file not found: {args.sst_file}", file=sys.stderr)
        sys.exit(1)

    records, timestamp = extract_gps_records(args.sst_file)

    if not records:
        print("No GPS records found in SST file", file=sys.stderr)
        sys.exit(1)

    gpx = create_gpx(records, timestamp)
    indent(gpx, space="  ")

    if args.stdout:
        tree = ElementTree(gpx)
        tree.write(sys.stdout.buffer, encoding="utf-8", xml_declaration=True)
        print()
    else:
        output_path = args.output or args.sst_file.with_suffix(".gpx")
        tree = ElementTree(gpx)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        print(f"GPX file written to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
