# Quantlabs G&L · LAYA

**Versión actual: v1.2.2 — pipeline UP/DOWN y contexto ATR/Fibonacci**

Aplicación local de **paper trading** para BTC Up/Down de 5 minutos en Polymarket.
Combina datos públicos de Binance, asks reales de Polymarket, una GAN experimental,
auditorías LAYA MLX y una política Q tabular. El perfil principal simula entradas de
**$1 total, tasas incluidas**. No envía órdenes reales ni necesita una wallet.

## Inicio rápido

Requisitos: Python 3.11+ compatible con las dependencias, Node.js 22+, npm e Internet.
La ruta MLX habitual requiere macOS con Apple Silicon y Metal. PyTorch usa CPU si
MPS no está disponible; esto no resuelve por sí solo una instalación MLX sin Metal.
La compilación CPU de MLX utilizada durante el desarrollo es una instalación
especial y no se instala automáticamente con estos scripts.

```sh
git clone https://github.com/rmrodriguezgit/Quantlabs_G-L.git
cd Quantlabs_G-L
./start-simulation.sh
```

Abrir **http://127.0.0.1:8000/**. El script activa `LAYA_MODE=live` y
`LAYA_EXECUTION=gan_laya`, prepara `.venv`, instala dependencias, compila React y
arranca FastAPI. Carga `aac6fef/laya-mlx`; la primera ejecución descarga unos
850 MB de pesos a `backend/data/huggingface`. Si los modelos o los datos no están
listos, muestra el motivo y bloquea entradas; no sustituye LAYA por una aprobación ficticia.

Ctrl+C detiene el supervisor y el backend. El supervisor limita los reintentos
tras fallos; no instala un servicio de inicio al encender el ordenador.
`PORT=8001 ./start-simulation.sh` cambia el puerto. Escucha solo en loopback.
No ejecutar múltiples instancias sobre el mismo archivo de cuenta.

### Perfiles disponibles

| Inicio | Perfil | Importe | Momento de entrada |
|---|---|---|---|
| `./start-simulation.sh` | **GAN + LAYA, principal** | $1 total | Ciclo activo, con más de 5 s restantes |
| `./start-live.sh` | Estrategia estricta, por defecto sin `LAYA_EXECUTION` definido | Half-Kelly, máximo 5% | Entre 30 y 15 s antes del cierre, inclusive |
| `LAYA_EXECUTION=exploratory ./start-live.sh` | Exploratorio, selecciona el menor ask | $1 total | Ciclo activo, con más de 5 s restantes |
| `./start.sh` | Demo, por defecto sin variables LIVE heredadas | Half-Kelly | Datos y cuotas sintéticos |

El perfil exploratorio ejercita el simulador sin exigir GAN/EV/LAYA favorables;
no representa una estrategia validada. El perfil principal exige todos sus filtros.
Ambos perfiles de $1 comparten el archivo histórico `live-exploratory.json`, pero
cada operación conserva su etiqueta. No se reclasifican operaciones antiguas.

## Novedades de la v1.2.2

El pipeline muestra P(UP), P(DOWN) y las dos aprobaciones independientes de LAYA.
El feed Binance conserva máximos/mínimos OHLC para calcular ATR(14) de Wilder
sobre velas cerradas de 5m. ATR mide volatilidad, no dirección ni un intervalo
probabilístico del precio futuro.

Fibonacci usa los extremos de las últimas 50 velas cerradas, ordenados por índice,
con niveles 0%, 23.6%, 38.2%, 50% (convencional), 61.8%, 78.6% y 100%. Muestra
el siguiente nivel por encima para UP y por debajo para DOWN, con distancia en
ATR. Si los extremos están en la misma vela o no hay rango, no inventa un tramo.
Los anclajes pueden cambiar cuando cierra otra vela; no se usan pivotes futuros.
Sin máximos/mínimos válidos, el contexto queda no disponible; no se aproxima ATR
con apertura y cierre.

Ambos indicadores están en **SHADOW descriptivo**: se guardan en los snapshots de
auditoría, sin votos en el score técnico ni cambios en los prompts LAYA, GAN, Q,
umbrales o entradas de $1. Hacen falta nuevas pruebas prospectivas antes de
promoverlos a filtros. Suite: 60 pruebas backend y 8 del panel de mercado.

