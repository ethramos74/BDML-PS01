"""Contrastes independientes y casos límite de identidades estadísticas."""
import sys,unittest
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import Ridge
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
for p in ['punto1_perfil_edad_ingreso','punto2_brecha_genero','punto3_prediccion_ingreso']:sys.path.insert(0,str(ROOT/p/'src'))
from perfil_edad import mco,pico_delta,bootstrap
from brecha_genero import fwl,bootstrap_fwl
from geih_modelos import ajustar_ridge,Diseno
from analisis_lineal import seleccion_grupos
from src.numerica import cov_cluster

class Identidades(unittest.TestCase):
    def setUp(self):
        r=np.random.default_rng(812);self.X=np.column_stack([np.ones(120),r.normal(size=(120,3))])
        self.y=self.X@np.array([2.,.8,-.6,.1])+r.normal(size=120)*(1+abs(self.X[:,1]))
    def test_mco_y_hc(self):
        f=mco(self.X,self.y);s=sm.OLS(self.y,self.X).fit()
        np.testing.assert_allclose(f['beta'],s.params,atol=1e-10)
        for v in ['HC1','HC3']:np.testing.assert_allclose(f['V_'+v.lower()],s.get_robustcov_results(cov_type=v).cov_params(),atol=1e-10)
    def test_rango_y_escala(self):
        X=np.column_stack([self.X,self.X[:,1]*1e9]);f=mco(X,self.y);self.assertEqual(f['k'],4)
        np.testing.assert_allclose(f['ajust'],sm.OLS(self.y,self.X).fit().fittedvalues,atol=1e-8)
    def test_fwl_y_grados_libertad(self):
        W=np.column_stack([self.X[:,:2],2*self.X[:,1]]);d=self.X[:,2];f=fwl(self.y,d,W)
        s=sm.OLS(self.y,np.column_stack([W,d])).fit();self.assertEqual(f['k'],3)
        self.assertAlmostEqual(f['b'],s.params[-1],places=10)
        self.assertAlmostEqual(f['se_corregido'],s.bse[-1],places=10)
        self.assertAlmostEqual(f['se_hc1'],s.get_robustcov_results(cov_type='HC1').bse[-1],places=10)
    def test_fwl_ponderado_y_hc1(self):
        w=np.exp(self.X[:,1]);W=self.X[:,:3];d=self.X[:,3]
        f=fwl(self.y,d,W,w);s=sm.WLS(self.y,self.X,weights=w).fit()
        self.assertAlmostEqual(f['b'],s.params[-1],places=10)
        self.assertAlmostEqual(f['se_hc1'],s.get_robustcov_results(cov_type='HC1').bse[-1],places=10)
        np.testing.assert_allclose(f['u']/np.sqrt(w/w.mean()),s.resid,atol=1e-10)
        f2=fwl(self.y,d,W,w*150)
        self.assertAlmostEqual(f['b'],f2['b'],places=10)
        self.assertAlmostEqual(f['se_hc1'],f2['se_hc1'],places=10)
    def test_bootstrap_pares_ponderado(self):
        w=np.exp(self.X[:,1]);B=8;seed=7;bs=bootstrap_fwl(self.y,self.X[:,3],self.X[:,:3],B=B,semilla=seed,pesos=w)
        rng=np.random.default_rng(seed)
        for b in range(B):
            ix=rng.integers(0,len(w),len(w));ref=sm.WLS(self.y[ix],self.X[ix],weights=w[ix]).fit().params[-1]
            self.assertAlmostEqual(bs[b],ref,places=10)
    def test_ridge_sklearn_y_loo(self):
        X,y=self.X,self.y;s=X.std(0);s[0]=0;f=ajustar_ridge(X,y,3.4)
        Z=X[:,1:]/s[1:];sk=Ridge(alpha=3.4).fit(Z,y)
        np.testing.assert_allclose(f['ajuste'],sk.predict(Z),atol=1e-9)
        for i in [0,18,119]:
            ok=np.arange(len(y))!=i;b=ajustar_ridge(X[ok],y[ok],3.4,escalar=s)['beta']
            self.assertAlmostEqual(f['loo'][i],y[i]-X[i]@b,places=9)
    def test_leverage_unitario(self):
        X=np.column_stack([self.X,np.arange(len(self.y))==0]);f=ajustar_ridge(X,self.y,0)
        self.assertTrue(np.isinf(f['loo'][0]))
    def test_cluster_statsmodels(self):
        grupos=np.repeat(np.arange(30),4);f=mco(self.X,self.y)
        V=sm.OLS(self.y,self.X).fit().get_robustcov_results(cov_type='cluster',groups=grupos).cov_params()
        np.testing.assert_allclose(cov_cluster(f,grupos),V,atol=1e-10)
    def test_delta_diferencias_finitas(self):
        b=np.array([1,.08,-.001]);V=np.diag([.01,.0001,.00000001]);_,se=pico_delta(b,V);h=1e-8
        fun=lambda x:-x[1]/(2*x[2]);g=np.array([(fun(b+np.eye(3)[i]*h)-fun(b-np.eye(3)[i]*h))/(2*h) for i in range(3)])
        self.assertAlmostEqual(se,np.sqrt(g@V@g),places=6)
    def test_seleccion_grupos_recupera_senal(self):
        rng=np.random.default_rng(26);x=rng.normal(size=(240,3));X=np.column_stack([np.ones(240),x,x[:,0]*x[:,1]])
        y=5*x[:,0]+3*x[:,1]+2*x[:,0]*x[:,1]+rng.normal(scale=.01,size=240)
        vc=[set(),{'a'},{'b'},{'ruido'},{'a','b'}]
        h,act,ix=seleccion_grupos(X,y,vc,1.,'adelante')
        self.assertTrue({'a','b'}<=set(act));self.assertIn(4,ix)
        self.assertTrue((h.RMSE_LOOCV.diff().dropna()<0).all())
    def test_categoria_unica(self):
        X,_,_=Diseno([('cat','g')]).fit_transform(pd.DataFrame({'g':['a']*8}));self.assertEqual(X.shape,(8,1))
    def test_splines_redundantes_leverage(self):
        rng=np.random.default_rng(13);d=pd.DataFrame({'age':rng.integers(18,80,800),'female':rng.integers(0,2,800)})
        terms=[('spline','age',6),('num','female'),('inter',('num','female'),('spline','age',6))]
        X,_,_=Diseno(terms).fit_transform(d);X=np.column_stack([X,X[:,2]])
        y=rng.normal(size=len(d));f=ajustar_ridge(X,y,0)
        self.assertLessEqual(f['gl'],X.shape[1]+1e-7)
        np.testing.assert_allclose(f['ajuste'],X@np.linalg.lstsq(X,y,rcond=None)[0],atol=1e-9)

