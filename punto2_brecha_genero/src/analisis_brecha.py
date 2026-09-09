"""Brecha ponderada por fex_c, FWL, bootstrap percentil y perfiles por sexo."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display,Markdown
from brecha_genero import diseno,mco,fwl,bootstrap_fwl,bootstrap_betas,picos_por_sexo,picos_de_betas,diagnostico_influencia
from src.reportes import tabla,guardar,por_grupo,media_ponderada,alcance,nota_poblacion,cobertura_grupos
ROOT=Path(__file__).resolve().parents[2];SAL=ROOT/'punto2_brecha_genero/salidas'
BLUE,RED='#1463AE','#A6405C'
S5=['age2','educ_f','horas','relab_f','formal','sizeFirm_f','oficio_grupo']
ESCALERA={'S0':[],'S1':['age2'],'S2':['age2','educ_f'],'S3':['age2','educ_f','horas'],'S4':S5[:-1],'S5':S5,'S6':S5[:-1]+['oficio_f'],'S7':S5[:-1]+['oficio_f','estrato_f','jefe_hogar']}

def cargar():
    m=pd.read_csv(ROOT/'datos/limpios/geih2018_muestra.csv')
    return m.loc[m.maxEducLevel.notna()].reset_index(drop=True)

def descriptivas(m):
    nota_poblacion(m,'Descriptivas de género')
    rows=[];fig,ax=plt.subplots(2,2,figsize=(14,9),layout='constrained')
    medias=por_grupo(m,['female','age'],min_n=15);tabla(medias,SAL/'medias_edad_sexo',plegable='Medias por edad y sexo: n, población representada e IC de la media')
    tabla(cobertura_grupos(m,['female','oficio_grupo']),SAL/'poblacion_sexo_ocupacion',decimales=0,plegable='Población representada por sexo y ocupación')
    for s,label,color in [(0,'Hombres',BLUE),(1,'Mujeres',RED)]:
        d=m.loc[m.female==s];w=d.fex_c
        r={'sexo':label,'n':len(d),'poblacion_representada':w.sum()}
        for col in ['age','anios_educ','totalHoursWorked','terciaria','formal']:r[col]=np.average(d[col],weights=w)
        rows.append(r)
        ax[0,0].hist(d.log_y,bins=40,weights=w,density=True,alpha=.4,color=color,label=label)
        ax[0,1].hist(d.totalHoursWorked,bins=np.arange(0,130,4),weights=w,density=True,alpha=.4,color=color,label=label)
        g=medias.loc[medias.female==s]
        ax[1,1].errorbar(g.age,g.media,yerr=1.96*g.ee,fmt='o-',ms=2.5,alpha=.8,color=color,label=label,elinewidth=.6)
    comp=pd.crosstab(m.oficio_grupo,m.female,values=m.fex_c,aggfunc='sum',normalize='columns');comp.columns=['Hombres','Mujeres']
    comp.plot.barh(ax=ax[1,0],color=[BLUE,RED])
    for a,title in zip(ax.flat,['(a) Distribución ponderada del log-ingreso','(b) Horas semanales, ponderadas','(c) Ocupación, proporciones ponderadas','(d) Media por edad y sexo e IC puntual 95%']):a.set_title(title);a.legend(fontsize=8)
    ax[0,0].set(xlabel='Log(ingreso)',ylabel='Densidad');ax[0,1].set(xlabel='Horas',ylabel='Densidad');ax[1,0].set(xlabel='Proporción dentro del sexo',ylabel='');ax[1,1].set(xlabel='Edad',ylabel='Media de log(ingreso)')
    nota_poblacion(m,fig=fig);guardar(fig,SAL/'figuras/fig01_datos_sexo');return tabla(pd.DataFrame(rows),SAL/'descriptivas_sexo')

def estimar(m):
    nota_poblacion(m,'Muestra original de S0-S7, base del bootstrap')
    y=m.log_y.to_numpy();d=m.female.to_numpy();w=m.fex_c.to_numpy();fits={};rows=[]
    for nombre,bloques in ESCALERA.items():
        W,noms,_=diseno(m,bloques);X=np.column_stack([W,d]);f=mco(X,y,w);r=fwl(y,d,W,w)
        assert abs(r['b']-f['beta'][-1])<1e-8
        assert np.allclose(r['u'],np.sqrt(w/w.mean())*f['resid'],atol=1e-8)
        bs=bootstrap_fwl(y,d,W,B=1000 if nombre=='S5' else 500,pesos=w)
        lo,hi=np.quantile(bs,[.025,.975]);fits[nombre]=(f,r,W,noms,bs)
        rows.append(dict(modelo=nombre,beta_Female=r['b'],brecha_porcentual=100*np.expm1(r['b']),EE_analitico_HC1=r['se_hc1'],EE_bootstrap=bs.std(ddof=1),IC_percentil_inf=lo,IC_percentil_sup=hi,R2_ponderado=f['r2'],rango=f['k'],n=len(m),diferencia_FWL=abs(r['b']-f['beta'][-1])))
    tab=tabla(pd.DataFrame(rows).assign(personas_representadas=alcance(m)['personas_representadas']),SAL/'escalera_controles_fwl')
    fig,ax=plt.subplots(1,2,figsize=(13,4.5),layout='constrained')
    ax[0].errorbar(tab.modelo,tab.brecha_porcentual,yerr=[100*(np.exp(tab.beta_Female)-np.exp(tab.IC_percentil_inf)),100*(np.exp(tab.IC_percentil_sup)-np.exp(tab.beta_Female))],fmt='o-',capsize=3,color=RED)
    ax[0].set(title='Brecha e IC percentil 95%',ylabel='Diferencia de medias geométricas, %',xlabel='Conjunto de controles')
    ax[1].plot(tab.modelo,tab.EE_analitico_HC1,'o-',label='Analítico HC1');ax[1].plot(tab.modelo,tab.EE_bootstrap,'s-',label='Bootstrap por filas');ax[1].legend()
    ax[1].set(title='Precisión del coeficiente Female',ylabel='Error estándar, log-puntos',xlabel='Conjunto de controles')
    nota_poblacion(m,fig=fig);guardar(fig,SAL/'figuras/fig02_escalera');return fits,tab

def geometria(m,fits):
    nota_poblacion(m,'FWL y modelo completo S5, ambos ponderados')
    f,r,W,noms,bs=fits['S5'];sw=np.sqrt(m.fex_c/m.fex_c.mean()).to_numpy()
    # Las dos primeras proyecciones se muestran en unidades originales.
    ry,rd=r['ey']/sw,r['ed']/sw
    fig,axes=plt.subplots(2,2,figsize=(14,10),layout='constrained');ax=axes.flat
    ax[0].scatter(m.female-rd,m.female,s=4,alpha=.08,color=BLUE)
    ax[0].set(title='(a) Primera etapa para Female',xlabel='Proyección ponderada de Female en W',ylabel='Female observado')
    ax[1].scatter(m.log_y-ry,m.log_y,s=4,alpha=.08,color=BLUE)
    ax[1].set(title='(b) Primera etapa para log(ingreso)',xlabel='Proyección ponderada del log-ingreso en W',ylabel='Log(ingreso) observado')
    ax[2].scatter(rd,ry,s=5,alpha=.09,color=RED)
    grid=np.linspace(np.quantile(rd,.005),np.quantile(rd,.995),100)
    ax[2].plot(grid,r['b']*grid,color='black',lw=2.5,label=f'FWL: {r["b"]:.6f}')
    ax[2].plot(grid,f['beta'][-1]*grid,color='#E69F00',ls='--',lw=1.8,label=f'MCO completo ponderado: {f["beta"][-1]:.6f}')
    ax[2].set(title='(c) Segunda etapa FWL',xlabel='Residuo de Female',ylabel='Residuo de log(ingreso)');ax[2].legend()
    ufwl=ry-r['b']*rd;ucompleto=f['resid'];error=float(np.max(np.abs(ufwl-ucompleto)))
    assert error<1e-8
    ax[3].scatter(ucompleto,ufwl,s=8,alpha=.3,color=BLUE)
    lim=[min(ucompleto.min(),ufwl.min()),max(ucompleto.max(),ufwl.max())]
    ax[3].plot(lim,lim,color='black',ls='--',label='Igualdad: recta de 45°')
    ax[3].set(title='(d) Residuos FWL frente al modelo completo',xlabel='Residuo del MCO completo ponderado',ylabel='Residuo final de FWL',aspect='equal')
    ax[3].legend(loc='upper left');ax[3].text(.04,.84,f'Máxima diferencia absoluta: {error:.2e}',transform=ax[3].transAxes,fontsize=10)
    nota_poblacion(m,fig=fig);guardar(fig,SAL/'figuras/fig03_fwl')
    tabla(pd.DataFrame([dict(beta_FWL=r['b'],beta_MCO_completo=f['beta'][-1],max_diferencia_residuos=error,**alcance(m))]),SAL/'verificacion_fwl')

def perfiles(m):
    nota_poblacion(m,'Ajuste conjunto de S1 y S5 con interacciones por sexo')
    rows=[];preds=[];fitmap={};boots={};grid=np.arange(18,76,dtype=float)
    for nombre,bloques in [('S1',['age2']),('S5',S5)]:
        X,noms,_=diseno(m,bloques+['female','fem_x_age2']);f=mco(X,m.log_y,m.fex_c)
        bs=bootstrap_betas(X,m.log_y,B=1000,pesos=m.fex_c)
        ph,pm=picos_de_betas(bs,noms);ih=noms.index('age^2');ig=noms.index('female x age^2')
        good=(bs[:,ih]<0)&((bs[:,ih]+bs[:,ig])<0);ph,pm=ph[good],pm[good]
        p=picos_por_sexo(f['beta'],f['V_hc1'],noms);boots[nombre]=(ph,pm);fitmap[nombre]=(f,X,noms)
        for sexo,values,peak,se in [('Hombres',ph,p['pico hombres'],p['EE hombres']),('Mujeres',pm,p['pico mujeres'],p['EE mujeres'])]:
            ds=m.loc[m.female.eq(int(sexo=='Mujeres'))]
            lo,hi=np.quantile(values,[.025,.975]);rows.append(dict(modelo=nombre,sexo=sexo,pico=peak,media_bootstrap=values.mean(),EE_delta=se,IC_delta_inf=peak-1.96*se,IC_delta_sup=peak+1.96*se,IC_percentil_inf=lo,IC_percentil_sup=hi,replicas_sin_maximo=int((~good).sum()),n_ajuste=len(m),personas_ajuste=alcance(m)['personas_representadas'],n_sexo=len(ds),personas_sexo=alcance(ds)['personas_representadas']))
            G=np.tile(np.average(X,axis=0,weights=m.fex_c),(len(grid),1));s=int(sexo=='Mujeres')
            for name,val in [('age',grid),('age^2',grid**2),('female',s),('female x age',s*grid),('female x age^2',s*grid**2)]:G[:,noms.index(name)]=val
            pr=G@f['beta'];sepr=np.sqrt(np.maximum(0,np.einsum('ij,jk,ik->i',G,f['V_hc1'],G)))
            preds.extend([dict(modelo=nombre,sexo=sexo,edad=a,prediccion=v,IC_inf=l,IC_sup=h) for a,v,l,h in zip(grid,pr,pr-1.96*sepr,pr+1.96*sepr)])
    tab=tabla(pd.DataFrame(rows),SAL/'picos_por_sexo');p=pd.DataFrame(preds);tabla(p,SAL/'perfiles_por_sexo',mostrar=False)
    fig,ax=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    for panel,nombre,a in [('a','S1',ax[0,0]),('b','S5',ax[0,1])]:
        for sexo,color in [('Hombres',BLUE),('Mujeres',RED)]:
            z=p[(p.modelo==nombre)&(p.sexo==sexo)];a.plot(z.edad,z.prediccion,color=color);a.fill_between(z.edad,z.IC_inf,z.IC_sup,color=color,alpha=.13)
            media=tab.loc[tab.modelo.eq(nombre)&tab.sexo.eq(sexo),'media_bootstrap'].iloc[0]
            a.axvline(media,color=color,ls='--',lw=1.8,label=f'Media bootstrap {sexo}: {media:.2f} años')
        a.set(title=f'({panel}) Perfil edad-ingreso por sexo ({nombre})',xlabel='Edad',ylabel='Log(ingreso) predicho');a.legend(fontsize=9,loc='lower left',frameon=True,facecolor='white',framealpha=1,edgecolor='none')
    ff,X,nms=fitmap['S5'];G=np.zeros((len(grid),X.shape[1]));G[:,nms.index('female')]=1;G[:,nms.index('female x age')]=grid;G[:,nms.index('female x age^2')]=grid**2
    dif=G@ff['beta'];se=np.sqrt(np.maximum(0,np.einsum('ij,jk,ik->i',G,ff['V_hc1'],G)))
    ax[1,0].plot(grid,dif,color=RED);ax[1,0].fill_between(grid,dif-1.96*se,dif+1.96*se,color=RED,alpha=.15)
    ax[1,0].set(title='(c) Brecha S5 por edad e IC puntual 95%',xlabel='Edad',ylabel='Mujeres menos hombres, log-puntos')
    for vals,label,color in zip(boots['S5'],['Hombres','Mujeres'],[BLUE,RED]):
        ax[1,1].hist(vals,bins=35,density=True,alpha=.4,color=color)
        ax[1,1].axvline(vals.mean(),color=color,ls='--',lw=2,label=f'Media bootstrap {label}: {vals.mean():.2f} años')
    ax[1,1].set(title='(d) Distribución bootstrap de los picos (S5)',xlabel='Edad pico',ylabel='Densidad');ax[1,1].legend(fontsize=9,frameon=True,facecolor='white',framealpha=1,edgecolor='none')
    nota_poblacion(m,fig=fig);guardar(fig,SAL/'figuras/fig04_perfiles');return tab

def subgrupos(m):
    nota_poblacion(m,'Referencia; la tabla informa la expansión de cada subgrupo')
    rows=[]
    grupos=[('Sin terciaria',m.terciaria==0),('Con terciaria',m.terciaria==1),('Formal',m.formal==1),('Informal',m.formal==0),('Cuenta propia',m.cuentaPropia==1),('Empleo particular',m.relab==1),('18 a 35 años',m.age<=35),('36 a 55 años',m.age.between(36,55)),('56 o más años',m.age>=56)]
    for label,mask in grupos:
        d=m.loc[mask]
        for nombre,bloques in [('S0',[]),('S5',S5)]:
            W,_,_=diseno(d,bloques);r=fwl(d.log_y,d.female,W,d.fex_c)
            rows.append(dict(grupo=label,modelo=nombre,n=len(d),personas_representadas=alcance(d)['personas_representadas'],beta=r['b'],EE_HC1=r['se_hc1'],IC_inf=r['b']-1.96*r['se_hc1'],IC_sup=r['b']+1.96*r['se_hc1']))
    t=tabla(pd.DataFrame(rows),SAL/'brecha_subgrupos')
    fig,ax=plt.subplots(figsize=(11,6),layout='constrained')
    for nombre,offset,color in [('S0',-.12,BLUE),('S5',.12,RED)]:
        z=t[t.modelo==nombre];ax.errorbar(z.beta,np.arange(len(z))+offset,xerr=1.96*z.EE_HC1,fmt='o',label=nombre,color=color,capsize=3)
    ax.set(yticks=np.arange(len(grupos)),yticklabels=[g[0] for g in grupos],xlabel='Coeficiente Female e IC 95% HC1',title='Brechas dentro de cada subgrupo, ponderadas por fex_c');ax.axvline(0,color='gray',lw=.6);ax.legend();ax.invert_yaxis()
    guardar(fig,SAL/'figuras/fig05_subgrupos');return t

def diagnostico(m,fits):
    nota_poblacion(m,'Diagnóstico de leverage e influencia sobre S5')
    f,r,W,noms,bs=fits['S5'];diag=diagnostico_influencia(f)
    solo_leverage=int((diag.leverage_alto&~diag.atipico).sum());solo_atipico=int((diag.atipico&~diag.leverage_alto).sum());ambas=int(diag.influyente.sum())
    resumen=tabla(pd.DataFrame([dict(condicion='Leverage alto, no atípica',n=solo_leverage),dict(condicion='Atípica, leverage no alto',n=solo_atipico),dict(condicion='Ambas (influyente)',n=ambas)]),SAL/'diagnostico_resumen',decimales=0)
    flag=diag.influyente.to_numpy()
    r_excl=fwl(m.log_y[~flag],m.female[~flag],W[~flag],m.fex_c[~flag])
    sensibilidad=tabla(pd.DataFrame([dict(muestra='Completa (S5)',n=len(m),beta_Female=r['b'],brecha_porcentual=100*np.expm1(r['b'])),dict(muestra='Sin influyentes (S5)',n=int((~flag).sum()),beta_Female=r_excl['b'],brecha_porcentual=100*np.expm1(r_excl['b']))]),SAL/'diagnostico_sensibilidad')
    perfil=tabla(m.loc[flag,['age','female','terciaria']].assign(ingreso_mensual=np.exp(m.loc[flag,'log_y'])).reset_index(drop=True),SAL/'diagnostico_perfil_influyentes',decimales=0) if ambas else pd.DataFrame()
    fig,ax=plt.subplots(figsize=(7,5.5),layout='constrained')
    ax.scatter(diag.leverage,diag.residuo_estudentizado,s=10,alpha=.3,color=BLUE,label=f'No influyentes (n={len(diag)-ambas})')
    if ambas:ax.scatter(diag.leverage[flag],diag.residuo_estudentizado[flag],s=32,color=RED,label=f'Influyentes (n={ambas})')
    ax.axhline(3,color='black',ls='--',lw=.8);ax.axhline(-3,color='black',ls='--',lw=.8);ax.axvline(3*diag.leverage.mean(),color='black',ls='--',lw=.8)
    ax.set(title='Leverage y residuo estudentizado externo, S5',xlabel='Leverage $h_{ii}$',ylabel='Residuo estudentizado externo');ax.legend(fontsize=9)
    nota_poblacion(m,fig=fig);guardar(fig,SAL/'figuras/fig06_diagnostico')
    display(Markdown(f'''De {len(diag):,} observaciones en S5, {solo_leverage} tienen leverage alto sin ser atípicas, {solo_atipico} son atípicas sin leverage alto, y {ambas} cumplen ambas condiciones a la vez.

Excluir las {ambas} observaciones influyentes mueve el coeficiente Female de {r["b"]:.4f} a {r_excl["b"]:.4f} (brecha de {100*np.expm1(r["b"]):.2f}% a {100*np.expm1(r_excl["b"]):.2f}%).'''))
    return resumen,sensibilidad,perfil
