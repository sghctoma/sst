from dataclasses import dataclass

from app.extensions import db


@dataclass
class Board(db.Model):
    id: int = db.Column(db.Text, primary_key=True)
    setup_id: int = db.Column(db.Integer, db.ForeignKey('setup.id'))
