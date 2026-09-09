"""Diapositivas científicas en PDF, gráficos y trazabilidad, íntegramente en Python.

Importa la proporción de página de la plantilla conservada Simple Light Mode.
Conserva fondo claro, composición abierta, tipografía sans y margen de 31 pt.
Las tablas son texto PDF, no capturas. Los gráficos se regeneran de CSV o datos.
"""
from pathlib import Path
import json, re, csv, zipfile, hashlib, xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf';FIG=ROOT/'slides/figuras'
P1=ROOT/'punto1_perfil_edad_ingreso/salidas'
P2=ROOT/'punto2_brecha_genero/salidas'
P3=ROOT/'punto3_prediccion_ingreso/salidas'
BLUE='#1463AE';RED='#A6405C';GRAY='#65717C'
TRACE=[]


def read(path,index=False):return pd.read_csv(path,index_col=0 if index else None)
def fmt(x,n=3):return f'{x:.{n}f}' if pd.notna(x) else 'No definido'
def pct(b):return f'{100*np.expm1(b):.1f}%'
def clean(s):return str(s).replace('−','-').replace('–','-').replace('—','-')
def plot(name,fig):
    FIG.mkdir(parents=True,exist_ok=True)
    fig.tight_layout();fig.savefig(FIG/(name+'.png'),dpi=200,bbox_inches='tight')
    fig.savefig(FIG/(name+'.svg'),bbox_inches='tight');plt.close(fig)
    return FIG/(name+'.png')


