import msgpack
import numpy as np

from bokeh.document import Document
from bokeh.events import DocumentReady, MouseMove
from bokeh.embed import components
from bokeh.layouts import row
from bokeh.models.callbacks import CustomJS
from bokeh.models.widgets.markups import Div
from bokeh.palettes import Spectral11
from bokeh.plotting import figure
from bokeh.themes import built_in_themes, DARK_MINIMAL

from app.extensions import db
from app.models.session import Session
from app.models.session_html import SessionHtml
from app.telemetry.balance import balance_figure
from app.telemetry.description import description_figure
from app.telemetry.fft import fft_figure
from app.telemetry.leverage import leverage_ratio_figure, shock_wheel_figure
from app.telemetry.map import map_figure
from app.telemetry.psst import Telemetry, dataclass_from_dict
from app.telemetry.travel import travel_figure, travel_histogram_figure
from app.telemetry.velocity import velocity_figure
from app.telemetry.velocity import (
    velocity_histogram_figure,
    velocity_band_stats_figure
)


def _setup_figure(telemetry: Telemetry) -> figure:

    linkage_name = telemetry.Linkage.Name
    fork_stroke = telemetry.Linkage.MaxFrontStroke
    shock_stroke = telemetry.Linkage.MaxRearStroke
    head_angle = telemetry.Linkage.HeadAngle
    fcal_name = telemetry.Front.Calibration.Name
    rcal_name = telemetry.Rear.Calibration.Name
    fcal_inputs = telemetry.Front.Calibration.Inputs
    rcal_inputs = telemetry.Rear.Calibration.Inputs

    fcal_input_rows = [f'<tr><th>{k}</th><td>{v}</td></tr>' for
                       k, v in fcal_inputs.items()]
    rcal_input_rows = [f'<tr><th>{k}</th><td>{v}</td></tr>' for
                       k, v in rcal_inputs.items()]

    return Div(
        name='setup',
        sizing_mode='stretch_width',
        height=300,
        stylesheets=['''
            div {
              width: 100%;
              height: 100%;
              padding: 15px;
              background: #15191c;
              font-size: 14px;
              color: #d0d0d0;
            }
            hr {
              border-top:1px dashed #d0d0d0;
              background-color: transparent;
              border-style: none none dashed;
            }
            th, td {
              max-width: 50%;
            }
            table, th, td {
              border: 1px dashed #d0d0d0;
              border-collapse: collapse;
              text-align: center;
              table-layout: fixed;
            }'''],
        text=f'''
            <b>Linkage:</b> {linkage_name}
            <table style="width: 100%;">
            <tbody>
            <tr><th>Head angle</th><td>{head_angle}</td></tr>
            <tr><th>Fork stroke</th><td>{fork_stroke}</td></tr>
            <tr><th>Shock stroke</th><td>{shock_stroke}</td></tr>
            </tbody>
            </table>
            <br /><b>Front calibration:</b>{fcal_name}<br />
            <table style="width: 100%;">
            <tbody>
            {''.join(fcal_input_rows)}
            </tbody>
            </table>
            <br /><b>Rear calibration:</b>{rcal_name}<br />
            <table style="width: 100%;">
            <tbody>
            {''.join(rcal_input_rows)}
            </tbody>
            </table>
            ''')


