import numpy as np

from typing import Any

from bokeh.models import ColumnDataSource
from bokeh.models.tickers import FixedTicker
from bokeh.plotting import figure

from app.telemetry.psst import Stroke


def _travel_velocity(strokes: list[Stroke], travel_max) -> (
                     np.array, np.array):
    t, v = [], []
    for s in strokes:
        t.append(s.Stat.MaxTravel / travel_max * 100)
        v.append(s.Stat.MaxVelocity)

    t = np.array(t)
    v = np.array(v)
    p = t.argsort()
    return t[p], v[p]


def _balance_data(front_strokes: list[Stroke], rear_strokes: list[Stroke],
                  front_max: float, rear_max: float) -> (
                  dict[str, Any], dict[str, Any]):
    ft, fv = _travel_velocity(front_strokes, front_max)
    rt, rv = _travel_velocity(rear_strokes, rear_max)

    fp = np.poly1d(np.polyfit(ft, fv, 1))
    rp = np.poly1d(np.polyfit(rt, rv, 1))

    f = dict(travel=ft.tolist(), velocity=fv.tolist(),
             trend=[fp(t) for t in ft])
    r = dict(travel=rt.tolist(), velocity=rv.tolist(),
             trend=[rp(t) for t in rt])

    return f, r


def balance_figure(front_strokes: list[Stroke], rear_strokes: list[Stroke],
                   front_max: float, rear_max: float, flipped: bool,
                   front_color: tuple[str], rear_color: tuple[str],
                   name: str, title: str) -> (figure):
    f, r = _balance_data(front_strokes, rear_strokes, front_max, rear_max)
    front_source = ColumnDataSource(name='ds_f', data=f)
    rear_source = ColumnDataSource(name='ds_r', data=r)

    p = figure(
        name=name,
        title=title,
        height=600,
        x_range=(0, np.fmax(f['travel'][-1], r['travel'][-1])),
        sizing_mode="stretch_width",
        toolbar_location=None,
        tools='',
        x_axis_label="Travel (%)",
        y_axis_label="Velocity (mm/s)",
        output_backend='webgl')
    p.xaxis.ticker = FixedTicker(ticks=list(range(0, 110, 10)))
    p.y_range.flipped = flipped
    p.circle(
        'travel', 'velocity',
        legend_label="Front",
        size=4,
        color=front_color,
        alpha=0.3,
        source=front_source)
    p.line(
        'travel', 'trend',
        line_width=2,
        color=front_color,
        source=front_source)
    p.circle(
        'travel', 'velocity',
        legend_label="Rear",
        size=4,
        color=rear_color,
        alpha=0.6,
        source=rear_source)
    p.line(
        'travel', 'trend',
        line_width=2,
        color=rear_color,
        source=rear_source)
    p.legend.location = 'top_left'

    return p


def update_balance(front_strokes: list[Stroke], rear_strokes: list[Stroke],
                   front_max: float, rear_max: float):
    f_data, r_data = _balance_data(
        front_strokes, rear_strokes, front_max, rear_max)
    return dict(
        f_data=f_data,
        r_data=r_data,
        range_end=np.fmax(f_data['travel'][-1], r_data['travel'][-1])
    )
