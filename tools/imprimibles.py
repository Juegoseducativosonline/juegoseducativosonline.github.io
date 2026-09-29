"""Actividades imprimibles para Transición (4 y 5 años): trazar, colorear, contar,
encerrar, unir y completar series. Casi sin texto: cada actividad lleva un icono
y una consigna corta pensada para que la lea un adulto.

Todo se dibuja con SVG generado aquí (sin imágenes externas), en trazo negro
sobre blanco para que se imprima bien y se pueda colorear.

Lo usa tools/generar.py; cada actividad es un dict con "tipo" y sus datos.
"""

import html
import math

ANCHO = 600
TRAZO_GUIA = 'stroke="#9aa3b5" stroke-width="5" stroke-linecap="round" stroke-dasharray="2 10" fill="none"'
CONTORNO = 'stroke="#222" stroke-width="4" fill="#fff" stroke-linejoin="round"'
FUENTE_TRAZO = "font-family=\"'Nunito', 'Segoe UI', Arial, sans-serif\""

COLORES = {'rojo': '#e03131', 'azul': '#1c7ed6', 'amarillo': '#fab005', 'verde': '#2f9e44',
           'naranja': '#f76707', 'morado': '#7048e8', 'café': '#8d5524', 'rosado': '#e64980'}

ICONOS = {'trazar_lineas': '✏️', 'trazar_letras': '✏️', 'trazar_numeros': '✏️', 'colorear_formas': '🖍️',
          'dibujo_colorear': '🖍️', 'contar_colorear': '🔢', 'encerrar': '⭕', 'unir': '🔗',
          'completar_serie': '🧩'}


class ErrorActividad(Exception):
    pass


def esc(t):
    return html.escape(str(t), quote=True)


def svg(alto, contenido, etiqueta):
    return ('<svg class="act-svg" viewBox="0 0 %d %d" role="img" aria-label="%s" xmlns="http://www.w3.org/2000/svg">%s</svg>'
            % (ANCHO, alto, esc(etiqueta), contenido))


def emoji(x, y, texto, tam=40):
    return ('<text x="%d" y="%d" font-size="%d" text-anchor="middle" dominant-baseline="central">%s</text>'
            % (x, y, tam, esc(texto)))


# --- Trazos ----------------------------------------------------------------------------------

def camino(patron, y, x0=80, x1=520):
    ancho = x1 - x0
    if patron == 'rectas':
        return 'M %d %d H %d' % (x0, y, x1)
    if patron == 'zigzag':
        pasos = 10
        puntos = ['%d %d' % (x0 + ancho * i / pasos, y + (-22 if i % 2 else 22)) for i in range(pasos + 1)]
        return 'M ' + ' L '.join(puntos)
    if patron == 'ondas':
        pasos = 6
        d = 'M %d %d' % (x0, y)
        for i in range(pasos):
            xa = x0 + ancho * (i + 0.5) / pasos
            xb = x0 + ancho * (i + 1) / pasos
            d += ' Q %d %d %d %d' % (xa, y + (-40 if i % 2 == 0 else 40), xb, y)
        return d
    if patron == 'arcos':
        pasos = 6
        radio = ancho / pasos / 2
        d = 'M %d %d' % (x0, y + 15)
        for i in range(pasos):
            d += ' A %d %d 0 0 1 %d %d' % (radio, radio, x0 + ancho * (i + 1) / pasos, y + 15)
        return d
    if patron == 'escalones':
        pasos = 8
        d = 'M %d %d' % (x0, y + 20)
        for i in range(pasos):
            xa = x0 + ancho * i / pasos
            xb = x0 + ancho * (i + 1) / pasos
            alto = y - 20 if i % 2 == 0 else y + 20
            d += ' V %d H %d' % (alto, xb)
        return d
    raise ErrorActividad('patrón de trazo desconocido: %r' % patron)


def trazar_lineas(a):
    filas = a['filas']
    alto = 110 * len(filas) + 10
    partes = []
    for i, f in enumerate(filas):
        y = 60 + i * 110
        partes.append('<path d="%s" %s/>' % (camino(f['patron'], y), TRAZO_GUIA))
        partes.append('<circle cx="80" cy="%d" r="7" fill="#2f9e44"/>' % (y + (15 if f['patron'] == 'arcos' else
                                                                             20 if f['patron'] == 'escalones' else
                                                                             22 if f['patron'] == 'zigzag' else 0)))
        partes.append(emoji(40, y, f['inicio'], 40))
        partes.append(emoji(562, y, f['fin'], 40))
    return svg(alto, ''.join(partes), 'Líneas punteadas para repasar')


