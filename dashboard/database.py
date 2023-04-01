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
    Column('session_id', Integer, ForeignKey('sessions.session_id')),
    Column('script', String, nullable=False),
    Column('travel', String, nullable=False),
    Column('velocity', String, nullable=False),
    Column('map', String, nullable=False),
    Column('lr', String, nullable=False),
    Column('sw', String, nullable=False),
    Column('setup', String, nullable=False),
    Column('desc', String, nullable=False),
    Column('f_thist', String, nullable=False),
    Column('f_fft', String, nullable=False),
    Column('f_vhist', String, nullable=False),
    Column('r_thist', String, nullable=False),
    Column('r_fft', String, nullable=False),
    Column('r_vhist', String, nullable=False),
    Column('cbalance', String, nullable=False),
    Column('rbalance', String, nullable=False),
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
    Column('timestamp', Integer, nullable=False),
    Column('data', LargeBinary, nullable=False),
    Column('track_id', Integer, ForeignKey('tracks.track_id')),
)

setups_table = Table(
    'setups',
    metadata_obj,
    Column('setup_id', Integer, primary_key=True),
    Column('name', String, nullable=False),
    Column('linkage_id', Integer, ForeignKey('linkages.linkage_id'),
           nullable=False),
    Column('front_calibration_id', Integer,
           ForeignKey('calibrations.calibration_id')),
    Column('rear_calibration_id', Integer,
           ForeignKey('calibrations.calibration_id')),
)

calibrations_table = Table(
    'calibrations',
    metadata_obj,
    Column('calibration_id', Integer, primary_key=True),
    Column('name', String, nullable=False),
    Column('arm', Float, nullable=False),
    Column('dist', Float, nullable=False),
    Column('stroke', Float, nullable=False),
    Column('angle', Float, nullable=False),
)

linkages_table = Table(
    'linkages',
    metadata_obj,
    Column('linkage_id', Integer, primary_key=True),
    Column('name', String, nullable=False),
    Column('raw_lr_data', String, nullable=False),
)


def stmt_tokens():
    return select(tokens_table)


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


def stmt_session_delete(session_id: int):
    return (delete(
        sessions_table)
        .where(sessions_table.c.session_id == session_id))


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
            .returning(tracks_table.c.track_id))


def stmt_session_tracks(session_id: int, track_id: int,
                        start_time: int, end_time: int):
    s1 = sessions_table.alias()
    s2 = sessions_table.alias()
    stmt_select = (select(
        s1.c.session_id)
        .join(s2, s1.c.setup_id == s2.c.setup_id)
        .where(s1.c.session_id == session_id)
        .where(s2.c.timestamp >= start_time)
        .where(s2.c.timestamp <= end_time))
    stmt_update = (update(
        sessions_table)
        .where(sessions_table.c.session_id.in_(stmt_select))
        .values(track_id=track_id))
    return stmt_update


def stmt_description(session_id: int, name: str, desc: str):
    return (update(
        sessions_table)
        .where(sessions_table.c.session_id == session_id)
        .values(name=name, description=desc))


def stmt_setup(session_id: int):
    fcal = calibrations_table.alias()
    rcal = calibrations_table.alias()
    return (select(
        setups_table.c.name,
        linkages_table.c.name,
        fcal,
        rcal)
        .join(linkages_table, linkages_table.c.linkage_id == setups_table.c.linkage_id)
        .join(fcal, fcal.c.calibration_id == setups_table.c.front_calibration_id)
        .join(rcal, rcal.c.calibration_id == setups_table.c.rear_calibration_id)
        .join(sessions_table, sessions_table.c.setup_id == setups_table.c.setup_id)
        .where(sessions_table.c.session_id == session_id))
