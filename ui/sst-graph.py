#!/usr/bin/env python3

import base64
import logging
import math

import msgpack
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State, MATCH
from dash.exceptions import PreventUpdate
from plotly.subplots import make_subplots
from scipy.fft import rfft, rfftfreq
from scipy.signal import savgol_filter
#from waitress import serve

TIME_STEP = 0.0002 # 5 kHz

DEFAULT_FORK_ARM           = 120
DEFAULT_FORK_MAX_DISTANCE  = 218
DEFAULT_FORK_MAX_TRAVEL    = 180
DEFAULT_SHOCK_ARM          = 88
DEFAULT_SHOCK_MAX_DISTANCE = 138
DEFAULT_SHOCK_MAX_TRAVEL   = 65

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

pio.templates.default = "plotly_dark"
CHART_COLORS = px.colors.qualitative.Prism

app = Dash(__name__)
app.title = "sufni suspension telemetry"

app.layout = html.Div([
    html.H3('sufni suspension telemetry', style={'font-family': 'monospace'}),
    html.Div(
        id='graph-container',
        style={
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px',
            'padding': '10px'
        }),
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
])

def graph_shock_wheel(coeffs, max_travel):
    p = np.poly1d(np.flip(coeffs))
    fig = go.Figure()
    x = list(range(int(max_travel)+1))
    y = [p(t) for t in x]
    fig.add_trace(go.Scatter(x=x, y=y, name="travel", line_color=CHART_COLORS[-1]))
    fig.update_xaxes(title_text="Shock travel", fixedrange=True)
    fig.update_yaxes(title_text="Rear wheel travel", tick0=0, dtick=y[-1]/5, fixedrange=True)
    fig.update_layout(margin=dict(l=70, r=10, t=10, b=10, autoexpand=True))

    return dcc.Graph(
        config={'displayModeBar': False},
        responsive=True,
        style={'height': '30vh', 'width': '15%', 'display': 'inline-block'},
        figure=fig)

def graph_leverage_ratio(wtlr):
    d = np.array(wtlr)
    x = d[:,0]
    y = d[:,1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, name="leverage ratio", line_color=CHART_COLORS[-1]))
    fig.update_xaxes(title_text="Rear wheel travel", fixedrange=True)
    fig.update_yaxes(title_text="Leverage ratio", tick0=0, dtick=y[-1]/5, fixedrange=True)
    fig.update_layout(margin=dict(l=70, r=10, t=10, b=10, autoexpand=True))

    return dcc.Graph(
        config={'displayModeBar': False},
        responsive=True,
        style={'height': '30vh', 'width': '15%', 'display': 'inline-block'},
        figure=fig)

def graph_travel(row, data):
    fork_max = data['ForkCalibration']['MaxTravel']
    p = np.poly1d(np.flip(data['CoeffsShockWheel']))
    shock_max = p(data['ShockCalibration']['MaxTravel'])

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if data['FrontTravel'] is not None:
        # subsampling travel data, because add_trace is slow as hell
        x = np.array(data['Time'])[::100]
        y = np.array(data['FrontTravel'])[::100]
        fig.add_trace(go.Scatter(x=x, y=y, name=f"fork-{data['Name']}",
            line_color=CHART_COLORS[row%len(CHART_COLORS)]), secondary_y=False)
    if data['RearTravel'] is not None:
        # subsampling travel data, because add_trace is slow as hell
        x = np.array(data['Time'])[::100]
        y = np.array(data['RearTravel'])[::100]
        fig.add_trace(go.Scatter(x=x, y=y, name=f"shock-{data['Name']}",
            line_color=CHART_COLORS[row%len(CHART_COLORS)+1]), secondary_y=True)
    fig.update_xaxes(title_text="Elapsed time (s)")
    fig.update_yaxes(title_text="Front travel (mm)", secondary_y=False,
            fixedrange=True, range=[fork_max, 0], tick0=fork_max, dtick=fork_max/10)
    fig.update_yaxes(title_text="Rear travel (mm)", secondary_y=True,
            fixedrange=True, range=[shock_max, 0], tick0=shock_max, dtick=shock_max/10)
    fig.update_layout(
        title="Travel",
        margin=dict(l=100, r=10, t=50, b=50, autoexpand=True),
        legend=dict(yanchor='bottom', y=1.0, xanchor='right', x=1.0, orientation='h'))

    return dcc.Graph(
        id={'type': 'travel', 'index': row},
        config={'displayModeBar': False},
        style={'width': '70%', 'height': '30vh', 'display': 'inline-block'},
        figure=fig)

def graph_auxiliary(typ, width, row):
    return dcc.Graph(
        id={'type': typ, 'index': row},
        config={'displayModeBar': False},
        style={'width': f'{width}%', 'height': '30vh', 'display': 'inline-block'},
        figure=go.Figure())

