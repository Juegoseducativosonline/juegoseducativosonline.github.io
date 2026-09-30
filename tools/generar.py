#!/usr/bin/env python3
"""Genera las páginas del sitio a partir de la carpeta contenido/.

    python tools/generar.py              # genera o actualiza los archivos
    python tools/generar.py --comprobar  # no escribe nada; falla si algo está desactualizado

Qué produce:
  * index.html, 404.html, sitemap.xml y assets/materias.css
  * <materia>/index.html para cada materia del catálogo
  * una página por cada juego de tipo "quiz"
  * en las páginas de juegos "interactivos", que están hechas a mano, reescribe
    solo los bloques delimitados por <!-- generado:NOMBRE --> y
    <!-- /generado:NOMBRE -->, y la clase del <body>.

Solo usa la biblioteca estándar de Python (3.8 o superior).
"""

import argparse
import hashlib
import html
import json
import random
import unicodedata
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import imprimibles  # tools/imprimibles.py: actividades de Transición

RAIZ = Path(__file__).resolve().parent.parent
CONTENIDO = RAIZ / 'contenido'

URL_SITIO = 'https://juegoseducativosonline.github.io'
NOMBRE_SITIO = 'Juegos Educativos Online'
# Grados del sistema colombiano: 0 = Transición (preescolar), 1.º a 5.º primaria,
# 6.º a 9.º básica secundaria, 10.º y 11.º media. La edad de referencia es la del
# inicio de cada grado (Transición, 5 años).
PRIMER_GRADO_SECUNDARIA = 6
EDAD_EN_TRANSICION = 5
GRADOS = [
    # (número, slug de la URL, etiqueta corta, cómo se nombra en una frase)
    (0, 'transicion', 'Transición', 'transición (preescolar)'),
    (1, 'primero', '1.º', 'primero de primaria'),
    (2, 'segundo', '2.º', 'segundo de primaria'),
    (3, 'tercero', '3.º', 'tercero de primaria'),
    (4, 'cuarto', '4.º', 'cuarto de primaria'),
    (5, 'quinto', '5.º', 'quinto de primaria'),
    (6, 'sexto', '6.º', 'sexto grado'),
    (7, 'septimo', '7.º', 'séptimo grado'),
    (8, 'octavo', '8.º', 'octavo grado'),
    (9, 'noveno', '9.º', 'noveno grado'),
    (10, 'decimo', '10.º', 'décimo grado'),
    (11, 'once', '11.º', 'grado once'),
]
GRADO = {g[0]: g for g in GRADOS}
# Franjas de edad para las familias: (edad mínima, edad máxima), en años.
EDADES = [(5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16)]
FUENTES = 'https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap'
MAX_RELACIONADOS = 3
COLOR_MARCA = '#3b5bdb'
RUTA_DESCARGAS = 'descargar/index.html'
# Carpetas del sitio que no pueden usarse como id de materia.
IDS_RESERVADOS = {'assets', 'contenido', 'tools', 'descargar', 'secundaria',
                  'docentes', 'familias', 'grados', 'edades'}
RUTA_DOCENTES = 'docentes/index.html'
RUTA_FAMILIAS = 'familias/index.html'
RUTA_CURRICULO = 'docentes/curriculo/index.html'
# Los PDF los produce tools/pdf.py imprimiendo las fichas y los packs con Chrome.
CARPETA_PDF = 'pdf'
RUTA_SECUNDARIA = 'secundaria/index.html'

# Juegos cuyos datos viven en contenido/*.json: hoja de estilos, script y función
# de arranque de cada motor.
MOTORES = {
    'quiz': (('quiz.css',), 'quiz.js', 'cargarQuiz'),
    'parejas': (('quiz.css', 'interactivos.css'), 'interactivos.js', 'cargarJuego'),
    'ordenar': (('quiz.css', 'interactivos.css'), 'interactivos.js', 'cargarJuego'),
}
MIN_PAREJAS = 3
MIN_ELEMENTOS_ORDENAR = 3

# Contraste mínimo WCAG AA para texto normal.
CONTRASTE_MINIMO = 4.5

MARCA_GENERADO = 'Generado por tools/generar.py'
AVISO_HTML = '<!-- %s a partir de contenido/. No lo edites a mano. -->' % MARCA_GENERADO
BLOQUES_INTERACTIVOS = ('comun', 'navegacion', 'pie')

PATRON_ID = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
PATRON_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')


class ErrorContenido(Exception):
    """Error en los datos de contenido/. El mensaje va dirigido a quien los edita."""


# --- Modelo -----------------------------------------------------------------

@dataclass
class Juego:
    tipo: str            # 'quiz' o 'interactivo'
    ruta: str            # p. ej. 'quimica/estados-materia.html'
    titulo: str
    descripcion: str
    icono: str
    nivel: str           # 'Primaria' o 'Secundaria': se deduce de los grados
    detalle: str         # '8 preguntas' o 'Interactivo'
    datos: Optional[dict] = None   # solo en los quiz: lo que se incrusta en la página
    titulo_seo: Optional[str] = None
    descripcion_seo: Optional[str] = None
    grados: List[int] = field(default_factory=list)
    curriculo: Optional[dict] = None   # objetivo, competencia, DBA y estándares (contenido/curriculo.json)
    materia: 'Materia' = field(default=None, repr=False)
    tema: 'Tema' = field(default=None, repr=False)


@dataclass
class Tema:
    id: str
    nombre: str
    descripcion: str
    juegos: List[Juego]


@dataclass
class Materia:
    id: str
    nombre: str
    icono: str
    color: str
    descripcion: str
    temas: List[Tema]
    titulo_seo: Optional[str] = None
    descripcion_seo: Optional[str] = None

    @property
    def juegos(self):
        return [j for t in self.temas for j in t.juegos]


# --- Utilidades -------------------------------------------------------------

def esc(texto):
    return html.escape(str(texto), quote=True)


def rel(ruta):
    return ruta.relative_to(RAIZ).as_posix()


def plural(n, singular, plural_):
    return '%d %s' % (n, singular if n == 1 else plural_)


def indentar(texto, sangria):
    return '\n'.join((sangria + linea) if linea else linea for linea in texto.split('\n'))


def url_de(ruta):
    """URL pública de un archivo del sitio: 'quimica/index.html' → '/quimica/'."""
    if ruta == 'index.html':
        return '/'
    if ruta.endswith('/index.html'):
        return '/' + ruta[:-len('index.html')]
    return '/' + ruta


def leer_json(ruta):
    try:
        return json.loads(ruta.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise ErrorContenido('No existe el archivo %s.' % rel(ruta))
    except json.JSONDecodeError as e:
        raise ErrorContenido('%s: JSON inválido en la línea %d, columna %d: %s.'
                             % (rel(ruta), e.lineno, e.colno, e.msg))


def texto_opcional(obj, clave, donde):
    if clave not in obj:
        return None
    return texto_obligatorio(obj, clave, donde)


def texto_obligatorio(obj, clave, donde):
    valor = obj.get(clave) if isinstance(obj, dict) else None
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorContenido('%s: falta "%s" o está vacío.' % (donde, clave))
    return valor.strip()


def lista_obligatoria(obj, clave, donde):
    valor = obj.get(clave)
    if not isinstance(valor, list) or not valor:
        raise ErrorContenido('%s: "%s" debe ser una lista con al menos un elemento.' % (donde, clave))
    return valor


def id_valido(obj, donde):
    valor = texto_obligatorio(obj, 'id', donde)
    if not PATRON_ID.match(valor):
        raise ErrorContenido('%s: el id "%s" solo puede tener minúsculas sin tilde, números y guiones.'
                             % (donde, valor))
    return valor


def grados_validos(obj, donde):
    grados = obj.get('grados') if isinstance(obj, dict) else None
    validos = isinstance(grados, list) and grados and all(
        isinstance(g, int) and not isinstance(g, bool) and g in GRADO for g in grados)
    # Se exige una serie seguida (1, 2, 3) para poder mostrarla como «1.º–3.º».
    if not validos or grados != list(range(grados[0], grados[0] + len(grados))):
        raise ErrorContenido('%s: "grados" debe ser una lista de grados seguidos entre 0 (Transición) y 11, '
                             'p. ej. [1, 2, 3].' % donde)
    return grados


def etiqueta_grados(grados):
    if len(grados) == 1:
        return GRADO[grados[0]][2]
    return '%s–%s' % (GRADO[grados[0]][2], GRADO[grados[-1]][2])


def edades_de(grados):
    return grados[0] + EDAD_EN_TRANSICION, grados[-1] + EDAD_EN_TRANSICION


def etiqueta_edades(grados):
    desde, hasta = edades_de(grados)
    return '%d años' % desde if desde == hasta else '%d–%d años' % (desde, hasta)


def juegos_de_edad(juegos, franja):
    desde, hasta = franja
    return [j for j in juegos if edades_de(j.grados)[0] <= hasta and edades_de(j.grados)[1] >= desde]


def slug_edad(franja):
    return 'de-%d-a-%d-anos' % franja


# --- Color ------------------------------------------------------------------

def hex_a_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def mezclar(color, con, proporcion):
    """Mezcla `color` con `con`; `proporcion` es cuánto pesa `con` (0 a 1)."""
    a, b = hex_a_rgb(color), hex_a_rgb(con)
    return '#%02x%02x%02x' % tuple(round(x + (y - x) * proporcion) for x, y in zip(a, b))


def luminancia(color):
    def canal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(c) for c in hex_a_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b):
    claro, oscuro = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


def paleta(color):
    return {
        'base': color.lower(),
        'oscuro': mezclar(color, '#000000', 0.25),
        'suave': mezclar(color, '#ffffff', 0.90),
        'borde': mezclar(color, '#ffffff', 0.65),
    }


# --- Carga y validación del contenido -----------------------------------------

def cargar_quiz(ruta_json, donde_catalogo):
    datos = leer_json(ruta_json)
    donde = rel(ruta_json)
    if not isinstance(datos, dict):
        raise ErrorContenido('%s: debe ser un objeto JSON.' % donde)

    mezclar_preguntas = datos.get('mezclarPreguntas', True)
    if not isinstance(mezclar_preguntas, bool):
        raise ErrorContenido('%s: "mezclarPreguntas" debe ser true o false.' % donde)

    leer_en_voz_alta = datos.get('leerEnVozAlta', False)
    if not isinstance(leer_en_voz_alta, bool):
        raise ErrorContenido('%s: "leerEnVozAlta" debe ser true o false.' % donde)

    pasajes = datos.get('pasajes', {})
    if not isinstance(pasajes, dict):
        raise ErrorContenido('%s: "pasajes" debe ser un objeto.' % donde)
    for clave, pasaje in pasajes.items():
        d = '%s, pasaje "%s"' % (donde, clave)
        texto_obligatorio(pasaje, 'titulo', d)
        parrafos = lista_obligatoria(pasaje, 'parrafos', d)
        if not all(isinstance(p, str) and p.strip() for p in parrafos):
            raise ErrorContenido('%s: todos los párrafos deben ser texto no vacío.' % d)

    preguntas = []
    enunciados = set()
    pasajes_usados = set()
    for n, p in enumerate(lista_obligatoria(datos, 'preguntas', donde), 1):
        d = '%s, pregunta %d' % (donde, n)
        enunciado = texto_obligatorio(p, 'enunciado', d)
        if enunciado in enunciados:
            raise ErrorContenido('%s: el enunciado está repetido.' % d)
        enunciados.add(enunciado)

        opciones = lista_obligatoria(p, 'opciones', d)
        if len(opciones) < 2:
            raise ErrorContenido('%s: necesita al menos 2 opciones.' % d)
        if not all(isinstance(o, str) and o.strip() for o in opciones):
            raise ErrorContenido('%s: todas las opciones deben ser texto no vacío.' % d)
        if len(set(opciones)) != len(opciones):
            raise ErrorContenido('%s: hay opciones repetidas.' % d)

        correcta = p.get('correcta')
        # bool es un int en Python: sin esta comprobación, true pasaría por 1.
        if isinstance(correcta, bool) or not isinstance(correcta, int) or not 0 <= correcta < len(opciones):
            raise ErrorContenido('%s: "correcta" debe ser el índice (desde 0) de una de sus %d opciones.'
                                 % (d, len(opciones)))

        limpia = {'enunciado': enunciado, 'opciones': opciones, 'correcta': correcta}
        if 'explicacion' in p:
            limpia['explicacion'] = texto_obligatorio(p, 'explicacion', d)
        if 'pasaje' in p:
            clave = texto_obligatorio(p, 'pasaje', d)
            if clave not in pasajes:
                raise ErrorContenido('%s: el pasaje "%s" no está definido en "pasajes".' % (d, clave))
            pasajes_usados.add(clave)
            limpia['pasaje'] = clave
        figura = figura_de(limpia['enunciado'])
        if figura:
            limpia['figura'] = figura
        else:
            emojis, resto = separar_ilustracion(limpia['enunciado'])
            if not emojis and ilustrar(resto):
                limpia['dibujo'] = ilustrar(resto)
        preguntas.append(limpia)

    sobrantes = set(pasajes) - pasajes_usados
    if sobrantes:
        raise ErrorContenido('%s: estos pasajes no los usa ninguna pregunta: %s.'
                             % (donde, ', '.join(sorted(sobrantes))))

    ruta_html = ruta_json.relative_to(CONTENIDO).with_suffix('.html').as_posix()
    return Juego(
        tipo='quiz',
        ruta=ruta_html,
        titulo=texto_obligatorio(datos, 'titulo', donde),
        descripcion=texto_obligatorio(datos, 'descripcion', donde),
        icono=texto_obligatorio(datos, 'icono', donde),
        nivel='',
        detalle=plural(len(preguntas), 'pregunta', 'preguntas'),
        datos={'mezclarPreguntas': mezclar_preguntas, 'leerEnVozAlta': leer_en_voz_alta,
               'pasajes': pasajes, 'preguntas': preguntas},
        titulo_seo=texto_opcional(datos, 'tituloSeo', donde),
        descripcion_seo=texto_opcional(datos, 'descripcionSeo', donde),
    )


