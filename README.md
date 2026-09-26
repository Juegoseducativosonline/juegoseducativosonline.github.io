# Juegos Educativos Online

Sitio estático publicado en https://juegoseducativosonline.github.io con GitHub Pages.

## Cómo está organizado

- `contenido/catalogo.json`: las materias, sus temas y qué juegos tiene cada tema.
- `contenido/<materia>/<juego>.json`: las preguntas de cada juego de tipo quiz.
- `tools/generar.py`: genera las páginas HTML a partir de `contenido/`.
- `assets/`: estilos y scripts compartidos (`materias.css` también se genera).
- `matematicas/*_practice*.html`: juegos interactivos hechos a mano. El generador solo
  reescribe sus bloques `<!-- generado:... -->` (cabecera, menú y pie).

Las páginas generadas llevan un aviso al principio: **no las edites a mano**, cambia el
contenido y vuelve a generar.

## Añadir o corregir preguntas

1. Edita o crea el JSON del juego en `contenido/<materia>/`. En cada pregunta,
   `correcta` es la posición (empezando en 0) de la respuesta buena en `opciones`.
   El juego baraja las opciones al jugar.
2. Si es un juego nuevo, añádelo a un tema en `contenido/catalogo.json`:
   `{"tipo": "quiz", "datos": "<materia>/<juego>.json"}`.
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