def trazar_caracteres(caracteres, etiqueta):
    """Una fila por carácter: modelo relleno y cuatro copias punteadas para repasar."""
    alto = 130 * len(caracteres) + 10
    partes = []
    for i, c in enumerate(caracteres):
        y = 105 + i * 130
        partes.append('<line x1="20" y1="%d" x2="580" y2="%d" stroke="#e1e5ee" stroke-width="2"/>' % (y + 4, y + 4))
        partes.append('<text x="70" y="%d" font-size="100" font-weight="800" text-anchor="middle" fill="#222" %s>%s</text>'
                      % (y, FUENTE_TRAZO, esc(c)))
        for k in range(4):
            partes.append('<text x="%d" y="%d" font-size="100" font-weight="800" text-anchor="middle" fill="none" '
                          'stroke="#8a93a6" stroke-width="2.5" stroke-dasharray="4 6" %s>%s</text>'
                          % (190 + k * 110, y, FUENTE_TRAZO, esc(c)))
    return svg(alto, ''.join(partes), etiqueta)


def trazar_letras(a):
    return trazar_caracteres(list(a['letras']), 'Letras punteadas para repasar')


def trazar_numeros(a):
    return trazar_caracteres([str(n) for n in a['numeros']], 'Números punteados para repasar')


# --- Formas ---------------------------------------------------------------------------------------

def forma(nombre, cx, cy, t=40):
    if nombre == 'circulo':
        return '<circle cx="%d" cy="%d" r="%d" %s/>' % (cx, cy, t, CONTORNO)
    if nombre == 'cuadrado':
        return '<rect x="%d" y="%d" width="%d" height="%d" %s/>' % (cx - t, cy - t, 2 * t, 2 * t, CONTORNO)
    if nombre == 'rectangulo':
        return '<rect x="%d" y="%d" width="%d" height="%d" %s/>' % (cx - 1.4 * t, cy - 0.8 * t, 2.8 * t, 1.6 * t, CONTORNO)
    if nombre == 'triangulo':
        return '<polygon points="%d,%d %d,%d %d,%d" %s/>' % (cx, cy - t, cx - t, cy + t * 0.8, cx + t, cy + t * 0.8, CONTORNO)
    if nombre == 'estrella':
        puntos = []
        for k in range(10):
            r = t if k % 2 == 0 else t * 0.45
            ang = -math.pi / 2 + k * math.pi / 5
            puntos.append('%.1f,%.1f' % (cx + r * math.cos(ang), cy + r * math.sin(ang)))
        return '<polygon points="%s" %s/>' % (' '.join(puntos), CONTORNO)
    if nombre == 'corazon':
        return ('<path d="M %d %d C %d %d %d %d %d %d C %d %d %d %d %d %d Z" %s/>'
                % (cx, cy + t, cx - 1.6 * t, cy - 0.2 * t, cx - 0.7 * t, cy - 1.3 * t, cx, cy - 0.5 * t,
                   cx + 0.7 * t, cy - 1.3 * t, cx + 1.6 * t, cy - 0.2 * t, cx, cy + t, CONTORNO))
    raise ErrorActividad('forma desconocida: %r' % nombre)


NOMBRE_FORMA = {'circulo': 'círculos', 'cuadrado': 'cuadrados', 'rectangulo': 'rectángulos',
                'triangulo': 'triángulos', 'estrella': 'estrellas', 'corazon': 'corazones'}


