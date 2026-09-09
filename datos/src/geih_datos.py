# -*- coding: utf-8 -*-
"""
geih_datos.py — Pipeline de datos del Problem Set 1 (GEIH 2018, Bogotá) en Python.

Tres etapas, cada una con su función principal:
  1. obtener_datos(...)   descarga (con caché local) y consolida los 10 bloques del sitio
                          del curso como TEXTO, sin tocar valores; agrega procedencia.
  2. validar(...)         corre las pruebas de integridad (estructura, procedencia,
                          contenido, llaves, códigos, identidades DANE, comparabilidad).
  3. tipar(...) / limpiar(...)  convierte a numérico y construye la muestra única
                          de análisis (ocupados 18+ con ingreso observado) con variables
                          derivadas, factores, banderas de extremos y diccionario.

Todas las decisiones están parametrizadas en CONFIG y documentadas en el notebook 01.
"""
from __future__ import annotations

import io
import os
import re
import time
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------------------
URL_BASE = "https://ignaciomsarmiento.github.io/GEIH2018_sample/"
BLOQUES = list(range(1, 11))
BLOQUES_ENTRENAMIENTO = list(range(1, 8))
BLOQUES_VALIDACION = [8, 9, 10]
N_OBS_ESPERADAS = 32177
N_VARS_ESPERADAS = 177
PROCEDENCIA = ["fila_en_bloque", "chunk", "url_origen", "muestra_ps3"]

CONFIG = dict(
    edad_minima=18,
    smmlv_2018=781_242,            # salario mínimo mensual 2018 (pesos)
    horas_semana_referencia=48,    # jornada legal 2018
    fraccion_minimo_hora=0.25,     # alerta_ingreso_bajo: ingreso/hora < 25 % del mínimo por hora
    multiplo_smmlv_alto=20,        # alerta_ingreso_alto: ingreso mensual > 20 SMMLV
    horas_maximas_plausibles=84,   # alerta_horas_altas: más de 12 h x 7 días
    min_obs_oficio=20,             # oficios con menos observaciones en la muestra principal -> "Otros"
)

VARIABLES_ESPERADAS = (
    "directorio,secuencia_p,orden,clase,dominio,mes,estrato1,sex,age,p6050,p6090,p6100,p6210,p6210s1,p6240,oficio,p6426,relab,"
    "p6500,p6510,p6510s1,p6510s2,p6545,p6545s1,p6545s2,p6580,p6580s1,p6580s2,p6585s1,p6585s1a1,p6585s1a2,p6585s2,p6585s2a1,p6585s2a2,"
    "p6585s3,p6585s3a1,p6585s3a2,p6585s4,p6585s4a1,p6585s4a2,p6590,p6590s1,p6600,p6600s1,p6610,p6610s1,p6620,p6620s1,p6630s1,p6630s1a1,"
    "p6630s2,p6630s2a1,p6630s3,p6630s3a1,p6630s4,p6630s4a1,p6630s6,p6630s6a1,p6750,p6760,p550,hoursWorkUsual,p6870,p6920,p7040,"
    "hoursWorkActualSecondJob,p7050,p7070,p7090,p7110,p7120,p7140s1,p7140s2,p7150,p7160,p7310,p7350,p7422,p7422s1,p7472,p7472s1,p7495,"
    "p7500s1,p7500s1a1,p7500s2,p7500s2a1,p7500s3,p7500s3a1,p7505,p7510s1,p7510s1a1,p7510s2,p7510s2a1,p7510s3,p7510s3a1,p7510s5,p7510s5a1,"
    "p7510s6,p7510s6a1,p7510s7,p7510s7a1,pet,ina,impa,isa,ie,imdi,iof1,iof2,iof3h,iof3i,iof6,cclasnr2,cclasnr3,cclasnr4,cclasnr5,cclasnr6,"
    "cclasnr7,cclasnr8,cclasnr11,impaes,isaes,iees,imdies,iof1es,iof2es,iof3hes,iof3ies,iof6es,ingtotob,ingtotes,ingtot,fex_c,depto,fex_dpto,"
    "fweight,maxEducLevel,college,regSalud,cotPension,wap,ocu,dsi,pea,inac,totalHoursWorked,formal,informal,cuentaPropia,microEmpresa,sizeFirm,"
    "y_salary_m,y_salary_m_hu,y_ingLab_m,y_horasExtras_m,y_especie_m,y_vivienda_m,y_otros_m,y_auxilioAliment_m,y_auxilioTransp_m,y_subFamiliar_m,"
    "y_subEducativo_m,y_primas_m,y_bonificaciones_m,y_primaServicios_m,y_primaNavidad_m,y_primaVacaciones_m,y_viaticos_m,y_accidentes_m,"
    "y_salarySec_m,y_ingLab_m_ha,y_gananciaNeta_m,y_gananciaNetaAgro_m,y_gananciaIndep_m,y_gananciaIndep_m_hu,y_total_m,y_total_m_ha"
).split(",")

