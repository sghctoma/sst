#!/usr/bin/env python

import msgpack

import numpy as np

from bokeh.io import curdoc
from bokeh.io import output_file, save
from bokeh.layouts import column, layout
from bokeh.models import ColumnDataSource
from bokeh.models.annotations import BoxAnnotation, ColorBar, Label, Span
from bokeh.models.axes import LinearAxis
from bokeh.models.mappers import LinearColorMapper
from bokeh.models.ranges import Range1d
from bokeh.models.tickers import FixedTicker
from bokeh.palettes import Spectral9
from bokeh.plotting import figure

from scipy.fft import rfft, rfftfreq
from scipy.signal import savgol_filter


def do_fft(travel):
    wf = np.kaiser(len(travel), 5)

    balanced_travel = travel - np.mean(travel)
    balanced_travel_f = rfft(balanced_travel * wf)
    balanced_spectrum = np.abs(balanced_travel_f)

    freqs= rfftfreq(len(travel), 0.0002)
    freqs = freqs[freqs <= 10] # cut off FFT graph at 10 Hz

    # TODO put a label that shows the most prominent frequencies
    #max_freq_idx = np.argpartition(balanced_spectrum, -1)[-1:]
    #print(f[max_freq_idx])

    return freqs, balanced_spectrum[:len(freqs)]

def group(array):
    idx_sort = np.argsort(array)
    sorted_records_array = array[idx_sort]
    _, idx_start = np.unique(sorted_records_array, return_index=True)
    res = np.split(idx_sort, idx_start[1:])
    return res

def jumps(travel, max_travel):
    threshold = max_travel * 0.04
    x = np.r_[False, (np.array(travel)<threshold), False]
    start = np.r_[False, ~x[:-1] & x[1:]]
    end = np.r_[x[:-1] & ~x[1:], False]
    # creating start-end pairs while filtering out single <threshold values
    jumps = np.where(start^end)[0] - 1
    jumps.shape = (-1, 2)

    if jumps[0][0] == 0: # beginning is not a jump
        jumps = jumps[1:]

    filtered_jumps = []
    for j in jumps:
        if j[1] + 500 > len(travel): # skip if we are at the end
            continue
        if j[1] - j[0] > 1500: # if jump if longer than 0.3 seconds
            vbefore = (travel[j[0]] - travel[j[0]-200]) / 0.02
            vafter = (travel[j[1]+200] - travel[j[1]]) / 0.02
            if vbefore < -1000 and vafter > 1000: # if suspension speed is sufficiently large
                filtered_jumps.append((j[0], j[1]))
    return filtered_jumps

def bottomouts(travel, max_travel):
    x = np.r_[False, (max_travel-travel<3), False]
    bo_start = np.r_[False, ~x[:-1] & x[1:]]
    return bo_start.nonzero()[0]

