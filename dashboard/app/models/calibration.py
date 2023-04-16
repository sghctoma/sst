import json

from dataclasses import dataclass
from app.extensions import db


@dataclass
class CalibrationMethod(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
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


@dataclass
class Calibration(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String, nullable=False)
    method_id: int = db.Column(db.Integer,
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

    def validate() -> bool:
        return True
