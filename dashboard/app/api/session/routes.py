import json
import msgpack
import requests
import uuid

from io import BytesIO
from http import HTTPStatus as status

from flask import current_app, jsonify, request, send_file
from flask_jwt_extended import (
    jwt_required,
    verify_jwt_in_request,
    unset_jwt_cookies
)
from markupsafe import Markup

from app import id_queue
from app.api.common import (
    get_entity,
    delete_entity)
from app.api.session import bp
from app.extensions import db
from app.models.session import Session
from app.models.session_html import SessionHtml
from app.models.track import Track
from app.telemetry.balance import update_balance
from app.telemetry.fft import update_fft
from app.telemetry.map import gpx_to_dict, track_data
from app.telemetry.psst import (
    Suspension,
    Strokes,
    Telemetry,
    dataclass_from_dict
)
from app.telemetry.travel import update_travel_histogram
from app.telemetry.velocity import (
    update_velocity_band_stats,
    update_velocity_histogram
)


def _filter_strokes(strokes: Strokes, start: int, end: int) -> Strokes:
    if start is None or end is None:
        return strokes
    return Strokes(
        Compressions=[c for c in strokes.Compressions if
                      c.Start > start and c.End < end],
        Rebounds=[r for r in strokes.Rebounds if
                  r.Start > start and r.End < end])


def _extract_range(sample_rate: int) -> (int, int):
    try:
        start = request.args.get('start')
        start = int(float(start) * sample_rate)
    except BaseException:
        start = None
    try:
        end = request.args.get('end')
        end = int(float(end) * sample_rate)
    except BaseException:
        end = None
    return start, end


def _validate_range(start: int, end: int, count: int) -> bool:
    return (start is not None and end is not None and
            start >= 0 and end < count and start < end)


def _update_stroke_based(strokes: Strokes, suspension: Suspension):
    thist = update_travel_histogram(strokes, suspension.TravelBins)
    vhist = update_velocity_histogram(
        strokes,
        suspension.Velocity,
        suspension.TravelBins,
        suspension.VelocityBins,
        suspension.FineVelocityBins,
        200
    )
    vbands = update_velocity_band_stats(
        strokes,
        suspension.Velocity,
        200
    )
    return dict(
        thist=thist,
        vhist=vhist,
        vbands=vbands,
        balance=None
    )


@bp.route('', methods=['GET'])
def get_all():
    entities = db.session.execute(Session.select().order_by(
        Session.timestamp.desc())).scalars()
    return jsonify(list(entities)), status.OK


@bp.route('/<uuid:id>/psst', methods=['GET'])
def get_psst(id: uuid.UUID):
    entity = Session.get(id)
    if not entity:
        return jsonify(msg="Session does not exist!"), status.NOT_FOUND
    data = BytesIO(entity.data)
    return send_file(
        data,
        as_attachment=True,
        download_name=f"{entity.name}.psst",
        mimetype="application/octet-stream",
    )


@bp.route('/last', methods=['GET'])
def get_last():
    entity = db.session.execute(Session.select().order_by(
        Session.timestamp.desc()).limit(1)).scalar_one_or_none()
    if not entity:
        return jsonify(msg="Session does not exist!"), status.NOT_FOUND
    return jsonify(entity), status.OK


@bp.route('/<uuid:id>', methods=['GET'])
def get(id: uuid.UUID):
    return get_entity(Session, id)


@bp.route('/<uuid:id>/filter', methods=['GET'])
def filter(id: uuid.UUID):
    entity = Session.get(id)
    if not entity:
        return jsonify(msg="Session does not exist!"), status.NOT_FOUND
    d = msgpack.unpackb(entity.data)
    t = dataclass_from_dict(Telemetry, d)

    start, end = _extract_range(t.SampleRate)
    count = len(t.Front.Travel if t.Front.Present else t.Rear.Travel)
    if not _validate_range(start, end, count):
        start = None
        end = None

    updated_data = {'front': None, 'rear': None}
    tick = 1.0 / t.SampleRate
    if t.Front.Present:
        f_strokes = _filter_strokes(t.Front.Strokes, start, end)
        updated_data['front'] = _update_stroke_based(f_strokes, t.Front)
        updated_data['front']['fft'] = update_fft(
            t.Front.Travel[start:end], tick)
    if t.Rear.Present:
        r_strokes = _filter_strokes(t.Rear.Strokes, start, end)
        updated_data['rear'] = _update_stroke_based(r_strokes, t.Rear)
        updated_data['rear']['fft'] = update_fft(
            t.Rear.Travel[start:end], tick)
    if t.Front.Present and t.Rear.Present:
        updated_data['balance'] = dict(
            compression=update_balance(
                f_strokes.Compressions,
                r_strokes.Compressions,
                t.Linkage.MaxFrontTravel,
                t.Linkage.MaxRearTravel
            ),
            rebound=update_balance(
                f_strokes.Rebounds,
                r_strokes.Rebounds,
                t.Linkage.MaxFrontTravel,
                t.Linkage.MaxRearTravel
            ),
        )

    return jsonify(updated_data)


