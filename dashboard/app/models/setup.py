from dataclasses import dataclass

from app.extensions import db


@dataclass
class Setup(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String, nullable=False)
    linkage_id: int = db.Column(db.Integer, db.ForeignKey('linkage.id'),
                                nullable=False)
    front_calibration_id: int = db.Column(db.Integer,
                                          db.ForeignKey('calibration.id'))
    rear_calibration_id: int = db.Column(db.Integer,
                                         db.ForeignKey('calibration.id'))
