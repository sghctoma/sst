import numpy as np

from typing import Any

from bokeh import events
from bokeh.models import ColumnDataSource
from bokeh.models.annotations import BoxAnnotation, ColorBar, Label, Span
from bokeh.models.callbacks import CustomJS
from bokeh.models.formatters import PrintfTickFormatter
from bokeh.models.mappers import LinearColorMapper
from bokeh.models.ranges import Range1d
from bokeh.models.tickers import FixedTicker, SingleIntervalTicker
from bokeh.models.tools import WheelZoomTool
from bokeh.palettes import Spectral11
from bokeh.plotting import figure
from scipy.stats import norm

from app.telemetry.psst import Strokes, Telemetry


TRAVEL_BINS_FOR_VELOCITY_HISTOGRAM = 10
HISTOGRAM_RANGE_MULTIPLIER = 1.5
HISTOGRAM_RANGE_HIGH = 2000
HISTOGRAM_RANGE_LOW = -HISTOGRAM_RANGE_HIGH


def velocity_figure(telemetry: Telemetry, lod: int,
                    front_color: tuple[str], rear_color: tuple[str]) -> figure:
    length = len(telemetry.Front.Velocity if telemetry.Front.Present else
                 telemetry.Rear.Velocity)
    time = np.around(np.arange(0, length, lod) / telemetry.SampleRate, 4)

    if telemetry.Front.Present:
        vf_lod = np.around(telemetry.Front.Velocity[::lod], 4) / 1000
    else:
        vf_lod = np.full(length, 0)[::lod]
    if telemetry.Rear.Present:
        vr_lod = np.around(telemetry.Rear.Velocity[::lod], 4) / 1000
    else:
        vr_lod = np.full(length, 0)[::lod]
    source = ColumnDataSource(data=dict(
        t=time,
        f=vf_lod,
        r=vr_lod,
    ))
    p = figure(
        name='velocity',
        title="Suspension velocity",
        height=275,
        min_border_left=50,
        min_border_right=50,
        sizing_mode="stretch_width",
        toolbar_location='above',
        tools='xpan,reset,hover',
        active_inspect=None,
        active_drag='xpan',
        tooltips=[("elapsed time", "@t s"),
                  ("front wheel", "@f m/s"),
                  ("rear wheel", "@r m/s")],
        x_axis_label="Elapsed time (s)",
        y_axis_label="Velocity (m/s)",
        output_backend='webgl')

    p.x_range = Range1d(0, time[-1], bounds='auto')

    line = p.line(
        't', 'f',
        legend_label="Front",
        line_width=2,
        color=front_color,
        source=source)
    p.line(
        't', 'r',
        legend_label="Rear",
        line_width=2,
        color=rear_color,
        source=source)
    p.legend.level = 'overlay'

    wz = WheelZoomTool(maintain_focus=False, dimensions='width')
    p.add_tools(wz)
    p.toolbar.active_scroll = wz

    p.hover.mode = 'vline'
    p.hover.renderers = [line]
    p.legend.location = 'bottom_right'
    p.legend.click_policy = 'hide'
    return p


def _normal_distribution_data(strokes: Strokes, velocity: list[float],
                              step: float) -> dict[str, np.array]:
    stroke_velocity = []
    for s in strokes.Compressions + strokes.Rebounds:
        stroke_velocity.extend(velocity[s.Start:s.End+1])
    stroke_velocity = np.array(stroke_velocity)
    mu, std = norm.fit(stroke_velocity)
    ny = np.linspace(stroke_velocity.min(), stroke_velocity.max(), 100)
    pdf = norm.pdf(ny, mu, std) * step * 100
    return dict(pdf=pdf.tolist(), ny=ny.tolist())


