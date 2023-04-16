from dataclasses import dataclass

from app.extensions import db


@dataclass
class Linkage(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String, nullable=False)
    head_angle: float = db.Column(db.Float, nullable=False)
    front_stroke: float = db.Column(db.Float, nullable=False)
    rear_stroke: float = db.Column(db.Float, nullable=False)
    raw_lr_data = db.Column(db.String, nullable=False)
