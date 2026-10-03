/*
 * Motor de preguntas de opción múltiple que usan todos los juegos de tipo
 * "quiz". Requiere assets/site.js y assets/quiz.css.
 *
 * Uso:
 *   JEO.iniciarQuiz({
 *     contenedor: document.getElementById('quiz'),
 *     mezclarPreguntas: true,
 *     preguntas: [
 *       {
 *         pasaje: { titulo: '...', parrafos: ['...'] },   // opcional
 *         enunciado: '¿...?',
 *         opciones: ['A', 'B', 'C'],
 *         correcta: 0,          // índice en `opciones`, tal como se escriben
 *         explicacion: '...'    // opcional, se muestra tras responder
 *       }
 *     ]
 *   });
 *
 * Todo el texto se inserta con textContent, nunca como HTML.
 */
(function (JEO) {
  'use strict';

  if (!JEO) {
    throw new Error('quiz.js necesita que assets/site.js se cargue antes.');
  }

  var MINIMO_OPCIONES = 2;

  /* Un error en los datos de un juego es un fallo de quien lo escribió:
     mejor detenerse al cargar que mostrar una pregunta sin respuesta válida. */
  function validar(preguntas) {
    if (!Array.isArray(preguntas) || preguntas.length === 0) {
      throw new Error('iniciarQuiz: se necesita al menos una pregunta.');
    }
    preguntas.forEach(function (p, i) {
      var etiqueta = 'iniciarQuiz: pregunta ' + (i + 1);
      if (!p.enunciado) {
        throw new Error(etiqueta + ' no tiene enunciado.');
      }
      if (!Array.isArray(p.opciones) || p.opciones.length < MINIMO_OPCIONES) {
        throw new Error(etiqueta + ' necesita al menos ' + MINIMO_OPCIONES + ' opciones.');
      }
      if (!(p.correcta >= 0 && p.correcta < p.opciones.length)) {
        throw new Error(etiqueta + ' tiene un índice de respuesta correcta fuera de rango.');
      }
    });
  }

  function crear(etiqueta, clase, texto) {
    var el = document.createElement(etiqueta);
    if (clase) {
      el.className = clase;
    }
    if (texto !== undefined) {
      el.textContent = texto;
    }
    return el;
  }

  function mensajeFinal(porcentaje) {
    if (porcentaje === 100) {
      return '🏆 ¡Perfecto! Has acertado todas las preguntas.';
    }
    if (porcentaje >= 70) {
      return '🌟 ¡Muy bien! Dominas casi todo el tema.';
    }
    if (porcentaje >= 40) {
      return '💪 ¡Buen intento! Repasa las explicaciones y vuelve a jugar.';
    }
    return '📚 Sigue practicando: cada partida te ayuda a aprender más.';
  }

  JEO.iniciarQuiz = function (config) {
    validar(config.preguntas);

    var contenedor = config.contenedor;
    var ronda = [];
    var indice = 0;
    var aciertos = 0;
    var pasajeActual = null;

    /* --- Estructura fija; cada pregunta solo cambia su contenido --- */

    var elProgresoTexto = crear('p', 'quiz-progreso');
    var elBarra = crear('div', 'progress-bar');
    var elRelleno = crear('div', 'progress-fill');
    elBarra.setAttribute('role', 'progressbar');
    elBarra.setAttribute('aria-label', 'Progreso del juego');
    elBarra.setAttribute('aria-valuemin', '0');
    elBarra.appendChild(elRelleno);

    var elPasaje = crear('article', 'quiz-pasaje hidden');
    var elEnunciado = crear('h2', 'quiz-enunciado');
    /* Permite mover el foco aquí al cambiar de pregunta, para que un lector
       de pantalla la anuncie. */
    elEnunciado.tabIndex = -1;
    /* Dibujo de la pregunta: cantidades para contar o una imagen que la acompaña. */
    var elFigura = crear('div', 'quiz-figura hidden');
    elFigura.setAttribute('aria-hidden', 'true');

    /* Botón para oír la pregunta: imprescindible para quien aún está
       aprendiendo a leer. Solo aparece si el juego lo pide y el navegador
       tiene síntesis de voz. */
    var puedeHablar = config.leerEnVozAlta && 'speechSynthesis' in window;
    var btnEscuchar = crear('button', 'btn btn-secundario quiz-escuchar', '🔊 Escuchar');
    btnEscuchar.type = 'button';
    if (!puedeHablar) {
      btnEscuchar.classList.add('hidden');
    }

    var elOpciones = crear('ul', 'quiz-opciones');
    var elFeedback = crear('p', 'feedback hidden');
    var elPorque = crear('div', 'quiz-porque hidden');
    elFeedback.setAttribute('role', 'status');
    elFeedback.setAttribute('aria-live', 'polite');

    var elAcciones = crear('div', 'controls');
    var btnSiguiente = crear('button', 'btn hidden', 'Siguiente ➜');
    btnSiguiente.type = 'button';
    elAcciones.appendChild(btnSiguiente);

    var elJuego = crear('div', 'quiz-juego');
    [elProgresoTexto, elBarra, elPasaje, elEnunciado, elFigura, btnEscuchar, elOpciones, elFeedback, elPorque, elAcciones]
      .forEach(function (el) { elJuego.appendChild(el); });

    var elRepaso = null;
    var historial = [];
    var elResultado = crear('section', 'quiz-resultado hidden');
    var elResultadoTitulo = crear('h2', null, 'Resultado');
    elResultadoTitulo.tabIndex = -1;
    var elResultadoCifra = crear('p', 'quiz-resultado-cifra');
    var elResultadoMensaje = crear('p');
    var btnReiniciar = crear('button', 'btn btn-acento', '🔄 Jugar de nuevo');
    btnReiniciar.type = 'button';
    [elResultadoTitulo, elResultadoCifra, elResultadoMensaje, btnReiniciar]
      .forEach(function (el) { elResultado.appendChild(el); });

    contenedor.replaceChildren(elJuego, elResultado);

    /* --- Flujo --- */

    function empezar() {
      /* Las opciones se barajan en cada partida; se guarda qué opción es la
         correcta por objeto, no por posición, para que el barajado no la pierda. */
      var base = config.mezclarPreguntas ? JEO.mezclar(config.preguntas) : config.preguntas;
      ronda = base.map(function (p) {
        return {
          pasaje: p.pasaje || null,
          enunciado: p.enunciado,
          figura: p.figura || null,
          dibujo: p.dibujo || '',
          explicacion: p.explicacion || '',
          curioso: p.curioso || '',
          opciones: JEO.mezclar(p.opciones.map(function (texto, i) {
            return { texto: texto, esCorrecta: i === p.correcta };
          }))
        };
      });
      indice = 0;
      aciertos = 0;
      historial = [];
      pasajeActual = null;

      elResultado.classList.add('hidden');
      elJuego.classList.remove('hidden');
      mostrarPregunta();
    }

    function mostrarPasaje(pasaje) {
      if (pasaje === pasajeActual) {
        return;
      }
      pasajeActual = pasaje;

      if (!pasaje) {
        elPasaje.classList.add('hidden');
        elPasaje.replaceChildren();
        return;
      }

      var hijos = [];
      if (pasaje.ilustracion) {
        var arte = crear('p', 'ficha-pasaje-arte', pasaje.ilustracion);
        arte.setAttribute('aria-hidden', 'true');
        hijos.push(arte);
      }
      hijos.push(crear('h2', 'quiz-pasaje-titulo', '📖 ' + pasaje.titulo));
      pasaje.parrafos.forEach(function (texto) {
        hijos.push(crear('p', null, texto));
      });
      elPasaje.replaceChildren.apply(elPasaje, hijos);
      elPasaje.classList.remove('hidden');
    }

    function actualizarProgreso() {
      var total = ronda.length;
      elProgresoTexto.textContent =
        'Pregunta ' + (indice + 1) + ' de ' + total + ' · Aciertos: ' + aciertos;
      elRelleno.style.width = (indice / total) * 100 + '%';
      elBarra.setAttribute('aria-valuemax', String(total));
      elBarra.setAttribute('aria-valuenow', String(indice));
    }

    /* Los emojis se quitan antes de leer: la voz los nombraría («cara
       sonriente…») y confundiría a quien escucha. */
    function sinEmojis(texto) {
      return texto.replace(/\p{Extended_Pictographic}|\uFE0F|\u200D/gu, '').replace(/\s+/g, ' ').trim();
    }

    function callar() {
      if (puedeHablar) {
        window.speechSynthesis.cancel();
      }
    }

    function leerPregunta() {
      var pregunta = ronda[indice];
      /* Cada trozo acaba en pausa (punto), salvo si ya trae su propio signo. */
      var trozos = [pregunta.enunciado].concat(pregunta.opciones.map(function (o) { return o.texto; }));
      var texto = trozos.map(sinEmojis).filter(Boolean).map(function (t) {
        return /[.?!…]$/.test(t) ? t : t + '.';
      }).join(' ');
      var locucion = new SpeechSynthesisUtterance(texto);
      locucion.lang = 'es-ES';
      locucion.rate = 0.9;
      var voz = window.speechSynthesis.getVoices().filter(function (v) {
        return v.lang && v.lang.toLowerCase().indexOf('es') === 0;
      })[0];
      if (voz) {
        locucion.voice = voz;
      }
      callar();
      window.speechSynthesis.speak(locucion);
    }

    function mostrarFigura(pregunta) {
      var hijos = [];
      if (pregunta.figura) {
        pregunta.figura.grupos.forEach(function (g, i) {
          var op = pregunta.figura.op;
          if (i && (op === '+' || op === '−')) {
            hijos.push(crear('span', 'figura-op', op));
          }
          hijos.push(crear('span', 'figura-grupo', new Array(g[1] + 1).join(g[0])));
        });
      } else if (pregunta.dibujo) {
        hijos.push(crear('span', 'figura-dibujo', pregunta.dibujo));
      }
      elFigura.replaceChildren.apply(elFigura, hijos);
      elFigura.classList.toggle('hidden', !hijos.length);
      elFigura.classList.toggle('figura-cantidades', !!pregunta.figura);
    }

    function mostrarPregunta() {
      var pregunta = ronda[indice];
      callar();

      mostrarPasaje(pregunta.pasaje);
      actualizarProgreso();
      elEnunciado.textContent = pregunta.enunciado;
      mostrarFigura(pregunta);

      elOpciones.replaceChildren.apply(elOpciones, pregunta.opciones.map(function (opcion) {
        var li = crear('li');
        var boton = crear('button', 'quiz-opcion');
        boton.type = 'button';
        var marca = crear('span', 'quiz-marca');
        marca.setAttribute('aria-hidden', 'true');
        boton.appendChild(marca);
        boton.appendChild(crear('span', 'solo-lectores quiz-estado'));
        boton.appendChild(crear('span', null, opcion.texto));
        boton.addEventListener('click', function () {
          responder(opcion, boton);
        });
        li.appendChild(boton);
        return li;
      }));

      elFeedback.className = 'feedback hidden';
      elPorque.classList.add('hidden');
      elFeedback.textContent = '';
      btnSiguiente.classList.add('hidden');
    }

    function marcar(boton, clase, simbolo, textoLector) {
      boton.classList.add(clase);
      boton.querySelector('.quiz-marca').textContent = simbolo;
      boton.querySelector('.quiz-estado').textContent = textoLector;
    }

    function responder(opcionElegida, botonElegido) {
      var pregunta = ronda[indice];
      var botones = elOpciones.querySelectorAll('.quiz-opcion');

      botones.forEach(function (boton, i) {
        boton.disabled = true;
        /* El color nunca va solo: el símbolo ✓/✗ lo distingue también
           para quien no percibe bien el rojo y el verde. */
        if (pregunta.opciones[i].esCorrecta) {
          marcar(boton, 'correcta', '✓', 'Respuesta correcta: ');
        }
      });

      var acierto = opcionElegida.esCorrecta;
      if (acierto) {
        aciertos++;
      } else {
        marcar(botonElegido, 'incorrecta', '✗', 'Tu respuesta: ');
      }

      var textoCorrecta = pregunta.opciones.filter(function (o) { return o.esCorrecta; })[0].texto;
      var mensaje = acierto
        ? JEO.felicitacion()
        : 'No es correcto. La respuesta es: ' + textoCorrecta + '.';
      historial.push({ titulo: pregunta.enunciado, respuesta: textoCorrecta, bien: acierto,
                       tuya: acierto ? '' : opcionElegida.texto, explicacion: pregunta.explicacion });

      elFeedback.textContent = mensaje;
      JEO.explicar(elPorque, pregunta.explicacion, pregunta.curioso);
      elFeedback.className = 'feedback ' + (acierto ? 'correct' : 'incorrect');

      actualizarProgreso();
      btnSiguiente.textContent = indice + 1 < ronda.length ? 'Siguiente ➜' : 'Ver resultado 🏁';
      btnSiguiente.classList.remove('hidden');
      btnSiguiente.focus();
    }

    function siguiente() {
      indice++;
      if (indice < ronda.length) {
        mostrarPregunta();
        elEnunciado.focus();
        return;
      }
      terminar();
    }

    function terminar() {
      var total = ronda.length;
      var porcentaje = JEO.porcentaje(aciertos, total);

      elResultadoCifra.textContent = aciertos + ' de ' + total + ' (' + porcentaje + '%)';
      elResultadoMensaje.textContent = mensajeFinal(porcentaje);
      JEO.registrarResultado(porcentaje);
      if (elRepaso) {
        elRepaso.remove();
      }
      elRepaso = JEO.repaso(historial, config.curiosos);
      elResultado.insertBefore(elRepaso, btnReiniciar);

      elJuego.classList.add('hidden');
      elResultado.classList.remove('hidden');
      elResultadoTitulo.focus();
    }

    btnSiguiente.addEventListener('click', siguiente);
    btnReiniciar.addEventListener('click', empezar);
    if (puedeHablar) {
      btnEscuchar.addEventListener('click', leerPregunta);
    }

    empezar();
  };

  /**
   * Arranca un quiz con los datos que tools/generar.py incrusta en la página
   * como <script type="application/json">. En esos datos cada pregunta nombra
   * su pasaje por clave, en lugar de repetir el texto.
   */
  JEO.cargarQuiz = function (contenedor, elementoDatos) {
    var datos = JSON.parse(elementoDatos.textContent);
    var pasajes = datos.pasajes || {};

    JEO.iniciarQuiz({
      contenedor: contenedor,
      mezclarPreguntas: datos.mezclarPreguntas,
      leerEnVozAlta: datos.leerEnVozAlta,
      curiosos: datos.curiosos || [],
      preguntas: datos.preguntas.map(function (p) {
        if (p.pasaje && !pasajes[p.pasaje]) {
          throw new Error('cargarQuiz: la pregunta «' + p.enunciado + '» usa un pasaje que no existe.');
        }
        /* Las preguntas de un mismo pasaje reciben el mismo objeto: así el
           motor sabe que el texto no cambia y no lo vuelve a dibujar. */
        return {
          enunciado: p.enunciado,
          figura: p.figura,
          dibujo: p.dibujo,
          opciones: p.opciones,
          correcta: p.correcta,
          explicacion: p.explicacion,
          curioso: p.curioso,
          pasaje: p.pasaje ? pasajes[p.pasaje] : null
        };
      })
    });
  };
})(window.JEO);
