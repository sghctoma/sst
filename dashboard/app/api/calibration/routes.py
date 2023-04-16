from http import HTTPStatus as status

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.api.calibration import bp
from app.extensions import db
from app.models.calibration import Calibration
from app.telemetry.psst import dataclass_from_dict


@bp.route('', methods=['GET'])
@jwt_required()
def get():
    entities = db.session.execute(db.select(Calibration)).scalars()
    return jsonify(list(entities)), status.OK


@bp.route('/<string:id>', methods=['GET'])
def get_all(id: str):
    entity = db.session.execute(
        db.select(Calibration).filter_by(id=id)).scalar_one_or_none()
    if not entity:
        return jsonify(msg="Calibration does not exist!"), status.NOT_FOUND
    return jsonify(entity), status.OK


@bp.route('/<string:id>', methods=['DELETE'])
@jwt_required()
def delete(id: str):
    db.session.execute(db.delete(Calibration).filter_by(id=id))
    db.session.commit()
    return '', status.NO_CONTENT


@bp.route('', methods=['PUT'])
@jwt_required()
def put():
    entity = dataclass_from_dict(Calibration, request.json)
    if not entity or not entity.validate():
        return jsonify(msg="Invalid data for Calibration"), status.BAD_REQUEST
    entity = db.session.merge(entity)
    db.session.commit()
    return jsonify(id=entity.id), status.CREATED
