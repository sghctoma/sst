import argparse
import json
import msgpack
import pytz

from datetime import datetime
from flask import Flask, request, session
from flask_session import Session
from jinja2 import Template
from sqlalchemy import (
    Column, Integer, LargeBinary, MetaData, String, Table,
    ForeignKey,
    create_engine, select, desc
)

from bokeh.embed import json_item
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure
from bokeh.resources import CDN
from bokeh.themes import built_in_themes, DARK_MINIMAL

from description import description_figure
from psst import Strokes, Telemetry, dataclass_from_dict


metadata_obj = MetaData()

bokeh_cache_table = Table(
    'bokeh_cache',
    metadata_obj,
    Column('session_id', Integer, ForeignKey('sessions.session_id')),
    Column('script', String),
    Column('div_travel', String),
    Column('div_velocity', String),
    Column('div_map', String),
    Column('div_lr', String),
    Column('div_sw', String),
    Column('div_setup', String),
    Column('json_f_fft', String),
    Column('json_r_fft', String),
    Column('json_f_thist', String),
    Column('json_r_thist', String),
    Column('json_f_vhist', String),
    Column('json_r_vhist', String),
    Column('json_cbalance', String),
    Column('json_rbalance', String),
)

tracks_table = Table(
    'tracks',
    metadata_obj,
    Column('track_id', Integer, primary_key=True),
    Column('track', String, nullable=False),
)

sessions_table = Table(
    'sessions',
    metadata_obj,
    Column('session_id', Integer, primary_key=True),
    Column('name', String),
    Column('setup_id', Integer, ForeignKey('setups.setup_id'), nullable=False),
    Column('description', String),
    Column('timestamp', Integer),
    Column('data', LargeBinary),
    Column('track_id', Integer, ForeignKey('tracks.track_id'), nullable=False),
)

app = Flask(__name__)
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

with open('templates/dashboard.html', 'r') as f:
    template_html = f.read()
    dashboard_page = Template(template_html)

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


def make_plot(title):
    from random import random
    x = [x for x in range(500)]
    y = [random() for _ in range(500)]
    s = ColumnDataSource(data=dict(x=x, y=y))
    p = figure(width=400, height=400, tools="lasso_select", title=title)
    p.scatter('x', 'y', source=s, alpha=0.6)
    return p


dark_minimal = built_in_themes[DARK_MINIMAL]

engine = create_engine(f'sqlite:///{cmd_args.database}')


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
    stmt = (select(
            sessions_table.c.session_id,
            sessions_table.c.name,
            sessions_table.c.description,
            sessions_table.c.timestamp)
            .order_by(desc(sessions_table.c.timestamp)))
    res = conn.execute(stmt)
    session['sessions'] = res.fetchall()

    stmt = (select(
            sessions_table.c.name,
            sessions_table.c.description,
            sessions_table.c.data,
            tracks_table.c.track)
            .join(tracks_table, isouter=True)
            .where(sessions_table.c.session_id == session_id))
    res = conn.execute(stmt, [(session_id,)])
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

    stmt = (select(bokeh_cache_table)
            .where(bokeh_cache_table.c.session_id == session_id))
    res = conn.execute(stmt)
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
    start = request.args.get('start')
    end = request.args.get('end')
    print(start, end)
    return session[f'{suspension[0]}_thist']


@app.route('/travel/fft', defaults={'suspension': None})
@app.route('/travel/fft/<string:suspension>')
def fft(suspension):
    start = request.args.get('start')
    end = request.args.get('end')
    print(start, end)
    return session[f'{suspension[0]}_fft']


@app.route('/velocity/histogram', defaults={'suspension': None})
@app.route('/velocity/histogram/<string:suspension>')
def velocity_hist(suspension):
    start = request.args.get('start')
    end = request.args.get('end')
    print(start, end)
    return session[f'{suspension[0]}_vhist']


@app.route('/balance/<string:stroke_type>')
def balance_compression(stroke_type):
    start = request.args.get('start')
    end = request.args.get('end')
    print(start, end)
    return session[f'{stroke_type[0]}balance']


@app.route('/session-dialog')
def session_dialog():
    p = make_plot("test")
    return json.dumps(json_item(p, theme=dark_minimal))


if __name__ == '__main__':
    app.run()
