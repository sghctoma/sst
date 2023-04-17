from dataclasses import dataclass

from app.extensions import db


@dataclass
class SessionHtml(db.Model):
    session_id: int = db.Column(db.Integer, db.ForeignKey('session.id'),
                                primary_key=True)
    script: str = db.Column(db.String, nullable=False)
    travel: str = db.Column(db.String, nullable=False)
    velocity: str = db.Column(db.String, nullable=False)
    map: str = db.Column(db.String, nullable=False)
    lr: str = db.Column(db.String, nullable=False)
    sw: str = db.Column(db.String, nullable=False)
    setup: str = db.Column(db.String, nullable=False)
    desc: str = db.Column(db.String, nullable=False)
    f_thist: str = db.Column(db.String)
    f_fft: str = db.Column(db.String)
    f_vhist: str = db.Column(db.String)
    r_thist: str = db.Column(db.String)
    r_fft: str = db.Column(db.String)
    r_vhist: str = db.Column(db.String)
    cbalance: str = db.Column(db.String)
    rbalance: str = db.Column(db.String)
