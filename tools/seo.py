"""Textos para posicionamiento: una sección con introducción y preguntas frecuentes por
página clave. Cada página apunta a su grupo de búsquedas (ver «busquedas»), sin
repetir la misma palabra clave en dos páginas, para que no compitan entre sí.

Lo usa tools/generar.py. Los textos son para personas: responden lo que busca
quien llega desde Google; las palabras clave aparecen de forma natural.
"""

PAGINAS = {
    'inicio': {
        'busquedas': ['juegos educativos online', 'juegos de aprendizaje online', 'juegos virtuales educativos'],
        'titulo': 'Juegos educativos online gratis para aprender jugando',
        'parrafos': [
            'Juegos Educativos Online reúne 80 juegos educativos online gratis de matemáticas, lectura y '
            'escritura, ciencias, emociones, inglés, tecnología y artes, desde Transición hasta grado 11. Son juegos '
            'virtuales educativos que funcionan en el computador, la tableta o el celular, sin registrarse y sin anuncios.',
            'Cada juego de aprendizaje online explica el porqué de cada respuesta, da pistas cuando hace falta y '
            'termina con un repaso y datos curiosos. Docentes y familias encuentran además fichas para imprimir, '
            'la relación con los DBA del MEN y consejos para acompañar.',
        ],
        'faq': [
            ('¿Los juegos educativos son gratis?',
             'Sí. Todos los juegos y fichas son gratuitos, no piden registro ni datos personales y no tienen anuncios.'),
            ('¿Para qué edades son los juegos?',
             'Hay actividades desde los 4 o 5 años (Transición) hasta los 16 (grado 11), organizadas por edad y por grado.'),
            ('¿Funcionan sin internet?',
             'Sí. Puedes instalar el sitio en el teléfono o el computador y seguir jugando sin conexión.'),
            ('¿Sirven para clase?',
             'Sí. Cada juego indica su objetivo, los DBA y estándares del MEN que trabaja, una guía didáctica, '
             'modo clase para proyectar y una ficha imprimible con solucionario.'),
        ],
    },
    'aprender-a-leer': {
        'busquedas': ['juegos para aprender a leer y escribir online', 'juegos lectoescritura online',
                      'juegos online para aprender a leer'],
        'titulo': 'Juegos para aprender a leer y escribir online',
        'parrafos': [
            'Estos juegos de lectoescritura online acompañan a niñas y niños de 4 a 9 años en cada paso: '
            'reconocer las vocales, unir sílabas, leer las primeras palabras y comprender cuentos cortos. '
            'Todas las preguntas se pueden escuchar en voz alta, así que sirven también para quien todavía no lee solo.',
            'Son juegos online para aprender a leer en casa o en el aula, con fichas para imprimir: trazar letras, '
            'encerrar dibujos por su sonido y colorear. Están alineados con los DBA de Transición, primero y segundo.',
        ],
        'faq': [
            ('¿A qué edad se empieza a aprender a leer?',
             'Entre los 4 y 5 años se trabaja la conciencia de los sonidos (vocales, rimas, sílabas); la lectura de '
             'palabras suele afianzarse en primero de primaria, hacia los 6 años. Cada niño tiene su ritmo.'),
            ('¿En qué orden conviene usar los juegos?',
             'Primero las vocales, luego las sílabas, después las primeras palabras y, por último, la lectura de cuentos cortos.'),
            ('¿Cómo ayudo a mi hijo a aprender a leer jugando?',
             'Juega a su lado 15 minutos al día, lee en voz alta las preguntas, pídele que repita los sonidos y '
             'celebra el esfuerzo. Las fichas impresas ayudan a practicar sin pantalla.'),
            ('¿Los juegos de lectoescritura tienen audio?',
             'Sí: cada pregunta tiene un botón «Escuchar» que la lee en voz alta.'),
        ],
    },
    'espanol': {
        'busquedas': ['juegos de español online', 'juegos de lectura y escritura', 'juegos de ortografía online'],
        'titulo': 'Juegos de español online: lectura, escritura y ortografía',
        'parrafos': [
            'Los juegos de español van desde las vocales y las sílabas hasta la comprensión de lectura, la '
            'ortografía, la gramática y los tipos de texto. Cada pregunta explica la respuesta para que el error '
            'también enseñe.',
            'Si buscas juegos para aprender a leer y escribir, empieza por la sección de lectoescritura; para '
            'grados superiores, prueba los textos informativos, la tilde y la intención comunicativa.',
        ],
        'faq': [
            ('¿Qué temas de español incluye?',
             'Vocales, sílabas, primeras palabras, comprensión lectora, ortografía, gramática, sinónimos, tipos de '
             'texto y situaciones comunicativas.'),
            ('¿Están alineados con el currículo?',
             'Sí, con los DBA de Lenguaje y los Estándares Básicos de Competencias del MEN de Colombia.'),
        ],
    },
    'emociones': {
        'busquedas': ['juegos de emociones online', 'juegos de educación emocional', 'juegos para reconocer emociones'],
        'titulo': 'Juegos de emociones online para niños',
        'parrafos': [
            'Los juegos de emociones online ayudan a niñas y niños a reconocer la alegría, la tristeza, el enojo o '
            'el miedo en sí mismos y en los demás, a calmarse con pasos sencillos y a resolver conflictos sin violencia.',
            'Son actividades de educación emocional para hacer en familia o en clase: después de jugar, conversen '
            'sobre lo que sintieron. Están alineados con los DBA y los estándares del MEN.',
        ],
        'faq': [
            ('¿Para qué sirve la educación emocional?',
             'Para reconocer y nombrar lo que sentimos, manejarlo de forma sana y relacionarnos mejor: es la base '
             'de la convivencia y del aprendizaje.'),
            ('¿Desde qué edad se pueden usar?',
             'Desde los 4 o 5 años, con un adulto que lea las preguntas; los juegos tienen lectura en voz alta.'),
        ],
    },
    'matematicas': {
        'busquedas': ['juegos de matemáticas online', 'juegos matemáticas 1 primaria online', 'juegos de sumas y restas'],
        'titulo': 'Juegos de matemáticas online para primaria y secundaria',
        'parrafos': [
            'Juegos de matemáticas online para contar, sumar, restar, multiplicar y dividir, con ejercicios que '
            'cambian en cada partida, además de fracciones, geometría, potencias y números enteros.',
            'Para primero de primaria hay juegos de conteo y de sumas y restas hasta 10 con dibujos para contar. '
            'En todos los grados se trabajan situaciones problema de la vida real, como la tienda escolar con pesos colombianos.',
        ],
        'faq': [
            ('¿Qué juegos de matemáticas hay para 1.º de primaria?',
             'Matemáticas para 1.º (conteo, sumas y restas hasta 10, números anterior y siguiente), problemas de '
             'suma y resta y la práctica de suma con ejercicios nuevos en cada partida.'),
            ('¿Incluyen resolución de problemas?',
             'Sí. Cada actividad incluye situaciones problema, y las fichas imprimibles traen una al final.'),
        ],
    },
    'secundaria': {
        'busquedas': ['juegos interactivos para jóvenes', 'juegos educativos para secundaria', 'juegos para adolescentes'],
        'titulo': 'Juegos interactivos para jóvenes de secundaria',
        'parrafos': [
            'Juegos interactivos para jóvenes de 11 a 16 años: química, física, historia, matemáticas, inglés y '
            'programación con retos de parejas, ordenar y preguntas con explicación.',
            'Sirven para repasar antes de una evaluación o para trabajar en el aula con el modo clase, y cada uno '
            'muestra los estándares del MEN que trabaja.',
        ],
        'faq': [
            ('¿Qué materias tienen juegos para secundaria?',
             'Matemáticas, química, física, historia, geografía, tecnología, programación, inglés y artes.'),
        ],
    },
}
