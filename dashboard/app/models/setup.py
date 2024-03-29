import uuid

from dataclasses import dataclass

from app.extensions import db
from app.models.synchronizable import Synchronizable


@dataclass
class Setup(db.Model, Synchronizable):
    id: uuid.UUID = db.Column(db.Uuid(), primary_key=True, default=uuid.uuid4)
    name: str = db.Column(db.String, nullable=False)
    linkage_id: uuid.UUID = db.Column(db.Uuid(), db.ForeignKey('linkage.id'),
                                      nullable=False)
    front_calibration_id: uuid.UUID = db.Column(
        db.Uuid(), db.ForeignKey('calibration.id'))
    rear_calibration_id: uuid.UUID = db.Column(
        db.Uuid(), db.ForeignKey('calibration.id'))

    def validate(self) -> bool:
        return self.linkage_id and (
            self.front_calibration_id or self.rear_calibration_id)
