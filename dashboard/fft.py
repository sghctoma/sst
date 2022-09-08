import numpy as np

from bokeh.models.ranges import Range1d
from bokeh.models.tools import WheelZoomTool
from bokeh.plotting import figure
from scipy.fft import rfft, rfftfreq


def do_fft(travel, tick):
    wf = np.kaiser(len(travel), 5)

    balanced_travel = travel - np.mean(travel)
    balanced_travel_f = rfft(balanced_travel * wf)
    balanced_spectrum = np.abs(balanced_travel_f)

    freqs= rfftfreq(len(travel), tick)
    freqs = freqs[freqs <= 10] # cut off FFT graph at 10 Hz

    # TODO put a label that shows the most prominent frequencies
    #max_freq_idx = np.argpartition(balanced_spectrum, -1)[-1:]
    #print(f[max_freq_idx])

    return freqs, balanced_spectrum[:len(freqs)]

def fft_figure(travel, tick, color, title):
    f, s = do_fft(travel, tick)
    p = figure(
        title=title,
        height=300,
        sizing_mode='stretch_width',
        toolbar_location='above',
        tools='xpan,reset,hover',
        tooltips="@x Hz",
        active_drag='xpan',
        x_axis_label="Fequency (Hz)",
        output_backend='webgl')
    wz = WheelZoomTool(maintain_focus=False, dimensions='width')
    p.add_tools(wz)
    p.toolbar.active_scroll = wz
    p.hover.mode = 'vline'
    p.yaxis.visible = False
    p.x_range = Range1d(0.05, 5.05, bounds=(0.05, 10.05))
    p.vbar(x=f, bottom=0, top=s, width=0.005, color=color)
    return p

