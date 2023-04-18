import msgpack
import pytz

from datetime import datetime

from bokeh.resources import CDN
from flask import render_template, Markup
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.main import bp
from app.extensions import db
from app.models.session import Session
from app.models.session_html import SessionHtml
from app.models.track import Track
from app.telemetry.psst import Telemetry, dataclass_from_dict
from app.telemetry.map import track_data


def _sessions_list(sessions: list) -> dict[str, tuple[int, str, str]]:
    last_day = datetime.min
    sessions_dict = dict()
    for s in sessions:
        d = datetime.fromtimestamp(s.timestamp)
        desc = s.description or f"No description for {s.name}"
        date_str = d.strftime('%Y.%m.%d')
        if d.date() != last_day:
            sessions_dict[date_str] = [(s.id, s.name, desc)]
            last_day = d.date()
        else:
            sessions_dict[date_str].append((s.id, s.name, desc))
    return sessions_dict


@bp.route('/', defaults={'session_id': None})
@bp.route('/<int:session_id>')
@jwt_required(optional=True)
def dashboard(session_id):
    full_access = get_jwt_identity() is not None

    sessions = db.session.execute(db.select(Session)).scalars()
    session_list = _sessions_list(list(sessions))

    session = db.session.execute(
        db.select(Session).filter_by(id=session_id)).scalar_one_or_none()
    if not session:
        return render_template(
            'empty.html',
            sessions=session_list,
            full_access=full_access,
            type="error",
            message="Session not found!",
        )
    track = db.session.execute(
        db.select(Track).filter_by(id=session.track)).scalar_one_or_none()

    d = msgpack.unpackb(session.data)
    t = dataclass_from_dict(Telemetry, d)

    suspension_count = 0
    if t.Front.Present:
        suspension_count += 1
    if t.Rear.Present:
        suspension_count += 1

    record_num = len(t.Front.Travel) if t.Front.Present else len(t.Rear.Travel)
    elapsed_time = record_num / t.SampleRate
    start_time = t.Timestamp
    end_time = start_time + elapsed_time
    full_track, session_track = track_data(track.track if track else None,
                                           start_time, end_time)

    session_html = db.session.execute(db.select(SessionHtml).filter_by(
        session_id=session.id)).scalar_one_or_none()
    if not session_html:
        return render_template(
            'empty.html',
            sessions=session_list,
            full_access=full_access,
            type="warning",
            message="Session cache not yet ready!",
        )
    components_script = session_html.script
    components_divs = [Markup(div) for div in session_html.divs]

    utc_str = datetime.fromtimestamp(t.Timestamp,
                                     pytz.UTC).strftime('%Y.%m.%d %H:%M')

    return render_template(
        'dashboard.html',
        sessions=session_list,
        resources=Markup(CDN.render()),
        suspension_count=suspension_count,
        name=session.name,
        date=utc_str,
        full_access=full_access,
        full_track=full_track,
        session_track=session_track,
        components_script=Markup(components_script),
        components_divs=components_divs)


@bp.route('/')
def index():
    return render_template('index.html')
