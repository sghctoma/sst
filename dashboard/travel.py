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
    time = np.around(np.arange(0, len(telemetry.Front.Travel)) / telemetry.SampleRate, 4) 
    front_max = telemetry.Front.Calibration.MaxStroke
    rear_max = telemetry.Frame.MaxRearTravel

    source = ColumnDataSource(data=dict(
        t=time[::lod],
        f=np.around(telemetry.Front.Travel[::lod], 4),
        r=np.around(telemetry.Rear.Travel[::lod], 4,),
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

def travel_histogram_figure(digitized, travel, mask, color, title):
    bins = digitized.Bins
    max_travel = bins[-1]
    hist = np.zeros(len(bins)-1)
    for i in range(len(digitized.Data)):
        if mask[i]:
            hist[digitized.Data[i]] += 1
    hist = hist / np.count_nonzero(mask) * 100

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
    add_travel_stat_labels(travel[mask], max_travel, np.max(hist), p)
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
