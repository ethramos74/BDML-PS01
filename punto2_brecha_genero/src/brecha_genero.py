"""Herramientas de género: FWL ponderado, bootstrap por filas y picos por sexo."""
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
def dummies(serie, base, prefijo):
    """Dummies de una categórica con categoría de referencia declarada. Devuelve (M, nombres)."""
    cats = [c for c in pd.Categorical(serie).categories if c != base]
    M = np.column_stack([(serie == c).astype(float).to_numpy() for c in cats]) if cats else np.empty((len(serie), 0))
    return M, [f"{prefijo}[{c}]" for c in cats]


BASES = {"educ_f": "Secundaria completa", "relab_f": "Obrero/empleado particular", "sizeFirm_f": "Mas de 50 trabajadores",
         "oficio_grupo": "Operarios y transporte", "oficio_f": "Otros", "estrato_f": "3", "parentesco_f": "Jefe/a", "regSalud_f": "Contributivo"}


def diseno(df, bloques, con_intercepto=True):
    """Construye X a partir de una lista de bloques. Cada bloque es una cadena:
       'age2' -> age y age^2;  'female' -> female;  'horas' -> horas y horas^2/100;
       'fem_x_age2' -> female*age y female*age^2;  nombre de columna numérica -> tal cual;
       nombre de categórica en BASES -> dummies con su base.
    Devuelve (X, nombres, grupos) donde grupos asigna cada columna a su bloque."""
    cols, nombres, grupos = [], [], []
    if con_intercepto:
        cols.append(np.ones(len(df))); nombres.append("const"); grupos.append("const")
    for b in bloques:
        if b == "age2":
            a = df["age"].to_numpy(float); cols += [a, a ** 2]; nombres += ["age", "age^2"]; grupos += ["age", "age"]
        elif b == "horas":
            h = df["totalHoursWorked"].to_numpy(float); cols += [h, h ** 2 / 100]; nombres += ["horas", "horas^2/100"]; grupos += ["horas", "horas"]
        elif b == "fem_x_age2":
            a = df["age"].to_numpy(float); f = df["female"].to_numpy(float); cols += [f * a, f * a ** 2]; nombres += ["female x age", "female x age^2"]; grupos += ["female x age", "female x age"]
        elif b in BASES:
            M, nm = dummies(df[b], BASES[b], b); cols += [M[:, j] for j in range(M.shape[1])]; nombres += nm; grupos += [b] * M.shape[1]
        else:
            cols.append(df[b].to_numpy(float)); nombres.append(b); grupos.append(b)
    return np.column_stack(cols), nombres, grupos


# ----------------------------------------------------------------------------
# MCO
# ----------------------------------------------------------------------------
def mco(X, y, pesos=None):
    return mco_estable(X, y, pesos)


def tabla_coeficientes(fit, nombres, V="V_hc1"):
    se_cl = np.sqrt(np.diag(fit["V_cl"])); se_r = np.sqrt(np.diag(fit[V])); t = fit["beta"] / se_r
    return pd.DataFrame({"coeficiente": fit["beta"], "EE clasico": se_cl, f"EE {V[2:].upper()}": se_r, "t": t,
                         "p": 2 * stats.t.sf(np.abs(t), fit["n"] - fit["k"])}, index=nombres)




# ----------------------------------------------------------------------------
# Frisch–Waugh–Lovell
# ----------------------------------------------------------------------------
def residualizar(v, W):
    """Residuo de la proyección MCO de v (vector o matriz) sobre las columnas de W."""
    return v - W @ coeficientes(W,v)


def fwl(y, d, W, pesos=None):
    """Coeficiente de d en la regresión de y sobre [d, W] por FWL.
    Devuelve dict con el coeficiente, tres errores estándar (ingenuo n-2, corregido n-k, HC1 con n-k),
    los residuos de las dos etapas y el residuo final."""
    y = np.asarray(y, float); d = np.asarray(d, float); W = np.asarray(W, float)
    if pesos is not None:
        w=np.asarray(pesos,float);w=np.sqrt(w/w.mean())
        y,d,W=y*w,d*w,W*w[:,None]
    n, kW = W.shape; k = factorizar(np.column_stack([W, d]))[1]
    ey, ed = residualizar(y, W), residualizar(d, W)
    sdd = float(ed @ ed)
    b = float(ed @ ey) / sdd
    u = ey - b * ed                                   # = residuo de la regresion completa
    ss = float(u @ u)
    se_ingenuo = np.sqrt(ss / (n - 2) / sdd)          # lo que reporta una regresion de residuo sobre residuo
    se_corregido = np.sqrt(ss / (n - k) / sdd)        # grados de libertad de la regresion completa
    se_hc1 = np.sqrt(n / (n - k) * float((ed ** 2 * u ** 2).sum()) / sdd ** 2)
    return dict(b=b, se_ingenuo=se_ingenuo, se_corregido=se_corregido, se_hc1=se_hc1, ey=ey, ed=ed, u=u, n=n, k=k,
                r2_parcial=1 - ss / float(ey @ ey))


