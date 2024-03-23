import json
import uuid

from dataclasses import dataclass

from app.extensions import db
from app.models.synchronizable import Synchronizable


@dataclass
class Track(db.Model, Synchronizable):
    id: uuid.UUID = db.Column(db.Uuid(), primary_key=True, default=uuid.uuid4)
    track: str = db.Column(db.String, nullable=False)

    def validate(self) -> bool:
        try:
            track = json.loads(self.track)
            data = [
                track['lat'],
                track['lon'],
                track['ele'],
                track['time']
            ]
        except BaseException:
            return False
        return len(set(map(len, data))) == 1 and len(data[0]) >= 1
