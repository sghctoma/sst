#!/usr/bin/env python3

import argparse
import json
import msgpack
import pytz

from datetime import datetime
from flask import Flask, request, session
from flask_session import Session
from jinja2 import Template
from sqlalchemy import create_engine
from typing import Callable

from bokeh.embed import json_item
from bokeh.layouts import row
from bokeh.models import ColumnDataSource
from bokeh.palettes import Spectral11
from bokeh.plotting import figure
from bokeh.resources import CDN
from bokeh.themes import built_in_themes, DARK_MINIMAL

from balance import balance_figure
from database import stmt_sessions, stmt_session, stmt_cache
from description import description_figure
from fft import fft_figure
from psst import Strokes, Telemetry, dataclass_from_dict
from travel import travel_histogram_figure
from velocity import velocity_band_stats_figure, velocity_histogram_figure


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

with open('templates/dashboard.html', 'r') as f:
    template_html = f.read()
    dashboard_page = Template(template_html)


def make_plot(title):
    from random import random
    x = [x for x in range(500)]
    y = [random() for _ in range(500)]
    s = ColumnDataSource(data=dict(x=x, y=y))
    p = figure(width=400, height=400, tools="lasso_select", title=title)
    p.scatter('x', 'y', source=s, alpha=0.6)
    return p


def _filter_strokes(strokes: Strokes, start: int, end: int) -> Strokes:
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


def _plot_json(susp: str, cname: str, fplot: Callable, rplot: Callable) -> str:
    start, end = _extract_range()
    t = session['telemetry']
    if not _validate_range(start, end):
        if (susp == 'front' or not susp) and t.Front.Present:
            return session[f'json_f_{cname}']

        if (susp == 'rear' or not susp) and t.Rear.Present:
            return session[f'json_r_{cname}']
    else:
        if (susp == 'front' or not susp) and t.Front.Present:
            strokes = _filter_strokes(t.Front.Strokes, start, end)
            p = fplot(strokes)
            return json.dumps(json_item(p, theme=dark_minimal))

        if (susp == 'rear' or not susp) and t.Rear.Present:
            strokes = _filter_strokes(t.Rear.Strokes, start, end)
            p = rplot(strokes)
            return json.dumps(json_item(p, theme=dark_minimal))


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
    session['sessions'] = res.fetchall()

    res = conn.execute(stmt_session(session_id))
    session_data = res.fetchone()
    session['session_name'] = session_data[0]
    p_desc = description_figure(
        session_data[0],
        session_data[1],
        session['full_access'])
    session['description'] = json.dumps(json_item(p_desc, theme=dark_minimal))

    session['track_json'] = session_data[3]  # XXX is this necessary?

    d = msgpack.unpackb(session_data[2])
    session['telemetry'] = dataclass_from_dict(Telemetry, d)

    res = conn.execute(stmt_cache(session_id))
    items = res.fetchone()
    if not items:
        return "ERR"

    components_script = items[1]
    div_travel = items[2]
    div_velocity = items[3]
    div_map = items[4]
    div_lr = items[5]
    div_sw = items[6]
    div_setup = items[7]

    session['json_f_fft'] = items[8]
    session['json_r_fft'] = items[9]
    session['json_f_thist'] = items[10]
    session['json_r_thist'] = items[11]
    session['json_f_vhist'] = items[12]
    session['json_r_vhist'] = items[13]
    session['json_cbalance'] = items[14]
    session['json_rbalance'] = items[15]

    utc_str = datetime.fromtimestamp(session['telemetry'].Timestamp,
                                     pytz.UTC).strftime('%Y.%m.%d %H:%M')

    return dashboard_page.render(
        resources=CDN.render(),
        suspension_count=2,
        name=session['session_name'],
        date=utc_str,
        components_script=components_script,
        div_travel=div_travel,
        div_velocity=div_velocity,
        div_map=div_map,
        div_lr=div_lr,
        div_sw=div_sw,
        div_setup=div_setup)


@app.route('/description')
def description():
    return session['description']


@app.route('/sessions')
def sessions():
    p = make_plot("test")
    return json.dumps(json_item(p, theme=dark_minimal))


