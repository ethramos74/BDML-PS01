"""Herramientas de la Seccion 3: matrices de diseno con trazabilidad de
variables, minimos cuadrados (ordinarios y ridge) con LOOCV exacto via la
matriz sombrero, e importancia de variables por grupos."""
import numpy as np
import pandas as pd
from sklearn.preprocessing import SplineTransformer


# ----------------------------------------------------------------------------
# Matriz de diseno
# ----------------------------------------------------------------------------
class Diseno:
    """Construye X a partir de una lista de terminos y recuerda, para cada
    columna, el conjunto de variables de las que depende (para importancia).

    Terminos admitidos:
      ("num", var)                 columna numerica tal cual
      ("poly", var, grado)         var, var^2, ..., var^grado (centrada en la media de entrenamiento)
      ("spline", var, n_knots)     base B-spline cubica (nudos en cuantiles de entrenamiento, extrapolacion lineal)
      ("cat", var)                 dummies con la primera categoria de entrenamiento como referencia
      ("inter", termA, termB)      productos columna a columna de dos terminos
    """

    def __init__(self, terminos):
        self.terminos = terminos
        self.ajustado = False

    # -- ajuste de parametros dependientes de entrenamiento ------------------
    def fit(self, df):
        self.par = {}
        for t in self.terminos:
            self._fit_termino(t, df)
        self.ajustado = True
        return self

    def _fit_termino(self, t, df):
        clave = repr(t)
        if t[0] == "poly":
            self.par[clave] = {"media": df[t[1]].mean()}
        elif t[0] == "spline":
            st = SplineTransformer(n_knots=t[2], degree=3, knots="quantile",
                                   extrapolation="linear", include_bias=False)
            st.fit(df[[t[1]]].to_numpy(dtype=float))
            self.par[clave] = {"st": st}
        elif t[0] == "cat":
            niveles = list(pd.Categorical(df[t[1]]).categories) if hasattr(df[t[1]], "cat") else sorted(df[t[1]].dropna().unique())
            presentes = [n for n in niveles if (df[t[1]] == n).any()]
            self.par[clave] = {"niveles": presentes}
        elif t[0] == "inter":
            self._fit_termino(t[1], df)
            self._fit_termino(t[2], df)

    # -- transformacion ------------------------------------------------------
    def _cols_termino(self, t, df):
        """Devuelve (matriz n x k, nombres, lista de conjuntos de variables)."""
        clave = repr(t)
        if t[0] == "num":
            return df[[t[1]]].to_numpy(dtype=float), [t[1]], [{t[1]}]
        if t[0] == "poly":
            x = df[t[1]].to_numpy(dtype=float) - self.par[clave]["media"]
            cols = np.column_stack([x ** k for k in range(1, t[2] + 1)])
            return cols, [f"{t[1]}^{k}" if k > 1 else t[1] for k in range(1, t[2] + 1)], [{t[1]}] * t[2]
        if t[0] == "spline":
            st = self.par[clave]["st"]
            cols = st.transform(df[[t[1]]].to_numpy(dtype=float))
            return cols, [f"bs({t[1]})_{k + 1}" for k in range(cols.shape[1])], [{t[1]}] * cols.shape[1]
        if t[0] == "cat":
            niveles = self.par[clave]["niveles"]
            v = df[t[1]].astype(str).to_numpy()
            cols = np.column_stack([(v == str(n)).astype(float) for n in niveles[1:]]) if len(niveles)>1 else np.empty((len(df), 0))
            return cols, [f"{t[1]}[{n}]" for n in niveles[1:]], [{t[1]}] * (len(niveles) - 1)
        if t[0] == "inter":
            A, na, va = self._cols_termino(t[1], df)
            B, nb, vb = self._cols_termino(t[2], df)
            cols, nombres, vars_ = [], [], []
            for i in range(A.shape[1]):
                for j in range(B.shape[1]):
                    cols.append(A[:, i] * B[:, j])
                    nombres.append(f"{na[i]}:{nb[j]}")
                    vars_.append(va[i] | vb[j])
            return (np.column_stack(cols) if cols else np.empty((len(df), 0))), nombres, vars_
        raise ValueError(t)

    def transform(self, df):
        assert self.ajustado
        bloques, nombres, vars_ = [np.ones((len(df), 1))], ["(Intercepto)"], [set()]
        for t in self.terminos:
            c, n, v = self._cols_termino(t, df)
            bloques.append(c); nombres += n; vars_ += v
        X = np.column_stack(bloques)
        return X, nombres, vars_

    def fit_transform(self, df):
        return self.fit(df).transform(df)

    def variables(self):
        out = set()
        def rec(t):
            if t[0] == "inter":
                rec(t[1]); rec(t[2])
            else:
                out.add(t[1])
        for t in self.terminos:
            rec(t)
        return out


