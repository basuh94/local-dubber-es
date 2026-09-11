# Arquitectura y flujo

Cómo funciona el sistema por dentro. Para *qué* hace y *por qué*, ver `FUNCIONAL.md`.

---

## 1. Visión general

Tres modelos de IA que **nunca se ejecutan a la vez**. La RTX 3070 tiene 8 GB y el
escritorio de Windows ya ocupa ~2 GB, así que el pipeline los encadena y descarga cada uno
antes de cargar el siguiente.

```mermaid
flowchart LR
    IN["Vídeo de YouTube<br/>o fichero local"] --> ASR
    ASR["faster-whisper<br/>~1,5 GB VRAM"] --> LLM
    LLM["Qwen3 vía Ollama<br/>~5,2 GB VRAM"] --> TTS
    TTS["Chatterbox V3<br/>~3,5 GB VRAM"] --> MIX
    MIX["FFmpeg<br/>sin GPU"] --> OUT["video_es.mp4"]

    style ASR fill:#2d4f3c,color:#fff
    style LLM fill:#4a3b5c,color:#fff
    style TTS fill:#5c3b2e,color:#fff
    style MIX fill:#3b4a5c,color:#fff
```

Pico real medido: **7,3 GB de 8 GB**, durante la traducción. Si los tres modelos se
cargaran a la vez no cabrían.

---

## 2. Las 7 etapas

```mermaid
flowchart TD
    S["ytdubber dub URL --profile balanced"] --> E1

    E1["<b>1. Descarga y extracción</b><br/>downloader.py"]
    E1 --> A1["work/source.mp4"]
    E1 --> A2["work/audio_16k.wav<br/>mono 16 kHz"]

    A2 --> E2["<b>2. Transcripción</b><br/>transcriber.py · faster-whisper CUDA<br/>VAD + timestamps por palabra"]
    E2 --> A3["words.json<br/>transcript_source.txt<br/>subtitles_source.srt"]

    A3 --> E3["<b>3. Segmentación</b><br/>segmenter.py<br/>corte por pausas y puntuación"]
    E3 --> A4["blocks_source.json"]

    A4 --> E4["<b>4. Traducción</b><br/>translator.py · Ollama HTTP<br/>bloque a bloque con contexto"]
    E4 --> A5["blocks_es.json<br/>subtitles_es.srt<br/>transcript_es.txt"]
    E4 --> U["unload_ollama<br/>libera VRAM"]

    A4 --> E5["<b>5. Referencia de voz</b><br/>segmenter + tts.py"]
    A1 --> E5
    E5 --> A6["work/voice_ref_auto.wav<br/>5-10 s del ponente"]

    A5 --> E6["<b>6. Síntesis y ajuste</b><br/>tts.py · Chatterbox V3 CUDA"]
    A6 --> E6
    U --> E6
    E6 --> A7["dub_blocks/*.wav<br/>blocks_voiced.json"]
    A7 --> E6b["assemble_dub<br/>cada bloque en su instante"]
    E6b --> A8["dub_es.wav"]

    A8 --> E7["<b>7. Mezcla final</b><br/>mixer.py · FFmpeg"]
    A1 --> E7
    E7 --> A9["<b>video_es.mp4</b>"]

    style E1 fill:#333,color:#fff
    style E2 fill:#2d4f3c,color:#fff
    style E3 fill:#333,color:#fff
    style E4 fill:#4a3b5c,color:#fff
    style E5 fill:#333,color:#fff
    style E6 fill:#5c3b2e,color:#fff
    style E7 fill:#3b4a5c,color:#fff
    style A9 fill:#1a5c2e,color:#fff
```

---

## 3. Segmentación: dónde cortar

Es la etapa más delicada. Un corte malo arrastra errores a la traducción y al doblaje.

```mermaid
flowchart TD
    W["palabra siguiente"] --> C{"¿termina en . ! ?<br/>y dura ≥ 1 s?"}
    C -->|sí| CUT["CORTAR"]
    C -->|no| C2{"¿dura ≥ 2 s, hay pausa ≥ 0,55 s<br/>y NO acaba en conector?"}
    C2 -->|sí| CUT
    C2 -->|no| C3{"¿dura ≥ 7,5 s<br/>y hay pausa o coma?"}
    C3 -->|sí| CUT
    C3 -->|no| C4{"¿dura ≥ 13 s<br/>y hay pausa mínima?"}
    C4 -->|sí| CUT
    C4 -->|no| C5{"¿dura ≥ 16 s?<br/><b>tope duro</b>"}
    C5 -->|sí| FORCE["CORTAR A LA FUERZA<br/>en el hueco más ancho visto"]
    C5 -->|no| W

    CUT --> M{"¿el bloque dura < 1,25 s?"}
    FORCE --> M
    M -->|sí| MERGE["fusionar con el anterior"]
    M -->|no| OK["bloque listo"]

    style FORCE fill:#7a3b2e,color:#fff
    style CUT fill:#2d4f3c,color:#fff
```