def meta_de_juego(datos, donde):
    """Campos comunes a todos los juegos con datos."""
    if not isinstance(datos, dict):
        raise ErrorContenido('%s: debe ser un objeto JSON.' % donde)
    return dict(
        titulo=texto_obligatorio(datos, 'titulo', donde),
        descripcion=texto_obligatorio(datos, 'descripcion', donde),
        icono=texto_obligatorio(datos, 'icono', donde),
        nivel='',
        titulo_seo=texto_opcional(datos, 'tituloSeo', donde),
        descripcion_seo=texto_opcional(datos, 'descripcionSeo', donde),
    )


def lista_de_textos(valores, donde, que, minimo):
    if not isinstance(valores, list) or len(valores) < minimo:
        raise ErrorContenido('%s: "%s" debe tener al menos %d elementos.' % (donde, que, minimo))
    if not all(isinstance(x, str) and x.strip() for x in valores):
        raise ErrorContenido('%s: todos los elementos de "%s" deben ser texto no vacío.' % (donde, que))
    if len(set(valores)) != len(valores):
        raise ErrorContenido('%s: hay elementos repetidos en "%s".' % (donde, que))
    return valores


def cargar_parejas(ruta_json):
    datos = leer_json(ruta_json)
    donde = rel(ruta_json)
    meta = meta_de_juego(datos, donde)
    pares = lista_obligatoria(datos, 'pares', donde)
    for n, par in enumerate(pares, 1):
        d = '%s, pareja %d' % (donde, n)
        texto_obligatorio(par, 'a', d)
        texto_obligatorio(par, 'b', d)
    # Cada lado debe ser único: si dos elementos tuvieran la misma pareja, el
    # juego no podría saber cuál es la correcta.
    lista_de_textos([x['a'] for x in pares], donde, 'pares (columna a)', MIN_PAREJAS)
    lista_de_textos([x['b'] for x in pares], donde, 'pares (columna b)', MIN_PAREJAS)
    por_ronda = datos.get('paresPorRonda', 6)
    if isinstance(por_ronda, bool) or not isinstance(por_ronda, int) or por_ronda < MIN_PAREJAS:
        raise ErrorContenido('%s: "paresPorRonda" debe ser un número entero de %d o más.' % (donde, MIN_PAREJAS))
    return Juego(
        tipo='parejas', ruta=ruta_json.relative_to(CONTENIDO).with_suffix('.html').as_posix(),
        detalle=plural(len(pares), 'pareja', 'parejas'),
        datos={'tipo': 'parejas', 'pares': [{'a': x['a'], 'b': x['b']} for x in pares],
               'paresPorRonda': por_ronda,
               'etiquetaA': texto_opcional(datos, 'etiquetaA', donde) or 'Relaciona',
               'etiquetaB': texto_opcional(datos, 'etiquetaB', donde) or 'con su pareja'},
        **meta)


def cargar_ordenar(ruta_json):
    datos = leer_json(ruta_json)
    donde = rel(ruta_json)
    meta = meta_de_juego(datos, donde)
    rondas = []
    for n, r in enumerate(lista_obligatoria(datos, 'rondas', donde), 1):
        d = '%s, ronda %d' % (donde, n)
        ronda = {'instruccion': texto_obligatorio(r, 'instruccion', d),
                 'elementos': lista_de_textos(r.get('elementos'), d, 'elementos', MIN_ELEMENTOS_ORDENAR)}
        explicacion = texto_opcional(r, 'explicacion', d)
        if explicacion:
            ronda['explicacion'] = explicacion
        rondas.append(ronda)
    return Juego(
        tipo='ordenar', ruta=ruta_json.relative_to(CONTENIDO).with_suffix('.html').as_posix(),
        detalle=plural(len(rondas), 'ronda', 'rondas'),
        datos={'tipo': 'ordenar', 'rondas': rondas},
        **meta)


def cargar_imprimible(ruta_json):
    """Ficha para imprimir de Transición (trazar, colorear, encerrar...): no tiene
    juego en pantalla; su página muestra las actividades y los botones para imprimir."""
    datos = leer_json(ruta_json)
    donde = rel(ruta_json)
    meta = meta_de_juego(datos, donde)
    actividades = lista_obligatoria(datos, 'actividades', donde)
    try:
        imprimibles.renderizar(actividades, donde)   # valida los datos antes de seguir
    except imprimibles.ErrorActividad as e:
        raise ErrorContenido(str(e))
    return Juego(
        tipo='imprimible', ruta=ruta_json.relative_to(CONTENIDO).with_suffix('.html').as_posix(),
        detalle='Para imprimir · %s' % plural(len(actividades), 'actividad', 'actividades'),
        datos={'actividades': actividades}, **meta)


def tiene_ficha(juego):
    return juego.tipo in MOTORES or juego.tipo == 'imprimible'


def cargar_interactivo(crudo, donde):
    ruta = texto_obligatorio(crudo, 'pagina', donde)
    archivo = RAIZ / ruta
    if not archivo.is_file():
        raise ErrorContenido('%s: no existe la página %s.' % (donde, ruta))
    contenido = archivo.read_text(encoding='utf-8')
    for bloque in BLOQUES_INTERACTIVOS:
        if contenido.count('<!-- generado:%s -->' % bloque) != 1 or \
                contenido.count('<!-- /generado:%s -->' % bloque) != 1:
            raise ErrorContenido('%s: %s debe tener una vez los marcadores <!-- generado:%s --> y '
                                 '<!-- /generado:%s -->.' % (donde, ruta, bloque, bloque))
    return Juego(
        tipo='interactivo',
        ruta=ruta,
        titulo=texto_obligatorio(crudo, 'titulo', donde),
        descripcion=texto_obligatorio(crudo, 'descripcion', donde),
        icono=texto_obligatorio(crudo, 'icono', donde),
        nivel='',
        detalle='Interactivo',
    )


def cargar_catalogo():
    catalogo = leer_json(CONTENIDO / 'catalogo.json')
    materias = []
    rutas = {}

    for i, cruda in enumerate(lista_obligatoria(catalogo, 'materias', 'catalogo.json'), 1):
        mid = id_valido(cruda, 'catalogo.json, materia %d' % i)
        donde = 'catalogo.json, materia "%s"' % mid
        if mid in IDS_RESERVADOS:
            raise ErrorContenido('%s: "%s" está reservado; usa otro id.' % (donde, mid))
        if any(m.id == mid for m in materias):
            raise ErrorContenido('%s: el id está repetido.' % donde)

        color = texto_obligatorio(cruda, 'color', donde)
        if not PATRON_COLOR.match(color):
            raise ErrorContenido('%s: el color debe tener la forma #rrggbb.' % donde)
        colores = paleta(color)
        # El color de la materia es fondo de texto blanco (cabeceras, botones) y
        # su tono oscuro es texto sobre el suave (etiquetas): ambos deben leerse bien.
        for fondo, texto, uso in ((colores['base'], '#ffffff', 'texto blanco sobre el color'),
                                  (colores['suave'], colores['oscuro'], 'etiquetas')):
            if contraste(fondo, texto) < CONTRASTE_MINIMO:
                raise ErrorContenido('%s: el color %s tiene poco contraste para %s (%.1f:1, mínimo %.1f:1). '
                                     'Usa un tono más oscuro.'
                                     % (donde, color, uso, contraste(fondo, texto), CONTRASTE_MINIMO))

        materia = Materia(mid, texto_obligatorio(cruda, 'nombre', donde), texto_obligatorio(cruda, 'icono', donde),
                          colores['base'], texto_obligatorio(cruda, 'descripcion', donde), [],
                          texto_opcional(cruda, 'tituloSeo', donde), texto_opcional(cruda, 'descripcionSeo', donde))

        for j, tema_crudo in enumerate(lista_obligatoria(cruda, 'temas', donde), 1):
            tid = id_valido(tema_crudo, '%s, tema %d' % (donde, j))
            donde_tema = '%s, tema "%s"' % (donde, tid)
            if any(t.id == tid for t in materia.temas):
                raise ErrorContenido('%s: el id está repetido.' % donde_tema)
            tema = Tema(tid, texto_obligatorio(tema_crudo, 'nombre', donde_tema),
                        texto_obligatorio(tema_crudo, 'descripcion', donde_tema), [])

            for k, juego_crudo in enumerate(lista_obligatoria(tema_crudo, 'juegos', donde_tema), 1):
                donde_juego = '%s, juego %d' % (donde_tema, k)
                tipo = juego_crudo.get('tipo') if isinstance(juego_crudo, dict) else None
                if tipo in MOTORES:
                    archivo = texto_obligatorio(juego_crudo, 'datos', donde_juego)
                    if not archivo.endswith('.json'):
                        raise ErrorContenido('%s: "datos" debe apuntar a un archivo .json.' % donde_juego)
                    cargador = {'quiz': lambda r: cargar_quiz(r, donde_juego),
                                'parejas': cargar_parejas, 'ordenar': cargar_ordenar}[tipo]
                    juego = cargador(CONTENIDO / archivo)
                elif tipo == 'imprimible':
                    juego = cargar_imprimible(CONTENIDO / texto_obligatorio(juego_crudo, 'datos', donde_juego))
                elif tipo == 'interactivo':
                    juego = cargar_interactivo(juego_crudo, donde_juego)
                else:
                    raise ErrorContenido('%s: tipo de juego desconocido %r; usa %s, "imprimible" o "interactivo".'
                                         % (donde_juego, tipo, ', '.join('"%s"' % t for t in MOTORES)))

                # Cada juego vive en la carpeta de su materia; así la URL dice a qué materia pertenece.
                if not juego.ruta.startswith(mid + '/') or juego.ruta == mid + '/index.html':
                    raise ErrorContenido('%s: %s debe estar dentro de la carpeta %s/ y no llamarse index.html.'
                                         % (donde_juego, juego.ruta, mid))
                if juego.ruta in rutas:
                    raise ErrorContenido('%s: %s ya lo usa otro juego (%s).'
                                         % (donde_juego, juego.ruta, rutas[juego.ruta]))
                rutas[juego.ruta] = donde_juego

                juego.grados = grados_validos(juego_crudo, donde_juego)
                juego.nivel = 'Secundaria' if juego.grados[0] >= PRIMER_GRADO_SECUNDARIA else 'Primaria'
                juego.materia, juego.tema = materia, tema
                tema.juegos.append(juego)
            materia.temas.append(tema)
        materias.append(materia)

    asignar_curriculo(materias)
    return materias


def asignar_curriculo(materias):
    """Une a cada juego su alineación curricular. Todo juego debe tenerla, con los
    mismos grados que el catálogo: así la página nunca muestra un DBA de otro grado."""
    datos = leer_json(CONTENIDO / 'curriculo.json')
    fuentes, alineacion = datos.get('fuentes', {}), datos.get('juegos', {})
    pedagogia = leer_json(CONTENIDO / 'pedagogia.json')
    juegos = {}
    for m in materias:
        for j in m.juegos:
            clave = j.ruta if j.tipo == 'interactivo' else j.ruta[:-len('.html')] + '.json'
            juegos[clave] = j
    for clave, j in juegos.items():
        c = alineacion.get(clave)
        donde = 'curriculo.json, juego "%s"' % clave
        if c is None:
            raise ErrorContenido('%s: falta su alineación curricular (objetivo, DBA y estándares).' % donde)
        if c.get('grados') != j.grados:
            raise ErrorContenido('%s: los grados %s no coinciden con los del catálogo %s.' % (donde, c.get('grados'), j.grados))
        texto_obligatorio(c, 'objetivo', donde)
        texto_obligatorio(c, 'competencia', donde)
        for ref in c.get('dba', []) + c.get('estandares', []):
            if ref.get('fuente') not in fuentes or not ref.get('texto'):
                raise ErrorContenido('%s: una referencia no tiene fuente conocida o texto.' % donde)
        if not c.get('dba') and not c.get('estandares'):
            raise ErrorContenido('%s: necesita al menos un DBA o un estándar.' % donde)
        # Coherencia: un juego solo cita DBA de sus propios grados.
        for ref in c.get('dba', []):
            if ref.get('grado') not in j.grados:
                raise ErrorContenido('%s: cita un DBA de grado %s, fuera de sus grados %s.'
                                     % (donde, ref.get('grado'), j.grados))
        p = pedagogia.get(clave)
        donde_p = 'pedagogia.json, juego "%s"' % clave
        if not isinstance(p, dict):
            raise ErrorContenido('%s: faltan los indicadores y la situación problema.' % donde_p)
        indicadores = lista_de_textos(p.get('indicadores'), donde_p, 'indicadores', 2)
        sit = p.get('situacion')
        if not isinstance(sit, dict):
            raise ErrorContenido('%s: falta "situacion".' % donde_p)
        situacion = {'ilustracion': texto_obligatorio(sit, 'ilustracion', donde_p),
                     'texto': texto_obligatorio(sit, 'texto', donde_p),
                     'preguntas': lista_de_textos(sit.get('preguntas'), donde_p, 'preguntas', 1)}
        j.curriculo = dict(c, fuentes_doc=fuentes, indicadores=indicadores, situacion=situacion)
    sobran = set(alineacion) - set(juegos)
    if sobran:
        raise ErrorContenido('curriculo.json tiene juegos que no están en el catálogo: %s.' % ', '.join(sorted(sobran)))


# --- Bloques compartidos -----------------------------------------------------

class Versiones:
    """Sufijo ?v=<hash> para los recursos, para que el navegador no use una
    copia vieja de un CSS o JS después de publicar un cambio."""

    def __init__(self, contenidos):
        self._hashes = {nombre: hashlib.sha256(datos.encode('utf-8')).hexdigest()[:10]
                        for nombre, datos in contenidos.items()}

    def url(self, nombre):
        return '/assets/%s?v=%s' % (nombre, self._hashes[nombre])


def bloque(nombre, contenido):
    return '<!-- generado:%s -->\n%s\n<!-- /generado:%s -->' % (nombre, contenido, nombre)


def bloque_comun(v):
    return '\n'.join([
        '<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml" />',
        '<link rel="apple-touch-icon" href="/assets/icono-180.png" />',
        '<link rel="manifest" href="/manifest.webmanifest" />',
        '<meta name="theme-color" content="%s" />' % COLOR_MARCA,
        '<link rel="preconnect" href="https://fonts.googleapis.com" />',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />',
        '<link rel="stylesheet" href="%s" />' % esc(FUENTES),
        '<link rel="stylesheet" href="%s" />' % v.url('site.css'),
        '<link rel="stylesheet" href="%s" />' % v.url('materias.css'),
    ])