## Novedades de la v1.2.1

El panel de mercado binario muestra la ventana BTC 5m activa con fecha, horario,
zona local y contador, pregunta/enlace al mercado correcto, apertura Binance,
precio actual y diferencia. UP/DOWN muestran probabilidades GAN complementarias
y asks por token en campos separados. La referencia oficial Chainlink no está
disponible en este feed: no se presenta la apertura Binance como si lo fuera.

El panel oculta datos obsoletos o del ciclo anterior durante una reconexión o cambio
de ventana; las cuotas se comprueban por token. Una GAN no preparada/degradada no
aparece como una estimación válida de 50%. La calculadora incluye tasas, EV y
avisos de profundidad y mínimo real. Elegir lado o cambiar su importe no envía
órdenes ni modifica el tamaño fijo de $1 del bot.

Comprobar las 8 pruebas del panel: `npm --prefix frontend run test:market`.

## Novedades de la v1.2.0

- Políticas UP/DOWN independientes y versionadas en `backend/directional.py`.
- Dos inferencias LAYA por snapshot: cada lado recibe evidencia y reglas propias.
- Confirmación obligatoria del precio actual y del momentum para evitar aprobar
  una dirección apoyada solamente por indicadores rezagados.
- Panel con los controles, probabilidades, EV y aprobación MLX de ambos lados.
- Evidencia direccional persistida en las nuevas operaciones.
- Nuevo espacio de estados Q para no reutilizar valores aprendidos con otra semántica del score.
- Nueva cohorte prospectiva, con entradas, PnL y acierto desglosados por UP/DOWN.
  Las cohortes anteriores permanecen en SQLite; el bankroll y el histórico se conservan.

## Reglas del perfil principal: GAN + LAYA, $1

### Validación por dirección

| Evidencia técnica | ENTRY UP | ENTRY DOWN |
|---|---|---|
| RSI | >50 | <50 |
| Tendencia de medias | EMA9 > EMA21 | EMA9 < EMA21 |
| Volumen firmado | Positivo | Negativo |
| Precio BTC actual | Sobre EMA9 y EMA21 | Bajo EMA9 y EMA21 |
| Momentum: precio actual frente al último cierre | Positivo | Negativo |

Se exige concordancia **>70%: al menos 4 de 5 controles**, y los controles de
**precio y momentum son obligatorios**. Una igualdad no apoya ninguna dirección.
Las dos políticas tienen umbrales numéricos inicialmente iguales; separarlas no
implica inventar diferencias sin validación futura. Rechazar UP no autoriza DOWN.

Para entrar también deben cumplirse:

1. P(UP)>58% para UP, o P(UP)<42% para DOWN; P(DOWN)=1−P(UP).
2. Aprobación LAYA del lado propuesto >70%, modelo conectado y confirmación técnica.
3. EV neto >0.05 con el ask y las tasas del lado propuesto; política Q permite la acción.
4. GAN entrenada con controles de media y dispersión válidos; datos y cuotas frescos.
5. Motor activo, ciclo vigente con más de 5 s restantes y máximo una entrada por ciclo.
6. Saldo y tamaño visible suficientes para el fill simulado.

Cada entrada debita **exactamente $1, tasas incluidas**. No se aumenta el importe
para alcanzar el mínimo real del mercado. Se permiten fracciones exclusivamente
paper por debajo del mínimo, identificadas como **BAJO MÍNIMO REAL**. Esos fills
no serían órdenes ejecutables en la plataforma.

## Datos, ejecución simulada y liquidación

- **BTC:** 200 velas cerradas de 5m y vela actual de Binance; precio del último
  agregado de operaciones con timestamp comprobado. Polling aproximado de un
  segundo, sujeto a latencia. No usa Binance WS ni yfinance.
- **Mercado:** Gamma descubre `btc-updown-5m-{epoch}`. Se verifican identidad,
  fechas, estado, resultados y versión. El adaptador actual admite CTF v1;
  versiones o estructuras de tasas desconocidas bloquean entradas.
- **Cuotas:** CLOB `/books`, asks y tamaño del mejor nivel de cada token.
  No se usa el midpoint como fill ni se inventa la cuota complementaria.
  Un lado sin vendedores se muestra como — y no puede recibir fills.
