#!/usr/bin/env python

import argparse
import msgpack

import numpy as np

from bokeh.events import DoubleTap, SelectionGeometry
from bokeh.io import curdoc
from bokeh.io import output_file, save
from bokeh.layouts import column, layout
from bokeh.models import ColumnDataSource
from bokeh.models.annotations import BoxAnnotation, ColorBar, Label, Span
from bokeh.models.axes import LinearAxis
from bokeh.models.callbacks import CustomJS
from bokeh.models.mappers import LinearColorMapper
from bokeh.models.ranges import Range1d
from bokeh.models.tickers import FixedTicker
from bokeh.models.tools import BoxSelectTool, WheelZoomTool
from bokeh.palettes import Spectral11
from bokeh.plotting import figure

from dataclasses import dataclass, fields as datafields
from pathlib import Path

from scipy.fft import rfft, rfftfreq
from scipy.stats import norm


def do_fft(travel, tick):
    wf = np.kaiser(len(travel), 5)

    balanced_travel = travel - np.mean(travel)
    balanced_travel_f = rfft(balanced_travel * wf)
    balanced_spectrum = np.abs(balanced_travel_f)

    freqs= rfftfreq(len(travel), tick)
    freqs = freqs[freqs <= 10] # cut off FFT graph at 10 Hz

    # TODO put a label that shows the most prominent frequencies
    #max_freq_idx = np.argpartition(balanced_spectrum, -1)[-1:]
    #print(f[max_freq_idx])

    return freqs, balanced_spectrum[:len(freqs)]

def group_(array):
    idx_sort = np.argsort(array)
    sorted_records_array = array[idx_sort]
    _, idx_start = np.unique(sorted_records_array, return_index=True)
    res = np.split(idx_sort, idx_start[1:])
    return res

def group(array, bins):
    dig = np.digitize(array, bins=bins) - 1
    idx_sort = np.argsort(dig)
    sorted_records_array = dig[idx_sort]
    uniq, idx_start = np.unique(sorted_records_array, return_index=True)
    split = np.split(idx_sort, idx_start[1:])
    res = []
    ui = 0
    for i in range(len(bins) - 1):
        if i in uniq:
            res.append(split[ui])
            ui += 1
        else:
            res.append(np.array([]))
    return res

def max_extension_intervals(travel, max_travel, sample_rate):
    travel_nz = travel < max_travel * 0.04
    # XXX: Maybe we should add a velocity threshold too.
    #velocity_nz = np.abs(velocity) < 200
    x = np.r_[False, (travel_nz), False]
    start = np.r_[False, ~x[:-1] & x[1:]]
    end = np.r_[x[:-1] & ~x[1:], False]
    # creating start-end pairs while filtering out single <threshold values
    me = np.where(start^end)[0] - 1
    me.shape = (-1, 2)
    diff = me[:,-1] - me[:,0]
    return me[diff>0.2*sample_rate] # return max extension intervals that are longer than 0.2s

def max_extensions_mask(max_extensions, length):
    l0 = max_extensions[:,[0]] <= np.arange(length)
    l1 = max_extensions[:,[1]] >= np.arange(length)
    return np.logical_not(np.any(l0&l1, axis=0))

def filter_jumps(max_extensions, velocity, sample_rate):
    v_check_interval = int(0.02 * sample_rate)
    if max_extensions[0][0] < v_check_interval: # beginning is not a jump
        max_extensions = max_extensions[1:]
    if max_extensions[-1][1] > len(velocity) - v_check_interval: # end is not a jumps
        max_extensions = max_extensions[:-1]

    jumps = []
    for me in max_extensions:
        v_before = np.mean(velocity[me[0]-v_check_interval:me[0]])
        v_after = np.mean(velocity[me[1]:me[1]+v_check_interval])
        if v_before < -200 and v_after > 1000: # if suspension speed is sufficiently large
            jumps.append(me)
    return jumps

