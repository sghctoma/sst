import base64
import msgpack
import uuid

from dataclasses import dataclass

from app.extensions import db
from app.models.synchronizable import Synchronizable
from app.telemetry.psst import Telemetry, dataclass_from_dict


@dataclass
class Session(db.Model, Synchronizable):
    id: uuid.UUID = db.Column(db.Uuid(), primary_key=True, default=uuid.uuid4)
    name: str = db.Column(db.String)
    setup: uuid.UUID = db.Column('setup_id', db.Uuid(),
                                 db.ForeignKey('setup.id'))
    description: str = db.Column(db.String)
    timestamp: int = db.Column(db.Integer, nullable=False)
    track: uuid.UUID = db.Column('track_id', db.Uuid(),
                                 db.ForeignKey('track.id'))
    data = db.Column(db.LargeBinary, nullable=False)
    front_springrate: str = db.Column(db.String)
    rear_springrate: str = db.Column(db.String)
    front_hsc: int = db.Column(db.Integer)
    rear_hsc: int = db.Column(db.Integer)
    front_lsc: int = db.Column(db.Integer)
    rear_lsc: int = db.Column(db.Integer)
    front_lsr: int = db.Column(db.Integer)
    rear_lsr: int = db.Column(db.Integer)
    front_hsr: int = db.Column(db.Integer)
    rear_hsr: int = db.Column(db.Integer)

    @property
    def psst_encoded(self) -> str:
        return base64.b64encode(self.data).decode('utf-8')

    # This differs from the psst() setter in that it does not touch any other
    # fields, just sets the raw data directly. Used during synchronization.
    @psst_encoded.setter
    def psst_encoded(self, data: str):
        self.data = base64.b64decode(data)

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
        self.setup_id = uuid.UUID('00000000000000000000000000000000')
