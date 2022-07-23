#!/usr/bin/env python3

import base64
import logging
import math
import struct

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State, MATCH
from dash.exceptions import PreventUpdate
from plotly.subplots import make_subplots
from scipy.fft import rfft, rfftfreq
#from waitress import serve

TIME_STEP = 0.0002 # 5 kHz

DEFAULT_FORK_ARM           = 110
DEFAULT_FORK_MAX_DISTANCE  = 210
DEFAULT_FORK_MAX_TRAVEL    = 180
DEFAULT_SHOCK_ARM          = 77
DEFAULT_SHOCK_MAX_DISTANCE = 147
DEFAULT_SHOCK_MAX_TRAVEL   = 65

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

pio.templates.default = "plotly_dark"
CHART_COLORS = px.colors.qualitative.Prism

app = Dash(__name__)
app.title = "sufni suspension telemetry"

app.layout = html.Div([
    html.H3('sufni suspension telemetry', style={'font-family': 'monospace'}),
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Files'),
        ]),
        style={
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        multiple=True
    ),
    html.Div(id='graph-container'),
    dcc.Loading(
        id='loading-upload',
        type='default',
        children=html.Div(id='loading-upload-output'),
        fullscreen=True,
        style={'background-color': 'rgba(32, 32, 32, 0.9)'},
    ),
    dcc.Store(
        id='telemetry-data',
        storage_type='memory',
    ),
    dcc.Store(
        id='calibration',
        storage_type='memory',
        data={
            'fork': {
                'arm': DEFAULT_FORK_ARM,
                'max_distance': DEFAULT_FORK_MAX_DISTANCE,
                'start_angle': np.arccos(DEFAULT_FORK_MAX_DISTANCE / 2 / DEFAULT_FORK_ARM),
                'max_travel': DEFAULT_FORK_MAX_TRAVEL,
            },
            'shock': {
                'arm': DEFAULT_SHOCK_ARM,
                'max_distance': DEFAULT_SHOCK_MAX_DISTANCE,
                'start_angle': np.arccos(DEFAULT_SHOCK_MAX_DISTANCE / 2 / DEFAULT_SHOCK_ARM),
                'max_travel': DEFAULT_SHOCK_MAX_TRAVEL,
            }
        }
    ),
    html.Div(
        children=[
            html.Div(
                children=[
                    html.H5('Calibration (?)'),
                    html.Img(src="assets/explanation.png", className="tooltiptext tooltip-bottom"),
                ],
                className="tooltipx",
                style={'grid-row': '1', 'grid-column': '1'}),
            
            html.B('Fork', style={'grid-row': '2', 'grid-column': '2'}),
            html.B('Shock', style={'grid-row': '2', 'grid-column': '3'}),
            html.P('Load Leverage Ratio data by clicking on graph', style={'grid-row': '2', 'grid-column': '4'}),

            html.P('Maximum travel (mm):',   style={'grid-row': '3', 'grid-column': '1'}),
            html.P('Arm length (mm):',       style={'grid-row': '4', 'grid-column': '1'}),
            html.P('Maximum distance (mm):', style={'grid-row': '5', 'grid-column': '1'}),
            html.P('Start angle (°):',       style={'grid-row': '6', 'grid-column': '1'}),

            dcc.Input(
                id='fork-max-travel',
                type='number',
                min=0,
                value=DEFAULT_FORK_MAX_TRAVEL,
                style={'grid-row': '3', 'grid-column': '2'}),
            dcc.Input(
                id='fork-arm',
                type='number',
                min=0,
                value=DEFAULT_FORK_ARM,
                style={'grid-row': '4', 'grid-column': '2'}),
            dcc.Input(
                id='fork-max',
                type='number',
                min=0,
                value=DEFAULT_FORK_MAX_DISTANCE,
                style={'grid-row': '5', 'grid-column': '2'}),
            dcc.Input(
                id='fork-start-angle',
                type='number',
                disabled=True,
                style={'grid-row': '6', 'grid-column': '2'}),

            dcc.Input(
                id='shock-max-travel',
                type='number',
                min=0,
                value=DEFAULT_SHOCK_MAX_TRAVEL,
                style={'grid-row': '3', 'grid-column': '3'}),
            dcc.Input(
                id='shock-arm',
                type='number',
                min=0,
                value=DEFAULT_SHOCK_ARM,
                style={'grid-row': '4', 'grid-column': '3'}),
            dcc.Input(
                id='shock-max',
                type='number',
                min=0,
                value=DEFAULT_SHOCK_MAX_DISTANCE,
                style={'grid-row': '5', 'grid-column': '3'}),
            dcc.Input(
                id='shock-start-angle',
                type='number',
                disabled=True,
                style={'grid-row': '6', 'grid-column': '3'}),
           
            html.Button('Apply',
                id='apply-calibration',
                style={'grid-row': '7', 'grid-column': '1 / span 3'}),

            html.Div(dcc.Upload(
                        id='upload-lr-curve',
                        multiple=False,
                        children=html.Div(id='lr-graph-container'),
                    ), style={'grid-row': '3 / span 6', 'grid-column': '4'})
        ],
        style={
            'display': 'grid',
            'grid-template-columns': '200px 100px 100px 450px auto',
            'grid-template-rows': '30px 30px 30px 30px 30px 30px 30px',
            'grid-gap': '5px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'margin': '10px',
            'padding': '5px',
        },
    ),
])

