#!/usr/bin/env python3

import argparse
import json
import msgpack
import pytz

from datetime import datetime
from flask import Flask, jsonify, request, session
from flask_session import Session
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import create_engine

from bokeh.palettes import Spectral11
from bokeh.resources import CDN
from bokeh.themes import built_in_themes, DARK_MINIMAL

from balance import update_balance
from database import (
    stmt_sessions,
    stmt_session,
    stmt_session_delete,
    stmt_cache,
    stmt_cache_delete,
    stmt_track,
    stmt_session_tracks,
    stmt_description
)
from fft import update_fft
from psst import Suspension, Strokes, Telemetry, dataclass_from_dict
from map import gpx_to_dict, track_data
from travel import update_travel_histogram
from velocity import update_velocity_band_stats, update_velocity_histogram


parser = argparse.ArgumentParser()
parser.add_argument(
    "-d", "--database",
    required=True,
    help="SQLite database path")
parser.add_argument(
    "-g", "--gosst_api",
    required=False,
    default="http://127.0.0.1:8080",
    help="GoSST HTTP API address:port")
cmd_args = parser.parse_args()

engine = create_engine(f'sqlite:///{cmd_args.database}')
dark_minimal = built_in_themes[DARK_MINIMAL]
front_color, rear_color = Spectral11[1], Spectral11[2]

app = Flask(__name__)
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

jinja_env = Environment(loader=FileSystemLoader('templates'))
dashboard_template = jinja_env.get_template('dashboard.html')
empty_template = jinja_env.get_template('empty.html')


def _sessions_list() -> dict[str, tuple[int, str, str]]:
    last_day = datetime.min
    sessions_dict = dict()
    for s in session['sessions']:
        d = datetime.fromtimestamp(s[3])
        desc = s[2] if s[2] else f"No description for {s[1]}"
        date_str = d.strftime('%Y.%m.%d')
        if d.date() != last_day:
            sessions_dict[date_str] = [(s[0], s[1], desc)]
            last_day = d.date()
        else:
            sessions_dict[date_str].append((s[0], s[1], desc))
    return sessions_dict


def _filter_strokes(strokes: Strokes, start: int, end: int) -> Strokes:
    if start is None or end is None:
        return strokes
    return Strokes(
        Compressions=[c for c in strokes.Compressions if
                      c.Start > start and c.End < end],
        Rebounds=[r for r in strokes.Rebounds if
                  r.Start > start and r.End < end])


def _extract_range() -> (int, int):
    try:
        start = request.args.get('start')
        start = int(float(start) * session['telemetry'].SampleRate)
    except BaseException:
        start = None
    try:
        end = request.args.get('end')
        end = int(float(end) * session['telemetry'].SampleRate)
    except BaseException:
        end = None
    return start, end


def _validate_range(start: int, end: int) -> bool:
    t = session['telemetry']
    mx = len(t.Front.Travel if t.Front.Present else t.Rear.Travel)
    return (start is not None and end is not None and
            start >= 0 and end < mx)


def _update_data(strokes: Strokes, suspension: Suspension):
    tick = 1.0 / session['telemetry'].SampleRate
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
        session['hst']
    )
    return dict(
        fft=fft,
        thist=thist,
        vhist=vhist,
        vbands=vbands,
        balance=None
    )


def _check_access():
    return 'full_access' in session and session['full_access']


