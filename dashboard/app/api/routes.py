import json
import msgpack

from http import HTTPStatus as status

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.api import bp
from app.models.session import Session
from app.models.track import Track
from app.telemetry.map import gpx_to_dict, track_data
from app.telemetry.psst import Telemetry, dataclass_from_dict


@bp.route('/gpx/<int:id>', methods=['PUT'])
@jwt_required()
def upload_gpx(id: int):
    session = db.session.execute(
        db.select(Session).filter_by(id=id)).scalar_one_or_none()
    if not session:
        return jsonify(msg="Session does not exist!"), status.NOT_FOUND

    d = msgpack.unpackb(session.data)
    t = dataclass_from_dict(Telemetry, d)
    record_num = len(t.Front.Travel) if t.Front.Present else len(t.Rear.Travel)
    elapsed_time = record_num / t.SampleRate
    start_time = t.Timestamp
    end_time = start_time + elapsed_time

    track_dict = gpx_to_dict(request.data)
    ts, tf = track_dict['time'][0], track_dict['time'][-1]
    full_track, session_track = track_data(track_dict, start_time, end_time)
    if session_track is None:
        return jsonify(msg="Track is not applicable!"), status.BAD_REQUEST

    new_track = Track(track=json.dumps(track_dict))
    db.session.add(new_track)
    db.session.commit()

    s1 = db.aliased(Session)
    s2 = db.aliased(Session)

    stmt_select = (
        db.session.query(s2.id)
        .select_from(s1)
        .join(s2, s1.setup == s2.setup)
        .filter(s1.id == id)
        .filter(s2.timestamp >= ts)
        .filter(s2.timestamp <= tf)
    )
    stmt_update = (
        db.update(Session)
        .filter(Session.id.in_(stmt_select))
        .values(track=new_track.id)
    )
    db.session.execute(stmt_update)
    db.session.commit()

    data = dict(full_track=full_track, session_track=session_track)
    return jsonify(data), 200
