"""Regenera cuadernos, HTML, tablas y figuras: python main.py."""
from pathlib import Path
import argparse, json, os, sys, time
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
os.environ['PS1_GEIH2018_DIR']=str(ROOT)
os.environ['MPLBACKEND']='Agg'
os.environ['PYTHONUTF8']='1'
for v in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[v]='1'
NOTEBOOKS={
 'datos':'datos/01_datos_obtencion_validacion_limpieza.ipynb',
 'edad':'punto1_perfil_edad_ingreso/punto1_perfil_edad_ingreso.ipynb',
 'brecha':'punto2_brecha_genero/punto2_brecha_genero.ipynb',
 'prediccion':'punto3_prediccion_ingreso/punto3_prediccion_ingreso_laboral.ipynb'}


def ejecutar_cuaderno(etapa):
    """Proceso IPython independiente con captura de tablas, gráficos y errores."""
    import nbformat
    from IPython.core.interactiveshell import InteractiveShell
    from IPython.utils.capture import capture_output
    from IPython.display import display, Image
    from nbconvert import HTMLExporter
    import matplotlib.pyplot as plt
    from threadpoolctl import threadpool_limits
    import io
    p=ROOT/NOTEBOOKS[etapa];nb=nbformat.read(p,as_version=4)
    logdir=ROOT/'output/logs';logdir.mkdir(parents=True,exist_ok=True)
    shell=InteractiveShell.instance();shell.ast_node_interactivity='last_expr'
    figuras_datos=iter(['nb01_fig01_2_validacion','nb01_fig02_4_limpieza_una_sola_muestra_de_analisis','nb01_fig03_5_la_muestra_en_cuatro_figuras'])
    def show(*args,**kwargs):
        for num in plt.get_fignums():
            f=plt.figure(num);stream=io.BytesIO();f.savefig(stream,format='png',dpi=120,bbox_inches='tight')
            if etapa=='datos':
                nombre=next(figuras_datos);dest=ROOT/'datos/auditoria/figuras';dest.mkdir(exist_ok=True)
                f.savefig(dest/(nombre+'.png'),dpi=180,bbox_inches='tight')
            display(Image(data=stream.getvalue()))
        plt.close('all')
    plt.show=show
    log=[];count=0;start=time.time()
    with threadpool_limits(limits=1):
        for i,c in enumerate(nb.cells):
            if c.cell_type!='code':continue
            count+=1;c.outputs=[];c.execution_count=count
            print(f'[{etapa}] celda {i+1}/{len(nb.cells)}',flush=True)
            with capture_output() as cap:result=shell.run_cell(c.source,store_history=True)
            if cap.stdout:c.outputs.append(nbformat.v4.new_output('stream',name='stdout',text=cap.stdout))
            if cap.stderr:c.outputs.append(nbformat.v4.new_output('stream',name='stderr',text=cap.stderr))
            for out in cap.outputs:c.outputs.append(nbformat.v4.new_output('display_data',data=out.data,metadata=out.metadata))
            log.extend([f'CELDA {i}',cap.stdout,cap.stderr])
            if result.error_in_exec or result.error_before_exec:
                nbformat.write(nb,p);(logdir/f'{etapa}.log').write_text('\n'.join(log),encoding='utf8')
                raise RuntimeError(f'{etapa}, celda {i}: {result.error_in_exec or result.error_before_exec}')
    nb.metadata['language_info']={'name':'python','version':sys.version.split()[0]}
    nbformat.write(nb,p)
    exporter=HTMLExporter();exporter.embed_images=True
    html,_=exporter.from_notebook_node(nb)
    html=html.replace('</head>','<style>p strong,li strong,p b,li b,td strong,th {font-weight:400 !important;} table {font-variant-numeric:tabular-nums;} </style></head>')
    p.with_suffix('.html').write_text(html,encoding='utf8')
    (logdir/f'{etapa}.log').write_text('\n'.join(log),encoding='utf8')
    return dict(etapa=etapa,estado='OK',celdas_ejecutadas=count,segundos=round(time.time()-start,2))


def main():
    import subprocess
    parser=argparse.ArgumentParser();parser.add_argument('--etapa',choices=list(NOTEBOOKS)+['verificar'])
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    if args.worker:
        result=ejecutar_cuaderno(args.etapa)
        (ROOT/f'output/logs/{args.etapa}.json').write_text(json.dumps(result,indent=2),encoding='utf8')
        print(json.dumps(result));return
    etapas=[args.etapa] if args.etapa else list(NOTEBOOKS)+['verificar']
    for etapa in etapas:
        inicio=time.time()
        if etapa in NOTEBOOKS:subprocess.run([sys.executable,'-X','utf8',str(ROOT/'main.py'),'--worker','--etapa',etapa],check=True)
        elif etapa=='verificar':subprocess.run([sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-v'],check=True)
        if etapa=='verificar':
            (ROOT/'output/logs').mkdir(parents=True,exist_ok=True)
            (ROOT/f'output/logs/{etapa}.json').write_text(json.dumps({'etapa':etapa,'estado':'OK','segundos':round(time.time()-inicio,2)},indent=2),encoding='utf8')
    logs=ROOT/'output/logs';logs.mkdir(parents=True,exist_ok=True)
    resumen=[json.loads((logs/f'{etapa}.json').read_text(encoding='utf8'))
             for etapa in list(NOTEBOOKS)+['verificar'] if (logs/f'{etapa}.json').exists()]
    (logs/'ejecucion.json').write_text(json.dumps({'etapas':resumen,'python':sys.version.split()[0]},indent=2),encoding='utf8')


if __name__=='__main__':main()
