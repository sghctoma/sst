from http import HTTPStatus as status

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.api.setup import bp
from app.extensions import db
from app.models.setup import Setup
from app.telemetry.psst import dataclass_from_dict


@bp.route('', methods=['GET'])
def get_all():
    entities = db.session.execute(db.select(Setup)).scalars()
    return jsonify(list(entities)), status.OK


@bp.route('/<int:id>', methods=['GET'])
def get(id: int):
    entity = db.session.execute(
        db.select(Setup).filter_by(id=id)).scalar_one_or_none()
    if not entity:
        return jsonify(msg="Session does not exist!"), status.NOT_FOUND
    return jsonify(entity), status.OK


@bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def delete(id: int):
    db.session.execute(db.delete(Setup).filter_by(id=id))
    db.session.commit()
    return '', status.NO_CONTENT


@bp.route('', methods=['PUT'])
@jwt_required()
def put():
    entity = dataclass_from_dict(Setup, request.json)
    if not entity:
        return jsonify(msg="Invalid data for Setup"), status.BAD_REQUEST
    entity = db.session.merge(entity)
    db.session.commit()
    return jsonify(id=entity.id), status.CREATED