def bootstrap_fwl(y, d, W, B=1000, semilla=2026, pesos=None):
    """Bootstrap por observaciones repitiendo las dos etapas de FWL en cada réplica."""
    rng = np.random.default_rng(semilla); y = np.asarray(y, float); d = np.asarray(d, float); W = np.asarray(W, float); n = len(y)
    bs = np.empty(B)
    for r in range(B):
        idx = rng.integers(0, n, n)
        Wb=W[idx];Yb=np.column_stack([y[idx],d[idx]])
        if pesos is not None:
            sw=np.sqrt(np.asarray(pesos,float)[idx]);Wb=Wb*sw[:,None];Yb=Yb*sw[:,None]
        residual=residualizar(Yb,Wb);ey,ed=residual[:,0],residual[:,1]
        bs[r] = float(ed @ ey) / float(ed @ ed)
    return bs


def bootstrap_betas(X, y, B=1000, semilla=2026, pesos=None):
    """Bootstrap de los coeficientes (solo betas) de la regresión de y sobre X. Devuelve B x k."""
    rng = np.random.default_rng(semilla); X = np.asarray(X, float); y = np.asarray(y, float); n = len(y)
    out = np.empty((B, X.shape[1]))
    for r in range(B):
        idx = rng.integers(0, n, n); Xb, yb = X[idx], y[idx]
        if pesos is not None:
            w = np.sqrt(np.asarray(pesos, float)[idx]); Xb, yb = Xb * w[:, None], yb * w
        out[r] = coeficientes(Xb, yb)
    return out


# ----------------------------------------------------------------------------
# Intervalos
# ----------------------------------------------------------------------------


# ----------------------------------------------------------------------------
# Picos por sexo en el modelo con interacciones
# ----------------------------------------------------------------------------
def picos_por_sexo(beta, V, nombres):
    """Edades pico de hombres y mujeres y su diferencia (método delta) en un modelo con
    age, age^2, female x age, female x age^2 (los demás términos no afectan el vértice)."""
    i = {nm: j for j, nm in enumerate(nombres)}
    b1, b2, g1, g2 = beta[i["age"]], beta[i["age^2"]], beta[i["female x age"]], beta[i["female x age^2"]]
    p_h = -b1 / (2 * b2); p_m = -(b1 + g1) / (2 * (b2 + g2))
    gh = np.zeros(len(beta)); gh[i["age"]] = -1 / (2 * b2); gh[i["age^2"]] = b1 / (2 * b2 ** 2)
    gm = np.zeros(len(beta)); c1, c2 = b1 + g1, b2 + g2
    gm[i["age"]] = gm[i["female x age"]] = -1 / (2 * c2); gm[i["age^2"]] = gm[i["female x age^2"]] = c1 / (2 * c2 ** 2)
    gd = gm - gh
    return {"pico hombres": p_h, "EE hombres": float(np.sqrt(gh @ V @ gh)), "pico mujeres": p_m, "EE mujeres": float(np.sqrt(gm @ V @ gm)),
            "diferencia (M - H)": p_m - p_h, "EE diferencia": float(np.sqrt(gd @ V @ gd))}


def picos_de_betas(betas, nombres):
    """Picos de hombres y mujeres para una matriz de réplicas de beta (B x k)."""
    i = {nm: j for j, nm in enumerate(nombres)}
    b1, b2, g1, g2 = betas[:, i["age"]], betas[:, i["age^2"]], betas[:, i["female x age"]], betas[:, i["female x age^2"]]
    return -b1 / (2 * b2), -(b1 + g1) / (2 * (b2 + g2))


# ----------------------------------------------------------------------------
# Leverage e influencia
# ----------------------------------------------------------------------------
def diagnostico_influencia(f, corte_leverage=3.0, corte_residuo=3.0):
    """Leverage y residuo estudentizado externamente sobre el diseño ponderado de f.
    Leverage alto y atipicidad son condiciones separadas; influyente es cumplir ambas.
    La varianza del residuo excluye la propia observación para no enmascararla."""
    h, ew, n, k = f["h"], f["resid_w"], f["n"], f["k"]
    s2_i = ((n - k) * f["sigma2"] - ew ** 2 / (1 - h)) / (n - k - 1)
    t = ew / np.sqrt(np.maximum(s2_i, 1e-12) * (1 - h))
    alto = h > corte_leverage * h.mean(); atipico = np.abs(t) > corte_residuo
    return pd.DataFrame({"leverage": h, "residuo_estudentizado": t, "leverage_alto": alto,
                         "atipico": atipico, "influyente": alto & atipico})