@bp.route('/<uuid:id>', methods=['DELETE'])
@jwt_required()
def delete(id: uuid.UUID):
    delete_entity(Session, id)
    db.session.execute(db.delete(SessionHtml).filter_by(session_id=id))
    db.session.commit()
    return '', status.NO_CONTENT


@bp.route('', methods=['PUT'])
@jwt_required()
def put():
    api_server = current_app.config['GOSST_HTTP_API']
    url = f'{api_server}/api/internal/session'
    resp = requests.put(url, json=request.json)
    if resp.status_code == status.CREATED:
        return jsonify(id=resp.json()['id']), status.CREATED
    else:
        return jsonify(msg="Session could not be imported"), status.BAD_REQUEST


@bp.route('/normalized', methods=['PUT'])
@jwt_required()
def put_normalized():
    api_server = current_app.config['GOSST_HTTP_API']
    url = f'{api_server}/api/internal/session/normalized'
    resp = requests.put(url, json=request.json)
    if resp.status_code == status.CREATED:
        return jsonify(id=resp.json()['id']), status.CREATED
    else:
        return jsonify(msg="Session could not be imported"), status.BAD_REQUEST


@bp.route('/psst', methods=['PUT'])
@jwt_required()
def put_processed():
    session_dict = request.json
    session_data = session_dict.pop('data')
    entity = dataclass_from_dict(Session, session_dict)
    if not entity:
        return jsonify(msg="Invalid data for Session"), status.BAD_REQUEST
    entity.psst = session_data
    entity = db.session.merge(entity)
    db.session.commit()
    generate_bokeh(entity.id)
    return jsonify(id=entity.id), status.CREATED


@bp.route('/<uuid:id>', methods=['PATCH'])
@jwt_required()
def patch(id: uuid.UUID):
    data = request.json
    db.session.execute(db.update(Session).filter_by(id=id).values(
        name=data['name'],
        description=data['desc']
    ))
    db.session.commit()
    return '', status.NO_CONTENT


@bp.route('/<uuid:id>/bokeh', methods=['PUT'])
def generate_bokeh(id: uuid.UUID):
    s = Session.get(id)
    if not s:
        return jsonify(msg=f"session #{id} does not exist"), status.BAD_REQUEST

    sh = db.session.execute(
        db.select(SessionHtml).filter_by(session_id=id)).scalar_one_or_none()
    if not sh:
        id_queue.put(id)
        return '', status.NO_CONTENT

    return jsonify(msg=f"already generated (session {id})"), status.BAD_REQUEST


@bp.route('/last/bokeh', methods=['GET'], defaults={'session_id': None})
@bp.route('/<uuid:session_id>/bokeh', methods=['GET'])
def session_html(session_id: uuid.UUID):
    # Not using @jwt_required(optional=True), because we want to be able to
    # load the dashboard even with an invalid token.
    try:
        verify_jwt_in_request()
        full_access = True
    except BaseException:
        full_access = False

    if not session_id:
        session = db.session.execute(Session.select().order_by(
            Session.timestamp.desc()).limit(1)).scalar_one_or_none()
    else:
        session = Session.get(session_id)
    if not session:
        return jsonify(), status.NOT_FOUND

    session_html = db.session.execute(db.select(SessionHtml).filter_by(
        session_id=session.id)).scalar_one_or_none()
    if not session_html:
        return jsonify(), status.NOT_FOUND
    components_script = Markup(session_html.script.replace(
        '<script type="text/javascript">', '').replace('</script>', ''))
    components_divs = [Markup(d) if d else None for d in session_html.divs]

    track = Track.get(session.track)

    d = msgpack.unpackb(session.data)
    t = dataclass_from_dict(Telemetry, d)

    suspension_count = 0
    if t.Front.Present:
        suspension_count += 1
    if t.Rear.Present:
        suspension_count += 1

    record_num = len(t.Front.Travel) if t.Front.Present else len(t.Rear.Travel)
    elapsed_time = record_num / t.SampleRate
    start_time = session.timestamp
    end_time = start_time + elapsed_time
    full_track, session_track = track_data(track.track if track else None,
                                           start_time, end_time)

    response = jsonify(
        id=session.id,
        name=session.name,
        description=session.description,
        start_time=session.timestamp,
        end_time=end_time,
        suspension_count=suspension_count,
        full_track=full_track,
        session_track=session_track,
        script=components_script,
        divs=components_divs,
        full_access=full_access,
    )
    if not full_access:
        unset_jwt_cookies(response)
    return response


@bp.route('/<uuid:id>/gpx', methods=['PUT'])
@jwt_required()
def upload_gpx(id: uuid.UUID):
    session = Session.get(id)
    if not session:
        return jsonify(msg="Session does not exist!"), status.NOT_FOUND

    d = msgpack.unpackb(session.data)
    t = dataclass_from_dict(Telemetry, d)
    record_num = len(t.Front.Travel) if t.Front.Present else len(t.Rear.Travel)
    elapsed_time = record_num / t.SampleRate
    start_time = session.timestamp
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
