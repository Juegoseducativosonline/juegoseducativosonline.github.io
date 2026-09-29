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

  /* --- Vista docente ----------------------------------------------------- */

  /* Quien llega desde /docentes/ o una página de grado ve, en cada juego, los
     lineamientos arriba; quien entra a jugar ve solo el juego. Se recuerda
     durante la visita (sessionStorage), y sin almacenamiento todo funciona
     igual, solo que sin recordar la elección. */
  var CLAVE_MODO = 'jeo-modo';

  function guardarModo(modo) {
    try {
      sessionStorage.setItem(CLAVE_MODO, modo);
    } catch (e) { /* almacenamiento no disponible: no se recuerda */ }
  }

  function leerModo() {
    try {
      return sessionStorage.getItem(CLAVE_MODO);
    } catch (e) {
      return null;
    }
  }

  if (/^\/(docentes|grados)\//.test(location.pathname)) {
    guardarModo('docente');
  }

  function aplicarModo() {
    document.documentElement.classList.toggle('vista-docente', leerModo() === 'docente');
  }
  aplicarModo();

  document.addEventListener('click', function (e) {
    var destino = e.target.closest('[data-modo], .entrada-jugar a');
    if (!destino) {
      return;
    }
    guardarModo(destino.getAttribute('data-modo') || 'estudiante');
    aplicarModo();
  });

  /* --- Uso sin internet -------------------------------------------------- */

  /* El service worker guarda el sitio para usarlo sin conexión. Solo existe en
     https y en localhost; abierto como archivo local simplemente no se usa. */
  var puedeTrabajarSinConexion = 'serviceWorker' in navigator &&
    (location.protocol === 'https:' || location.hostname === 'localhost');

  if (puedeTrabajarSinConexion) {
    navigator.serviceWorker.register('/sw.js').catch(function (error) {
      /* Sin service worker el sitio funciona igual, solo que no sin conexión. */
      console.warn('No se pudo activar el modo sin conexión:', error);
    });
  }

  var estado = document.getElementById('estado-offline');
  if (estado) {
    var marcar = function (texto, clase) {
      estado.textContent = texto;
      estado.className = 'estado-offline ' + clase;
    };
    if (!puedeTrabajarSinConexion || !window.caches) {
      marcar('Este navegador no permite guardar el sitio para usarlo sin conexión. Prueba con Chrome, Edge, Firefox o Safari actualizados.', 'estado-aviso');
    } else {
      marcar('Guardando el sitio en este dispositivo…', 'estado-pendiente');
      navigator.serviceWorker.ready.then(function () {
        return caches.open(estado.dataset.cache);
      }).then(function (cache) {
        return cache.keys();
      }).then(function (guardados) {
        if (guardados.length >= Number(estado.dataset.total)) {
          marcar('✓ Listo: este dispositivo ya tiene todo el sitio guardado y puede usarse sin conexión.', 'estado-ok');
        } else {
          marcar('El sitio se está actualizando. Vuelve a abrir esta página en unos segundos, con conexión.', 'estado-pendiente');
        }
      }).catch(function () {
        marcar('No se pudo comprobar el modo sin conexión. Vuelve a intentarlo con internet.', 'estado-aviso');
      });
    }
  }

  /* Chrome, Edge y Android avisan cuando el sitio se puede instalar; entonces
     se muestra el botón. Safari no lo permite: ahí sirven las instrucciones. */
  var avisoInstalacion = null;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    avisoInstalacion = e;
    document.querySelectorAll('[data-instalar]').forEach(function (boton) {
      boton.classList.remove('hidden');
    });
  });

  document.querySelectorAll('[data-instalar]').forEach(function (boton) {
    boton.addEventListener('click', function () {
      if (!avisoInstalacion) {
        return;
      }
      avisoInstalacion.prompt();
      avisoInstalacion.userChoice.then(function () {
        avisoInstalacion = null;
        boton.classList.add('hidden');
      });
    });
  });

  document.querySelectorAll('[data-imprimir]').forEach(function (boton) {
    boton.addEventListener('click', function () {
      window.print();
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
