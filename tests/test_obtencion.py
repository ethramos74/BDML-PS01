"""Política de obtención verificada sin realizar peticiones externas."""
import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'datos/src'))
import geih_datos as gd

HTML='<table><thead><tr><th></th><th>age</th></tr></thead><tbody><tr><td>1</td><td>30</td></tr></tbody></table>'

class Obtencion(unittest.TestCase):
    def test_robots_prohibe_sin_descargar_tablas(self):
        session=Mock();session.headers={};session.get.return_value=Mock(status_code=200,text='User-agent: *\nDisallow: /')
        with tempfile.TemporaryDirectory() as dest,patch('requests.Session',return_value=session),patch.object(gd.time,'sleep'):
            with self.assertRaises(PermissionError):gd.obtener_datos(dest,verbose=False)
        self.assertEqual(session.get.call_count,1)

    def test_robots_ausente_y_pausa_minima(self):
        session=Mock();session.headers={}
        session.get.side_effect=[Mock(status_code=404,text=''),Mock(text='<div></div>'),Mock(text=HTML)]
        with tempfile.TemporaryDirectory() as dest,patch('requests.Session',return_value=session),patch.object(gd.time,'sleep') as sleep,patch.object(gd,'BLOQUES',[1]),patch.object(gd,'VARIABLES_ESPERADAS',['age']),patch.object(gd,'N_OBS_ESPERADAS',1):
            d=gd.obtener_datos(dest,pausa=0,verbose=False)
            self.assertEqual(d.age.iloc[0],'30')
            self.assertTrue(all(c.args[0]>=1 for c in sleep.call_args_list))
        self.assertEqual(session.get.call_count,3)

    def test_cache_evitar_red(self):
        with tempfile.TemporaryDirectory() as dest,patch('requests.Session') as session,patch.object(gd,'BLOQUES',[1]),patch.object(gd,'VARIABLES_ESPERADAS',['age']),patch.object(gd,'N_OBS_ESPERADAS',1):
            Path(dest,'page_01.html').write_text('<div></div>',encoding='utf8')
            Path(dest,'geih_page_01.html').write_text(HTML,encoding='utf8')
            self.assertEqual(len(gd.obtener_datos(dest,verbose=False)),1)
            session.return_value.get.assert_not_called()

if __name__=='__main__':unittest.main()
