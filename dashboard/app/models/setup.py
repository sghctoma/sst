import uuid

from dataclasses import dataclass

from app.extensions import db


@dataclass
class Setup(db.Model):
    id: uuid.UUID = db.Column(db.Uuid(), primary_key=True, default=uuid.uuid4)
    name: str = db.Column(db.String, nullable=False)
    linkage_id: uuid.UUID = db.Column(db.Uuid(), db.ForeignKey('linkage.id'),
                                      nullable=False)
    front_calibration_id: uuid.UUID = db.Column(
        db.Uuid(), db.ForeignKey('calibration.id'))
    rear_calibration_id: uuid.UUID = db.Column(
        db.Uuid(), db.ForeignKey('calibration.id'))