# ----------------------------------------------------------------------------
# Minimos cuadrados penalizados (lambda = 0 es MCO) con LOOCV exacto
# ----------------------------------------------------------------------------
def ajustar_ridge(X, y, lam=0.0, escalar=None):
    """Ridge estable: RSS + lambda sum (s_j beta_j)^2, intercepto libre.

    PRESS es exacto para X, penalización y lambda fijos. No vuelve a estimar
    los nudos ni los hiperparámetros al excluir una fila. h=1 implica que
    el atajo 0/0 no está definido, no un error predictivo infinito real.
    """
    X, y = np.asarray(X, float), np.asarray(y, float)
    if not np.isfinite(X).all() or not np.isfinite(y).all() or lam < 0:
        raise ValueError("Diseño finito y lambda no negativo requeridos")
    n, p = X.shape
    if not np.allclose(X[:, 0], 1):
        raise ValueError("La primera columna debe ser el intercepto")
    if escalar is None:
        escalar = X.std(axis=0, ddof=0)
    escalar = np.asarray(escalar, float).copy(); escalar[0] = 0
    mu = X.mean(axis=0); mu[0] = 0
    escala = np.linalg.norm(X-mu, axis=0)
    # Columnas constantes a precisión de máquina no se amplifican al escalar.
    escala[escala < 1e-12] = 1
    Z = (X-mu)/escala
    T = np.diag(1/escala); T[0, 1:] = -mu[1:]/escala[1:]
    if lam == 0:
        P = np.linalg.pinv(Z, rcond=max(Z.shape)*np.finfo(float).eps)
        A_inv_z = P@P.T
        bz = P@y
    else:
        Az = Z.T@Z + lam*np.diag((escalar/escala)**2)
        A_inv_z = np.linalg.pinv(Az, hermitian=True)
        bz = A_inv_z@(Z.T@y)
    beta = T@bz
    ajuste = X@beta; e = y-ajuste
    # La diagonal de Z Z+ evita formar el producto inestable de dos inversas
    # cuando MCO tiene bases redundantes (splines e interacciones).
    h = np.clip(np.einsum('ij,ji->i', Z, P) if lam == 0 else
                np.einsum('ij,ij->i', Z@A_inv_z, Z), 0, 1)
    loo = np.divide(e, 1-h, out=np.full(n, np.inf), where=(1-h)>1e-9)
    return dict(beta=beta, ajuste=ajuste, resid=e, h=h, loo=loo,
                lam=lam, escalar=escalar, A_inv=T@A_inv_z@T.T, gl=float(h.sum()))


def rmse(a, b):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def loocv_rmse(fit):
    return float(np.sqrt(np.mean(fit["loo"] ** 2)))


def elegir_lambda_loocv(X, y, lams, escalar=None):
    """Devuelve la tabla lambda -> RMSE LOOCV y el lambda optimo. `escalar` permite
    fijar la escala de la penalizacion (p. ej. la del entrenamiento completo) cuando
    se trabaja con submuestras en las que algunas columnas casi no varian."""
    if escalar is None:
        escalar = X.std(axis=0, ddof=0); escalar[0] = 0.0
    filas = []
    for lam in lams:
        f = ajustar_ridge(X, y, lam, escalar)
        filas.append({"lambda": lam, "rmse_loocv": loocv_rmse(f), "gl_efectivos": float(np.sum(f["h"]))})
    tab = pd.DataFrame(filas)
    return tab, float(tab.loc[tab.rmse_loocv.idxmin(), "lambda"])


# ----------------------------------------------------------------------------
# Importancia por grupos de variables
# ----------------------------------------------------------------------------
def columnas_sin(vars_cols, quitar):
    """Indices de las columnas que NO dependen de ninguna variable en `quitar`."""
    quitar = set(quitar)
    return [j for j, v in enumerate(vars_cols) if not (v & quitar)]


def importancia_drop_one(Xtr, ytr, Xva, yva, vars_cols, grupos, lam=0.0):
    """Para cada grupo de variables, reajusta el modelo sin ese grupo y mide el
    aumento del RMSE en validacion y del RMSE LOOCV en entrenamiento."""
    base = ajustar_ridge(Xtr, ytr, lam)
    r_va0 = rmse(yva, Xva @ base["beta"]); r_loo0 = loocv_rmse(base)
    filas = []
    for nombre, vs in grupos.items():
        idx = columnas_sin(vars_cols, vs)
        f = ajustar_ridge(Xtr[:, idx], ytr, lam)
        filas.append({"grupo": nombre, "n_columnas": Xtr.shape[1] - len(idx),
                      "delta_rmse_validacion": rmse(yva, Xva[:, idx] @ f["beta"]) - r_va0,
                      "delta_rmse_loocv": loocv_rmse(f) - r_loo0})
    return pd.DataFrame(filas).sort_values("delta_rmse_loocv", ascending=False).reset_index(drop=True)


def importancia_permutacion(predecir, df_va, yva, grupos, n_rep=20, semilla=2026):
    """Permuta conjuntamente las columnas de cada grupo en validacion y mide el
    aumento medio del RMSE (con su desviacion entre repeticiones)."""
    rng = np.random.default_rng(semilla)
    base = rmse(yva, predecir(df_va))
    filas = []
    for nombre, vs in grupos.items():
        deltas = []
        for _ in range(n_rep):
            d = df_va.copy()
            perm = rng.permutation(len(d))
            for v in vs:
                d[v] = d[v].to_numpy()[perm]
            deltas.append(rmse(yva, predecir(d)) - base)
        filas.append({"grupo": nombre, "delta_rmse_permutacion": np.mean(deltas), "sd": np.std(deltas, ddof=1)})
    return pd.DataFrame(filas).sort_values("delta_rmse_permutacion", ascending=False).reset_index(drop=True)
