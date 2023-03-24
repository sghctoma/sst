from sqlalchemy import (
    Column, Integer, LargeBinary, MetaData, String, Table,
    ForeignKey,
    select, desc
)

metadata_obj = MetaData()

bokeh_cache_table = Table(
    'bokeh_cache',
    metadata_obj,
    Column('session_id', Integer, ForeignKey('sessions.session_id')),
    Column('script', String),
    Column('div_travel', String),
    Column('div_velocity', String),
    Column('div_map', String),
    Column('div_lr', String),
    Column('div_sw', String),
    Column('div_setup', String),
    Column('json_f_fft', String),
    Column('json_r_fft', String),
    Column('json_f_thist', String),
    Column('json_r_thist', String),
    Column('json_f_vhist', String),
    Column('json_r_vhist', String),
    Column('json_cbalance', String),
    Column('json_rbalance', String),
)

tracks_table = Table(
    'tracks',
    metadata_obj,
    Column('track_id', Integer, primary_key=True),
    Column('track', String, nullable=False),
)

sessions_table = Table(
    'sessions',
    metadata_obj,
    Column('session_id', Integer, primary_key=True),
    Column('name', String),
    Column('setup_id', Integer, ForeignKey('setups.setup_id'), nullable=False),
    Column('description', String),
    Column('timestamp', Integer),
    Column('data', LargeBinary),
    Column('track_id', Integer, ForeignKey('tracks.track_id'), nullable=False),
)


def stmt_sessions():
    return (select(
        sessions_table.c.session_id,
        sessions_table.c.name,
        sessions_table.c.description,
        sessions_table.c.timestamp)
        .order_by(desc(sessions_table.c.timestamp)))


def stmt_session(session_id: int):
    return (select(
        sessions_table.c.name,
        sessions_table.c.description,
        sessions_table.c.data,
        tracks_table.c.track)
        .join(tracks_table, isouter=True)
        .where(sessions_table.c.session_id == session_id))


def stmt_cache(session_id: int):
    return (select(
        bokeh_cache_table)
        .where(bokeh_cache_table.c.session_id == session_id))
