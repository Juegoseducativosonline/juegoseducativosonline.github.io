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
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

RAIZ = Path(__file__).resolve().parent.parent
CONTENIDO = RAIZ / 'contenido'

URL_SITIO = 'https://juegoseducativosonline.github.io'
NOMBRE_SITIO = 'Juegos Educativos Online'
NIVELES = ('Primaria', 'Secundaria')
FUENTES = 'https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap'
MAX_RELACIONADOS = 3

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
    nivel: str
    detalle: str         # '8 preguntas' o 'Interactivo'
    datos: Optional[dict] = None   # solo en los quiz: lo que se incrusta en la página
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


def nivel_valido(obj, donde):
    nivel = texto_obligatorio(obj, 'nivel', donde)
    if nivel not in NIVELES:
        raise ErrorContenido('%s: el nivel debe ser %s, no "%s".' % (donde, ' o '.join(NIVELES), nivel))
    return nivel


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
        nivel=nivel_valido(datos, donde),
        detalle=plural(len(preguntas), 'pregunta', 'preguntas'),
        datos={'mezclarPreguntas': mezclar_preguntas, 'pasajes': pasajes, 'preguntas': preguntas},
    )


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
        nivel=nivel_valido(crudo, donde),
        detalle='Interactivo',
    )


def cargar_catalogo():
    catalogo = leer_json(CONTENIDO / 'catalogo.json')
    materias = []
    rutas = {}

    for i, cruda in enumerate(lista_obligatoria(catalogo, 'materias', 'catalogo.json'), 1):
        mid = id_valido(cruda, 'catalogo.json, materia %d' % i)
        donde = 'catalogo.json, materia "%s"' % mid
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
                          colores['base'], texto_obligatorio(cruda, 'descripcion', donde), [])

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
                if tipo == 'quiz':
                    archivo = texto_obligatorio(juego_crudo, 'datos', donde_juego)
                    if not archivo.endswith('.json'):
                        raise ErrorContenido('%s: "datos" debe apuntar a un archivo .json.' % donde_juego)
                    juego = cargar_quiz(CONTENIDO / archivo, donde_juego)
                elif tipo == 'interactivo':
                    juego = cargar_interactivo(juego_crudo, donde_juego)
                else:
                    raise ErrorContenido('%s: tipo de juego desconocido %r; usa "quiz" o "interactivo".'
                                         % (donde_juego, tipo))

                # Cada juego vive en la carpeta de su materia; así la URL dice a qué materia pertenece.
                if not juego.ruta.startswith(mid + '/') or juego.ruta == mid + '/index.html':
                    raise ErrorContenido('%s: %s debe estar dentro de la carpeta %s/ y no llamarse index.html.'
                                         % (donde_juego, juego.ruta, mid))
                if juego.ruta in rutas:
                    raise ErrorContenido('%s: %s ya lo usa otro juego (%s).'
                                         % (donde_juego, juego.ruta, rutas[juego.ruta]))
                rutas[juego.ruta] = donde_juego

                juego.materia, juego.tema = materia, tema
                tema.juegos.append(juego)
            materia.temas.append(tema)
        materias.append(materia)

    return materias


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


def bloque_navegacion(materias, actual=None, migas=None):
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
    <a class="marca" href="/"><span class="marca-logo" aria-hidden="true">🎮</span>Juegos Educativos</a>
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
    <span class="tarjeta-juego-pie"><span>%s</span><span class="tarjeta-juego-cta" aria-hidden="true">Jugar →</span></span>
  </a>