def create_cache(session_id: int, lod: int, hst: int):
    front_color, rear_color = Spectral11[1], Spectral11[2]

    session = db.session.execute(
        db.select(Session).filter_by(id=session_id)).scalar_one_or_none()
    if not session:
        return None

    d = msgpack.unpackb(session.data)
    telemetry = dataclass_from_dict(Telemetry, d)

    tick = 1.0 / telemetry.SampleRate  # time step length in seconds

    p_setup = _setup_figure(telemetry)

    if telemetry.Front.Present:
        p_front_travel_hist = travel_histogram_figure(
            telemetry.Front.Strokes,
            telemetry.Front.TravelBins,
            front_color,
            "Travel histogram (front)")
        p_front_vel_hist = velocity_histogram_figure(
            telemetry.Front.Strokes,
            telemetry.Front.Velocity,
            telemetry.Front.TravelBins,
            telemetry.Front.VelocityBins,
            hst,
            "Speed histogram (front)")
        p_front_vel_stats = velocity_band_stats_figure(
            telemetry.Front.Strokes,
            telemetry.Front.Velocity,
            hst)
        p_front_fft = fft_figure(
            telemetry.Front.Strokes,
            telemetry.Front.Travel,
            tick,
            front_color,
            "Frequencies (front)")

    if telemetry.Rear.Present:
        p_rear_travel_hist = travel_histogram_figure(
            telemetry.Rear.Strokes,
            telemetry.Rear.TravelBins,
            rear_color,
            "Travel histogram (rear)")
        p_rear_vel_hist = velocity_histogram_figure(
            telemetry.Rear.Strokes,
            telemetry.Rear.Velocity,
            telemetry.Rear.TravelBins,
            telemetry.Rear.VelocityBins,
            hst,
            "Speed histogram (rear)")
        p_rear_vel_stats = velocity_band_stats_figure(
            telemetry.Rear.Strokes,
            telemetry.Rear.Velocity,
            hst)
        p_rear_fft = fft_figure(
            telemetry.Rear.Strokes,
            telemetry.Rear.Travel,
            tick,
            rear_color,
            "Frequencies (rear)")

    p_travel = travel_figure(telemetry, lod, front_color, rear_color)
    p_velocity = velocity_figure(telemetry, lod, front_color, rear_color)
    p_travel.x_range.js_link('start', p_velocity.x_range, 'start')
    p_travel.x_range.js_link('end', p_velocity.x_range, 'end')
    p_velocity.x_range.js_link('start', p_travel.x_range, 'start')
    p_velocity.x_range.js_link('end', p_travel.x_range, 'end')

    '''
    Leverage-related graphs. These are input data, not something measured.
    '''
    p_lr = leverage_ratio_figure(
        np.array(telemetry.Linkage.LeverageRatio), Spectral11[5])
    p_sw = shock_wheel_figure(telemetry.Linkage.ShockWheelCoeffs,
                              telemetry.Linkage.MaxRearStroke,
                              Spectral11[5])

    '''
    Compression and rebound velocity balance
    '''
    if telemetry.Front.Present and telemetry.Rear.Present:
        p_balance_compression = balance_figure(
            telemetry.Front.Strokes.Compressions,
            telemetry.Rear.Strokes.Compressions,
            telemetry.Linkage.MaxFrontTravel,
            telemetry.Linkage.MaxRearTravel,
            False,
            front_color,
            rear_color,
            'balance_compression',
            "Compression velocity balance")
        p_balance_rebound = balance_figure(
            telemetry.Front.Strokes.Rebounds,
            telemetry.Rear.Strokes.Rebounds,
            telemetry.Linkage.MaxFrontTravel,
            telemetry.Linkage.MaxRearTravel,
            True,
            front_color,
            rear_color,
            'balance_rebound',
            "Rebound velocity balance")

    p_desc = description_figure(session_id, session.name, session.description)
    p_map, on_mousemove = map_figure()
    p_travel.js_on_event(MouseMove, on_mousemove)

    '''
    Construct the layout.
    '''
    suspension_count = 0
    if telemetry.Front.Present:
        suspension_count += 1
    if telemetry.Rear.Present:
        suspension_count += 1

    dark_minimal_theme = built_in_themes[DARK_MINIMAL]
    document = Document()

    document.add_root(p_travel)
    document.add_root(p_velocity)
    document.add_root(p_map)
    document.add_root(p_lr)
    document.add_root(p_sw)
    document.add_root(p_setup)
    document.add_root(p_desc)
    columns = ['session_id', 'script', 'travel', 'velocity', 'map', 'lr', 'sw',
               'setup', 'desc']

    if telemetry.Front.Present:
        prefix = 'front_' if suspension_count == 2 else ''
        p_front_travel_hist.name = f'{prefix}travel_hist'
        p_front_fft.name = f'{prefix}fft'
        p_front_velocity = row(
            name=f'{prefix}velocity_hist',
            sizing_mode='stretch_width',
            children=[
                p_front_vel_hist,
                p_front_vel_stats])
        document.add_root(p_front_travel_hist)
        document.add_root(p_front_fft)
        document.add_root(p_front_velocity)
        columns.extend(['f_thist', 'f_fft', 'f_vhist'])
    if telemetry.Rear.Present:
        prefix = 'rear_' if suspension_count == 2 else ''
        p_rear_travel_hist.name = f'{prefix}travel_hist'
        p_rear_fft.name = f'{prefix}fft'
        p_rear_velocity = row(
            name=f'{prefix}velocity_hist',
            sizing_mode='stretch_width',
            children=[
                p_rear_vel_hist,
                p_rear_vel_stats])
        document.add_root(p_rear_travel_hist)
        document.add_root(p_rear_fft)
        document.add_root(p_rear_velocity)
        columns.extend(['r_thist', 'r_fft', 'r_vhist'])
    if suspension_count == 2:
        document.add_root(p_balance_compression)
        document.add_root(p_balance_rebound)
        columns.extend(['cbalance', 'rbalance'])

    # Some Bokeh models (like the description box or the map) need to be
    # dynamically initialized based on values in a particular Flask session.
    document.js_on_event(DocumentReady, CustomJS(
        args=dict(), code='SST.init_models();'))

    script, divs = components(document.roots, theme=dark_minimal_theme)
    components_data = dict(zip(columns, [session_id, script] + list(divs)))
    session_html = dataclass_from_dict(SessionHtml, components_data)

    db.session.add(session_html)
    db.session.commit()