def hist_velocity(velocity, travel, max_travel, step):
    mn = int(((velocity.min() // step) - 1) * step)
    mx = int(((velocity.max() // step) + 1) * step)
    bins = list(range(mn, mx, step))
    dig = np.digitize(velocity, bins=list(range(mn, mx, step))) - 1

    data = []
    idx_groups = group(dig)
    if (max_travel % 10 == 0):
        mx = max_travel
    else:
        mx = (max_travel // 10 + 1) * 10

    cutoff = []
    travel_bins = np.linspace(0, mx, 10)
    for g in idx_groups:
        t = travel[g]
        th, _ = np.histogram(t, bins=travel_bins)
        th = th / len(velocity) * 100
        data.append(th)
        if len(t)/len(travel) > 0.001:
            cutoff.append(bins[len(data)])

    data = np.transpose(np.array(data))

    data_dict = dict(y = bins[1:])
    xs = []
    for i in range(len(data)):
        xs.append(f'x{i}')
        data_dict[f'x{i}'] = data[i]

    return xs, travel_bins, ColumnDataSource(data=data_dict), cutoff[0], cutoff[-1]

def add_velocity_stat_labels(velocity, p):
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
        'x': 30,
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

def velocity_histogram_figure(velocity, travel, max_travel, high_speed_threshold, title):
    step = 10
    xs, tbins, source, lo, hi = hist_velocity(velocity, travel, max_travel, step)
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
    p.hbar_stack(xs, y='y', height=step, color=Spectral9, line_color='black', source=source)

    mapper = LinearColorMapper(palette=Spectral9, low=0, high=tbins[-1])
    color_bar = ColorBar(
        color_mapper=mapper,
        height=8,
        title="Travel (mm)",
        ticker=FixedTicker(ticks=tbins))
    p.add_layout(color_bar, 'above')

    lowspeed_box = BoxAnnotation(top=high_speed_threshold, bottom=-high_speed_threshold,
        left=0, fill_color='#FFFFFF', fill_alpha=0.1)
    p.add_layout(lowspeed_box)
    add_velocity_stat_labels(velocity, p)
    return p

def add_travel_stat_labels(travel, max_travel, p):
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
        'x': np.max(hist),
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

def travel_histogram_figure(travel, max_travel, color, title):
    hist, bins = np.histogram(travel, bins=np.arange(0, max_travel+max_travel/20, max_travel/20))
    hist = hist / len(travel) * 100
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
    p.hbar(y=bins[:-1], height=max_travel/20, left=0, right=hist, color=color, line_color='black')
    add_travel_stat_labels(travel, max_travel, p)
    return p

def add_jump_labels(travel, max_travel):
    #TODO: Calculate jumps from both front and rear travel.
    j_rear = jumps(travel, max_travel)
    for j in j_rear:
        t1 = j[0] * 0.0002
        t2 = j[1] * 0.0002
        b = BoxAnnotation(left=t1, right=t2, fill_color=Spectral9[-1], fill_alpha=0.2)
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
            text=f"{t2-t1:.2f}s jump")
        p_travel.add_layout(l)

def travel_figure(telemetry, front_color, rear_color):
    p_travel = figure(
        title="Suspension travel",
        height=400,
        sizing_mode="stretch_width",
        toolbar_location='above',
        tools='xpan,xwheel_zoom,xzoom_in,xzoom_out,reset',
        active_drag='xpan',
        active_scroll='xwheel_zoom',
        x_axis_label="Elapsed time (s)",
        y_axis_label="Travel (mm)",
        y_range=(telemetry['ForkCalibration']['MaxTravel'], 0),
        output_backend='webgl')

    front_max = telemetry['ForkCalibration']['MaxTravel']
    rear_max = telemetry['MaxWheelTravel']
    p_travel.yaxis.ticker = FixedTicker(ticks=np.linspace(0, front_max, 10))
    extra_y_axis = LinearAxis(y_range_name='rear')
    extra_y_axis.ticker = FixedTicker(ticks=np.linspace(0, rear_max, 10))
    p_travel.extra_y_ranges = {'rear': Range1d(start=rear_max, end=0)}
    p_travel.add_layout(LinearAxis(y_range_name='rear'), 'right')
    p_travel.x_range.start = 0
    p_travel.x_range.end = telemetry['Time'][-1]

    p_travel.line(
        np.around(telemetry['Time'], 4)[::100],
        np.around(telemetry['FrontTravel'], 4)[::100],
        legend_label="Front travel",
        line_width=2,
        color=front_color)
    p_travel.line(
        np.around(telemetry['Time'], 4)[::100],
        np.around(telemetry['RearTravel'], 4)[::100],
        y_range_name='rear',
        legend_label="Rear travel",
        line_width=2,
        color=rear_color)
    p_travel.legend.location = 'bottom_right'
    p_travel.legend.click_policy = 'hide'
    add_jump_labels(telemetry['RearTravel'], telemetry['MaxWheelTravel'])
    return p_travel

def shock_wheel_figure(coeffs, max_travel, color):
    f = np.poly1d(np.flip(coeffs))
    p = figure(
        title="Shock - Wheel Travel",
        height=400,
        width=300,
        sizing_mode='fixed',
        toolbar_location=None,
        active_drag=None,
        active_scroll=None,
        tools='hover',
        active_inspect='hover',
        tooltips=[("shock travel", "$x"), ("wheel travel", "$y")],
        x_axis_label="Shock Travel (mm)",
        y_axis_label="Wheel Travel (mm)",
        output_backend='webgl')

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

    x = wtlr[:,0]
    y = wtlr[:,1]
    p.line(x, y, line_width=2, color=color)
    return p

def fft_figure(travel, color, title):
    f, s = do_fft(travel)
    p_fft = figure(
        title=title,
        height=300,
        sizing_mode='stretch_width',
        toolbar_location='above',
        tools='xpan,xwheel_zoom,xzoom_in,xzoom_out,reset',
        active_drag='xpan',
        active_scroll='xwheel_zoom',
        x_axis_label="Fequency (Hz)",
        output_backend='webgl')
    p_fft.yaxis.visible = False
    p_fft.x_range.start = -0.1
    p_fft.x_range.end = 10.1
    p_fft.vbar(x=f, bottom=0, top=s, width=0.005, color=color)
    return p_fft

def velocity_stats_fugure(velocity, high_speed_threshold):
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

    p.y_range.start = 0
    p.y_range.end = 100
    p.x_range.start = 0
    p.x_range.end = 1
    return p

# ------

telemetry = msgpack.unpackb(open('/home/sghctoma/projects/sst/sample_data/20220724/00101.PSST', 'rb').read())

front_travel = np.array(telemetry['FrontTravel'])
front_travel[front_travel<0] = 0
front_travel_smooth = savgol_filter(front_travel, 51, 3)
front_velocity = np.gradient(front_travel_smooth, 0.0002)
front_max = telemetry['ForkCalibration']['MaxTravel']

rear_travel = np.array(telemetry['RearTravel'])
rear_travel[rear_travel<0] = 0
rear_travel_smooth = savgol_filter(rear_travel, 51, 3)
rear_velocity = np.gradient(rear_travel_smooth, 0.0002)
rear_max = telemetry['MaxWheelTravel']

# ------

curdoc().theme = 'dark_minimal'
output_file("stacked_split.html")

front_color = Spectral9[0]
rear_color = Spectral9[1]

p_travel = travel_figure(telemetry, front_color, rear_color)
p_lr = leverage_ratio_figure(np.array(telemetry['WheelLeverageRatio']), Spectral9[4])
p_sw = shock_wheel_figure(telemetry['CoeffsShockWheel'], telemetry['ShockCalibration']['MaxTravel'], Spectral9[4])

p_front_vel_hist = velocity_histogram_figure(front_velocity, front_travel, front_max, 400, "Speed histogram (front)")
p_rear_vel_hist = velocity_histogram_figure(rear_velocity, rear_travel, rear_max, 400, "Speed histogram (rear)")
p_front_travel_hist = travel_histogram_figure(front_travel, front_max, front_color, "Travel histogram (front)")
p_rear_travel_hist = travel_histogram_figure(rear_travel, rear_max, rear_color, "Travel histogram (rear)")

p_front_fft = fft_figure(front_travel, front_color, "Frequencies (front)")
p_rear_fft = fft_figure(rear_travel, rear_color, "Frequencies (rear)")

p_vel_stats_front = velocity_stats_fugure(front_velocity, 400)
p_vel_stats_rear = velocity_stats_fugure(rear_velocity, 400)

l = layout(
    children=[
        [p_travel, p_lr, p_sw],
        [column(p_front_travel_hist, p_rear_travel_hist), p_front_vel_hist, p_vel_stats_front, p_rear_vel_hist, p_vel_stats_rear],
        [p_front_fft, p_rear_fft],
    ],
    sizing_mode='stretch_width')
save(l)