def migas_html(migas):
    """migas: lista de (texto, url); la última, sin url, es la página actual."""
    items = []
    for texto, url in migas:
        if url:
            items.append('    <li><a href="%s">%s</a></li>' % (esc(url), esc(texto)))
        else:
            items.append('    <li aria-current="page">%s</li>' % esc(texto))
    return '<nav class="migas" aria-label="Ruta de navegación">\n  <ol>\n%s\n  </ol>\n</nav>' % '\n'.join(items)


def bloque_navegacion(materias, actual=None, migas=None, docente=None):
    enlaces = []
    for m in materias:
        actual_attr = ' aria-current="page"' if m is actual else ''
        enlaces.append(
            '        <li><a class="materia-%s" href="/%s/"%s>'
            '<span class="menu-icono" aria-hidden="true">%s</span>%s</a></li>'
            % (m.id, m.id, actual_attr, esc(m.icono), esc(m.nombre)))
    partes = ['''<a class="salto-contenido" href="#contenido">Saltar al contenido</a>
<header class="barra-sitio">
  <div class="barra-sitio-interior">
    <a class="marca" href="/"><span class="marca-logo" aria-hidden="true">🎮</span><span class="marca-texto">Juegos Educativos</span></a>
    <nav class="barra-enlaces" aria-label="Secciones">
      <a href="/docentes/"><span aria-hidden="true">🍎</span><span class="barra-texto">Docentes</span></a>
      <a href="/familias/"><span aria-hidden="true">🏠</span><span class="barra-texto">Familias</span></a>
    </nav>
    <details class="menu-materias">
      <summary>📚 Materias</summary>
      <ul class="menu-materias-lista">
%s
      </ul>
    </details>
  </div>
</header>''' % '\n'.join(enlaces)]
    if migas:
        partes.append(migas_html(migas))
    if docente:
        partes.append(docente)
    return '\n'.join(partes)


def tarjeta_juego(j):
    return '''<li class="tarjeta-juego materia-%s">
  <a href="%s">
    <span class="tarjeta-juego-cabeza">
      <span class="tarjeta-juego-icono" aria-hidden="true">%s</span>
      <span class="insignia">%s</span>
    </span>
    <h3>%s</h3>
    <span class="tarjeta-juego-desc">%s</span>
    <span class="tarjeta-juego-pie"><span>%s · %s</span><span class="tarjeta-juego-cta" aria-hidden="true">Jugar →</span></span>
  </a>
</li>''' % (j.materia.id, url_de(j.ruta), esc(j.icono), esc(etiqueta_grados(j.grados)), esc(j.titulo),
            esc(j.descripcion), esc(j.detalle), esc(etiqueta_edades(j.grados)))


def lista_tarjetas(juegos, clase='rejilla-juegos'):
    return '<ul class="%s">\n%s\n</ul>' % (clase, indentar('\n'.join(tarjeta_juego(j) for j in juegos), '  '))


def etiqueta_dba(ref):
    grado = 'Transición' if ref['grado'] == 0 else '%d.º' % ref['grado']
    return '%s · %s · DBA %s' % (ref['area'], grado, ref['numero'])


def etiqueta_estandar(ref, fuentes):
    sigla = {'G22': 'Guía 22', 'G30': 'Guía 30', 'D16': 'Documento 16'}.get(ref['fuente'])
    return '%s · %s%s' % (ref['area'], ref['grupo'], ' (%s)' % sigla if sigla else '')


def ruta_pack_grado(grado):
    return 'packs/grado-%s.html' % grado[1]


def ruta_pack_materia(materia):
    return 'packs/materia-%s.html' % materia.id


def pdf_de(ruta_html):
    """PDF que tools/pdf.py genera para una ficha o un pack."""
    if ruta_html.startswith('packs/'):
        return '%s/%s.pdf' % (CARPETA_PDF, ruta_html[len('packs/'):-len('.html')])
    return '%s/%s.pdf' % (CARPETA_PDF, ruta_html[:-len('-ficha.html')])


def peso_pdf(ruta_html):
    """Tamaño del PDF ya generado, para mostrarlo junto al enlace ('' si aún no existe)."""
    archivo = RAIZ / pdf_de(ruta_html)
    if not archivo.exists():
        return ''
    kb = archivo.stat().st_size / 1024
    return ' (%s)' % ('%d KB' % kb if kb < 1024 else ('%.1f MB' % (kb / 1024)).replace('.', ','))


def enlace_pdf(ruta_html, texto, clase='btn'):
    return '<a class="%s" href="/%s" download>%s%s</a>' % (clase, pdf_de(ruta_html), texto, esc(peso_pdf(ruta_html)))


def contenido_curriculo(juego):
    """Lineamientos primero (objetivo, DBA, estándares) y, después, las descargas."""
    c = juego.curriculo
    fuentes = c['fuentes_doc']
    partes = ['<p><strong>Objetivo de aprendizaje:</strong> %s</p>' % esc(c['objetivo']),
              '<p><strong>Competencia que se trabaja:</strong> %s</p>' % esc(c['competencia'])]
    if c['dba']:
        partes.append('<h3>Derechos Básicos de Aprendizaje (DBA)</h3>')
        partes.append('<ul class="lista-curriculo">')
        partes += ['  <li><span class="insignia">%s</span> «%s»</li>' % (esc(etiqueta_dba(r)), esc(r['texto']))
                   for r in c['dba']]
        partes.append('</ul>')
    if c['estandares']:
        partes.append('<h3>Estándares y orientaciones del MEN</h3>')
        partes.append('<ul class="lista-curriculo">')
        partes += ['  <li><span class="insignia">%s</span> «%s»</li>' % (esc(etiqueta_estandar(r, fuentes)), esc(r['texto']))
                   for r in c['estandares']]
        partes.append('</ul>')
    partes.append('<h3>Indicadores de desempeño</h3>')
    partes.append('<ul class="lista-curriculo">%s</ul>' % ''.join('<li>%s</li>' % esc(i) for i in c['indicadores']))
    partes.append(situacion_problema(juego))
    usadas = []
    for r in c['dba'] + c['estandares']:
        if r['fuente'] not in usadas:
            usadas.append(r['fuente'])
    partes.append('<p class="nota">Fuentes: %s. Textos citados literalmente. '
                  '<a href="/docentes/curriculo/">Ver la matriz curricular completa</a>.</p>'
                  % '; '.join('<a href="%s">%s</a>' % (esc(fuentes[f]['url']), esc(fuentes[f]['titulo'])) for f in usadas))

    descargas = []
    if tiene_ficha(juego):
        descargas.append(enlace_pdf(ruta_ficha(juego), '📄 Ficha en PDF'))
    descargas += [enlace_pdf(ruta_pack_grado(GRADO[g]), '📦 Pack de %s' % GRADO[g][2], 'btn btn-secundario')
                  for g in juego.grados]
    descargas.append(enlace_pdf(ruta_pack_materia(juego.materia), '📚 Pack de %s' % juego.materia.nombre,
                                'btn btn-secundario'))
    partes.append('<h3>Descargar para imprimir</h3>')
    partes.append('<div class="descargas">%s</div>' % ' '.join(descargas))
    return '\n'.join(partes)


def bloque_curriculo(juego, posicion='inferior'):
    """Dos versiones del mismo contenido:
    - 'superior': arriba del juego y abierta; solo se ve en la vista de docente
      (quien llega desde /docentes/ o una página de grado; lo decide site.js).
    - 'inferior': al final y plegada, para quien entra a jugar."""
    cuerpo = indentar(contenido_curriculo(juego), '  ')
    if posicion == 'superior':
        return '\n'.join([
            '<section class="bloque-docente-superior" aria-labelledby="docente-titulo">',
            '  <div class="bloque-docente-cabeza">',
            '    <h2 id="docente-titulo">🍎 Vista docente: lineamientos de esta actividad</h2>',
            '    <button type="button" class="btn btn-secundario" data-modo="estudiante">Ver como estudiante</button>',
            '  </div>',
            cuerpo,
            '</section>'])
    return '\n'.join([
        '<details class="curriculo curriculo-inferior">',
        '  <summary>🍎 ¿Eres docente? Objetivo, DBA y fichas en PDF</summary>',
        cuerpo,
        '</details>'])


def cabecera_academica(juego):
    """Recuadro al inicio de cada ficha impresa: objetivo, competencia, DBA,
    estándares e indicadores de desempeño."""
    c = juego.curriculo
    filas = ['<p><strong>Objetivo:</strong> %s</p>' % esc(c['objetivo']),
             '<p><strong>Competencia:</strong> %s</p>' % esc(c['competencia'])]
    if c['dba']:
        filas.append('<p><strong>DBA:</strong> %s</p>' % ' '.join(
            '<span class="aca-ref">%s «%s»</span>' % (esc(etiqueta_dba(r)), esc(r['texto'])) for r in c['dba']))
    if c['estandares']:
        filas.append('<p><strong>Estándar:</strong> %s</p>' % ' '.join(
            '<span class="aca-ref">%s «%s»</span>' % (esc(etiqueta_estandar(r, c['fuentes_doc'])), esc(r['texto']))
            for r in c['estandares'][:2]))
    filas.append('<p><strong>Indicadores de desempeño:</strong></p><ul>%s</ul>'
                 % ''.join('<li>%s</li>' % esc(i) for i in c['indicadores']))
    return '<section class="ficha-academica" aria-label="Aspectos académicos">\n  %s\n</section>' % '\n  '.join(filas)


def situacion_problema(juego, numero=None):
    """Situación problema ilustrada, con renglones para responder. En la ficha es
    una pregunta más (lleva número); en la vista docente va sin número."""
    sit = juego.curriculo['situacion']
    preguntas = ''.join('<li>%s<span class="renglon"></span></li>' % esc(q) for q in sit['preguntas'])
    numero_html = ('<span class="ficha-numero">%d.</span> ' % numero) if numero else ''
    return ('<section class="situacion-problema ficha-pregunta">\n  <p class="situacion-arte" aria-hidden="true">%s</p>\n'
            '  <h3>%s🧩 Situación problema</h3>\n  <p>%s</p>\n  <ol type="a">%s</ol>\n</section>'
            % (esc(sit['ilustracion']), numero_html, esc(sit['texto']), preguntas))


def numero_situacion(juego):
    """La situación va después de la última pregunta de la ficha."""
    d = juego.datos
    for clave in ('preguntas', 'pares', 'rondas', 'actividades'):
        if d.get(clave):
            return len(d[clave]) + 1
    return 1


def resumen_curriculo(juego):
    """Versión corta para la hoja de respuestas de la ficha impresa."""
    c = juego.curriculo
    dba = '; '.join('%s: «%s»' % (etiqueta_dba(r), r['texto']) for r in c['dba'])
    return ('<div class="ficha-curriculo">\n  <p><strong>Objetivo:</strong> %s</p>\n%s</div>'
            % (esc(c['objetivo']), ('  <p><strong>DBA:</strong> %s</p>\n' % esc(dba)) if dba else ''))


def bloque_pie(materias, v, juego=None):
    partes = []
    if juego and juego.curriculo:
        partes.append(bloque_curriculo(juego))
    if juego:
        # Primero los del mismo tema; sort es estable, así se respeta el orden del catálogo.
        otros = sorted((j for j in juego.materia.juegos if j is not juego),
                       key=lambda j: j.tema is not juego.tema)[:MAX_RELACIONADOS]
        if otros:
            partes.append('''<section class="relacionados" aria-labelledby="relacionados-titulo">
  <h2 id="relacionados-titulo">Más juegos de %s</h2>
%s
  <a class="enlace-flecha" href="/%s/">Ver todos los juegos de %s →</a>
</section>''' % (esc(juego.materia.nombre), indentar(lista_tarjetas(otros), '  '),
                 juego.materia.id, esc(juego.materia.nombre)))

    enlaces = '\n'.join('        <li><a class="materia-%s" href="/%s/">%s %s</a></li>'
                        % (m.id, m.id, esc(m.icono), esc(m.nombre)) for m in materias)
    partes.append('''<footer class="pie-sitio">
  <div class="pie-sitio-interior">
    <div class="pie-marca">
      <a class="marca" href="/"><span class="marca-logo" aria-hidden="true">🎮</span><span class="marca-texto">Juegos Educativos</span></a>
      <p>Juegos gratuitos para aprender en casa o en clase, desde cualquier dispositivo y sin registrarse.</p>
      <p><a class="enlace-flecha" href="/secundaria/">🎓 Juegos para secundaria</a></p>
      <p><a class="enlace-flecha" href="/descargar/">📥 Usar sin internet y fichas para imprimir</a></p>
    </div>
    <nav aria-labelledby="pie-materias-titulo">
      <h2 class="pie-titulo" id="pie-materias-titulo">Materias</h2>
      <ul class="pie-materias">
%s
      </ul>
    </nav>
  </div>
</footer>''' % enlaces)
    partes.append('<script src="%s"></script>' % v.url('site.js'))
    return '\n'.join(partes)


def cabeza(v, titulo, descripcion, ruta, tipo_og='website', estilos=(), robots=None):
    url = URL_SITIO + url_de(ruta)
    lineas = [
        '<meta charset="UTF-8" />',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />',
        '<title>%s</title>' % esc(titulo),
        '<meta name="description" content="%s" />' % esc(descripcion),
    ]
    if robots:
        lineas.append('<meta name="robots" content="%s" />' % esc(robots))
    else:
        lineas += [
            '<link rel="canonical" href="%s" />' % esc(url),
            '<meta property="og:type" content="%s" />' % tipo_og,
            '<meta property="og:site_name" content="%s" />' % esc(NOMBRE_SITIO),
            '<meta property="og:title" content="%s" />' % esc(titulo),
            '<meta property="og:description" content="%s" />' % esc(descripcion),
            '<meta property="og:url" content="%s" />' % esc(url),
            '<meta name="twitter:card" content="summary" />',
        ]
    lineas.append(bloque('comun', bloque_comun(v)))
    lineas += ['<link rel="stylesheet" href="%s" />' % v.url(e) for e in estilos]
    return '<head>\n%s\n</head>' % indentar('\n'.join(lineas), '  ')


def documento(head, clase_body, cuerpo):
    return '<!DOCTYPE html>\n<html lang="es">\n%s\n%s\n<body class="%s">\n%s\n</body>\n</html>\n' % (
        AVISO_HTML, head, clase_body, indentar(cuerpo, '  '))


