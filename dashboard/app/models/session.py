from dataclasses import dataclass

from app.extensions import db


@dataclass
class Session(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String)
    setup_id: str = db.Column(db.Integer, db.ForeignKey('setup.id'),
                              nullable=False)
    description: str = db.Column(db.String)
    timestamp: int = db.Column(db.Integer, nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    track_id: int = db.Column(db.Integer, db.ForeignKey('track.id'))
