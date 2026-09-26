/*
 * Utilidades compartidas por todas las páginas.
 *
 * Se carga como script clásico (no módulo) para que las páginas sigan
 * funcionando al abrirlas directamente desde el disco, sin servidor.
 */
window.JEO = (function () {
  'use strict';

  var EMOJIS = ['🎉', '🌟', '⭐', '🎊', '👏', '🥳', '🚀', '💪'];

  var ELOGIOS = [
    '¡Excelente trabajo!',
    '¡Muy bien!',
    '¡Fantástico!',
    '¡Eres increíble!',
    '¡Sigue así!',
    '¡Perfecto!',
    '¡Genial!',
    '¡Magnífico!'
  ];

  /** Entero aleatorio en el intervalo cerrado [min, max]. */
  function enteroAleatorio(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  /** Elemento al azar de un array no vacío. */
  function alAzar(lista) {
    return lista[Math.floor(Math.random() * lista.length)];
  }

  /** Copia de `lista` en orden aleatorio (Fisher-Yates); no modifica el original. */
  function mezclar(lista) {
    var copia = lista.slice();
    for (var i = copia.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = copia[i];
      copia[i] = copia[j];
      copia[j] = tmp;
    }
    return copia;
  }

  /** Porcentaje entero de aciertos; 0 cuando todavía no hay intentos. */
  function porcentaje(aciertos, total) {
    return total > 0 ? Math.round((aciertos / total) * 100) : 0;
  }

  /** Frase de ánimo con emoji, para una respuesta correcta. */
  function felicitacion() {
    return alAzar(ELOGIOS) + ' ' + alAzar(EMOJIS);
  }

  /* El menú de materias es un <details>: funciona sin JavaScript. Esto solo
     añade lo que se espera de un menú desplegable: cerrarse con Escape o al
     pulsar fuera de él. */
  document.addEventListener('click', function (e) {
    document.querySelectorAll('details.menu-materias[open]').forEach(function (menu) {
      if (!menu.contains(e.target)) {
        menu.removeAttribute('open');
      }
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') {
      return;
    }
    document.querySelectorAll('details.menu-materias[open]').forEach(function (menu) {
      menu.removeAttribute('open');
      menu.querySelector('summary').focus();
    });
  });

  return {
    EMOJIS: EMOJIS,
    ELOGIOS: ELOGIOS,
    enteroAleatorio: enteroAleatorio,
    alAzar: alAzar,
    mezclar: mezclar,
    porcentaje: porcentaje,
    felicitacion: felicitacion
  };
})();