class Deck:
    def __init__(self,section,topic):
        self.section=section;self.topic=topic;self.page=0
        self.team=json.loads((ROOT/'slides/equipo.json').read_text(encoding='utf8'))
        self.path=OUT/f'{section}_equipo_{self.team["numero"]}.pdf'
        z=zipfile.ZipFile(ROOT/'slides/assets/plantilla_simple_light.pptx')
        el=ET.fromstring(z.read('ppt/presentation.xml')).find('{http://schemas.openxmlformats.org/presentationml/2006/main}sldSz')
        self.W,self.H=int(el.attrib['cx'])/12700,int(el.attrib['cy'])/12700
        self.c=canvas.Canvas(str(self.path),pagesize=(self.W,self.H),pageCompression=1)
        self.c.setTitle(f'Problem Set 1 - {topic} - Equipo {self.team["numero"]}')
        self.c.setAuthor('Equipo '+self.team['numero'])
        self.notes=[]

    def text(self,s,x,y,w=850,size=20,bold=False,color='#101010',leading=None):
        style=ParagraphStyle('t',fontName='BodyBold' if bold else 'Body',fontSize=size,
                             leading=leading or size*1.28,textColor=colors.HexColor(color),spaceAfter=0)
        para=Paragraph(clean(s),style);_,h=para.wrap(w,self.H)
        if y-h<16:raise ValueError(f'Texto fuera de página {self.section}/{self.page}: {s[:65]}')
        para.drawOn(self.c,x,y-h)
        return h

    def new(self,title,source,note=''):
        if self.page:self.c.showPage()
        self.page+=1
        self.c.setFillColor(colors.white);self.c.rect(0,0,self.W,self.H,fill=1,stroke=0)
        self.text(title,31,self.H-27,self.W-62,32,bold=True)
        self.text(f'{self.topic} · Equipo {self.team["numero"]}',31,31,620,10,color=GRAY)
        self.c.setFont('Body',10);self.c.setFillColor(colors.HexColor(GRAY));self.c.drawRightString(self.W-31,20,str(self.page))
        if source:self.text(source,31,58,self.W-90,10,color=GRAY)
        self.notes.append((self.page,title,note))
        TRACE.append({'pdf':self.path.relative_to(ROOT).as_posix(),'diapositiva':self.page,'titulo':title,
                      'fuentes':source,'generador':'src/entregables.py'})

    def chart(self,path,x=52,y=101,w=850,h=345):
        im=ImageReader(str(path));iw,ih=im.getSize();scale=min(w/iw,h/ih)
        self.c.drawImage(im,x+(w-iw*scale)/2,y+(h-ih*scale)/2,width=iw*scale,height=ih*scale,mask='auto')
        TRACE[-1]['figura']=Path(path).relative_to(ROOT).as_posix()

    def table(self,headers,rows,widths,y=425,size=16):
        style=ParagraphStyle('cell',fontName='Body',fontSize=size,leading=size*1.24)
        head=ParagraphStyle('head',parent=style,fontName='BodyBold')
        cells=[[Paragraph(clean(v),head) for v in headers]]+[[Paragraph(clean(v),style) for v in row] for row in rows]
        tab=Table(cells,colWidths=widths,hAlign='LEFT')
        tab.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LINEBELOW',(0,0),(-1,0),1,colors.black),
                                ('LINEBELOW',(0,-1),(-1,-1),.6,colors.HexColor('#AAAAAA')),
                                ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
                                ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)]))
        _,h=tab.wrap(sum(widths),self.H)
        if y-h<85:raise ValueError(f'Tabla muy alta: {self.section}, página {self.page}, {h}')
        tab.drawOn(self.c,40,y-h)

    def bullets(self,items,y=415,size=22):
        for title,body in items:
            h=self.text(title,48,y,850,size,bold=True);y-=h+8
            h=self.text(body,48,y,850,size-2,color='#333333');y-=h+27

    def names(self):
        names=self.team['integrantes']
        self.text('Integrantes',31,144,200,12,bold=True)
        for i,n in enumerate(names):
            x=31+(i%2)*450;y=120-(i//2)*24
            self.text(n or f'{i+1}. __________________________________',x,y,420,12)

    def finish(self):
        self.c.save()
        notes=ROOT/'slides'/f'notas_{self.section}.md'
        notes.write_text('# '+self.topic+'\n\nTiempo orientativo: 15 minutos para el cuerpo principal. Las páginas señaladas como anexo sirven para preguntas.\n\n'+
                         '\n\n'.join(f'## {p}. {t}\n\n{n}' for p,t,n in self.notes),encoding='utf8')


def graficos_edad(m):
    p=read(P1/'perfiles_predichos.csv');means=m.groupby('age').log_y.agg(['mean','std','count']);means=means[means['count']>=20]
    plots={}
    fig,ax=plt.subplots(figsize=(10,4));ax.hist(m.age,bins=np.arange(18,93,2),color=BLUE,alpha=.8)
    ax.set(xlabel='Edad, años',ylabel='Personas',xlim=(17,93));plots['edad_dist']=plot('edad_distribucion',fig)
    for tipo in ['inc','ambos']:
        fig,ax=plt.subplots(figsize=(10,4))
        ax.errorbar(means.index,means['mean'],yerr=1.96*means['std']/np.sqrt(means['count']),fmt='o',ms=3,color=GRAY,alpha=.5,label='Media observada por edad e IC 95%')
        ax.plot(p.edad,p.incondicional,color=BLUE,lw=2.5,label='Perfil incondicional')
        ax.fill_between(p.edad,p.inc_inf,p.inc_sup,color=BLUE,alpha=.13)
        if tipo=='ambos':
            ax.plot(p.edad,p.condicional_medias,color=RED,lw=2.5,label='Horas y vínculo constantes')
            ax.fill_between(p.edad,p.con_inf,p.con_sup,color=RED,alpha=.13)
        ax.set(xlabel='Edad, años',ylabel='Logaritmo del ingreso mensual',xlim=(18,75));ax.legend(fontsize=11,loc='lower center')
        plots[tipo]=plot('edad_perfil_'+tipo,fig)
    ic=read(P1/'intervalos_pico_incondicional.csv');fig,ax=plt.subplots(figsize=(10,3.8))
    for j,row in ic.iterrows():ax.plot([row.inferior,row.superior],[j,j],color=BLUE,lw=4)
    ax.set(yticks=range(len(ic)),yticklabels=ic.iloc[:,0],xlabel='Edad pico, años');ax.invert_yaxis();plots['ic']=plot('edad_intervalos',fig)
    d=read(P1/'descomposicion_perfiles.csv');fig,ax=plt.subplots(figsize=(10,4))
    for col,label,color in [('contribucion horas','Horas',BLUE),('contribucion cuenta propia','Cuenta propia',RED),('contribucion otros relab','Otros vínculos',GRAY)]:ax.plot(d.edad,d[col],label=label,color=color,lw=2)
    ax.axhline(0,color='black',lw=.6);ax.set(xlabel='Edad, años',ylabel='Diferencia de perfiles, log-puntos',xlim=(18,75));ax.legend();plots['descomp']=plot('edad_composicion',fig)
    rob=read(P1/'robustez_heterogeneidad.csv').iloc[:6];fig,ax=plt.subplots(figsize=(10,4))
    ax.errorbar(rob.pico,range(6),xerr=[rob.pico-rob['IC inf'],rob['IC sup']-rob.pico],fmt='o',color=BLUE,capsize=4)
    labels=['Incondicional','Con ponderadores','Sin extremos','Ingreso por hora','Horas y vínculo','Horas y vínculo, ponderado']
    ax.set(yticks=range(6),yticklabels=labels,xlabel='Edad pico, IC 95% delta HC1');ax.invert_yaxis();plots['rob']=plot('edad_robustez',fig)
    return plots


def edad(m):
    plots=graficos_edad(m);picos=read(P1/'edad_pico_intervalos.csv');b=read(P1/'coeficientes_incondicional.csv',True);c=read(P1/'coeficientes_condicional.csv',True)
    p,q=picos.iloc[0],picos.iloc[1];d=Deck('age','Perfil edad-ingreso')
    d.new('Result Overview','GEIH 2018, Bogotá. Fuente: edad_pico_intervalos.csv. IC percentil, 2,000 réplicas.',
          'Abrir con el hallazgo: el vértice cuadrático es preciso dentro del modelo. Distinguirlo de la trayectoria causal de una persona. Dedicar 1 minuto.')
    d.text(f'{p.pico:.1f} años',31,434,800,67,bold=True)
    d.text(f'Pico incondicional · IC 95% [{p["IC percentil inf"]:.1f}, {p["IC percentil sup"]:.1f}]',34,333,850,24)
    d.text(f'Con horas y vínculo constantes: <b>{q.pico:.1f} años</b><br/>IC 95% [{q["IC percentil inf"]:.1f}, {q["IC percentil sup"]:.1f}]',34,277,850,24)
    d.text('La composición laboral desplaza el perfil. La edad sola explica poco del ingreso individual.',34,200,850,19)
    d.names()
    d.new('Una muestra transversal de ocupados adultos','Fuente: datos/limpios/geih2018_muestra.csv. Se muestran todas las edades observadas.',
          'Definir la unidad y la selección: ocupados de 18+ con monto positivo. Son 14,764 observaciones, no una cohorte seguida en el tiempo. 1 minuto.')
    d.chart(plots['edad_dist'],h=310,y=128)
    d.text(f'{len(m):,} personas · Ingreso positivo observado · 1,778 ocupados sin monto fuera de la muestra',45,103,860,17)
    d.new('Capital humano y forma del perfil','Fuente: enunciado, sección 4. Mincer (1974), marco de capital humano.',
          'La edad aproxima experiencia, pero también mezcla cohortes y selección al empleo. La parábola es una restricción funcional. 1 minuto.')
    d.bullets([('Especificación del enunciado','log(w) = β₁ + β₂ Edad + β₃ Edad² + u'),
               ('Máximo interior','Requiere β₃ &lt; 0 y Edad* = -β₂ / (2β₃) dentro del soporte observado.'),
               ('Lectura económica','La acumulación y depreciación de capital humano son compatibles con la concavidad. La evidencia transversal no separa ese mecanismo de cohortes y selección.')],size=22)
    d.new('Regresiones e incertidumbre del pico','Fuente: tablas de coeficientes y edad_pico_intervalos.csv. EE HC1 entre paréntesis; coeficiente de Edad² y su EE × 1,000.',
          'Leer coeficientes de edad, el cambio de R² y los intervalos. EE HC1 entre paréntesis. relab es factor con referencia empleo particular; categorías 8-9 agrupadas por escaso soporte. 2 minutos.')
    rows=[]
    for var,label,mult in [('const','Constante',1),('age','Edad',1),('age^2','Edad² × 1,000',1000),('totalHoursWorked','Horas semanales',1)]:
        vals=[]
        for t in [b,c]:vals.append(f'{t.loc[var,"coeficiente"]*mult:.4f}<br/>({t.loc[var,"EE HC1"]*mult:.4f})' if var in t.index else '-')
        rows.append([label,*vals])
    rows += [['Tipo de vínculo','Sin controles','Factor (base: particular)'],['Pico, IC 95% bootstrap',f'{p.pico:.1f} [{p["IC percentil inf"]:.1f}, {p["IC percentil sup"]:.1f}]',f'{q.pico:.1f} [{q["IC percentil inf"]:.1f}, {q["IC percentil sup"]:.1f}]'],['R² / n',f'{p.R2:.3f} / {int(p.n):,}',f'{q.R2:.3f} / {int(q.n):,}']]
    d.table(['Variable','Incondicional','Condicional'],rows,[270,290,310],y=440,size=15)
    d.new('La edad capta una fracción pequeña de la dispersión','Fuente: perfiles_predichos.csv y muestra común. Bandas puntuales 95% HC1.',
          'La precisión del promedio no equivale a precisión individual. La curva impone simetría. Comentar el bajo R². 1.5 minutos.')
    d.chart(plots['inc']);d.text(f'R² = {p.R2:.3f} · RMSE en muestra = {p["RMSE en muestra"]:.3f} log-puntos',45,93,850,18)
    d.new('El control de horas y vínculo desplaza el perfil','Fuente: perfiles_predichos.csv. Ambos perfiles usan la misma muestra.',
          'El perfil condicional promedia los controles en la misma distribución a todas las edades. El contraste no mide el efecto causal de mantener las horas fijas. 1.5 minutos.')
    d.chart(plots['ambos']);d.text('Las bandas representan incertidumbre del promedio ajustado.',45,91,850,17)
    d.new('La diferencia responde a horas y composición del empleo','Fuente: descomposicion_perfiles.csv. Identidad exacta de proyecciones lineales.',
          'Explicar que una identidad algebraica reparte la diferencia: no atribuye causalidad. Las horas bajan en edades mayores y cambia el peso del trabajo independiente. 1.5 minutos.')
    d.chart(plots['descomp']);d.text('Cada aporte compara el control proyectado por edad con su media.',45,92,850,17)
    d.new('La inferencia del vértice es estable dentro de la cuadrática','Fuente: intervalos_pico_incondicional.csv. Todos los intervalos tienen nivel 95%.',
          'Mostrar qué remuestrea el bootstrap y aclarar que la forma cuadrática está fija. La coincidencia de métodos no valida la especificación. 1 minuto.')
    d.chart(plots['ic']);d.text('El intervalo no incorpora la incertidumbre sobre la forma del perfil.',45,94,850,17)
    d.new('Ponderación, extremos y resultado por hora','Fuente: robustez_heterogeneidad.csv. Las variantes por hora cambian el resultado estudiado.',
          'La sensibilidad no selecciona arbitrariamente una muestra favorable. Los extremos se conservan en la estimación principal. 1 minuto.')
    d.chart(plots['rob'])
    d.new('Alcance económico y utilidad tributaria','Fuente: resultados de la sección 1 y documentación GEIH.',
          'Cerrar: perfil promedio preciso, predicción individual limitada. Los tres límites son transversabilidad, selección de ingresos observados y diseño de encuesta. 1.5 minutos.')
    d.bullets([('Un perfil promedio, dependiente de la forma funcional','El máximo cuadrático resume la muestra. Las formas flexibles permiten una meseta.'),
               ('Inferencia condicionada al muestreo','HC1 y bootstrap por personas no reproducen todo el diseño DANE. La sensibilidad por hogar complementa el análisis.'),
               ('Un insumo descriptivo para política','La edad sola no permite identificar subreporte. Un ingreso inferior a la curva requiere más información.')],size=21)
    d.new('Anexo · Sensibilidad a dependencia dentro del hogar','Fuente: sensibilidad_hogares.csv. CR1 agrupada por directorio y secuencia del hogar.',
          'Si preguntan por dependencia de la encuesta, distinguir el ajuste CR1 de hogar de los pesos, estratos y unidades primarias que exige el diseño completo.')
    h=read(P1/'sensibilidad_hogares.csv')
    d.table(['Perfil','Pico','EE CR1','IC 95% CR1','Hogares'],[[r.especificacion,f'{r.pico:.2f}',f'{r.EE_CR1_hogar:.3f}',f'[{r.IC_inf:.2f}, {r.IC_sup:.2f}]',f'{r.n_hogares:,}'] for _,r in h.iterrows()],[230,130,130,220,160],size=18)
    d.text('El intervalo usa aproximación normal. El hogar no sustituye las unidades primarias y los estratos del diseño original.',45,250,850,22)
    d.finish()


def graficos_brecha(m):
    plots={};t=read(P2/'escalera_controles_fwl.csv');p=read(P2/'perfiles_por_sexo.csv')
    fig,ax=plt.subplots(figsize=(10,4))
    ax.errorbar(range(len(t)),100*np.expm1(t['beta FWL']),
                yerr=[100*(np.exp(t['beta FWL'])-np.exp(t['beta FWL']-1.96*t['EE HC1'])),100*(np.exp(t['beta FWL']+1.96*t['EE HC1'])-np.exp(t['beta FWL']))],fmt='o-',color=RED,capsize=4)
    ax.set(xticks=range(len(t)),xticklabels=[s[:2] for s in t.especificacion],ylabel='Brecha de medias geométricas, %',xlabel='Conjunto de controles');ax.axhline(0,color=GRAY,lw=.7)
    plots['escalera']=plot('brecha_escalera',fig)
    fig,ax=plt.subplots(figsize=(10,4))
    ax.plot(p.edad,p.hombres_S5,color=BLUE,label='Hombres',lw=2.5);ax.plot(p.edad,p.mujeres_S5,color=RED,label='Mujeres',lw=2.5)
    ax.set(xlabel='Edad, años',ylabel='Log-ingreso predicho',xlim=(18,75));ax.legend();plots['perfiles']=plot('brecha_perfiles',fig)
    fig,ax=plt.subplots(figsize=(10,4));ax.plot(p.edad,p.brecha_S5,color=RED,lw=2.5)
    ax.fill_between(p.edad,p.brecha_S5_inf,p.brecha_S5_sup,color=RED,alpha=.15);ax.axhline(0,color=GRAY,lw=.7)
    ax.set(xlabel='Edad, años',ylabel='Brecha condicional, log-puntos',xlim=(18,75));plots['edad']=plot('brecha_por_edad',fig)
    fig,ax=plt.subplots(figsize=(10,4));vals=m.groupby('female').agg(horas=('totalHoursWorked','mean'),terciaria=('terciaria','mean'))
    for sexo,color,label in [(0,BLUE,'Hombres'),(1,RED,'Mujeres')]:
        x=m[m.female==sexo].totalHoursWorked;ax.hist(x,bins=np.arange(0,130,4),density=True,alpha=.45,color=color,label=f'{label}: media {x.mean():.1f} h')
    ax.set(xlabel='Horas semanales',ylabel='Densidad',xlim=(0,120));ax.legend();plots['horas']=plot('brecha_horas',fig)
    return plots


def brecha(m):
    plots=graficos_brecha(m);t=read(P2/'escalera_controles_fwl.csv');s0=t.iloc[0];s5=t[t.especificacion.str.startswith('S5')].iloc[0]
    peaks=read(P2/'picos_por_sexo.csv');pk=peaks[peaks.especificacion=='S5 preferida'].iloc[0]
    d=Deck('gap','Brecha de género')
    d.new('Result Overview','Fuente: escalera_controles_fwl.csv. Brechas porcentuales entre medias geométricas.',
          'Abrir con la magnitud de la brecha y su cambio al incluir controles. La medida se refiere a medias geométricas. 1 minuto.')
    d.text(pct(s0['beta FWL']),31,430,410,67,bold=True)
    d.text(pct(s5['beta FWL']),490,430,410,67,bold=True)
    d.text('Sin controles',34,324,410,25,bold=True);d.text('Con controles S5',492,324,410,25,bold=True)
    d.text(f'β Female = {s0["beta FWL"]:.3f}<br/>EE bootstrap = {s0["EE bootstrap"]:.3f}',34,277,410,22)
    d.text(f'β Female = {s5["beta FWL"]:.3f}<br/>EE bootstrap = {s5["EE bootstrap"]:.3f}',492,277,410,22)
    d.text('Comparar personas con observables similares no identifica discriminación causal.',34,197,850,19)
    d.names()
    d.new('Las horas motivan una comparación condicional','Fuente: muestra común de la sección 2. Horas usuales del principal más efectivas del segundo empleo.',
          'La distribución motiva el control de horas. Describir composición sin convertirla en explicación causal. La educación también difiere entre grupos. 1 minuto.')
    d.chart(plots['horas']);d.text('El ingreso mensual combina remuneración por hora y tiempo de trabajo.',45,91,850,17)
    d.new('Cada control define qué trabajadores comparamos','Fuente: especificaciones de la sección 2. S5 es una brecha aditiva constante.',
          'Justificar cada control. Educación aproxima capital humano y edad experiencia/cohorte. Los controles de empleo pueden ser mediadores o malos controles para un efecto causal. 2 minutos.')
    d.table(['Bloque','Contenido','Interpretación'],[
        ['S1-S2','Edad, edad² y educación','Experiencia aproximada y capital humano'],
        ['S3','Horas y horas²','Intensidad de trabajo'],
        ['S4','Vínculo, formalidad, tamaño','Asignación a puestos y empresas'],
        ['S5','Grupo ocupacional','Comparación entre tareas similares'],
        ['S6-S7','Oficio fino, estrato y jefatura','Sensibilidad a una comparación más restringida']],[130,325,415],y=434,size=17)
    d.text('Los controles laborales pueden bloquear mecanismos de desigualdad o introducir selección.',45,114,850,18)
    d.new('Brechas, errores estándar y ajuste en muestra','Fuente: escalera_controles_fwl.csv. Analítico homoscedástico con rango efectivo; HC1 robusto.',
          'El enunciado pide esta comparación. Explicar que el bootstrap repite ambas etapas. La precisión no implica identificación causal. 2 minutos.')
    rows=[]
    for key in ['S0','S2','S3','S5','S7']:
        r=t[t.especificacion.str.startswith(key)].iloc[0]
        rows.append([key,f'{r["beta FWL"]:.3f}',f'{r["EE corregido (n-k)"]:.4f}',f'{r["EE HC1"]:.4f}',f'{r["EE bootstrap"]:.4f}',f'{r["R2 completo"]:.3f}'])
    d.table(['Modelo','β Female','EE analítico','EE HC1','EE bootstrap','R²'],rows,[130,140,150,140,180,130],y=433,size=17)
    d.text('Misma muestra: 14,763 personas. S0-S7: 500 réplicas, excepto S5: 1,000.',45,154,850,18)
    d.new('FWL recupera el coeficiente de la regresión completa','Fuente: brecha_genero.py y verificación numérica en el cuaderno.',
          'Explicar el teorema verbalmente: descontar de ambos lados lo que explican los controles y relacionar residuos. El error residual final coincide. 1.5 minutos.')
    d.bullets([('Primera etapa','Proyectar log(w) y Female sobre el mismo conjunto de controles W.'),
               ('Segunda etapa','Relacionar ambos residuos: β̂ = (d̃′ỹ) / (d̃′d̃).'),
               ('Inferencia','El denominador de la varianza residual usa n - rango([W, Female]). El bootstrap vuelve a estimar las dos etapas.')],size=23)
    d.new('La brecha depende del conjunto de controles','Fuente: escalera_controles_fwl.csv. IC 95% transformados desde la escala logarítmica.',
          'Educación puede ampliar la brecha y horas reducirla. Hablar de ajustes condicionales, no de porcentajes causalmente explicados. 1 minuto.')
    d.chart(plots['escalera']);d.text('S0: sin controles · S2: educación · S3: horas · S5: ocupación · S7: estrato y jefatura',43,94,865,16)
    d.new('Los perfiles por sexo requieren interacciones con edad','Fuente: perfiles_por_sexo.csv y picos_por_sexo.csv. S5 extendida con Female × edad y Female × edad².',
          'Distinguir S5 aditiva del modelo extendido. Mantener los otros controles en la misma distribución. Los picos son de medias logarítmicas condicionales. 1.5 minutos.')
    d.chart(plots['perfiles'],h=290,y=139)
    d.text(f'Hombres: {pk["pico hombres"]:.1f} años, IC 95% {pk["IC boot hombres"]}<br/>Mujeres: {pk["pico mujeres"]:.1f} años, IC 95% {pk["IC boot mujeres"]}',45,124,850,20)
    d.new('La brecha condicional varía a lo largo de la edad','Fuente: perfiles_por_sexo.csv. Banda puntual 95% delta HC1.',
          'La interacción produce una brecha creciente en magnitud a edades mayores. No es la trayectoria de una cohorte ni el efecto de envejecer. 1 minuto.')
    d.chart(plots['edad']);d.text('Las bandas son puntuales. No forman una banda simultánea para toda la curva.',45,93,850,17)
    d.new('Qué permite concluir la evidencia','Fuente: resultados de la sección 2.',
          'Cerrar con persistencia descriptiva, papel de controles y límites para política. 1.5 minutos.')
    d.bullets([('Persistencia condicional','La diferencia de ingresos geométricos permanece al incorporar características observadas.'),
               ('La elección de controles cambia el objeto estimado','Horas y asignación laboral pueden reflejar mecanismos de desigualdad. Su inclusión no elimina variables omitidas.'),
               ('Aplicación tributaria','El sexo describe patrones de la muestra. Una predicción no basta para imputar subreporte a una persona.')],size=22)
    d.new('Anexo · Picos y precisión por sexo','Fuente: picos_por_sexo.csv. Bootstrap pareado de 1,000 réplicas.',
          'La diferencia de picos usa las mismas réplicas por sexo, preservando su covarianza.')
    rows=[]
    for k in ['S1 sin controles','S5 preferida']:
        r=peaks[peaks.especificacion==k].iloc[0]
        rows.append([k,f'{r["pico hombres"]:.1f}<br/>{r["IC boot hombres"]}',f'{r["pico mujeres"]:.1f}<br/>{r["IC boot mujeres"]}',f'{r["diferencia (M - H)"]:.1f}<br/>{r["IC boot diferencia"]}'])
    d.table(['Especificación','Hombres, IC 95%','Mujeres, IC 95%','Diferencia M-H, IC'],rows,[240,205,205,220],y=425,size=18)
    d.text('Un máximo requiere curvatura negativa y debe evaluarse dentro del rango de edades observado.',45,240,850,22)
    d.finish()


def prediccion():
    t=read(P3/'rmse_especificaciones.csv');s=json.loads((P3/'resumen.json').read_text(encoding='utf8'))
    cv=read(P3/'loocv_vs_validacion.csv');imp=read(P3/'importancia_variables.csv')
    fig,ax=plt.subplots(figsize=(11,4.5));xx=np.arange(len(t))
    for col,label,color,marker in [('RMSE_entrenamiento','Ajuste en entrenamiento',GRAY,'o'),('RMSE_LOOCV','LOOCV condicional',BLUE,'o'),('RMSE_validacion','Validación, bloques 8-10',RED,'s')]:
        ax.plot(xx,t[col],marker+'-',color=color,label=label)
    ax.set(xticks=xx,xticklabels=t.modelo,ylabel='RMSE de log(ingreso)',xlabel='Especificación');ax.legend()
    comparacion=plot('pred_comparacion',fig)
    labels={'totalHoursWorked':'Horas totales y usuales','educacion':'Educación','tamano_empresa':'Tamaño de empresa','estrato':'Estrato','ocupacion':'Ocupación','formalidad':'Formalidad','antiguedad':'Antigüedad','edad':'Edad','vinculo':'Vínculo laboral','sexo':'Sexo'}
    top=imp.head(10).iloc[::-1];fig,ax=plt.subplots(figsize=(10,4.5))
    ax.barh([labels.get(v,v) for v in top.variable],top.delta_RMSE,color=BLUE)
    ax.set(xlabel='Aumento de RMSE al permutar el grupo en validación')
    importancia=plot('pred_importancia',fig)
    d=Deck('pred','Predicción del ingreso')
    d.new('Result Overview','Fuente: rmse_especificaciones.csv y resumen.json. MCO, ridge, elastic net, boosting y promedio jackknife.',
          'El ganador es el mínimo efectivo de toda la tabla. El universo es explícito y no se afirma que sea el mejor algoritmo posible. 1 minuto.')
    d.text(f'{s["rmse_validacion"]:.3f}',31,435,500,70,bold=True)
    d.text('RMSE de validación, en log-puntos',35,330,850,25)
    d.text(f'<b>{s["ganador"]}: {s["especificacion"]}</b><br/>LOOCV por reajuste: {s["rmse_loocv"]:.3f}',35,274,850,24)
    d.text('Las horas aportan información predictiva. La precisión difiere según el tipo de empleo.',35,196,850,19)
    d.names()
    d.new('Una evaluación fuera de muestra con orden temporal','Fuente: muestra común y metadatos de los bloques del sitio del curso.',
          'La validación está formada por bloques 8-10. Explicar que seleccionamos con esos datos y no los llamamos test independiente. 1 minuto.')
    d.bullets([('Entrenamiento: bloques 1-7',f'{s["n_entrenamiento"]:,} personas. Ajuste de coeficientes, categorías, nudos y penalización.'),
               ('Validación: bloques 8-10',f'{s["n_validacion"]:,} personas. La regla elige el menor RMSE entre {s["numero_especificaciones"]} especificaciones.'),
               ('Alcance','Los bloques siguen el calendario. El mínimo en validación puede ser optimista por selección y requiere un test nuevo para evaluar el modelo final.')],size=22)
    d.new('Modelos de referencia de las secciones 1 y 2','Fuente: rmse_especificaciones.csv. Todos los coeficientes se reestiman en entrenamiento.',
          'M4 reproduce la brecha aditiva y M4i su extensión con perfiles por sexo. M0 usa la media de entrenamiento, no la media de validación. 1 minuto.')
    tt=t[t.modelo.isin(['M0','M1','M2','M3','M4','M4i'])]
    d.table(['Modelo','Especificación','RMSE validación'],[[r.modelo,r.especificacion,f'{r.RMSE_validacion:.4f}'] for _,r in tt.iterrows()],[130,520,220],size=19)
    d.new('Flexibilidad dentro de modelos lineales','Fuente: rmse_especificaciones.csv. Selección por el mínimo de toda la tabla.',
          'Motivar el aumento de flexibilidad: recursos, no linealidades, interacciones, ocupación y contracción. No asignar parsimonia después de conocer el ganador. 1.5 minutos.')
    tt=t[t.modelo.isin(['M5','M6','M7','M8','M9'])]
    d.table(['Modelo','Especificación','RMSE validación'],[[r.modelo+(' *' if r.seleccionado else ''),r.especificacion,f'{r.RMSE_validacion:.4f}'] for _,r in tt.iterrows()],[130,520,220],y=442,size=17)
    d.text('La flexibilidad incorpora recursos, relaciones no lineales, interacciones y ocupaciones detalladas.',45,116,850,18)
    d.new('Regularización, árboles y promedio de modelos','Fuente: rmse_especificaciones.csv. Diez especificaciones adicionales en total.',
          'Boosting combina árboles pequeños de forma secuencial. La parada temprana se determina dentro del entrenamiento; después se reajusta con todas sus filas. El promedio jackknife combina modelos lineales. 1 minuto.')
    tt=t[t.modelo.isin(['M10','M11','M12','M13','M14'])]
    d.table(['Modelo','Especificación','RMSE validación'],[[r.modelo+(' *' if r.seleccionado else ''),r.especificacion,f'{r.RMSE_validacion:.4f}'] for _,r in tt.iterrows()],[130,520,220],y=432,size=18)
    d.text('* Ganador entre las 16 especificaciones. Los hiperparámetros se determinan dentro del entrenamiento.',45,126,850,18)
    d.new('Flexibilidad, contracción y error predictivo','Fuente: rmse_especificaciones.csv. Un LOO indeterminado se deja sin punto en la gráfica.',
          'Comparar error de ajuste y errores fuera de muestra. No afirmar una descomposición causal sesgo-varianza a partir de una sola curva. 1 minuto.')
    d.chart(comparacion)
    d.new('LOOCV y validación estiman riesgos diferentes','Fuente: loocv_vs_validacion.csv. RMSE agregado sobre todas las predicciones externas.',
          'LOOCV del ganador reajusta un modelo por persona excluida. Fija los hiperparámetros, incluyendo el número de árboles. La CV externa vuelve a determinar la parada temprana. Ninguna corrige haber usado validación para elegir familia. 2 minutos.')
    d.table(['Medida','RMSE','Qué se vuelve a estimar'],[
        ['LOOCV por reajuste',f'{cv.iloc[1].RMSE:.4f}','Árboles y discretización; hiperparámetros fijos'],
        ['CV externa de 5 pliegues',f'{cv.iloc[2].RMSE:.4f}','Categorías, árboles y parada temprana'],
        ['CV por hogares',f'{cv.iloc[3].RMSE:.4f}','Categorías y árboles; iteraciones fijas'],
        ['Validación, bloques 8-10',f'{cv.iloc[4].RMSE:.4f}','Predicción con el ajuste de entrenamiento']],[300,150,420],size=18)
    d.text('La diferencia no descarta sobreajuste ni demuestra deriva temporal. Cada comparación tiene un alcance específico.',45,155,850,20)
    d.new('Importancia por permutación conjunta','Fuente: importancia_variables.csv. Aumento de RMSE en validación; 30 permutaciones por grupo.',
          'Permutar conjuntamente las variables redundantes preserva su relación dentro del grupo. Medir cuánto empeoran las predicciones del modelo fijo. La medida depende de correlaciones y no identifica efectos causales. 1.5 minutos.')
    d.chart(importancia,h=319,y=115)
    d.text(f'Horas trabajadas: aumento de RMSE = {s["delta_rmse_principal"]:.3f}. Se permutan juntas horas totales y usuales.',45,96,850,17)
    d.new('Las predicciones dependen de las horas de forma no lineal','Fuente: dependencia_horas.csv y ale_horas.csv. Perfil promedio de validación.',
          'PDP modifica las horas y ALE acumula diferencias locales. Ambas son descriptivas y pueden implicar perfiles con escaso soporte conjunto. 1.5 minutos.')
    d.chart(P3/'figuras/fig03_dependencia_horas.png',h=327,y=111)
    d.text('El índice refiere a ingreso geométrico predicho. No mide el retorno causal de una hora adicional.',45,91,850,17)
    d.new('La precisión cambia según el vínculo laboral','Fuente: rmse_por_grupo_validacion.csv. Tamaños de grupo indicados junto a cada barra.',
          'Comparar la precisión de asalariados e independientes y señalar el soporte pequeño de algunos vínculos. El error esperado puede variar mucho entre contribuyentes. 1 minuto.')
    d.chart(P3/'figuras/fig04_error_por_empleo.png')
    d.new('Un residuo grande requiere corroboración externa','Fuente: diagnósticos de validación y límites de medición GEIH.',
          'Cerrar respondiendo la pregunta central: el modelo localiza discrepancias, pero no observa evasión. Proponer evaluación externa de falsos positivos y desempeño por grupos. 1 minuto.')
    d.bullets([('Qué observa el modelo','Ingreso declarado, características laborales y diferencias respecto de una predicción.'),
               ('Qué puede producir una discrepancia','Heterogeneidad legítima, errores de medición, variables omitidas o subreporte.'),
               ('Qué falta para fiscalizar','Evidencia independiente del ingreso verdadero y evaluación de falsos positivos. Un residuo no constituye prueba de evasión.')],size=22)
    d.new('Anexo · Intervalos con calibración separada','Fuente: intervalos_conformales_cobertura.csv. Modelo auxiliar M9 y 25% de entrenamiento para calibrar.',
          'Es split conformal con orden finito. La cobertura nominal requiere intercambiabilidad. La muestra temporal y la dependencia de encuesta impiden asumir esa garantía automáticamente.')
    d.chart(P3/'figuras/fig05_cobertura_conformal.png',h=309,y=131)
    d.text('El 90% es nominal. En «Otro» hay un caso de calibración: el intervalo por grupo es infinito y su cobertura del 100% no informa sobre precisión.',45,115,850,17)
    d.new('Anexo · Incertidumbre en la comparación','Fuente: rmse_especificaciones.csv. Bootstrap pareado de 2,000 réplicas de validación.',
          'Los intervalos condicionan en los ajustes y no corrigen selección ni multiplicidad. Un intervalo que contiene cero no prueba equivalencia.')
    tt=t.sort_values('RMSE_validacion').head(5)
    d.table(['Modelo','RMSE','Diferencia vs. ganador','IC 95% de diferencia'],[[r.modelo,f'{r.RMSE_validacion:.4f}',f'{r.dif_vs_ganador:+.4f}',f'[{r.IC_dif_inf:+.4f}, {r.IC_dif_sup:+.4f}]'] for _,r in tt.iterrows()],[160,160,280,270],size=18)
    d.text('Estos intervalos no incluyen incertidumbre de volver a entrenar y seleccionar todos los modelos.',45,168,850,20)
    d.finish()


def construir():
    OUT.mkdir(parents=True,exist_ok=True);FIG.mkdir(parents=True,exist_ok=True)
    for name,bold in [('Body',False),('BodyBold',True)]:
        path=font_manager.findfont(font_manager.FontProperties(family='DejaVu Sans',weight='bold' if bold else 'normal'))
        pdfmetrics.registerFont(TTFont(name,path))
    pdfmetrics.registerFontFamily('Body',normal='Body',bold='BodyBold',italic='Body',boldItalic='BodyBold')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':13,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'legend.frameon':False})
    m=read(ROOT/'datos/limpios/geih2018_muestra.csv')
    edad(m);brecha(m[m.maxEducLevel.notna()]);prediccion()
    pd.DataFrame(TRACE).to_csv(ROOT/'slides/trazabilidad.csv',index=False)
    # Metadatos reproducibles de los productos y fuente utilizada.
    paths=[ROOT/'datos/brutos/geih2018_original.csv']+list(OUT.glob('*.pdf'))
    manifest=[{'archivo':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in paths]
    (ROOT/'output/manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('PDF generados:',*[p.name for p in OUT.glob('*.pdf')])


if __name__=='__main__':construir()
