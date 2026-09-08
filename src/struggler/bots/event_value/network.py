"""A tiny one-hidden-layer tanh network, with no third-party dependencies."""
import json
import math
import random
from pathlib import Path

from .features import FEATURE_NAMES, TimingPrior

EXPOSURE_INDICES = tuple(i for i, n in enumerate(FEATURE_NAMES) if n.endswith(':exposure'))
SIGNED_INDICES = tuple(i for i, n in enumerate(FEATURE_NAMES) if n.endswith(':signed_exposure'))


class ValueNetwork:
    def __init__(self, hidden: int = 16, seed: int = 0, prior: TimingPrior = TimingPrior()):
        if hidden < 1:
            raise ValueError('hidden width must be positive')
        self.hidden, self.prior = hidden, prior
        rng = random.Random(seed)
        self.width = len(FEATURE_NAMES)
        self.w = [[rng.gauss(0, 1/math.sqrt(self.width)) for _ in range(self.width)]
                  for _ in range(hidden)]
        self.b = [0.0]*hidden
        self.out = [0.0]*hidden
        self.bias = 0.0

    @property
    def parameter_count(self):
        return self.hidden*(self.width+2)+1

    def forward(self, x):
        if len(x) != self.width:
            raise ValueError('feature width does not match checkpoint')
        h = [math.tanh(sum(a*b for a, b in zip(row, x))+bias)
             for row, bias in zip(self.w, self.b)]
        return sum(a*b for a, b in zip(h, self.out))+self.bias, h

    def predict(self, x):
        # The network learns a VP residual scaled by ten; current scoring is
        # supplied exactly by the engine, not relearned by the network.
        if len(x) != self.width:
            raise ValueError('feature width does not match checkpoint')
        if not any(x[i] > 0 for i in EXPOSURE_INDICES):
            return 0.0
        value = 10*self.forward(x)[0]
        signs = [x[i] for i in SIGNED_INDICES if x[i] != 0]
        # These six events only move influence toward their beneficiary.
        # Do not learn a bonus from exclusively hostile event exposure (or
        # a penalty from exclusively friendly exposure) from sparse data.
        if signs and all(s < 0 for s in signs):
            value = min(0.0, value)
        elif signs and all(s > 0 for s in signs):
            value = max(0.0, value)
        return value

    def fit_epoch(self, rows, *, rng, rate=0.03, batch_size=16):
        """Mini-batch SGD; clipping bounds one unusual scenario's gradient."""
        order = list(range(len(rows)))
        rng.shuffle(order)
        for start in range(0, len(order), batch_size):
            batch = order[start:start+batch_size]
            dw = [[0.0]*self.width for _ in range(self.hidden)]
            db, do = [0.0]*self.hidden, [0.0]*self.hidden
            bias = 0.0
            for index in batch:
                x, target = rows[index]
                if not any(x[i] > 0 for i in EXPOSURE_INDICES):
                    continue
                prediction, h = self.forward(x)
                error = max(-2, min(2, prediction-target/10))
                bias += error
                for j in range(self.hidden):
                    do[j] += error*h[j]
                    back = error*self.out[j]*(1-h[j]*h[j])
                    db[j] += back
                    for k, value in enumerate(x):
                        dw[j][k] += back*value
            step = rate/len(batch)
            self.bias -= step*bias
            for j in range(self.hidden):
                self.out[j] -= step*do[j]
                self.b[j] -= step*db[j]
                for k in range(self.width):
                    self.w[j][k] -= step*dw[j][k]

    def save(self, path, **metadata):
        data = dict(version=1, features=FEATURE_NAMES, hidden=self.hidden,
                    prior=self.prior.__dict__, w=self.w, b=self.b, out=self.out,
                    bias=self.bias, metadata=metadata)
        Path(path).write_text(json.dumps(data, indent=2)+'\n')

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        if data.get('version') != 1 or data.get('features') != list(FEATURE_NAMES):
            raise ValueError('incompatible event-value feature schema')
        model = cls(data['hidden'], prior=TimingPrior(**data['prior']))
        if (len(data['w']) != model.hidden or any(len(r) != model.width for r in data['w'])
                or len(data['b']) != model.hidden or len(data['out']) != model.hidden):
            raise ValueError('invalid network shape')
        numbers = [v for row in data['w'] for v in row] + data['b'] + data['out'] + [data['bias']]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in numbers):
            raise ValueError('nonfinite or nonnumeric network parameter')
        model.w, model.b, model.out, model.bias = data['w'], data['b'], data['out'], data['bias']
        return model