def figure_velocityhistogram(telemetry_data, dataset, row, limits=None):
    fig = go.Figure()
    fig.update_xaxes(title_text="Velocity histogram (%)", fixedrange=True)
    fig.update_yaxes(range=[-2000, 2000])
    fig.update_layout(margin=dict(l=0, r=10, t=50, b=50))

    data = telemetry_data[row][dataset]
    if data is None:
        return fig
    if limits:
        data = data[max(0, limits[0]):min(limits[1],len(data))]

    data_smooth = savgol_filter(data, 51, 3)
    velocity = np.gradient(data_smooth, TIME_STEP) 

    HIGH_SPEED_THRESHOLD = 400
    count = len(velocity)
    avgr = np.average(velocity[velocity < 0])
    hsr = np.count_nonzero(velocity < -HIGH_SPEED_THRESHOLD)
    lsr = np.count_nonzero((velocity > -HIGH_SPEED_THRESHOLD) & (velocity < 0))
    avgc = np.average(velocity[velocity > 0])
    lsc = np.count_nonzero((velocity > 0) & (velocity < HIGH_SPEED_THRESHOLD))
    hsc = np.count_nonzero(velocity > HIGH_SPEED_THRESHOLD)
    
    annotation_r = (
        f"<b>Avg.</b>: {avgr:4.2f} mm/s<br />"
        f"<b>HSR</b>: {hsr/count*100:14.2f} %<br />"
        f"<b>LSR</b>: {lsr/count*100:14.2f} %"
    )
    fig.add_annotation(text=annotation_r,
        xref="x domain", yref="y domain", x=0.95, y=0.05, bgcolor="#222222", showarrow=False)

    annotation_c = (
        f"<b>Avg.</b>: {avgc:4.2f} mm/s<br />"
        f"<b>HSC</b>: {hsc/count*100:14.2f} %<br />"
        f"<b>LSC</b>: {lsc/count*100:14.2f} %"
    )
    fig.add_annotation(text=annotation_c,
        xref="x domain", yref="y domain", x=0.95, y=0.95, bgcolor="#222222", showarrow=False)

    step = 100 # mm/s
    mn = int(((velocity.min() // step) - 1) * step)
    mx = int(((velocity.max() // step) + 1) * step)
    hist, bins = np.histogram(velocity, bins=list(range(mn, mx, step)))
    hist = hist / len(velocity) * 100

    colorindex = row % len(CHART_COLORS) + (1 if dataset == 'RearTravel' else 0)
    color = CHART_COLORS[colorindex]
    fig.add_trace(go.Bar(x=hist, y=bins, marker_color=color, orientation='h'))

    return fig

def figure_travelhistogram(telemetry_data, dataset, row, limits=None):
    fig = go.Figure()
    fig.update_xaxes(title_text="Travel histogram (%)", fixedrange=True)
    fig.update_layout(margin=dict(l=0, r=10, t=50, b=50))

    data = np.array(telemetry_data[row][dataset])
    if data is None:
        return fig
    if limits:
        data = data[max(0, limits[0]):min(limits[1],len(data))]

    if dataset == "RearTravel":
        p = np.poly1d(np.flip(telemetry_data[row]['CoeffsShockWheel']))
        mx = p(telemetry_data[row]['ShockCalibration']['MaxTravel'])
    else:
        mx = telemetry_data[row]['ForkCalibration']['MaxTravel']

    hist, bins = np.histogram(data, bins=np.arange(0, mx+mx/20, mx/20))
    hist = hist / len(data) * 100
    fig.update_yaxes(range=[mx+mx/20, -mx/20], fixedrange=True)

    bottomouts = np.count_nonzero(data[mx - data < 3])
    average = np.average(data)
    max_travel = np.max(data)
    
    annotation = (
        f"<b>Max. Travel:</b> {max_travel:9.2f} mm ({max_travel/mx*100:5.1f} %)<br />"
        f"<b>Avg. Travel:</b> {average:10.2f} mm ({average/mx*100:5.1f} %)<br />"
        f"<b>Bottom Outs:</b> {bottomouts:>34} "
    )
    fig.add_annotation(text=annotation,
        xref="x domain", yref="y domain", x=0.95, y=0.05, bgcolor="#222222", showarrow=False)
    
    colorindex = row % len(CHART_COLORS) + (1 if dataset == 'RearTravel' else 0)
    color = CHART_COLORS[colorindex]
    fig.add_trace(go.Bar(x=hist, y=bins, marker_color=color, orientation='h'))

    return fig

def figure_fft(telemetry_data, dataset, row, limits=None):
    data = telemetry_data[row][dataset]

    fig = go.Figure()
    fig.update_xaxes(title_text="Frequency (Hz)")
    fig.update_yaxes(showticklabels=False, fixedrange=True)
    fig.update_layout(margin=dict(l=0, r=10, t=50, b=50))

    if data is None:
        return fig

    if limits:
        data = data[max(0, limits[0]):min(limits[1],len(data))]

    time_f = rfftfreq(len(data), TIME_STEP)
    time_f = time_f[time_f <= 10] # cut off FFT graph at 10 Hz

    colorindex = row % len(CHART_COLORS) + (1 if dataset == 'RearTravel' else 0)
    color = CHART_COLORS[colorindex]
    fig.add_trace(go.Scatter(x=time_f, y=do_fft(time_f, data), marker_color=color))
    return fig

@app.callback(
        Output({'type': 'fork-fft', 'index': MATCH}, 'figure'),
        Output({'type': 'shock-fft', 'index': MATCH}, 'figure'),
        Output({'type': 'fork-histogram-travel', 'index': MATCH}, 'figure'),
        Output({'type': 'shock-histogram-travel', 'index': MATCH}, 'figure'),
        Output({'type': 'fork-histogram-velocity', 'index': MATCH}, 'figure'),
        Output({'type': 'shock-histogram-velocity', 'index': MATCH}, 'figure'),
        Input({'type': 'travel', 'index': MATCH}, 'relayoutData'),
        State({'type': 'travel', 'index': MATCH}, 'id'),
        State('telemetry-data', 'data'), prevent_initial_call=True)
def recalculate_auxiliary(relayoutData, id, telemetry_data):
    if not relayoutData:
        raise PreventUpdate

    row = id['index']
    if 'autosize' in relayoutData or 'xaxis.autorange' in relayoutData:
        return [
            figure_fft(telemetry_data, 'FrontTravel', row),
            figure_fft(telemetry_data, 'RearTravel', row),
            figure_travelhistogram(telemetry_data, 'FrontTravel', row),
            figure_travelhistogram(telemetry_data, 'RearTravel', row),
            figure_velocityhistogram(telemetry_data, 'FrontTravel', row),
            figure_velocityhistogram(telemetry_data, 'RearTravel', row)]
    else:
        start = int(relayoutData['xaxis.range[0]'] / TIME_STEP)
        stop  = int(relayoutData['xaxis.range[1]'] / TIME_STEP)
        return [
            figure_fft(telemetry_data, 'FrontTravel', row, (start, stop)),
            figure_fft(telemetry_data, 'RearTravel', row, (start, stop)),
            figure_travelhistogram(telemetry_data, 'FrontTravel', row, (start, stop)),
            figure_travelhistogram(telemetry_data, 'RearTravel', row, (start, stop)),
            figure_velocityhistogram(telemetry_data, 'FrontTravel', row, (start, stop)),
            figure_velocityhistogram(telemetry_data, 'RearTravel', row, (start, stop))]

@app.callback(
        Output('graph-container', 'children'),
        Output('telemetry-data', 'data'),
        Output('loading-upload-output', 'children'),
        Input('upload-data', 'contents'),
        State('upload-data', 'filename'))
def create_graphs(content_list, filename_list):
    graphs = []

    telemetry_data = list()
    if content_list:
        row = 0
        for c,f in zip(content_list, filename_list):
            _, encoded = c.split(',')
            data = base64.b64decode(encoded)
            t = msgpack.unpackb(data)
            telemetry_data.append(t)

            graphs.append(graph_travel(row, t))

            graphs.append(graph_shock_wheel(t['CoeffsShockWheel'], t['ShockCalibration']['MaxTravel']))
            graphs.append(graph_leverage_ratio(t['WheelLeverageRatio']))

            graphs.append(graph_auxiliary('fork-histogram-travel', 25, row))
            graphs.append(graph_auxiliary('shock-histogram-travel', 25, row))
            graphs.append(graph_auxiliary('fork-histogram-velocity', 25, row))
            graphs.append(graph_auxiliary('shock-histogram-velocity', 25, row))
            graphs.append(graph_auxiliary('fork-fft', 50, row))
            graphs.append(graph_auxiliary('shock-fft', 50, row))

            row += 1

    return html.Div(graphs), telemetry_data, None

def do_fft(f, travel):
    wf = np.kaiser(len(travel), 5)

    balanced_travel = travel - np.mean(travel)
    balanced_travel_f = rfft(balanced_travel * wf)
    balanced_spectrum = np.abs(balanced_travel_f)

    #max_freq_idx = np.argpartition(balanced_spectrum, -1)[-1:]
    #print(f[max_freq_idx])

    return balanced_spectrum[:len(f)]

app.run_server(debug=True)
