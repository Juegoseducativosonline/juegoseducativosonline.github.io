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

  /* --- Efectos de juego: sonido de acierto y de error, confeti y barra de progreso ---------
     Funcionan en todos los juegos sin tocar cada motor: se observa cuándo una
     respuesta queda marcada como correcta o incorrecta (clases correct/correcta/
     correcto e incorrect/incorrecta/incorrecto) y cuándo aparece el resultado final. */
  var CLAVE_SONIDO = 'jeo-sonido';
  var audio = null;

  function sonidoActivo() {
    try { return localStorage.getItem(CLAVE_SONIDO) !== 'no'; } catch (e) { return true; }
  }

  function tono(frecuencia, inicio, duracion, tipo, volumen) {
    var t = audio.currentTime + inicio;
    var osc = audio.createOscillator();
    var gan = audio.createGain();
    osc.type = tipo;
    osc.frequency.setValueAtTime(frecuencia, t);
    gan.gain.setValueAtTime(0.0001, t);
    gan.gain.exponentialRampToValueAtTime(volumen, t + 0.02);
    gan.gain.exponentialRampToValueAtTime(0.0001, t + duracion);
    osc.connect(gan).connect(audio.destination);
    osc.start(t);
    osc.stop(t + duracion + 0.05);
  }

  function sonar(cual) {
    if (!sonidoActivo()) {
      return;
    }
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === 'suspended') {
        audio.resume();
      }
      if (cual === 'bien') {          // do–mi–sol hacia arriba
        tono(523, 0, 0.15, 'triangle', 0.25);
        tono(659, 0.1, 0.15, 'triangle', 0.25);
        tono(784, 0.2, 0.25, 'triangle', 0.25);
      } else if (cual === 'mal') {    // dos notas graves que bajan
        tono(220, 0, 0.2, 'sawtooth', 0.08);
        tono(165, 0.18, 0.3, 'sawtooth', 0.08);
      } else if (cual === 'fin') {    // pequeña fanfarria
        [523, 659, 784, 1047].forEach(function (f, i) { tono(f, i * 0.12, 0.25, 'triangle', 0.22); });
        tono(1047, 0.5, 0.5, 'triangle', 0.2);
      }
    } catch (e) { /* sin audio: el juego sigue igual */ }
  }

  var movimientoReducido = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var COLORES_CONFETI = ['#f03e3e', '#fab005', '#40c057', '#228be6', '#be4bdb', '#fd7e14'];

  function confeti(cantidad) {
    if (movimientoReducido) {
      return;
    }
    var capa = document.createElement('div');
    capa.className = 'capa-confeti';
    capa.setAttribute('aria-hidden', 'true');
    for (var i = 0; i < cantidad; i++) {
      var trozo = document.createElement('span');
      trozo.style.left = Math.random() * 100 + 'vw';
      trozo.style.background = COLORES_CONFETI[i % COLORES_CONFETI.length];
      trozo.style.animationDelay = Math.random() * 0.6 + 's';
      trozo.style.animationDuration = 1.8 + Math.random() * 1.4 + 's';
      trozo.style.setProperty('--giro', (Math.random() * 720 - 360) + 'deg');
      trozo.style.setProperty('--deriva', (Math.random() * 30 - 15) + 'vw');
      capa.appendChild(trozo);
    }
    document.body.appendChild(capa);
    setTimeout(function () { capa.remove(); }, 3800);
  }

  /* Varias marcas a la vez (una hoja de ejercicios revisada de una vez, o la
     correcta que se resalta tras un error) cuentan como una sola respuesta. */
  var pendiente = null;
  var ultimoFinal = 0;
  function registrar(tipo) {
    if (!pendiente) {
      pendiente = { bien: 0, mal: 0 };
      setTimeout(function () {
        var p = pendiente;
        pendiente = null;
        if (p.mal) {
          sonar('mal');
        } else if (p.bien) {
          sonar('bien');
          confeti(25);
          avanzarMeta();
        }
      }, 120);
    }
    pendiente[tipo]++;
  }

  function celebrarFinal() {
    var ahora = Date.now();
    if (ahora - ultimoFinal < 2000) {
      return;
    }
    ultimoFinal = ahora;
    setTimeout(function () { sonar('fin'); confeti(140); }, 150);
  }

  var CLASES_BIEN = /(^|\s)(correct|correcta|correcto)(\s|$)/;
  var CLASES_MAL = /(^|\s)(incorrect|incorrecta|incorrecto)(\s|$)/;
  var FINALES = '.quiz-resultado, .resultado';

  var observador = new MutationObserver(function (cambios) {
    cambios.forEach(function (c) {
      var el = c.target;
      if (c.type !== 'attributes' || !(el instanceof Element)) {
        return;
      }
      var antes = c.oldValue || '';
      var ahora = el.className && el.className.baseVal === undefined ? el.className : '';
      if (el.matches(FINALES) && !el.classList.contains('hidden') && /(^|\s)hidden(\s|$)/.test(antes)) {
        celebrarFinal();
        return;
      }
      /* Un mensaje de estado se reescribe con la misma clase en cada acierto: cuenta siempre. */
      var nuevo = el.classList.contains('feedback') ? '' : antes;
      if (CLASES_MAL.test(ahora) && !CLASES_MAL.test(nuevo)) {
        registrar('mal');
      } else if (CLASES_BIEN.test(ahora) && !CLASES_BIEN.test(nuevo)) {
        registrar('bien');
        if (/🎉/.test(el.textContent)) {
          celebrarFinal();
        }
      }
    });
  });

  /* Barra de progreso para las prácticas de operaciones, que no tienen una propia:
     en una hoja de ejercicios, cuántos van respondidos; en las de una pregunta a la
     vez, cuántos aciertos lleva hacia la meta de 10. */
  var META_ACIERTOS = 10;
  var metaRelleno = null;
  var metaTexto = null;
  var aciertosMeta = 0;

  function crearBarra(antesDe) {
    var caja = document.createElement('div');
    caja.className = 'progreso-actividad';
    metaTexto = document.createElement('p');
    metaTexto.className = 'quiz-progreso';
    var barra = document.createElement('div');
    barra.className = 'progress-bar';
    barra.setAttribute('role', 'progressbar');
    barra.setAttribute('aria-valuemin', '0');
    metaRelleno = document.createElement('div');
    metaRelleno.className = 'progress-fill';
    barra.appendChild(metaRelleno);
    caja.appendChild(metaTexto);
    caja.appendChild(barra);
    antesDe.parentNode.insertBefore(caja, antesDe);
    return barra;
  }

  function pintarBarra(barra, hechas, total, texto) {
    metaRelleno.style.width = Math.min(100, (hechas / total) * 100) + '%';
    barra.setAttribute('aria-valuemax', String(total));
    barra.setAttribute('aria-valuenow', String(Math.min(hechas, total)));
    metaTexto.textContent = texto;
  }

  var barraMeta = null;
  function avanzarMeta() {
    if (!barraMeta) {
      return;
    }
    aciertosMeta++;
    pintarBarra(barraMeta, aciertosMeta, META_ACIERTOS, aciertosMeta >= META_ACIERTOS
      ? '🏆 ¡Meta cumplida! ' + aciertosMeta + ' aciertos'
      : 'Meta: ' + aciertosMeta + ' de ' + META_ACIERTOS + ' aciertos');
    if (aciertosMeta === META_ACIERTOS) {
      celebrarFinal();
    }
  }

  function prepararPractica() {
    var campos = document.querySelectorAll('.answer-input');
    if (document.querySelector('#quiz')) {
      return;
    }
    if (!campos.length) {
      /* Hojas que se arman al elegir el nivel: se espera a que aparezcan los ejercicios. */
      var espera = new MutationObserver(function () {
        if (document.querySelector('.answer-input')) {
          espera.disconnect();
          prepararPractica();
        }
      });
      espera.observe(document.body, { childList: true, subtree: true });
      return;
    }
    var principal = document.querySelector('main') || document.body;
    var ancla = principal.querySelector('.game-area, .exercise-area, .content > *') || principal.firstElementChild;
    if (!ancla) {
      return;
    }
    if (campos.length > 1) {
      var barra = crearBarra(ancla);
      var contar = function () {
        var todos = document.querySelectorAll('.answer-input');
        var hechos = Array.prototype.filter.call(todos, function (c) { return c.value.trim() !== ''; }).length;
        pintarBarra(barra, hechos, todos.length, 'Respondidas: ' + hechos + ' de ' + todos.length);
      };
      document.addEventListener('input', function (e) {
        if (e.target.classList && e.target.classList.contains('answer-input')) { contar(); }
      });
      /* La hoja cambia al elegir otro nivel: se recuenta. */
      new MutationObserver(function (cambios) {
        /* Los cambios de la propia barra no cuentan: evitaría un ciclo sin fin. */
        if (cambios.some(function (c) { return !c.target.closest('.progreso-actividad'); })) {
          contar();
        }
      }).observe(principal, { childList: true, subtree: true });
      contar();
    } else {
      barraMeta = crearBarra(ancla);
      pintarBarra(barraMeta, 0, META_ACIERTOS, 'Meta: 0 de ' + META_ACIERTOS + ' aciertos');
    }
  }

  /* Botón para silenciar, junto a cada juego. */
  function prepararBotonSonido() {

    var boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'btn btn-secundario boton-sonido';
    var pintar = function () {
      boton.textContent = sonidoActivo() ? '🔊 Sonido: sí' : '🔇 Sonido: no';
      boton.setAttribute('aria-pressed', String(sonidoActivo()));
    };
    boton.addEventListener('click', function () {
      try { localStorage.setItem(CLAVE_SONIDO, sonidoActivo() ? 'no' : 'si'); } catch (e) { /* sin almacenamiento */ }
      pintar();
    });
    pintar();
    var contenido = document.querySelector('main.content, main') || document.body;
    contenido.insertBefore(boton, contenido.firstChild);

    /* Modo clase: para proyectar. Pantalla completa, solo el juego y letra grande. */
    var clase = document.createElement('button');
    clase.type = 'button';
    clase.className = 'btn btn-secundario boton-sonido boton-clase';
    clase.textContent = '📽️ Modo clase';
    var raiz = document.documentElement;
    function salir() {
      raiz.classList.remove('modo-clase');
      clase.textContent = '📽️ Modo clase';
    }
    clase.addEventListener('click', function () {
      if (raiz.classList.contains('modo-clase')) {
        if (document.fullscreenElement && document.exitFullscreen) { document.exitFullscreen(); }
        salir();
        return;
      }
      raiz.classList.add('modo-clase');
      clase.textContent = '✖ Salir del modo clase';
      if (raiz.requestFullscreen) { raiz.requestFullscreen().catch(function () { /* sin pantalla completa: sigue con letra grande */ }); }
    });
    document.addEventListener('fullscreenchange', function () {
      if (!document.fullscreenElement) { salir(); }
    });
    contenido.insertBefore(clase, contenido.firstChild);
  }

  if (document.querySelector('#quiz, .answer-input') || /_practice/.test(location.pathname)) {
    observador.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'], attributeOldValue: true });
    prepararPractica();
    prepararBotonSonido();
  }

  /* --- Explicaciones y repaso final, comunes a todos los juegos ------------------------ */
  function nodo(etiqueta, clase, texto) {
    var el = document.createElement(etiqueta);
    if (clase) { el.className = clase; }
    if (texto !== undefined) { el.textContent = texto; }
    return el;
  }

  /* Pinta en `el` la explicación y, si hay, un dato curioso. Se muestra siempre,
     se haya acertado o no: lo importante es entender el porqué. */
  function explicar(el, explicacion, curioso) {
    var hijos = [];
    if (explicacion) {
      var p = nodo('p', 'porque-texto');
      p.appendChild(nodo('strong', null, '📘 ¿Por qué? '));
      p.appendChild(document.createTextNode(explicacion));
      hijos.push(p);
    }
    if (curioso) {
      var c = nodo('p', 'porque-curioso');
      c.appendChild(nodo('strong', null, '🤓 ¿Sabías que…? '));
      c.appendChild(document.createTextNode(curioso));
      hijos.push(c);
    }
    el.replaceChildren.apply(el, hijos);
    el.classList.toggle('hidden', !hijos.length);
  }

  /* Repaso al final de la actividad: cada ítem con su respuesta y explicación,
     marcado ✓ o ✗, y los datos curiosos del tema. */
  function repaso(items, curiosos) {
    var sec = nodo('section', 'repaso');
    sec.appendChild(nodo('h3', null, '📘 Repaso: las respuestas y su porqué'));
    var ol = nodo('ol', 'repaso-lista');
    items.forEach(function (it) {
      var li = nodo('li', it.bien === false ? 'repaso-mal' : 'repaso-bien');
      li.appendChild(nodo('span', 'repaso-marca', it.bien === false ? '✗ ' : '✓ '));
      li.appendChild(nodo('strong', null, it.titulo));
      if (it.tuya) {
        li.appendChild(nodo('span', 'repaso-tuya', ' Tu respuesta: ' + it.tuya + '.'));
      }
      li.appendChild(nodo('span', 'repaso-respuesta', ' Respuesta: ' + it.respuesta + '.'));
      if (it.explicacion) {
        li.appendChild(nodo('span', 'repaso-explicacion', ' ' + it.explicacion));
      }
      ol.appendChild(li);
    });
    sec.appendChild(ol);
    if (curiosos && curiosos.length) {
      sec.appendChild(nodo('h3', null, '🤓 Datos curiosos'));
      var ul = nodo('ul', 'repaso-curiosos');
      curiosos.forEach(function (t) { ul.appendChild(nodo('li', null, t)); });
      sec.appendChild(ul);
    }
    return sec;
  }

  return {
    explicar: explicar,
    repaso: repaso,
    EMOJIS: EMOJIS,
    ELOGIOS: ELOGIOS,
    enteroAleatorio: enteroAleatorio,
    alAzar: alAzar,
    mezclar: mezclar,
    porcentaje: porcentaje,
    felicitacion: felicitacion
  };
})();
