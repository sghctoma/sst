#!/usr/bin/env python3

import base64
import json
import logging
import math
import struct

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State, MATCH
from scipy.fft import rfft, rfftfreq
#from waitress import serve

TIME_STEP = 0.0002 # 5 kHz

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

telemetry_data = list()

pio.templates.default = "plotly_dark"
CHART_COLORS = px.colors.qualitative.Prism

app = Dash(__name__)
app.title = "sufni suspension telemetry"

app.layout = html.Div([
    html.H3('sufni suspension telemetry', style={'font-family': 'monospace'}),
    html.Div(id='graph-container'),
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Files')
        ]),
        style={
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        multiple=True
    ),
])

def graph_travel(row):
    td = telemetry_data[row]
    fig = go.Figure()
    if td['fork_travel'] is not None:
        fig.add_trace(go.Scatter(x=td['time'], y=td['fork_travel'],
            name=f"fork-{td['name']}",
            line_color=CHART_COLORS[row%len(CHART_COLORS)]))
    if td['shock_travel'] is not None:
        fig.add_trace(go.Scatter(x=td['time'], y=td['shock_travel'],
            name=f"shock-{td['name']}",
            line_color=CHART_COLORS[row%len(CHART_COLORS)+1]))
    fig.update_xaxes(title_text="Elapsed time (s)")
    fig.update_yaxes(title_text="Height (mm)", fixedrange=True)
    fig.update_layout(
        title=td['name'],
        margin=dict(l=100, r=10, t=50, b=50, autoexpand=True),
        legend=dict(yanchor='bottom', y=1.0, xanchor='right', x=1.0, orientation='h'))

    return dcc.Graph(
        id={'type': 'travel', 'index': row},
        config={'displayModeBar': False},
        style={'width': '70%', 'height': '30vh', 'display': 'inline-block'},
        figure=fig)

def figure_fft(dataset, row, limits=None):
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
        Output({'type': 'fork-fft', 'index': MATCH}, 'figure'),
        Output({'type': 'shock-fft', 'index': MATCH}, 'figure'),
        Input({'type': 'travel', 'index': MATCH}, 'relayoutData'),
        State({'type': 'travel', 'index': MATCH}, 'id'), prevent_initial_call=True)
def recalculate_ffts(relayoutData, id):
    logger.info(json.dumps(relayoutData))
    row = id['index']
    if 'autosize' in relayoutData or 'xaxis.autorange' in relayoutData:
        return [
            figure_fft('fork_travel', row),
            figure_fft('shock_travel', row)]
    else:
        start = int(relayoutData['xaxis.range[0]'] / TIME_STEP)
        stop  = int(relayoutData['xaxis.range[1]'] / TIME_STEP)
        return [
            figure_fft('fork_travel', row, (start, stop)),
            figure_fft('shock_travel', row, (start, stop))]

@app.callback(
        Output("graph-container", "children"),
        Input("upload-data", "contents"),
        State('upload-data', 'filename'))
def create_graphs(content_list, filename_list):
    graphs = []
    if content_list:
        telemetry_data.clear()
        row = 0
        for c,f in zip(content_list, filename_list):
            parse_data(c, f)
            graphs.append(graph_travel(row))
            graphs.append(graph_fft('fork-fft', row))
            graphs.append(graph_fft('shock-fft', row))
            row += 1

    return html.Div(graphs)

def do_fft(f, travel):
    wf = np.kaiser(len(travel), 10)

    balanced_travel = travel - np.mean(travel)
    balanced_travel_f = rfft(balanced_travel * wf)
    balanced_spectrum = np.abs(balanced_travel_f)

    #max_freq_idx = np.argpartition(balanced_spectrum, -1)[-1:]
    #print(f[max_freq_idx])

    return balanced_spectrum[:len(f)]

def distance(record):
    arm_length = 1.0        # TODO: should be measured
    min_height = 0          # TODO: should be measured
    start_angle = np.pi / 9 # TODO: should be measured
    angle = np.pi / 4096 * record
    return arm_length * math.cos(angle + start_angle) - min_height

def parse_data(content, filename):
    _, encoded = content.split(',')
    data = base64.b64decode(encoded)

    '''
    Data is a stream of "records" defined as the following struct
    in the Teensy code:
    
    struct record {
        uint32_t micros;
        uint16_t frontAngle;
        uint16_t rearAngle;
    };
    '''
    first_record = struct.unpack('<HH', data[4:8])
    unpacked = [(r[0], distance(r[1]), distance(r[2])) for r in struct.iter_unpack('<LHH', data)]
    elapsed_seconds = (unpacked[-1][0] - unpacked[1][0]) / 1000000
    record_count = len(unpacked)
    logger.info(f"elapsed time: {elapsed_seconds} s")
    logger.info(f"record count: {record_count}")
    logger.info(f"sample rate:  {record_count / elapsed_seconds} sample/s")

    fork_travel = (np.array([r[1] for r in unpacked])) if first_record[0] != 0xFFFF else None
    shock_travel = (np.array([r[2] for r in unpacked])) if first_record[1] != 0xFFFF else None

    telemetry_data.append({
        'name': filename,
        'time': [TIME_STEP * i for i in range(len(unpacked))], # could also use the stored value
        'fork_travel': fork_travel,
        'shock_travel': shock_travel})

    return telemetry_data[-1]

app.run_server(debug=True)
