from bokeh.models.ranges import Range1d
from bokeh.models.tickers import FixedTicker
import numpy as np

from bokeh.models import ColumnDataSource
from bokeh.plotting import figure


def strokes(velocity, travel=None, threshold=5):
    zero_crossings = np.where(np.diff(np.sign(velocity)))[0] + 1
    if len(zero_crossings) == 0:
        return [], []
    zero_crossings = np.insert(zero_crossings, 0, 0)
    zero_crossings = np.append(zero_crossings, len(velocity) - 1)
    compressions, rebounds = [], []
    for i in range(len(zero_crossings) - 1):
        start = zero_crossings[i]
        end = zero_crossings[i + 1]
        if start == end:
            continue
        if velocity[start] > 0:
            compressions.append((start, end))
        if velocity[start] < 0:
            rebounds.append((start, end))

    if travel is not None:
        compressions = [c for c in compressions if
                        travel[c[1]] - travel[c[0]] >= threshold]
        rebounds = [r for r in rebounds if
                    travel[r[0]] - travel[r[1]] >= threshold]
    return compressions, rebounds


def travel_velocity(travel, travel_max, velocity):
    compressions, rebounds = strokes(velocity, travel, travel_max * 0.025)
    ct, cv, rt, rv = [], [], [], []
    for c in compressions:
        v_max = np.max(velocity[c[0]:c[1]])
        ct.append(travel[c[1]] / travel_max * 100)
        cv.append(v_max)
    for r in rebounds:
        v_min = np.min(velocity[r[0]:r[1]])
        rt.append(travel[r[0]] / travel_max * 100)
        rv.append(v_min)
    ct = np.array(ct)
    cv = np.array(cv)
    rt = np.array(rt)
    rv = np.array(rv)
    cp = ct.argsort()
    rp = rt.argsort()
    return ct[cp], cv[cp], rt[rp], rv[rp]


def balance_data(front_travel, front_max, front_velocity,
                 rear_travel, rear_max, rear_velocity):
    fct, fcv, frt, frv = travel_velocity(
        front_travel, front_max, front_velocity)
    rct, rcv, rrt, rrv = travel_velocity(rear_travel, rear_max, rear_velocity)
    fcp = np.poly1d(np.polyfit(fct, fcv, 1))
    frp = np.poly1d(np.polyfit(frt, frv, 1))
    rcp = np.poly1d(np.polyfit(rct, rcv, 1))
    rrp = np.poly1d(np.polyfit(rrt, rrv, 1))

    fc = dict(travel=fct, velocity=fcv, trend=[fcp(t) for t in fct])
    rc = dict(travel=rct, velocity=rcv, trend=[rcp(t) for t in rct])
    fr = dict(travel=frt, velocity=frv, trend=[frp(t) for t in frt])
    rr = dict(travel=rrt, velocity=rrv, trend=[rrp(t) for t in rrt])

    return fc, rc, fr, rr


def update_balance(pc, pr, front_travel, front_max,
                   front_velocity, rear_travel, rear_max, rear_velocity):
    ds_fc = pc.select_one('ds_fc')
    ds_rc = pc.select_one('ds_rc')
    ds_fr = pr.select_one('ds_fr')
    ds_rr = pr.select_one('ds_rr')
    ds_fc.data, ds_rc.data, ds_fr.data, ds_rr.data = balance_data(
        front_travel, front_max, front_velocity,
        rear_travel, rear_max, rear_velocity)
    pc.x_range = Range1d(0, np.fmax(
        ds_fc.data['travel'][-1], ds_rc.data['travel'][-1]))
    pr.x_range = Range1d(0, np.fmax(
        ds_fr.data['travel'][-1], ds_rr.data['travel'][-1]))


def balance_figures(front_travel, front_max, front_velocity, front_color,
                    rear_travel, rear_max, rear_velocity, rear_color):
    fc, rc, fr, rr = balance_data(
        front_travel, front_max, front_velocity,
        rear_travel, rear_max, rear_velocity)
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
