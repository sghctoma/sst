import numpy as np

from bokeh.models import ColumnDataSource
from bokeh.models.ranges import Range1d
from bokeh.models.tickers import FixedTicker
from bokeh.plotting import figure

from psst import Strokes


def _travel_velocity(strokes: Strokes, travel_max):
    ct, cv, rt, rv = [], [], [], []
    for c in strokes.Compressions:
        ct.append(c.Stat.MaxTravel / travel_max * 100)
        cv.append(c.Stat.MaxVelocity)
    for r in strokes.Rebounds:
        rt.append(r.Stat.MaxTravel / travel_max * 100)
        rv.append(r.Stat.MaxVelocity)

    ct = np.array(ct)
    cv = np.array(cv)
    rt = np.array(rt)
    rv = np.array(rv)
    cp = ct.argsort()
    rp = rt.argsort()
    return ct[cp], cv[cp], rt[rp], rv[rp]


def _balance_data(front_strokes: Strokes, rear_strokes: Strokes,
                  front_max: float, rear_max: float):
    fct, fcv = [], []
    for c in front_strokes.Compressions:
        fct.append(c.Stat.MaxTravel / front_max * 100)
        fcv.append(c.Stat.MaxVelocity)
    frt, frv = [], []
    for r in front_strokes.Rebounds:
        frt.append(r.Stat.MaxTravel / front_max * 100)
        frv.append(r.Stat.MaxVelocity)
    rct, rcv = [], []
    for c in front_strokes.Compressions:
        rct.append(c.Stat.MaxTravel / rear_max * 100)
        rcv.append(c.Stat.MaxVelocity)
    rrt, rrv = [], []
    for r in front_strokes.Rebounds:
        rrt.append(r.Stat.MaxTravel / rear_max * 100)
        rrv.append(r.Stat.MaxVelocity)

    fct, fcv, frt, frv = _travel_velocity(front_strokes, front_max)
    rct, rcv, rrt, rrv = _travel_velocity(rear_strokes, rear_max)

    fcp = np.poly1d(np.polyfit(fct, fcv, 1))
    frp = np.poly1d(np.polyfit(frt, frv, 1))
    rcp = np.poly1d(np.polyfit(rct, rcv, 1))
    rrp = np.poly1d(np.polyfit(rrt, rrv, 1))

    fc = dict(travel=fct, velocity=fcv, trend=[fcp(t) for t in fct])
    rc = dict(travel=rct, velocity=rcv, trend=[rcp(t) for t in rct])
    fr = dict(travel=frt, velocity=frv, trend=[frp(t) for t in frt])
    rr = dict(travel=rrt, velocity=rrv, trend=[rrp(t) for t in rrt])

    return fc, rc, fr, rr


def update_balance(pc: figure, pr: figure,
                   front_strokes: Strokes, rear_strokes: Strokes,
                   front_max: float, rear_max: float):
    ds_fc = pc.select_one('ds_fc')
    ds_rc = pc.select_one('ds_rc')
    ds_fr = pr.select_one('ds_fr')
    ds_rr = pr.select_one('ds_rr')
    ds_fc.data, ds_rc.data, ds_fr.data, ds_rr.data = _balance_data(
        front_strokes, rear_strokes, front_max, rear_max)
    pc.x_range = Range1d(0, np.fmax(
        ds_fc.data['travel'][-1], ds_rc.data['travel'][-1]))
    pr.x_range = Range1d(0, np.fmax(
        ds_fr.data['travel'][-1], ds_rr.data['travel'][-1]))


def balance_figures(front_strokes: Strokes, rear_strokes: Strokes,
                    front_max: float, rear_max: float,
                    front_color: tuple[str], rear_color: tuple[str]):
    fc, rc, fr, rr = _balance_data(front_strokes, rear_strokes,
                                   front_max, rear_max)
    front_compression_source = ColumnDataSource(name='ds_fc', data=fc)
    rear_compression_source = ColumnDataSource(name='ds_rc', data=rc)
    front_rebound_source = ColumnDataSource(name='ds_fr', data=fr)
    rear_rebound_source = ColumnDataSource(name='ds_rr', data=rr)

    p_compression = figure(
        name='balance_compression',
        title="Compression velocity balance",
        height=600,
        sizing_mode="stretch_width",
        toolbar_location=None,
        tools='',
        x_axis_label="Travel (%)",
        y_axis_label="Velocity (mm/s)",
        output_backend='webgl')
    p_compression.x_range = Range1d(
        0, np.fmax(fc['travel'][-1], rc['travel'][-1]))
    p_compression.xaxis.ticker = FixedTicker(ticks=list(range(0, 110, 10)))
    p_compression.circle(
        'travel', 'velocity',
        legend_label="Front",
        size=4,
        color=front_color,
        alpha=0.3,
        source=front_compression_source)
    p_compression.line(
        'travel', 'trend',
        line_width=2,
        color=front_color,
        source=front_compression_source)
    p_compression.circle(
        'travel', 'velocity',
        legend_label="Rear",
        size=4,
        color=rear_color,
        alpha=0.6,
        source=rear_compression_source)
    p_compression.line(
        'travel', 'trend',
        line_width=2,
        color=rear_color,
        source=rear_compression_source)
    p_compression.legend.location = 'top_left'

    p_rebound = figure(
        name='balance_rebound',
        title="Rebound velocity balance",
        height=600,
        sizing_mode="stretch_width",
        toolbar_location=None,
        tools='',
        x_axis_label="Travel (%)",
        y_axis_label="Velocity (mm/s)",
        output_backend='webgl')
    p_rebound.x_range = Range1d(0, np.fmax(fr['travel'][-1], rr['travel'][-1]))
    p_rebound.xaxis.ticker = FixedTicker(ticks=list(range(0, 110, 10)))
    p_rebound.y_range.flipped = True
    p_rebound.circle(
        'travel', 'velocity',
        legend_label="Front",
        size=4,
        color=front_color,
        alpha=0.3,
        source=front_rebound_source)
    p_rebound.line(
        'travel', 'trend',
        line_width=2,
        color=front_color,
        source=front_rebound_source)
    p_rebound.circle(
        'travel', 'velocity',
        legend_label="Rear",
        size=4,
        color=rear_color,
        alpha=0.6,
        source=rear_rebound_source)
    p_rebound.line(
        'travel', 'trend',
        line_width=2,
        color=rear_color,
        source=rear_rebound_source)
    p_rebound.legend.location = 'top_left'

    return p_compression, p_rebound
