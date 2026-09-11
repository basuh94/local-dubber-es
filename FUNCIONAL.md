# Funcional del sistema

Qué hace el sistema, con qué reglas y con qué límites. Para *cómo* está construido por
dentro, ver `ARQUITECTURA.md`.

---

## 1. Qué es

Un doblador automático de vídeo que se ejecuta **entero en tu máquina**. Coge un vídeo en
inglés, lo traduce al español de España y lo vuelve a locutar **con la voz del ponente
original**, encajando cada frase en su hueco temporal y conservando la música y los
efectos del vídeo.

Nada sale de tu equipo: no hay API de pago, ni subida a la nube, ni clave de ningún
servicio. Los tres modelos corren en tu RTX 3070.

**No es** un traductor de subtítulos (aunque los genera), ni un separador de pistas, ni un
sistema de doblaje de calidad de estudio.

---

## 2. Formas de usarlo

| Vía | Cómo | Para qué |
|---|---|---|
| **Ejecutable** | Doble clic en `YouTube Dubber.exe` | Lo normal. Arranca Ollama y el panel |
| **Panel web** | `ytdubber web` → `127.0.0.1:8765` | Igual, sin el .exe |
| **Línea de comandos** | `ytdubber dub "URL" --profile balanced` | Automatizar, scripts, lotes |
| **Diagnóstico** | `ytdubber doctor` | Comprobar que la instalación está sana |

La ventana del panel debe quedarse abierta: si la cierras, se cae el servidor y con él
cualquier doblaje en curso. `Ctrl+C` para pararlo limpiamente.

---

## 3. Entradas

**Origen**: una URL de YouTube o la ruta de un vídeo local.

**Idioma de origen**: `en` por defecto. Se puede dejar en automático, pero indicarlo es más
fiable.

**Perfil**: ver más abajo.

**Referencia de voz** (opcional): un WAV limpio de 5-10 s con **una sola persona hablando**.
Si no lo das, el sistema elige automáticamente un fragmento del propio vídeo: entre los que
el reconocimiento entendió bien, el de habla más rápida.

> **Si das tu propia referencia, elige un fragmento donde la persona hable a buen ritmo.**
> Chatterbox no solo copia el timbre, **copia la velocidad**. Una referencia con pausas
> hace que todo el doblaje salga lento y no quepa en su sitio. Medido: una referencia de
> 8,7 car/s produjo 693 s de voz recortada; una de 19,7 car/s, 57 s. Es la decisión que
> más afecta al resultado final.

**Nivel del audio original** (opcional, por defecto 0.12): cuánto se oye la pista original
por debajo de la voz doblada.

---

## 4. Perfiles

| | `fast` | `balanced` ⭐ | `quality` |
|---|---|---|---|
| Transcripción | `small` | `large-v3-turbo` | `large-v3` |
| Traducción | `qwen3:4b` | `qwen3:8b` | `qwen3:8b` |
| Voz | Chatterbox V3 | Chatterbox V3 | Chatterbox V3 |
| Tope de aceleración | 1,35x | 1,30x | 1,25x |
| Tomas de voz por bloque | 2 | 3 | 4 |
| Uso | Previsualizar | **Recomendado** | Máxima fidelidad |

**`balanced` es el recomendado** para una 3070 de 8 GB, y es el valor por defecto.

Sobre `quality`: usa `large-v3` sin destilar. Medido sobre una charla técnica, transcribe
**bastante mejor** que turbo —turbo confundía «censorship» con «sensor shape» y «Qwen» con
«queen»— a cambio de 122 s frente a 28 s. En un vídeo cuyo doblaje tarda 20 minutos, ese
minuto extra no se nota. Merece la pena en contenido con terminología técnica.

---

## 5. Qué produce

Al terminar, el panel archiva todo en `library/<fecha>_<título>/`:

| Fichero | Qué es |
|---|---|
| **`video_es.mp4`** | **El resultado.** Vídeo original + audio doblado |
| `dub_es.wav` | Solo la voz española, por si quieres remezclar |
| `subtitles_es.srt` | Subtítulos en español |
| `subtitles_source.srt` | Subtítulos en el idioma original |
| `transcript_es.txt` | Traducción en texto plano |
| `transcript_source.txt` | Transcripción original |
| `blocks_es.json` | **El fichero a editar** si quieres retocar una frase |
| `blocks_voiced.json` | Métricas de encaje temporal por bloque |
| `words.json` | Cada palabra con su instante exacto |
| `meta.json` | Perfil, duración, avisos, fecha |

Los intermedios (los WAV por bloque, el vídeo descargado, el audio de trabajo) se **borran
automáticamente**. En una prueba real eso liberó 322 MB de un solo doblaje.

---

## 6. Reglas de calidad

Estas son las garantías que el sistema cumple, y son deliberadas.

### Lo que NUNCA hace

| | Por qué importa |
|---|---|
| **No ralentiza** una frase corta para rellenar su hueco | Sonaría arrastrado y artificial. Se completa con silencio |
| **No acelera sin límite** una frase larga | Cada perfil tiene su tope, y se aplica lo mínimo necesario |
| **No corta en conectores** | Evita el *"...y" / "...entonces"* partido entre bloques |
| **No pierde texto en la traducción** | Reintentos puntuados, y respaldo al original si todo falla |
| **No cuela otros alfabetos** | Detecta cirílico y CJK y reintenta |
| **No elimina música ni efectos** | El original se atenúa bajo la voz, no se borra |