# --- Páginas ------------------------------------------------------------------

def pagina_inicio(materias, v):
    juegos = [j for m in materias for j in m.juegos]
    preguntas = sum(len(j.datos['preguntas']) for j in juegos if j.tipo == 'quiz')
    nombres = ', '.join(m.nombre.lower() for m in materias[:-1]) + ' y ' + materias[-1].nombre.lower()
    descripcion = ('Juegos educativos online gratis de %s: juegos virtuales de aprendizaje para primaria '
                   'y secundaria, sin registro y desde cualquier dispositivo.' % nombres)

    arte = '\n'.join('    <li class="materia-%s">%s</li>' % (m.id, esc(m.icono)) for m in materias)
    tarjetas = []
    for m in materias:
        chips = ''.join('<span class="chip">%s</span>' % esc(t.nombre) for t in m.temas)
        tarjetas.append('''<li class="tarjeta-materia materia-%s" id="%s">
  <a href="/%s/">
    <span class="tarjeta-materia-icono" aria-hidden="true">%s</span>
    <h3>%s</h3>
    <span class="tarjeta-materia-desc">%s</span>
    <span class="chips">%s</span>
    <span class="tarjeta-materia-pie"><span>%s · %s</span><span class="flecha" aria-hidden="true">→</span></span>
  </a>
</li>''' % (m.id, m.id, m.id, esc(m.icono), esc(m.nombre), esc(m.descripcion), chips,
            plural(len(m.temas), 'tema', 'temas'), plural(len(m.juegos), 'juego', 'juegos')))

    cuerpo = '''%s
<main id="contenido">
  <section class="portada">
    <div class="portada-interior">
      <div class="portada-texto">
        <p class="portada-etiqueta">Gratis · Sin registro · Para estudiantes, docentes y familias</p>
        <h1>Aprende jugando</h1>
        <p class="portada-lema">Juegos para practicar matemáticas, lectura, ciencias, inglés y mucho más, desde cualquier dispositivo.</p>
        <ul class="portada-cifras">
          <li><strong>%d</strong> materias</li>
          <li><strong>%d</strong> juegos</li>
          <li><strong>%d</strong> preguntas</li>
        </ul>
        <a class="btn btn-grande" href="#materias">Elegir materia ↓</a>
      </div>
      <ul class="portada-arte" aria-hidden="true">
%s
      </ul>
    </div>
  </section>

  <section class="seccion" aria-labelledby="entradas-titulo">
    <div class="seccion-cabeza">
      <h2 id="entradas-titulo">¿Quién eres?</h2>
      <p>Elige tu camino: cada uno te lleva a lo que necesitas.</p>
    </div>
    <ul class="rejilla-entradas">
      <li class="entrada entrada-jugar">
        <a href="#materias">
          <span class="entrada-icono" aria-hidden="true">🎮</span>
          <h3>Quiero jugar</h3>
          <span>Juegos de todas las materias para aprender mientras te diviertes.</span>
          <span class="entrada-cta">Elegir materia →</span>
        </a>
      </li>
      <li class="entrada entrada-docentes">
        <a href="/docentes/">
          <span class="entrada-icono" aria-hidden="true">🍎</span>
          <h3>Soy docente</h3>
          <span>Recursos por grado, fichas imprimibles con respuestas e ideas para usarlos en clase.</span>
          <span class="entrada-cta">Ver recursos →</span>
        </a>
      </li>
      <li class="entrada entrada-familias">
        <a href="/familias/">
          <span class="entrada-icono" aria-hidden="true">🏠</span>
          <h3>Soy madre o padre</h3>
          <span>Actividades según la edad de tus hijos, para hacer en casa con o sin pantalla.</span>
          <span class="entrada-cta">Ver actividades →</span>
        </a>
      </li>
    </ul>
  </section>

  <section class="seccion" id="materias" aria-labelledby="materias-titulo">
    <div class="seccion-cabeza">
      <h2 id="materias-titulo">Elige una materia</h2>
      <p>Cada materia está organizada por temas. Empieza por el que quieras.</p>
    </div>
    <ul class="rejilla-materias">
%s
    </ul>
  </section>

  <section class="seccion" aria-labelledby="secundaria-titulo">
    <div class="aviso-offline">
      <span class="paso-icono" aria-hidden="true">🎓</span>
      <div>
        <h2 id="secundaria-titulo">¿Estás en secundaria?</h2>
        <p>Juegos interactivos para jóvenes: relaciona parejas contra el reloj y ordena líneas del tiempo de química, física, historia, inglés y más.</p>
      </div>
      <a class="btn" href="/secundaria/">Ver juegos</a>
    </div>
  </section>

  <section class="seccion" aria-labelledby="sin-internet-titulo">
    <div class="aviso-offline">
      <span class="paso-icono" aria-hidden="true">📥</span>
      <div>
        <h2 id="sin-internet-titulo">Juega sin internet o imprime las fichas</h2>
        <p>Instala el sitio como aplicación para usarlo sin conexión, o descarga fichas con las preguntas y sus respuestas para trabajar en papel.</p>
      </div>
      <a class="btn" href="/descargar/">Ver opciones</a>
    </div>
  </section>

  <section class="seccion" aria-labelledby="como-titulo">
    <div class="seccion-cabeza">
      <h2 id="como-titulo">¿Cómo funciona?</h2>
    </div>
    <ol class="pasos">
      <li><span class="paso-icono" aria-hidden="true">📚</span><h3>Elige una materia</h3><p>Y dentro de ella, el tema que quieras repasar.</p></li>
      <li><span class="paso-icono" aria-hidden="true">🎯</span><h3>Juega y responde</h3><p>Cada respuesta se corrige al momento, y muchas traen una explicación.</p></li>
      <li><span class="paso-icono" aria-hidden="true">🏆</span><h3>Supera tu marca</h3><p>Preguntas y ejercicios cambian en cada partida: vuelve a jugar para mejorar.</p></li>
    </ol>
  </section>
</main>
%s''' % (bloque_navegacion(materias), len(materias), len(juegos), preguntas, arte,
         indentar('\n'.join(tarjetas), '      '), bloque_pie(materias, v))

    head = cabeza(v, 'Juegos educativos online gratis: aprende jugando — %s' % NOMBRE_SITIO, descripcion, 'index.html')
    return documento(head, 'pagina-inicio', cuerpo)


def pagina_materia(materia, materias, v):
    indice = '\n'.join('          <li><a href="#tema-%s">%s</a></li>' % (t.id, esc(t.nombre)) for t in materia.temas)
    secciones = []
    for t in materia.temas:
        secciones.append('''<section class="tema" id="tema-%s" aria-labelledby="tema-%s-titulo">
  <div class="tema-cabeza">
    <h2 id="tema-%s-titulo">%s</h2>
    <p>%s</p>
  </div>
%s
</section>''' % (t.id, t.id, t.id, esc(t.nombre), esc(t.descripcion), indentar(lista_tarjetas(t.juegos), '  ')))

    otras = '\n'.join('      <li><a class="materia-%s" href="/%s/"><span class="menu-icono" aria-hidden="true">%s</span>%s</a></li>'
                      % (m.id, m.id, esc(m.icono), esc(m.nombre)) for m in materias if m is not materia)

    cuerpo = '''%s
<div class="cabecera-materia">
  <div class="cabecera-materia-interior">
%s
    <div class="cabecera-materia-titulo">
      <span class="cabecera-materia-icono" aria-hidden="true">%s</span>
      <div>
        <h1>%s</h1>
        <p>%s</p>
      </div>
    </div>
    <p class="cabecera-materia-meta">%s · %s</p>
    <nav class="indice-temas" aria-label="Temas de %s">
      <ul>
%s
      </ul>
    </nav>
  </div>
</div>
<main id="contenido" class="pagina">
%s
  <section class="otras-materias" aria-labelledby="otras-titulo">
    <h2 id="otras-titulo">Otras materias</h2>
    <ul class="chips-materias">
%s
    </ul>
  </section>
</main>
%s''' % (bloque_navegacion(materias, actual=materia),
         indentar(migas_html([('Inicio', '/'), (materia.nombre, None)]), '    '),
         esc(materia.icono), esc(materia.nombre), esc(materia.descripcion),
         plural(len(materia.temas), 'tema', 'temas'), plural(len(materia.juegos), 'juego', 'juegos'),
         esc(materia.nombre), indice, indentar('\n'.join(secciones), '  '), otras, bloque_pie(materias, v))

    head = cabeza(v, '%s — %s' % (materia.titulo_seo or materia.nombre, NOMBRE_SITIO),
                  materia.descripcion_seo or '%s Juegos educativos gratuitos de %s por temas.'
                  % (materia.descripcion, materia.nombre.lower()),
                  materia.id + '/index.html')
    return documento(head, 'materia-%s' % materia.id, cuerpo)


def migas_de(juego):
    return [('Inicio', '/'), (juego.materia.nombre, '/%s/' % juego.materia.id),
            (juego.tema.nombre, '/%s/#tema-%s' % (juego.materia.id, juego.tema.id)), (juego.titulo, None)]


def json_para_script(datos):
    """JSON seguro dentro de <script>: sin '<' literal, ningún texto puede cerrar la etiqueta."""
    texto = json.dumps(datos, ensure_ascii=False, separators=(',', ':'))
    return texto.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def pagina_imprimible(juego, materias, v):
    instrucciones, bloques, _ = ficha_imprimible(juego)
    cuerpo = """%s
<div class="container">
  <header class="header">
    <span class="header-icono" aria-hidden="true">%s</span>
    <h1>%s</h1>
    <p>%s</p>
    <p class="header-meta"><span class="insignia insignia-clara">%s</span><span>%s</span></p>
  </header>
  <main class="content" id="contenido">
    <div class="ficha-acciones">
      %s
      <a class="btn btn-secundario" href="%s">🖨️ Ver la ficha para imprimir</a>
    </div>
    <p class="ficha-instrucciones">%s</p>
    <div class="ficha-cuerpo act-cuerpo act-pantalla">
%s
    </div>
  </main>
</div>
%s""" % (bloque_navegacion(materias, migas=migas_de(juego), docente=bloque_curriculo(juego, 'superior')),
         esc(juego.icono), esc(juego.titulo), esc(juego.descripcion), esc(etiqueta_grados(juego.grados)),
         esc('%s · %s' % (juego.detalle, etiqueta_edades(juego.grados))),
         enlace_pdf(ruta_ficha(juego), '📄 Descargar PDF', 'btn btn-acento'), url_de(ruta_ficha(juego)),
         instrucciones, indentar('\n'.join(bloques), '      '), bloque_pie(materias, v, juego))
    head = cabeza(v, '%s — %s' % (juego.titulo_seo or juego.titulo, NOMBRE_SITIO),
                  juego.descripcion_seo or juego.descripcion, juego.ruta, tipo_og='article')
    return documento(head, 'materia-%s' % juego.materia.id, cuerpo)


def pagina_juego(juego, materias, v):
    if juego.tipo == 'imprimible':
        return pagina_imprimible(juego, materias, v)
    estilos, script, arranque = MOTORES[juego.tipo]
    cuerpo = '''%s
<div class="container">
  <header class="header">
    <span class="header-icono" aria-hidden="true">%s</span>
    <h1>%s</h1>
    <p>%s</p>
    <p class="header-meta"><span class="insignia insignia-clara">%s</span><span>%s</span><a class="enlace-ficha" href="%s">🖨️ Ficha para imprimir</a></p>
  </header>
  <main class="content" id="contenido">
    <div id="quiz">
      <noscript><p>Este juego necesita JavaScript activado en el navegador.</p></noscript>
    </div>
  </main>
</div>
%s
<script src="%s"></script>
<script type="application/json" id="datos-quiz">%s</script>
<script>
  JEO.%s(document.getElementById('quiz'), document.getElementById('datos-quiz'));
</script>''' % (bloque_navegacion(materias, migas=migas_de(juego), docente=bloque_curriculo(juego, 'superior')),
                esc(juego.icono), esc(juego.titulo),
                esc(juego.descripcion), esc(etiqueta_grados(juego.grados)),
                esc('%s · %s' % (juego.detalle, etiqueta_edades(juego.grados))), url_de(ruta_ficha(juego)),
                bloque_pie(materias, v, juego), v.url(script), json_para_script(juego.datos), arranque)

    head = cabeza(v, '%s — %s' % (juego.titulo_seo or juego.titulo, NOMBRE_SITIO),
                  juego.descripcion_seo or juego.descripcion, juego.ruta, tipo_og='article', estilos=estilos)
    return documento(head, 'materia-%s' % juego.materia.id, cuerpo)


def pagina_404(materias, v):
    enlaces = '\n'.join('      <li><a class="materia-%s" href="/%s/"><span class="menu-icono" aria-hidden="true">%s</span>%s</a></li>'
                        % (m.id, m.id, esc(m.icono), esc(m.nombre)) for m in materias)
    cuerpo = '''%s
<div class="container">
  <header class="header">
    <span class="header-icono" aria-hidden="true">🧭</span>
    <h1>Página no encontrada</h1>
    <p>El enlace que seguiste no existe o cambió de sitio.</p>
  </header>
  <main class="content" id="contenido">
    <p>Vuelve al <a href="/">inicio</a> o elige una materia:</p>
    <ul class="chips-materias">
%s
    </ul>
  </main>
</div>
%s''' % (bloque_navegacion(materias), enlaces, bloque_pie(materias, v))
    head = cabeza(v, 'Página no encontrada — %s' % NOMBRE_SITIO,
                  'La página que buscas no existe.', '404.html', robots='noindex')
    return documento(head, 'pagina-error', cuerpo)


def materias_css(materias):
    reglas = ['/* %s a partir de contenido/catalogo.json. No lo edites a mano. */' % MARCA_GENERADO]
    for m in materias:
        c = paleta(m.color)
        reglas.append('''
.materia-%s {
  --materia: %s;
  --materia-oscuro: %s;
  --materia-suave: %s;
  --materia-borde: %s;
  --color-primario: %s;
  --color-primario-oscuro: %s;
}''' % (m.id, c['base'], c['oscuro'], c['suave'], c['borde'], c['base'], c['oscuro']))
    return '\n'.join(reglas) + '\n'


def ruta_ficha(juego):
    return juego.ruta[:-len('.html')] + '-ficha.html'


