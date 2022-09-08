import numpy as np

from bokeh.models import ColumnDataSource
from bokeh.models.annotations import BoxAnnotation, ColorBar, Label, Span
from bokeh.models.mappers import LinearColorMapper
from bokeh.models.ranges import Range1d
from bokeh.models.tickers import FixedTicker
from bokeh.palettes import Spectral11
from bokeh.plotting import figure
from scipy.stats import norm

def velocity_histogram_figure(dt, dv, velocity, mask, high_speed_threshold, title):
    step = dv.Bins[1] - dv.Bins[0]
    hist = np.zeros(((len(dt.Bins)-1)//2, len(dv.Bins)-1))
    for i in range(len(dv.Data)):
        if mask[i]:
            vbin = dv.Data[i]
            tbin = dt.Data[i] // 2
            hist[tbin][vbin] += 1
    hist = hist / np.count_nonzero(mask) * 100

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
    add_velocity_stat_labels(velocity[mask], largest_bin, p)
    return p

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

def velocity_stats_figure(velocity, high_speed_threshold):
    count = len(velocity)
    hsr = np.count_nonzero(velocity < -high_speed_threshold) / count * 100
    lsr = np.count_nonzero((velocity > -high_speed_threshold) & (velocity < 0)) / count * 100
    lsc = np.count_nonzero((velocity > 0) & (velocity < high_speed_threshold)) / count * 100
    hsc = np.count_nonzero(velocity > high_speed_threshold) / count * 100

    source = ColumnDataSource(data=dict(
        x=[0],
        hsc=[hsc],
        lsc=[lsc],
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
    p.vbar_stack(['hsc', 'lsc', 'lsr', 'hsr'], x='x',
        width=2,
        color=['#303030', '#282828', '#282828', '#303030'],
        line_color=['gray']*4,
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
    l_lsr = Label(x=0, y=hsc+lsc+lsr/2, text=f"LSR: {lsr:.2f}%", **text_props)
    l_hsr = Label(x=0, y=hsc+lsc+lsr+hsr/2, text=f"HSR: {hsr:.2f}%", **text_props)
    p.add_layout(l_hsr)
    p.add_layout(l_lsr)
    p.add_layout(l_lsc)
    p.add_layout(l_hsc)

    p.y_range = Range1d(0, 100)
    p.x_range = Range1d(0, 1)
    return p

