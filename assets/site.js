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
    porcentaje: porcentaje,
    felicitacion: felicitacion
  };
})();
