from dataclasses import dataclass

from app.extensions import db


@dataclass
class Track(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    track: str = db.Column(db.String, nullable=False)
