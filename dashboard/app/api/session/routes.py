import base64
import msgpack
import socket

from io import BytesIO
from http import HTTPStatus as status

from flask import current_app, jsonify, request, send_file
from flask_jwt_extended import jwt_required

from app import id_queue
from app.api.session import bp
from app.extensions import db
from app.models.session import Session
from app.models.session_html import SessionHtml
from app.telemetry.balance import update_balance
from app.telemetry.fft import update_fft
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
            start >= 0 and end < count)


def _update_data(strokes: Strokes, suspension: Suspension, sample_rate: int):
    tick = 1.0 / sample_rate
    fft = update_fft(strokes, suspension.Travel, tick)
    thist = update_travel_histogram(strokes, suspension.TravelBins)
    vhist = update_velocity_histogram(
        strokes,
        suspension.Velocity,
        suspension.TravelBins,
        suspension.VelocityBins
    )
    vbands = update_velocity_band_stats(
        strokes,
        suspension.Velocity,
        350
    )
    return dict(
        fft=fft,
        thist=thist,
        vhist=vhist,
        vbands=vbands,
        balance=None
    )


@bp.route('', methods=['GET'])
def get_all():
    entities = db.session.execute(db.select(Session).order_by(
        Session.timestamp.desc())).scalars()
    return jsonify(list(entities)), status.OK


@bp.route('/<int:id>/psst', methods=['GET'])
def get_psst(id: int):
    entity = db.session.execute(
        db.select(Session).filter_by(id=id)).scalar_one_or_none()
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
    entity = db.session.execute(db.select(Session).order_by(
        Session.timestamp.desc()).limit(1)).scalar_one_or_none()
    if not entity:
        return jsonify(msg="Session does not exist!"), status.NOT_FOUND
    return jsonify(entity), status.OK


@bp.route('/<int:id>', methods=['GET'])
def get(id: int):
    entity = db.session.execute(
        db.select(Session).filter_by(id=id)).scalar_one_or_none()
    if not entity:
        return jsonify(msg="Session does not exist!"), status.NOT_FOUND
    return jsonify(entity), status.OK


@bp.route('/<int:id>/filter', methods=['GET'])
def filter(id: int):
    entity = db.session.execute(
        db.select(Session).filter_by(id=id)).scalar_one_or_none()
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
    if t.Front.Present:
        f_strokes = _filter_strokes(t.Front.Strokes, start, end)
        updated_data['front'] = _update_data(f_strokes, t.Front, t.SampleRate)
    if t.Rear.Present:
        r_strokes = _filter_strokes(t.Rear.Strokes, start, end)
        updated_data['rear'] = _update_data(r_strokes, t.Rear, t.SampleRate)
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


@bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def delete(id: int):
    db.session.execute(db.delete(Session).filter_by(id=id))
    db.session.execute(db.delete(SessionHtml).filter_by(session_id=id))
    db.session.commit()
    return '', status.NO_CONTENT


@bp.route('', methods=['PUT'])
@jwt_required()
def put():
    try:
        data = request.json
        name = bytes(data['name'], 'ascii')
        setup_id = int(data['setup'])
        encoded_sst = data['data']
        sst_data = base64.b64decode(encoded_sst)
    except BaseException:
        return jsonify(msg="Invalid data for Session"), status.BAD_REQUEST

    gosst_server = (current_app.config['GOSST_HOST'],
                    current_app.config['GOSST_PORT'])
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(gosst_server)

    # We don't have a board ID here, so we use the setup ID prefixed with
    # "SETUP_". This is handled in gosst-tcp.
    header = (b'SETUP_' + int.to_bytes(setup_id, 4, 'little') +
              len(sst_data).to_bytes(8, 'little', signed=False) +
              name)
    client_socket.send(header)

    # wait for header response
    response = client_socket.recv(1)[0]
    if response != 4:
        return jsonify(msg="Header was not accepted"), status.BAD_REQUEST

    # send SST data
    client_socket.send(sst_data)
    response = client_socket.recv(1)[0]
    if response != 6:
        return jsonify(msg="Session could not be imported"), status.BAD_REQUEST

    response = client_socket.recv(4)
    id = int.from_bytes(response, 'little')
    client_socket.close()

    if 'desc' in data:
        db.session.execute(db.update(Session).filter_by(id=id).values(
            description=data['desc']
        ))
        db.session.commit()

    return jsonify(id=id), status.CREATED


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


@bp.route('/<int:id>', methods=['PATCH'])
@jwt_required()
def patch(id: int):
    data = request.json
    db.session.execute(db.update(Session).filter_by(id=id).values(
        name=data['name'],
        description=data['desc']
    ))
    db.session.commit()
    return '', status.NO_CONTENT


@bp.route('/<int:id>/bokeh', methods=['PUT'])
def generate_bokeh(id: int):
    s = db.session.execute(
        db.select(Session.id).filter_by(id=id)).scalar_one_or_none()
    if not s:
        return jsonify(msg=f"session #{id} does not exist"), status.BAD_REQUEST

    sh = db.session.execute(
        db.select(SessionHtml).filter_by(session_id=id)).scalar_one_or_none()
    if not sh:
        id_queue.put(id)
        return '', status.NO_CONTENT

    return jsonify(msg=f"already generated (session {id})"), status.BAD_REQUEST
