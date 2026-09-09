"""Perfil cuadrático, bootstrap percentil y método delta con fex_c."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from perfil_edad import diseno_edad,mco,pico_delta,banda_delta,bootstrap,tabla_coeficientes
from src.reportes import tabla,guardar,por_grupo,alcance,nota_poblacion,cobertura_grupos
ROOT=Path(__file__).resolve().parents[2];SAL=ROOT/'punto1_perfil_edad_ingreso/salidas'
BLUE,RED,GRAY='#1463AE','#A6405C','#65717C'

def cargar():
    m=pd.read_csv(ROOT/'datos/limpios/geih2018_muestra.csv')
    assert m.fex_c.gt(0).all()
    return m

def descriptivas(m):
    nota_poblacion(m,'Descriptivas de edad')
    medias=por_grupo(m,'age',min_n=20);horas=por_grupo(m,'age','totalHoursWorked',20)
    tabla(medias,SAL/'medias_edad',plegable='Medias por edad: n, población representada e intervalos de la media')
    tabla(horas,SAL/'horas_edad',plegable='Horas por edad: n y población representada')
    bins=pd.cut(m.age,[17,25,35,45,55,65,92]);comp=pd.crosstab(bins,m.relab_f,values=m.fex_c,aggfunc='sum',normalize='index')
    tabla(cobertura_grupos(m.assign(grupo_edad=bins),['grupo_edad','relab_f']),SAL/'poblacion_edad_empleo',decimales=0,plegable='Población representada por grupo de edad y tipo de empleo')
    fig,ax=plt.subplots(2,2,figsize=(14,10),layout='constrained')
    pop=m.groupby('age').fex_c.sum()/1000;ax[0,0].bar(pop.index,pop,color=BLUE)
    ax[0,0].set(title='(a) Población representada por edad',xlabel='Edad',ylabel='Miles de personas, fex_c')
    ax[0,1].errorbar(medias.age,medias.media,yerr=1.96*medias.ee,fmt='o',ms=3,color=BLUE,alpha=.8)
    ax[0,1].set(title='(b) Media ponderada de log(ingreso) e IC 95%',xlabel='Edad',ylabel='Media de log(ingreso)')
    ax[1,0].plot(horas.age,horas.media,'o-',ms=3,color=BLUE)
    ax[1,0].set(title='(c) Horas semanales medias ponderadas',xlabel='Edad',ylabel='Horas totales')
    comp.plot.bar(stacked=True,ax=ax[1,1],legend=False,colormap='tab20')
    ax[1,1].set_title('(d) Tipo de empleo por grupo de edad',pad=77)
    ax[1,1].legend(loc='lower center',bbox_to_anchor=(.5,1.01),ncol=2,fontsize=8,frameon=False)
    ax[1,1].set(xlabel='Grupo de edad',ylabel='Proporción ponderada');ax[1,1].tick_params(axis='x',rotation=25)
    nota_poblacion(m,fig=fig);guardar(fig,SAL/'figuras/fig01_datos_edad')
    return medias

def estimar(m):
    nota_poblacion(m,'Ambos modelos de edad')
    y=m.log_y.to_numpy();w=m.fex_c.to_numpy();fits={};boots={};rows=[]
    for nombre,controles in [('Incondicional',False),('Condicional',True)]:
        X,noms=diseno_edad(m,controles);f=mco(X,y,w)
        boot=bootstrap(X,y,B=2000,pesos=w);valid=boot['picos'][boot['betas'][:,2]<0]
        p,se=pico_delta(f['beta'],f['V_hc1']);lo,hi=np.quantile(valid,[.025,.975])
        assert f['beta'][2]<0 and m.age.min()<p<m.age.max()
        rows.append(dict(modelo=nombre,pico=p,EE_delta=se,IC_delta_inf=p-1.96*se,IC_delta_sup=p+1.96*se,IC_percentil_inf=lo,IC_percentil_sup=hi,EE_bootstrap=np.std(valid,ddof=1),sesgo_bootstrap=np.mean(valid)-p,replicas_sin_maximo=boot['sin_pico'],R2_ponderado=f['r2'],RMSE_ponderado=f['rmse_ponderado'],n=len(m)))
        coef=tabla_coeficientes(f,noms).reset_index(names='variable')
        tabla(coef,SAL/f'coeficientes_{nombre.lower()}',mostrar=False)
        fits[nombre]=(f,X,noms);boots[nombre]=boot
    res=tabla(pd.DataFrame(rows).assign(personas_representadas=alcance(m)['personas_representadas']),SAL/'edad_pico_intervalos')
    # Tabla comparativa completa con coeficientes, precisión, pico y ajuste.
    tablas=[]
    for nom,(f,X,nms) in fits.items():
        coef=tabla_coeficientes(f,nms).reset_index(names='variable')[['variable','coeficiente','EE HC1']]
        coef.columns=['variable',f'coef_{nom}',f'EE_HC1_{nom}'];tablas.append(coef)
    comparacion=tablas[0].merge(tablas[1],on='variable',how='outer')
    metricas=[]
    for etiqueta,campo in [('Edad pico','pico'),('IC percentil 95%: inferior','IC_percentil_inf'),
                           ('IC percentil 95%: superior','IC_percentil_sup'),('R² ponderado','R2_ponderado'),
                           ('RMSE ponderado','RMSE_ponderado'),('Observaciones','n'),('Personas representadas','personas_representadas')]:
        fila={'variable':etiqueta}
        for nom in fits:
            fila[f'coef_{nom}']=res.loc[res.modelo==nom,campo].iloc[0]
        metricas.append(fila)
    tabla(pd.concat([comparacion,pd.DataFrame(metricas)],ignore_index=True),SAL/'comparacion_regresiones')
    return fits,boots,res


def perfiles(m,fits,boots,res):
    nota_poblacion(m,'Ajuste de los perfiles y bootstrap')
    edades=np.arange(18,76);tab=pd.DataFrame({'edad':edades});fig,ax=plt.subplots(1,2,figsize=(13,4.8),layout='constrained')
    for nom,color in [('Incondicional',BLUE),('Condicional',RED)]:
        f,X,_=fits[nom];extra=np.tile(np.average(X[:,3:],axis=0,weights=m.fex_c),(len(edades),1)) if X.shape[1]>3 else None
        pr,lo,hi=banda_delta(f,edades,x_extra=extra)
        tab[nom]=pr;tab[nom+'_inf']=lo;tab[nom+'_sup']=hi
        p=res.loc[res.modelo==nom,'pico'].iloc[0]
        ax[0].plot(edades,pr,label=f'{nom}: pico {p:.1f}',color=color)
        ax[0].fill_between(edades,lo,hi,color=color,alpha=.12)
        ps=boots[nom]['picos'];ps=ps[boots[nom]['betas'][:,2]<0]
        ax[1].hist(ps,bins=35,density=True,color=color,alpha=.4,label=nom)
        a,b=np.quantile(ps,[.025,.975]);ax[1].axvline(a,color=color,ls=':');ax[1].axvline(b,color=color,ls=':')
    ax[0].set(title='Perfiles comparados: ponderación fex_c',xlabel='Edad',ylabel='Log(ingreso) predicho');ax[0].legend()
    ax[1].set(title='Bootstrap de los picos: extremos percentiles 2.5 y 97.5',xlabel='Edad pico',ylabel='Densidad');ax[1].legend()
    nota_poblacion(m,fig=fig);guardar(fig,SAL/'figuras/fig02_perfiles_bootstrap');tabla(tab,SAL/'perfiles_predichos',mostrar=False)

def robustez(m):
    nota_poblacion(m,'Referencia de robustez; cada variante tiene su propio total en la tabla')
    rows=[]
    casos=[('Incondicional, fex_c',m,False,True,'log_y'),('Incondicional, sin pesos',m,False,False,'log_y'),('Sin extremos, fex_c',m.loc[~m.alerta_extremo],False,True,'log_y'),('Ingreso por hora, fex_c',m.assign(log_h=np.log(m.y_total_m_ha)),False,True,'log_h'),('Condicional, fex_c',m,True,True,'log_y')]
    casos += [(lab,m.loc[mask],False,True,'log_y') for lab,mask in [('Hombres',m.female==0),('Mujeres',m.female==1),('Sin terciaria',m.terciaria==0),('Con terciaria',m.terciaria==1),('Formales',m.formal==1),('Informales',m.formal==0)]]
    fig,ax=plt.subplots(1,3,figsize=(16,6),gridspec_kw={'width_ratios':[1.5,1,1]},layout='constrained')
    for lab,d,con,pond,col in casos:
        X,_=diseno_edad(d,con);f=mco(X,d[col],d.fex_c if pond else None);p,se=pico_delta(f['beta'],f['V_hc1'])
        rows.append(dict(variante=lab,n=len(d),personas_representadas=alcance(d)['personas_representadas'] if pond else np.nan,pico=p,IC_inf=p-1.96*se,IC_sup=p+1.96*se,curvatura=f['beta'][2],R2=f['r2']))
        if lab in ['Hombres','Mujeres','Sin terciaria','Con terciaria']:
            a=ax[1] if 'terciaria' in lab else ax[2];grid=np.arange(18,76);pr,lo,hi=banda_delta(f,grid)
            a.plot(grid,pr,label=lab);a.fill_between(grid,lo,hi,alpha=.1)
    r=pd.DataFrame(rows);tabla(r,SAL/'robustez_heterogeneidad')
    ax[0].errorbar(r.pico,np.arange(len(r)),xerr=[r.pico-r.IC_inf,r.IC_sup-r.pico],fmt='o',capsize=3)
    ax[0].set(yticks=np.arange(len(r)),yticklabels=r.variante,xlabel='Edad pico e IC 95% delta HC1',title='(a) Pico por variante');ax[0].invert_yaxis()
    for a,title in zip(ax[1:],['(b) Perfil por educación','(c) Perfil por sexo']):a.set(title=title,xlabel='Edad',ylabel='Log(ingreso) predicho');a.legend(fontsize=9)
    guardar(fig,SAL/'figuras/fig03_robustez');return r


def interpretar(m):
    y = m.log_y.to_numpy()
    w = m.fex_c.to_numpy()
    X, nombres = diseno_edad(
        m,
        controles=True
    )
    fit = mco(
        X,
        y,
        w
    )
    coef = pd.DataFrame({
        'variable': nombres,
        'b': fit['beta']
    })
    relab = coef[
        coef['variable'].str.startswith('relab[')
    ].copy()
    relab['brecha_porcentual_cat_ref'] = relab.apply(
        lambda r: 100 * np.expm1(r['b']),
        axis=1
    )
    relab['tipo'] = 'cat'
    relab = relab.rename(
        columns={
            'b': 'coef_Condicional'
        }
    )
    referencia = pd.DataFrame({
        'tipo': ['cat_referencia'],
        'variable': ['Relab[Empleado Particular]'],
        'coef_Condicional': ['-'],
        'brecha_porcentual_cat_ref': [0.0]
    })
    relab = pd.concat(
        [
            referencia,
            relab[
                [
                    'tipo',
                    'variable',
                    'coef_Condicional',
                    'brecha_porcentual_cat_ref'
                ]
            ]
        ],
        ignore_index=True
    )
    tabla(
        relab,
        SAL / 'interpretacion_relab_condicional'
    )
    fig, ax = plt.subplots(
        figsize=(10, 5.5),
        layout='constrained'
    )
    colores = [
        GRAY if tipo == 'cat_referencia'
        else BLUE if brecha >= 0
        else RED
        for tipo, brecha in zip(
            relab['tipo'],
            relab['brecha_porcentual_cat_ref']
        )
    ]
    ax.barh(
        relab['variable'],
        relab['brecha_porcentual_cat_ref'],
        color=colores
    )
    ax.axvline(
        0,
        color=GRAY,
        linewidth=1
    )
    ax.set(
        title='Brecha porcentual por tipo de empleo',
        xlabel='Brecha porcentual frente a Empleado Particular (%)',
        ylabel='Tipo de empleo'
    )
    ax.invert_yaxis()
    guardar(
        fig,
        SAL / 'figuras/fig04_brecha_relab_condicional'
    )
    return relab