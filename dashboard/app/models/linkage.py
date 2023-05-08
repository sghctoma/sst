import io
import csv

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

    def _process_w_lr(self, reader) -> bool:
        shock_travel = []
        wheel_travel = []
        leverage_ratio = []
        shock = 0
        for row in reader:
            wheel = float(row['Wheel_T'])
            leverage = float(row['Leverage_R'])
            shock_travel.append(shock)
            wheel_travel.append(wheel)
            leverage_ratio.append(leverage)
            shock += 1.0 / leverage
        self.data = '\n'.join([f'{z[0]},{z[1]}' for z in zip(wheel_travel,
                                                             leverage_ratio)])
        return len(shock_travel) != 0 and len(wheel_travel) != 0

    def _process_w_s(self, reader):
        shock_travel = []
        wheel_travel = []
        leverage_ratio = []
        idx = 0
        for row in reader:
            s = float(row['Shock_T'])
            w = float(row['Wheel_T'])
            lr = 0
            if idx > 0:
                sdiff = s - shock_travel[idx-1]
                wdiff = w - wheel_travel[idx-1]
                lr = wdiff / sdiff
                leverage_ratio[idx-1] = lr
            shock_travel.append(s)
            wheel_travel.append(w)
            idx += 1

            # this will be overwritten in the next run, except for the last row
            leverage_ratio.append(lr)

        self.data = '\n'.join([f'{z[0]},{z[1]}' for z in zip(wheel_travel,
                                                             leverage_ratio)])
        return len(shock_travel) != 0 and len(leverage_ratio) != 0

    def validate(self) -> bool:
        f = io.StringIO(self.data)
        reader = csv.DictReader(f, delimiter=';')
        if 'Wheel_T' not in reader.fieldnames:
            return False
        if 'Leverage_R' in reader.fieldnames:
            try:
                return self._process_w_lr(reader)
            except BaseException:
                return False
        elif 'Shock_T' in reader.fieldnames:
            try:
                return self._process_w_s(reader)
            except BaseException:
                return False
            pass
        else:
            return False
