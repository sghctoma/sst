from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.api.linkage import bp
from app.extensions import db
from app.models.linkage import Linkage


@bp.route('', methods=['GET'])
def get():
    sessions = db.session.execute(db.select(Linkage)).scalars()
    return jsonify(list(sessions)), 200


@bp.route('/<int:id>', methods=['GET'])
def get_all(id: int):
    session = db.session.execute(
        db.select(Linkage).filter_by(id=id)).scalar_one_or_none()
    if not session:
        return jsonify(msg="Session does not exist!"), 404
    return jsonify(session), 200


@bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def delete(id: int):
    db.session.execute(db.delete(Linkage).filter_by(id=id))
    db.session.commit()
    return '', 204


@bp.route('/<int:id>', methods=['PATCH'])
@jwt_required()
def patch(id: int):
    data = request.json
    db.session.execute(db.update(Linkage).filter_by(id=id).values(
        name=data['name'],
        description=data['desc']
    ))
    db.session.commit()
    return '', 204


@bp.route('', methods=['PUT'])
@jwt_required()
def put(id: int):
    data = request.json
    print(data)
    db.session.commit()
    return '', 201