# Conjuntos admisibles (diccionario del curso + catálogo DANE 547). El 9 solo es "no sabe"
# en las variables donde el DANE lo etiqueta así; en p6050, p6870 y relab es categoría válida.
CONJUNTOS = {
    "clase": [1], "depto": [11], "sex": [0, 1], "mes": list(range(1, 13)), "estrato1": list(range(1, 7)), "p6050": list(range(1, 10)),
    "p6090": [1, 2, 9], "p6100": [1, 2, 3, 9], "p6210": [1, 2, 3, 4, 5, 6, 9], "p6240": list(range(1, 7)), "oficio": list(range(1, 100)),
    "relab": list(range(1, 10)), "p6870": list(range(1, 10)), "p6920": [1, 2, 3], "p7040": [1, 2], "maxEducLevel": [1, 2, 3, 4, 5, 6, 7, 9],
    "college": [0, 1], "regSalud": [1, 2, 3, 9], "cotPension": [1, 2, 3, 9], "sizeFirm": list(range(1, 6)), "wap": [0, 1], "ocu": [0, 1],
    "dsi": [0, 1], "pea": [0, 1], "inac": [0, 1], "pet": [1], "ina": [1], "formal": [0, 1], "informal": [0, 1], "cuentaPropia": [0, 1],
    "microEmpresa": [0, 1],
}
MONTOS = ["p6500", "p6510s1", "p6545s1", "p6580s1", "p6585s1a1", "p6585s2a1", "p6585s3a1", "p6585s4a1", "p6590s1", "p6600s1", "p6610s1",
          "p6620s1", "p6630s1a1", "p6630s2a1", "p6630s3a1", "p6630s4a1", "p6630s6a1", "p6750", "p7070", "p7422s1", "p7472s1", "p7500s1a1",
          "p7500s2a1", "p7500s3a1", "p7510s1a1", "p7510s2a1", "p7510s3a1", "p7510s5a1", "p7510s6a1", "p7510s7a1"]

ETIQ_RELAB = {1: "Obrero/empleado particular", 2: "Empleado del gobierno", 3: "Empleado domestico", 4: "Cuenta propia",
              5: "Patron/empleador", 6: "Sin remuneracion", 7: "Sin remuneracion", 8: "Otro", 9: "Otro"}
NIV_RELAB = ["Obrero/empleado particular", "Empleado del gobierno", "Empleado domestico", "Cuenta propia", "Patron/empleador",
             "Sin remuneracion", "Otro"]
NIV_EDUC = ["Ninguno", "Preescolar", "Primaria incompleta", "Primaria completa", "Secundaria incompleta", "Secundaria completa", "Terciaria"]
NIV_SIZE = ["Independiente", "2-5 trabajadores", "6-10 trabajadores", "11-50 trabajadores", "Mas de 50 trabajadores"]
NIV_OFGRUPO = ["Profesionales y tecnicos", "Directivos", "Administrativos", "Comerciantes y vendedores", "Servicios", "Agropecuarios",
               "Operarios y transporte"]
NIV_PARENTESCO = {1: "Jefe/a", 2: "Pareja", 3: "Hijo/a", 4: "Nieto/a", 5: "Otro pariente", 6: "Servicio domestico", 7: "Pensionista",
                  8: "Trabajador", 9: "Otro no pariente"}
NIV_REGSALUD = {1: "Contributivo", 2: "Especial", 3: "Subsidiado"}


# --------------------------------------------------------------------------------------
# 1. Obtención
# --------------------------------------------------------------------------------------
def _leer_tabla_html(html: str) -> pd.DataFrame:
    """Extrae la única tabla de una página como texto crudo (sin conversión de tipos)."""
    from lxml import html as lh
    doc = lh.fromstring(html)
    tablas = doc.xpath("//table")
    if len(tablas) != 1:
        raise ValueError(f"Se esperaba exactamente una tabla; hay {len(tablas)}")
    t = tablas[0]
    encabezados = [("".join(th.itertext())).strip() for th in t.xpath("./thead/tr/th")]
    filas = [[("".join(td.itertext())).strip() for td in tr.xpath("./td")] for tr in t.xpath("./tbody/tr")]
    if not filas or any(len(f) != len(encabezados) for f in filas):
        raise ValueError("La tabla está vacía o no es rectangular")
    if encabezados[0] != "":
        raise ValueError("La primera columna debía ser el índice de fila sin nombre")
    encabezados[0] = "fila_en_bloque"
    return pd.DataFrame(filas, columns=encabezados, dtype=str)