def graph_leverage(lr_function, max_travel):
    fig = go.Figure()
    x = list(range(max_travel+1))
    y = [lr_function(t) for t in x]
    fig.add_trace(go.Scatter(x=x, y=y, name="leverage", line_color=CHART_COLORS[-1]))
    fig.update_xaxes(title_text="Shock travel", fixedrange=True)
    fig.update_yaxes(title_text="Rear wheel travel", tick0=0, dtick=y[-1]/5, fixedrange=True)
    fig.update_layout(margin=dict(l=70, r=10, t=10, b=10, autoexpand=True))

    return dcc.Graph(
        config={'displayModeBar': False},
        responsive=True,
        style={'height': '19vh'},
        figure=fig)

def graph_travel(row, data, fork_max, shock_max):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if data['fork_travel'] is not None:
        fig.add_trace(go.Scatter(x=data['time'], y=data['fork_travel'],
            name=f"fork-{data['name']}",
            line_color=CHART_COLORS[row%len(CHART_COLORS)]), secondary_y=False)
    if data['shock_travel'] is not None:
        fig.add_trace(go.Scatter(x=data['time'], y=data['shock_travel'],
            name=f"shock-{data['name']}",
            line_color=CHART_COLORS[row%len(CHART_COLORS)+1]), secondary_y=True)
    fig.update_xaxes(title_text="Elapsed time (s)")
    fig.update_yaxes(title_text="Fork travel (mm)", secondary_y=False,
            fixedrange=True, range=[fork_max, 0], tick0=fork_max, dtick=fork_max/10)
    fig.update_yaxes(title_text="Shock travel (mm)", secondary_y=True,
            fixedrange=True, range=[shock_max, 0], tick0=shock_max, dtick=shock_max/10)
    fig.update_layout(
        title=data['name'],
        margin=dict(l=100, r=10, t=50, b=50, autoexpand=True),
        legend=dict(yanchor='bottom', y=1.0, xanchor='right', x=1.0, orientation='h'))

    return dcc.Graph(
        id={'type': 'travel', 'index': row},
        config={'displayModeBar': False},
        style={'width': '70%', 'height': '30vh', 'display': 'inline-block'},
        figure=fig)

def figure_fft(telemetry_data, dataset, row, limits=None):
    data = telemetry_data[row][dataset]

    fig = go.Figure()
    fig.update_xaxes(title_text="Frequency (Hz)", range=[0, 5])
    fig.update_yaxes(showticklabels=False, fixedrange=True)
    fig.update_layout(margin=dict(l=0, r=10, t=50, b=50))

    if data is None:
        return fig

    if limits:
        data = data[max(0, limits[0]):min(limits[1],len(data))]

    time_f = rfftfreq(len(data), TIME_STEP)
    time_f = time_f[time_f <= 10] # cut off FFT graph at 10 Hz

    colorindex = row % len(CHART_COLORS) + (1 if dataset == 'shock_travel' else 0)
    color = CHART_COLORS[colorindex]
    fig.add_trace(go.Scatter(x=time_f, y=do_fft(time_f, data), marker_color=color))
    return fig

def graph_fft(typ, row):
    return dcc.Graph(
        id={'type': typ, 'index': row},
        config={'displayModeBar': False},
        style={'width': '15%', 'height': '30vh', 'display': 'inline-block'},
        figure=go.Figure())

@app.callback(
        Output('calibration', 'data'),
        Input('apply-calibration', 'n_clicks'),
        State('calibration', 'data'),
        State('fork-arm', 'value'),
        State('fork-max', 'value'),
        State('fork-max-travel', 'value'),
        State('shock-arm', 'value'),
        State('shock-max', 'value'),
        State('shock-max-travel', 'value'))
def on_apply_calibration(n_clicks, calibration,
        f_arm, f_max, f_max_travel,
        s_arm, s_max, s_max_travel):
    for p in [n_clicks, f_arm, f_max, f_max_travel, s_arm, s_max, s_max_travel]:
        if p is None:
            raise PreventUpdate

    calibration['fork'] = {
        'arm': f_arm,
        'max_distance': f_max,
        'start_angle': np.arccos(f_max / 2.0 / f_arm),
        'max_travel': f_max_travel,
    }
    calibration['shock'] = {
        'arm': s_arm,
        'max_distance': s_max,
        'start_angle': np.arccos(s_max / 2.0 / s_arm),
        'max_travel': s_max_travel,
    }
    
    return calibration

@app.callback(
        Output('fork-start-angle', 'value'),
        Input('fork-arm', 'value'),
        Input('fork-max', 'value'))
def fork_arm_changed(arm, max):
    return round(np.degrees(np.arccos(max / 2 / arm)), 2)