def bottomouts(travel, max_travel):
    x = np.r_[False, (max_travel-travel<3), False]
    bo_start = np.r_[False, ~x[:-1] & x[1:]]
    return bo_start.nonzero()[0]

def add_velocity_stat_labels(velocity, mx, p):
    avgr = np.average(velocity[velocity < 0])
    maxr = np.min(velocity[velocity < 0])
    avgc = np.average(velocity[velocity > 0])
    maxc = np.max(velocity[velocity > 0])

    s_avgr = Span(location=avgr, dimension='width',
            line_color='gray', line_dash='dashed', line_width=2)
    s_maxr = Span(location=maxr, dimension='width',
            line_color='gray', line_dash='dashed', line_width=2)
    s_avgc = Span(location=avgc, dimension='width',
            line_color='gray', line_dash='dashed', line_width=2)
    s_maxc = Span(location=maxc, dimension='width',
            line_color='gray', line_dash='dashed', line_width=2)
    p.add_layout(s_avgr)
    p.add_layout(s_maxr)
    p.add_layout(s_avgc)
    p.add_layout(s_maxc)

    text_props = {
        'x': mx,
        'x_units': 'data',
        'y_units': 'data',
        'text_baseline': 'middle',
        'text_align': 'right',
        'text_font_size': '14px',
        'text_color': '#fefefe'}
    l_avgr = Label(y=avgr, text=f"avg. rebound vel.: {avgr:.1f} mm/s", y_offset=10, **text_props)
    l_maxr = Label(y=maxr, text=f"max. rebound vel.: {maxr:.1f} mm/s", y_offset=-10, **text_props)
    l_avgc = Label(y=avgc, text=f"avg. comp. vel.: {avgc:.1f} mm/s", y_offset=-10, **text_props)
    l_maxc = Label(y=maxc, text=f"max. comp. vel.: {maxc:.1f} mm/s", y_offset=10, **text_props)
    p.add_layout(l_avgr)
    p.add_layout(l_maxr)
    p.add_layout(l_avgc)
    p.add_layout(l_maxc)

