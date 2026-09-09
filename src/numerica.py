"""Mínimos cuadrados estables e inferencia con rango efectivo."""
import numpy as np


def factorizar(X):
    X = np.asarray(X, float)
    escala = np.linalg.norm(X, axis=0)
    escala[escala == 0] = 1
    Z = X / escala
    U, s, Vt = np.linalg.svd(Z, full_matrices=False)
    ok = s > max(Z.shape) * np.finfo(float).eps * s[0]
    P = (Vt[ok].T / s[ok]) @ U[:, ok].T
    P = P / escala[:, None]
    return P, int(ok.sum())


def coeficientes(X, y):
    # Escalado previo evita elevar al cuadrado el número de condición.
    X = np.asarray(X, float)
    escala = np.linalg.norm(X, axis=0)
    escala[escala == 0] = 1
    b=np.linalg.lstsq(X / escala, y, rcond=None)[0]
    return b / (escala[:,None] if b.ndim>1 else escala)


def mco_estable(X, y, pesos=None):
    X, y = np.asarray(X, float), np.asarray(y, float)
    if not np.isfinite(X).all() or not np.isfinite(y).all():
        raise ValueError("El diseño y el resultado deben ser finitos")
    n, p = X.shape
    w = np.ones(n) if pesos is None else np.asarray(pesos, float)
    if (w <= 0).any() or not np.isfinite(w).all():
        raise ValueError("Pesos positivos y finitos requeridos")
    w = w / w.mean()
    Xw, yw = X * np.sqrt(w[:, None]), y * np.sqrt(w)
    P, k = factorizar(Xw)
    if n <= k:
        raise ValueError("Sin grados de libertad residuales")
    beta = P @ yw
    ajust = X @ beta
    e, ew = y - ajust, yw - Xw @ beta
    bread = P @ P.T
    h = np.clip(np.einsum('ij,ji->i', Xw, P), 0, 1)
    sigma2 = float(ew @ ew / (n-k))
    V1 = (P * ew) @ (P * ew).T * n/(n-k)
    # HC3 no está definido para una observación con leverage unitario.
    er3 = np.divide(ew, 1-h, out=np.zeros_like(ew), where=(1-h)>1e-10)
    V3 = (P * er3) @ (P * er3).T
    if np.any(1-h <= 1e-10):
        V3[:] = np.nan
    sst = np.sum(w * (y-np.average(y, weights=w))**2)
    r2 = 1-float(ew@ew)/sst
    return dict(beta=beta, ajust=ajust, resid=e, resid_w=ew, XtX_inv=bread,
                h=h, n=n, k=k, p=p, sigma2=sigma2, V_cl=sigma2*bread,
                V_hc1=V1, V_hc3=V3, r2=r2,
                r2_adj=1-(1-r2)*(n-1)/(n-k), rmse=float(np.sqrt(np.mean(e**2))),
                rmse_ponderado=float(np.sqrt(np.average(e**2,weights=w))),
                Xw=Xw, yw=yw)


def cov_cluster(fit, grupos):
    """CR1 por hogar. No sustituye el diseño muestral completo del DANE."""
    _, g = np.unique(np.asarray(grupos).astype(str), return_inverse=True)
    G, n, k = g.max()+1, fit['n'], fit['k']
    if G < 2:
        raise ValueError("Se necesitan al menos dos hogares")
    scores = np.zeros((G, fit['p']))
    np.add.at(scores, g, fit['Xw'] * fit['resid_w'][:, None])
    B = fit['XtX_inv']
    return G/(G-1)*(n-1)/(n-k) * B @ (scores.T@scores) @ B