### Lo que hace cuando algo no cabe

1. Intenta que quepa **a velocidad natural**, aprovechando la pausa hasta la frase
   siguiente.
2. Si no, pide al traductor una versión **más breve** que quepa en el tiempo.
3. Si no, genera **varias tomas de voz** y se queda con la que encaje.
4. Si no, **acelera** lo justo, hasta el tope del perfil.
5. Si aun así no cabe, **recorta la cola y te avisa** con el número de bloque y los
   segundos que sobran.

Nunca recorta en silencio. Los bloques afectados aparecen en el panel y son editables en
`blocks_es.json`.

### Traducción

- Español **de España**: *ordenador* y no *computadora*, *selfie* y no *autofoto*.
- Glosario técnico fijo: *hinge*→bisagra, *spatial audio*→audio espacial,
  *reflections*→reflejos, *inner/outer display*→pantalla interior/exterior.
- Nombres propios, marcas y acrónimos se preservan.
- Al modelo se le da el bloque anterior y el siguiente como contexto, con orden explícita
  de traducir solo el actual.

---

## 7. Rendimiento real

Medido en tu equipo (RTX 3070 8 GB, Windows 11).

**Vídeo de 3 minutos, perfil `balanced`:**

| Etapa | Tiempo |
|---|---|
| Descarga | 3 s |
| Transcripción | 7 s |
| Segmentación | <1 s |
| Traducción | 42 s |
| Referencia de voz | 1 s |
| **Síntesis de voz** | **141 s** |
| Mezcla final | 1 s |
| **Total** | **~3,2 min** |

**La síntesis de voz es el 72 % del tiempo.** Todo lo demás es marginal. Un vídeo de 20
minutos tarda del orden de 25-30 minutos.

**VRAM**: pico de 7,3 GB de 8 GB, durante la traducción. Si tienes Chrome o Teams abiertos
consumiendo VRAM, Ollama puede volcar parte del modelo a CPU y la traducción se ralentiza.
Cerrarlos antes de doblar ayuda.

---

## 8. Límites conocidos

Conviene tenerlos claros antes de esperar un resultado perfecto.

**Es doblaje automático.** Un resultado de calidad de estudio sigue necesitando retoques
manuales. El sistema te deja los ficheros intermedios precisamente para eso.

**Los locutores rápidos son el caso difícil.** Chatterbox no admite control de duración: la
velocidad sale de la referencia de voz y del muestreo. Con una referencia bien elegida el
sistema encaja prácticamente todo —medido sobre una charla técnica a 194 palabras/minuto:
1 bloque recortado de 78, 5 segundos de voz perdida—, pero si la referencia es lenta o le
das tú una con pausas, el doblaje entero se alarga y se recorta.

**Sin puntuación en la transcripción, la segmentación empeora.** Algunos audios hacen que
Whisper devuelva texto continuo sin puntos ni comas. Entonces los bloques se cortan por
reloj en vez de por sentido. Medido en un caso real: 9 signos de puntuación en 3885
palabras, tanto con `large-v3-turbo` como con `large-v3`.

**Hay variabilidad entre ejecuciones.** Dos pasadas del mismo vídeo pueden segmentar
distinto y elegir referencias de voz distintas, y eso cambia el resultado de forma
apreciable. **Una sola ejecución no es concluyente** para juzgar la calidad del encaje
temporal; si quieres comparar configuraciones, fija la referencia con `--voice-ref`.

**No es separación de fuentes.** El audio original se atenúa bajo la voz doblada, pero si
el vídeo tiene el habla mezclada con música, seguirás oyendo la voz original de fondo.

**Un doblaje cada vez.** El pipeline usa directorios de trabajo compartidos.

**La transcripción manda.** Si el reconocimiento oye mal un nombre propio o un término
técnico, la traducción será fiel a lo que oyó mal. Revisa `blocks_es.json` en vídeos que
importen.

---

## 9. Diagnóstico

`ytdubber doctor` comprueba, en orden: Python 3.11, FFmpeg y ffprobe, la GPU NVIDIA,
PyTorch con CUDA, las DLL de CUDA en `vendor/cuda12/`, que importen faster-whisper y
Chatterbox, y que Ollama responda con el modelo del perfil descargado.

**Síntomas frecuentes**

| Síntoma | Causa |
|---|---|
| `cublas64_12.dll is not found` | `vendor/cuda12/` vacío. Relanzar `scripts/setup_windows.ps1` |
| `Ollama no reachable` | Ollama no arrancado, o el modelo sin descargar |
| El puerto 8765 está ocupado | Quedó un panel anterior vivo. El lanzador lo detecta y abre el navegador |
| Traducción lenta | VRAM ocupada por el escritorio; Ollama vuelca a CPU |
| Muchos avisos de recorte | Locutor rápido. Ver «Límites conocidos» |

Prueba real de los modelos sobre la GPU: `scripts\model_smoke_test.ps1`.

---

## 10. Consideración de uso

La clonación de voz solo debe usarse sobre contenido y voces sobre los que tengas derechos.