def orden_fijo(juego, clave, n):
    """Permutación aleatoria pero fija de range(n): depende solo del juego y de
    `clave`, así la ficha no cambia cada vez que se genera el sitio."""
    semilla = int(hashlib.sha256((juego.ruta + clave).encode('utf-8')).hexdigest(), 16)
    orden = list(range(n))
    random.Random(semilla).shuffle(orden)
    return orden


def opciones_de_ficha(juego, pregunta):
    """Opciones en papel: barajadas de forma fija para que la respuesta no caiga
    siempre en la a)."""
    orden = orden_fijo(juego, pregunta['enunciado'], len(pregunta['opciones']))
    return [pregunta['opciones'][i] for i in orden], orden.index(pregunta['correcta'])


LETRAS = 'abcdefghijklmnopqrstuvwxyz'


# Opciones de hasta este largo caben en dos columnas dentro de la ficha impresa.
LARGO_OPCION_CORTA = 22


# Palabra (o raíz) del enunciado → dibujo. Se usa cuando la pregunta no trae el suyo.
ILUSTRACIONES = [
    ('manzana', '🍎'), ('fresa', '🍓'), ('naranja', '🍊'), ('banano', '🍌'), ('uva', '🍇'), ('pera', '🍐'),
    ('limón', '🍋'), ('sandía', '🍉'), ('pizza', '🍕'), ('torta', '🎂'), ('pastel', '🎂'), ('chocolat', '🍫'),
    ('galleta', '🍪'), ('dulce', '🍬'), ('caramelo', '🍬'), ('helado', '🍦'), ('pan', '🍞'), ('empanada', '🥟'),
    ('jugo', '🧃'), ('leche', '🥛'), ('huevo', '🥚'), ('arepa', '🫓'), ('receta', '🥣'),
    ('globo', '🎈'), ('canica', '🔵'), ('balón', '⚽'), ('pelota', '⚽'), ('gol', '⚽'), ('partido', '⚽'), ('lápi', '✏️'),
    ('cuaderno', '📓'), ('libro', '📚'), ('cuento', '📖'), ('biblioteca', '📚'), ('colegio', '🏫'),
    ('escuela', '🏫'), ('salón', '🏫'), ('profesor', '👩‍🏫'), ('estudiante', '🧒🏽'), ('niñ', '🧒🏽'),
    ('bus', '🚌'), ('carro', '🚗'), ('bicicleta', '🚲'), ('avión', '✈️'), ('tren', '🚆'), ('barco', '⛵'),
    ('dinero', '💵'), ('peso', '🪙'), ('moneda', '🪙'), ('billete', '💵'), ('tienda', '🏪'), ('compra', '🛒'),
    ('precio', '🏷️'), ('perro', '🐕'), ('gato', '🐈'), ('gallina', '🐔'), ('pollito', '🐥'), ('vaca', '🐄'),
    ('caballo', '🐴'), ('pez', '🐟'), ('peces', '🐟'), ('pájaro', '🐦'), ('ave', '🐦'), ('mariposa', '🦋'),
    ('abeja', '🐝'), ('hormiga', '🐜'), ('rana', '🐸'), ('conejo', '🐰'), ('león', '🦁'), ('elefante', '🐘'),
    ('tortuga', '🐢'), ('serpiente', '🐍'), ('mono', '🐒'), ('oso', '🐻'), ('animal', '🐾'),
    ('flor', '🌸'), ('planta', '🌱'), ('semilla', '🌱'), ('árbol', '🌳'), ('hoja', '🍃'), ('raíz', '🌱'),
    ('sol', '☀️'), ('luna', '🌙'), ('estrella', '⭐'), ('planeta', '🪐'), ('tierra', '🌍'), ('lluvia', '🌧️'),
    ('agua', '💧'), ('hielo', '🧊'), ('fuego', '🔥'), ('temperatura', '🌡️'), ('grados', '🌡️'),
    ('montaña', '⛰️'), ('río', '🏞️'), ('mar', '🌊'), ('océano', '🌊'), ('mapa', '🗺️'), ('norte', '🧭'),
    ('país', '🌎'), ('capital', '🏙️'), ('ciudad', '🏙️'), ('historia', '📜'), ('rey', '👑'), ('guerra', '⚔️'),
    ('corazón', '❤️'), ('cuerpo', '🧍'), ('hueso', '🦴'), ('diente', '🦷'), ('ojo', '👁️'), ('pulmón', '🫁'),
    ('cerebro', '🧠'), ('alimento', '🥗'), ('salud', '🩺'),
    ('computador', '💻'), ('internet', '🌐'), ('celular', '📱'), ('clave', '🔒'), ('contraseña', '🔒'),
    ('robot', '🤖'), ('programa', '🧩'), ('energía', '⚡'), ('luz', '💡'), ('sonido', '🔊'), ('imán', '🧲'),
    ('fuerza', '💪'), ('velocidad', '🏎️'), ('metro', '📏'), ('kilo', '⚖️'), ('masa', '⚖️'), ('tiempo', '⏱️'),
    ('hora', '⏰'), ('reloj', '⏰'), ('calendario', '📅'), ('día', '📅'), ('mes', '📅'),
    ('mezcla', '🧪'), ('átomo', '⚛️'), ('elemento', '⚗️'), ('ácido', '🍋'),
    ('triángulo', '🔺'), ('cuadrado', '⬛'), ('círculo', '⚪'), ('rectángulo', '▭'), ('ángulo', '📐'),
    ('área', '📐'), ('perímetro', '📏'), ('cubo', '🧊'), ('fracción', '🍕'), ('mitad', '🍕'),
    ('color', '🎨'), ('pintura', '🎨'), ('música', '🎵'), ('nota', '🎵'), ('instrumento', '🎸'), ('canción', '🎶'),
    ('feliz', '😀'), ('alegr', '😀'), ('triste', '😢'), ('rabia', '😠'), ('enojad', '😠'), ('miedo', '😨'),
    ('amig', '🤝'), ('familia', '👨‍👩‍👧'), ('mamá', '👩'), ('papá', '👨'), ('abuel', '👵'),
    ('carta', '✉️'), ('mensaje', '💬'), ('palabra', '🔤'), ('oración', '✍️'), ('letra', '🔤'),
]


def ilustrar(texto):
    """Hasta dos dibujos según las palabras del enunciado (orden de aparición)."""
    t = ' ' + texto.lower() + ' '
    hallados = []
    for palabra, dibujo in ILUSTRACIONES:
        m = re.search(r'(?<!\w)' + re.escape(palabra) + ('' if len(palabra) > 3 else r'\b'), t)
        i = m.start() if m else -1
        if i >= 0 and dibujo not in [d for _, d in hallados]:
            hallados.append((i, dibujo))
    return ''.join(d for _, d in sorted(hallados)[:2])


OPERACION = re.compile(r'(?<![\d.,/])(\d{1,2})\s*([+\-−×x])\s*(\d{1,2})(?![\d.,/])')
NUMERO_SUELTO = re.compile(r'(?<![\d.,/])(\d{1,2})(?!\d|[.,]\d|[/°%])')
MAX_EN_GRUPO = 20
NO_CONTABLE = re.compile(r'/|[−-]\s*\d|°|\$|\d\s*(?:cm|m|km|kg|g|l|litros|metros)\b|fracci|área|perímetro|'
                         r'\bde\s+\d|\btienen\s+\d|\bcada\b|\bveces\b|\bporciones\b|\d+\s+\w+\s+de\s+\d', re.I)


def figura_de(texto):
    """Dibujo de las cantidades de un enunciado, para contar: {'grupos': [[dibujo, n], ...], 'op': '+'}.
    Con una operación escrita se muestra el signo; en un problema de palabras solo los
    dos grupos, sin el signo, para no darle la operación a quien lo resuelve."""
    emojis, resto = separar_ilustracion(texto)
    # Lo que se cuenta suele nombrarse justo después del primer número («8 huevos»).
    primero = re.search(r'\d', resto)
    dibujo = ((ilustrar(resto[primero.start():]) if primero else '') or emojis or ilustrar(resto) or '🔵')[:2]
    dibujo = dibujo if len(dibujo) == 1 or dibujo[1] in '️‍' else dibujo[0]
    m = OPERACION.search(resto)
    if m:
        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
        op = {'-': '−', 'x': '×'}.get(op, op)
        if op == '×':
            if 1 < a <= 6 and 1 < b <= 6:
                return {'grupos': [[dibujo, b]] * a, 'op': '×'}
            return None
        if a <= MAX_EN_GRUPO and b <= MAX_EN_GRUPO:
            return {'grupos': [[dibujo, a], [dibujo, b]], 'op': op}
        return None
    # Solo problemas de juntar, quitar y comparar: sin negativos, medidas, dinero,
    # fracciones ni «filas de 8» (eso es multiplicar y los grupos lo contarían mal).
    if NO_CONTABLE.search(resto):
        return None
    numeros = [int(n) for n in NUMERO_SUELTO.findall(resto)]
    if len(numeros) == 2 and all(1 <= n <= MAX_EN_GRUPO for n in numeros) and (emojis or ilustrar(resto)):
        return {'grupos': [[dibujo, numeros[0]], [dibujo, numeros[1]]], 'op': ''}
    return None


def figura_html(figura):
    if not figura:
        return ''
    partes = []
    for i, (dibujo, n) in enumerate(figura['grupos']):
        if i:
            if figura['op'] in ('+', '−'):
                partes.append('<span class="figura-op">%s</span>' % esc(figura['op']))
        partes.append('<span class="figura-grupo">%s</span>' % esc(dibujo * n))
    return '<div class="figura-cantidades" aria-hidden="true">%s</div>' % ''.join(partes)


def separar_ilustracion(texto):
    """Separa los emojis del inicio de un enunciado («🍎🍎🍎 ¿Cuántas…?») para
    imprimirlos grandes como ilustración. Devuelve (emojis, resto del texto)."""
    i = 0
    while i < len(texto) and (unicodedata.category(texto[i]) in ('So', 'Sk', 'Mn', 'Cf')
                              or texto[i] in '‍️'):
        i += 1
    if i == 0:
        return '', texto
    return texto[:i], texto[i:].lstrip()


def enunciado_ficha(n, texto):
    emojis, resto = separar_ilustracion(texto)
    figura = figura_de(texto)
    emojis = '' if figura else (emojis or ilustrar(resto))
    ilustracion = ('<span class="ficha-ilustracion" aria-hidden="true">%s</span>' % esc(emojis)) if emojis else ''
    return '  %s<p class="ficha-enunciado"><span class="ficha-numero">%d.</span> %s</p>%s' % (
        ilustracion, n, esc(resto), figura_html(figura))


def pasaje_ficha(pasaje):
    parrafos = '\n'.join('  <p>%s</p>' % esc(t) for t in pasaje['parrafos'])
    ilustracion = pasaje.get('ilustracion', '')
    arte = ('\n  <p class="ficha-pasaje-arte" aria-hidden="true">%s</p>' % esc(ilustracion)) if ilustracion else ''
    return ('<article class="quiz-pasaje ficha-pasaje">%s\n  <h2 class="quiz-pasaje-titulo">📖 %s</h2>\n%s\n</article>'
            % (arte, esc(pasaje['titulo']), parrafos))


def ficha_quiz(juego):
    bloques, respuestas = [], []
    pasaje_actual = None
    for n, p in enumerate(juego.datos['preguntas'], 1):
        if p.get('pasaje') and p['pasaje'] != pasaje_actual:
            pasaje_actual = p['pasaje']
            bloques.append(pasaje_ficha(juego.datos['pasajes'][pasaje_actual]))
        opciones, correcta = opciones_de_ficha(juego, p)
        items = '\n'.join('    <li>%s</li>' % esc(o) for o in opciones)
        cortas = ' cortas' if max(len(o) for o in opciones) <= LARGO_OPCION_CORTA else ''
        bloques.append('<div class="ficha-pregunta">\n%s\n  <ol class="ficha-opciones%s" type="a">\n%s\n  </ol>\n</div>'
                       % (enunciado_ficha(n, p['enunciado']), cortas, items))
        explicacion = (' <span class="ficha-explicacion">%s</span>' % esc(p['explicacion'])) if p.get('explicacion') else ''
        respuestas.append('<li><strong>%s)</strong> %s%s</li>' % (LETRAS[correcta], esc(opciones[correcta]), explicacion))
    return 'Rodea con un círculo la letra de la respuesta correcta.', bloques, respuestas


def ficha_parejas(juego):
    pares = juego.datos['pares']
    izquierda = orden_fijo(juego, 'izquierda', len(pares))
    derecha = orden_fijo(juego, 'derecha', len(pares))
    filas = []
    for fila, (i, j) in enumerate(zip(izquierda, derecha)):
        filas.append('    <tr><td><span class="ficha-numero">%d.</span> %s</td><td class="ficha-hueco">____</td>'
                     '<td><span class="ficha-numero">%s)</span> %s</td></tr>'
                     % (fila + 1, esc(pares[i]['a']), LETRAS[fila], esc(pares[j]['b'])))
    tabla = ('<table class="ficha-tabla">\n  <thead><tr><th>%s</th><th>Letra</th><th>%s</th></tr></thead>\n  <tbody>\n%s\n  </tbody>\n</table>'
             % (esc(juego.datos['etiquetaA']), esc(juego.datos['etiquetaB']), '\n'.join(filas)))
    respuestas = []
    for fila, i in enumerate(izquierda):
        letra = LETRAS[derecha.index(i)]
        respuestas.append('<li><strong>%d → %s)</strong> %s: %s</li>'
                          % (fila + 1, letra, esc(pares[i]['a']), esc(pares[i]['b'])))
    return ('Escribe junto a cada número la letra de su pareja.', [tabla], respuestas)


def ficha_ordenar(juego):
    bloques, respuestas = [], []
    for n, ronda in enumerate(juego.datos['rondas'], 1):
        elementos = ronda['elementos']
        orden = orden_fijo(juego, ronda['instruccion'], len(elementos))
        if orden == sorted(orden):
            orden = orden[1:] + orden[:1]  # nunca imprimir la ronda ya resuelta
        items = '\n'.join('    <li><span class="ficha-hueco">___</span> %s</li>' % esc(elementos[i]) for i in orden)
        bloques.append('<div class="ficha-pregunta">\n  <p class="ficha-enunciado"><span class="ficha-numero">%d.</span> %s</p>\n'
                       '  <ul class="ficha-ordenar">\n%s\n  </ul>\n</div>' % (n, esc(ronda['instruccion']), items))
        explicacion = (' <span class="ficha-explicacion">%s</span>' % esc(ronda['explicacion'])) if ronda.get('explicacion') else ''
        respuestas.append('<li>%s.%s</li>' % (esc(' → '.join(elementos)), explicacion))
    return 'Numera cada elemento según el orden correcto, empezando por el 1.', bloques, respuestas


