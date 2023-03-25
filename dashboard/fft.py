import numpy as np

from bokeh.models.ranges import Range1d
from bokeh.models.sources import ColumnDataSource
from bokeh.models.tools import HoverTool, WheelZoomTool
from bokeh.plotting import figure
from scipy.fft import rfft, rfftfreq

from psst import Strokes


def _fft_data(strokes: Strokes, travel: list[float], tick: float) -> (
              dict[str, np.array]):
    stroke_travel = []
    for s in strokes.Compressions + strokes.Rebounds:
        stroke_travel.extend(travel[s.Start:s.End+1])
    balanced_travel = stroke_travel - np.mean(stroke_travel)
    n = np.max([20000, len(balanced_travel)])
    balanced_travel_f = rfft(balanced_travel, n=n)
    balanced_spectrum = np.abs(balanced_travel_f)

    freqs = rfftfreq(n, tick)
    freqs = freqs[freqs <= 10]  # cut off FFT graph at 10 Hz

    # TODO put a label that shows the most prominent frequencies
    # max_freq_idx = np.argpartition(balanced_spectrum, -1)[-1:]
    # print(f[max_freq_idx])

    return dict(freqs=freqs, spectrum=balanced_spectrum[:len(freqs)])


def fft_figure(strokes: Strokes, travel: list[float], tick: float,
               color: tuple[str], title: str) -> figure:
    data = _fft_data(strokes, travel, tick)
    source = ColumnDataSource(name='ds_fft', data=data)
    p = figure(
        title=title,
        min_height=150,
        min_border_left=70,
        min_border_right=50,
        sizing_mode='stretch_both',
        toolbar_location='above',
        tools='xpan,reset',
        active_drag='xpan',
        x_axis_label="Fequency (Hz)",
        output_backend='webgl')
    wzt = WheelZoomTool(maintain_focus=False, dimensions='width')
    p.add_tools(wzt)
    ht = HoverTool(name='ht', tooltips="@freqs Hz",
                   mode='vline', attachment='above')
    p.add_tools(ht)
    p.yaxis.visible = False
    p.x_range = Range1d(0.05, 3.05, bounds=(0.05, 10.05))
    bar_width = 4.9 / len(source.data['freqs'])
    p.vbar(name='b_fft', x='freqs', bottom=0, top='spectrum',
           source=source, width=bar_width, line_width=2,
           color=color, fill_alpha=0.4)
    return p
