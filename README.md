# Juegos Educativos Online

Sitio estático publicado en https://juegoseducativosonline.github.io con GitHub Pages.

## Cómo está organizado

- `contenido/catalogo.json`: las materias, sus temas y qué juegos tiene cada tema.
- `contenido/<materia>/<juego>.json`: los datos de cada juego. Hay tres tipos:
  `quiz` (preguntas de opción múltiple), `parejas` (lista `pares` con `a` y `b`) y
  `ordenar` (lista `rondas`, cada una con `instruccion` y sus `elementos` en el orden
  correcto). Copia un archivo existente del mismo tipo como plantilla.
- `tools/generar.py`: genera las páginas HTML a partir de `contenido/`.
- `assets/`: estilos y scripts compartidos (`materias.css` también se genera).
- `sw.js` y `manifest.webmanifest` (generados): permiten instalar el sitio como aplicación
  y usarlo sin internet. Cada juego de preguntas tiene además una ficha para imprimir
  (`<juego>-ficha.html`). Todo esto se regenera solo al ejecutar el generador.
- `tools/iconos.py`: dibuja los iconos de la aplicación; solo hace falta si cambia su diseño.
- `matematicas/*_practice*.html`: juegos interactivos hechos a mano. El generador solo
  reescribe sus bloques `<!-- generado:... -->` (cabecera, menú y pie).

Las páginas generadas llevan un aviso al principio: **no las edites a mano**, cambia el
contenido y vuelve a generar.

## Añadir o corregir preguntas

1. Edita o crea el JSON del juego en `contenido/<materia>/`. En cada pregunta,
   `correcta` es la posición (empezando en 0) de la respuesta buena en `opciones`.
   El juego baraja las opciones al jugar.
2. Si es un juego nuevo, añádelo a un tema en `contenido/catalogo.json`:
   `{"tipo": "quiz", "datos": "<materia>/<juego>.json", "grados": [3, 4, 5]}` (o `"parejas"` /
   `"ordenar"`). `grados` es obligatorio: grados seguidos de 0 (Transición) a 11. De ahí salen
   la edad, el nivel (primaria o secundaria) y las páginas por grado y por edad.
3. Genera y publica:

```bash
python tools/generar.py
git add -A
git commit -m "Describe el cambio"
git push
```

Si hay un error en los datos (una respuesta fuera de rango, opciones repetidas, un
archivo que no existe...), el generador se detiene y dice exactamente dónde está.

Para comprobar sin escribir nada que todo está generado y al día:

```bash
python tools/generar.py --comprobar
```