class DatosYEntregas(unittest.TestCase):
    def test_muestra_y_separacion(self):
        m=pd.read_csv(ROOT/'datos/limpios/geih2018_muestra.csv');self.assertTrue(m.id_persona.is_unique)
        self.assertTrue((m.y_total_m>0).all());np.testing.assert_allclose(m.log_y,np.log(m.y_total_m),atol=1e-12)
        self.assertTrue((m.age>=18).all());self.assertTrue((m.entrenamiento==m.chunk.le(7)).all())
    def test_ganador_real(self):
        t=pd.read_csv(ROOT/'punto3_prediccion_ingreso/salidas/rmse_especificaciones.csv')
        self.assertIn('seleccionado',t)
        self.assertEqual(set(t.familia),{'MCO','Ridge'})
        self.assertTrue({'R5','R6','R7','M1w','M2w','M3w','M4w','M4iw'}<=set(t.modelo))
        self.assertEqual(int(t.seleccionado.sum()),1)
        self.assertAlmostEqual(t.loc[t.seleccionado,'RMSE_validacion'].iloc[0],t.RMSE_validacion.min())
        self.assertGreaterEqual(len(t),9)
    def test_predicciones_loo_completas(self):
        p=pd.read_csv(ROOT/'punto3_prediccion_ingreso/salidas/predicciones_cv.csv')
        c=pd.read_csv(ROOT/'punto3_prediccion_ingreso/salidas/loocv_vs_validacion.csv')
        m=pd.read_csv(ROOT/'datos/limpios/geih2018_muestra.csv')
        expected=set(m.loc[m.entrenamiento & m.maxEducLevel.notna(),'id_persona'])
        self.assertEqual(set(p.id_persona),expected)
        self.assertTrue(p.id_persona.is_unique)
        self.assertTrue(np.isfinite(p.pred_loo).all())
        self.assertAlmostEqual(np.sqrt(np.mean((p.log_y-p.pred_loo)**2)),c.loc[c.medida.str.startswith('LOOCV'),'RMSE'].iloc[0],places=10)
    def test_cobertura_de_todas_las_variables(self):
        for name,path in [('base_completa','datos/intermedios/geih2018_tipado.csv'),('muestra_analisis','datos/limpios/geih2018_muestra.csv')]:
            d=pd.read_csv(ROOT/path);s=pd.read_csv(ROOT/f'datos/auditoria/summary_{name}.csv').set_index('variable')
            self.assertEqual(set(s.index),set(d.columns))
            for c in d:
                self.assertEqual(s.loc[c,'no_nulos'],d[c].notna().sum())
                self.assertAlmostEqual(s.loc[c,'porcentaje_no_nulos'],100*d[c].notna().mean(),places=10)

if __name__=='__main__':unittest.main()
