#!/usr/bin/env python

import argparse
import msgpack
import numpy as np

from bokeh.io import curdoc
from bokeh.io import output_file, save
from bokeh.layouts import column, layout
from bokeh.palettes import Spectral11
from pathlib import Path

from extremes import topouts, combined_topouts
from extremes import intervals_mask, filter_airtimes, filter_idlings
from extremes import add_airtime_labels, add_idling_marks
from fft import fft_figure
from leverage import shock_wheel_figure, leverage_ratio_figure
from psst import Telemetry, dataclass_from_dict
from travel import travel_figure, travel_histogram_figure
from velocity import velocity_histogram_figure, velocity_stats_figure


def parse_arguments():
    parser = argparse.ArgumentParser(description="Turn PSST to HTML")
    parser.add_argument('input', help="PSST file path")
    parser.add_argument('output', help="HTML file path", nargs='?')
    args = parser.parse_args()

    psst_file = args.input
    html_file = args.output
    if not html_file:
        html_file = Path(psst_file).with_suffix('.html')
    return psst_file, html_file

def main():
    psst_file, html_file = parse_arguments()
    telemetry = dataclass_from_dict(Telemetry, msgpack.unpackb(open(psst_file, 'rb').read()))

    high_speed_threshold = 100
    tick = 1.0 / telemetry.SampleRate # time step length in seconds

    # collect information for graphs
    front_travel = np.array(telemetry.Front.Travel)
    front_velocity = np.array(telemetry.Front.Velocity)
    rear_travel = np.array(telemetry.Rear.Travel)
    rear_velocity = np.array(telemetry.Rear.Velocity)

    '''
    Topouts are intervals where suspension is at zero extension for an extended period of time. It allows us to filter
    out e.g. the beginning and the end of the ride, where the bike is at rest, or intervals where we stop mid-ride.
    Filtering these out is important, because they can skew travel and velocity statistics. They are handled
    individually for front and rear suspension.
    '''
    front_topouts = topouts(front_travel, telemetry.Front.Calibration.MaxStroke, telemetry.SampleRate)
    rear_topouts = topouts(rear_travel, telemetry.Frame.MaxRearTravel, telemetry.SampleRate)
    front_topouts_mask = intervals_mask(front_topouts, len(front_travel))
    rear_topouts_mask = intervals_mask(rear_topouts, len(rear_travel))

    '''
    We use both suspensions to find airtimes. Basically, everything is considered airtime if both suspensions are close
    to zero travel, and suspension velocity at the end of the interval reaches a threshold. A few remarks:
     - Originally, I used a velocity threshold at the beginning too of a candidate interval, but there were a lot of
       false negatives usually with drops.
     - We use the mean of front and rear travel to determine closeness to zero. This is based on the empirical
       observation that sometimes one of the suspensions (usually my fork) oscillates outside the set threshold during
       airtime (usually during drops). I expect this to become a problem if anybody else starts using this program, but
       could not come up with better heuristics so far.
    '''
    comb_topouts = combined_topouts(front_travel, telemetry.Front.Calibration.MaxStroke,
        rear_travel, telemetry.Frame.MaxRearTravel, telemetry.SampleRate)
    airtimes = filter_airtimes(comb_topouts, front_velocity, rear_velocity, telemetry.SampleRate)
    airtimes_mask = intervals_mask(np.array(airtimes), len(front_travel), False)
    front_idlings = filter_idlings(front_topouts, airtimes_mask)
    rear_idlings = filter_idlings(rear_topouts, airtimes_mask)

    # create graphs
    curdoc().theme = 'dark_minimal'
    output_file(html_file, title=f"Sufni Suspension Telemetry Dashboard ({Path(psst_file).name})")
    front_color = Spectral11[1]
    rear_color = Spectral11[2]

    p_travel = travel_figure(telemetry, 100, front_color, rear_color)
    add_airtime_labels(airtimes, tick, p_travel)
    add_idling_marks(front_idlings, tick, p_travel)
    add_idling_marks(rear_idlings, tick, p_travel)

    p_lr = leverage_ratio_figure(np.array(telemetry.Frame.WheelLeverageRatio), Spectral11[5])
    p_sw = shock_wheel_figure(telemetry.Frame.CoeffsShockWheel, telemetry.Rear.Calibration.MaxStroke, Spectral11[5])

    p_front_travel_hist = travel_histogram_figure(telemetry.Front.DigitizedTravel, front_travel, front_topouts_mask,
        front_color, "Travel histogram (front)")
    p_rear_travel_hist = travel_histogram_figure(telemetry.Rear.DigitizedTravel, rear_travel, rear_topouts_mask,
        rear_color, "Travel histogram (rear)")
    p_front_vel_hist = velocity_histogram_figure(telemetry.Front.DigitizedTravel, telemetry.Front.DigitizedVelocity,
        front_velocity, front_topouts_mask, high_speed_threshold, "Speed histogram (front)")
    p_rear_vel_hist = velocity_histogram_figure(telemetry.Rear.DigitizedTravel, telemetry.Rear.DigitizedVelocity,
        rear_velocity, rear_topouts_mask, high_speed_threshold, "Speed histogram (rear)")

    p_vel_stats_front = velocity_stats_figure(front_velocity[front_topouts_mask], high_speed_threshold)
    p_vel_stats_rear = velocity_stats_figure(rear_velocity[front_topouts_mask], high_speed_threshold)

    p_front_fft = fft_figure(front_travel[front_topouts_mask], tick, front_color, "Frequencies (front)")
    p_rear_fft = fft_figure(rear_travel[rear_topouts_mask], tick, rear_color, "Frequencies (rear)")

    # add graphs to layout
    l = layout(
        children=[
            [p_travel, p_lr, p_sw],
            [column(p_front_travel_hist, p_rear_travel_hist), p_front_vel_hist, p_vel_stats_front, p_rear_vel_hist, p_vel_stats_rear],
            [p_front_fft, p_rear_fft],
        ],
        sizing_mode='stretch_width')
    save(l)

if __name__ == "__main__":
    main()
