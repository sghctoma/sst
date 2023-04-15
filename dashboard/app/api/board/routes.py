from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.api.board import bp
from app.extensions import db
from app.models.board import Board


@bp.route('', methods=['GET'])
@jwt_required()
def get():
    entities = db.session.execute(db.select(Board)).scalars()
    return jsonify(list(entities)), 200


@bp.route('/<string:id>', methods=['GET'])
def get_all(id: str):
    entity = db.session.execute(
        db.select(Board).filter_by(id=id)).scalar_one_or_none()
    if not entity:
        return jsonify(msg="Board does not exist!"), 404
    return jsonify(entity), 200


@bp.route('/<string:id>', methods=['DELETE'])
@jwt_required()
def delete(id: str):
    db.session.execute(db.delete(Board).filter_by(id=id))
    db.session.commit()
    return '', 204


@bp.route('/<string:id>', methods=['PATCH'])
@jwt_required()
def patch(id: str):
    data = request.json
    db.session.execute(db.update(Board).filter_by(id=id).values(
        # XXX
    ))
    db.session.commit()
    return '', 204


@bp.route('', methods=['PUT'])
@jwt_required()
def put():
    data = request.json
    print(data)
    db.session.commit()
    return '', 201
