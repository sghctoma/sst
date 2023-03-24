import numpy as np

from bokeh.events import DoubleTap, SelectionGeometry
from bokeh.models import ColumnDataSource
from bokeh.models.annotations import BoxAnnotation, Label, Span
from bokeh.models.axes import LinearAxis
from bokeh.models.callbacks import CustomJS
from bokeh.models.ranges import Range1d
from bokeh.models.tickers import FixedTicker
from bokeh.models.tools import BoxSelectTool, CrosshairTool, WheelZoomTool
from bokeh.palettes import Spectral11
from bokeh.plotting import figure

from psst import Airtime, Strokes, Telemetry


HISTOGRAM_RANGE_MULTIPLIER = 1.3


def travel_figure(telemetry: Telemetry, lod: int,
                  front_color: tuple[str], rear_color: tuple[str]) -> figure:
    length = len(telemetry.Front.Travel if telemetry.Front.Present else
                 telemetry.Rear.Travel)
    time = np.around(np.arange(0, length, lod) / telemetry.SampleRate, 4)
    front_max = telemetry.Front.Calibration.MaxStroke
    rear_max = telemetry.Linkage.MaxRearTravel

    if telemetry.Front.Present:
        tf_lod = np.around(telemetry.Front.Travel[::lod], 4)
    else:
        tf_lod = np.full(length, 0)[::lod]
    if telemetry.Rear.Present:
        tr_lod = np.around(telemetry.Rear.Travel[::lod], 4)
    else:
        tr_lod = np.full(length, 0)[::lod]
    source = ColumnDataSource(data=dict(t=time, f=tf_lod, r=tr_lod,))
    p = figure(
        name='travel',
        title="Wheel travel",
        height=400,
        min_border_left=50,
        min_border_right=50,
        sizing_mode="stretch_width",
        toolbar_location='above',
        tools='xpan,reset,hover',
        active_inspect=None,
        active_drag='xpan',
        tooltips=[("elapsed time", "@t s"),
                  ("front wheel", "@f mm"),
                  ("rear wheel", "@r mm")],
        x_axis_label="Elapsed time (s)",
        y_axis_label="Travel (mm)",
        y_range=(front_max, 0),
        output_backend='webgl')

    _add_airtime_labels(p, telemetry.Airtimes)

    p.yaxis.ticker = FixedTicker(ticks=np.linspace(0, front_max, 10))
    p.extra_y_ranges = {'rear': Range1d(start=rear_max, end=0)}
    p.add_layout(LinearAxis(y_range_name='rear'), 'right')

    p.x_range = Range1d(0, time[-1], bounds='auto')

    line = p.line(
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
    p.legend.level = 'overlay'

    left_unselected = BoxAnnotation(
        left=p.x_range.start,
        right=p.x_range.start,
        fill_alpha=0.8,
        fill_color='#000000')
    right_unselected = BoxAnnotation(
        left=p.x_range.end,
        right=p.x_range.end,
        fill_alpha=0.8,
        fill_color='#000000')
    p.add_layout(left_unselected)
    p.add_layout(right_unselected)

    bs = BoxSelectTool(dimensions="width")
    p.add_tools(bs)
    p.js_on_event(
        DoubleTap,
        CustomJS(
            args=dict(
                lu=left_unselected,
                ru=right_unselected,
                end=p.x_range.end),
            code='''
                 lu.right = 0;
                 ru.left = end;
                 lu.change.emit();
                 ru.change.emit();
                 '''))
    p.js_on_event(
        SelectionGeometry,
        CustomJS(
            args=dict(
                lu=left_unselected,
                ru=right_unselected),
            code='''
                 const geometry = cb_obj['geometry'];
                 lu.right = geometry['x0'];
                 ru.left = geometry['x1'];
                 lu.change.emit();
                 ru.change.emit();
                 '''))

    wz = WheelZoomTool(maintain_focus=False, dimensions='width')
    p.add_tools(wz)
    p.toolbar.active_scroll = wz

    ch = CrosshairTool(dimensions='height', line_color='#d0d0d0')
    p.add_tools(ch)
    p.toolbar.active_inspect = ch

    p.hover.mode = 'vline'
    p.hover.line_policy = 'none'
    p.hover.show_arrow = False
    p.hover.renderers = [line]
    p.legend.location = 'bottom_right'
    p.legend.click_policy = 'hide'
    return p


def _travel_histogram_data(strokes: Strokes, bins: list[float]) -> (
                           dict[str, list[float]]):
    hist = np.zeros(len(bins) - 1)
    total_count = 0
    for s in strokes.Compressions + strokes.Rebounds:
        total_count += s.Stat.Count
        for d in s.DigitizedTravel:
            hist[d] += 1
    hist = hist / total_count * 100.0
    return dict(y=bins[:-1], right=hist)


def travel_histogram_figure(strokes: Strokes, bins: list[float],
                            color: tuple[str], title: str) -> figure:
    max_travel = bins[-1]
    data = _travel_histogram_data(strokes, bins)
    source = ColumnDataSource(name='ds_hist', data=data)
    p = figure(
        title=title,
        min_height=300,
        min_border_left=70,
        min_border_right=50,
        sizing_mode="stretch_both",
        x_axis_label="Time (%)",
        y_axis_label='Travel (mm)',
        toolbar_location='above',
        tools='ypan,ywheel_zoom,reset',
        active_drag='ypan',
        output_backend='webgl')
    p.x_range.start = 0
    p.x_range.end = HISTOGRAM_RANGE_MULTIPLIER * np.max(data['right'])
    p.y_range.flipped = True
    p.hbar(y='y', height=max_travel / (len(bins) - 1) - 3,
           left=0, right='right', source=source, line_width=2,
           color=color, fill_alpha=0.4)

    _add_travel_stat_labels(strokes, max_travel, p.x_range.end, p)
    return p


def _travel_stats(strokes: Strokes, max_travel: float) -> (
                  float, float, str, str):
    sum = 0
    count = 0
    mx = 0
    bo = 0
    for s in strokes.Compressions + strokes.Rebounds:
        sum += s.Stat.SumTravel
        count += s.Stat.Count
        bo += s.Stat.Bottomouts
        if s.Stat.MaxTravel > mx:
            mx = s.Stat.MaxTravel
    avg = sum / count

    avg_text = f"avg.: {avg:.2f} mm ({avg/max_travel*100:.1f}%)"
    mx_text = (f"max.: {mx:.2f} mm ({mx/max_travel*100:.1f}%) / "
               f"{bo} bottom outs")
    return avg, mx, avg_text, mx_text


def _add_travel_stat_labels(strokes: Strokes, max_travel: float,
                            hist_max: float, p: figure):
    avg, mx, avg_text, mx_text = _travel_stats(strokes, max_travel)
    s_avg = Span(name='s_avg', location=avg, dimension='width',
                 line_color='gray', line_dash='dashed', line_width=2)
    s_max = Span(name='s_max', location=mx, dimension='width',
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
    l_avg = Label(name='l_avg', y=avg, text=avg_text,
                  y_offset=-10, **text_props)
    l_max = Label(name='l_max', y=mx, text=mx_text, y_offset=10, **text_props)
    p.add_layout(l_avg)
    p.add_layout(l_max)


def update_travel_histogram(p: figure, strokes: Strokes, bins: list[float]):
    ds = p.select_one('ds_hist')
    ds.data = _travel_histogram_data(strokes, bins)

    p.x_range.end = HISTOGRAM_RANGE_MULTIPLIER * np.max(ds.data['right'])

    avg, mx, avg_text, mx_text = _travel_stats(strokes, bins[-1])
    l_avg = p.select_one('l_avg')
    l_avg.text = avg_text
    l_avg.x = p.x_range.end
    l_avg.y = avg
    l_max = p.select_one('l_max')
    l_max.text = mx_text
    l_max.x = p.x_range.end
    l_max.y = mx
    s_avg = p.select_one('s_avg')
    s_avg.location = avg
    s_max = p.select_one('s_max')
    s_max.location = mx


def _add_airtime_labels(p_travel: figure, airtimes: list[Airtime]):
    for airtime in airtimes:
        b = BoxAnnotation(left=airtime.Start, right=airtime.End,
                          fill_color=Spectral11[-2], fill_alpha=0.2)
        p_travel.add_layout(b)
        airtime_label = Label(
            x=airtime.Start + (airtime.End - airtime.Start) / 2,
            y=30,
            x_units='data',
            y_units='screen',
            text_font_size='14px',
            text_color='#fefefe',
            text_align='center',
            text_baseline='middle',
            text=f"{airtime.End-airtime.Start:.2f}s air")
        p_travel.add_layout(airtime_label)
