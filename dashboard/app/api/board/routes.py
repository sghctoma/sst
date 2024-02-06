from flask import request
from flask_jwt_extended import jwt_required

from app.api.common import (
    get_entities,
    delete_entity,
    put_entity)
from app.api.board import bp
from app.models.board import Board


@bp.route('', methods=['GET'])
@jwt_required()
def get_all():
    return get_entities(Board)


@bp.route('/<string:id>', methods=['DELETE'])
@jwt_required()
def delete(id: str):
    return delete_entity(Board, id)


@bp.route('', methods=['PUT'])
@jwt_required()
def put():
    return put_entity(Board, request.json)
