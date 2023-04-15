from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.api.session import bp
from app.extensions import db
from app.models.session import Session
from app.models.session_html import SessionHtml


@bp.route('', methods=['GET'])
def get():
    entity = db.session.execute(db.select(Session)).scalars()
    return jsonify(list(entity)), 200


@bp.route('/<int:id>', methods=['GET'])
def get_all(id: int):
    entity = db.session.execute(
        db.select(Session).filter_by(id=id)).scalar_one_or_none()
    if not entity:
        return jsonify(msg="Session does not exist!"), 404
    return jsonify(entity), 200


@bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def delete(id: int):
    db.session.execute(db.delete(Session).filter_by(id=id))
    db.session.execute(db.delete(SessionHtml).filter_by(session_id=id))
    db.session.commit()
    return '', 204


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


@bp.route('', methods=['PUT'])
@jwt_required()
def put():
    data = request.json
    print(data)
    db.session.commit()
    return '', 201
