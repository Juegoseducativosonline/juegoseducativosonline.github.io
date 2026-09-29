#!/usr/bin/env python3
"""Genera los PDF de las fichas y de los packs imprimiéndolos con Chrome.

    python tools/generar.py   # primero, para tener las páginas al día
    python tools/pdf.py       # luego, los PDF en la carpeta pdf/
    python tools/generar.py   # otra vez, para mostrar el tamaño de cada PDF en los enlaces

Levanta un servidor local temporal (las páginas usan rutas desde la raíz, como
en GitHub Pages) e imprime cada página con Chrome o Edge sin ventana, con el
mismo diseño de impresión que usa el navegador. Solo vuelve a imprimir lo que
cambió: guarda una huella de cada página en pdf/huellas.json.

Chrome se busca en las rutas habituales de Windows, macOS y Linux; se puede
indicar otro con la variable de entorno CHROME.
"""

import functools
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_PDF = RAIZ / 'pdf'
HUELLAS = CARPETA_PDF / 'huellas.json'
ESPERA_CARGA_MS = 8000       # tiempo virtual para que carguen la tipografía y los estilos
LIMITE_SEGUNDOS = 120        # por página; un pack grande tarda más que una ficha

CANDIDATOS_CHROME = [
    os.environ.get('CHROME', ''),
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    shutil.which('google-chrome') or '', shutil.which('chromium') or '', shutil.which('chromium-browser') or '',
]

# El tamaño del PDF aparece en el propio botón de descarga de la ficha: se ignora
# al calcular la huella, o cada impresión cambiaría la página y habría que reimprimir.
PESO = re.compile(r' \(\d+(?:,\d)? (?:KB|MB)\)')


def buscar_chrome():
    for ruta in CANDIDATOS_CHROME:
        if ruta and Path(ruta).is_file():
            return ruta
    sys.exit('No encontré Chrome ni Edge. Indica la ruta con la variable de entorno CHROME.')


def destino(ruta_html):
    """Misma regla que pdf_de() en tools/generar.py."""
    if ruta_html.startswith('packs/'):
        return CARPETA_PDF / (ruta_html[len('packs/'):-len('.html')] + '.pdf')
    return CARPETA_PDF / (ruta_html[:-len('-ficha.html')] + '.pdf')


def paginas_a_imprimir():
    fichas = sorted(p.relative_to(RAIZ).as_posix() for p in RAIZ.glob('*/*-ficha.html'))
    packs = sorted(p.relative_to(RAIZ).as_posix() for p in (RAIZ / 'packs').glob('*.html'))
    return fichas + packs


def huella(ruta_html, estilos):
    texto = PESO.sub('', (RAIZ / ruta_html).read_text(encoding='utf-8'))
    return hashlib.sha256((texto + estilos).encode('utf-8')).hexdigest()[:16]


class ServidorSilencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    chrome = buscar_chrome()
    paginas = paginas_a_imprimir()
    if not paginas:
        sys.exit('No hay fichas ni packs: ejecuta primero python tools/generar.py.')

    estilos = ''.join((RAIZ / 'assets' / n).read_text(encoding='utf-8') for n in ('site.css', 'quiz.css'))
    anteriores = json.loads(HUELLAS.read_text(encoding='utf-8')) if HUELLAS.exists() else {}
    pendientes = [p for p in paginas if anteriores.get(p) != huella(p, estilos) or not destino(p).exists()]
    print('%d páginas; %d por imprimir.' % (len(paginas), len(pendientes)))

    manejador = functools.partial(ServidorSilencioso, directory=str(RAIZ))
    servidor = http.server.ThreadingHTTPServer(('127.0.0.1', 0), manejador)
    puerto = servidor.server_address[1]
    threading.Thread(target=servidor.serve_forever, daemon=True).start()

    nuevas = dict(anteriores)
    fallos = []
    # Perfil temporal propio: no toca el navegador que la persona tenga abierto.
    with tempfile.TemporaryDirectory() as perfil:
        for n, ruta in enumerate(pendientes, 1):
            salida = destino(ruta)
            salida.parent.mkdir(parents=True, exist_ok=True)
            orden = [chrome, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', '--no-first-run',
                     '--user-data-dir=' + perfil, '--virtual-time-budget=%d' % ESPERA_CARGA_MS,
                     '--print-to-pdf=' + str(salida), 'http://127.0.0.1:%d/%s' % (puerto, ruta)]
            try:
                subprocess.run(orden, check=True, timeout=LIMITE_SEGUNDOS, capture_output=True)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                fallos.append('%s: %s' % (ruta, error))
                continue
            # Chrome puede salir sin error y no escribir nada: se comprueba el archivo.
            if not salida.exists() or salida.read_bytes()[:5] != b'%PDF-':
                fallos.append('%s: no se generó un PDF válido' % ruta)
                continue
            nuevas[ruta] = huella(ruta, estilos)
            print('  [%d/%d] %s → %s (%d KB)' % (n, len(pendientes), ruta, salida.relative_to(RAIZ).as_posix(),
                                                  salida.stat().st_size // 1024))
    servidor.shutdown()

    # PDF de páginas que ya no existen (un juego borrado o renombrado).
    esperados = {destino(p) for p in paginas}
    for viejo in CARPETA_PDF.rglob('*.pdf'):
        if viejo not in esperados:
            viejo.unlink()
            print('  eliminado (ya no existe su página): %s' % viejo.relative_to(RAIZ).as_posix())
    nuevas = {p: h for p, h in nuevas.items() if p in paginas}

    HUELLAS.write_text(json.dumps(nuevas, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    if fallos:
        print('Fallaron %d:' % len(fallos), file=sys.stderr)
        for f in fallos:
            print('  ' + f, file=sys.stderr)
        return 1
    print('Listo. Ahora ejecuta python tools/generar.py para mostrar el tamaño de cada PDF.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
