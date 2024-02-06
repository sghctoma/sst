from datetime import datetime

from app.extensions import db


class Synchronizable(object):
    updated = db.Column(db.Integer, server_default=db.func.unixepoch(),
                        onupdate=lambda: int(datetime.now().timestamp()))
    client_updated = db.Column(db.Integer, server_default=db.text('0'))
    deleted = db.Column(db.Integer)
