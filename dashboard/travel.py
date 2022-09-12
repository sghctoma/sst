import numpy as np

from bokeh.events import DoubleTap, SelectionGeometry
from bokeh.models import ColumnDataSource
from bokeh.models.annotations import BoxAnnotation, Label, Span
from bokeh.models.axes import LinearAxis
from bokeh.models.callbacks import CustomJS
from bokeh.models.ranges import Range1d
from bokeh.models.tickers import FixedTicker
from bokeh.models.tools import BoxSelectTool, WheelZoomTool
from bokeh.plotting import figure

from extremes import bottomouts


def travel_figure(telemetry, lod, front_color, rear_color):
    l = len(telemetry.Front.Travel if telemetry.Front.Present else telemetry.Rear.Travel)
    time = np.around(np.arange(0, l)/telemetry.SampleRate, 4) 
    front_max = telemetry.Front.Calibration.MaxStroke
    rear_max = telemetry.Frame.MaxRearTravel

    source = ColumnDataSource(data=dict(
        t=time[::lod],
        f=np.around(telemetry.Front.Travel[::lod], 4) if telemetry.Front.Present else np.full(l, 0)[::lod],
        r=np.around(telemetry.Rear.Travel[::lod], 4,) if telemetry.Rear.Present else np.full(l, 0)[::lod],
    ))
    p = figure(
        title="Wheel travel",
        height=400,
        sizing_mode="stretch_width",
        toolbar_location='above',
        tools='xpan,reset,hover',
        active_inspect=None,
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
    p.legend.level = 'overlay'

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
        '''))

    wz = WheelZoomTool(maintain_focus=False, dimensions='width')
    p.add_tools(wz)
    p.toolbar.active_scroll = wz
   
    p.hover.mode = 'vline'
    p.hover.renderers = [l]
    p.legend.location = 'bottom_right'
    p.legend.click_policy = 'hide'
    return p

def travel_histogram_data(digitized, mask):
    hist = np.zeros(len(digitized.Bins)-1)
    for i in range(len(digitized.Data)):
        if mask[i]:
            hist[digitized.Data[i]] += 1
    hist = hist / np.count_nonzero(mask) * 100
    return dict(y=digitized.Bins[:-1], right=hist)

def travel_histogram_figure(digitized, travel, mask, color, title):
    bins = digitized.Bins
    max_travel = bins[-1]
    data = travel_histogram_data(digitized, mask)
    source = ColumnDataSource(name='ds_hist', data=data)
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
    p.hbar(y='y', height=max_travel/(len(bins)-1), left=0, right='right', source=source, color=color, line_color='black')
    add_travel_stat_labels(travel[mask], max_travel, np.max(data['right']), p)
    return p

def travel_stats(travel, max_travel):
    avg = np.average(travel)
    mx = np.max(travel)
    bo = bottomouts(travel, max_travel)
    avg_text = f"avg.: {avg:.2f} mm ({avg/max_travel*100:.1f}%)"
    mx_text = f"max.: {mx:.2f} mm ({mx/max_travel*100:.1f}%) / {len(bo)} bottom outs"
    return avg, mx, avg_text, mx_text

def add_travel_stat_labels(travel, max_travel, hist_max, p):
    avg, mx, avg_text, mx_text = travel_stats(travel, max_travel)
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
    l_avg = Label(name='l_avg', y=avg, text=avg_text, y_offset=-10, **text_props)
    l_max = Label(name='l_max', y=mx, text=mx_text, y_offset=10, **text_props)
    p.add_layout(l_avg)
    p.add_layout(l_max)

def update_travel_histogram(p, travel, digitized, mask):
    ds = p.select_one('ds_hist')
    ds.data = travel_histogram_data(digitized, mask)

    avg, mx, avg_text, mx_text = travel_stats(travel[mask], ds.data['y'][-1])
    l_avg = p.select_one('l_avg')
    l_avg.text = avg_text
    l_avg.x = np.max(ds.data['right'])
    l_avg.y = avg
    l_max = p.select_one('l_max')
    l_max.text = mx_text
    l_max.x = np.max(ds.data['right'])
    l_max.y = mx
    s_avg = p.select_one('s_avg')
    s_avg.location = avg
    s_max = p.select_one('s_max')
    s_max.location = mx

