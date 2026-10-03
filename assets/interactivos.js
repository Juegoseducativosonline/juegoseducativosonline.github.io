/*
 * Motores de los juegos interactivos «parejas» y «ordenar». Requiere
 * assets/site.js y assets/interactivos.css.
 *
 * tools/generar.py incrusta los datos en la página como
 * <script type="application/json"> y llama a JEO.cargarJuego.
 *
 * Todo el texto se inserta con textContent, nunca como HTML.
 */
(function (JEO) {
  'use strict';

  if (!JEO) {
    throw new Error('interactivos.js necesita que assets/site.js se cargue antes.');
  }

  /* Tras un fallo en parejas, el tiempo que se ven marcadas en rojo. */
  var PAUSA_FALLO_MS = 700;

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

  function boton(clase, texto) {
    var b = crear('button', clase, texto);
    b.type = 'button';
    return b;
  }

  function formatoTiempo(ms) {
    var segundos = Math.round(ms / 1000);
    var minutos = Math.floor(segundos / 60);
    var resto = segundos % 60;
    return minutos + ':' + (resto < 10 ? '0' : '') + resto;
  }

  function estrellas(fallos) {
    if (fallos === 0) {
      return { cuantas: 3, mensaje: '🏆 ¡Perfecto! Sin un solo fallo.' };
    }
    if (fallos <= 3) {
      return { cuantas: 2, mensaje: '🌟 ¡Muy bien! Casi perfecto.' };
    }
    return { cuantas: 1, mensaje: '💪 ¡Completado! Juega otra vez para bajar tus fallos.' };
  }

  /**
   * Esqueleto común: progreso, instrucción, zona de juego, mensajes, botón de
   * seguir y pantalla final. Cada motor rellena la zona de juego.
   */
  function montarEstructura(contenedor) {
    var e = {
      progreso: crear('p', 'quiz-progreso'),
      barra: crear('div', 'progress-bar'),
      relleno: crear('div', 'progress-fill'),
      instruccion: crear('h2', 'quiz-enunciado'),
      zona: crear('div', 'juego-zona'),
      estado: crear('p', 'feedback hidden'),
      porque: crear('div', 'quiz-porque hidden'),
      seguir: boton('btn hidden', 'Siguiente ➜'),
      juego: crear('div', 'quiz-juego'),
      final: crear('section', 'quiz-resultado hidden'),
      finalTitulo: crear('h2', null, 'Resultado'),
      finalEstrellas: crear('p', 'resultado-estrellas'),
      finalCifras: crear('p', 'quiz-resultado-cifra'),
      finalMensaje: crear('p'),
      reiniciar: boton('btn btn-acento', '🔄 Jugar de nuevo')
    };
    e.barra.setAttribute('role', 'progressbar');
    e.barra.setAttribute('aria-label', 'Progreso del juego');
    e.barra.setAttribute('aria-valuemin', '0');
    e.barra.appendChild(e.relleno);
    e.instruccion.tabIndex = -1;
    e.estado.setAttribute('role', 'status');
    e.estado.setAttribute('aria-live', 'polite');
    e.finalTitulo.tabIndex = -1;

    var acciones = crear('div', 'controls');
    acciones.appendChild(e.seguir);
    [e.progreso, e.barra, e.instruccion, e.zona, e.estado, e.porque, acciones].forEach(function (el) {
      e.juego.appendChild(el);
    });
    [e.finalTitulo, e.finalEstrellas, e.finalCifras, e.finalMensaje, e.reiniciar].forEach(function (el) {
      e.final.appendChild(el);
    });
    contenedor.replaceChildren(e.juego, e.final);
    return e;
  }

  function avisar(e, mensaje, clase) {
    e.estado.textContent = mensaje;
    e.estado.className = 'feedback ' + (clase || '');
  }

  function progreso(e, texto, hechas, total) {
    e.progreso.textContent = texto;
    e.relleno.style.width = (hechas / total) * 100 + '%';
    e.barra.setAttribute('aria-valuemax', String(total));
    e.barra.setAttribute('aria-valuenow', String(hechas));
  }

  function mostrarFinal(e, fallos, tiempoMs, resumen, items, curiosos) {
    var nota = estrellas(fallos);
    JEO.registrarResultado(nota.cuantas === 3 ? 100 : nota.cuantas === 2 ? 75 : 40);
    var viejo = e.final.querySelector('.repaso');
    if (viejo) {
      viejo.remove();
    }
    e.final.insertBefore(JEO.repaso(items || [], curiosos), e.reiniciar);
    e.finalEstrellas.textContent = '⭐⭐⭐'.slice(0, nota.cuantas);
    e.finalEstrellas.setAttribute('aria-label', nota.cuantas + ' de 3 estrellas');
    e.finalCifras.textContent = '⏱️ ' + formatoTiempo(tiempoMs) + ' · ' + fallos + (fallos === 1 ? ' fallo' : ' fallos');
    e.finalMensaje.textContent = resumen + ' ' + nota.mensaje;
    e.juego.classList.add('hidden');
    e.final.classList.remove('hidden');
    e.finalTitulo.focus();
  }

  /* --- Parejas -------------------------------------------------------------- */

  /**
   * Relaciona cada elemento de la columna A con su pareja de la columna B.
   * Se elige uno de cada lado, en cualquier orden. Si hay muchas parejas se
   * juegan por rondas, para que quepan en una pantalla de móvil.
   */
  JEO.iniciarParejas = function (contenedor, datos) {
    var e = montarEstructura(contenedor);
    var rondas, indiceRonda, fallos, inicio, aciertosRonda, bloqueado;
    var seleccion = { a: null, b: null };

    function repartirEnRondas(pares) {
      var mezclados = JEO.mezclar(pares);
      var porRonda = datos.paresPorRonda;
      var resultado = [];
      for (var i = 0; i < mezclados.length; i += porRonda) {
        resultado.push(mezclados.slice(i, i + porRonda));
      }
      /* Una ronda final de 1 o 2 parejas sería trivial: se une a la anterior. */
      if (resultado.length > 1 && resultado[resultado.length - 1].length < 3) {
        var sobrantes = resultado.pop();
        resultado[resultado.length - 1] = resultado[resultado.length - 1].concat(sobrantes);
      }
      return resultado;
    }

    function empezar() {
      rondas = repartirEnRondas(datos.pares);
      indiceRonda = 0;
      fallos = 0;
      inicio = Date.now();
      e.final.classList.add('hidden');
      e.juego.classList.remove('hidden');
      mostrarRonda();
    }

    function columna(titulo, pares, lado) {
      var col = crear('div', 'parejas-columna');
      col.appendChild(crear('h3', 'parejas-titulo', titulo));
      var lista = crear('ul', 'parejas-lista');
      JEO.mezclar(pares).forEach(function (par) {
        var li = crear('li');
        var b = boton('pareja', lado === 'a' ? par.a : par.b);
        b.setAttribute('aria-pressed', 'false');
        b.parLado = lado;
        b.par = par;
        b.addEventListener('click', function () {
          elegir(b);
        });
        li.appendChild(b);
        lista.appendChild(li);
      });
      col.appendChild(lista);
      return col;
    }

    function mostrarRonda() {
      var pares = rondas[indiceRonda];
      aciertosRonda = 0;
      bloqueado = false;
      seleccion = { a: null, b: null };
      e.instruccion.textContent = rondas.length > 1
        ? 'Ronda ' + (indiceRonda + 1) + ' de ' + rondas.length + ': relaciona cada pareja'
        : 'Relaciona cada pareja';
      var tablero = crear('div', 'parejas-tablero');
      tablero.appendChild(columna(datos.etiquetaA, pares, 'a'));
      tablero.appendChild(columna(datos.etiquetaB, pares, 'b'));
      e.zona.replaceChildren(tablero);
      e.estado.className = 'feedback hidden';
      e.porque.classList.add('hidden');
      e.seguir.classList.add('hidden');
      actualizarProgreso();
    }

    function actualizarProgreso() {
      var hechas = 0;
      for (var i = 0; i < indiceRonda; i++) {
        hechas += rondas[i].length;
      }
      hechas += aciertosRonda;
      progreso(e, 'Parejas: ' + hechas + ' de ' + datos.pares.length + ' · Fallos: ' + fallos,
               hechas, datos.pares.length);
    }

    function soltar(lado) {
      if (seleccion[lado]) {
        seleccion[lado].setAttribute('aria-pressed', 'false');
        seleccion[lado] = null;
      }
    }

    function elegir(b) {
      if (bloqueado || b.disabled) {
        return;
      }
      var lado = b.parLado;
      if (seleccion[lado] === b) {
        soltar(lado);
        return;
      }
      soltar(lado);
      seleccion[lado] = b;
      b.setAttribute('aria-pressed', 'true');
      if (seleccion.a && seleccion.b) {
        comprobar(seleccion.a, seleccion.b);
      }
    }

    function comprobar(ba, bb) {
      if (ba.par === bb.par) {
        [ba, bb].forEach(function (x) {
          x.setAttribute('aria-pressed', 'false');
          x.classList.add('emparejada');
          x.disabled = true;
          x.insertBefore(crear('span', 'solo-lectores', 'Emparejada: '), x.firstChild);
        });
        seleccion = { a: null, b: null };
        aciertosRonda++;
        actualizarProgreso();
        JEO.explicar(e.porque, '', ba.par.dato || '');
        if (aciertosRonda === rondas[indiceRonda].length) {
          terminarRonda();
        } else {
          avisar(e, '✓ ' + ba.par.a + ' — ' + ba.par.b, 'correct');
        }
        return;
      }

      fallos++;
      actualizarProgreso();
      avisar(e, '✗ No son pareja. Inténtalo otra vez.', 'incorrect');
      /* Se marcan en rojo un momento; mientras, no se aceptan más clics. */
      bloqueado = true;
      ba.classList.add('fallo');
      bb.classList.add('fallo');
      setTimeout(function () {
        ba.classList.remove('fallo');
        bb.classList.remove('fallo');
        soltar('a');
        soltar('b');
        bloqueado = false;
      }, PAUSA_FALLO_MS);
    }

    function terminarRonda() {
      var ultima = indiceRonda + 1 === rondas.length;
      avisar(e, ultima ? '🎉 ¡Todas las parejas encontradas!' : '🎉 ¡Ronda completada!', 'correct');
      e.seguir.textContent = ultima ? 'Ver resultado 🏁' : 'Siguiente ronda ➜';
      e.seguir.classList.remove('hidden');
      e.seguir.focus();
    }

    e.seguir.addEventListener('click', function () {
      indiceRonda++;
      if (indiceRonda < rondas.length) {
        mostrarRonda();
        e.instruccion.focus();
        return;
      }
      mostrarFinal(e, fallos, Date.now() - inicio,
                   'Has relacionado las ' + datos.pares.length + ' parejas.',
                   datos.pares.map(function (p) {
                     return { titulo: p.a, respuesta: p.b, explicacion: p.dato || '' };
                   }), datos.curiosos);
    });
    e.reiniciar.addEventListener('click', empezar);

    empezar();
  };

  /* --- Ordenar -------------------------------------------------------------- */

  /**
   * Coloca los elementos de cada ronda en el orden correcto con los botones
   * ↑ y ↓, y comprueba. Funciona igual con ratón, dedo y teclado.
   */
  JEO.iniciarOrdenar = function (contenedor, datos) {
    var e = montarEstructura(contenedor);
    var indiceRonda, fallos, inicio, actual, resuelta;
    var comprobar = boton('btn', '✓ Comprobar');
    var btnPista = boton('btn btn-secundario', '💡 Pista');
    var btnSolucion = boton('btn btn-secundario hidden', '👀 Ver la solución');
    var fallosRonda, pistasRonda, resultados;
    e.seguir.parentNode.insertBefore(comprobar, e.seguir);
    e.seguir.parentNode.insertBefore(btnPista, e.seguir);
    e.seguir.parentNode.insertBefore(btnSolucion, e.seguir);

    function desordenar(elementos) {
      /* Nunca se presenta una ronda ya resuelta. */
      var copia;
      do {
        copia = JEO.mezclar(elementos);
      } while (copia.join('\u0000') === elementos.join('\u0000'));
      return copia;
    }

    function empezar() {
      indiceRonda = 0;
      fallos = 0;
      resultados = [];
      inicio = Date.now();
      e.final.classList.add('hidden');
      e.juego.classList.remove('hidden');
      mostrarRonda();
    }

    function mostrarRonda() {
      var ronda = datos.rondas[indiceRonda];
      actual = desordenar(ronda.elementos);
      resuelta = false;
      fallosRonda = 0;
      pistasRonda = 0;
      e.instruccion.textContent = ronda.instruccion;
      e.estado.className = 'feedback hidden';
      e.porque.classList.add('hidden');
      e.seguir.classList.add('hidden');
      comprobar.classList.remove('hidden');
      btnPista.classList.remove('hidden');
      btnSolucion.classList.add('hidden');
      progreso(e, 'Ronda ' + (indiceRonda + 1) + ' de ' + datos.rondas.length + ' · Fallos: ' + fallos,
               indiceRonda, datos.rondas.length);
      dibujar(null);
    }

    /* `marcas`: null, o por posición true/false para pintar aciertos y fallos. */
    function dibujar(marcas, enfocar) {
      var lista = crear('ol', 'ordenar-lista');
      actual.forEach(function (texto, i) {
        var li = crear('li', 'ordenar-elemento');
        if (marcas) {
          li.classList.add(marcas[i] ? 'correcto' : 'incorrecto');
        }
        li.appendChild(crear('span', 'ordenar-numero', String(i + 1)));
        li.appendChild(crear('span', 'ordenar-texto', texto));
        if (marcas) {
          li.appendChild(crear('span', 'solo-lectores', marcas[i] ? ' (en su sitio)' : ' (fuera de sitio)'));
        }
        var acciones = crear('span', 'ordenar-acciones');
        [['subir', '↑', -1, 'Subir'], ['bajar', '↓', 1, 'Bajar']].forEach(function (d) {
          var b = boton('ordenar-mover', d[1]);
          b.dataset.accion = d[0];
          b.setAttribute('aria-label', d[3] + ' «' + texto + '»');
          b.disabled = resuelta || (d[2] < 0 ? i === 0 : i === actual.length - 1);
          b.addEventListener('click', function () {
            mover(i, d[2], d[0]);
          });
          acciones.appendChild(b);
        });
        li.appendChild(acciones);
        lista.appendChild(li);
      });
      e.zona.replaceChildren(lista);
      if (enfocar) {
        var destino = lista.children[enfocar.posicion].querySelector('[data-accion="' + enfocar.accion + '"]');
        /* En un extremo el botón queda desactivado: se enfoca el del otro sentido. */
        if (destino.disabled) {
          destino = lista.children[enfocar.posicion].querySelector('.ordenar-mover:not(:disabled)');
        }
        if (destino) {
          destino.focus();
        }
      }
    }

    function mover(i, sentido, accion) {
      var j = i + sentido;
      var tmp = actual[i];
      actual[i] = actual[j];
      actual[j] = tmp;
      e.estado.className = 'feedback hidden';
      /* El foco sigue al elemento movido, para poder pulsar varias veces seguidas. */
      dibujar(null, { posicion: j, accion: accion });
    }

    comprobar.addEventListener('click', function () {
      var ronda = datos.rondas[indiceRonda];
      var marcas = actual.map(function (texto, i) {
        return texto === ronda.elementos[i];
      });
      var bien = marcas.filter(Boolean).length;

      if (bien === marcas.length) {
        resuelta = true;
        dibujar(marcas);
        avisar(e, '🎉 ¡Orden correcto!', 'correct');
        cerrarRonda(true);
        var ultima = indiceRonda + 1 === datos.rondas.length;
        e.seguir.textContent = ultima ? 'Ver resultado 🏁' : 'Siguiente ronda ➜';
        e.seguir.classList.remove('hidden');
        progreso(e, 'Ronda ' + (indiceRonda + 1) + ' de ' + datos.rondas.length + ' · Fallos: ' + fallos,
                 indiceRonda + 1, datos.rondas.length);
        e.seguir.focus();
        return;
      }

      fallos++;
      fallosRonda++;
      dibujar(marcas);
      /* Tras dos intentos se ofrece ver la solución, para no quedarse atascado. */
      if (fallosRonda >= 2) {
        btnSolucion.classList.remove('hidden');
      }
      progreso(e, 'Ronda ' + (indiceRonda + 1) + ' de ' + datos.rondas.length + ' · Fallos: ' + fallos,
               indiceRonda, datos.rondas.length);
      avisar(e, bien + ' de ' + marcas.length + ' en su sitio. Mueve los marcados en rojo y vuelve a comprobar.',
             'incorrect');
    });

    /* Común al acierto y a «ver la solución»: explicación, repaso y botón de seguir. */
    function cerrarRonda(bien) {
      var ronda = datos.rondas[indiceRonda];
      comprobar.classList.add('hidden');
      btnPista.classList.add('hidden');
      btnSolucion.classList.add('hidden');
      JEO.explicar(e.porque, ronda.explicacion, ronda.curioso);
      resultados.push({ titulo: ronda.instruccion, respuesta: ronda.elementos.join(' → '),
                        explicacion: ronda.explicacion, bien: bien && fallosRonda === 0 });
      var ultima = indiceRonda + 1 === datos.rondas.length;
      e.seguir.textContent = ultima ? 'Ver resultado 🏁' : 'Siguiente ronda ➜';
      e.seguir.classList.remove('hidden');
      progreso(e, 'Ronda ' + (indiceRonda + 1) + ' de ' + datos.rondas.length + ' · Fallos: ' + fallos,
               indiceRonda + 1, datos.rondas.length);
      e.seguir.focus();
    }

    /* Pista: primero la del contenido, si la hay; luego, cada vez, dónde va uno de
       los elementos que aún están fuera de sitio. */
    btnPista.addEventListener('click', function () {
      var ronda = datos.rondas[indiceRonda];
      pistasRonda++;
      if (ronda.pista && pistasRonda === 1) {
        avisar(e, '💡 ' + ronda.pista, 'pista');
        return;
      }
      for (var i = 0; i < ronda.elementos.length; i++) {
        if (actual[i] !== ronda.elementos[i]) {
          avisar(e, '💡 En el puesto ' + (i + 1) + ' va «' + ronda.elementos[i] + '».', 'pista');
          return;
        }
      }
      avisar(e, '💡 ¡Ya está todo en su sitio! Pulsa «Comprobar».', 'pista');
    });

    btnSolucion.addEventListener('click', function () {
      var ronda = datos.rondas[indiceRonda];
      actual = ronda.elementos.slice();
      resuelta = true;
      dibujar(actual.map(function () { return true; }));
      avisar(e, 'Así es el orden correcto. Léelo con calma y fíjate en el porqué.', 'pista');
      cerrarRonda(false);
    });

    e.seguir.addEventListener('click', function () {
      indiceRonda++;
      if (indiceRonda < datos.rondas.length) {
        mostrarRonda();
        e.instruccion.focus();
        return;
      }
      mostrarFinal(e, fallos, Date.now() - inicio,
                   'Has ordenado las ' + datos.rondas.length + ' rondas.', resultados, datos.curiosos);
    });
    e.reiniciar.addEventListener('click', empezar);

    empezar();
  };

  /** Arranca el motor que corresponde a los datos incrustados en la página. */
  JEO.cargarJuego = function (contenedor, elementoDatos) {
    var datos = JSON.parse(elementoDatos.textContent);
    if (datos.tipo === 'parejas') {
      JEO.iniciarParejas(contenedor, datos);
    } else if (datos.tipo === 'ordenar') {
      JEO.iniciarOrdenar(contenedor, datos);
    } else {
      throw new Error('cargarJuego: tipo de juego desconocido «' + datos.tipo + '».');
    }
  };
})(window.JEO);
