import uuid

from datetime import datetime

from flask import jsonify
from http import HTTPStatus as status

from app.extensions import db


def get_entities(klass: type):
    entities = klass.get_all()
    return jsonify(list(entities)), status.OK


def get_entity(klass: type, id: uuid.UUID | str):
    entity = klass.get(id)
    if not entity:
        return jsonify(msg=f"{klass.__name__} does not exist!"), status.NOT_FOUND
    return jsonify(entity), status.OK


def delete_entity(klass: type, id: uuid.UUID | str):
    entity = klass.get(id)
    if entity:
        entity.deleted = int(datetime.now().timestamp())
        db.session.commit()
    return '', status.NO_CONTENT


def put_entity(klass: type, json: dict):
    id = klass.put(json)
    if not id:
        return jsonify(msg=f"Invalid data for {klass.__name__}"), status.BAD_REQUEST
    return jsonify(id=id), status.CREATED
