"""Herramientas de edad: mínimos cuadrados ponderados, pico, delta y bootstrap por filas."""
# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.numerica import mco_estable, coeficientes, factorizar, cov_cluster

# ----------------------------------------------------------------------------
# Matrices de diseño
# ----------------------------------------------------------------------------
BASE_RELAB = "Obrero/empleado particular"


def dummies(serie, base, prefijo):
    """Dummies de una categórica con categoría de referencia declarada."""
    cats = [c for c in pd.Categorical(serie).categories if c != base]
    M = np.column_stack([(serie == c).astype(float).to_numpy() for c in cats]) if cats else np.empty((len(serie), 0))
    return M, [f"{prefijo}[{c}]" for c in cats]


def diseno_edad(df, controles=False, grado=2, centro=0.0, escala=1.0, base_relab=BASE_RELAB):
    """X = [1, a, a^2, ..., (controles)] con a = (age - centro)/escala.  Devuelve (X, nombres).
    Para grados altos conviene centrar y escalar (p. ej. centro=40, escala=10) por condicionamiento numérico."""
    a = (df["age"].to_numpy(float) - centro) / escala
    cols = [np.ones(len(df))] + [a ** p for p in range(1, grado + 1)]
    nombres = ["const"] + ["age" if p == 1 else f"age^{p}" for p in range(1, grado + 1)]
    if controles:
        cols.append(df["totalHoursWorked"].to_numpy(float)); nombres.append("totalHoursWorked")
        D, nd = dummies(df["relab_f"], base_relab, "relab")
        cols += [D[:, j] for j in range(D.shape[1])]; nombres += nd
    return np.column_stack(cols), nombres


# ----------------------------------------------------------------------------
# MCO con errores estándar robustos
# ----------------------------------------------------------------------------
def mco(X, y, pesos=None):
    return mco_estable(X, y, pesos)


def tabla_coeficientes(fit, nombres, V="V_hc1"):
    """Tabla con coeficiente, EE clásico, EE robusto, t y p (con el EE elegido)."""
    se_cl = np.sqrt(np.diag(fit["V_cl"])); se_r = np.sqrt(np.diag(fit[V]))
    t = fit["beta"] / se_r
    p = 2 * stats.t.sf(np.abs(t), fit["n"] - fit["k"])
    return pd.DataFrame({"coeficiente": fit["beta"], "EE clasico": se_cl, f"EE {V[2:].upper()}": se_r, "t": t, "p": p}, index=nombres)


# ----------------------------------------------------------------------------
# Edad pico
# ----------------------------------------------------------------------------
def pico(beta, i1=1, i2=2, centro=0.0, escala=1.0):
    """Vértice de la parábola en la escala original de la edad: centro + escala * (-b1 / (2 b2))."""
    return centro + escala * (-beta[i1] / (2.0 * beta[i2]))


def pico_delta(beta, V, i1=1, i2=2, centro=0.0, escala=1.0):
    """Edad pico y su EE por el método delta: g = d pico / d beta."""
    b1, b2 = beta[i1], beta[i2]
    g = np.zeros(len(beta)); g[i1] = -escala / (2 * b2); g[i2] = escala * b1 / (2 * b2 ** 2)
    return pico(beta, i1, i2, centro, escala), float(np.sqrt(g @ V @ g))




def banda_delta(fit, edades, V="V_hc1", centro=0.0, escala=1.0, grado=2, nivel=0.95, x_extra=None):
    """Banda puntual del perfil predicho: EE por el método delta (lineal en beta)."""
    a = (np.asarray(edades, float) - centro) / escala
    k = len(fit["beta"])
    G = np.zeros((len(a), k)); G[:, 0] = 1
    for p in range(1, grado + 1):
        G[:, p] = a ** p
    if x_extra is not None:
        G[:, grado + 1:] = x_extra
    pred = G @ fit["beta"]
    se = np.sqrt(np.einsum("ij,jk,ik->i", G, fit[V], G))
    z = stats.norm.ppf(0.5 + nivel / 2)
    return pred, pred - z * se, pred + z * se


# ----------------------------------------------------------------------------
# Bootstrap percentil
# ----------------------------------------------------------------------------
def bootstrap(X, y, B=2000, semilla=2026, pesos=None, i1=1, i2=2, centro=0.0, escala=1.0, estadisticos=None):
    """Bootstrap no paramétrico por observaciones. Devuelve betas (B x k), picos (B,)
    y el número de réplicas con b2 >= 0 (pico inexistente)."""
    rng = np.random.default_rng(semilla)
    X = np.asarray(X, float); y = np.asarray(y, float); n = len(y)
    betas = np.empty((B, X.shape[1])); extra = []
    for b in range(B):
        idx = rng.integers(0, n, n)
        Xb, yb = X[idx], y[idx]
        if pesos is not None:                      # MCO ponderado en la réplica
            w = np.sqrt(np.asarray(pesos, float)[idx]); Xb, yb = Xb * w[:, None], yb * w
        # solo los coeficientes (mínimos cuadrados con escalado y SVD): lo único que necesita el pico
        betas[b] = coeficientes(Xb, yb)
        if estadisticos is not None:
            extra.append(estadisticos(betas[b], idx))
    picos = centro + escala * (-betas[:, i1] / (2 * betas[:, i2]))
    sin_pico = int((betas[:, i2] >= 0).sum())
    out = dict(betas=betas, picos=picos, sin_pico=sin_pico)
    if estadisticos is not None:
        out["extra"] = np.array(extra)
    return out






# ----------------------------------------------------------------------------
# Pruebas y descriptivas
# ----------------------------------------------------------------------------