**El tope duro existe por una razón concreta.** Todas las reglas preferentes exigen
puntuación *o* una pausa. Hay transcripciones que no tienen ninguna de las dos —habla
continua sin puntuar— y entonces el guard de conectores puede vetar *todos* los cortes. Sin
tope, un bloque creció hasta 246 segundos y 4087 caracteres, desbordó el contexto del TTS y
mató el proceso con un *device-side assert* de CUDA.

**Conectores**: no se corta justo después de `and, or, but, so, when, that, because, the,
a, to, of, in, on...` salvo que la frase termine en punto. Evita el clásico *"...y"* ⏎
*"...entonces"*.

---

## 4. Encaje temporal: el corazón del doblaje

El español ocupa ~11 % más que el inglés y Chatterbox habla a ~111 palabras/minuto. Casi
siempre sobra audio. Estas son las reglas, por orden:

```mermaid
flowchart TD
    G["voz sintetizada"] --> Q1{"¿es más corta que<br/>su hueco original?"}
    Q1 -->|sí| PAD["<b>Rellenar con silencio</b><br/>velocidad natural intacta<br/>NUNCA se ralentiza"]
    Q1 -->|no| Q2{"¿cabe usando además<br/>la pausa hasta el<br/>bloque siguiente?"}
    Q2 -->|sí| NAT["<b>Velocidad natural</b><br/>invade la pausa"]
    Q2 -->|no| Q3{"¿cabe acelerando<br/>hasta el tope del perfil?"}
    Q3 -->|sí| SPD["<b>Acelerar</b> lo justo<br/>min necesario, tope"]
    Q3 -->|no| TRIM["<b>Recortar la cola</b><br/>+ AVISO en pantalla"]

    style PAD fill:#2d4f3c,color:#fff
    style NAT fill:#2d4f3c,color:#fff
    style SPD fill:#5c4a2e,color:#fff
    style TRIM fill:#7a3b2e,color:#fff
```

Tres garantías que el código cumple siempre:

1. **Nunca se ralentiza** una frase corta para rellenar su hueco. Se completa con silencio.
2. **La aceleración tiene tope** por perfil, y se aplica `min(necesario, tope)` — los
   bloques que ya caben no se tocan.
3. **Si hay que recortar, se avisa** con el número de bloque y los segundos que sobran.

### Ventana disponible

```mermaid
flowchart LR
    subgraph Línea de tiempo
    B1["bloque N<br/>inicio → fin"] --- P["pausa"] --- B2["bloque N+1"]
    end
    B1 -.-> V["<b>ventana</b> = inicio(N+1) − inicio(N) − 0,12 s<br/>último bloque: duración + 1,5 s"]
```

El margen de 0,12 s evita que una frase pise el arranque de la siguiente.

---

## 5. Traducción

```mermaid
sequenceDiagram
    participant P as pipeline
    participant T as translator.py
    participant O as Ollama :11434

    P->>T: bloques + modelo + max_speedup
    loop por cada bloque
        T->>T: ventana → presupuesto de caracteres<br/>12,5 car/s × ventana × tope
        T->>O: prompt con PREVIOUS / CURRENT / NEXT<br/>+ glosario + límite de longitud
        O-->>T: JSON {"translation": "..."}
        T->>T: puntuar candidato
        alt vacío, cirílico/CJK, muy corto o muy largo
            T->>O: reintentar (hasta 3)
        end
        T->>T: quedarse con el MEJOR, no con el último
    end
    T->>O: keep_alive=0 (descargar de VRAM)
    T-->>P: bloques traducidos
```

- **Contexto sin contaminación**: al modelo se le dan el bloque anterior y el siguiente
  como contexto, con instrucción explícita de traducir *solo* el actual.
- **Presupuesto de longitud**: se le pide una traducción que quepa en el tiempo disponible,
  con un suelo del 60 % de la longitud original para que no omita contenido.
