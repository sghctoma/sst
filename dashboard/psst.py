from dataclasses import dataclass, fields as datafields


@dataclass
class Digitized:
    Data: list
    Bins: list

@dataclass
class Frame:
    WheelLeverageRatio: list
    CoeffsShockWheel: list
    MaxRearTravel: float

@dataclass
class Calibration:
    ArmLength: float
    MaxDistance: float
    MaxStroke: float
    StartAngle: float

@dataclass
class Suspension:
    Calibration: Calibration
    Travel: list
    Velocity: list
    DigitizedTravel: Digitized
    DigitizedVelocity: Digitized

@dataclass
class Telemetry:
    Name: str
    Version: int
    SampleRate: int
    Front: Suspension
    Rear: Suspension
    Frame: Frame

# source: https://stackoverflow.com/a/54769644
def dataclass_from_dict(klass, d):
    try:
        fieldtypes = {f.name:f.type for f in datafields(klass)}
        return klass(**{f:dataclass_from_dict(fieldtypes[f],d[f]) for f in d})
    except:
        return d # Not a dataclass field