def colorear_formas(a):
    """Formas mezcladas; una leyenda con muestras de color dice cómo pintar cada una."""
    orden = a['formas']
    por_fila = 5
    filas = (len(orden) + por_fila - 1) // por_fila
    alto = 110 * filas + 70
    partes = []
    # Leyenda: muestra de color + forma pequeña, para quien aún no lee.
    colores = a['colores']
    x = 30
    for f, color in colores.items():
        if color not in COLORES:
            raise ErrorActividad('color desconocido: %r' % color)
        partes.append('<rect x="%d" y="12" width="34" height="34" rx="6" fill="%s"/>' % (x, COLORES[color]))
        partes.append(forma(f, x + 62, 29, 14))
        x += 120
    for i, f in enumerate(orden):
        cx = 70 + (i % por_fila) * 115
        cy = 120 + (i // por_fila) * 110
        partes.append(forma(f, cx, cy, 38))
    return svg(alto, ''.join(partes), 'Formas para colorear según la leyenda')


# --- Dibujos para colorear --------------------------------------------------------------------------

def dibujo(nombre, cx, cy):
    c = CONTORNO
    if nombre == 'casa':
        return ('<rect x="%d" y="%d" width="140" height="110" %s/>'
                '<polygon points="%d,%d %d,%d %d,%d" %s/>'
                '<rect x="%d" y="%d" width="36" height="60" %s/>'
                '<rect x="%d" y="%d" width="34" height="34" %s/>'
                % (cx - 70, cy - 20, c, cx - 88, cy - 18, cx, cy - 95, cx + 88, cy - 18, c,
                   cx - 18, cy + 30, c, cx + 25, cy + 5, c))
    if nombre == 'sol':
        rayos = ''.join('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#222" stroke-width="4" stroke-linecap="round"/>'
                        % (cx + 58 * math.cos(k * math.pi / 6), cy + 58 * math.sin(k * math.pi / 6),
                           cx + 85 * math.cos(k * math.pi / 6), cy + 85 * math.sin(k * math.pi / 6)) for k in range(12))
        return rayos + ('<circle cx="%d" cy="%d" r="48" %s/>'
                        '<circle cx="%d" cy="%d" r="5" fill="#222"/><circle cx="%d" cy="%d" r="5" fill="#222"/>'
                        '<path d="M %d %d Q %d %d %d %d" stroke="#222" stroke-width="4" fill="none" stroke-linecap="round"/>'
                        % (cx, cy, c, cx - 16, cy - 10, cx + 16, cy - 10, cx - 20, cy + 14, cx, cy + 30, cx + 20, cy + 14))
    if nombre == 'arbol':
        return ('<rect x="%d" y="%d" width="34" height="80" %s/>'
                '<circle cx="%d" cy="%d" r="45" %s/><circle cx="%d" cy="%d" r="45" %s/><circle cx="%d" cy="%d" r="50" %s/>'
                % (cx - 17, cy + 20, c, cx - 40, cy - 10, c, cx + 40, cy - 10, c, cx, cy - 50, c))
    if nombre == 'flor':
        petalos = ''.join('<circle cx="%.1f" cy="%.1f" r="24" %s/>'
                          % (cx + 34 * math.cos(k * math.pi / 3), cy - 40 + 34 * math.sin(k * math.pi / 3), c)
                          for k in range(6))
        return ('<path d="M %d %d V %d" stroke="#222" stroke-width="5"/>'
                '<ellipse cx="%d" cy="%d" rx="26" ry="12" transform="rotate(-30 %d %d)" %s/>'
                % (cx, cy - 20, cy + 90, cx + 24, cy + 45, cx + 24, cy + 45, c)
                + petalos + '<circle cx="%d" cy="%d" r="22" %s/>' % (cx, cy - 40, c))
    if nombre == 'pez':
        return ('<polygon points="%d,%d %d,%d %d,%d" %s/>'
                '<ellipse cx="%d" cy="%d" rx="80" ry="48" %s/>'
                '<circle cx="%d" cy="%d" r="8" fill="#222"/>'
                '<path d="M %d %d Q %d %d %d %d" stroke="#222" stroke-width="4" fill="none"/>'
                % (cx + 60, cy, cx + 115, cy - 42, cx + 115, cy + 42, c, cx - 10, cy, c, cx - 50, cy - 10,
                   cx - 5, cy - 40, cx + 15, cy, cx - 5, cy + 40))
    if nombre == 'manzana':
        return ('<path d="M %d %d C %d %d %d %d %d %d C %d %d %d %d %d %d Z" %s/>'
                '<path d="M %d %d Q %d %d %d %d" stroke="#222" stroke-width="5" fill="none"/>'
                '<ellipse cx="%d" cy="%d" rx="22" ry="10" transform="rotate(-25 %d %d)" %s/>'
                % (cx, cy - 45, cx - 110, cy - 95, cx - 95, cy + 95, cx, cy + 70,
                   cx + 95, cy + 95, cx + 110, cy - 95, cx, cy - 45, c,
                   cx, cy - 45, cx + 4, cy - 75, cx + 14, cy - 88, cx + 32, cy - 72, cx + 32, cy - 72, c))
    if nombre == 'globo':
        return ('<path d="M %d %d Q %d %d %d %d" stroke="#222" stroke-width="3" fill="none"/>'
                '<ellipse cx="%d" cy="%d" rx="55" ry="70" %s/>'
                '<polygon points="%d,%d %d,%d %d,%d" %s/>'
                % (cx, cy + 32, cx - 25, cy + 70, cx, cy + 100, cx, cy - 40, c, cx, cy + 30, cx - 9, cy + 42, cx + 9, cy + 42, c))
    raise ErrorActividad('dibujo desconocido: %r' % nombre)


def dibujo_colorear(a):
    dibujos = a['dibujos']
    alto = 280
    paso = ANCHO / len(dibujos)
    partes = [dibujo(d, int(paso * (i + 0.5)), 140) for i, d in enumerate(dibujos)]
    return svg(alto, ''.join(partes), 'Dibujos para colorear')


# --- Contar, encerrar, unir, series ------------------------------------------------------------------

def contar_colorear(a):
    filas = a['filas']
    alto = 90 * len(filas) + 10
    partes = []
    for i, f in enumerate(filas):
        y = 50 + i * 90
        n = f['cantidad']
        if not 1 <= n <= 5:
            raise ErrorActividad('contar_colorear admite de 1 a 5 dibujos por fila')
        for k in range(n):
            partes.append(emoji(40 + k * 50, y, f['emoji'], 38))
        partes.append('<line x1="290" y1="%d" x2="290" y2="%d" stroke="#e1e5ee" stroke-width="2"/>' % (y - 35, y + 35))
        for k in range(5):
            partes.append('<circle cx="%d" cy="%d" r="20" stroke="#222" stroke-width="3" fill="#fff"/>' % (330 + k * 55, y))
    return svg(alto, ''.join(partes), 'Dibujos para contar y círculos para colorear')


def encerrar(a):
    """Cada fila: una pregunta corta y varios dibujos (con tamaño opcional)."""
    filas = a['filas']
    alto = 120 * len(filas) + 10
    partes = []
    for i, f in enumerate(filas):
        y = 70 + i * 120
        items = f['items']
        partes.append('<text x="22" y="%d" font-size="26" font-weight="800" text-anchor="middle" '
                      'dominant-baseline="central" fill="#555" %s>%d</text>' % (y, FUENTE_TRAZO, i + 1))
        paso = (ANCHO - 60) / len(items)
        for k, it in enumerate(items):
            texto, tam = (it[0], it[1]) if isinstance(it, list) else (it, 56)
            partes.append(emoji(int(60 + paso * (k + 0.5)), y, texto, tam))
    return svg(alto, ''.join(partes), 'Dibujos para encerrar')


def unir(a):
    pares = a['pares']
    orden = a.get('orden_derecha') or list(range(len(pares)))[::-1]
    alto = 100 * len(pares) + 10
    partes = []
    for i, (izq, _) in enumerate(pares):
        y = 55 + i * 100
        partes.append(emoji(90, y, izq, 52))
        partes.append('<circle cx="160" cy="%d" r="8" fill="#222"/>' % y)
    for i, k in enumerate(orden):
        y = 55 + i * 100
        partes.append('<circle cx="440" cy="%d" r="8" fill="#222"/>' % y)
        partes.append(emoji(510, y, pares[k][1], 52))
    return svg(alto, ''.join(partes), 'Dibujos para unir con una línea')


def completar_serie(a):
    series = a['series']
    alto = 100 * len(series) + 10
    partes = []
    for i, s in enumerate(series):
        y = 55 + i * 100
        for k, e in enumerate(s):
            partes.append(emoji(50 + k * 75, y, e, 46))
        x = 50 + len(s) * 75
        partes.append('<rect x="%d" y="%d" width="64" height="64" rx="10" stroke="#222" stroke-width="3" '
                      'stroke-dasharray="8 6" fill="#fff"/>' % (x - 32, y - 32))
    return svg(alto, ''.join(partes), 'Series para completar')


RENDER = {'trazar_lineas': trazar_lineas, 'trazar_letras': trazar_letras, 'trazar_numeros': trazar_numeros,
          'colorear_formas': colorear_formas, 'dibujo_colorear': dibujo_colorear,
          'contar_colorear': contar_colorear, 'encerrar': encerrar, 'unir': unir,
          'completar_serie': completar_serie}


def renderizar(actividades, donde):
    """HTML de todas las actividades de una ficha. Falla con un mensaje claro si
    una actividad está mal escrita."""
    bloques = []
    for n, a in enumerate(actividades, 1):
        tipo = a.get('tipo')
        if tipo not in RENDER:
            raise ErrorActividad('%s, actividad %d: tipo desconocido %r; usa %s.'
                                 % (donde, n, tipo, ', '.join(sorted(RENDER))))
        consigna = a.get('consigna')
        if not isinstance(consigna, str) or not consigna.strip():
            raise ErrorActividad('%s, actividad %d: falta la consigna.' % (donde, n))
        try:
            dibujo_svg = RENDER[tipo](a)
        except (KeyError, TypeError, ValueError) as e:
            raise ErrorActividad('%s, actividad %d (%s): datos incompletos o mal escritos (%s).' % (donde, n, tipo, e))
        extra = ''
        if tipo == 'encerrar':
            extra = '\n  <ol class="act-preguntas">%s</ol>' % ''.join('<li>%s</li>' % esc(f['pregunta']) for f in a['filas'])
        bloques.append('<section class="actividad">\n  <p class="act-consigna"><span class="act-icono" aria-hidden="true">%s</span>'
                       '<span class="act-num">%d</span> %s</p>%s\n  %s\n</section>'
                       % (ICONOS[tipo], n, esc(consigna), extra, dibujo_svg))
    return bloques
