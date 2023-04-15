import json
import msgpack

from flask import (
    jsonify,
    render_template,
    request
)
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.api import bp
from app.models.board import Board
from app.models.calibration import Calibration, CalibrationMethod
from app.models.linkage import Linkage
from app.models.session import Session
from app.models.session_html import SessionHtml
from app.models.setup import Setup
from app.models.track import Track

from app.telemetry.map import gpx_to_dict, track_data
from app.telemetry.psst import Telemetry, dataclass_from_dict


@bp.route('/gpx/<int:id>', methods=['PUT'])
@jwt_required()
def upload_gpx(int: id):
    session = db.session.execute(
        db.select(Session).filter_by(id=id)).scalar_one_or_none()
    if not session:
        return jsonify(msg="Session does not exist!"), 404

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
        return jsonify(msg="Track is not applicable!"), 400

    new_track = Track(track=json.dumps(track_dict))
    db.session.add(new_track)
    db.session.commit()

    s1 = db.aliased(Session)
    s2 = db.aliased(Session)

    stmt_select = (
        db.select(s2.id)
        .join(s2, s1.setup_id == s2.setup_id)
        .filter(s1.id == id)
        .filter(s2.timestamp >= ts)
        .filter(s2.timestamp <= tf)
    )
    stmt_update = (
        db.select(Session)
        .filter(Session.id.in_(stmt_select))
        .update({"track_id": new_track.id}, synchronize_session=False)
    )
    db.session.execute(stmt_update)
    db.session.commit()

    data = dict(full_track=full_track, session_track=session_track)
    return jsonify(data), 200