def ficha_imprimible(juego):
    actividades = juego.datos['actividades']
    bloques = imprimibles.renderizar(actividades, juego.ruta)
    respuestas = ['<li><strong>Actividad %d:</strong> %s</li>' % (n, esc(a['respuesta']))
                  for n, a in enumerate(actividades, 1) if a.get('respuesta')]
    return ('Un adulto lee cada consigna en voz alta. Se necesitan lápiz y colores.', bloques, respuestas)


FICHAS = {'quiz': ficha_quiz, 'parejas': ficha_parejas, 'ordenar': ficha_ordenar, 'imprimible': ficha_imprimible}


def clase_cuerpo(juego):
    """Las actividades con dibujos grandes ocupan todo el ancho; el resto va a dos columnas."""
    return 'ficha-cuerpo act-cuerpo' if juego.tipo == 'imprimible' else 'ficha-cuerpo'


def titulo_respuestas(respuestas):
    """En las fichas de Transición la hoja final es una guía para el adulto."""
    return 'Respuestas' if respuestas else 'Para el adulto'


def pagina_ficha(juego, materias, v):
    instrucciones, bloques, respuestas = FICHAS[juego.tipo](juego)
    migas = migas_de(juego)[:-1] + [(juego.titulo, url_de(juego.ruta)), ('Ficha', None)]
    cuerpo = """%s
<div class="container ficha">
  <header class="header">
    <span class="header-icono" aria-hidden="true">%s</span>
    <h1>%s</h1>
    <p>%s</p>
    <p class="header-meta"><span class="insignia insignia-clara">%s</span><span>%s · %s</span></p>
  </header>
  <main class="content" id="contenido">
    <div class="ficha-acciones no-imprimir">
      <button type="button" class="btn" data-imprimir>🖨️ Imprimir o guardar como PDF</button>
      %s
      <a class="btn btn-secundario" href="%s">🎮 %s</a>
    </div>
%s
    <p class="ficha-datos"><span>Nombre:</span><span>Fecha:</span></p>
    <p class="ficha-instrucciones">%s</p>
    <div class="%s">
%s
%s
    </div>
    <section class="ficha-respuestas" aria-labelledby="respuestas-titulo">
      <h2 id="respuestas-titulo">%s: %s</h2>
      <ol>
%s
      </ol>
%s
    </section>
  </main>
</div>
%s""" % (bloque_navegacion(materias, migas=migas), esc(juego.icono), esc(juego.titulo), esc(juego.descripcion),
         esc(etiqueta_grados(juego.grados)), esc(juego.materia.nombre), esc(juego.detalle),
         enlace_pdf(ruta_ficha(juego), '📄 Descargar PDF', 'btn btn-acento'), url_de(juego.ruta),
         'Ver en pantalla' if juego.tipo == 'imprimible' else 'Jugar en pantalla',
         indentar(cabecera_academica(juego), '    '), instrucciones, clase_cuerpo(juego),
         indentar('\n'.join(bloques), '      '), indentar(situacion_problema(juego, numero_situacion(juego)), '      '), titulo_respuestas(respuestas), esc(juego.titulo),
         indentar('\n'.join(respuestas), '        '), '', bloque_pie(materias, v))

    head = cabeza(v, 'Ficha: %s — %s' % (juego.titulo, NOMBRE_SITIO),
                  'Ficha para imprimir de %s, con sus respuestas.' % juego.titulo,
                  ruta_ficha(juego), robots='noindex')
    return documento(head, 'materia-%s pagina-ficha' % juego.materia.id, cuerpo)


def cabecera_banda(migas, icono, titulo, texto, meta='', extra=''):
    """Cabecera de color de las páginas de sección (docentes, familias, grado, edad)."""
    return """<div class="cabecera-materia cabecera-marca">
  <div class="cabecera-materia-interior">
%s
    <div class="cabecera-materia-titulo">
      <span class="cabecera-materia-icono" aria-hidden="true">%s</span>
      <div>
        <h1>%s</h1>
        <p>%s</p>
      </div>
    </div>%s%s
  </div>
</div>""" % (indentar(migas_html(migas), '    '), icono, esc(titulo), esc(texto),
             ('\n    <p class="cabecera-materia-meta">%s</p>' % esc(meta)) if meta else '', extra)


def grados_con_juegos(materias):
    juegos = [j for m in materias for j in m.juegos]
    return [(g, [j for j in juegos if g[0] in j.grados]) for g in GRADOS
            if any(g[0] in j.grados for j in juegos)]


def edades_con_juegos(materias):
    juegos = [j for m in materias for j in m.juegos]
    return [(f, juegos_de_edad(juegos, f)) for f in EDADES if juegos_de_edad(juegos, f)]


def ruta_grado(grado):
    return 'grados/%s/index.html' % grado[1]


def ruta_edad(franja):
    return 'edades/%s/index.html' % slug_edad(franja)


def titulo_grado(grado):
    return 'Juegos educativos para %s' % grado[3]


EDAD_JOVENES = 13


def quienes(franja):
    return 'jóvenes' if franja[0] >= EDAD_JOVENES else 'niños'


def titulo_edad(franja):
    return 'Juegos educativos para %s de %d a %d años' % ((quienes(franja),) + franja)


def tarjetas_seccion(items):
    """items: (url, icono, título, subtítulo, recuento)."""
    return '<ul class="rejilla-secciones">\n%s\n</ul>' % '\n'.join(
        '  <li><a href="%s"><span class="seccion-icono" aria-hidden="true">%s</span>'
        '<strong>%s</strong><span>%s</span><span class="seccion-recuento">%s</span></a></li>'
        % (url, icono, esc(titulo), esc(sub), esc(n)) for url, icono, titulo, sub, n in items)


def juegos_por_materia(materias, juegos):
    """Secciones de tarjetas, una por materia, con los juegos dados."""
    # Por identidad: comparar juegos con == recorrería materia → juegos → materia sin fin.
    elegidos = {id(j) for j in juegos}
    secciones = []
    for m in materias:
        propios = [j for j in m.juegos if id(j) in elegidos]
        if propios:
            secciones.append("""<section class="tema materia-%s" aria-labelledby="sec-%s">
  <div class="tema-cabeza">
    <h2 id="sec-%s">%s %s</h2>
  </div>
%s
</section>""" % (m.id, m.id, m.id, esc(m.icono), esc(m.nombre), indentar(lista_tarjetas(propios), '  ')))
    return '\n'.join(secciones)


def enlaces_fichas(juegos):
    fichas = [j for j in juegos if tiene_ficha(j)]
    if not fichas:
        return ''
    return """<section class="opcion-offline" aria-labelledby="fichas-seccion">
  <h2 id="fichas-seccion">🖨️ Fichas para imprimir</h2>
  <ul class="lista-fichas">
%s
  </ul>
</section>""" % '\n'.join('    <li><a href="%s">%s %s</a> <span class="detalle">%s</span></li>'
                          % (url_de(ruta_ficha(j)), esc(j.icono), esc(j.titulo), esc(j.materia.nombre))
                          for j in fichas)


def pagina_docentes(materias, v):
    grados = grados_con_juegos(materias)
    tarjetas = tarjetas_seccion([(url_de(ruta_grado(g)), '🎒' if g[0] < PRIMER_GRADO_SECUNDARIA else '🎓',
                                  g[2] if g[0] else 'Transición', g[3].capitalize(),
                                  plural(len(js), 'juego', 'juegos')) for g, js in grados])
    cuerpo = """%s
%s
<main id="contenido" class="pagina">
%s

  <section class="tema" aria-labelledby="por-grado">
    <div class="tema-cabeza">
      <h2 id="por-grado">Recursos por grado</h2>
      <p>Juegos y fichas de todas las materias, organizados según el grado de tus estudiantes.</p>
    </div>
%s
  </section>

  <section class="tema" aria-labelledby="en-clase">
    <div class="tema-cabeza">
      <h2 id="en-clase">Cómo usarlos en clase</h2>
      <p>Ideas que funcionan con un solo computador o con toda la sala de informática.</p>
    </div>
    <ul class="pasos">
      <li><span class="paso-icono" aria-hidden="true">📽️</span><h3>Jugar en grupo</h3><p>Proyecta un juego y que la clase vote cada respuesta antes de marcarla. Las explicaciones abren la discusión.</p></li>
      <li><span class="paso-icono" aria-hidden="true">🖨️</span><h3>Evaluación rápida</h3><p>Imprime la ficha del tema y quita la hoja de respuestas antes de repartirla.</p></li>
      <li><span class="paso-icono" aria-hidden="true">🔁</span><h3>Estaciones</h3><p>Rota a los grupos entre juegos de parejas, de ordenar y fichas en papel.</p></li>
      <li><span class="paso-icono" aria-hidden="true">📥</span><h3>Aula sin internet</h3><p>Instala el sitio en los equipos con conexión una vez, y funcionará después sin ella.</p></li>
    </ul>
  </section>

  <section class="tema" aria-labelledby="recursos-mas">
    <div class="tema-cabeza">
      <h2 id="recursos-mas">Más recursos</h2>
    </div>
    <ul class="lista-fichas">
      <li><a href="/descargar/">📥 Todas las fichas para imprimir y cómo usar el sitio sin internet</a></li>
      <li><a href="/secundaria/">🎓 Juegos interactivos para secundaria</a></li>
      <li><a href="/docentes/curriculo/">📘 Matriz curricular: objetivo, DBA y estándares del MEN de cada juego</a></li>
      <li><a href="https://github.com/Juegoseducativosonline/juegoseducativosonline.github.io/tree/main/contenido">📂 Todas las preguntas en datos abiertos, para adaptarlas</a></li>
    </ul>
  </section>

%s
</main>
%s""" % (bloque_navegacion(materias),
         cabecera_banda([('Inicio', '/'), ('Docentes', None)], '🍎', 'Recursos para docentes',
                        'Juegos educativos, fichas imprimibles con respuestas y actividades por grado. Gratis y sin registro.',
                        '%s · de Transición a %s' % (plural(sum(len(m.juegos) for m in materias), 'recurso', 'recursos'),
                                                     grados[-1][0][2]),
                        '\n    <p class="descargas"><a class="btn btn-blanco" href="#packs-titulo">🖨️ Ver PDF para imprimir</a></p>'),
         indentar(juegos_por_materia(materias, [j for m in materias for j in m.juegos]), '  '),
         indentar(tarjetas, '    '), indentar(seccion_packs(materias), '  '), bloque_pie(materias, v))
    head = cabeza(v, 'Recursos educativos gratis para docentes: juegos y fichas por grado — %s' % NOMBRE_SITIO,
                  'Recursos educativos gratuitos para docentes: juegos interactivos y fichas imprimibles con '
                  'respuestas, organizados por grado de Transición a secundaria.', RUTA_DOCENTES)
    return documento(head, 'pagina-docentes', cuerpo)


def pagina_familias(materias, v):
    edades = edades_con_juegos(materias)
    iconos = ['🧸', '🎈', '🚲', '⚽', '🎧', '🎓']
    tarjetas = tarjetas_seccion([(url_de(ruta_edad(f)), iconos[EDADES.index(f)], '%d a %d años' % f,
                                  ', '.join(GRADO[g][2] for g in range(f[0] - EDAD_EN_TRANSICION,
                                                                        f[1] - EDAD_EN_TRANSICION + 1) if g in GRADO),
                                  plural(len(js), 'actividad', 'actividades')) for f, js in edades])
    cuerpo = """%s
%s
<main id="contenido" class="pagina">
  <section class="tema" aria-labelledby="por-edad">
    <div class="tema-cabeza">
      <h2 id="por-edad">Actividades por edad</h2>
      <p>Elige la edad de tu hijo o hija y encontrarás juegos y fichas pensados para esa etapa.</p>
    </div>
%s
  </section>

  <section class="tema" aria-labelledby="consejos">
    <div class="tema-cabeza">
      <h2 id="consejos">Consejos para acompañar</h2>
      <p>Pequeños hábitos que hacen que el juego se convierta en aprendizaje.</p>
    </div>
    <ul class="pasos">
      <li><span class="paso-icono" aria-hidden="true">⏱️</span><h3>Ratos cortos</h3><p>De 15 a 20 minutos es suficiente. Mejor un poco cada día que mucho de una vez.</p></li>
      <li><span class="paso-icono" aria-hidden="true">💬</span><h3>Juega a su lado</h3><p>Pregúntale por qué eligió una respuesta. Explicarlo en voz alta fija lo aprendido.</p></li>
      <li><span class="paso-icono" aria-hidden="true">🖨️</span><h3>También sin pantalla</h3><p>Cada juego tiene una ficha para imprimir: ideal para el fin de semana o un viaje.</p></li>
      <li><span class="paso-icono" aria-hidden="true">🌟</span><h3>Celebra el esfuerzo</h3><p>Las estrellas miden el progreso, no el valor. Anímale a volver a jugar para mejorar.</p></li>
    </ul>
  </section>

  <section class="tema" aria-labelledby="sin-internet-familias">
    <div class="tema-cabeza">
      <h2 id="sin-internet-familias">Para usar sin internet</h2>
    </div>
    <ul class="lista-fichas">
      <li><a href="/descargar/">📥 Instala los juegos en tu teléfono o tableta y úsalos sin conexión</a></li>
      <li><a href="/emociones/">💛 Juegos de emociones para hablar en familia de lo que sentimos</a></li>
    </ul>
  </section>
</main>
%s""" % (bloque_navegacion(materias),
         cabecera_banda([('Inicio', '/'), ('Familias', None)], '🏠', 'Actividades para hacer en casa',
                        'Juegos educativos y fichas para tus hijos según su edad: gratis, sin registro y también sin internet.'),
         indentar(tarjetas, '    '), bloque_pie(materias, v))
    head = cabeza(v, 'Actividades educativas para niños en casa: juegos y fichas por edad — %s' % NOMBRE_SITIO,
                  'Actividades educativas para hacer en casa con tus hijos: juegos y fichas imprimibles gratis, '
                  'organizados por edad, de 5 a 16 años.', RUTA_FAMILIAS)
    return documento(head, 'pagina-familias', cuerpo)


