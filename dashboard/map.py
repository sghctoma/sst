import math
import numpy as np
import xyzservices.providers as xyz

from gpx_converter import Converter
from bokeh.models import ColumnDataSource
from bokeh.palettes import Spectral11
from bokeh.plotting import figure


def geographic_to_mercator(x_lon, y_lat):
    if abs(x_lon) > 180 or abs(y_lat) >= 90:
        return None

    num = x_lon * 0.017453292519943295
    x_m = 6378137.0 * num
    a = y_lat * 0.017453292519943295
    y_m = 3189068.5 * math.log((1.0 + math.sin(a)) / (1.0 - math.sin(a)))
    return x_m, y_m


def map_figure(filename, start_time, end_time):
    track = Converter(input_file=filename).gpx_to_dictionary(
        latitude_key='lat',
        longitude_key='lon')
    for i in range(len(track['time'])):
        track['lon'][i], track['lat'][i] = geographic_to_mercator(
            track['lon'][i], track['lat'][i])
    ds_track = ColumnDataSource(data=track)

    t = np.array(track['time'])
    session_indices = np.where(np.logical_and(t >= start_time, t <= end_time))
    if len(session_indices[0]) == 0:
        return figure(name='map')

    session_lon = np.array(track['lon'])[session_indices]
    session_lat = np.array(track['lat'])[session_indices]
    session_data = {'lon': session_lon, 'lat': session_lat}
    ds_session = ColumnDataSource(data=session_data)

    p = figure(
        name="map",
        x_axis_type=None,
        y_axis_type=None,
        sizing_mode='stretch_width',
        height=677,
        tools='pan,wheel_zoom,reset',
        active_drag='pan',
        active_scroll='wheel_zoom',
        output_backend='webgl')
    tile_provider = xyz.Jawg.Dark(
        accessToken='lK4rYCmlPZb5Fj4GjObrgGYo0IQnEz00hWXR7lpmRUHQ2a9R6jwr8aEpaSJxh5tn',
        variant='aa40616c-c117-442e-ae6f-901ffa0e14a4'
    )
    p.add_tile(tile_provider)
    p.line(x='lon', y='lat', source=ds_track,
           color=Spectral11[3], alpha=0.5, width=2)
    p.circle(x=track['lon'][0], y=track['lat'][0],
             color='#229954', alpha=0.8, size=10)
    p.circle(x=track['lon'][-1], y=track['lat'][-1],
             color='#E74C3C', alpha=0.8, size=10)

    p.line(x='lon', y='lat', source=ds_session,
           color=Spectral11[10], alpha=0.8, width=5)
    return p
