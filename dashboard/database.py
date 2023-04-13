from sqlalchemy import (
    Column, MetaData, Table,
    Float, Integer, LargeBinary, String,
    ForeignKey,
    desc, delete, insert, select, update
)


metadata_obj = MetaData()

tokens_table = Table(
    'tokens',
    metadata_obj,
    Column('token', String, nullable=False)
)

bokeh_components_table = Table(
    'bokeh_components',
    metadata_obj,
    Column('session_id', Integer, ForeignKey('sessions.id')),
    Column('script', String, nullable=False),
    Column('travel', String, nullable=False),
    Column('velocity', String, nullable=False),
    Column('map', String, nullable=False),
    Column('lr', String, nullable=False),
    Column('sw', String, nullable=False),
    Column('setup', String, nullable=False),
    Column('desc', String, nullable=False),
    Column('f_thist', String),
    Column('f_fft', String),
    Column('f_vhist', String),
    Column('r_thist', String),
    Column('r_fft', String),
    Column('r_vhist', String),
    Column('cbalance', String),
    Column('rbalance', String),
)

tracks_table = Table(
    'tracks',
    metadata_obj,
    Column('id', Integer, primary_key=True),
    Column('track', String, nullable=False),
)

sessions_table = Table(
    'sessions',
    metadata_obj,
    Column('id', Integer, primary_key=True),
    Column('name', String),
    Column('setup_id', Integer, ForeignKey('setups.id'), nullable=False),
    Column('description', String),
    Column('timestamp', Integer, nullable=False),
    Column('data', LargeBinary, nullable=False),
    Column('track_id', Integer, ForeignKey('tracks.id')),
)

setups_table = Table(
    'setups',
    metadata_obj,
    Column('id', Integer, primary_key=True),
    Column('name', String, nullable=False),
    Column('linkage_id', Integer, ForeignKey('linkages.id'),
           nullable=False),
    Column('front_calibration_id', Integer,
           ForeignKey('calibrations.id')),
    Column('rear_calibration_id', Integer,
           ForeignKey('calibrations.id')),
)

calibration_methods_table = Table(
    'calibration_methods',
    metadata_obj,
    Column('id', Integer, primary_key=True),
    Column('name', String, nullable=False),
    Column('description', String),
    Column('data', String, nullable=False),
)

calibrations_table = Table(
    'calibrations',
    metadata_obj,
    Column('id', Integer, primary_key=True),
    Column('name', String, nullable=False),
    Column('method_id', Integer, ForeignKey('calibration_methods.id'),
           nullable=False),
    Column('inputs', String, nullable=False),
)

linkages_table = Table(
    'linkages',
    metadata_obj,
    Column('id', Integer, primary_key=True),
    Column('name', String, nullable=False),
    Column('head_angle', Float, nullable=False),
    Column('raw_lr_data', String, nullable=False),
)


def stmt_tokens():
    return select(tokens_table)


def stmt_sessions():
    return (select(
        sessions_table.c.id,
        sessions_table.c.name,
        sessions_table.c.description,
        sessions_table.c.timestamp)
        .join(bokeh_components_table,
              sessions_table.c.id == bokeh_components_table.c.session_id)
        .order_by(desc(sessions_table.c.timestamp)))


def stmt_session(session_id: int):
    return (select(
        sessions_table.c.name,
        sessions_table.c.description,
        sessions_table.c.data,
        tracks_table.c.track)
        .join(tracks_table, isouter=True)
        .where(sessions_table.c.id == session_id))


def stmt_session_delete(session_id: int):
    return (delete(
        sessions_table)
        .where(sessions_table.c.id == session_id))


def stmt_cache(session_id: int):
    return (select(
        bokeh_components_table)
        .where(bokeh_components_table.c.session_id == session_id))


def stmt_cache_insert():
    return insert(bokeh_components_table)


def stmt_cache_delete(session_id: int):
    return (delete(
        bokeh_components_table)
        .where(bokeh_components_table.c.session_id == session_id))


def stmt_track(track: str):
    return (insert(tracks_table)
            .values(track=track)
            .returning(tracks_table.c.id))


def stmt_session_tracks(session_id: int, track_id: int,
                        start_time: int, end_time: int):
    s1 = sessions_table.alias()
    s2 = sessions_table.alias()
    stmt_select = (select(
        s2.c.id)
        .join(s2, s1.c.setup_id == s2.c.setup_id)
        .where(s1.c.id == session_id)
        .where(s2.c.timestamp >= start_time)
        .where(s2.c.timestamp <= end_time))
    stmt_update = (update(
        sessions_table)
        .where(sessions_table.c.id.in_(stmt_select))
        .values(track_id=track_id))
    return stmt_update


def stmt_description(session_id: int, name: str, desc: str):
    return (update(
        sessions_table)
        .where(sessions_table.c.id == session_id)
        .values(name=name, description=desc))