- **Tasas:** para la estructura compatible, `tokens × rate × ask × (1−ask)`.
  Se limita el fill a la liquidez visible. No se simulan prioridad, reservas de
  terceros ni evolución del libro durante la latencia.
- **Resolución:** exclusivamente mercado oficial CLOB con `closed=true` y un
  único token `winner=true`. Una posición puede seguir abierta tras el cierre
  hasta publicarse el resultado. Pausar entradas no detiene su resolución.

El histórico muestra apertura BTC de referencia, cierre de la misma vela Binance,
hora, diferencia de precio y ganador oficial UP/DOWN. El resolvedor recupera la
vela exacta y verifica que esté cerrada. Mientras tanto muestra **En curso** o
**Pendiente de dato**. Binance no decide el resultado oficial: el mercado consultado
usa **Chainlink TWAP de 60 s**, una fuente y objetivo distintos del spot del modelo.

La curva de equidad usa efectivo + posiciones abiertas a coste, sin mark-to-market.
Drawdown se calcula sobre liquidaciones; profit factor aparece como — si aún no
hay pérdidas. Los empates demo resuelven DOWN; live utiliza el resultado oficial.

## Modelos y alcance

### GAN activa

Genera **1,000 escenarios** de retornos y aproxima el horizonte restante a partir
de velas cerradas y desplazamiento spot actual. El generador residual se entrena
con objetivo adversarial y penalizaciones de media, dispersión y cuantiles.
El control de salud usa 4,096 muestras: sesgo normalizado absoluto <0.35 y
desviación relativa dentro de (0.5,1.8). Bloquea degradación o colapso, pero no
acredita precisión predictiva. La probabilidad puede alcanzar 0% o 100% y sigue
siendo experimental, sin calibración financiera fuera de muestra.

### LAYA MLX y Q-learning

LAYA usa `laya_mlx.load` y `predict` con una pregunta `choice` por dirección,
`LAYA_APPROVED`/`LAYA_REJECTED`. Un fallo de inferencia no reutiliza la aprobación
del lado contrario. Su confianza es una medida de auditoría textual de consistencia,
**no una probabilidad de ganar dinero**.

La política Q tabular empieza sin entrenamiento financiero previo; actualiza con
recompensa terminal PnL/coste. Puede mantener WAIT aunque otros filtros pasen.
No fuerza exploración para generar operaciones. La GAN activa se vuelve a entrenar
tras reinicio; el checkpoint offline descrito abajo no la sustituye.

### Experimento condicional offline

`backend/training/` implementa tres WGAN-GP condicionales, 12 variables causales,
objetivo normalizado por volatilidad/horizonte y calibración logística separada.
El experimento usó 43,200 velas de un minuto de 30 días, anteriores al día de las
dos pérdidas estudiadas; partición temporal 60/20/20 con purgas de 20 minutos.

| Modelo, segmento de prueba | Brier ↓ | Acierto direccional |
|---|---:|---:|
| GAN condicional calibrada | 0.1977 | 68.1% |
| Referencia estadística de difusión | **0.1859** | **69.2%** |
| Arquitectura GAN anterior reentrenada | 0.1888 | 68.9% |

Prueba sobre 1,726 velas, con cinco momentos observados por vela; no son casos
independientes ni win rate de una estrategia. Las etiquetas son Binance, sin libros
de cuotas ni liquidaciones oficiales históricas. **El candidato no superó la
referencia y no se promovió a ejecución.** Estos resultados no evalúan la nueva
política direccional v1.2.0 ni prueban beneficio. Cualquier ajuste posterior necesita
otro segmento futuro, porque este holdout ya fue observado.

Reproducir sobre el caché local, no incluido en GitHub:

```sh
.venv/bin/python -m backend.training.run \
  --data backend/data/training/btc-1m-1789603200-1792195200.json \
  --out ../analisis-gan --steps 800
```

`download_minutes` en `backend/training/data.py` permite obtener el caché.
Los checkpoints quedan en `backend/data/training/` y el resumen reproducible en
`backend/training/latest_evaluation.json`. No hay validación walk-forward completa
ni evidencia de rentabilidad; no se garantiza frecuencia de entrada ni ganancias.

## Laboratorio prospectivo

Cohorte actual: **`v1.2.0-directional-v1-anchor30to15-ev005-slippage001`**.