- **Puntuación de candidatos**: la completitud satura al llegar a la longitud del original
  —más largo no es más completo— y se penaliza el exceso. Alfabeto extraño resta 2 puntos.
- **Respaldo**: si los 3 intentos fallan, se conserva el texto original y se avisa.

---

## 5.b Elección de la referencia de voz

**La decisión más influyente de todo el pipeline**, y la menos obvia.

Chatterbox no solo clona el timbre: **clona el ritmo** del clip que se le da como
referencia, de forma casi proporcional. Si la referencia es un pasaje donde el ponente va
despacio, *todas* las frases del doblaje saldrán lentas, no cabrán en su hueco y se
recortarán.

```mermaid
flowchart TD
    B["bloques del vídeo"] --> F1{"duración entre<br/>5 y 10,5 s"}
    F1 --> F2{"confianza ≥ 90 %<br/>de la mejor"}
    F2 --> F3["elegir el de<br/><b>habla más rápida</b>"]
    F3 --> R["work/voice_ref_auto.wav"]
    F1 -.->|ninguno| FB["los 5 más cercanos a 7 s"]
    FB --> F2

    style F3 fill:#1a5c2e,color:#fff
```

Medido sobre el mismo vídeo, aislando esta única variable:

| referencia | ritmo del doblaje | voz recortada |
|---|---|---|
| 8,74 car/s | 9,93 car/s | 693 s |
| 19,74 car/s | 14,89 car/s | 57 s |

**92 % menos de voz perdida, a coste cero.** El filtro de confianza sigue mandando primero:
un fragmento rápido que el reconocimiento apenas entendió es una mala muestra de voz.

Si das tu propia referencia con `--voice-ref`, esta selección no se aplica. Elige un clip
donde la persona hable a buen ritmo, no uno donde haga pausas.

---

## 6. Síntesis de voz

Chatterbox genera **tokens de voz a 25/segundo**. La duración es literalmente
`nº_tokens / 25`: no hay parámetro de velocidad, la duración es un resultado del muestreo.
Como muestrea con `temperature=0.8`, cada toma de la misma frase sale distinta —medido,
entre un 18 % y un 30 % de dispersión.

```mermaid
flowchart TD
    TXT["texto español del bloque"] --> SPL{"¿supera 1000 tokens?<br/>(límite real: 2048)"}
    SPL -->|sí| CHUNK["trocear por frases → comas → palabras"]
    SPL -->|no| GEN
    CHUNK --> GEN["generar toma"]
    GEN --> FIT{"¿cabe en la ventana<br/>con el tope de aceleración?"}
    FIT -->|sí| ACC["aceptar"]
    FIT -->|no| MORE{"¿quedan tomas?"}
    MORE -->|sí| ESC["siguiente toma<br/>cfg_weight según escalera"]
    ESC --> GEN
    MORE -->|no| SHORT["quedarse con la más corta"]

    style ACC fill:#2d4f3c,color:#fff
    style SHORT fill:#5c4a2e,color:#fff
```

**Escalera de `cfg_weight`** (`balanced`: `0.0 → 0.0 → 0.3`): las primeras tomas conservan
el `0.0` que impide que la referencia inglesa arrastre su acento al español. Solo cuando un
bloque va camino de que le corten el final se sube, porque un poco de acento es mejor que
perder palabras. El valor realmente usado queda anotado en `blocks_voiced.json`.

El troceo es una red de seguridad: con la segmentación correcta no llega a dispararse
nunca, pero evita que un caso patológico mate el proceso.

---

## 7. Mezcla final

```mermaid
flowchart LR
    V["source.mp4<br/>vídeo + audio original"] --> F
    D["dub_es.wav<br/>voz española"] --> F
    F["FFmpeg filter_complex"] --> O["video_es.mp4"]

    F -.- N1["vídeo: copiado sin recodificar"]
    F -.- N2["original al 12 % mientras habla el doblaje,<br/>al 100 % el resto"]
    F -.- N3["audio: AAC 192k · +faststart"]
```

**La música y los efectos se conservan.** No hay separación de fuentes: el audio original
se atenúa (*ducking*) solo durante las ventanas de voz doblada y vuelve a volumen completo
en cuanto callan. El vídeo se copia tal cual, sin pérdida ni tiempo de recodificación.

---

## 8. Panel de control

El panel **no reimplementa nada**: ejecuta la misma CLI como subproceso y lee su salida.

