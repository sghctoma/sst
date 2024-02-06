import uuid

from dataclasses import dataclass


@dataclass
class Linkage:
    Name: str
    HeadAngle: float
    MaxFrontStroke: float
    MaxRearStroke: float
    MaxFrontTravel: float
    MaxRearTravel: float
    LeverageRatio: list[float]
    ShockWheelCoeffs: list[float]


@dataclass
class Calibration:
    Name: str
    MethodId: uuid.UUID
    Inputs: dict[str: float]

    def __post_init__(self):
        self.MethodId = uuid.UUID(self.MethodId)


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
    FineDigitizedVelocity: list[int]


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
    FineVelocityBins: list[float]


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


def _dfd(klass: type, d: dict):
    # source: https://stackoverflow.com/a/54769644
    try:
        annotations = klass.__annotations__
        annotated_fields = {
            f: _dfd(annotations[f], d[f]) for f in annotations if f in d}
        non_annotated_fields = [f for f in d if f not in klass.__annotations__]

        o = klass(**annotated_fields)
        # Set any non annotated fields that are present in the dict. These
        # are set as-is, since we don't have information on their type.
        for f in non_annotated_fields:
            setattr(o, f, d[f])

        return o
    except BaseException:
        if isinstance(d, str) and klass is uuid.UUID:
            d = uuid.UUID(d)
        return d  # Not a dataclass field


def dataclass_from_dict(klass: type, d: dict):
    o = _dfd(klass, d)
    return o if isinstance(o, klass) else None