</li>''' % (j.materia.id, url_de(j.ruta), esc(j.icono), esc(j.nivel), esc(j.titulo),
            esc(j.descripcion), esc(j.detalle))


def lista_tarjetas(juegos, clase='rejilla-juegos'):
    return '<ul class="%s">\n%s\n</ul>' % (clase, indentar('\n'.join(tarjeta_juego(j) for j in juegos), '  '))


def bloque_pie(materias, v, juego=None):
    partes = []
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
      <a class="marca" href="/"><span class="marca-logo" aria-hidden="true">🎮</span>Juegos Educativos</a>
      <p>Juegos gratuitos para aprender en casa o en clase, desde cualquier dispositivo y sin registrarse.</p>
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
    descripcion = ('Juegos educativos gratuitos de %s. Para primaria y secundaria, '
                   'sin registro y desde cualquier dispositivo.' % nombres)

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
        <p class="portada-etiqueta">Gratis · Sin registro · Primaria y secundaria</p>
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

  <section class="seccion" id="materias" aria-labelledby="materias-titulo">
    <div class="seccion-cabeza">
      <h2 id="materias-titulo">Elige una materia</h2>
      <p>Cada materia está organizada por temas. Empieza por el que quieras.</p>
    </div>
    <ul class="rejilla-materias">
%s
    </ul>
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

    head = cabeza(v, '%s — Aprende jugando' % NOMBRE_SITIO, descripcion, 'index.html')
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

    head = cabeza(v, '%s — %s' % (materia.nombre, NOMBRE_SITIO),
                  '%s Juegos educativos gratuitos de %s por temas.' % (materia.descripcion, materia.nombre.lower()),
                  materia.id + '/index.html')
    return documento(head, 'materia-%s' % materia.id, cuerpo)


def migas_de(juego):
    return [('Inicio', '/'), (juego.materia.nombre, '/%s/' % juego.materia.id),
            (juego.tema.nombre, '/%s/#tema-%s' % (juego.materia.id, juego.tema.id)), (juego.titulo, None)]


def json_para_script(datos):
    """JSON seguro dentro de <script>: sin '<' literal, ningún texto puede cerrar la etiqueta."""
    texto = json.dumps(datos, ensure_ascii=False, separators=(',', ':'))
    return texto.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def pagina_quiz(juego, materias, v):
    cuerpo = '''%s
<div class="container">
  <header class="header">
    <span class="header-icono" aria-hidden="true">%s</span>
    <h1>%s</h1>
    <p>%s</p>
    <p class="header-meta"><span class="insignia insignia-clara">%s</span><span>%s</span></p>
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
  JEO.cargarQuiz(document.getElementById('quiz'), document.getElementById('datos-quiz'));
</script>''' % (bloque_navegacion(materias, migas=migas_de(juego)), esc(juego.icono), esc(juego.titulo),
                esc(juego.descripcion), esc(juego.nivel), esc(juego.detalle),
                bloque_pie(materias, v, juego), v.url('quiz.js'), json_para_script(juego.datos))

    head = cabeza(v, '%s — %s' % (juego.titulo, NOMBRE_SITIO), juego.descripcion, juego.ruta,
                  tipo_og='article', estilos=('quiz.css',))
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


def sitemap(materias):
    rutas = ['index.html'] + ['%s/index.html' % m.id for m in materias] + [j.ruta for m in materias for j in m.juegos]
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
        'navegacion': bloque_navegacion(materias, migas=migas_de(juego)),
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
        if generado and actual is not None and MARCA_GENERADO not in actual:
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

    css_materias = materias_css(materias)
    recursos = {nombre: (RAIZ / 'assets' / nombre).read_text(encoding='utf-8')
                for nombre in ('site.css', 'quiz.css', 'site.js', 'quiz.js')}
    recursos['materias.css'] = css_materias
    v = Versiones(recursos)

    e = Escritor(comprobar)
    e.escribir('assets/materias.css', css_materias)
    e.escribir('index.html', pagina_inicio(materias, v))
    e.escribir('404.html', pagina_404(materias, v))
    e.escribir('sitemap.xml', sitemap(materias))
    for m in materias:
        e.escribir('%s/index.html' % m.id, pagina_materia(m, materias, v))
        for j in m.juegos:
            if j.tipo == 'quiz':
                e.escribir(j.ruta, pagina_quiz(j, materias, v))
            else:
                e.escribir(j.ruta, parchear_interactivo(j, materias, v), generado=False)
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