```mermaid
sequenceDiagram
    actor U as Usuario
    participant W as Navegador
    participant S as FastAPI :8765
    participant C as subproceso<br/>ytdubber dub
    participant L as library.py

    U->>W: pega URL, pulsa Doblar
    W->>S: POST /api/job
    S->>S: yt-dlp: título + miniatura
    S->>S: limpiar work/ y output/
    S->>C: lanzar CLI
    loop cada segundo
        W->>S: GET /api/job
        S-->>W: etapa, bloque N/M, avisos, log
    end
    C-->>S: fin (código 0)
    S->>L: archive()
    L->>L: mover a library/<fecha>_<título>/
    L->>L: borrar intermedios
    L-->>S: metadatos
    S-->>W: done + entrada de biblioteca
```

**Un trabajo cada vez.** El pipeline usa `work/` y `output/` compartidos; dos en paralelo
se pisarían. Un segundo intento devuelve `409` con la explicación.

### Estados

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> preparing: POST /api/job
    preparing --> running: subproceso lanzado
    running --> archiving: código 0
    archiving --> done
    running --> error: código ≠ 0
    preparing --> cancelling: POST cancel
    running --> cancelling: POST cancel
    cancelling --> cancelled: limpia, no archiva
    done --> preparing: nuevo trabajo
    error --> preparing
    cancelled --> preparing
```

---

## 9. Mapa de módulos

```mermaid
flowchart TD
    CLI["cli.py<br/>doctor · dub · web"] --> PIPE["pipeline.py<br/>orquestación"]
    CLI --> PRE["preflight.py<br/>diagnóstico"]
    CLI --> WEB["webapp.py<br/>FastAPI"]

    WEB --> HTML["web/index.html"]
    WEB --> LIB["library.py<br/>archivar · listar · borrar"]
    WEB -.->|subproceso| CLI

    PIPE --> DL["downloader.py"]
    PIPE --> TR["transcriber.py"]
    PIPE --> SEG["segmenter.py"]
    PIPE --> TRA["translator.py"]
    PIPE --> TTS["tts.py"]
    PIPE --> MIX["mixer.py"]
    PIPE --> MOD["models.py<br/>perfiles"]

    SEG --> UT["utils.py<br/>rutas · ventanas · SRT · CUDA"]
    TRA --> UT
    TTS --> UT
    MIX --> UT
    LIB --> UT

    EXE["YouTube Dubber.exe<br/>launcher.py"] -.->|arranca| WEB

    style CLI fill:#333,color:#fff
    style PIPE fill:#333,color:#fff
    style UT fill:#444,color:#fff
```

| Módulo | Responsabilidad |
|---|---|
| `cli.py` | Punto de entrada. Subcomandos y argumentos |
| `pipeline.py` | Orquesta las 7 etapas. No contiene lógica de negocio |
| `downloader.py` | yt-dlp + extracción de audio. Purga descargas previas |
| `transcriber.py` | faster-whisper con VAD y timestamps por palabra |
| `segmenter.py` | Corte en bloques y elección de la referencia de voz |
| `translator.py` | Ollama, presupuesto de longitud, reintentos puntuados |
| `tts.py` | Chatterbox, selección de tomas, encaje temporal, ensamblado |
| `mixer.py` | Ducking del original y multiplexado final |
| `models.py` | Perfiles `fast` / `balanced` / `quality` |
| `utils.py` | Rutas, geometría de ventanas, SRT, DLL de CUDA |
| `preflight.py` | `ytdubber doctor` |
| `webapp.py` | API del panel y runner de trabajos |
| `library.py` | Biblioteca y limpieza de residuos |

---

## 10. Dependencias externas

```mermaid
flowchart LR
    subgraph Sistema
    FF["FFmpeg / ffprobe"]
    OL["Ollama :11434"]
    NV["Driver NVIDIA + CUDA"]
    end
    subgraph venv
    TO["PyTorch 2.6.0+cu126"]
    FW["faster-whisper + CTranslate2"]
    CB["chatterbox-tts"]
    YT["yt-dlp"]
    FA["FastAPI + uvicorn"]
    end
    subgraph vendor
    CU["cuda12/*.dll<br/>cuBLAS + cuDNN 9"]
    end

    FW --> CU
    FW --> NV
    TO --> NV
```

**Sobre `vendor/cuda12/`**: CTranslate2 necesita `cublas64_12.dll` y cuDNN 9 en Windows.
El proyecto los lleva en local y los registra con `os.add_dll_directory()` antes de
importar. Así se evita tocar `System32`. Es la causa del clásico
`cublas64_12.dll is not found` si esa carpeta está vacía.