def navegacion_hermanas(items, actual):
    """Fila de enlaces a los otros grados o edades."""
    return '<nav class="indice-temas" aria-label="Otros">\n  <ul>\n%s\n  </ul>\n</nav>' % '\n'.join(
        '    <li><a href="%s"%s>%s</a></li>' % (url, ' aria-current="page"' if clave == actual else '', esc(texto))
        for clave, url, texto in items)


def pagina_grado(grado, juegos, materias, v):
    hermanas = navegacion_hermanas([(g[0], url_de(ruta_grado(g)), g[2]) for g, _ in grados_con_juegos(materias)],
                                   grado[0])
    edad = grado[0] + EDAD_EN_TRANSICION
    titulo = titulo_grado(grado)
    cuerpo = """%s
%s
<main id="contenido" class="pagina">
%s
%s
</main>
%s""" % (bloque_navegacion(materias),
         cabecera_banda([('Inicio', '/'), ('Docentes', '/docentes/'), (grado[3].capitalize(), None)],
                        '🎒' if grado[0] < PRIMER_GRADO_SECUNDARIA else '🎓', titulo,
                        'Juegos y fichas imprimibles para %s (unos %d años), de todas las materias.' % (grado[3], edad),
                        plural(len(juegos), 'juego', 'juegos'),
                        '\n' + indentar(hermanas, '    ')),
         indentar(juegos_por_materia(materias, juegos), '  '),
         # Primero las actividades; al final, las descargas.
         '  <p class="descargas">%s</p>\n%s' % (enlace_pdf(ruta_pack_grado(grado), '📦 Descargar todas las fichas en PDF',
                                                           'btn btn-acento'), indentar(enlaces_fichas(juegos), '  ')),
         bloque_pie(materias, v))
    head = cabeza(v, '%s — %s' % (titulo, NOMBRE_SITIO),
                  '%s: juegos interactivos y fichas imprimibles gratis de matemáticas, lectura, ciencias y más, '
                  'para usar en clase o en casa.' % titulo, ruta_grado(grado))
    return documento(head, 'pagina-grado', cuerpo)


def pagina_edad(franja, juegos, materias, v):
    hermanas = navegacion_hermanas([(f, url_de(ruta_edad(f)), '%d–%d años' % f) for f, _ in edades_con_juegos(materias)],
                                   franja)
    titulo = titulo_edad(franja)
    cuerpo = """%s
%s
<main id="contenido" class="pagina">
%s
%s
</main>
%s""" % (bloque_navegacion(materias),
         cabecera_banda([('Inicio', '/'), ('Familias', '/familias/'), ('%d a %d años' % franja, None)], '🧒', titulo,
                        'Actividades educativas para hacer en casa con %s de %d a %d años: juegos y fichas para imprimir.'
                        % ((quienes(franja),) + franja), plural(len(juegos), 'actividad', 'actividades'), '\n' + indentar(hermanas, '    ')),
         indentar(juegos_por_materia(materias, juegos), '  '), indentar(enlaces_fichas(juegos), '  '),
         bloque_pie(materias, v))
    head = cabeza(v, '%s — %s' % (titulo, NOMBRE_SITIO),
                  'Actividades y juegos educativos gratis para %s de %d a %d años: lectura, matemáticas, '
                  'emociones, ciencias y fichas para imprimir.' % ((quienes(franja),) + franja), ruta_edad(franja))
    return documento(head, 'pagina-edad', cuerpo)


def pagina_matriz(materias, v):
    fuentes = next(j.curriculo['fuentes_doc'] for m in materias for j in m.juegos)
    secciones = []
    total_dba = total_est = 0
    for m in materias:
        filas = []
        for j in m.juegos:
            c = j.curriculo
            total_dba += len(c['dba'])
            total_est += len(c['estandares'])
            dba = '<br>'.join('<strong>%s</strong> %s' % (esc(etiqueta_dba(r)), esc(r['texto'])) for r in c['dba']) or '—'
            est = '<br>'.join('<strong>%s</strong> %s' % (esc(etiqueta_estandar(r, fuentes)), esc(r['texto']))
                              for r in c['estandares']) or '—'
            filas.append('      <tr><td><a href="%s">%s %s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                         % (url_de(j.ruta), esc(j.icono), esc(j.titulo), esc(etiqueta_grados(j.grados)),
                            esc(c['objetivo']), dba, est))
        secciones.append("""<section class="tema materia-%s" aria-labelledby="mc-%s">
  <div class="tema-cabeza"><h2 id="mc-%s">%s %s</h2></div>
  <div class="tabla-desplazable">
    <table class="tabla-curriculo">
      <thead><tr><th>Juego</th><th>Grados</th><th>Objetivo de aprendizaje</th><th>DBA</th><th>Estándares y orientaciones</th></tr></thead>
      <tbody>
%s
      </tbody>
    </table>
  </div>
</section>""" % (m.id, m.id, m.id, esc(m.icono), esc(m.nombre), '\n'.join(filas)))

    lista_fuentes = '\n'.join('      <li><a href="%s">%s</a></li>' % (esc(f['url']), esc(f['titulo'])) for f in fuentes.values())
    juegos = sum(len(m.juegos) for m in materias)
    cuerpo = """%s
%s
<main id="contenido" class="pagina">
  <p class="nota">Cada juego está alineado con los Derechos Básicos de Aprendizaje (DBA) y con los Estándares Básicos de Competencias del Ministerio de Educación Nacional de Colombia. Los enunciados se citan literalmente de los documentos oficiales. En Tecnología, Inglés de secundaria y Artes, que no tienen DBA, se usan las guías y orientaciones del MEN para esas áreas.</p>
%s
  <section class="opcion-offline" aria-labelledby="fuentes-titulo">
    <h2 id="fuentes-titulo">Documentos oficiales consultados</h2>
    <ul class="lista-fichas">
%s
    </ul>
  </section>
</main>
%s""" % (bloque_navegacion(materias),
         cabecera_banda([('Inicio', '/'), ('Docentes', '/docentes/'), ('Matriz curricular', None)], '📘',
                        'Matriz curricular: DBA y estándares',
                        'Objetivo de aprendizaje, DBA y estándares del MEN de cada juego, para planear clases con confianza.',
                        '%s · %d DBA · %d estándares y orientaciones' % (plural(juegos, 'juego', 'juegos'), total_dba, total_est)),
         indentar('\n'.join(secciones), '  '), lista_fuentes, bloque_pie(materias, v))
    head = cabeza(v, 'Juegos educativos alineados con los DBA y los Estándares del MEN — %s' % NOMBRE_SITIO,
                  'Matriz curricular: cada juego educativo con su objetivo de aprendizaje, los Derechos Básicos de '
                  'Aprendizaje (DBA) y los Estándares Básicos de Competencias del MEN de Colombia.', RUTA_CURRICULO)
    return documento(head, 'pagina-curriculo', cuerpo)


def pagina_pack(titulo, subtitulo, juegos, v, ruta):
    """Pack imprimible: portada con índice y, detrás, cada ficha seguida de su hoja
    de respuestas. tools/pdf.py lo convierte en un único PDF."""
    fichas = [j for j in juegos if tiene_ficha(j)]
    indice = '\n'.join('      <li><strong>%s %s</strong> <span class="detalle">%s · %s</span></li>'
                       % (esc(j.icono), esc(j.titulo), esc(j.materia.nombre), esc(etiqueta_grados(j.grados)))
                       for j in fichas)
    articulos, solucionario = [], []
    for n, j in enumerate(fichas, 1):
        instrucciones, bloques, respuestas = FICHAS[j.tipo](j)
        articulos.append("""<article class="pack-ficha">
  <header class="pack-ficha-cabeza">
    <p class="pack-ficha-num">Ficha %d · %s · %s</p>
    <h2>%s %s</h2>
    <p>%s</p>
  </header>
%s
  <p class="ficha-datos"><span>Nombre:</span><span>Fecha:</span></p>
  <p class="ficha-instrucciones">%s</p>
  <div class="%s">
%s
%s
  </div>
</article>""" % (n, esc(j.materia.nombre), esc(etiqueta_grados(j.grados)), esc(j.icono), esc(j.titulo),
                 esc(j.descripcion), indentar(cabecera_academica(j), '  '), instrucciones, clase_cuerpo(j),
                 indentar('\n'.join(bloques), '    '), indentar(situacion_problema(j, numero_situacion(j)), '    ')))
        if respuestas:
            solucionario.append('<section class="sol-ficha"><h3>Ficha %d · %s %s</h3><ol>%s</ol></section>'
                                % (n, esc(j.icono), esc(j.titulo), ''.join(respuestas)))

    cuerpo = """<main id="contenido" class="pack">
  <section class="pack-portada">
    <p class="pack-marca"><span class="marca-logo" aria-hidden="true">🎮</span> %s</p>
    <h1>%s</h1>
    <p class="pack-subtitulo">%s</p>
    <p class="pack-cifras">%s con objetivo, DBA, indicadores y situación problema · Solucionario al final</p>
    <h2>Contenido</h2>
    <ol class="pack-indice">
%s
    </ol>
    <p class="nota">Juegos y fichas gratuitos en %s · Alineados con los DBA y los Estándares del MEN.</p>
  </section>
%s
  <section class="solucionario">
    <h2>✅ Solucionario para el docente</h2>
%s
  </section>
</main>""" % (esc(NOMBRE_SITIO), esc(titulo), esc(subtitulo), plural(len(fichas), 'ficha', 'fichas'), indice,
              esc(URL_SITIO.replace('https://', '')), indentar('\n'.join(articulos), '  '),
              indentar('\n'.join(solucionario), '    '))
    head = cabeza(v, '%s — %s' % (titulo, NOMBRE_SITIO), subtitulo, ruta, robots='noindex')
    return documento(head, 'pagina-pack', cuerpo)


def packs(materias, v):
    """Packs por grado y por materia: {ruta_html: html}."""
    salida = {}
    for grado, juegos in grados_con_juegos(materias):
        if any(tiene_ficha(j) for j in juegos):
            if grado[0] == 0:
                juegos = [j for j in juegos if j.tipo == 'imprimible']
            salida[ruta_pack_grado(grado)] = pagina_pack(
                'Pack de fichas: %s' % grado[3], 'Fichas de todas las materias para %s.' % grado[3],
                juegos, v, ruta_pack_grado(grado))
    for m in materias:
        salida[ruta_pack_materia(m)] = pagina_pack(
            'Pack de fichas: %s' % m.nombre, 'Todas las fichas de %s, de todos los grados.' % m.nombre,
            m.juegos, v, ruta_pack_materia(m))
    return salida


def seccion_packs(materias):
    """Bloque destacado de descargas en PDF para la página de docentes."""
    por_grado = '\n'.join('      <li>%s</li>' % enlace_pdf(ruta_pack_grado(g), '📦 %s' % (g[2] if g[0] else 'Transición'),
                                                           'btn btn-secundario')
                          for g, js in grados_con_juegos(materias) if any(tiene_ficha(j) for j in js))
    por_materia = '\n'.join('      <li>%s</li>' % enlace_pdf(ruta_pack_materia(m), '%s %s' % (m.icono, m.nombre),
                                                             'btn btn-secundario') for m in materias)
    return """<section class="tema packs-pdf" aria-labelledby="packs-titulo">
  <div class="tema-cabeza">
    <h2 id="packs-titulo">📦 Packs de fichas en PDF</h2>
    <p>Descarga todas las fichas de un grado o de una materia en un solo PDF, listo para imprimir: portada con índice, y cada ficha con su hoja de respuestas, su objetivo y sus DBA.</p>
  </div>
  <h3>Por grado</h3>
  <ul class="lista-descargas">
%s
  </ul>
  <h3>Por materia</h3>
  <ul class="lista-descargas">
%s
  </ul>
</section>""" % (por_grado, por_materia)


def pagina_secundaria(materias, v):
    grupos = []
    total = 0
    for m in materias:
        juegos = [j for j in m.juegos if j.grados[-1] >= PRIMER_GRADO_SECUNDARIA]
        if not juegos:
            continue
        total += len(juegos)
        grupos.append("""<section class="tema materia-%s" aria-labelledby="sec-%s">
  <div class="tema-cabeza">
    <h2 id="sec-%s">%s %s</h2>
  </div>
%s
</section>""" % (m.id, m.id, m.id, esc(m.icono), esc(m.nombre), indentar(lista_tarjetas(juegos), '  ')))

    cuerpo = """%s
<div class="cabecera-materia">
  <div class="cabecera-materia-interior">
%s
    <div class="cabecera-materia-titulo">
      <span class="cabecera-materia-icono" aria-hidden="true">🎓</span>
      <div>
        <h1>Juegos para secundaria</h1>
        <p>Juegos interactivos para jóvenes: relaciona parejas contra el reloj, ordena líneas del tiempo y pon a prueba lo que sabes de química, física, historia, inglés o programación.</p>
      </div>
    </div>
    <p class="cabecera-materia-meta">%s</p>
  </div>
</div>
<main id="contenido" class="pagina">
%s
</main>
%s""" % (bloque_navegacion(materias), indentar(migas_html([('Inicio', '/'), ('Secundaria', None)]), '    '),
         plural(total, 'juego', 'juegos'), indentar('\n'.join(grupos), '  '), bloque_pie(materias, v))

    head = cabeza(v, 'Juegos interactivos para jóvenes de secundaria online — %s' % NOMBRE_SITIO,
                  'Juegos interactivos online gratis para jóvenes de secundaria: parejas, líneas del tiempo y retos '
                  'de química, física, historia, inglés, matemáticas y programación.', RUTA_SECUNDARIA)
    return documento(head, 'pagina-secundaria', cuerpo)


