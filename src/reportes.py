"""Tablas CSV/LaTeX y descriptivas ponderadas para los cuadernos."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display,HTML,Markdown

def tabla(df,ruta,decimales=4,mostrar=True,plegable=None):
    ruta=Path(ruta);ruta.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(ruta.with_suffix('.csv'),index=False)
    df.to_latex(ruta.with_suffix('.tex'),index=False,longtable=len(df)>30,escape=True,float_format=lambda x:f'{x:.{decimales}f}')
    if mostrar:
        html=df.to_html(index=False,float_format=lambda x:f'{x:.{decimales}f}',border=0)
        if plegable:html=f'<details><summary>{plegable}</summary>{html}</details>'
        display(HTML(html))
    return df

def alcance(df):
    """Tamaño observado y expansión original, sin normalizar los pesos."""
    w=df.fex_c.to_numpy(float)
    if not np.isfinite(w).all() or not (w>0).all():
        raise ValueError('La población representada requiere fex_c finito y positivo.')
    return dict(n_muestra=len(df),personas_representadas=float(w.sum()))


def nota_poblacion(df,ambito='Muestra de estimación',fig=None):
    r=alcance(df)
    texto=f'{ambito}: {r["n_muestra"]:,} registros; aproximadamente {r["personas_representadas"]:,.0f} personas representadas por fex_c.'
    if fig is None:display(Markdown(texto+' IC del total: no disponible con el diseño suministrado.'))
    else:fig.suptitle(texto,fontsize=10,fontweight='normal')
def cobertura_grupos(df,grupos):
    if isinstance(grupos,str):grupos=[grupos]
    rows=[]
    for keys,d in df.groupby(grupos,observed=True,dropna=False):
        if not isinstance(keys,tuple):keys=(keys,)
        rows.append(dict(zip(grupos,keys))|alcance(d))
    return pd.DataFrame(rows)


def guardar(fig,ruta):
    ruta=Path(ruta);ruta.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(ruta.with_suffix('.png'),dpi=170,bbox_inches='tight')
    fig.savefig(ruta.with_suffix('.svg'),bbox_inches='tight')
    plt.show();plt.close(fig)

def media_ponderada(x,w):
    x,w=np.asarray(x,float),np.asarray(w,float);ok=np.isfinite(x)&np.isfinite(w)&(w>0)
    x,w=x[ok],w[ok];n=len(x)
    if n<2:return dict(media=np.nan,sd=np.nan,ee=np.nan,n=n,poblacion=w.sum(),n_efectivo=np.nan)
    mu=np.average(x,weights=w)
    # Sandwich HC1 de la regresión ponderada sobre una constante.
    ee=np.sqrt(n/(n-1)*np.sum(w*w*(x-mu)**2)/w.sum()**2)
    return dict(media=mu,sd=np.sqrt(np.average((x-mu)**2,weights=w)),ee=ee,n=n,poblacion=w.sum(),n_efectivo=w.sum()**2/(w@w))

def por_grupo(df,grupos,col='log_y',min_n=2):
    if isinstance(grupos,str):grupos=[grupos]
    rows=[]
    for keys,d in df.groupby(grupos,observed=True):
        if not isinstance(keys,tuple):keys=(keys,)
        r=media_ponderada(d[col],d.fex_c)
        if r['n']>=min_n:rows.append(dict(zip(grupos,keys))|r)
    t=pd.DataFrame(rows)
    t['IC_inf']=t.media-1.96*t.ee;t['IC_sup']=t.media+1.96*t.ee
    return t

def resumen_variables(df):
    rows=[];n=len(df)
    for c in df:
        s=df[c];num=pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
        r=dict(variable=c,tipo=str(s.dtype),filas=n,no_nulos=int(s.notna().sum()),porcentaje_no_nulos=100*s.notna().mean(),valores_distintos=s.nunique(dropna=True))
        r.update({k:np.nan for k in ['media','desv_est','minimo','p25','mediana','p75','maximo']})
        if num and s.notna().any():r.update(dict(media=s.mean(),desv_est=s.std(),minimo=s.min(),p25=s.quantile(.25),mediana=s.median(),p75=s.quantile(.75),maximo=s.max()))
        r['moda']=str(s.mode().iloc[0]) if s.notna().any() else ''
        rows.append(r)
    return pd.DataFrame(rows)
