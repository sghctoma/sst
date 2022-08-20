#!/usr/bin/env python

import msgpack

import numpy as np

from bokeh.io import curdoc
from bokeh.io import output_file, save
from bokeh.layouts import column, layout
from bokeh.models import ColumnDataSource
from bokeh.models.annotations import BoxAnnotation, ColorBar
from bokeh.models.axes import LinearAxis
from bokeh.models.mappers import LinearColorMapper
from bokeh.models.ranges import Range1d
from bokeh.models.tickers import FixedTicker
from bokeh.palettes import Spectral9
from bokeh.plotting import figure
from bokeh.transform import dodge

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

def bottomouts(travel, max_travel):
    x = np.r_[False, (max_travel-travel<3), False]
    bo_start = np.r_[False, ~x[:-1] & x[1:]]
    return bo_start.nonzero()[0]

def hist_velocity(velocity, travel, max_travel):
    step = 100
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

def velocity_histogram_figure(velocity, travel, max_travel, title):
    xs, tbins, source, lo, hi = hist_velocity(velocity, travel, max_travel)
    p = figure(
        title=title,
        height=500,
        y_range=[hi, lo],
        x_axis_label="Time (%)",
        y_axis_label='Velocity (mm/s)',
        toolbar_location='above',
        tools='ypan,ywheel_zoom,reset',
        active_drag='ypan',
        active_scroll='ywheel_zoom',
        output_backend='webgl')
    p.x_range.start = 0
    p.hbar_stack(xs, y='y', height=100, color=Spectral9, line_color='black', source=source)

    mapper = LinearColorMapper(palette=Spectral9[::-1], low=tbins[-1], high=0)
    color_bar = ColorBar(
        color_mapper=mapper,
        width=8,
        title="Travel (mm)",
        ticker=FixedTicker(ticks=tbins))
    p.add_layout(color_bar, 'right')

    lowspeed_box = BoxAnnotation(top=400, bottom=-400,
        left=0, fill_color='#FFFFFF', fill_alpha=0.1)
    p.add_layout(lowspeed_box)
    return p

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
    return p

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

def statistics_figure(f_travel, r_travel, f_max_travel, r_max_travel, f_velocity, r_velocity):
    high_speed_threshold = 400

    f_count = len(f_velocity)
    f_avgr = np.average(f_velocity[f_velocity < 0])
    f_maxr = np.min(f_velocity[f_velocity < 0])
    f_hsr = np.count_nonzero(f_velocity < -high_speed_threshold) / f_count * 100
    f_lsr = np.count_nonzero((f_velocity > -high_speed_threshold) & (f_velocity < 0)) / f_count * 100
    f_avgc = np.average(f_velocity[f_velocity > 0])
    f_maxc = np.max(f_velocity[f_velocity > 0])
    f_lsc = np.count_nonzero((f_velocity > 0) & (f_velocity < high_speed_threshold)) / f_count * 100
    f_hsc = np.count_nonzero(f_velocity > high_speed_threshold) / f_count * 100

    r_count = len(r_velocity)
    r_avgr = np.average(r_velocity[r_velocity < 0])
    r_maxr = np.min(r_velocity[r_velocity < 0])
    r_hsr = np.count_nonzero(r_velocity < -high_speed_threshold) / r_count * 100
    r_lsr = np.count_nonzero((r_velocity > -high_speed_threshold) & (r_velocity < 0)) / r_count * 100
    r_avgc = np.average(r_velocity[r_velocity > 0])
    r_maxc = np.max(r_velocity[r_velocity > 0])
    r_lsc = np.count_nonzero((r_velocity > 0) & (r_velocity < high_speed_threshold)) / r_count * 100
    r_hsc = np.count_nonzero(r_velocity > high_speed_threshold) / r_count * 100

    f_max = np.max(f_travel)
    r_max = np.max(r_travel)
    f_avg = np.average(f_travel)
    r_avg = np.average(r_travel)
    f_bo = bottomouts(f_travel, f_max_travel)
    r_bo = bottomouts(r_travel, r_max_travel)

    data = dict(
        value = [
            "Max. Travel", f"{f_max:.2f} mm ({f_max/f_max_travel*100:.1f} %)", f"{r_max:.2f} mm ({r_max/r_max_travel*100:.1f} %)",
            "Avg. Travel", f"{f_avg:.2f} mm ({f_avg/f_max_travel*100:.1f} %)", f"{r_avg:.2f} mm ({r_avg/r_max_travel*100:.1f} %) ",
            "Bottom Outs", f"{len(f_bo)}", f"{len(r_bo)}",
            "Avg. Rebound Vel.", f"{f_avgr:.2f} mm/s", f"{r_avgr:.2f} mm/s",
            "Max. Rebound Vel.", f"{f_maxr:.2f} mm/s", f"{r_maxr:.2f} mm/s",
            "HSR (% of R time)", f"{f_hsr:.2f} %", f"{r_hsr:.2f} %",
            "LSR (% of R time)", f"{f_lsr:.2f} %", f"{r_lsr:.2f} %",
            "Avg. Comp. Vel.", f"{f_avgc:.2f} mm/s", f"{r_avgc:.2f} mm/s",
            "Max. Comp. Vel.", f"{f_maxc:.2f} mm/s", f"{r_maxc:.2f} mm/s",
            "HSC (% of C time)", f"{f_hsc:.2f} %", f"{r_hsc:.2f} %",
            "LSC (% of C time)", f"{f_lsc:.2f} %", f"{r_lsc:.2f} %"],
        group = ["Statistic", "Front", "Rear"] * 11,
        statistic = [str(i//3) for i in range(33)])
    source = ColumnDataSource(data=data)

    p = figure(
        title="Statistics",
        width=500,
        height=400,
        x_range=["Statistic", "Front", "Rear"],
        y_range=["9", "10", "6", "5", "8", "4", "7", "3", "2", "1", "0"],
        sizing_mode='fixed',
        toolbar_location=None)

    x = dodge("group", -0.4, range=p.x_range)
    p.text(x=x, y='statistic', text='value', source=source,
            text_align='left', text_baseline='middle', text_color='white')

    p.grid.grid_line_color = None
    p.axis.major_label_standoff = 10
    p.yaxis.visible = False
    return p

# ------

telemetry = msgpack.unpackb(open('/home/sghctoma/projects/sst/sample_data/20220724/00097.PSST', 'rb').read())

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

p_front_vel_hist = velocity_histogram_figure(front_velocity, front_travel, front_max, "Front velocity histogram")
p_rear_vel_hist = velocity_histogram_figure(rear_velocity, rear_travel, rear_max, "Rear velocity histogram")
p_front_travel_hist = travel_histogram_figure(front_travel, front_max, front_color, "Front travel histogram")
p_rear_travel_hist = travel_histogram_figure(rear_travel, rear_max, rear_color, "Rear travel histogram")

p_front_fft = fft_figure(front_travel, front_color, "Frequencies in front travel")
p_rear_fft = fft_figure(rear_travel, rear_color, "Frequencies in rear travel")

p_statistics = statistics_figure(front_travel, rear_travel, front_max, rear_max, front_velocity, rear_velocity)

l = layout(
    children=[
        [p_travel, p_statistics, p_lr, p_sw],
        [column(p_front_travel_hist, p_rear_travel_hist), p_front_vel_hist, p_rear_vel_hist],
        [p_front_fft, p_rear_fft],
    ],
    sizing_mode='stretch_width')
save(l)
