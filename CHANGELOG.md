# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Este proyecto sigue [Versionado Semántico](https://semver.org/lang/es/).

La versión vive en un único sitio: `src/ytdubber/__init__.py`. `pyproject.toml` la lee de
ahí con `dynamic = ["version"]`.

## [0.3.0] - 2026-09-11

Puesta en marcha y validación completa sobre Windows 11 + RTX 3070 8 GB, más un panel de
control local. Todo lo que sigue está verificado con ejecuciones reales, no solo con tests.

### Añadido

- **Panel de control local** (`ytdubber web`): lanzar un doblaje desde el navegador con
  seguimiento de las 7 etapas, progreso por bloque durante el TTS, avisos agrupados, log en
  vivo y cancelación. Un trabajo cada vez, porque el pipeline usa `work/` y `output/`
  compartidos (`src/ytdubber/webapp.py`, `src/ytdubber/web/index.html`).
- **Biblioteca de vídeos doblados** (`src/ytdubber/library.py`): al terminar, el resultado
  se archiva en `library/<fecha>_<titulo>/` con miniatura y metadatos, y los intermedios se
  borran. Listado, reproducción, descarga y borrado desde el panel.
- **Lanzador `YouTube Dubber.exe`** (`scripts/launcher.py`, `scripts/build_launcher.ps1`):
  arranca Ollama si hace falta, levanta el panel y abre el navegador. Se compila en un venv
  aparte (`.venv-build`) para no tocar el entorno de ejecución.
- `scripts/panel.ps1` como alternativa al ejecutable.
- `ytdubber --version`; la versión aparece también en `doctor` y en el panel.
- Tope duro de segmentación configurable (`hard_max_duration`, 16 s por defecto).
- Troceo automático del texto antes del TTS cuando excede el contexto del modelo.
- Presupuesto de longitud por bloque en la traducción, derivado de la ventana temporal
  disponible y del ritmo medido del TTS (12,5 caracteres/segundo).
- Aviso explícito por bloque cuando la voz sintetizada no cabe en su ventana.

### Corregido

- **Bloqueo por *device-side assert* de CUDA en el TTS.** Con ASR sin puntuar ni pausas,
  todas las reglas de corte del segmentador podían ser vetadas y un bloque crecía sin
  límite (246 s, 4087 caracteres → 2952 tokens). El T3 de Chatterbox dimensiona su
  embedding de posiciones a 2048 tokens, así que el índice se salía de la tabla y el
  proceso moría sin posibilidad de recuperación. Ahora hay un tope duro en el segmentador
  y un troceo defensivo antes de `generate()`.
- **Se doblaba el vídeo equivocado en silencio.** La plantilla de salida de yt-dlp es un
  nombre fijo, no ligado a la URL; con un `work/source.*` previo, yt-dlp respondía
  «has already been downloaded» y el pipeline procesaba el fichero anterior. Ahora se purga
  antes de descargar.
- **La suite de tests escribía en el `work/` del proyecto.** El test de integración de
  FFmpeg llamaba al `download_source()` real, dejando un vídeo de 2 s que envenenaba la
  siguiente ejecución. Ahora se aísla en un directorio temporal.
- **`pytest` sin argumentos ejecutaba el smoke test de GPU.** `scripts/model_smoke_test.py`
  encaja con el patrón de descubrimiento por defecto, así que los tests unitarios
  descargaban y ejecutaban todos los modelos. Acotado con `testpaths = ["tests"]`.
- **El reintento de traducción se quedaba con el peor candidato.** El bucle asignaba
  `best = text` en cada vuelta, de modo que un tercer intento vacío o con cirílico
  sobrescribía una traducción válida del primero. Ahora puntúa los candidatos y conserva el
  mejor, con respaldo al texto original si los tres fallan.
- **Se recortaba voz en silencio.** `fit_audio` calculaba la señal `trimmed` pero nadie la
  leía. Además comprimía frases que cabrían a velocidad natural en la pausa siguiente.
- **El *ducking* devolvía la música a volumen completo con el español aún hablando**,
  porque usaba el final del bloque original en lugar de la duración real doblada.
- `scripts/setup_windows.ps1`: resuelve 7-Zip cuando no está en el PATH y verifica la
  integridad del archivo descargado. Una descarga truncada dejaba `vendor/cuda12` vacío y
  afloraba mucho más tarde como `cublas64_12.dll is not found`.
- El lanzador mata el árbol de procesos completo al cerrar. En Windows el `python.exe` de
  un venv es un redirector que ejecuta el intérprete base como hijo, así que terminar el
  proceso directo dejaba el servidor vivo ocupando el puerto.

### Notas de validación

- Suite de tests: 28 casos, todos en verde.
- `scripts/model_smoke_test.ps1`: PASS con CUDA (PyTorch 2.6.0+cu126, RTX 3070).
- Doblaje completo verificado de extremo a extremo; MP4 final íntegro y re-transcrito como
  español con probabilidad 0,98.
- **Limitación conocida:** con locutores rápidos el resultado se degrada. Chatterbox habla
  a ~111 palabras/minuto y no admite control de duración; con una fuente a ~194 p/m hace
  falta comprimir 1,46x y el perfil `balanced` capa la aceleración a 1,12x, de modo que
  parte de la voz se recorta. Los bloques afectados se avisan durante la ejecución.
- **Variabilidad entre ejecuciones:** dos pasadas idénticas del mismo vídeo dieron 32 % y
  8 % de voz recortada. El ruido viene de los timestamps de palabra y de la longitud
  variable que devuelve el traductor. Una sola ejecución no es concluyente para medir
  calidad de encaje temporal.
- `large-v3` frente a `large-v3-turbo` sobre el mismo audio: misma puntuación (9 signos,
  0 comas en ambos), pero `large-v3` transcribe bastante mejor —turbo confundía
  «censorship» con «sensor shape» y «Qwen» con «queen»— y detecta 3,7 veces más pausas, a
  cambio de 122 s frente a 28 s.

## [0.2.0]

Versión de partida del proyecto, previa a este trabajo.