@app.route('/', defaults={'session_id': None})
@app.route('/<int:session_id>')
def dashboard(session_id):
    session['id'] = session_id

    # lod - Level of Detail for travel graph (downsample ratio)
    try:
        session['lod'] = int(request.args.get('lod'))
    except BaseException:
        session['lod'] = 5

    # hst - High Speed Threshold for velocity graphs/statistics in mm/s
    try:
        session['hst'] = int(request.args.get('hst'))
    except BaseException:
        session['hst'] = 350

    session['full_access'] = True  # XXX

    conn = engine.connect()
    res = conn.execute(stmt_sessions())
    session['sessions'] = [list(r) for r in res.fetchall()]

    res = conn.execute(stmt_session(session_id))
    session_data = res.fetchone()
    if not session_data:
        return empty_template.render(
            sessions=_sessions_list(),
            full_access=session['full_access']
        )

    session['session_name'] = session_data[0]

    d = msgpack.unpackb(session_data[2])
    t = dataclass_from_dict(Telemetry, d)
    session['telemetry'] = t

    suspension_count = 0
    if t.Front.Present:
        suspension_count += 1
    if t.Rear.Present:
        suspension_count += 1

    record_num = len(t.Front.Travel) if t.Front.Present else len(t.Rear.Travel)
    elapsed_time = record_num / t.SampleRate
    start_time = t.Timestamp
    end_time = start_time + elapsed_time
    session['start_time'] = start_time
    session['end_time'] = end_time
    full_track, session_track = track_data(session_data[3],
                                           start_time, end_time)

    res = conn.execute(stmt_cache(session_id))
    components = res.fetchone()
    if not components:
        return empty_template.render(
            sessions=_sessions_list(),
            full_access=session['full_access']
        )

    components_script = components[1]
    components_divs = components[2:]

    utc_str = datetime.fromtimestamp(t.Timestamp,
                                     pytz.UTC).strftime('%Y.%m.%d %H:%M')

    conn.close()
    return dashboard_template.render(
        sessions=_sessions_list(),
        resources=CDN.render(),
        suspension_count=suspension_count,
        name=session['session_name'],
        date=utc_str,
        full_access=session['full_access'],
        full_track=full_track,
        session_track=session_track,
        components_script=components_script,
        components_divs=components_divs)


@app.route('/updates')
def updates():
    start, end = _extract_range()
    t = session['telemetry']
    if not _validate_range(start, end):
        start = None
        end = None

    updated_data = {'front': None, 'rear': None}
    if t.Front.Present:
        f_strokes = _filter_strokes(t.Front.Strokes, start, end)
        updated_data['front'] = _update_data(f_strokes, t.Front)
    if t.Rear.Present:
        r_strokes = _filter_strokes(t.Rear.Strokes, start, end)
        updated_data['rear'] = _update_data(r_strokes, t.Rear)
    if t.Front.Present and t.Rear.Present:
        updated_data['balance'] = dict(
            compression=update_balance(
                f_strokes.Compressions,
                r_strokes.Compressions,
                t.Front.Calibration.MaxStroke,
                t.Linkage.MaxRearTravel
            ),
            rebound=update_balance(
                f_strokes.Rebounds,
                r_strokes.Rebounds,
                t.Front.Calibration.MaxStroke,
                t.Linkage.MaxRearTravel
            ),
        )

    return jsonify(updated_data)


@app.route('/<int:id>', methods=['DELETE'])
def delete_session(id: int):
    if not _check_access():
        return '', 401

    with engine.connect() as conn:
        conn.execute(stmt_session_delete(id))
        conn.execute(stmt_cache_delete(id))
        # TODO: delete track too, if no other sessions use it
        conn.commit()

    return '', 204


@app.route('/<int:id>', methods=['PATCH'])
def update_session(id: int):
    if not _check_access():
        return '', 401

    data = request.json
    with engine.connect() as conn:
        conn.execute(stmt_description(id, data['name'], data['desc']))
        conn.commit()

    return '', 204


@app.route('/gpx', methods=['PUT'])
def upload_gpx():
    if not _check_access():
        return '', 401

    track_dict = gpx_to_dict(request.data)
    ts, tf = track_dict['time'][0], track_dict['time'][-1]
    full_track, session_track = track_data(
        track_dict, session['start_time'], session['end_time'])
    if session_track is None:
        return '', 400
    data = dict(full_track=full_track, session_track=session_track)

    with engine.connect() as conn:
        res = conn.execute(stmt_track(json.dumps(track_dict)))
        track_id = res.fetchone()[0]
        conn.execute(stmt_session_tracks(
            session['id'], track_id, ts, tf))
        conn.commit()

    return jsonify(data), 200


if __name__ == '__main__':
    app.run()
