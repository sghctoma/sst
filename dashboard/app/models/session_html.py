from app.extensions import db


class SessionHtml(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    script = db.Column(db.String, nullable=False)
    travel = db.Column(db.String, nullable=False)
    velocity = db.Column(db.String, nullable=False)
    map = db.Column(db.String, nullable=False)
    lr = db.Column(db.String, nullable=False)
    sw = db.Column(db.String, nullable=False)
    setup = db.Column(db.String, nullable=False)
    desc = db.Column(db.String, nullable=False)
    f_thist = db.Column(db.String)
    f_fft = db.Column(db.String)
    f_vhist = db.Column(db.String)
    r_thist = db.Column(db.String)
    r_fft = db.Column(db.String)
    r_vhist = db.Column(db.String)
    cbalance = db.Column(db.String)
    rbalance = db.Column(db.String)
