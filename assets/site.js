/*
 * Utilidades compartidas por todos los juegos.
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