def velocity_histogram_figure(dt, dv, velocity, mem, high_speed_threshold, title):
    step = dv.Bins[1] - dv.Bins[0]
    hist = np.zeros(((len(dt.Bins)-1)//2, len(dv.Bins)-1))
    for i in range(len(dv.Data)):
        if mem[i]:
            vbin = dv.Data[i]
            tbin = dt.Data[i] // 2
            hist[tbin][vbin] += 1
    hist = hist / np.count_nonzero(mem) * 100

    thist = np.transpose(hist)
    largest_bin = 0
    cutoff = []
    for i in range(len(thist)):
        sm = np.sum(thist[i])
        if sm > largest_bin:
            largest_bin = sm
        if sm > 0.1:
            cutoff.append(i)

    sd = {str(k): v for k,v in enumerate(hist)}
    sd['y'] = np.array(dv.Bins[:-1])+step/2
    source = ColumnDataSource(data=sd)
    hi, lo = dv.Bins[cutoff[-1]], dv.Bins[cutoff[0]]

    p = figure(
        title=title,
        height=500,
        y_range=[hi, lo],
        x_axis_label="Time (%)",
        y_axis_label='Speed (mm/s)',
        toolbar_location='above',
        tools='ypan,ywheel_zoom,reset',
        active_drag='ypan',
        active_scroll='ywheel_zoom',
        output_backend='webgl')
    p.x_range.start = 0
    palette = Spectral11[1:]
    p.hbar_stack([str(i) for i in range(len(hist))], y='y', height=step, color=palette, line_color='black', source=source)

    mu, std = norm.fit(velocity)
    ny = np.linspace(velocity.min(), velocity.max(), 1000)
    pdf = norm.pdf(ny, mu, std) * step * 100 
    p.line(pdf, ny, line_width=2, line_dash='dashed', color=Spectral11[-2])

    mapper = LinearColorMapper(palette=palette, low=0, high=100)
    color_bar = ColorBar(
        color_mapper=mapper,
        height=8,
        title="Travel (%)",
        ticker=FixedTicker(ticks=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]))
    p.add_layout(color_bar, 'above')

    lowspeed_box = BoxAnnotation(top=high_speed_threshold, bottom=-high_speed_threshold,
        left=0, fill_color='#FFFFFF', fill_alpha=0.1)
    p.add_layout(lowspeed_box)
    add_velocity_stat_labels(velocity[mem], largest_bin, p)
    return p

def add_travel_stat_labels(travel, max_travel, hist_max, p):
    avg = np.average(travel)
    mx = np.max(travel)
    bo = bottomouts(travel, max_travel)
    s_avg = Span(location=avg, dimension='width',
            line_color='gray', line_dash='dashed', line_width=2)
    s_max = Span(location=mx, dimension='width',
            line_color='gray', line_dash='dashed', line_width=2)
    p.add_layout(s_avg)
    p.add_layout(s_max)

    text_props = {
        'x': hist_max,
        'x_units': 'data',
        'y_units': 'data',
        'text_baseline': 'middle',
        'text_align': 'right',
        'text_font_size': '14px',
        'text_color': '#fefefe'}
    l_avg = Label(y=avg, text=f"avg.: {avg:.2f} mm ({avg/max_travel*100:.1f}%)", y_offset=-10, **text_props)
    l_max = Label(y=mx, text=f"max.: {mx:.2f} mm ({mx/max_travel*100:.1f}%) / {len(bo)} bottom outs", y_offset=10, **text_props)
    p.add_layout(l_avg)
    p.add_layout(l_max)

def travel_histogram_figure(digitized, travel, mem, color, title):
    bins = digitized.Bins
    max_travel = bins[-1]
    hist = np.zeros(len(bins)-1)
    for i in range(len(digitized.Data)):
        if mem[i]:
            hist[digitized.Data[i]] += 1

    hist = hist / len(digitized.Data) * 100
    p = figure(
        title=title,
        height=250,
        sizing_mode="stretch_width",
        x_axis_label="Time (%)",
        y_axis_label='Travel (mm)',
        toolbar_location='above',
        tools='ypan,ywheel_zoom,reset',
        active_drag='ypan',
        active_scroll='ywheel_zoom',
        output_backend='webgl')
    p.x_range.start = 0
    p.y_range.flipped = True
    p.hbar(y=bins[:-1], height=max_travel/(len(bins)-1), left=0, right=hist, color=color, line_color='black')
    add_travel_stat_labels(travel[mem], max_travel, np.max(hist), p)
    return p

def add_jump_labels(jumps, tick, p_travel):
    for j in jumps:
        t1 = j[0] * tick
        t2 = j[1] * tick
        b = BoxAnnotation(left=t1, right=t2, fill_color=Spectral11[-2], fill_alpha=0.2)
        p_travel.add_layout(b)
        l = Label(
            x=t1+(t2-t1)/2,
            y=30,
            x_units='data',
            y_units='screen',
            text_font_size='14px',
            text_color='#fefefe',
            text_align='center',
            text_baseline='middle',
            text=f"{t2-t1:.2f}s air")
        p_travel.add_layout(l)

def travel_figure(telemetry, front_color, rear_color):
    time = np.around(np.arange(0, len(telemetry.Front.Travel)) / telemetry.SampleRate, 4) 
    front_max = telemetry.Front.Calibration.MaxStroke
    rear_max = telemetry.Frame.MaxRearTravel

    source = ColumnDataSource(data=dict(
        t=time[::100],
        f=np.around(telemetry.Front.Travel, 4)[::100],
        r=np.around(telemetry.Rear.Travel, 4,)[::100],
    ))
    p = figure(
        title="Wheel travel",
        height=400,
        sizing_mode="stretch_width",
        toolbar_location='above',
        tools='xpan,reset,hover',
        active_drag='xpan',
        tooltips=[("elapsed time", "@t s"), ("front wheel", "@f mm"), ("rear wheel", "@r mm")],
        x_axis_label="Elapsed time (s)",
        y_axis_label="Travel (mm)",
        y_range=(front_max, 0),
        output_backend='webgl')

    p.yaxis.ticker = FixedTicker(ticks=np.linspace(0, front_max, 10))
    extra_y_axis = LinearAxis(y_range_name='rear')
    extra_y_axis.ticker = FixedTicker(ticks=np.linspace(0, rear_max, 10))
    p.extra_y_ranges = {'rear': Range1d(start=rear_max, end=0)}
    p.add_layout(LinearAxis(y_range_name='rear'), 'right')

    p.x_range = Range1d(0, time[-1], bounds='auto')

    l = p.line(
        't', 'f',
        legend_label="Front",
        line_width=2,
        color=front_color,
        source=source)
    p.line(
        't', 'r',
        y_range_name='rear',
        legend_label="Rear",
        line_width=2,
        color=rear_color,
        source=source)

    left_unselected = BoxAnnotation(left=p.x_range.start, right=p.x_range.start, fill_alpha=0.8, fill_color='#000000')
    right_unselected = BoxAnnotation(left=p.x_range.end, right=p.x_range.end, fill_alpha=0.8, fill_color='#000000')
    p.add_layout(left_unselected)
    p.add_layout(right_unselected)

    bs = BoxSelectTool(dimensions="width")
    p.add_tools(bs)
    p.js_on_event(DoubleTap, CustomJS(args=dict(lu=left_unselected, ru=right_unselected, end=p.x_range.end), code='''
        lu.right = 0;
        ru.left = end;
        lu.change.emit();
        ru.change.emit();
        '''))
    p.js_on_event(SelectionGeometry, CustomJS(args=dict(lu=left_unselected, ru=right_unselected), code='''
        const geometry = cb_obj['geometry'];
        lu.right = geometry['x0'];
        ru.left = geometry['x1'];
        lu.change.emit();
        ru.change.emit();

        //TODO: redraw FFTs and histograms
        '''))

    wz = WheelZoomTool(maintain_focus=False, dimensions='width')
    p.add_tools(wz)
    p.toolbar.active_scroll = wz
   
    p.hover.mode = 'vline'
    p.hover.renderers = [l]
    p.legend.location = 'bottom_right'
    p.legend.click_policy = 'hide'
    return p

def shock_wheel_figure(coeffs, max_travel, color):
    f = np.poly1d(np.flip(coeffs))
    p = figure(
        title="Shock - Wheel displacement",
        height=400,
        width=300,
        sizing_mode='fixed',
        toolbar_location=None,
        active_drag=None,
        active_scroll=None,
        tools='hover',
        active_inspect='hover',
        tooltips=[("shock stroke", "$x"), ("wheel travel", "$y")],
        x_axis_label="Shock Stroke (mm)",
        y_axis_label="Wheel Travel (mm)",
        output_backend='webgl')
    p.hover.mode = 'vline'

    x = np.arange(0, max_travel, 1)
    y = [f(t) for t in x]
    p.line(x, y, line_width=2, color=color)
    return p

def leverage_ratio_figure(wtlr, color):
    p = figure(
        title="Leverage Ratio",
        height=400,
        width=300,
        sizing_mode='fixed',
        toolbar_location=None,
        active_drag=None,
        active_scroll=None,
        tools='hover',
        active_inspect='hover',
        tooltips=[("wheel travel", "$x"), ("leverage ratio", "$y")],
        x_axis_label="Rear Wheel Travel (mm)",
        y_axis_label="Leverage Ratio",
        output_backend='webgl')
    p.hover.mode = 'vline'

    x = wtlr[:,0]
    y = wtlr[:,1]
    p.line(x, y, line_width=2, color=color)
    return p

def fft_figure(travel, tick, color, title):
    f, s = do_fft(travel, tick)
    p = figure(
        title=title,
        height=300,
        sizing_mode='stretch_width',
        toolbar_location='above',
        tools='xpan,reset,hover',
        tooltips="$x Hz",
        active_drag='xpan',
        x_axis_label="Fequency (Hz)",
        output_backend='webgl')
    wz = WheelZoomTool(maintain_focus=False, dimensions='width')
    p.add_tools(wz)
    p.toolbar.active_scroll = wz
    p.hover.mode = 'vline'
    p.yaxis.visible = False
    p.x_range = Range1d(0.05, 5.05, bounds=(0.05, 10.05))
    p.vbar(x=f, bottom=0, top=s, width=0.005, color=color)
    return p

def velocity_stats_figure(velocity, high_speed_threshold):
    count = len(velocity)
    hsr = np.count_nonzero(velocity < -high_speed_threshold) / count * 100
    lsr = np.count_nonzero((velocity > -high_speed_threshold) & (velocity < 0)) / count * 100
    zero = np.count_nonzero(velocity == 0) / count * 100
    lsc = np.count_nonzero((velocity > 0) & (velocity < high_speed_threshold)) / count * 100
    hsc = np.count_nonzero(velocity > high_speed_threshold) / count * 100

    source = ColumnDataSource(data=dict(
        x=[0],
        hsc=[hsc],
        lsc=[lsc],
        zero=[zero],
        lsr=[lsr],
        hsr=[hsr],
    ))
    p = figure(
        title="Speed zones\n\n\n\n", #XXX OK, this is fucking ugly, but setting title.standoff
                                     #    above a certain value somehow affects neighbouring figures...
        width=100,
        height=500,
        sizing_mode='fixed',
        tools='',
        toolbar_location=None)
    #p.title.standoff = 100
    p.grid.grid_line_color = None
    p.xaxis.visible = False
    p.yaxis.visible = False
    p.vbar_stack(['hsc', 'lsc', 'zero', 'lsr', 'hsr'], x='x',
        width=2,
        color=['#303030', '#282828', '#202020', '#282828', '#303030'],
        line_color=['gray']*5,
        source=source)

    text_props = {
        'x_units': 'data',
        'y_units': 'data',
        'x_offset': 5,
        'text_baseline': 'middle',
        'text_align': 'left',
        'text_font_size': '14px',
        'text_color': '#fefefe'}
    l_hsc = Label(x=0, y=hsc/2, text=f"HSC: {hsc:.2f}%", **text_props)
    l_lsc = Label(x=0, y=hsc+lsc/2, text=f"LSC: {lsc:.2f}%", **text_props)
    l_zero = Label(x=0, y=hsc+lsc+zero/2, text=f"NUL: {zero:.2f}%", **text_props)
    l_lsr = Label(x=0, y=hsc+lsc+zero+lsr/2, text=f"LSR: {lsr:.2f}%", **text_props)
    l_hsr = Label(x=0, y=hsc+lsc+zero+lsr+hsr/2, text=f"HSR: {hsr:.2f}%", **text_props)
    p.add_layout(l_hsr)
    p.add_layout(l_lsr)
    p.add_layout(l_zero)
    p.add_layout(l_lsc)
    p.add_layout(l_hsc)

    p.y_range = Range1d(0, 100)
    p.x_range = Range1d(0, 1)
    return p

@dataclass
class Digitized:
    Data: list
    Bins: list

@dataclass
class Frame:
    WheelLeverageRatio: list
    CoeffsShockWheel: list
    MaxRearTravel: float

@dataclass
class Calibration:
    ArmLength: float
    MaxDistance: float
    MaxStroke: float
    StartAngle: float

@dataclass
class Suspension:
    Calibration: Calibration
    Travel: list
    Velocity: list
    DigitizedTravel: Digitized
    DigitizedVelocity: Digitized

@dataclass
class Telemetry:
    Name: str
    Version: int
    SampleRate: int
    Front: Suspension
    Rear: Suspension
    Frame: Frame

# source: https://stackoverflow.com/a/54769644
def dataclass_from_dict(klass, d):
    try:
        fieldtypes = {f.name:f.type for f in datafields(klass)}
        return klass(**{f:dataclass_from_dict(fieldtypes[f],d[f]) for f in d})
    except:
        return d # Not a dataclass field

def parse_arguments():
    parser = argparse.ArgumentParser(description="Turn PSST to HTML")
    parser.add_argument('input', help="PSST file path")
    parser.add_argument('output', help="HTML file path", nargs='?')
    args = parser.parse_args()

    psst_file = args.input
    html_file = args.output
    if not html_file:
        html_file = Path(psst_file).with_suffix('.html')
    return psst_file, html_file

def main():
    psst_file, html_file = parse_arguments()
    telemetry = dataclass_from_dict(Telemetry, msgpack.unpackb(open(psst_file, 'rb').read()))

    high_speed_threshold = 100
    tick = 1.0 / telemetry.SampleRate # time step length in seconds

    front_travel = np.array(telemetry.Front.Travel)
    front_velocity = np.array(telemetry.Front.Velocity)

    rear_travel = np.array(telemetry.Rear.Travel)
    rear_velocity = np.array(telemetry.Rear.Velocity)

    curdoc().theme = 'dark_minimal'
    output_file(html_file, title=f"Sufni Suspention Telemetry Dashboard ({Path(psst_file).name})")
    front_color = Spectral11[1]
    rear_color = Spectral11[2]

    p_travel = travel_figure(telemetry, front_color, rear_color)
    me = max_extension_intervals(rear_travel, telemetry.Frame.MaxRearTravel, telemetry.SampleRate)
    front_mem = max_extensions_mask(me, len(front_travel))
    rear_mem = max_extensions_mask(me, len(rear_travel))
    jumps = filter_jumps(me, rear_velocity, telemetry.SampleRate)
    add_jump_labels(jumps, tick, p_travel)

    p_lr = leverage_ratio_figure(np.array(telemetry.Frame.WheelLeverageRatio), Spectral11[5])
    p_sw = shock_wheel_figure(telemetry.Frame.CoeffsShockWheel, telemetry.Rear.Calibration.MaxStroke, Spectral11[5])

    p_front_travel_hist = travel_histogram_figure(telemetry.Front.DigitizedTravel, front_travel, front_mem, front_color, "Travel histogram (front)")
    p_rear_travel_hist = travel_histogram_figure(telemetry.Rear.DigitizedTravel, rear_travel, rear_mem, rear_color, "Travel histogram (rear)")
    p_front_vel_hist = velocity_histogram_figure(telemetry.Front.DigitizedTravel, telemetry.Front.DigitizedVelocity,
        front_velocity, front_mem, high_speed_threshold, "Speed histogram (front)")
    p_rear_vel_hist = velocity_histogram_figure(telemetry.Rear.DigitizedTravel, telemetry.Rear.DigitizedVelocity,
        rear_velocity, rear_mem, high_speed_threshold, "Speed histogram (rear)")

    p_front_fft = fft_figure(front_travel[front_mem], tick, front_color, "Frequencies (front)")
    p_rear_fft = fft_figure(rear_travel[rear_mem], tick, rear_color, "Frequencies (rear)")

    p_vel_stats_front = velocity_stats_figure(front_velocity[front_mem], high_speed_threshold)
    p_vel_stats_rear = velocity_stats_figure(rear_velocity[rear_mem], high_speed_threshold)

    l = layout(
        children=[
            [p_travel, p_lr, p_sw],
            [column(p_front_travel_hist, p_rear_travel_hist), p_front_vel_hist, p_vel_stats_front, p_rear_vel_hist, p_vel_stats_rear],
            [p_front_fft, p_rear_fft],
        ],
        sizing_mode='stretch_width')
    save(l)

if __name__ == "__main__":
    main()
