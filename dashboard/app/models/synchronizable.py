import uuid

from datetime import datetime

from app.extensions import db
from app.telemetry.psst import dataclass_from_dict as dfd


class Synchronizable(object):
    updated = db.Column(db.Integer, server_default=db.func.unixepoch(),
                        onupdate=lambda: int(datetime.now().timestamp()))
    client_updated = db.Column(db.Integer, server_default=db.text('0'))
    deleted = db.Column(db.Integer)

    @classmethod
    def select(cls):
        return db.select(cls).filter(cls.deleted.is_(None))

    @classmethod
    def get_all(cls):
        return db.session.execute(cls.select()).scalars()

    @classmethod
    def get(cls, id: uuid.UUID | str):
        return db.session.execute(
            cls.select().filter_by(id=id)).scalar_one_or_none()

    @classmethod
    def delete(cls, id: uuid.UUID):
        entity = db.session.execute(
            cls.select().filter_by(id=id)).scalar_one_or_none()
        if entity:
            entity.deleted = int(datetime.now().timestamp())
            db.session.commit()

    @classmethod
    def put(cls, json: dict):
        entity = dfd(cls, json)
        print(entity)
        if not entity or (hasattr(entity, 'validate') and not entity.validate()):
            return None
        entity = db.session.merge(entity)
        db.session.commit()
        return entity.id