@app.callback(
        Output('shock-start-angle', 'value'),
        Input('shock-arm', 'value'),
        Input('shock-max', 'value'))
def shock_arm_changed(arm, max):
    return round(np.degrees(np.arccos(max / 2 / arm)), 2)

@app.callback(
        Output({'type': 'fork-fft', 'index': MATCH}, 'figure'),
        Output({'type': 'shock-fft', 'index': MATCH}, 'figure'),
        Input({'type': 'travel', 'index': MATCH}, 'relayoutData'),
        State({'type': 'travel', 'index': MATCH}, 'id'),
        State('telemetry-data', 'data'), prevent_initial_call=True)
def recalculate_ffts(relayoutData, id, telemetry_data):
    if not relayoutData:
        raise PreventUpdate

    row = id['index']
    if 'autosize' in relayoutData or 'xaxis.autorange' in relayoutData:
        return [
            figure_fft(telemetry_data, 'fork_travel', row),
            figure_fft(telemetry_data, 'shock_travel', row)]
    else:
        start = int(relayoutData['xaxis.range[0]'] / TIME_STEP)
        stop  = int(relayoutData['xaxis.range[1]'] / TIME_STEP)
        return [
            figure_fft(telemetry_data, 'fork_travel', row, (start, stop)),
            figure_fft(telemetry_data, 'shock_travel', row, (start, stop))]

@app.callback(
        Output('graph-container', 'children'),
        Output('lr-graph-container', 'children'),
        Output('telemetry-data', 'data'),
        Output('loading-upload-output', 'children'),
        Input('calibration', 'data'),
        Input('upload-lr-curve', 'contents'),
        Input('upload-data', 'contents'),
        State('upload-data', 'filename'))
def create_graphs(calibration, lr_curve, content_list, filename_list):
    graphs = []
    if lr_curve:
        _, encoded = lr_curve.split(',')
        raw_data = base64.b64decode(encoded).decode('utf-8')
        data = np.array([list(map(float, line.rstrip().split(','))) for line in raw_data.splitlines() if
            line and not line.startswith('#')])

        wheel_travel = data[:, 0]
        inverse = [1.0/f for f in data[:, 1]]
        shock_travel = [0.0]
        for f in inverse[:-1]:
            shock_travel.append(shock_travel[-1]+f)
        p = np.polyfit(shock_travel, wheel_travel, 3)
        lr_f = np.poly1d(p)
    else:
        lr_f = lambda x: x

    fork_max_travel = calibration['fork']['max_travel']
    shock_max_travel = lr_f(calibration['shock']['max_travel'])

    telemetry_data = list()
    if content_list:
        row = 0
        for c,f in zip(content_list, filename_list):
            telemetry_data.append(parse_data(c, f, calibration, lr_f))
            graphs.append(graph_travel(row, telemetry_data[row], fork_max_travel, shock_max_travel))
            graphs.append(graph_fft('fork-fft', row))
            graphs.append(graph_fft('shock-fft', row))
            row += 1

    lr_graph = graph_leverage(lr_f, calibration['shock']['max_travel'])

    return html.Div(graphs), lr_graph, telemetry_data, None

def do_fft(f, travel):
    wf = np.kaiser(len(travel), 5)

    balanced_travel = travel - np.mean(travel)
    balanced_travel_f = rfft(balanced_travel * wf)
    balanced_spectrum = np.abs(balanced_travel_f)

    #max_freq_idx = np.argpartition(balanced_spectrum, -1)[-1:]
    #print(f[max_freq_idx])

    return balanced_spectrum[:len(f)]

def angle_to_travel(record, calibration):
    angle = np.pi / 4096 * record
    total_distance = 2 * calibration['arm'] * math.cos(angle + calibration['start_angle'])
    return calibration['max_distance'] - total_distance

def parse_data(content, filename, calibration, lr_function):
    _, encoded = content.split(',')
    data = base64.b64decode(encoded)

    '''
    Data is a stream of "records" defined as the following struct in the MCU code:
    
    struct record {
        uint32_t micros;
        uint16_t fork_angle;
        uint16_t shock_angle;
    };
    '''
    first_record = struct.unpack('<HH', data[4:8])
    unpacked = [(
        r[0],
        angle_to_travel(r[1], calibration['fork']),
        lr_function(angle_to_travel(r[2], calibration['shock']))) for r in struct.iter_unpack('<LHH', data)]
    elapsed_seconds = (unpacked[-1][0] - unpacked[1][0]) / 1000000
    record_count = len(unpacked)
    logger.debug(f"elapsed time: {elapsed_seconds} s")
    logger.debug(f"record count: {record_count}")
    logger.debug(f"sample rate:  {record_count / elapsed_seconds} sample/s")

    fork_travel = [r[1] for r in unpacked] if first_record[0] != 0xFFFF else None
    shock_travel = [r[2] for r in unpacked] if first_record[1] != 0xFFFF else None

    return {
        'name': filename,
        'time': [TIME_STEP * i for i in range(len(unpacked))], # could also use the stored value
        'fork_travel': fork_travel,
        'shock_travel': shock_travel}

app.run_server(debug=True)
