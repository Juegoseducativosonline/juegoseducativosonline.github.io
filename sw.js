/* Generado por tools/generar.py. No lo edites a mano. */
/*
 * Guarda el sitio completo en el dispositivo para que funcione sin internet.
 * El nombre de la caché cambia con cada versión publicada: el navegador
 * descarga la nueva y borra la anterior.
 */
'use strict';

var CACHE = 'jeo-5c5fe2c398cc';
var RECURSOS = [
  "/",
  "/404.html",
  "/artes/",
  "/artes/colores-ficha.html",
  "/artes/colores.html",
  "/artes/musica-ficha.html",
  "/artes/musica.html",
  "/assets/favicon.svg",
  "/assets/icono-180.png",
  "/assets/icono-192.png",
  "/assets/icono-512.png",
  "/assets/materias.css?v=9f1248c012",
  "/assets/quiz.css?v=ca763d9b25",
  "/assets/quiz.js?v=3ac616eefd",
  "/assets/site.css?v=86e2b85d18",
  "/assets/site.js?v=87e83ed258",
  "/descargar/",
  "/emociones/",
  "/emociones/manejar-ficha.html",
  "/emociones/manejar.html",
  "/emociones/reconocer-ficha.html",
  "/emociones/reconocer.html",
  "/espanol/",
  "/espanol/gramatica-ficha.html",
  "/espanol/gramatica.html",
  "/espanol/juego-lectura-ficha.html",
  "/espanol/juego-lectura.html",
  "/espanol/ortografia-ficha.html",
  "/espanol/ortografia.html",
  "/espanol/primeras-palabras-ficha.html",
  "/espanol/primeras-palabras.html",
  "/espanol/silabas-ficha.html",
  "/espanol/silabas.html",
  "/espanol/vocales-ficha.html",
  "/espanol/vocales.html",
  "/fisica/",
  "/fisica/energia-ficha.html",
  "/fisica/energia.html",
  "/fisica/fuerzas-ficha.html",
  "/fisica/fuerzas.html",
  "/fisica/luz-sonido-ficha.html",
  "/fisica/luz-sonido.html",
  "/ingles/",
  "/ingles/colores-numeros-ficha.html",
  "/ingles/colores-numeros.html",
  "/ingles/saludos-ficha.html",
  "/ingles/saludos.html",
  "/manifest.webmanifest",
  "/matematicas/",
  "/matematicas/division_practice.html",
  "/matematicas/fracciones-ficha.html",
  "/matematicas/fracciones.html",
  "/matematicas/geometria-ficha.html",
  "/matematicas/geometria.html",
  "/matematicas/multiplication_practice.html",
  "/matematicas/primero-primaria-ficha.html",
  "/matematicas/primero-primaria.html",
  "/matematicas/resta_practice_html.html",
  "/matematicas/suma_practice.html",
  "/naturales/",
  "/naturales/animales-ficha.html",
  "/naturales/animales.html",
  "/naturales/cuerpo-humano-ficha.html",
  "/naturales/cuerpo-humano.html",
  "/naturales/juego-plantas-ficha.html",
  "/naturales/juego-plantas.html",
  "/quimica/",
  "/quimica/elementos-ficha.html",
  "/quimica/elementos.html",
  "/quimica/estados-materia-ficha.html",
  "/quimica/estados-materia.html",
  "/quimica/mezclas-ficha.html",
  "/quimica/mezclas.html",
  "/sociales/",
  "/sociales/geografia-ficha.html",
  "/sociales/geografia.html",
  "/sociales/quiz-historia-ficha.html",
  "/sociales/quiz-historia.html",
  "/tecnologia/",
  "/tecnologia/computadora-ficha.html",
  "/tecnologia/computadora.html",
  "/tecnologia/internet-seguro-ficha.html",
  "/tecnologia/internet-seguro.html",
  "/tecnologia/maquinas-simples-ficha.html",
  "/tecnologia/maquinas-simples.html"
];
var FUENTES = /^https:\/\/fonts\.(googleapis|gstatic)\.com\//;

self.addEventListener('install', function (evento) {
  evento.waitUntil(caches.open(CACHE).then(function (cache) {
    return cache.addAll(RECURSOS);
  }).then(function () {
    return self.skipWaiting();
  }));
});

self.addEventListener('activate', function (evento) {
  evento.waitUntil(caches.keys().then(function (nombres) {
    return Promise.all(nombres.filter(function (n) {
      return n.indexOf('jeo-') === 0 && n !== CACHE;
    }).map(function (n) {
      return caches.delete(n);
    }));
  }).then(function () {
    return self.clients.claim();
  }));
});

self.addEventListener('fetch', function (evento) {
  var peticion = evento.request;
  if (peticion.method !== 'GET') {
    return;
  }

  /* Páginas: primero la red, para ver siempre lo último; sin conexión, la copia guardada. */
  if (peticion.mode === 'navigate') {
    evento.respondWith(fetch(peticion).catch(function () {
      return caches.match(peticion, { ignoreSearch: true }).then(function (guardada) {
        return guardada || caches.match('/404.html');
      });
    }));
    return;
  }

  /* Tipografía de Google: se guarda la primera vez que se usa. */
  if (FUENTES.test(peticion.url)) {
    evento.respondWith(caches.open(CACHE).then(function (cache) {
      return cache.match(peticion).then(function (guardada) {
        return guardada || fetch(peticion).then(function (respuesta) {
          cache.put(peticion, respuesta.clone());
          return respuesta;
        });
      });
    }));
    return;
  }

  /* Estilos, scripts e iconos llevan su versión en la URL: la copia guardada siempre vale. */
  if (new URL(peticion.url).origin === self.location.origin) {
    evento.respondWith(caches.match(peticion).then(function (guardada) {
      return guardada || fetch(peticion);
    }));
  }
});
