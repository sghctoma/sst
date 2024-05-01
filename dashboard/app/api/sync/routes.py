from datetime import datetime
from http import HTTPStatus as status

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.api.sync import bp
from app.extensions import db
from app.models.board import Board
from app.models.calibration import CalibrationMethod, Calibration
from app.models.linkage import Linkage
from app.models.session import Session
from app.models.setup import Setup
from app.telemetry.psst import dataclass_from_dict as dfd


def merge(entity: db.Model) -> db.Model:
    klass = type(entity)
    db_entity = db.session.execute(
        db.select(klass).filter_by(id=entity.id)).scalar_one_or_none()

    # insert if not already present
    if not db_entity:
        db.session.add(entity)
        entity.client_updated = entity.updated
        entity.updated = int(datetime.now().timestamp())
        db.session.flush()
        return entity

    if entity.deleted is not None:
        db_entity.deleted = entity.deleted
        db_entity.updated = entity.updated
    else:
        if db_entity.client_updated > entity.updated:
            # some other client updated the row  later and synced earlier. We
            # want the latest update, so discard content in this update, but
            # adjust update timestamp.
            db_entity.updated = int(datetime.now().timestamp())
        else:
            db_entity = db.session.merge(entity)
            db_entity.updated = int(datetime.now().timestamp())
            db_entity.client_updated = entity.updated

    db.session.flush()
    return db_entity


def pull_entities(klass: type, since: int):
    if since is None:
        entities = db.session.execute(db.select(klass)).scalars()
    else:
        was_updated = klass.updated >= since
        was_deleted = db.and_(klass.deleted is not None, klass.deleted > since)
        entities = db.session.execute(db.select(klass).where(
            db.or_(was_updated, was_deleted))).scalars()

    entities_list = []
    for entity in list(entities):
        new_entity = {}
        for k, _ in entity.__annotations__.items():
            new_entity[k] = getattr(entity, k)

        # Normally, we dont want the sync timestamps to present in API answers,
        # so these fields are not annotated in the models. We need them here
        # though, so we are adding them manually.
        new_entity['updated'] = entity.updated
        new_entity['client_updated'] = entity.client_updated
        new_entity['deleted'] = entity.deleted

        # The data field of Sessions is not annotated either, we have to
        # include it manually for non-deleted sessions.
        if klass is Session and entity.deleted is None:
            new_entity['psst_encoded'] = entity.psst_encoded

        entities_list.append(new_entity)

    return entities_list


def push_entities(klass: type, entities_json: list):
    key = klass.__table__.name
    if key in entities_json:
        for entity_dict in entities_json[key]:
            entity = dfd(klass, entity_dict)
            if entity:
                merge(entity)


@bp.route('pull', methods=['GET'])
@jwt_required()
def pull():
    try:
        since = int(request.args.get('since'))
    except BaseException:
        since = None

    with db.session.begin_nested():
        sync_data = {
            Board.__table__.name: pull_entities(Board, since),
            CalibrationMethod.__table__.name: pull_entities(CalibrationMethod,
                                                            since),
            Calibration.__table__.name: pull_entities(Calibration, since),
            Linkage.__table__.name: pull_entities(Linkage, since),
            Setup.__table__.name: pull_entities(Setup, since),
            Session.__table__.name: pull_entities(Session, since)}
    return jsonify(sync_data), status.OK


@bp.route('push', methods=['PUT'])
@jwt_required()
def push():
    entities_json = request.json
    with db.session.begin_nested():
        push_entities(Board, entities_json)
        push_entities(CalibrationMethod, entities_json)
        push_entities(Calibration, entities_json)
        push_entities(Linkage, entities_json)
        push_entities(Setup, entities_json)
        push_entities(Session, entities_json)
        db.session.commit()
    return '', status.NO_CONTENT
