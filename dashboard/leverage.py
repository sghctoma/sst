import numpy as np

from bokeh.plotting import figure


def shock_wheel_figure(coeffs, max_stroke, color):
    f = np.poly1d(np.flip(coeffs))
    p = figure(
        name='sw',
        title="Shock - Wheel displacement",
        height=300,
        width=300,
        sizing_mode='stretch_width',
        toolbar_location=None,
        active_drag=None,
        active_scroll=None,
        tools='hover',
        active_inspect='hover',
        tooltips=[("shock stroke", "@x"), ("wheel travel", "@y")],
        x_axis_label="Shock Stroke (mm)",
        y_axis_label="Wheel Travel (mm)",
        output_backend='webgl')
    p.hover.mode = 'vline'

    x = np.arange(0, max_stroke, 1)
    y = [f(t) for t in x]
    p.line(x, y, line_width=2, color=color)
    return p


def leverage_ratio_figure(wtlr, color):
    p = figure(
        name='lr',
        title="Leverage Ratio",
        height=300,
        width=300,
        sizing_mode='stretch_width',
        toolbar_location=None,
        active_drag=None,
        active_scroll=None,
        tools='hover',
        active_inspect='hover',
        tooltips=[("wheel travel", "@x"), ("leverage ratio", "@y")],
        x_axis_label="Rear Wheel Travel (mm)",
        y_axis_label="Leverage Ratio",
        output_backend='webgl')
    p.hover.mode = 'vline'

    x = wtlr[:, 0]
    y = wtlr[:, 1]
    p.line(x, y, line_width=2, color=color)
    return p
