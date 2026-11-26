"""Explicit experimental variants; frozen production/research functions stay intact."""
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class Protocol:
    q_scale: float = 1.0
    omega_scale: float = 1.0
    tilt: float = 1.0
    allocation: str = 'legacy'


def posterior(cov, prior, p, q, omega, tau=.05):
    """BL mean using view-space solve; tau*cov is uncertainty of the prior mean."""
    if len(q) == 0:
        return prior.copy()
    c = tau * cov
    return prior + c @ p.T @ np.linalg.solve(p @ c @ p.T + np.diag(omega), q-p @ prior)


def project_box_simplex(v, lower=.005, upper=.1):
    """Euclidean projection onto sum(w)=1, lower<=w<=upper (uniform bounds)."""
    v = np.asarray(v, dtype=float)
    if v.ndim != 1 or not np.isfinite(v).all() or len(v) == 0:
        raise ValueError('Expected finite nonempty vector')
    if lower < 0 or upper < lower or len(v)*lower > 1+1e-12 or len(v)*upper < 1-1e-12:
        raise ValueError('Infeasible bounds')
    lo, hi = float(np.min(v-upper)), float(np.max(v-lower))
    for _ in range(100):
        mid = (lo+hi)/2
        if np.clip(v-mid, lower, upper).sum() > 1:
            lo = mid
        else:
            hi = mid
    w = np.clip(v-(lo+hi)/2, lower, upper)
    if abs(w.sum()-1) > 1e-10:
        raise ArithmeticError('Projection residual')
    return w


def round_box_simplex(w, lower=.005, upper=.1, units=10000):
    """Largest remainder on a feasible integer grid; no sector constraints here."""
    w = np.asarray(w,dtype=float)
    if not np.isfinite(w).all() or abs(w.sum()-1)>1e-9 or np.any(w<lower-1e-9) or np.any(w>upper+1e-9):
        raise ValueError('Input must already satisfy continuous constraints')
    low=int(np.ceil(lower*units-1e-9)); high=int(np.floor(upper*units+1e-9))
    if low>high or len(w)*low>units or len(w)*high<units:
        raise ValueError('Infeasible grid')
    raw=w*units; out=np.clip(np.floor(raw).astype(int),low,high)
    while out.sum()<units:
        eligible=np.flatnonzero(out<high)
        j=eligible[np.argmax((raw-out)[eligible])];out[j]+=1
    while out.sum()>units:
        eligible=np.flatnonzero(out>low)
        j=eligible[np.argmax((out-raw)[eligible])];out[j]-=1
    return out/units


def weights(mu, spec, lower=.005, upper=.1):
    n=len(mu);std=mu.std()
    if std<1e-10:
        raw=np.ones(n)/n
    else:
        raw=np.clip((1+spec.tilt*(mu-mu.mean())/std)/n,lower,upper)
        raw/=raw.sum()
    if spec.allocation=='legacy':return raw
    if spec.allocation=='projected':return project_box_simplex(raw,lower,upper)
    if spec.allocation=='rounded':return round_box_simplex(project_box_simplex(raw,lower,upper),lower,upper)
    raise ValueError(spec.allocation)
