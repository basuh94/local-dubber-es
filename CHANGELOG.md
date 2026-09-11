# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Este proyecto sigue [Versionado Semántico](https://semver.org/lang/es/).

La versión vive en un único sitio: `src/ytdubber/__init__.py`. `pyproject.toml` la lee de
ahí con `dynamic = ["version"]`.

## [0.4.0] - 2026-09-11

Trabajo sobre la calidad del encaje temporal, guiado por mediciones repetidas sobre una
charla técnica de 20 minutos con locutor rápido (el peor caso del pipeline).

**Resultado: la voz recortada pasa del 32 % al 0 % del habla** (de 551 s a 5 s, de 58
bloques afectados a 1 de 78).

### Corregido

- **La referencia de voz determinaba la velocidad de todo el doblaje, y se elegía sin
  mirarla.** `choose_voice_reference` ordenaba por confianza del reconocimiento y
  duración. Chatterbox clona el *ritmo* del clip de referencia casi proporcionalmente, así
  que cuando el selector caía en un pasaje lento, el español se alargaba y se recortaba en
  todos los bloques. Medido aislando esa única variable: una referencia de 8,74 car/s
  produjo un doblaje de 9,93 car/s con 693 s recortados; una de 19,74 car/s produjo 14,89
  car/s con 57 s recortados. **92 % menos de voz perdida sin tocar nada más y sin coste de
  GPU.** Ahora, entre los candidatos que el ASR entendió bien (confianza ≥ 90 % de la
  mejor), se elige el de habla más rápida.

  Este era también el origen de la «variabilidad entre ejecuciones» documentada en 0.3.0:
  no era ruido, era el selector eligiendo pasajes distintos en cada pasada.

### Cambiado

- **Tope de aceleración subido**: `fast` 1,15 → 1,35, `balanced` 1,12 → 1,30,
  `quality` 1,10 → 1,25. El valor anterior se había fijado sin medir la distribución real
  de excesos. Como `fit_audio` aplica `min(necesario, tope)`, un tope más alto **no toca
  los bloques que ya caben**: medido, subir de 1,12 a 1,30 bajó los bloques recortados de
  21 a 10 y la voz perdida de 85 s a 69 s, mientras la aceleración media realmente
  aplicada solo pasó de 1,09x a 1,19x. Coste de GPU: cero.

### Añadido

- Selección de tomas en el TTS (`tts_takes` por perfil). Chatterbox genera tokens de voz a
  una tasa fija de 25/s, así que la duración es un resultado del muestreo y varía entre un
  18 % y un 30 % de una toma a otra. El sintetizador genera hasta N tomas y acepta la
  primera que cabe en su ventana; si ninguna cabe, conserva la más corta.
- Escalera de `cfg_weight` por toma (`balanced`: 0,0 → 0,0 → 0,3). Las primeras tomas
  conservan el 0,0 que impide que una referencia inglesa arrastre su acento al español;
  solo se sube cuando el bloque va camino de perder la cola. El valor usado se registra en
  `blocks_voiced.json`.
- `ytdubber dub --tts-takes N` y `--max-speedup X` para probar sin editar perfiles.
- `ARQUITECTURA.md` (flujo completo con diagramas Mermaid) y `FUNCIONAL.md` (qué hace el
  sistema, reglas de calidad y límites conocidos).

### Mediciones

Mismo vídeo, siete ejecuciones completas:

| run | Configuración | recortados | voz perdida | ritmo |
|---|---|---|---|---|
| 1 | cap 1,12 · 1 toma · ref vieja | 58 (74 %) | 551 s (32 %) | 10,65 c/s |
| 2 | cap 1,12 · 1 toma · ref vieja | 24 (28 %) | 98 s (8 %) | 15,07 c/s |
| 3 | cap 1,12 · 3 tomas · ref vieja | 21 (27 %) | 85 s (7 %) | 14,68 c/s |
| 4 | cap 1,30 · 3 tomas · ref vieja | 10 (13 %) | 69 s (5 %) | 13,68 c/s |
| 5 | cap 1,30 · 1 toma · ref vieja | 48 (62 %) | 693 s (36 %) | 9,93 c/s |
| 6 | cap 1,30 · 1 toma · **ref nueva** | 11 (14 %) | 57 s (4 %) | 14,89 c/s |
| **7** | **cap 1,30 · 3 tomas · ref nueva** | **1 (1 %)** | **5 s (0 %)** | **15,32 c/s** |

Los runs 1 y 2 son la **misma configuración** y difieren un 32 % frente a un 8 %. Esa
aparente aleatoriedad llevó a dos conclusiones equivocadas antes de identificar la causa:
las ejecuciones caían en referencias de voz distintas. Los runs 5 y 6 son el experimento
que lo aísla —idénticos salvo el clip de referencia—, y los runs 6 y 7 muestran que, con
una referencia buena, las tomas extra bajan de ~90 a 11 y el `cfg_weight` original se
conserva en el 96 % de los bloques.

**Lección metodológica:** en este pipeline, comparar dos ejecuciones completas sin fijar la
referencia de voz no demuestra nada.

Otras mediciones de esta versión:

- `cfg_weight` es la única palanca de ritmo real de Chatterbox: 13,3 chars/s a 0,0 frente a
  15,3 a 0,3 y 16,4 a 0,5. `exaggeration` y `temperature` no afectan al ritmo.
  `repetition_penalty=1.0` degenera (dispersión del 156 %).
- Subir `cfg_weight` no degrada la inteligibilidad (WER 0,000 y p(español) 0,999 en 0,0,
  0,3 y 0,5), pero eso **no mide el acento**, que es la razón por la que el proyecto fijó
  0,0. De ahí que la escalera lo suba solo como último recurso.
- `large-v3` frente a `large-v3-turbo`: misma puntuación (9 signos, 0 comas en ambos, así
  que la falta de puntuación no viene de la destilación), pero turbo comete errores de
  transcripción que corrompen el sentido («censorship» → «sensor shape», «Qwen» →
  «queen») y detecta 3,7 veces menos pausas. 122 s frente a 28 s.

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