@app.route('/travel/histogram', defaults={'suspension': None})
@app.route('/travel/histogram/<string:suspension>')
def travel_hist(suspension):
    def fplot(strokes: Strokes) -> figure:
        p = travel_histogram_figure(
            strokes,
            session['telemetry'].Front.TravelBins,
            front_color,
            "Travel histogram (front)")
        p.name = 'front_travel_hist'
        return p

    def rplot(strokes: Strokes) -> figure:
        p = travel_histogram_figure(
            strokes,
            session['telemetry'].Rear.TravelBins,
            rear_color,
            "Travel histogram (rear)")
        p.name = 'rear_travel_hist'
        return p

    return _plot_json(suspension, 'thist', fplot, rplot)


@app.route('/travel/fft', defaults={'suspension': None})
@app.route('/travel/fft/<string:suspension>')
def fft(suspension):
    def fplot(strokes: Strokes) -> figure:
        p = fft_figure(
            strokes,
            session['telemetry'].Front.Travel,
            1.0 / session['telemetry'].SampleRate,
            front_color,
            "Frequencies (front)")
        p.name = 'front_fft'
        return p

    def rplot(strokes: Strokes) -> figure:
        p = fft_figure(
            strokes,
            session['telemetry'].Rear.Travel,
            1.0 / session['telemetry'].SampleRate,
            rear_color,
            "Frequencies (rear)")
        p.name = 'rear_fft'
        return p

    return _plot_json(suspension, 'fft', fplot, rplot)


@app.route('/velocity/histogram', defaults={'suspension': None})
@app.route('/velocity/histogram/<string:suspension>')
def velocity_hist(suspension):
    def fplot(strokes: Strokes) -> figure:
        hist = velocity_histogram_figure(
            strokes,
            session['telemetry'].Front.Velocity,
            session['telemetry'].Front.TravelBins,
            session['telemetry'].Front.VelocityBins,
            session['hst'],
            "Speed histogram (front)"
        )
        stats = velocity_band_stats_figure(
            strokes,
            session['telemetry'].Front.Velocity,
            session['hst'],
        )
        p = row(
            name='front_velocity_hist',
            sizing_mode='stretch_width',
            children=[hist, stats]
        )
        return p

    def rplot(strokes: Strokes) -> figure:
        hist = velocity_histogram_figure(
            strokes,
            session['telemetry'].Rear.Velocity,
            session['telemetry'].Rear.TravelBins,
            session['telemetry'].Rear.VelocityBins,
            session['hst'],
            "Speed histogram (rear)"
        )
        stats = velocity_band_stats_figure(
            strokes,
            session['telemetry'].Rear.Velocity,
            session['hst'],
        )
        p = row(
            name='rear_velocity_hist',
            sizing_mode='stretch_width',
            children=[hist, stats]
        )
        return p

    return _plot_json(suspension, 'vhist', fplot, rplot)


@app.route('/balance/<string:stroke_type>')
def balance_compression(stroke_type):
    start, end = _extract_range()
    if not _validate_range(start, end):
        return session[f'json_{stroke_type[0]}balance']

    t = session['telemetry']
    front_strokes = _filter_strokes(t.Front.Strokes, start, end)
    rear_strokes = _filter_strokes(t.Rear.Strokes, start, end)
    if stroke_type == 'compression':
        p = balance_figure(
            front_strokes.Compressions,
            rear_strokes.Compressions,
            t.Front.Calibration.MaxStroke,
            t.Linkage.MaxRearTravel,
            False,
            front_color,
            rear_color,
            'balance_compression',
            "Compression velocity balance"
        )
        return json.dumps(json_item(p, theme=dark_minimal))

    if stroke_type == 'rebound':
        p = balance_figure(
            front_strokes.Rebounds,
            rear_strokes.Rebounds,
            t.Front.Calibration.MaxStroke,
            t.Linkage.MaxRearTravel,
            True,
            front_color,
            rear_color,
            'balance_rebound',
            "Rebound velocity balance"
        )
        return json.dumps(json_item(p, theme=dark_minimal))


@app.route('/session-dialog')
def session_dialog():
    p = make_plot("test")
    return json.dumps(json_item(p, theme=dark_minimal))


if __name__ == '__main__':
    app.run()
