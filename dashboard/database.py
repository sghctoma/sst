from sqlalchemy import (
    Column, Integer, LargeBinary, MetaData, String, Table,
    ForeignKey,
    insert, desc, select, update
)


metadata_obj = MetaData()

bokeh_components_table = Table(
    'bokeh_components',
    metadata_obj,
    Column('session_id', Integer, ForeignKey('sessions.session_id')),
    Column('script', String),
    Column('travel', String),
    Column('velocity', String),
    Column('map', String),
    Column('lr', String),
    Column('sw', String),
    Column('setup', String),
    Column('desc', String),
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
