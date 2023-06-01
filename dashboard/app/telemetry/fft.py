import numpy as np

from bokeh.models import CustomJS
from bokeh.models.formatters import CustomJSTickFormatter
from bokeh.models.ranges import Range1d
from bokeh.models.sources import ColumnDataSource
from bokeh.models.tickers import FixedTicker
from bokeh.models.tools import HoverTool, WheelZoomTool
from bokeh.plotting import figure
from scipy.fft import rfft, rfftfreq

from app.telemetry.psst import Strokes


def _fft_data(strokes: Strokes, travel: list[float], tick: float) -> (
              dict[str, np.array]):
    start = min(strokes.Compressions[0].Start, strokes.Rebounds[0].Start)
    end = max(strokes.Compressions[-1].End, strokes.Rebounds[-1].End)
    stroke_travel = travel[start:end]
    balanced_travel = stroke_travel - np.mean(stroke_travel)
    n = np.max([20000, len(balanced_travel)])
    balanced_travel_f = rfft(balanced_travel, n=n)
    balanced_spectrum = np.square(np.abs(balanced_travel_f)).tolist()

    freqs = rfftfreq(n, tick)
    freqs = freqs[freqs <= 10].tolist()  # cut off FFT graph at 10 Hz

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
        y_axis_label="Power",
        output_backend='webgl')
    wzt = WheelZoomTool(maintain_focus=False, dimensions='width')
    p.add_tools(wzt)
    ht = HoverTool(name='ht', tooltips="@freqs Hz",
                   mode='vline', attachment='above')
    p.add_tools(ht)
    temp_spectrum = np.array(data['spectrum'])
    ticker_min = np.min(temp_spectrum[temp_spectrum != 0])
    ticker_max = np.max(data['spectrum'])
    p.yaxis.ticker = FixedTicker(ticks=[
        ticker_min,
        (ticker_min + ticker_max) / 2.0,
        ticker_max,
    ])
    p.yaxis.formatter = CustomJSTickFormatter(
        args={}, code='''
            const t = Math.floor(20 * Math.log10(tick))
            return t === NaN ? "" : t
        ''')

    p.x_range = Range1d(
        0.0,
        800.0 / len(source.data['freqs']) * 3.0,
        bounds=(0.0, 10.0))
    bar_width = 4.9 / len(source.data['freqs'])
    p.vbar(name='b_fft', x='freqs', bottom=0, top='spectrum',
           source=source, width=bar_width, line_width=2,
           color=color, fill_alpha=0.4)

    source.js_on_change('data', CustomJS(args=dict(
        xr=p.x_range, yr=p.y_range, ticker=p.yaxis.ticker), code='''
            xr.end = 800 / cb_obj.data.freqs.length * 3
            yr.start = Math.min(...cb_obj.data.spectrum)
            yr.end = Math.max(...cb_obj.data.spectrum)
            const tickerMin = Math.min(...cb_obj.data.spectrum.filter(e => e != 0))
            const tickerMax = Math.max(...cb_obj.data.spectrum)
            ticker.ticks = [tickerMin, (tickerMin + tickerMax) / 2.0, tickerMax]
        '''))
    return p


def update_fft(strokes: Strokes, travel: list[float], tick: float):
    data = _fft_data(strokes, travel, tick)
    return dict(
        data=data,
    )
