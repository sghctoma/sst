import base64
import msgpack

from dataclasses import dataclass

from app.extensions import db
from app.telemetry.psst import Telemetry, dataclass_from_dict


@dataclass
class Session(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String)
    setup: int = db.Column('setup_id', db.Integer, db.ForeignKey('setup.id'))
    description: str = db.Column(db.String)
    timestamp: int = db.Column(db.Integer, nullable=False)
    track: int = db.Column('track_id', db.Integer, db.ForeignKey('track.id'))
    data = db.Column(db.LargeBinary, nullable=False)

    @property
    def psst(self) -> bytes:
        return self.data

    @psst.setter
    def psst(self, data: str):
        psst_data = base64.b64decode(data)
        psst_dict = msgpack.unpackb(psst_data,
                                    strict_map_key=True)
        telemetry = dataclass_from_dict(Telemetry, psst_dict)
        self.data = psst_data
        self.timestamp = telemetry.Timestamp
        self.setup_id = -1
