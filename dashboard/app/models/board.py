import uuid

from dataclasses import dataclass

from app.extensions import db


@dataclass
class Board(db.Model):
    id: str = db.Column(db.Text, primary_key=True)
    setup_id: uuid.UUID = db.Column(db.Uuid(), db.ForeignKey('setup.id'))