def pagina_descargas(materias, v, version, total_recursos):
    grupos = []
    for m in materias:
        fichas = [j for j in m.juegos if tiene_ficha(j)]
        if not fichas:
            continue
        enlaces = '\n'.join('    <li><a href="%s">%s %s</a> <span class="detalle">%s</span></li>'
                            % (url_de(ruta_ficha(j)), esc(j.icono), esc(j.titulo), esc(j.detalle)) for j in fichas)
        grupos.append('<div class="grupo-fichas materia-%s">\n  <h3><span class="menu-icono" aria-hidden="true">%s</span>%s</h3>\n'
                      '  <ul>\n%s\n  </ul>\n</div>' % (m.id, esc(m.icono), esc(m.nombre), enlaces))

    cuerpo = """%s
<div class="container">
  <header class="header">
    <span class="header-icono" aria-hidden="true">📥</span>
    <h1>Usar sin internet</h1>
    <p>Para jugar en clase, en casa o de viaje, aunque no haya conexión.</p>
  </header>
  <main class="content" id="contenido">
    <section class="opcion-offline" aria-labelledby="app-titulo">
      <h2 id="app-titulo">1. Instalar como aplicación <span class="insignia">Recomendado</span></h2>
      <p>El sitio completo, con todos los juegos, se guarda en el dispositivo y funciona sin conexión. Ocupa muy poco espacio y se actualiza solo la próxima vez que haya internet.</p>
      <p class="estado-offline" id="estado-offline" data-cache="%s" data-total="%d" role="status">Comprobando si este dispositivo ya tiene el sitio guardado…</p>
      <p><button type="button" class="btn hidden" data-instalar>📲 Instalar la aplicación</button></p>
      <ul class="pasos-instalar">
        <li><strong>Android (Chrome):</strong> menú <em>⋮</em> → <em>Instalar aplicación</em> o <em>Añadir a pantalla de inicio</em>.</li>
        <li><strong>iPhone o iPad (Safari):</strong> botón <em>Compartir</em> → <em>Añadir a pantalla de inicio</em>.</li>
        <li><strong>Computadora (Chrome o Edge):</strong> icono de instalar en la barra de direcciones, o menú → <em>Instalar Juegos Educativos</em>.</li>
      </ul>
      <p class="nota">Aunque no la instales, después de visitar el sitio una vez con conexión este navegador también podrá abrirlo sin internet.</p>
    </section>

    <section class="opcion-offline" aria-labelledby="fichas-titulo">
      <h2 id="fichas-titulo">2. Fichas para imprimir o guardar como PDF</h2>
      <p>Cada juego tiene una ficha con espacio para el nombre y la hoja de respuestas en una página aparte, pensada para docentes y familias. Ábrela y pulsa <em>Imprimir o guardar como PDF</em>.</p>
      <div class="rejilla-fichas">
%s
      </div>
      <p class="nota">Los juegos de operaciones (suma, resta, multiplicación y división) generan ejercicios nuevos en cada partida, así que no tienen una ficha fija.</p>
    </section>

    <section class="opcion-offline" aria-labelledby="docentes-titulo">
      <h2 id="docentes-titulo">3. Para docentes: todo el contenido</h2>
      <p>Todas las preguntas están en archivos de datos abiertos, listos para reutilizar o adaptar.</p>
      <ul class="pasos-instalar">
        <li><a href="https://github.com/Juegoseducativosonline/juegoseducativosonline.github.io/tree/main/contenido">Ver las preguntas en GitHub</a> (un archivo por juego).</li>
        <li><a href="https://github.com/Juegoseducativosonline/juegoseducativosonline.github.io/archive/refs/heads/main.zip">Descargar todo el sitio en un ZIP</a>. Para abrirlo sin internet hace falta un pequeño servidor local; por ejemplo, con Python instalado, ejecuta <code>python -m http.server</code> dentro de la carpeta y abre <code>http://localhost:8000</code>.</li>
      </ul>
    </section>
  </main>
</div>
%s""" % (bloque_navegacion(materias, migas=[('Inicio', '/'), ('Usar sin internet', None)]), version, total_recursos,
         indentar('\n'.join(grupos), '        '), bloque_pie(materias, v))

    head = cabeza(v, 'Usar sin internet y fichas para imprimir — %s' % NOMBRE_SITIO,
                  'Instala los juegos educativos para usarlos sin conexión o descarga fichas para imprimir con sus respuestas.',
                  RUTA_DESCARGAS)
    return documento(head, 'pagina-descargas', cuerpo)


def manifiesto():
    datos = {
        'name': NOMBRE_SITIO,
        'short_name': 'Juegos Educativos',
        'description': 'Juegos educativos gratuitos de matemáticas, lectura, ciencias, inglés y más.',
        'lang': 'es',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'background_color': '#f4f6fb',
        'theme_color': COLOR_MARCA,
        'icons': [
            {'src': '/assets/icono-192.png', 'sizes': '192x192', 'type': 'image/png'},
            {'src': '/assets/icono-512.png', 'sizes': '512x512', 'type': 'image/png'},
            {'src': '/assets/icono-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
    }
    return json.dumps(datos, ensure_ascii=False, indent=2) + '\n'


PLANTILLA_SW = r"""/* __MARCA__. No lo edites a mano. */
/*
 * Guarda el sitio completo en el dispositivo para que funcione sin internet.
 * El nombre de la caché cambia con cada versión publicada: el navegador
 * descarga la nueva y borra la anterior.
 */
'use strict';

var CACHE = '__VERSION__';
var RECURSOS = __RECURSOS__;
var FUENTES = /^https:\/\/fonts\.(googleapis|gstatic)\.com\//;

self.addEventListener('install', function (evento) {
  evento.waitUntil(caches.open(CACHE).then(function (cache) {
    return cache.addAll(RECURSOS);
  }).then(function () {
    return self.skipWaiting();
  }));
});

self.addEventListener('activate', function (evento) {
  evento.waitUntil(caches.keys().then(function (nombres) {
    return Promise.all(nombres.filter(function (n) {
      return n.indexOf('jeo-') === 0 && n !== CACHE;
    }).map(function (n) {
      return caches.delete(n);
    }));
  }).then(function () {
    return self.clients.claim();
  }));
});

self.addEventListener('fetch', function (evento) {
  var peticion = evento.request;
  if (peticion.method !== 'GET') {
    return;
  }

  /* Páginas: primero la red, para ver siempre lo último; sin conexión, la copia guardada. */
  if (peticion.mode === 'navigate') {
    evento.respondWith(fetch(peticion.url, { cache: 'no-cache' }).catch(function () {
      return caches.match(peticion, { ignoreSearch: true }).then(function (guardada) {
        return guardada || caches.match('/404.html');
      });
    }));
    return;
  }

  /* Tipografía de Google: se guarda la primera vez que se usa. */
  if (FUENTES.test(peticion.url)) {
    evento.respondWith(caches.open(CACHE).then(function (cache) {
      return cache.match(peticion).then(function (guardada) {
        return guardada || fetch(peticion).then(function (respuesta) {
          cache.put(peticion, respuesta.clone());
          return respuesta;
        });
      });
    }));
    return;
  }

  /* Estilos, scripts e iconos llevan su versión en la URL: la copia guardada siempre vale. */
  if (new URL(peticion.url).origin === self.location.origin) {
    evento.respondWith(caches.match(peticion).then(function (guardada) {
      return guardada || fetch(peticion);
    }));
  }
});
"""


def service_worker(version, recursos):
    return (PLANTILLA_SW.replace('__MARCA__', MARCA_GENERADO).replace('__VERSION__', version)
            .replace('__RECURSOS__', json.dumps(recursos, indent=2)))


def sitemap(materias):
    rutas = (['index.html', RUTA_DOCENTES, RUTA_CURRICULO, RUTA_FAMILIAS, RUTA_SECUNDARIA, RUTA_DESCARGAS]
             + [ruta_grado(g) for g, _ in grados_con_juegos(materias)]
             + [ruta_edad(f) for f, _ in edades_con_juegos(materias)]
             + ['%s/index.html' % m.id for m in materias]
             + [j.ruta for m in materias for j in m.juegos])
    urls = '\n'.join('  <url><loc>%s%s</loc></url>' % (URL_SITIO, esc(url_de(r))) for r in rutas)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<!-- %s. No lo edites a mano. -->\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n'
            % (MARCA_GENERADO, urls))


def parchear_interactivo(juego, materias, v):
    """Actualiza los bloques generados de una página hecha a mano, sin tocar el resto."""
    ruta = RAIZ / juego.ruta
    texto = ruta.read_text(encoding='utf-8')
    bloques = {
        'comun': bloque_comun(v),
        'navegacion': bloque_navegacion(materias, migas=migas_de(juego), docente=bloque_curriculo(juego, 'superior')),
        'pie': bloque_pie(materias, v, juego),
    }
    for nombre, contenido in bloques.items():
        patron = re.compile(r'^([ \t]*)<!-- generado:%s -->.*?<!-- /generado:%s -->' % (nombre, nombre),
                            re.S | re.M)
        texto = patron.sub(lambda m: indentar(bloque(nombre, contenido), m.group(1)), texto, count=1)

    texto, cambios = re.subn(r'<body[^>]*>', '<body class="materia-%s">' % juego.materia.id, texto, count=1)
    if cambios != 1:
        raise ErrorContenido('%s: no se encontró la etiqueta <body>.' % juego.ruta)
    return texto


# --- Escritura -----------------------------------------------------------------

class Escritor:
    def __init__(self, comprobar):
        self.comprobar = comprobar
        self.cambiados = []

    def escribir(self, ruta_rel, contenido, generado=True):
        ruta = RAIZ / ruta_rel
        actual = ruta.read_text(encoding='utf-8') if ruta.exists() else None
        # Protege páginas hechas a mano de ser machacadas por error.
        if generado and actual is not None and MARCA_GENERADO not in actual and not ruta_rel.endswith('.webmanifest'):
            raise ErrorContenido('%s ya existe y no lo generó este script. Si debe generarse, bórralo '
                                 'primero; si es una página hecha a mano, cambia la ruta del juego.' % ruta_rel)
        if actual == contenido:
            return
        self.cambiados.append(ruta_rel)
        if not self.comprobar:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            with open(ruta, 'w', encoding='utf-8', newline='\n') as f:
                f.write(contenido)


def generar(comprobar):
    materias = cargar_catalogo()
    juegos = [j for m in materias for j in m.juegos]
    con_datos = [j for j in juegos if tiene_ficha(j)]

    rutas_juegos = {j.ruta for j in juegos}
    for j in con_datos:
        if ruta_ficha(j) in rutas_juegos:
            raise ErrorContenido('La ficha de %s (%s) coincide con la ruta de otro juego.' % (j.ruta, ruta_ficha(j)))

    css_materias = materias_css(materias)
    recursos = {nombre: (RAIZ / 'assets' / nombre).read_text(encoding='utf-8')
                for nombre in {'site.css', 'site.js'} | {n for css, js, _ in MOTORES.values() for n in css + (js,)}}
    recursos['materias.css'] = css_materias
    v = Versiones(recursos)

    salida = {'assets/materias.css': css_materias, 'manifest.webmanifest': manifiesto(),
              'index.html': pagina_inicio(materias, v), '404.html': pagina_404(materias, v),
              'sitemap.xml': sitemap(materias), RUTA_SECUNDARIA: pagina_secundaria(materias, v),
              RUTA_DOCENTES: pagina_docentes(materias, v), RUTA_FAMILIAS: pagina_familias(materias, v),
              RUTA_CURRICULO: pagina_matriz(materias, v)}
    salida.update(packs(materias, v))
    for grado, juegos_grado in grados_con_juegos(materias):
        salida[ruta_grado(grado)] = pagina_grado(grado, juegos_grado, materias, v)
    for franja, juegos_edad in edades_con_juegos(materias):
        salida[ruta_edad(franja)] = pagina_edad(franja, juegos_edad, materias, v)
    for m in materias:
        salida['%s/index.html' % m.id] = pagina_materia(m, materias, v)
    for j in con_datos:
        salida[j.ruta] = pagina_juego(j, materias, v)
        salida[ruta_ficha(j)] = pagina_ficha(j, materias, v)
    interactivos = {j.ruta: parchear_interactivo(j, materias, v) for j in juegos if j.tipo == 'interactivo'}

    # Lo que la aplicación guarda para funcionar sin internet: todas las páginas,
    # los recursos versionados y los iconos.
    # Los packs son grandes y solo sirven para imprimir: no se guardan para uso sin conexión.
    paginas = [r for r in list(salida) + list(interactivos)
               if r.endswith('.html') and not r.startswith('packs/')] + [RUTA_DESCARGAS]
    lista = sorted({url_de(r) for r in paginas} | {v.url(n) for n in recursos} |
                   {'/assets/favicon.svg', '/assets/icono-192.png', '/assets/icono-512.png',
                    '/assets/icono-180.png', '/manifest.webmanifest'})

    # La versión resume todo lo publicado: cualquier cambio renueva la copia sin conexión.
    huella = hashlib.sha256()
    for ruta, contenido in sorted(list(salida.items()) + list(interactivos.items())):
        huella.update(ruta.encode('utf-8') + contenido.encode('utf-8'))
    for icono in sorted((RAIZ / 'assets').glob('icono-*.png')):
        huella.update(icono.read_bytes())
    # La página de descargas lleva dentro la versión, así que se resume sin ella.
    huella.update(pagina_descargas(materias, v, '', 0).encode('utf-8'))
    version = 'jeo-' + huella.hexdigest()[:12]

    salida[RUTA_DESCARGAS] = pagina_descargas(materias, v, version, len(lista))
    salida['sw.js'] = service_worker(version, lista)

    e = Escritor(comprobar)
    for ruta, contenido in salida.items():
        e.escribir(ruta, contenido)
    for ruta, contenido in interactivos.items():
        e.escribir(ruta, contenido, generado=False)
    return materias, e.cambiados


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--comprobar', action='store_true',
                        help='no escribe nada; termina con error si algún archivo generado está desactualizado')
    args = parser.parse_args()

    try:
        materias, cambiados = generar(args.comprobar)
    except ErrorContenido as error:
        print('Error en el contenido: %s' % error, file=sys.stderr)
        return 1

    juegos = sum(len(m.juegos) for m in materias)
    if args.comprobar:
        if cambiados:
            print('Desactualizados (ejecuta python tools/generar.py):', file=sys.stderr)
            for ruta in cambiados:
                print('  ' + ruta, file=sys.stderr)
            return 1
        print('Todo al día: %d materias, %d juegos.' % (len(materias), juegos))
        return 0

    print('%d materias, %d juegos. Archivos actualizados: %d' % (len(materias), juegos, len(cambiados)))
    for ruta in cambiados:
        print('  ' + ruta)
    return 0


if __name__ == '__main__':
    sys.exit(main())
