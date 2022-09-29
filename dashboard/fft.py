import numpy as np

from bokeh.models.ranges import Range1d
from bokeh.models.sources import ColumnDataSource
from bokeh.models.tools import HoverTool, WheelZoomTool
from bokeh.plotting import figure
from scipy.fft import rfft, rfftfreq


def fft_data(travel, tick):
    balanced_travel = travel - np.mean(travel)
    n = len(balanced_travel)
    if n < 10000:
        n = 10000
    balanced_travel_f = rfft(balanced_travel, n=n)
    balanced_spectrum = np.abs(balanced_travel_f)

    freqs= rfftfreq(n, tick)
    freqs = freqs[freqs <= 10] # cut off FFT graph at 10 Hz

    # TODO put a label that shows the most prominent frequencies
    #max_freq_idx = np.argpartition(balanced_spectrum, -1)[-1:]
    #print(f[max_freq_idx])

    return dict(freqs=freqs, spectrum=balanced_spectrum[:len(freqs)])

def fft_figure(travel, tick, color, title):
    source = ColumnDataSource(name='ds_fft', data=fft_data(travel, tick))
    p = figure(
        title=title,
        height=300,
        sizing_mode='stretch_width',
        toolbar_location='above',
        tools='xpan,reset',
        active_drag='xpan',
        x_axis_label="Fequency (Hz)",
        output_backend='webgl')
    wzt = WheelZoomTool(maintain_focus=False, dimensions='width')
    p.add_tools(wzt)
    ht = HoverTool(name='ht', tooltips="@freqs Hz", mode='vline', attachment='above')
    p.add_tools(ht)
    p.yaxis.visible = False
    p.x_range = Range1d(0.05, 5.05, bounds=(0.05, 10.05))
    p.vbar(name='b_fft', x='freqs', bottom=0, top='spectrum', source=source, width=4.9/len(source.data['freqs']), color=color)
    return p

def update_fft(p, travel, tick):
    ds = p.select_one('ds_fft')
    ds.data = fft_data(travel, tick)
    b = p.select_one('b_fft')
    b.glyph.width = 4.9 / len(ds.data['freqs'])
