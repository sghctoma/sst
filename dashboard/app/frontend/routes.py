from bokeh.resources import CDN
from flask import render_template
from markupsafe import Markup

from app.frontend import bp


@bp.route('/')
def dashboard():
    return render_template(
        'index.html',
        resources=Markup(CDN.render()),
    )
