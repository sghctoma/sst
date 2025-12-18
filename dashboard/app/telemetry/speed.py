import numpy as np

from bokeh.models import ColumnDataSource
from bokeh.models.annotations import Span
from bokeh.models.ranges import Range1d
from bokeh.models.tools import CrosshairTool, WheelPanTool, WheelZoomTool
from bokeh.palettes import Spectral11
from bokeh.plotting import figure


def speed_figure(speed_data: list[float], sample_rate: float = 10.0) -> figure:
    """Create GPS speed figure.

    Args:
        speed_data: Speed values in km/h at 10Hz (0.1s intervals)
        sample_rate: Samples per second (default 10Hz from GPS interpolation)

    Returns:
        Bokeh figure with speed line plot
    """
    length = len(speed_data)
    time = np.around(np.arange(0, length) / sample_rate, 4)
    speed = np.around(speed_data, 2)

    source = ColumnDataSource(data=dict(t=time, s=speed))

    p = figure(
        name='speed',
        title="GPS Speed",
        height=275,
        min_border_left=50,
        min_border_right=50,
        sizing_mode="stretch_width",
        toolbar_location='above',
        tools='xpan,reset,hover',
        active_inspect=None,
        active_drag='xpan',
        tooltips=[("elapsed time", "@t s"),
                  ("speed", "@s km/h")],
        x_axis_label="Elapsed time (s)",
        y_axis_label="Speed (km/h)",
        output_backend='webgl')

    p.x_range = Range1d(0, time[-1] if len(time) > 0 else 1, bounds='auto')

    line = p.line(
        't', 's',
        legend_label="GPS Speed",
        line_width=2,
        color=Spectral11[4],  # Different color from front/rear
        source=source)

    p.legend.level = 'overlay'

    wp = WheelPanTool(dimension='width')
    p.add_tools(wp)
    wz = WheelZoomTool(maintain_focus=False, dimensions='width')
    p.add_tools(wz)
    p.toolbar.active_scroll = wz

    s_current_time = Span(name='s_current_time_speed',
                          location=0,
                          dimension='height',
                          line_color='#d0d0d0')
    ch = CrosshairTool(dimensions='height', line_color='#d0d0d0',
                       overlay=s_current_time)
    p.add_tools(ch)
    p.toolbar.active_inspect = ch

    p.hover.mode = 'vline'
    p.hover.renderers = [line]
    p.legend.location = 'bottom_right'

    return p
