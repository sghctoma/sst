import json
import math
import uuid

from dataclasses import dataclass
from app.extensions import db
from app.utils.expr import ExpressionParser


_std_env = dict(
    pi=math.pi,
    sin=math.sin,
    cos=math.cos,
    tan=math.tan,
    asin=math.asin,
    acos=math.acos,
    atan=math.atan,
    sqrt=math.sqrt,
    sample=0,
    MAX_STROKE=0,
    MAX_TRAVEL=0,
)


@dataclass
class CalibrationMethod(db.Model):
    id: uuid.UUID = db.Column(db.Uuid(), primary_key=True, default=uuid.uuid4)
    name: str = db.Column(db.String, nullable=False)
    description: str = db.Column(db.String)
    properties_raw = db.Column('data', db.String, nullable=False)

    properties: dict

    @property
    def properties(self) -> dict:
        return json.loads(self.properties_raw)

    @properties.setter
    def properties(self, value: dict):
        self.properties_raw = json.dumps(value)

    def validate(self) -> float:
        env = dict(_std_env)
        for input in self.properties['inputs']:
            env[input] = 0
        parser = ExpressionParser(env)
        for k, v in self.properties['intermediates'].items():
            env[k] = parser.validate(v)
        parser = ExpressionParser(env)
        return parser.validate(self.properties['expression'])


@dataclass
class Calibration(db.Model):
    id: uuid.UUID = db.Column(db.Uuid(), primary_key=True, default=uuid.uuid4)
    name: str = db.Column(db.String, nullable=False)
    method_id: uuid.UUID = db.Column(db.Uuid(),
                                     db.ForeignKey('calibration_method.id'),
                                     nullable=False)
    inputs_raw = db.Column('inputs', db.String, nullable=False)

    inputs: dict[str: float]

    @property
    def inputs(self):
        return json.loads(self.inputs_raw)

    @inputs.setter
    def inputs(self, value: dict[str: float]):
        self.inputs_raw = json.dumps(value)

    def validate(self) -> bool:
        cm = db.session.execute(db.select(CalibrationMethod).filter_by(
            id=self.method_id)).scalar_one_or_none()
        if not cm:
            return False
        for k in cm.properties['inputs']:
            if k not in self.inputs:
                return False
        return True
