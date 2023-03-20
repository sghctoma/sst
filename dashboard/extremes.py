from bokeh.models.annotations import BoxAnnotation, Label
from bokeh.palettes import Spectral11
from bokeh.plotting import figure

from psst import Airtime


def add_airtime_labels(p_travel: figure, airtimes: list[Airtime]):
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