def _velocity_histogram_data(strokes: Strokes, hst: int, tbins: list[float],
                             vbins: list[float], vbins_fine: list[float]) -> (
                             dict[str, Any], float):
    step = vbins[1] - vbins[0]
    step_lowspeed = vbins_fine[1] - vbins_fine[0]
    divider = (len(tbins) - 1) // TRAVEL_BINS_FOR_VELOCITY_HISTOGRAM
    hist = np.zeros((TRAVEL_BINS_FOR_VELOCITY_HISTOGRAM, len(vbins) - 1))
    total_count = 0

    hist_lowspeed = np.zeros((TRAVEL_BINS_FOR_VELOCITY_HISTOGRAM,
                              len(vbins_fine) - 1))

    for s in strokes.Compressions + strokes.Rebounds:
        total_count += s.Stat.Count
        for i in range(s.Stat.Count):
            vbin = s.DigitizedVelocity[i]
            tbin = s.DigitizedTravel[i] // divider
            hist[tbin][vbin] += 1

            vbin_fine = s.FineDigitizedVelocity[i]
            if -(hst+step_lowspeed) <= vbins_fine[vbin_fine] < hst:
                hist_lowspeed[tbin][vbin_fine] += 1
    hist = hist / total_count * 100.0
    hist_lowspeed = hist_lowspeed / total_count * 100.0

    thist = np.transpose(hist)
    largest_bin = 0
    for i in range(len(thist)):
        sm = np.sum(thist[i])
        if sm > largest_bin:
            largest_bin = sm

    thist_lowspeed = np.transpose(hist_lowspeed)
    largest_bin_lowspeed = 0
    for i in range(len(thist_lowspeed)):
        sm = np.sum(thist_lowspeed[i])
        if sm > largest_bin_lowspeed:
            largest_bin_lowspeed = sm

    sd = {str(k): v.tolist() for k, v in enumerate(hist)}
    sd['y'] = (np.array(vbins[:-1]) + step / 2).tolist()

    sd_lowspeed = {str(k): v.tolist() for k, v in enumerate(hist_lowspeed)}
    sd_lowspeed['y'] = (np.array(vbins_fine[:-1]) + step_lowspeed / 2).tolist()

    return (sd, sd_lowspeed,
            HISTOGRAM_RANGE_MULTIPLIER * largest_bin,
            HISTOGRAM_RANGE_MULTIPLIER * largest_bin_lowspeed)


def velocity_histogram_figure(strokes: Strokes, velocity: list[float],
                              tbins: list[float], vbins: list[float],
                              vbins_fine: list[float], hst: int,
                              title: str, title_lowspeed: str) -> figure:
    step = vbins[1] - vbins[0]
    step_lowspeed = vbins_fine[1] - vbins_fine[0]
    sd, sd_lowspeed, mx, mx_lowspeed = _velocity_histogram_data(
        strokes, hst, tbins, vbins, vbins_fine)
    source = ColumnDataSource(name='ds_hist', data=sd)
    source_lowspeed = ColumnDataSource(name='ds_hist_lowspeed',
                                       data=sd_lowspeed)

    p = figure(
        title=title,
        height=600,
        sizing_mode='stretch_width',
        x_range=(0, mx),
        y_range=(HISTOGRAM_RANGE_HIGH, HISTOGRAM_RANGE_LOW),
        x_axis_label="Time (%)",
        y_axis_label='Speed (mm/s)',
        toolbar_location='above',
        tools='ypan,ywheel_zoom,reset',
        active_drag='ypan',
        output_backend='webgl')
    p.yaxis[0].formatter = PrintfTickFormatter(format="%5d")
    palette = Spectral11[1:]
    k = list(sd.keys())
    k.remove('y')
    p.hbar_stack(stackers=k, name='hb', y='y', height=step,
                 color=palette, line_color='black', fill_alpha=0.8,
                 source=source)

    source_normal = ColumnDataSource(
        name='ds_normal',
        data=_normal_distribution_data(strokes, velocity, step))
    p.line(x='pdf', y='ny', line_width=2, source=source_normal,
           line_dash='dashed', color=Spectral11[-2])

    p_lowspeed = figure(
        title=title_lowspeed,
        height=600,
        max_width=250,
        sizing_mode='stretch_width',
        x_range=(0, mx_lowspeed),
        y_range=(hst+100, -(hst+100)),
        x_axis_label="Time (%)",
        y_axis_label='Speed (mm/s)',
        toolbar_location=None,
        tools='',
        output_backend='webgl')
    p_lowspeed.yaxis[0].formatter = PrintfTickFormatter(format="%5d")
    k_lowspeed = list(sd_lowspeed.keys())
    k_lowspeed.remove('y')
    p_lowspeed.hbar_stack(stackers=k_lowspeed, name='hb_lowspeed', y='y',
                          height=step_lowspeed, color=palette,
                          line_color='black', fill_alpha=0.8,
                          source=source_lowspeed)
    p_lowspeed.xaxis.ticker = SingleIntervalTicker(interval=1.0)

    source_normal_lowspeed = ColumnDataSource(
        name='ds_normal_lowspeed',
        data=_normal_distribution_data(strokes, velocity, step_lowspeed))
    p_lowspeed.line(x='pdf', y='ny', line_width=2,
                    source=source_normal_lowspeed,
                    line_dash='dashed', color=Spectral11[-2])

    mapper = LinearColorMapper(palette=palette, low=0, high=100)
    color_bar = ColorBar(
        color_mapper=mapper,
        height=8,
        title="Travel (%)",
        ticker=FixedTicker(ticks=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]))
    p.add_layout(color_bar, 'above')
    p_lowspeed.add_layout(color_bar, 'above')

    lowspeed_box = BoxAnnotation(
        top=hst,
        bottom=-hst,
        left=0,
        right=None,  # XXX https://github.com/bokeh/bokeh/issues/13432
        fill_color='#FFFFFF',
        fill_alpha=0.1)
    p.add_layout(lowspeed_box)
    _add_velocity_stat_labels(p, strokes, mx)

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

    return p, p_lowspeed


