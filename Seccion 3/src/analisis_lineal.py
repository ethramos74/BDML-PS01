"""Predicción con MCO/ridge, selección de grupos y evaluación separada."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import KFold
from geih_modelos import Diseno,ajustar_ridge,elegir_lambda_loocv,rmse,loocv_rmse,columnas_sin,importancia_permutacion
from src.reportes import tabla,guardar,alcance,nota_poblacion
ROOT=Path(__file__).resolve().parents[2];SAL=ROOT/'punto3_prediccion_ingreso/salidas'
LAMS=np.logspace(-2,4,25)

def cargar():
    m=pd.read_csv(ROOT/'datos/limpios/geih2018_muestra.csv');m=m[m.maxEducLevel.notna()].copy()
    return m[m.entrenamiento].reset_index(drop=True),m[~m.entrenamiento].reset_index(drop=True)

def preparar(tr,va):
    tr,va=tr.copy(),va.copy();freq=tr.oficio.value_counts();keep=set(freq[freq>=20].index)
    for d in [tr,va]:d['oficio_f']=d.oficio.map(lambda x:f'{int(x):02d}' if x in keep else 'Otros')
    for c in ['educ_f','relab_f','sizeFirm_f','oficio_grupo','oficio_f','estrato_f','parentesco_f','regSalud_f']:
        levels=sorted(tr[c].astype(str).unique());levels=(['Otros']+[x for x in levels if x!='Otros']) if 'Otros' in levels else levels
        tr[c]=pd.Categorical(tr[c].astype(str),categories=levels);va[c]=pd.Categorical(va[c].astype(str),categories=levels)
    return tr,va

def especificaciones():
    num=lambda v:('num',v);cat=lambda v:('cat',v);pol=lambda v,g=2:('poly',v,g);spl=lambda v,k=6:('spline',v,k);inter=lambda a,b:('inter',a,b)
    s5=[num('female'),pol('age'),cat('educ_f'),pol('totalHoursWorked'),cat('relab_f'),num('formal'),cat('sizeFirm_f'),cat('oficio_grupo')]
    base=s5+[cat('estrato_f'),num('jefe_hogar'),pol('antiguedad_anios'),num('segundo_empleo')]
    cubic=[pol(t[1],3) if t[0]=='poly' else t for t in base]
    quartic=[pol(t[1],4) if t[0]=='poly' else t for t in base]
    spline=[spl(t[1],5 if t[1]=='antiguedad_anios' else 6) if t[0]=='poly' else t for t in base]
    inters=[inter(num('female'),spl('age')),inter(num('female'),cat('educ_f')),inter(num('female'),spl('totalHoursWorked')),inter(num('female'),cat('relab_f')),inter(cat('educ_f'),spl('age'))]
    fine=spline+inters+[cat('oficio_f')]
    amplio=fine+[cat('parentesco_f'),cat('regSalud_f'),num('quiere_mas_horas'),num('horas_segundo_empleo'),num('cotiza_pension'),num('microEmpresa'),
        inter(cat('estrato_f'),cat('oficio_grupo')),inter(cat('relab_f'),spl('age')),inter(num('female'),cat('estrato_f')),inter(num('terciaria'),cat('oficio_grupo')),inter(cat('relab_f'),spl('antiguedad_anios',5)),inter(cat('relab_f'),spl('totalHoursWorked'))]
    escolar=amplio+[pol('anios_educ'),num('hoursWorkUsual'),num('cuentaPropia'),inter(num('anios_educ'),spl('age')),inter(num('formal'),spl('totalHoursWorked')),inter(cat('sizeFirm_f'),pol('antiguedad_anios'))]
    specs={
      'M0':('Media de entrenamiento',[],False),
      'M1':('Edad y edad²',[pol('age')],False),
      'M2':('Edad, horas y vínculo',[pol('age'),num('totalHoursWorked'),cat('relab_f')],False),
      'M3':('Brecha sin controles',[num('female')],False),
      'M4':('Controles S5 aditivos',s5,False),
      'M4i':('S5 con perfiles por sexo',s5+[inter(num('female'),pol('age'))],False),
      'M5':('Recursos y antigüedad cuadrática',base,False),
      'M6':('Polinomios cúbicos',cubic,False),
      'M7':('Polinomios de grado cuatro',quartic,False),
      'M8':('Bases cúbicas por tramos',spline,False),
      'M9':('Interacciones y ocupación detallada',fine,False),
      'R1':('Ridge sobre polinomios de grado cuatro',quartic,True),
      'R2':('Ridge sobre interacciones y oficio',fine,True),
      'R3':('Ridge con interacciones ampliadas',amplio,True),
      'R4':('Ridge con escolaridad y jornadas',escolar,True)}
    return specs

def auditar_variables(tr):
    used=set().union(*(Diseno(t[1]).variables() for t in especificaciones().values()))
    raw=pd.read_csv(ROOT/'datos/intermedios/geih2018_tipado.csv',low_memory=False)
    keys=['directorio','secuencia_p','orden'];idx=raw.set_index(keys).index.isin(tr.set_index(keys).index);raw=raw.loc[idx]
    total={c:raw[c] for c in raw};total.update({c:tr[c] for c in tr})
    equivalent={'sex':'female','p6050':'parentesco_f y jefe_hogar','estrato1':'estrato_f','maxEducLevel':'educ_f y anios_educ','p6210':'educ_f','p6210s1':'anios_educ','relab':'relab_f','oficio':'oficio_f','sizeFirm':'sizeFirm_f','cotPension':'cotiza_pension','p6920':'cotiza_pension','p6426':'antiguedad_anios','hoursWorkActualSecondJob':'horas_segundo_empleo','p7040':'segundo_empleo','p7090':'quiere_mas_horas','p6100':'regSalud_f','regSalud':'regSalud_f','informal':'formal','p6870':'sizeFirm_f','college':'terciaria (corrige codificación)'}
    admin={'fila_en_bloque','directorio','secuencia_p','orden','id_persona','url_origen','dominio','clase','depto','chunk','muestra_ps3','entrenamiento','mes','mes_f'}
    design={'fex_c','fex_dpto','fweight'};scope={'ocu','wap','pet','pea','dsi','ina','inac','p6240'}
    rows=[]
    for c,s in total.items():
        if c in used:decision='Candidata';motivo='Disponible en el conjunto de especificaciones; ver columnas_modelos.csv'
        elif c in equivalent:decision='Representada';motivo='Se usa '+equivalent[c]
        elif c in admin:decision='Excluir';motivo='Identificador, localización constante o partición temporal; no aprendizaje por llave o mes'
        elif c in design:decision='Evaluación/diseño';motivo='Factor de expansión; fex_c se utiliza en ajuste de referencia y RMSE ponderado, no como predictor'
        elif c in scope or s.nunique(dropna=True)<2:decision='Excluir';motivo='Define población elegible o no tiene variación útil en entrenamiento'
        elif c.startswith(('y_','log_','impa','isa','ie','imdi','iof','ingtot','cclas','alerta_','dane_')):decision='Excluir';motivo='Resultado, ingreso relacionado, imputación o alerta dependiente del ingreso; riesgo de fuga'
        elif c.startswith(('p65','p66','p675','p676','p707','p742','p747','p749','p750','p751')):decision='Excluir';motivo='Montos o preguntas del reporte de remuneraciones/otros ingresos; se evita usar información tributaria cercana al resultado'
        else:decision='No incorporada';motivo='Pregunta adicional o con saltos de cuestionario; fuera del conjunto común de características laborales codificadas; no se imputa sin modelo de medición'
        rows.append(dict(variable=c,tipo=str(s.dtype),no_nulos_entrenamiento=int(s.notna().sum()),porcentaje_no_nulos=100*s.notna().mean(),decision=decision,motivo=motivo))
    return tabla(pd.DataFrame(rows),SAL/'auditoria_predictores',mostrar=False)

def ajustar(nombre,tr,va):
    title,terms,pen=especificaciones()[nombre];at,av=preparar(tr,va);D=Diseno(terms);X,nms,vc=D.fit_transform(at);Xv,_,_=D.transform(av)
    lt,lam=elegir_lambda_loocv(X,tr.log_y,LAMS) if pen else (pd.DataFrame(),0.)
    f=ajustar_ridge(X,tr.log_y,lam)
    return dict(nombre=nombre,titulo=title,D=D,X=X,Xv=Xv,nombres=nms,vc=vc,fit=f,lam=lam,lambda_tabla=lt,pred=Xv@f['beta'],tr=at,va=av,idx=list(range(X.shape[1])),pesos=False)

def seleccion_grupos(X,y,vc,lam,modo,cache=None,inicio=None):
    """Búsqueda local por PRESS de grupos con jerarquía: una interacción
    solo aparece si todas sus variables están presentes. No usa validación."""
    grupos=sorted(set().union(*vc));cache={} if cache is None else cache
    def evaluar(act):
        key=frozenset(act)
        if key not in cache:
            ix=[j for j,v in enumerate(vc) if v<=key]
            f=ajustar_ridge(X[:,ix],y,lam);cache[key]=(loocv_rmse(f),ix)
        return cache[key]
    act=set(grupos) if modo=='atras' else set(inicio or [])
    valor,ix=evaluar(act);hist=[dict(paso=0,movimiento='inicio',grupos='|'.join(sorted(act)),n_columnas=len(ix),RMSE_LOOCV=valor)]
    vistos={frozenset(act)}
    while True:
        cand=[]
        if modo!='atras':cand += [('añadir '+g,act|{g}) for g in grupos if g not in act]
        if modo!='adelante':cand += [('retirar '+g,act-{g}) for g in sorted(act)]
        vals=[(evaluar(a)[0],mov,a) for mov,a in cand if frozenset(a) not in vistos]
        if not vals:break
        val,mov,new=min(vals,key=lambda z:(z[0],z[1]))
        if not val<valor-1e-7:break
        act=new;valor=val;vistos.add(frozenset(act));_,ix=evaluar(act)
        hist.append(dict(paso=len(hist),movimiento=mov,grupos='|'.join(sorted(act)),n_columnas=len(ix),RMSE_LOOCV=valor))
    return pd.DataFrame(hist),sorted(act),evaluar(act)[1]

def estimar(tr,va):
    nota_poblacion(tr,'Entrenamiento de las referencias ponderadas')
    nota_poblacion(va,'Evaluación del RMSE ponderado de todos los modelos')
    resultados={};columnas=[]
    for nombre in especificaciones():
        print('Estimando',nombre,flush=True);r=ajustar(nombre,tr,va);resultados[nombre]=r
    # Reestimación de las referencias ponderadas de las secciones 1 y 2.
    for base in ['M1','M2','M3','M4','M4i']:
        r=resultados[base].copy();sw=np.sqrt(tr.fex_c.to_numpy()/tr.fex_c.mean());Xw=r['X']*sw[:,None]
        # MCO ponderado se resuelve mediante el módulo común. PRESS usa su H.
        from src.numerica import mco_estable
        ff=mco_estable(r['X'],tr.log_y,tr.fex_c);f=dict(beta=ff['beta'],ajuste=ff['ajust'],resid=ff['resid'],h=ff['h'],loo=ff['resid']/(1-ff['h']),gl=ff['k'])
        r.update(nombre=base+'w',titulo=r['titulo']+' (fex_c)',fit=f,pred=r['Xv']@f['beta'],pesos=True);resultados[base+'w']=r
    full=resultados['R4'];cache={};elegidos=[]
    for nombre,modo in [('R5','adelante'),('R6','atras'),('R7','mixto')]:
        print('Selección',modo,flush=True)
        h,act,ix=seleccion_grupos(full['X'],tr.log_y.to_numpy(),full['vc'],full['lam'],modo,cache,inicio=elegidos if modo=='mixto' else None)
        if modo=='adelante':elegidos=act
        lt,lam=elegir_lambda_loocv(full['X'][:,ix],tr.log_y,LAMS);r=full.copy();f=ajustar_ridge(full['X'][:,ix],tr.log_y,lam)
        r.update(nombre=nombre,titulo='Ridge, selección '+modo,X=full['X'][:,ix],Xv=full['Xv'][:,ix],idx=ix,nombres=[full['nombres'][j] for j in ix],vc=[full['vc'][j] for j in ix],fit=f,lam=lam,lambda_tabla=lt,pred=full['Xv'][:,ix]@f['beta'],seleccion=modo)
        resultados[nombre]=r;tabla(h,SAL/f'seleccion_{modo}',mostrar=False)
    # El mismo conjunto seleccionado hacia adelante, reestimado por MCO.
    r=resultados['R5'].copy();f=ajustar_ridge(r['X'],tr.log_y,0);r.update(nombre='M10',titulo='MCO, grupos elegidos hacia adelante',fit=f,lam=0.,pred=r['Xv']@f['beta']);resultados['M10']=r
    rows=[]
    for nombre,r in resultados.items():
        f=r['fit'];pred=r['pred'];loo=loocv_rmse(f) if np.isfinite(f['loo']).all() else np.nan
        rows.append(dict(modelo=nombre,especificacion=r['titulo'],familia='Ridge' if r['lam']>0 else 'MCO',ponderado_ajuste=r['pesos'],columnas=r['X'].shape[1],gl=f['gl'],lambda_ridge=r['lam'],RMSE_entrenamiento=rmse(tr.log_y,f['ajuste']),RMSE_LOOCV=loo,RMSE_validacion=rmse(va.log_y,pred),RMSE_validacion_fex_c=np.sqrt(np.average((va.log_y-pred)**2,weights=va.fex_c))))
        columnas.extend(dict(modelo=nombre,columna=n,variables='|'.join(sorted(v))) for n,v in zip(r['nombres'],r['vc']))
    t=pd.DataFrame(rows);win=t.loc[t.RMSE_validacion.idxmin(),'modelo'];t['seleccionado']=t.modelo.eq(win)
    anotar_poblaciones(t,tr,va)
    tabla(pd.DataFrame(columnas),SAL/'columnas_modelos',mostrar=False);tabla(t,SAL/'rmse_especificaciones')
    tabla(resultados[win]['lambda_tabla'],SAL/'lambda_modelo_ganador',mostrar=False)
    return resultados,t,win


def anotar_poblaciones(t,tr,va):
    """Expansión del ajuste ponderado y del RMSE poblacional de cada modelo."""
    t['n_entrenamiento']=len(tr);t['n_validacion']=len(va)
    t['personas_ajuste_fex_c']=np.where(t.ponderado_ajuste,alcance(tr)['personas_representadas'],np.nan)
    t['personas_validacion_fex_c']=alcance(va)['personas_representadas']
    tabla(t[['modelo','ponderado_ajuste','n_entrenamiento','personas_ajuste_fex_c','n_validacion','personas_validacion_fex_c']],SAL/'poblacion_especificaciones',decimales=0,plegable='Personas representadas en el ajuste y en la evaluación de cada modelo')
    return t

def comparar(t):
    fig,ax=plt.subplots(figsize=(13,5),layout='constrained');z=t.sort_values('RMSE_validacion')
    ax.plot(z.modelo,z.RMSE_validacion,'o-',label='Validación');ax.plot(z.modelo,z.RMSE_LOOCV,'s-',label='LOOCV condicional');ax.plot(z.modelo,z.RMSE_entrenamiento,'.-',label='Entrenamiento')
    ax.set(xlabel='Modelo, ordenado por RMSE de validación',ylabel='RMSE del log-ingreso',title='MCO y ridge: ajuste y evaluación');ax.tick_params(axis='x',rotation=55);ax.legend();guardar(fig,SAL/'figuras/fig01_modelos')

def validar(tr,va,r):
    nota_poblacion(va,'Población cubierta por la sensibilidad del RMSE con fex_c')
    # Evaluación complementaria con términos del ganador fijados; no se llama
    # anidada porque no repite toda la búsqueda de grupos ni elección de familia.
    y=tr.log_y.to_numpy();pred=np.empty(len(tr));details=[]
    full=r['D'].terminos;act=set().union(*r['vc'])
    for fold,(i,j) in enumerate(KFold(5,shuffle=True,random_state=2026).split(tr),1):
        a,b=preparar(tr.iloc[i],tr.iloc[j]);D=Diseno(full);X,_,vc=D.fit_transform(a);Xv,_,_=D.transform(b);ix=[k for k,v in enumerate(vc) if v<=act];X,Xv=X[:,ix],Xv[:,ix]
        if r['pesos']:
            from src.numerica import mco_estable
            f=mco_estable(X,y[i],a.fex_c);p=Xv@f['beta'];lam=0.
        else:
            _,lam=elegir_lambda_loocv(X,y[i],LAMS) if r['lam']>0 else (None,0.)
            f=ajustar_ridge(X,y[i],lam);p=Xv@f['beta']
        pred[j]=p;details.append(dict(pliegue=fold,lambda_ridge=lam,RMSE=rmse(y[j],p)))
    f=r['fit'];ploo=y-f['loo'];assert np.isfinite(ploo).all()
    t=pd.DataFrame([dict(medida='LOOCV condicional',RMSE=loocv_rmse(f)),dict(medida='CV 5, transformaciones y lambda renovadas; grupos fijos',RMSE=rmse(y,pred)),dict(medida='Validación bloques 8-10',RMSE=rmse(va.log_y,r['pred']))])
    tabla(t,SAL/'loocv_vs_validacion');tabla(pd.DataFrame(details),SAL/'cv_pliegues',mostrar=False)
    tabla(pd.DataFrame({'id_persona':tr.id_persona,'log_y':y,'pred_loo':ploo,'pred_cv5':pred}),SAL/'predicciones_cv',mostrar=False)
    return t

def importancia(tr,va,r):
    grupos={v:{v} for v in sorted(set().union(*r['vc']))}
    def predict(d):return r['D'].transform(d)[0][:,r['idx']]@r['fit']['beta']
    # Métrica principal: importancia de cada variable en el predictor fijo.
    perm=importancia_permutacion(predict,r['va'],va.log_y.to_numpy(),grupos,n_rep=30)
    perm=perm.rename(columns={'grupo':'variable','delta_rmse_permutacion':'delta_RMSE_validacion','sd':'sd_permutaciones'})
    # Contraste incremental: retirar la variable y todos sus términos, reajustar.
    drop=[]
    for v in perm.variable:
        ix=columnas_sin(r['vc'],{v});X,Xv=r['X'][:,ix],r['Xv'][:,ix]
        if r['pesos']:
            from src.numerica import mco_estable
            f=mco_estable(X,tr.log_y,tr.fex_c);pred=Xv@f['beta']
        else:
            _,lam=elegir_lambda_loocv(X,tr.log_y,LAMS) if r['lam']>0 else (None,0.)
            f=ajustar_ridge(X,tr.log_y,lam);pred=Xv@f['beta']
        drop.append(rmse(va.log_y,pred)-rmse(va.log_y,r['pred']))
    perm['delta_RMSE_reajuste']=drop;tabla(perm,SAL/'importancia_variables')
    fig,ax=plt.subplots(figsize=(11,5.5),layout='constrained');z=perm.head(12).iloc[::-1]
    ax.barh(z.variable,z.delta_RMSE_validacion,xerr=z.sd_permutaciones,color='#1463AE',capsize=2)
    ax.set(xlabel='Aumento de RMSE al permutar; barras: una DE entre sorteos',title='Importancia predictiva por variable');guardar(fig,SAL/'figuras/fig02_importancia')
    principal=perm.iloc[0].variable;d=r['va'];s=d[principal]
    # Evidencia mínima del enunciado, dentro del análisis de importancia.
    if pd.api.types.is_numeric_dtype(s):grid=np.unique(np.quantile(s,np.linspace(.05,.95,25)))
    else:grid=[v for v in d[principal].cat.categories if (d[principal]==v).any()]
    rows=[]
    for v in grid:
        x=d.copy();x[principal]=v;rows.append(dict(variable=principal,valor=v,prediccion_media_log=predict(x).mean()))
    profile=pd.DataFrame(rows);tabla(profile,SAL/'perfil_variable_importante',mostrar=False)
    fig,ax=plt.subplots(figsize=(10,4.5),layout='constrained');ax.plot(profile.valor.astype(float) if pd.api.types.is_numeric_dtype(s) else profile.valor.astype(str),profile.prediccion_media_log,'o-',color='#1463AE')
    ax.set(xlabel=principal,ylabel='Promedio del log-ingreso predicho',title='Respuesta del modelo a la variable de mayor importancia');guardar(fig,SAL/'figuras/fig03_variable_importante')
    return perm,profile

def resumen(tr,va,t,win,cv,imp):
    r=t.loc[t.modelo==win].iloc[0]
    out=dict(ganador=win,especificacion=r.especificacion,numero_modelos=len(t),n_entrenamiento=len(tr),n_validacion=len(va),rmse_validacion=float(r.RMSE_validacion),rmse_loo=float(r.RMSE_LOOCV),rmse_validacion_fex_c=float(r.RMSE_validacion_fex_c),variable_principal=imp.iloc[0].variable)
    out['rmse_cv5_grupos_fijos']=float(cv.loc[cv.medida.str.startswith('CV 5'),'RMSE'].iloc[0])
    (SAL/'resumen.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');return out
