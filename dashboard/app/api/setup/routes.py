from http import HTTPStatus as status

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.api.setup import bp
from app.extensions import db
from app.models.board import Board
from app.models.calibration import Calibration
from app.models.linkage import Linkage
from app.models.setup import Setup
from app.telemetry.psst import dataclass_from_dict as dfd


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
    entity = dfd(Setup, request.json)
    if not entity:
        return jsonify(msg="Invalid data for Setup"), status.BAD_REQUEST
    entity = db.session.merge(entity)
    db.session.commit()
    return jsonify(id=entity.id), status.CREATED


@bp.route('/combined', methods=['PUT'])
@jwt_required()
def put_combined():
    lnk = request.json['linkage']
    if type(lnk) == int:
        linkage = db.session.execute(
            db.select(Linkage).filter_by(id=lnk)).scalar_one_or_none()
    else:
        linkage = dfd(Linkage, request.json['linkage'])
        if not linkage.validate():
            linkage = None
    if not linkage:
        return jsonify(msg="Invalid data for linkage!"), status.BAD_REQUEST

    front_calibration = (dfd(Calibration, request.json['front_calibration'])
                         if 'front_calibration' in request.json else None)
    if front_calibration and not front_calibration.validate():
        return jsonify(msg="Invalid data for calibration!"), status.BAD_REQUEST

    rear_calibration = (dfd(Calibration, request.json['rear_calibration'])
                        if 'rear_calibration' in request.json else None)
    if rear_calibration and not rear_calibration.validate():
        return jsonify(msg="Invalid data for calibration!"), status.BAD_REQUEST

    board = (dfd(Board, request.json['board'])
             if 'board' in request.json else None)

    if not front_calibration and not rear_calibration:
        return jsonify(msg="No calibration given"), status.BAD_REQUEST

    if not linkage:
        return jsonify(msg="Missing or invalid linkage"), status.BAD_REQUEST

    setup = Setup(
        name=request.json['name'],
    )
    try:
        with db.session.begin_nested():
            linkage = db.session.merge(linkage)
            db.session.flush()
            setup.linkage_id = linkage.id
            if front_calibration:
                front_calibration = db.session.merge(front_calibration)
                db.session.flush()
                setup.front_calibration_id = front_calibration.id
            if rear_calibration:
                rear_calibration = db.session.merge(rear_calibration)
                db.session.flush()
                setup.rear_calibration_id = rear_calibration.id
            setup = db.session.merge(setup)
            db.session.flush()
            if board:
                board.setup_id = setup.id
                db.session.merge(board)
                db.session.flush()
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return (jsonify(msg=f"Transaction failed: {e}"),
                status.INTERNAL_SERVER_ERROR)

    return jsonify(id=setup.id), status.CREATED