def obtener_datos(carpeta_html: str, pausa: float = 1.0, url_base: str = URL_BASE, verbose: bool = True) -> pd.DataFrame:
    """Descarga los 10 bloques (con caché en carpeta_html) y devuelve la base consolidada
    como texto con las columnas de procedencia. Politica de cortesía: descarga secuencial,
    una pausa entre peticiones y reutilización de los HTML ya guardados."""
    import requests
    os.makedirs(carpeta_html, exist_ok=True)
    sesion = requests.Session(); sesion.headers["User-Agent"] = "GEIH2018AcademicBot/1.0"
    robots = None

    def permiso(url):
        nonlocal robots, pausa
        if urlsplit(url).netloc != urlsplit(url_base).netloc:
            raise ValueError("La fuente apunta a otro dominio; requiere revisar su política")
        if robots is None:
            robot_url = urljoin(url_base, "/robots.txt")
            time.sleep(max(pausa, 1.0))
            response = sesion.get(robot_url, timeout=60)
            robots = RobotFileParser(robot_url)
            if response.status_code in (404, 410):
                robots.parse([])
            elif response.status_code == 200:
                robots.parse(response.text.splitlines())
            else:
                raise RuntimeError(f"No se pudo verificar robots.txt: HTTP {response.status_code}")
            pausa = max(pausa, robots.crawl_delay(sesion.headers['User-Agent']) or robots.crawl_delay('*') or 1.0)
            Path(carpeta_html, "robots.txt").write_text(response.text, encoding="utf8")
            Path(carpeta_html, "robots_auditoria.json").write_text(json.dumps({
                "url": robot_url, "http_status": response.status_code,
                "consultado_utc": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                "delay_segundos": pausa,
                "interpretacion": "sin archivo de reglas" if response.status_code in (404, 410) else "reglas analizadas"
            }, indent=2), encoding="utf8")
        if not robots.can_fetch(sesion.headers['User-Agent'], url):
            raise PermissionError(f"robots.txt no permite consultar {url}")

    def bajar(url, nombre):
        ruta = os.path.join(carpeta_html, nombre)
        if os.path.exists(ruta) and os.path.getsize(ruta) > 0:
            return Path(ruta).read_text(encoding="utf-8")
        permiso(url)
        time.sleep(pausa)
        r = sesion.get(url, timeout=300); r.raise_for_status()
        Path(ruta).write_text(r.text, encoding="utf-8")
        return r.text

    bloques = []
    for k in BLOQUES:
        pagina = bajar(f"{url_base}page{k}.html", f"page_{k:02d}.html")
        m = re.search(r'w3-include-html="([^"]+)"', pagina)
        url_tabla = (m.group(1) if m else f"pages/geih_page_{k}.html")
        if not url_tabla.startswith("http"):
            url_tabla = urljoin(url_base, url_tabla)
        html = bajar(url_tabla, f"geih_page_{k:02d}.html")
        d = _leer_tabla_html(html)
        faltan = set(VARIABLES_ESPERADAS) - set(d.columns)
        if faltan:
            raise ValueError(f"Bloque {k}: faltan variables {sorted(faltan)[:5]}...")
        d["chunk"] = k; d["url_origen"] = url_tabla
        d["muestra_ps3"] = "entrenamiento" if k in BLOQUES_ENTRENAMIENTO else "validacion"
        bloques.append(d)
        if verbose:
            print(f"bloque {k:2d}: {len(d):,} filas")
    datos = pd.concat(bloques, ignore_index=True)
    if len(datos) != N_OBS_ESPERADAS:
        raise ValueError(f"Total inesperado: {len(datos)} (esperado {N_OBS_ESPERADAS})")
    return datos[["fila_en_bloque"] + VARIABLES_ESPERADAS + ["chunk", "url_origen", "muestra_ps3"]]


def cargar_original(ruta_csv: str) -> pd.DataFrame:
    """Lee la base bruta como texto, con 'NA' literal (no como NaN)."""
    d = pd.read_csv(ruta_csv, dtype=str, keep_default_na=False)
    d["chunk"] = d["chunk"].astype(int)
    return d


# --------------------------------------------------------------------------------------
# 2. Validación
# --------------------------------------------------------------------------------------
@dataclass
class Bitacora:
    filas: list = field(default_factory=list)

    def registrar(self, id_, categoria, prueba, resultado, detalle=""):
        assert resultado in ("OK", "ADVERTENCIA", "ERROR")
        self.filas.append(dict(id=id_, categoria=categoria, prueba=prueba, resultado=resultado, detalle=str(detalle)))

    def comprobar(self, id_, categoria, prueba, condicion, detalle="", si_falla="ERROR"):
        self.registrar(id_, categoria, prueba, "OK" if bool(condicion) else si_falla, detalle)

    def tabla(self):
        return pd.DataFrame(self.filas)


def a_numero(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.where(s != "NA"), errors="coerce")


def tipar(datos: pd.DataFrame) -> pd.DataFrame:
    """Convierte las 177 variables originales a numérico (dominio queda como texto)."""
    out = datos.copy()
    for v in VARIABLES_ESPERADAS:
        if v != "dominio":
            out[v] = a_numero(out[v])
    out["fila_en_bloque"] = out["fila_en_bloque"].astype(int)
    return out