def _add_velocity_stat_labels(p: figure, strokes: Strokes, mx):
    avgr, maxr, avgc, maxc = _velocity_stats(strokes)

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


def _velocity_stats(strokes: Strokes) -> (float, float, float, float):
    csum = 0
    ccount = 0
    maxc = 0
    for c in strokes.Compressions:
        csum += c.Stat.SumVelocity
        ccount += c.Stat.Count
        if c.Stat.MaxVelocity > maxc:
            maxc = c.Stat.MaxVelocity
    avgc = csum / ccount

    rsum = 0
    rcount = 0
    maxr = 0
    for r in strokes.Rebounds:
        rsum += r.Stat.SumVelocity
        rcount += r.Stat.Count
        if r.Stat.MaxVelocity < maxr:
            maxr = r.Stat.MaxVelocity
    avgr = rsum / rcount
    return avgr, maxr, avgc, maxc


def _velocity_band_stats(strokes: Strokes, velocity: list[float],
                         high_speed_threshold: float) -> (
                         float, float, float, float):
    velocity_ = np.array(velocity)
    total_count = 0
    lsc, hsc = 0, 0
    for c in strokes.Compressions:
        total_count += c.Stat.Count
        stroke_lsc = np.count_nonzero(
            velocity_[c.Start:c.End+1] < high_speed_threshold)
        lsc += stroke_lsc
        hsc += c.Stat.Count - stroke_lsc

    lsr, hsr = 0, 0
    for r in strokes.Rebounds:
        total_count += r.Stat.Count
        stroke_lsr = np.count_nonzero(
            velocity_[r.Start:r.End+1] > -high_speed_threshold)
        lsr += stroke_lsr
        hsr += r.Stat.Count - stroke_lsr

    lsc = lsc / total_count * 100.0
    hsc = hsc / total_count * 100.0
    lsr = lsr / total_count * 100.0
    hsr = hsr / total_count * 100.0

    return hsr, lsr, lsc, hsc


def velocity_band_stats_figure(strokes: Strokes, velocity: list[float],
                               high_speed_threshold: float) -> figure:
    hsr, lsr, lsc, hsc = _velocity_band_stats(strokes, velocity,
                                              high_speed_threshold)
    source = ColumnDataSource(name='ds_stats', data=dict(
        x=[0], hsc=[hsc], lsc=[lsc], lsr=[lsr], hsr=[hsr]))
    p = figure(
        # XXX OK, this is fucking ugly, but setting title.standoff
        #    above a certain value somehow affects neighbouring figures...
        title="Speed\nzones\n\n\n",
        width=70,
        height=600,
        x_range=(0, 1),
        y_range=(0, 1),
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

    p.y_range.end = hsr + lsr + lsc + hsc
    return p


def update_velocity_histogram(strokes: Strokes, velocity: list[float],
                              tbins: list[float], vbins: list[float],
                              vbins_fine: list[float],
                              high_speed_threshold: int):
    step = vbins[1] - vbins[0]
    step_lowspeed = vbins_fine[1] - vbins_fine[0]
    data, data_lowspeed, mx, mx_lowspeed = _velocity_histogram_data(
        strokes, high_speed_threshold, tbins, vbins, vbins_fine)
    avgr, maxr, avgc, maxc = _velocity_stats(strokes)
    return dict(
        data=data,
        mx=mx,
        data_lowspeed=data_lowspeed,
        mx_lowspeed=mx_lowspeed,
        normal_data=_normal_distribution_data(strokes, velocity, step),
        normal_data_lowspeed=_normal_distribution_data(strokes, velocity,
                                                       step_lowspeed),
        avgr=avgr,
        maxr=maxr,
        avgc=avgc,
        maxc=maxc,
        avgr_text=f"avg. rebound vel.: {avgr:.1f} mm/s",
        maxr_text=f"max. rebound vel.: {maxr:.1f} mm/s",
        avgc_text=f"avg. comp. vel.: {avgc:.1f} mm/s",
        maxc_text=f"max. comp. vel.: {maxc:.1f} mm/s",
    )


def update_velocity_band_stats(strokes: Strokes, velocity: list[float],
                               high_speed_threshold: float):
    hsr, lsr, lsc, hsc = _velocity_band_stats(strokes, velocity,
                                              high_speed_threshold)
    return dict(
        data=dict(x=[0], hsc=[hsc], lsc=[lsc], lsr=[lsr], hsr=[hsr]),
        hsr=hsr,
        lsr=lsr,
        lsc=lsc,
        hsc=hsc,
        hsr_text=f"HSR:\n{hsr:.2f}%",
        lsr_text=f"LSR:\n{lsr:.2f}%",
        lsc_text=f"LSC:\n{lsc:.2f}%",
        hsc_text=f"HSC:\n{hsc:.2f}%",
    )
