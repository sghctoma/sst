import uuid

from flask import request
from flask_jwt_extended import jwt_required

from app.api.common import (
    get_entity,
    get_entities,
    delete_entity,
    put_entity)
from app.api.linkage import bp
from app.models.linkage import Linkage


@bp.route('', methods=['GET'])
def get_all():
    return get_entities(Linkage)


@bp.route('/<uuid:id>', methods=['GET'])
def get(id: uuid.UUID):
    return get_entity(Linkage, id)


@bp.route('/<uuid:id>', methods=['DELETE'])
@jwt_required()
def delete(id: uuid.UUID):
    return delete_entity(Linkage, id)


@bp.route('', methods=['PUT'])
@jwt_required()
def put():
    return put_entity(Linkage, request.json)