SQLite registra snapshots incluidos WAIT, rechazos y errores: probabilidades,
salud GAN, las dos auditorías, controles técnicos, precio de referencia, timestamps,
cuotas, profundidad, tasas, decisión y bloqueos. No reconstruye señales antiguas.

La comparación shadow fija **la misma primera señal válida entre 30 y 15 s antes
del cierre** para GAN sola, GAN + indicadores y GAN + indicadores + LAYA.
La señal queda congelada; no se reemplaza por otra posterior más favorable.
La falta de ask del lado propuesto impide el fill, pero no elimina la señal del Brier.
Se omite Q para aislar las diferencias entre variantes. Indicadores y LAYA usan
la confirmación direccional; las operaciones shadow no modifican la cuenta.

Un resolvedor obtiene resultados oficiales incluso sin entradas paper. El panel
muestra Brier frente a la referencia 0.25, fiabilidad descriptiva, PnL neto, win rate,
profit factor, drawdown, frecuencia y desglose UP/DOWN. El estrés +$0.01/token es
hipotético y tiene su propio recuento de fills. Los bloqueos cuentan snapshots
correlacionados. Estas métricas ancladas a 30–15 s **no equivalen al rendimiento de
todas las entradas** del perfil principal, que puede evaluar durante el resto del ciclo.

## Persistencia, API y desarrollo

| Archivo local, excluido de GitHub | Contenido |
|---|---|
| `backend/data/live-exploratory.json` | Cuenta principal de $1, posiciones y Q-table |
| `backend/data/live.json` | Cuenta de estrategia estricta |
| `backend/data/demo.json` | Cuenta demo |
| `backend/data/live-exploratory-events.jsonl` | Logs del perfil principal |
| `backend/data/live-research.sqlite3` | Auditoría y cohortes prospectivas |
| `backend/data/huggingface/` | Caché del modelo LAYA |

Cuenta, evidencia, posiciones y Q-table persisten entre reinicios. La auditoría
se conserva independientemente de un reinicio de cuenta paper. No se publican
cuentas, bases, pesos ni entornos virtuales.

| Endpoint | Uso |
|---|---|
| `GET /api/state` | Snapshot del motor |
| `GET /api/health` | Salud y estado de modelos |
| `POST /api/pause` | Alternar pausa de nuevas entradas |
| `GET /api/research` | Evaluación prospectiva y resumen offline disponible |
| `GET /api/research/signals.csv?limit=10000` | Exportar auditoría de la cohorte actual |
| `WS /ws` | Snapshot cada segundo |

CSV: máximo 100,000 filas por descarga; el panel solicita 10,000. El histórico
completo permanece en SQLite local.

```sh
.venv/bin/python -m unittest discover -s tests -v
npm --prefix frontend run build
```

Validación de la v1.2.0: **47 pruebas aprobadas y build TypeScript/Vite correcto**.

Referencias del proyecto: [LAYA MLX](https://github.com/rmrodriguezgit/laya-mlx),
[Polymarket](https://docs.polymarket.com/),
[WGAN-GP](https://arxiv.org/abs/1704.00028).

### Prueba bayesiana en sombra (experimental)

`backend/bayesian.py` permite reproducir un calibrador Beta-Binomial por cohorte,
lado, banda GAN, confirmación técnica y aprobación LAYA. Lee SQLite en modo
solo lectura y usa únicamente resoluciones oficiales conocidas antes de cada
predicción. Conserva P(UP)+P(DOWN)=1; nunca multiplica confianza LAYA por GAN ni
permite que Bayes anule su rechazo. No está conectado a las órdenes ni al dashboard.

```sh
.venv/bin/python -m backend.bayesian --db backend/data/live-research.sqlite3 --out ../analisis-bayesiano
```

Prueba inicial: 9 velas antiguas y 1 de v1.2.0, analizadas por separado. Brier
original/bayesiano: 0.07573/0.20808 y 0.000144/0.25, respectivamente. La variante
no mejoró y no se promovió. Ninguna señal de esas muestras cumplía todos los
filtros LAYA; no hay evidencia de mejora del PnL. Se necesitan resultados futuros
y más señales aprobadas antes de ajustar probabilidades operativas. Suite tras
este experimento: 54 pruebas aprobadas.
