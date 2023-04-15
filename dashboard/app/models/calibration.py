from dataclasses import dataclass
from app.extensions import db


@dataclass
class CalibrationMethod(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String, nullable=False)
    description: str = db.Column(db.String)
    data: str = db.Column(db.String, nullable=False)


@dataclass
class Calibration(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String, nullable=False)
    method_id: int = db.Column(db.Integer,
                               db.ForeignKey('calibration_method.id'),
                               nullable=False)
    inputs: str = db.Column(db.String, nullable=False)
