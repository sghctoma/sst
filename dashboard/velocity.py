import numpy as np

from bokeh import events
from bokeh.models import ColumnDataSource
from bokeh.models.annotations import BoxAnnotation, ColorBar, Label, Span
from bokeh.models.callbacks import CustomJS
from bokeh.models.formatters import PrintfTickFormatter
from bokeh.models.mappers import LinearColorMapper
from bokeh.models.tickers import FixedTicker
from bokeh.palettes import Spectral11
from bokeh.plotting import figure
from scipy.stats import norm


HISTOGRAM_RANGE_MULTIPLIER = 1.5
HISTOGRAM_RANGE_HIGH = 2000
HISTOGRAM_RANGE_LOW = -HISTOGRAM_RANGE_HIGH


def normal_distribution_data(velocity, step):
    mu, std = norm.fit(velocity)
    ny = np.linspace(velocity.min(), velocity.max(), 100)
    pdf = norm.pdf(ny, mu, std) * step * 100
    return dict(pdf=pdf, ny=ny)


def velocity_histogram_data(dt, dv, mask, step):
    hist = np.zeros(((len(dt.Bins) - 1) // 2, len(dv.Bins) - 1))
    for i in range(len(dv.Data)):
        if mask[i]:
            vbin = dv.Data[i]
            tbin = dt.Data[i] // 2
            hist[tbin][vbin] += 1
    hist = hist / np.count_nonzero(mask) * 100

    thist = np.transpose(hist)
    largest_bin = 0
    for i in range(len(thist)):
        sm = np.sum(thist[i])
        if sm > largest_bin:
            largest_bin = sm

    sd = {str(k): v for k, v in enumerate(hist)}
    sd['y'] = np.array(dv.Bins[:-1]) + step / 2
    return sd, HISTOGRAM_RANGE_MULTIPLIER * largest_bin


def update_velocity_histogram(p, dt, dv, velocity, mask):
    ds = p.select_one('ds_hist')
    step = dv.Bins[1] - dv.Bins[0]
    sd, mx = velocity_histogram_data(dt, dv, mask, step)
    ds.data = sd
    p.x_range.start = 0
    p.x_range.end = mx
    p.y_range.start = HISTOGRAM_RANGE_HIGH
    p.y_range.end = HISTOGRAM_RANGE_LOW

    ds_normal = p.select_one('ds_normal')
    ds_normal.data = normal_distribution_data(velocity[mask], step)

    update_velocity_stats(p, velocity[mask], mx)


def velocity_histogram_figure(
        dt, dv, velocity, mask, high_speed_threshold, title):
    step = dv.Bins[1] - dv.Bins[0]
    sd, mx = velocity_histogram_data(dt, dv, mask, step)
    source = ColumnDataSource(name='ds_hist', data=sd)

    p = figure(
        title=title,
        height=606,
        sizing_mode='stretch_width',
        y_range=[HISTOGRAM_RANGE_HIGH, HISTOGRAM_RANGE_LOW],
        x_axis_label="Time (%)",
        y_axis_label='Speed (mm/s)',
        toolbar_location='above',
        tools='ypan,ywheel_zoom,reset',
        active_drag='ypan',
        output_backend='webgl')
    p.yaxis[0].formatter = PrintfTickFormatter(format="%5d")
    p.x_range.start = 0
    p.x_range.end = mx
    palette = Spectral11[1:]
    k = list(sd.keys())
    k.remove('y')
    p.hbar_stack(stackers=k, name='hb', y='y', height=step,
                 color=palette, line_color='black', fill_alpha=0.8,
                 source=source)

    source_normal = ColumnDataSource(
        name='ds_normal', data=normal_distribution_data(velocity[mask], step))
    p.line(x='pdf', y='ny', line_width=2, source=source_normal,
           line_dash='dashed', color=Spectral11[-2])

    mapper = LinearColorMapper(palette=palette, low=0, high=100)
    color_bar = ColorBar(
        color_mapper=mapper,
        height=8,
        title="Travel (%)",
        ticker=FixedTicker(ticks=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]))
    p.add_layout(color_bar, 'above')

    lowspeed_box = BoxAnnotation(
        top=high_speed_threshold,
        bottom=-high_speed_threshold,
        left=0,
        fill_color='#FFFFFF',
        fill_alpha=0.1)
    p.add_layout(lowspeed_box)
    add_velocity_stat_labels(velocity[mask], mx, p)


    js_update_label_positions = CustomJS(args=dict(p=p), code='''
            let top = p.y_range.end;
            let bottom = p.y_range.start;
            let maxr = p.select_one('s_maxr').location
            let maxc = p.select_one('s_maxc').location
            if (top > maxr && top < - 500) {
                p.select_one('l_maxr').y = top;
            }
            if (bottom < maxc && bottom > 500) {
                p.select_one('l_maxc').y = bottom;
            }
            ''')
    p.js_on_event(events.Pan, js_update_label_positions)
    p.js_on_event(events.MouseWheel, js_update_label_positions)

    return p


def add_velocity_stat_labels(velocity, mx, p):
    avgr, maxr, avgc, maxc = velocity_stats(velocity)

    s_avgr = Span(name='s_avgr', location=avgr, dimension='width',
                  line_color='gray', line_dash='dashed', line_width=2)
    s_maxr = Span(name='s_maxr', location=maxr, dimension='width',
                  line_color='gray', line_dash='dashed', line_width=2)
    s_avgc = Span(name='s_avgc', location=avgc, dimension='width',
                  line_color='gray', line_dash='dashed', line_width=2)
    s_maxc = Span(name='s_maxc', location=maxc, dimension='width',
                  line_color='gray', line_dash='dashed', line_width=2)
    p.add_layout(s_avgr)
    p.add_layout(s_maxr)
    p.add_layout(s_avgc)
    p.add_layout(s_maxc)

    top = p.y_range.end
    bottom = p.y_range.start

    text_props = {
        'x': mx,
        'x_units': 'data',
        'y_units': 'data',
        'text_baseline': 'middle',
        'text_align': 'right',
        'text_font_size': '14px',
        'text_color': '#fefefe'}
    l_avgr = Label(
        name='l_avgr',
        y=avgr,
        text=f"avg. rebound vel.: {avgr:.1f} mm/s",
        y_offset=10,
        **text_props)
    l_maxr = Label(
        name='l_maxr',
        y=np.fmax(
            top,
            maxr),
        text=f"max. rebound vel.: {maxr:.1f} mm/s",
        y_offset=-10,
        **text_props)
    l_avgc = Label(
        name='l_avgc',
        y=avgc,
        text=f"avg. comp. vel.: {avgc:.1f} mm/s",
        y_offset=-10,
        **text_props)
    l_maxc = Label(
        name='l_maxc',
        y=np.fmin(
            bottom,
            maxc),
        text=f"max. comp. vel.: {maxc:.1f} mm/s",
        y_offset=10,
        **text_props)
    p.add_layout(l_avgr)
    p.add_layout(l_maxr)
    p.add_layout(l_avgc)
    p.add_layout(l_maxc)


def velocity_stats(velocity):
    avgr = np.average(velocity[velocity < 0])
    maxr = np.min(velocity[velocity < 0])
    avgc = np.average(velocity[velocity > 0])
    maxc = np.max(velocity[velocity > 0])
    return avgr, maxr, avgc, maxc


def update_velocity_stats(p, velocity, mx):
    avgr, maxr, avgc, maxc = velocity_stats(velocity)
    top = p.y_range.end
    bottom = p.y_range.start

    p.select_one('s_avgr').location = avgr
    p.select_one('s_avgc').location = avgc
    p.select_one('s_maxr').location = maxr
    p.select_one('s_maxc').location = maxc

    l_avgr = p.select_one('l_avgr')
    l_avgr.x = mx
    l_avgr.y = avgr
    l_avgr.text = f"avg. rebound vel.: {avgr:.1f} mm/s"
    l_maxr = p.select_one('l_maxr')
    l_maxr.x = mx
    l_maxr.y = np.fmax(top, maxr)
    l_maxr.text = f"max. rebound vel.: {maxr:.1f} mm/s"
    l_avgc = p.select_one('l_avgc')
    l_avgc.x = mx
    l_avgc.y = avgc
    l_avgc.text = f"avg. comp. vel.: {avgc:.1f} mm/s"
    l_maxc = p.select_one('l_maxc')
    l_maxc.x = mx
    l_maxc.y = np.fmin(bottom, maxc)
    l_maxc.text = f"max. comp. vel.: {maxc:.1f} mm/s"


def velocity_band_stats(velocity, high_speed_threshold):
    count = len(velocity)
    hsr = np.count_nonzero(velocity < -high_speed_threshold) / count * 100
    lsr = np.count_nonzero((velocity > -high_speed_threshold)
                           & (velocity < 0)) / count * 100
    lsc = np.count_nonzero((velocity > 0) & (
        velocity < high_speed_threshold)) / count * 100
    hsc = np.count_nonzero(velocity > high_speed_threshold) / count * 100
    return hsr, lsr, lsc, hsc


def velocity_band_stats_figure(velocity, high_speed_threshold):
    hsr, lsr, lsc, hsc = velocity_band_stats(velocity, high_speed_threshold)
    source = ColumnDataSource(name='ds_stats', data=dict(
        x=[0], hsc=[hsc], lsc=[lsc], lsr=[lsr], hsr=[hsr]))
    p = figure(
        # XXX OK, this is fucking ugly, but setting title.standoff
        #    above a certain value somehow affects neighbouring figures...
        title="Speed\nzones\n\n\n",
        width=70,
        height=606,
        sizing_mode='fixed',
        tools='',
        toolbar_location=None)
    p.grid.grid_line_color = None
    p.xaxis.visible = False
    p.yaxis.visible = False
    p.vbar_stack(['hsc', 'lsc', 'lsr', 'hsr'], x='x',
                 width=2,
                 color=['#303030', '#282828', '#282828', '#303030'],
                 line_color=['gray'] * 4,
                 source=source)

    text_props = {
        'x_units': 'data',
        'y_units': 'data',
        'x_offset': 5,
        'text_baseline': 'middle',
        'text_align': 'left',
        'text_font_size': '14px',
        'text_color': '#fefefe'}
    l_hsr = Label(name='l_hsr', x=0, y=hsc + lsc + lsr + hsr / 2,
                  text=f" HSR:\n{hsr:.2f}%", **text_props)
    l_lsr = Label(name='l_lsr', x=0, y=hsc + lsc + lsr / 2,
                  text=f" LSR:\n{lsr:.2f}%", **text_props)
    l_lsc = Label(name='l_lsc', x=0, y=hsc + lsc / 2,
                  text=f" LSC:\n{lsc:.2f}%", **text_props)
    l_hsc = Label(name='l_hsc', x=0, y=hsc / 2,
                  text=f" HSC:\n{hsc:.2f}%", **text_props)
    p.add_layout(l_hsr)
    p.add_layout(l_lsr)
    p.add_layout(l_lsc)
    p.add_layout(l_hsc)

    p.y_range.start = 0
    p.y_range.end = hsr + lsr + lsc + hsc
    p.x_range.start = 0
    p.x_range.end = 1
    return p


def update_velocity_band_stats(p, velocity, high_speed_threshold):
    ds = p.select_one('ds_stats')
    hsr, lsr, lsc, hsc = velocity_band_stats(velocity, high_speed_threshold)
    ds.data = dict(x=[0], hsc=[hsc], lsc=[lsc], lsr=[lsr], hsr=[hsr])

    l_hsr = p.select_one('l_hsr')
    l_hsr.text = f"HSR:\n{hsr:.2f}%"
    l_hsr.y = hsc + lsc + lsr + hsr / 2
    l_lsr = p.select_one('l_lsr')
    l_lsr.text = f"LSR:\n{lsr:.2f}%"
    l_lsr.y = hsc + lsc + lsr / 2
    l_lsc = p.select_one('l_lsc')
    l_lsc.text = f"LSC:\n{lsc:.2f}%"
    l_lsc.y = hsc + lsc / 2
    l_hsc = p.select_one('l_hsc')
    l_hsc.text = f"HSC:\n{hsc:.2f}%"
    l_hsc.y = hsc / 2

    p.y_range.start = 0
    p.y_range.end = hsr + lsr + lsc + hsc
