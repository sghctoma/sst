import uuid

from flask import request
from flask_jwt_extended import jwt_required

from app.api.common import (
    get_entity,
    get_entities,
    delete_entity,
    put_entity)
from app.api.calibration_method import bp
from app.models.calibration import CalibrationMethod


@bp.route('', methods=['GET'])
def get_all():
    return get_entities(CalibrationMethod)


@bp.route('/<uuid:id>', methods=['GET'])
def get(id: uuid.UUID):
    return get_entity(CalibrationMethod, id)


@bp.route('/<uuid:id>', methods=['DELETE'])
@jwt_required()
def delete(id: uuid.UUID):
    return delete_entity(CalibrationMethod, id)


@bp.route('', methods=['PUT'])
@jwt_required()
def put():
    return put_entity(CalibrationMethod, request.json)
