package sst

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"io"

	psst "gosst/formats/psst"
)

const (
	ChunkTypeRates     = 0x00
	ChunkTypeTelemetry = 0x01
	ChunkTypeMarker    = 0x02
)

type header struct {
	Magic     [3]byte
	Version   uint8
	Padding   uint32
	Timestamp int64
}

type chunkHeader struct {
	Type   uint8
	Length uint16
}

type rateEntry struct {
	Type uint8
	Rate uint16
}

type record struct {
	ForkAngle  uint16
	ShockAngle uint16
}

type NotSSTError struct{}

func (e *NotSSTError) Error() string {
	return "Data is not SST format"
}

type VersionError struct {
	Version uint8
}

func (e *VersionError) Error() string {
	return fmt.Sprintf("Unsupported SST version: %d", e.Version)
}

func ProcessRaw(sst_data []byte) (front, rear []uint16, markers []float64, meta psst.Meta, err error) {
	f := bytes.NewReader(sst_data)
	var fileHeader header
	err = binary.Read(f, binary.LittleEndian, &fileHeader)
	if err != nil {
		return
	}

	if string(fileHeader.Magic[:]) != "SST" {
		err = &NotSSTError{}
		return
	}

	if fileHeader.Version != 4 {
		err = &VersionError{Version: fileHeader.Version}
		return
	}

	meta.Version = fileHeader.Version
	meta.Timestamp = fileHeader.Timestamp
	meta.Name = "SST Session"

	var records []record
	var totalTelemetrySamples int

	for {
		var ch chunkHeader
		err = binary.Read(f, binary.LittleEndian, &ch)
		if err == io.EOF {
			err = nil
			break
		}
		if err != nil {
			return
		}

		switch ch.Type {
		case ChunkTypeRates:
			numEntries := int(ch.Length) / 3
			for i := 0; i < numEntries; i++ {
				var re rateEntry
				if err = binary.Read(f, binary.LittleEndian, &re); err != nil {
					return
				}
				if re.Type == ChunkTypeTelemetry {
					meta.TelemetrySampleRate = re.Rate
				}
			}
		case ChunkTypeTelemetry:
			numSamples := int(ch.Length) / 4
			chunkRecords := make([]record, numSamples)
			if err = binary.Read(f, binary.LittleEndian, &chunkRecords); err != nil {
				return
			}
			records = append(records, chunkRecords...)
			totalTelemetrySamples += numSamples
		case ChunkTypeMarker:
			if meta.TelemetrySampleRate > 0 {
				markers = append(markers, float64(totalTelemetrySamples)/float64(meta.TelemetrySampleRate))
			}
		default:
			// Skip unknown chunk
			if _, err = f.Seek(int64(ch.Length), io.SeekCurrent); err != nil {
				return
			}
		}
	}

	if len(records) == 0 {
		return
	}

	var hasFront = records[0].ForkAngle != 0xffff
	var hasRear = records[0].ShockAngle != 0xffff

	// Rudimentary attempt to fix datasets where the sensor jumps to an unreasonably
	// large number after a few tenth of seconds, but measures everything correctly
	// from that baseline.
	var frontError, rearError uint16
	var frontBaseline, rearBaseline uint16
	frontError = 0
	frontBaseline = records[0].ForkAngle
	for _, r := range records[1:] {
		if r.ForkAngle > frontBaseline {
			if r.ForkAngle-frontBaseline > 0x0050 {
				frontError = r.ForkAngle
			}
			break
		}
	}
	rearError = 0
	rearBaseline = records[0].ShockAngle
	for _, r := range records[1:] {
		if r.ShockAngle > rearBaseline {
			if r.ShockAngle-rearBaseline > 0x0050 {
				rearError = r.ShockAngle
			}
			break
		}
	}

	for idx := range records {
		if hasFront {
			front = append(front, records[idx].ForkAngle-frontError)
		}
		if hasRear {
			rear = append(rear, records[idx].ShockAngle-rearError)
		}
	}

	return
}
