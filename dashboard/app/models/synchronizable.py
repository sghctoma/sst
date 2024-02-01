from app.extensions import db


class Synchronizable(object):
    updated = db.Column(db.Integer, server_default=db.func.unixepoch())
    client_updated = db.Column(db.Integer)
    deleted = db.Column(db.Integer)
