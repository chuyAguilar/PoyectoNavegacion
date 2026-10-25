"""Filtro 1-Euro para la posicion de un marker.

`OneEuroFilter` es el de `tracker.py` (meta 003, fase 4): el mismo calculo,
con `filter` en vez de `filtrar`. `PositionFilter` son los tres 1-Euro (x, y,
z) que el tracker creaba por marker y aplicaba a `tvec` con el tiempo del
frame. La orientacion de Marker0 no se filtra (clarify.md P6 de la meta 003).
"""
from __future__ import annotations

import numpy as np


class OneEuroFilter:
    """Filtro 1-Euro para suavizado adaptativo de una senal escalar."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.0) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

    def _alpha(self, cutoff, dt):
        tau = 1.0 / (2 * np.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x: float, t: float) -> float:
        """La muestra `x` en el tiempo `t` (segundos), suavizada. La primera sale tal cual."""
        if self.t_prev is None:
            self.t_prev = t
            self.x_prev = x
            return x
        dt = max(t - self.t_prev, 1e-3)
        dx = (x - self.x_prev) / dt
        a_d = self._alpha(1.0, dt)
        dx_smooth = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff = self.min_cutoff + self.beta * np.abs(dx_smooth)
        a = self._alpha(cutoff, dt)
        x_smooth = a * x + (1 - a) * self.x_prev
        self.x_prev = x_smooth
        self.dx_prev = dx_smooth
        self.t_prev = t
        return x_smooth


class PositionFilter:
    """Tres 1-Euro, uno por eje, sobre la traslacion `tvec` (3x1) de un marker."""

    def __init__(self, min_cutoff: float, beta: float) -> None:
        self.filters = [OneEuroFilter(min_cutoff, beta) for _ in range(3)]

    def filter(self, tvec: np.ndarray, t: float) -> np.ndarray:
        """`tvec` filtrado, con la forma 3x1 que usa el tracker."""
        tvec_flat = np.asarray(tvec).flatten()
        tvec_filt = np.array([self.filters[j].filter(tvec_flat[j], t) for j in range(3)])
        return tvec_filt.reshape(3, 1)
