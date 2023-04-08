package sst

import (
	"bytes"
	"encoding/binary"

	psst "gosst/internal/formats/psst"
)

type header struct {
	Magic      [3]byte
	Version    uint8
	SampleRate uint16
	Padding    uint16
	Timestamp  int64
}

type record struct {
	ForkAngle  uint16
	ShockAngle uint16
}

type sst_record struct {
	ForkAngle  uint16
	ShockAngle uint16
}

type NotSSTError struct{}

func (e *NotSSTError) Error() string {
	return "Data is not SST format"
}

func ProcessRaw(sst_data []byte) (front, rear []uint16, meta psst.Meta, err error) {
	f := bytes.NewReader(sst_data)
	headers := make([]header, 1)
	err = binary.Read(f, binary.LittleEndian, &headers)
	if err != nil {
		return
	}
	fileHeader := headers[0]

	if string(fileHeader.Magic[:]) == "SST" {
		meta.Version = fileHeader.Version
		meta.SampleRate = fileHeader.SampleRate
		meta.Timestamp = fileHeader.Timestamp
	} else {
		err = &NotSSTError{}
		return
	}

	records := make([]record, (len(sst_data)-16 /* sizeof(header) */)/4 /* sizeof(record) */)
	err = binary.Read(f, binary.LittleEndian, &records)
	if err != nil {
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
			if r.ForkAngle > 0x0050 {
				frontError = r.ForkAngle
			}
			break
		}
	}
	rearError = 0
	rearBaseline = records[0].ShockAngle
	for _, r := range records[1:] {
		if r.ShockAngle > rearBaseline {
			if r.ShockAngle > 0x0050 {
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