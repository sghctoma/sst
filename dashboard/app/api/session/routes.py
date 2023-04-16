from http import HTTPStatus as status

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.api.session import bp
from app.extensions import db
from app.models.session import Session
from app.models.session_html import SessionHtml
from app.telemetry.psst import dataclass_from_dict


@bp.route('', methods=['GET'])
@jwt_required()
def get():
    entities = db.session.execute(db.select(Session)).scalars()
    return jsonify(list(entities)), status.OK


@bp.route('/<string:id>', methods=['GET'])
def get_all(id: str):
    entity = db.session.execute(
        db.select(Session).filter_by(id=id)).scalar_one_or_none()
    if not entity:
        return jsonify(msg="Session does not exist!"), status.NOT_FOUND
    return jsonify(entity), status.OK


@bp.route('/<string:id>', methods=['DELETE'])
@jwt_required()
def delete(id: str):
    db.session.execute(db.delete(Session).filter_by(id=id))
    db.session.execute(db.delete(SessionHtml).filter_by(id=id))
    db.session.commit()
    return '', status.NO_CONTENT


@bp.route('', methods=['PUT'])
@jwt_required()
def put():
    entity = dataclass_from_dict(Session, request.json)
    if not entity:
        return jsonify(msg="Invalid data for Session"), status.BAD_REQUEST
    db.session.merge(entity)
    db.session.commit()
    return '', status.CREATED


@bp.route('/<int:id>', methods=['PATCH'])
@jwt_required()
def patch(id: int):
    data = request.json
    db.session.execute(db.update(Session).filter_by(id=id).values(
        name=data['name'],
        description=data['desc']
    ))
    db.session.commit()
    return '', 204
