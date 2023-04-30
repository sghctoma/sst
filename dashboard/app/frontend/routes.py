import msgpack
import pytz

from datetime import datetime
from http import HTTPStatus as status

from bokeh.resources import CDN
from flask import jsonify, render_template, Markup
from flask_jwt_extended import (
    verify_jwt_in_request,
    unset_jwt_cookies
)
from app.frontend import bp
from app.extensions import db
from app.models.session import Session
from app.models.session_html import SessionHtml
from app.models.track import Track
from app.telemetry.psst import Telemetry, dataclass_from_dict
from app.telemetry.map import track_data


@bp.route('/')
def dashboard():
    return render_template(
        'index.html',
        resources=Markup(CDN.render()),
    )


@bp.route('/bokeh/last', defaults={'session_id': None})
@bp.route('/bokeh/<int:session_id>')
def session_html(session_id):
    # Not using @jwt_required(optional=True), because we want to be able to
    # load the dashboard even with an invalid token.
    try:
        verify_jwt_in_request()
        full_access = True
    except BaseException:
        full_access = False

    if not session_id:
        session = db.session.execute(db.select(Session).order_by(
            Session.timestamp.desc()).limit(1)).scalar_one_or_none()
    else:
        session = db.session.execute(
            db.select(Session).filter_by(id=session_id)).scalar_one_or_none()
    if not session:
        return jsonify(), status.NOT_FOUND

    session_html = db.session.execute(db.select(SessionHtml).filter_by(
        session_id=session.id)).scalar_one_or_none()
    if not session_html:
        return jsonify(), status.NOT_FOUND
    components_script = Markup(session_html.script.replace(
        '<script type="text/javascript">', '').replace('</script>', ''))
    components_divs = [Markup(d) if d else None for d in session_html.divs]

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

    response = jsonify(
        id=session.id,
        name=session.name,
        description=session.description,
        start_time=t.Timestamp,
        end_time=end_time,
        suspension_count=suspension_count,
        full_track=full_track,
        session_track=session_track,
        script=components_script,
        divs=components_divs,
        full_access=full_access,
    )
    if not full_access:
        unset_jwt_cookies(response)
    return response