def validar(datos: pd.DataFrame, diccionario_dane: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    """Corre las pruebas de integridad sobre la base bruta (texto). Devuelve la tabla de
    resultados y un diccionario con las tablas de apoyo (mes x bloque, panorama, etc.)."""
    b = Bitacora(); apoyo = {}
    # 1. Estructura
    c = "1. Estructura"
    b.comprobar("1.1", c, "Número de observaciones", len(datos) == N_OBS_ESPERADAS, f"{len(datos):,} (esperadas {N_OBS_ESPERADAS:,})")
    b.comprobar("1.2", c, "Número de columnas (177 + 4 de procedencia)", datos.shape[1] == N_VARS_ESPERADAS + 4, datos.shape[1])
    originales = [v for v in datos.columns if v in VARIABLES_ESPERADAS]
    b.comprobar("1.3", c, "Las 177 variables originales están presentes y en el orden del sitio", originales == VARIABLES_ESPERADAS)
    b.comprobar("1.4", c, "Columnas de procedencia presentes", all(p in datos.columns for p in PROCEDENCIA))
    # 2. Procedencia
    c = "2. Procedencia y bloques"
    conteo = datos["chunk"].value_counts().sort_index()
    b.comprobar("2.1", c, "chunk toma los valores 1..10 con 3.217-3.218 filas cada uno",
                list(conteo.index) == BLOQUES and conteo.between(3217, 3218).all(), "; ".join(f"{k}={v}" for k, v in conteo.items()))
    esperada = np.where(datos["chunk"].isin(BLOQUES_ENTRENAMIENTO), "entrenamiento", "validacion")
    b.comprobar("2.2", c, "muestra_ps3 = entrenamiento (1-7) / validacion (8-10)", (datos["muestra_ps3"].to_numpy() == esperada).all())
    fila = datos["fila_en_bloque"].astype(int)
    b.comprobar("2.3", c, "fila_en_bloque es 1..n dentro de cada bloque", all((fila[datos["chunk"] == k].to_numpy() == np.arange(1, (datos["chunk"] == k).sum() + 1)).all() for k in BLOQUES))
    # 3. Contenido textual
    c = "3. Contenido textual y conversión"
    patron = re.compile(r"^-?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][-+]?[0-9]+)?$")
    no_num, vacias, n_sci, n_blancos = [], [], 0, 0
    for v in VARIABLES_ESPERADAS:
        s = datos[v]; pres = s[s != "NA"]
        n_blancos += int((pres.str.strip() == "").sum())
        if len(pres) == 0: vacias.append(v); continue
        if not pres.str.match(patron).all(): no_num.append(v)
        n_sci += int(pres.str.contains("e", regex=False).sum())
    b.comprobar("3.1", c, "Los faltantes vienen como texto 'NA'; no hay blancos", n_blancos == 0, f"blancos: {n_blancos}")
    b.comprobar("3.2", c, "Todo valor presente es numérico salvo dominio (= BOGOTA)", no_num == ["dominio"], f"no numéricas: {no_num}")
    b.registrar("3.3", c, "Notación científica (cifras redondas, se recupera exacta)", "OK", f"{n_sci:,} celdas")
    b.comprobar("3.4", c, "Columnas 100 % NA: solo p550 y y_gananciaNetaAgro_m", set(vacias) == {"p550", "y_gananciaNetaAgro_m"}, vacias, "ADVERTENCIA")
    num = tipar(datos)
    perdidas = sum(int(num[v].isna().sum() - (datos[v] == "NA").sum()) for v in VARIABLES_ESPERADAS if v != "dominio")
    b.comprobar("3.5", c, "La conversión a numérico no crea NA adicionales", perdidas == 0, perdidas)
    # 4. Llaves y constantes
    c = "4. Llaves y constantes"
    llave = datos["directorio"] + "-" + datos["secuencia_p"] + "-" + datos["orden"]
    b.comprobar("4.1", c, "directorio + secuencia_p + orden identifica una única persona", llave.is_unique,
                f"viviendas {datos['directorio'].nunique():,}; hogares {(datos['directorio'] + '-' + datos['secuencia_p']).nunique():,}")
    b.comprobar("4.2", c, "clase = 1, dominio = BOGOTA, depto = 11 constantes", (num["clase"] == 1).all() and (datos["dominio"] == "BOGOTA").all() and (num["depto"] == 11).all())
    b.comprobar("4.3", c, "fex_c positivo; su suma aproxima la población de Bogotá 2018", (num["fex_c"] > 0).all(), f"suma fex_c = {num['fex_c'].sum():,.0f}")
    # 5. Códigos
    c = "5. Codificaciones"
    fuera = {v: sorted(set(num[v].dropna().unique()) - set(CONJUNTOS[v])) for v in CONJUNTOS}
    fuera = {k: v for k, v in fuera.items() if v}
    b.comprobar("5.1", c, "Todas las variables codificadas toman solo valores admisibles", not fuera, fuera or f"{len(CONJUNTOS)} variables")
    b.comprobar("5.2", c, "age entera entre 0 y 110", num["age"].between(0, 110).all(), f"min {num['age'].min():.0f}, max {num['age'].max():.0f}")
    h = num["totalHoursWorked"]
    b.comprobar("5.3", c, "totalHoursWorked entre 1 y 168", h.dropna().between(1, 168).all(), f"max {h.max():.0f}; >126: {(h > 126).sum()}")
    centinelas = {v: int(num[v].isin([98, 99]).sum()) for v in MONTOS}
    centinelas["p6426"] = int(num["p6426"].isin([998, 999]).sum()); centinelas["hoursWorkActualSecondJob"] = int(num["hoursWorkActualSecondJob"].isin([98, 99]).sum())
    b.comprobar("5.4", c, "Sin códigos especiales DANE (98/99 en montos, 998/999 en antigüedad)", sum(centinelas.values()) == 0,
                {k: v for k, v in centinelas.items() if v} or f"{len(centinelas)} variables", "ADVERTENCIA")
    # 6. Diccionario DANE
    c = "6. Catálogo DANE"
    if diccionario_dane is not None:
        alias = {"P6020": "sex", "P6040": "age", "P4030S1A1": "estrato1", "P6430": "relab", "OFICIO": "oficio", "P6800": "hoursWorkUsual",
                 "P7045": "hoursWorkActualSecondJob", "DPTO": "depto", "MES": "mes"}
        n_cruz, fallas = 0, {}
        for _, r in diccionario_dane.iterrows():
            nd = str(r["variable"]).strip().upper(); nombre = alias.get(nd, nd.lower()); cats = str(r.get("categorias", "") or "").strip()
            if nombre not in num.columns or not cats or nombre in ("sex", "ocu", "dsi", "dominio"): continue
            adm = []
            for x in cats.split(";"):
                if "=" in x:
                    try: adm.append(float(x.split("=")[0].strip()))
                    except ValueError: pass
            if not adm: continue
            n_cruz += 1
            f = sorted(set(num[nombre].dropna().unique()) - set(adm))
            if f: fallas[nombre] = f
        b.comprobar("6.1", c, "Códigos observados dentro de las categorías del catálogo DANE 547", not fallas, fallas or f"{n_cruz} variables cruzadas", "ADVERTENCIA")
    else:
        b.registrar("6.1", c, "Catálogo DANE no disponible", "ADVERTENCIA", "se omite el cruce")
    # 7. Consistencia de variables construidas
    c = "7. Consistencia de variables construidas"
    ocu = num["ocu"] == 1
    def igual(a, b_, tol=0, rel=False):
        a, b_ = np.asarray(a, float), np.asarray(b_, float); ambos = np.isnan(a) & np.isnan(b_)
        d = np.abs(a - b_); d = d / np.maximum(np.maximum(np.abs(a), np.abs(b_)), 1) if rel else d
        return ambos | (d <= tol)
    b.comprobar("7.1", c, "pea = ocu | dsi; ocu + dsi + inac = wap", (num["pea"] == ((num["ocu"] == 1) | (num["dsi"] == 1)).astype(float)).all() and ((num["ocu"] + num["dsi"] + num["inac"]) == num["wap"]).all())
    lab = ["relab", "oficio", "totalHoursWorked", "hoursWorkUsual", "sizeFirm", "microEmpresa", "formal", "informal", "p6426", "p6870"]
    b.comprobar("7.2", c, "Variables de empleo existen exactamente para ocu = 1", all((num[v].isna() == ~ocu).all() for v in lab), f"ocupados {int(ocu.sum()):,}")
    b.comprobar("7.3", c, "cuentaPropia = (relab == 4); microEmpresa = (sizeFirm <= 2); cotPension = p6920; regSalud = p6100 con 9 -> NA",
                (num["cuentaPropia"] == (num["relab"] == 4).astype(float)).all() and igual(num["microEmpresa"], (num["sizeFirm"] <= 2).astype(float).where(num["sizeFirm"].notna())).all()
                and igual(num["cotPension"], num["p6920"]).all() and igual(num["regSalud"], num["p6100"].where(num["p6100"] != 9)).all())
    rec = num["p6870"].map({1: 1, 2: 2, 3: 2, 4: 3, 5: 4, 6: 4, 7: 4, 8: 5, 9: 5})
    b.comprobar("7.4", c, "sizeFirm recodifica p6870 (1; 2-3; 4; 5-7; 8-9)", igual(num["sizeFirm"], rec).all())
    coinc_terc = float((num["college"] == (num["maxEducLevel"] == 7).astype(float)).mean()); coinc_media = float((num["college"] == (num["maxEducLevel"] == 6).astype(float)).mean())
    b.comprobar("7.5", c, "college = 1 corresponde a terciaria (maxEducLevel = 7) como dice el diccionario", coinc_terc == 1,
                f"coincide con terciaria {100*coinc_terc:.0f} %; con secundaria completa {100*coinc_media:.0f} % -> NO usar college", "ADVERTENCIA")
    y, yl, yg = num["y_total_m"], num["y_ingLab_m"], num["y_gananciaIndep_m"]
    suma = (yl.fillna(0) + yg.fillna(0)).where(~(yl.isna() & yg.isna()))
    b.comprobar("7.6", c, "y_total_m = y_ingLab_m + y_gananciaIndep_m; nadie tiene ambos; nunca vale cero", igual(y, suma, 1).all() and not (yl.notna() & yg.notna()).any() and not (y == 0).any(),
                f"con asalariado {int(yl.notna().sum()):,}; con independiente {int(yg.notna().sum()):,}")
    b.comprobar("7.7", c, "y_salary_m = p6500 con los ceros convertidos a NA", igual(num["y_salary_m"], num["p6500"].where(num["p6500"] != 0), 0.5).all(), f"p6500 = 0: {int((num['p6500'] == 0).sum())}")
    b.comprobar("7.8", c, "y_gananciaNeta_m = p6750 / p6760 = y_gananciaIndep_m", igual(num["y_gananciaNeta_m"], num["p6750"] / num["p6760"], 1e-5, True).all() and igual(num["y_gananciaNeta_m"], yg).all())
    f_mes = 30 / 7
    b.comprobar("7.9", c, "y_total_m_ha = y_total_m / (totalHoursWorked x 30/7); idem salario y ingreso laboral por hora",
                igual(num["y_total_m_ha"], y / (h * f_mes), 1e-5, True).all() and igual(num["y_salary_m_hu"], num["y_salary_m"] / (num["hoursWorkUsual"] * f_mes), 1e-5, True).all())
    seg = num["hoursWorkActualSecondJob"].fillna(0)
    b.comprobar("7.10", c, "totalHoursWorked = hoursWorkUsual + hoursWorkActualSecondJob", igual(h, (num["hoursWorkUsual"] + seg).where(num["hoursWorkUsual"].notna())).all())
    # 8. Panorama de la muestra
    c = "8. Panorama de la muestra"
    adulto = num["age"] >= CONFIG["edad_minima"]; base = ocu & adulto & y.notna()
    b.registrar("8.1", c, "Tamaños de muestra", "OK", f"ocupados {int(ocu.sum()):,}; ocupados 18+ {int((ocu & adulto).sum()):,}; con y_total_m {int(base.sum()):,}; sin y_total_m {int((ocu & adulto & y.isna()).sum()):,}")
    falt = num.loc[ocu & adulto & y.isna(), "relab"].value_counts().sort_index()
    b.registrar("8.2", c, "Ocupados 18+ sin y_total_m por relab", "OK", "; ".join(f"{int(k)}={v}" for k, v in falt.items()))
    reempl = base & num["impaes"].notna()
    b.registrar("8.3", c, "Ingresos observados que el DANE reemplazó por imputación (extremos)", "ADVERTENCIA" if reempl.any() else "OK", f"{int(reempl.sum())} casos")
    apoyo["panorama"] = dict(ocupados=int(ocu.sum()), ocupados_18=int((ocu & adulto).sum()), muestra=int(base.sum()), sin_ingreso=int((ocu & adulto & y.isna()).sum()))
    # 9. Comparabilidad
    c = "9. Comparabilidad entrenamiento / validación"
    mes_bloque = pd.crosstab(datos["chunk"], num["mes"]); apoyo["mes_por_bloque"] = mes_bloque
    b.registrar("9.1", c, "Los bloques siguen el calendario (2-3 meses consecutivos por bloque): partición temporal", "ADVERTENCIA",
                "; ".join(f"{k}={'-'.join(str(m) for m in row[row > 0].index)}" for k, row in mes_bloque.iterrows()))
    viv_e = set(datos.loc[datos["chunk"].isin(BLOQUES_ENTRENAMIENTO), "directorio"]); viv_v = set(datos.loc[datos["chunk"].isin(BLOQUES_VALIDACION), "directorio"])
    b.comprobar("9.2", c, "Casi ninguna vivienda aparece en ambas particiones", len(viv_e & viv_v) <= 2, f"viviendas en ambas: {len(viv_e & viv_v)}", "ADVERTENCIA")
    part = datos["muestra_ps3"]
    ly = np.log(y)
    dif = abs(ly[base & (part == "validacion")].mean() - ly[base & (part == "entrenamiento")].mean())
    b.comprobar("9.3", c, "Media de log(y) similar entre particiones (muestra base)", dif < 0.05, f"dif = {dif:.3f}; sd ent {ly[base & (part=='entrenamiento')].std():.3f} vs val {ly[base & (part=='validacion')].std():.3f}", "ADVERTENCIA")
    for v in ["relab", "oficio", "sizeFirm", "maxEducLevel", "estrato1"]:
        e = set(num.loc[base & (part == "entrenamiento"), v].dropna()); s_ = set(num.loc[base & (part == "validacion"), v].dropna()) - e
        b.comprobar(f"9.4.{v}", c, f"{v}: todo nivel de validación existe en entrenamiento", not s_, f"solo en validación: {sorted(s_)}" if s_ else f"{len(e)} niveles", "ADVERTENCIA")
    return b.tabla(), apoyo


# --------------------------------------------------------------------------------------
# 3. Limpieza
# --------------------------------------------------------------------------------------
def limpiar(tipado: pd.DataFrame, cfg: dict = CONFIG) -> dict:
    """Construye la base ampliada (ocupados 18+) y la muestra principal. Devuelve un dict
    con 'ocupados18', 'muestra', 'embudo', 'exclusiones', 'alertas', 'oficios', 'diccionario'."""
    d = tipado
    n_base = len(d); n_ocu = int((d["ocu"] == 1).sum())
    oc = d[(d["ocu"] == 1) & (d["age"] >= cfg["edad_minima"])].copy()
    umbral_hora_bajo = cfg["smmlv_2018"] / (cfg["horas_semana_referencia"] * 30 / 7) * cfg["fraccion_minimo_hora"]
    umbral_alto = cfg["multiplo_smmlv_alto"] * cfg["smmlv_2018"]
    oc["id_persona"] = oc["directorio"].astype(int).astype(str) + "-" + oc["secuencia_p"].astype(int).astype(str) + "-" + oc["orden"].astype(int).astype(str)
    oc["entrenamiento"] = oc["muestra_ps3"] == "entrenamiento"
    oc["log_y"] = np.log(oc["y_total_m"])
    oc["female"] = 1 - oc["sex"].astype(int)
    oc["jefe_hogar"] = (oc["p6050"] == 1).astype(int)
    oc["parentesco_f"] = pd.Categorical(oc["p6050"].map(NIV_PARENTESCO), categories=list(NIV_PARENTESCO.values()))
    oc["educ_f"] = pd.Categorical(oc["maxEducLevel"].map(dict(zip(range(1, 8), NIV_EDUC))), categories=NIV_EDUC)
    oc["terciaria"] = (oc["maxEducLevel"] == 7).astype(float).where(oc["maxEducLevel"].notna())
    s1, p = oc["p6210s1"].astype(float), oc["p6210"]
    oc["anios_educ"] = np.select([p.isna() | (p == 9) | s1.isna() | (s1 == 99), p.isin([1, 2]), p == 3, p == 4, p == 5, p == 6],
                                 [np.nan, 0, s1, np.where(s1 == 0, 5, s1), np.where(s1 == 0, 9, s1), 11 + s1], default=np.nan)
    oc["relab_f"] = pd.Categorical(oc["relab"].map(ETIQ_RELAB), categories=NIV_RELAB)
    oc["oficio_grupo"] = pd.cut(oc["oficio"], bins=[0, 19, 29, 39, 49, 59, 69, 99], labels=NIV_OFGRUPO)
    oc["sizeFirm_f"] = pd.Categorical(oc["sizeFirm"].map(dict(zip(range(1, 6), NIV_SIZE))), categories=NIV_SIZE)
    oc["estrato_f"] = pd.Categorical(oc["estrato1"].astype(int).astype(str), categories=[str(i) for i in range(1, 7)])
    oc["regSalud_f"] = pd.Categorical(oc["regSalud"].map(NIV_REGSALUD).fillna("No responde"), categories=list(NIV_REGSALUD.values()) + ["No responde"])
    oc["mes_f"] = pd.Categorical(oc["mes"].astype(int).astype(str), categories=[str(i) for i in range(1, 13)])
    oc["cotiza_pension"] = (oc["cotPension"] == 1).astype(int)
    oc["antiguedad_anios"] = oc["p6426"] / 12
    oc["segundo_empleo"] = (oc["p7040"] == 1).astype(int)
    oc["horas_segundo_empleo"] = oc["hoursWorkActualSecondJob"].fillna(0)
    oc["quiere_mas_horas"] = (oc["p7090"] == 1).astype(int)
    y = oc["y_total_m"]
    oc["motivo_exclusion"] = np.select(
        [y.notna() & (y > 0), y.notna() & (y <= 0), oc["relab"].isin([6, 7]), oc["relab"].isin([1, 2, 3, 8]), oc["relab"].isin([4, 5, 9])],
        [None, "Ingreso reportado igual a 0", "Sin remuneracion por definicion (relab 6 o 7)",
         "Asalariado que no reporto el monto (p6500 = 0; DANE lo imputa)", "Independiente o patron que no reporto el monto (p6750 NA; DANE lo imputa)"],
        default="Sin ingreso reportado")
    oc["muestra_principal"] = oc["motivo_exclusion"].isna()
    oc["dane_faltante"] = (oc["cclasnr2"] == 1).astype(float).where(oc["cclasnr2"].notna())
    oc["alerta_ingreso_bajo"] = oc["y_total_m_ha"].notna() & (oc["y_total_m_ha"] < umbral_hora_bajo)
    oc["alerta_ingreso_alto"] = y.notna() & (y > umbral_alto)
    oc["alerta_horas_altas"] = oc["totalHoursWorked"] > cfg["horas_maximas_plausibles"]
    oc["alerta_dane_extremo"] = y.notna() & oc["impaes"].notna()
    oc["alerta_extremo"] = oc["alerta_ingreso_bajo"] | oc["alerta_ingreso_alto"] | oc["alerta_horas_altas"] | oc["alerta_dane_extremo"]
    # oficio_f: códigos con pocas observaciones en la muestra principal -> "Otros"
    conteo = oc.loc[oc["muestra_principal"] & oc["entrenamiento"], "oficio"].value_counts()
    raros = set(conteo[conteo < cfg["min_obs_oficio"]].index)
    niveles = sorted(f"{int(c):02d}" for c in conteo.index if c not in raros) + ["Otros"]
    of = oc["oficio"].apply(lambda c: "Otros" if c in raros else f"{int(c):02d}")
    oc["oficio_f"] = pd.Categorical(of.where(of.isin(niveles), "Otros"), categories=niveles)
    oficios = pd.DataFrame({"oficio": conteo.index.astype(int), "n_entrenamiento": conteo.values}).sort_values("oficio")
    oficios["agrupado_en_otros"] = oficios["oficio"].isin(raros)

    orden = ["id_persona", "directorio", "secuencia_p", "orden", "chunk", "muestra_ps3", "entrenamiento", "mes", "mes_f", "fex_c",
             "muestra_principal", "motivo_exclusion",
             "y_total_m", "log_y", "y_total_m_ha", "y_ingLab_m", "y_gananciaIndep_m", "y_salary_m", "impa", "impaes", "dane_faltante",
             "age", "sex", "female", "jefe_hogar", "p6050", "parentesco_f", "estrato1", "estrato_f",
             "maxEducLevel", "educ_f", "terciaria", "anios_educ", "p6210", "p6210s1",
             "relab", "relab_f", "oficio", "oficio_f", "oficio_grupo", "sizeFirm", "sizeFirm_f", "microEmpresa", "cuentaPropia",
             "formal", "cotPension", "cotiza_pension", "regSalud", "regSalud_f", "p6426", "antiguedad_anios", "totalHoursWorked",
             "hoursWorkUsual", "horas_segundo_empleo", "segundo_empleo", "quiere_mas_horas",
             "alerta_ingreso_bajo", "alerta_ingreso_alto", "alerta_horas_altas", "alerta_dane_extremo", "alerta_extremo"]
    oc = oc[orden]
    muestra = oc[oc["muestra_principal"]].drop(columns=["muestra_principal", "motivo_exclusion"]).copy()
    for c in ["educ_f", "relab_f", "oficio_f", "oficio_grupo", "sizeFirm_f", "estrato_f", "mes_f", "parentesco_f", "regSalud_f"]:
        muestra[c] = muestra[c].cat.remove_unused_categories()
    embudo = pd.DataFrame({"paso": [1, 2, 3, 4], "descripcion": ["Base tipada (todas las personas)", "Ocupados (ocu == 1)",
                           f"Ocupados de {cfg['edad_minima']}+ (base ampliada)", "Con ingreso laboral positivo observado (muestra principal)"],
                           "n_personas": [n_base, n_ocu, len(oc), len(muestra)]})
    embudo["n_excluidas"] = embudo["n_personas"].shift(1) - embudo["n_personas"]
    embudo["n_excluidas"] = embudo["n_excluidas"].astype("Int64")
    exclusiones = (oc[~oc["muestra_principal"]].groupby(["motivo_exclusion", "relab_f"], observed=True).size().rename("n").reset_index())
    alertas = muestra.groupby("muestra_ps3")[["alerta_ingreso_bajo", "alerta_ingreso_alto", "alerta_horas_altas", "alerta_dane_extremo", "alerta_extremo"]].sum()
    alertas.insert(0, "n", muestra.groupby("muestra_ps3").size())
    return dict(ocupados18=oc, muestra=muestra, embudo=embudo, exclusiones=exclusiones, alertas=alertas, oficios=oficios,
                diccionario=diccionario_variables(), umbrales=dict(hora_bajo=umbral_hora_bajo, mensual_alto=umbral_alto))


def diccionario_variables() -> pd.DataFrame:
    filas = [
        ("id_persona", "Llave única de persona: directorio-secuencia_p-orden", "construida"),
        ("directorio", "Llave de vivienda (GEIH)", "original"), ("secuencia_p", "Llave de hogar", "original"), ("orden", "Llave de persona", "original"),
        ("chunk", "Bloque del sitio (1-10); sigue el calendario de la encuesta", "obtención"),
        ("muestra_ps3", "entrenamiento (bloques 1-7) o validacion (8-10)", "obtención"), ("entrenamiento", "True si muestra_ps3 == entrenamiento", "construida"),
        ("mes", "Mes de la entrevista", "original"), ("mes_f", "mes como categórica", "construida"), ("fex_c", "Factor de expansión anualizado", "original"),
        ("muestra_principal", "True si entra a la muestra de análisis", "construida"), ("motivo_exclusion", "Por qué no entra; NA si entra", "construida"),
        ("y_total_m", "Ingreso laboral mensual nominal 2018 (asalariado + independiente)", "original"), ("log_y", "log(y_total_m): variable dependiente", "construida"),
        ("y_total_m_ha", "Ingreso por hora = y_total_m / (totalHoursWorked x 30/7)", "original"), ("y_ingLab_m", "Componente asalariado", "original"),
        ("y_gananciaIndep_m", "Componente independiente (= p6750 / p6760)", "original"), ("y_salary_m", "Salario ocupación principal (= p6500; 0 -> NA)", "original"),
        ("impa", "Ingreso primera actividad DANE antes de imputación (referencia)", "original"), ("impaes", "Ingreso imputado por DANE (faltantes/extremos)", "original"),
        ("dane_faltante", "1 si DANE clasificó el ingreso como faltante (cclasnr2 == 1)", "construida"),
        ("age", "Edad en años", "original"), ("sex", "1 hombre, 0 mujer", "original"), ("female", "1 mujer (= 1 - sex)", "construida"),
        ("jefe_hogar", "1 si jefe/a del hogar (p6050 == 1)", "construida"), ("p6050", "Parentesco con el jefe (código)", "original"),
        ("parentesco_f", "Parentesco como categórica", "construida"), ("estrato1", "Estrato de la vivienda (1-6)", "original"), ("estrato_f", "estrato1 como categórica", "construida"),
        ("maxEducLevel", "Máximo nivel educativo (1-7)", "original"), ("educ_f", "maxEducLevel con etiquetas", "construida"),
        ("terciaria", "1 si educación terciaria (maxEducLevel == 7); reemplaza a college", "construida"),
        ("anios_educ", "Años de educación aproximados (superior = 11 + años aprobados)", "construida"), ("p6210", "Nivel educativo (pregunta original)", "original"),
        ("p6210s1", "Último grado aprobado", "original"), ("relab", "Tipo de ocupación (1-9)", "original"), ("relab_f", "relab con etiquetas; 6-7 sin remuneración, 8-9 otro", "construida"),
        ("oficio", "Ocupación CNO-70 a dos dígitos", "original"), ("oficio_f", "oficio como categórica; raros agrupados en Otros", "construida"),
        ("oficio_grupo", "Grupo mayor de ocupación (7)", "construida"), ("sizeFirm", "Tamaño de la empresa (1-5)", "original"), ("sizeFirm_f", "sizeFirm con etiquetas", "construida"),
        ("microEmpresa", "1 si 5 trabajadores o menos", "original"), ("cuentaPropia", "1 si cuenta propia", "original"), ("formal", "1 si formal (seguridad social)", "original"),
        ("cotPension", "1 cotiza, 2 no, 3 pensionado", "original"), ("cotiza_pension", "1 si cotiza actualmente", "construida"),
        ("regSalud", "1 contributivo, 2 especial, 3 subsidiado; NA frecuente", "original"), ("regSalud_f", "regSalud con etiquetas y categoría 'No responde'", "construida"),
        ("p6426", "Meses en la empresa actual", "original"), ("antiguedad_anios", "p6426 / 12", "construida"),
        ("totalHoursWorked", "Horas semanales: usuales del principal + efectivas del segundo empleo", "original"), ("hoursWorkUsual", "Horas usuales ocupación principal", "original"),
        ("horas_segundo_empleo", "Horas en el segundo empleo (0 si no tiene)", "construida"), ("segundo_empleo", "1 si tenía otro trabajo (p7040 == 1)", "construida"),
        ("quiere_mas_horas", "1 si quiere trabajar más horas (p7090 == 1): subempleo visible", "construida"),
        ("alerta_ingreso_bajo", "Ingreso por hora < fracción del mínimo por hora", "construida"), ("alerta_ingreso_alto", "Ingreso mensual > múltiplo del SMMLV", "construida"),
        ("alerta_horas_altas", "Horas > máximo plausible", "construida"), ("alerta_dane_extremo", "DANE reemplazó el ingreso observado por imputación", "construida"),
        ("alerta_extremo", "Unión de las alertas", "construida"),
    ]
    return pd.DataFrame(filas, columns=["variable", "descripcion", "origen"])
