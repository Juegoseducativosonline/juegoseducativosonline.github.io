#!/usr/bin/env python3
"""Dibuja los iconos PNG de la aplicación instalable (assets/icono-*.png).

    python tools/iconos.py

Solo hace falta volver a ejecutarlo si cambia el diseño del icono. Usa solo la
biblioteca estándar: degradado de marca con un botón de «jugar» blanco.
"""
import struct
import zlib
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / 'assets'
INICIO, FIN = (0x3b, 0x5b, 0xdb), (0x70, 0x48, 0xe8)
MUESTRAS = 4  # submuestreo por eje, para suavizar los bordes


def png(ancho, alto, pixeles):
    filas = b''.join(b'\x00' + bytes(pixeles[y * ancho * 4:(y + 1) * ancho * 4]) for y in range(alto))

    def trozo(tipo, datos):
        return struct.pack('>I', len(datos)) + tipo + datos + struct.pack('>I', zlib.crc32(tipo + datos) & 0xffffffff)

    return (b'\x89PNG\r\n\x1a\n' + trozo(b'IHDR', struct.pack('>IIBBBBB', ancho, alto, 8, 6, 0, 0, 0))
            + trozo(b'IDAT', zlib.compress(filas, 9)) + trozo(b'IEND', b''))


def dentro_redondeado(x, y, radio):
    """(x, y) en [0,1]²; cuadrado con esquinas de radio `radio`."""
    cx = min(max(x, radio), 1 - radio)
    cy = min(max(y, radio), 1 - radio)
    return (x - cx) ** 2 + (y - cy) ** 2 <= radio ** 2


def dentro_triangulo(x, y, escala):
    # Triángulo de «jugar» centrado ópticamente (algo desplazado a la derecha).
    ax, ay = 0.5 - 0.17 * escala + 0.03 * escala, 0.5 - 0.2 * escala
    bx, by = ax, 0.5 + 0.2 * escala
    cx, cy = 0.5 + 0.2 * escala + 0.03 * escala, 0.5

    def lado(px, py, qx, qy, rx, ry):
        return (px - rx) * (qy - ry) - (qx - rx) * (py - ry)

    d1, d2, d3 = lado(x, y, ax, ay, bx, by), lado(x, y, bx, by, cx, cy), lado(x, y, cx, cy, ax, ay)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


def dibujar(tam, redondeado, escala):
    pixeles = bytearray(tam * tam * 4)
    for py in range(tam):
        for px in range(tam):
            fondo = blanco = 0
            for sy in range(MUESTRAS):
                for sx in range(MUESTRAS):
                    x = (px + (sx + 0.5) / MUESTRAS) / tam
                    y = (py + (sy + 0.5) / MUESTRAS) / tam
                    if redondeado and not dentro_redondeado(x, y, 0.22):
                        continue
                    fondo += 1
                    if (x - 0.5) ** 2 + (y - 0.5) ** 2 <= (0.3 * escala) ** 2 and not dentro_triangulo(x, y, escala):
                        blanco += 1
            total = MUESTRAS * MUESTRAS
            t = (px + py) / (2 * tam)
            color = [round(a + (b - a) * t) for a, b in zip(INICIO, FIN)]
            mezcla = blanco / fondo if fondo else 0
            i = (py * tam + px) * 4
            pixeles[i:i + 3] = bytes(round(c + (255 - c) * mezcla) for c in color)
            pixeles[i + 3] = round(255 * fondo / total)
    return png(tam, tam, pixeles)


if __name__ == '__main__':
    # «maskable»: sin esquinas y con el dibujo dentro de la zona segura (80 %),
    # porque Android recorta el icono con la forma que elija.
    for nombre, tam, redondeado, escala in (('icono-192.png', 192, True, 1.0),
                                            ('icono-512.png', 512, True, 1.0),
                                            ('icono-maskable-512.png', 512, False, 0.8),
                                            ('icono-180.png', 180, False, 0.9)):
        (ASSETS / nombre).write_bytes(dibujar(tam, redondeado, escala))
        print(nombre)
