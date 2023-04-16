from dataclasses import dataclass

from app.extensions import db


@dataclass
class Linkage(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String, nullable=False)
    head_angle: float = db.Column(db.Float, nullable=False)
    front_stroke: float = db.Column(db.Float, nullable=False)
    rear_stroke: float = db.Column(db.Float, nullable=False)
    data: str = db.Column('raw_lr_data', db.String, nullable=False)

    def validate(self) -> bool:
        shock_travel = []
        wheel_travel = []
        shock = 0
        for line in self.data.split('\n'):
            try:
                split = line.split(',')
                wheel = float(split[0])
                leverage = float(split[1])
                shock_travel.append(shock)
                wheel_travel.append(wheel)
                shock += 1.0 / leverage
            except BaseException:
                pass
        return len(shock_travel) != 0 and len(wheel_travel) != 0
