import uuid

from dataclasses import dataclass

from app.extensions import db
from app.models.synchronizable import Synchronizable


@dataclass
class Board(db.Model, Synchronizable):
    id: str = db.Column(db.Text, primary_key=True)
    setup_id: uuid.UUID = db.Column(db.Uuid(), db.ForeignKey('setup.id'))
