from dataclasses import dataclass, fields as datafields


@dataclass
class Linkage:
    Name: str
    HeadAngle: float
    LeverageRatio: list[float]
    ShockWheelCoeffs: list[float]
    MaxFrontTravel: float
    MaxRearTravel: float


@dataclass
class Calibration:
    Name: str
    ArmLength: float
    MaxDistance: float
    MaxStroke: float
    StartAngle: float


@dataclass
class StrokeStat:
    SumTravel: float
    MaxTravel: float
    SumVelocity: float
    MaxVelocity: float
    Bottomouts: int
    Count: int


@dataclass
class Stroke:
    Start: int
    End: int
    Stat: StrokeStat
    DigitizedTravel: list[int]
    DigitizedVelocity: list[int]


@dataclass
class Strokes:
    Compressions: list[Stroke]
    Rebounds: list[Stroke]

    def __post_init__(self):
        self.Compressions = [dataclass_from_dict(Stroke, d) for d in self.Compressions]
        self.Rebounds = [dataclass_from_dict(Stroke, d) for d in self.Rebounds]


@dataclass
class Airtime:
    Start: float
    End: float


@dataclass
class Suspension:
    Present: bool
    Calibration: Calibration
    Travel: list[float]
    Velocity: list[float]
    Strokes: Strokes
    TravelBins: list[float]
    VelocityBins: list[float]


@dataclass
class Telemetry:
    Name: str
    Version: int
    SampleRate: int
    Timestamp: int
    Front: Suspension
    Rear: Suspension
    Linkage: Linkage
    Airtimes: list[Airtime]

    def __post_init__(self):
        self.Airtimes = [dataclass_from_dict(Airtime, d) for d in self.Airtimes]


def dataclass_from_dict(klass: type, d: dict):
    # source: https://stackoverflow.com/a/54769644
    try:
        fieldtypes = {f.name: f.type for f in datafields(klass)}
        return klass(
            **{f: dataclass_from_dict(fieldtypes[f], d[f]) for f in d})
    except BaseException:
        return d  # Not a dataclass field
