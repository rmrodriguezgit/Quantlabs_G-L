# Quantlabs_G-L

**Quantlabs G&L · LAYA · v1.1.2**

Sistema local de paper trading con precios BTC y asks Polymarket en tiempo real, GAN experimental, auditor LAYA MLX y política Q tabular. No contiene claves privadas ni código para enviar órdenes reales.

## Arranque

```sh
./start-live.sh
```

Abrir http://127.0.0.1:8000. `start-live.sh` instala dependencias, activa LIVE/PAPER, carga `aac6fef/laya-mlx`, compila React y arranca FastAPI. La primera carga descarga unos 850 MB de pesos en `backend/data/huggingface`. Requiere Python 3.11+ compatible con PyTorch/MLX, Node 22+, Internet y macOS Apple Silicon. PyTorch cae a CPU si MPS no está disponible. MLX oficial requiere Metal; esta sesión usa una compilación CPU de MLX cuando la GPU no es accesible. Si la carga falla, se muestra el error y se bloquean entradas, sin cambiar a baseline.

Para demo sintética: `./start.sh`. Ctrl+C detiene el supervisor y backend. Hay hasta cinco reinicios ante caída. `PORT=8001 ./start-live.sh` cambia el puerto. La aplicación escucha solo en loopback. No ejecutar múltiples workers sobre el mismo JSON de cuenta.

## Datos y simulación

- Descubrimiento del mercado exacto `btc-updown-5m-{epoch}` mediante Gamma. Se verifican slug, inicio y cierre, resultados Up/Down, estado y versión antes de operar. Adaptador actual para CTF v1; otra versión queda bloqueada.
- BTC Binance: 200 velas cerradas 5m y vela actual. Precio tomado del último agregado de operaciones, con timestamp comprobado. Polling aproximado de un segundo; si la red tarda, la frecuencia disminuye. Se rechazan datos y libros obsoletos.
- Asks de los tokens UP/DOWN desde CLOB `/books`, precio de compra y profundidad del mejor ask. No se usa el midpoint como fill ni se inventa la cuota complementaria.
- Ventana de entrada inclusiva: 30 a 15 segundos antes del cierre. Una entrada por ciclo. Umbrales estrictos P(UP)>58% o <42%, concordancia técnica>70%, aprobación MLX>70%, EV neto>0.05 y política Q permite la acción.
- Half-Kelly sobre precio efectivo con tasas; coste total máximo 5% del efectivo disponible. Fill limitado a tokens visibles en mejor ask y mínimo del libro. Se simula la tasa `tokens × rate × p × (1-p)` para mercados cuya `feeSchedule.exponent=1`; una estructura desconocida bloquea operaciones. El simulador no reproduce prioridad, latencia de fill ni reservas de terceros.
- Liquidación únicamente con `closed=true` y un único token `winner=true` del mercado oficial CLOB. Una posición puede quedar abierta después del cierre hasta publicar el resultado; no se liquida por precio Binance ni por el reloj. Cuenta, posiciones, Q-table y logs sobreviven al reinicio.
- Dashboard: señal, filtros PASS/WAIT, log de señales y ejecuciones, reloj, curva de equidad, métricas, calculadora bruta, historial, enlace al mercado y pausa de nuevas entradas. Las posiciones pendientes siguen resolviéndose al pausar.

## Modelos y límites

La GAN genera 1,000 retornos. Se entrena solo con velas cerradas y aplica una aproximación de escalado temporal de sus shocks al horizonte restante y desplazamiento spot actual. La probabilidad resultante es experimental y no está calibrada fuera de muestra. No hay garantía de frecuencia de entradas ni de rentabilidad.

El mercado consultado usa **Chainlink TWAP de 60 segundos**. El modelo usa **spot Binance**, por lo que existe una diferencia de fuente y objetivo. Se indica en el dashboard. Para investigación se permiten fills de paper sujetos a filtros; los resultados no validan la idoneidad del modelo para operar dinero real.

LAYA usa `laya_mlx.load` y `predict` con pregunta `choice` y resultados LAYA_APPROVED / LAYA_REJECTED. Se auditan RSI, EMA9/21 y delta del volumen taker de Binance (volumen base comprador menos vendedor); la concordancia técnica y aprobación MLX son métricas distintas. LAYA es un auditor de consistencia, no un predictor financiero entrenado para BTC.

Q-learning empieza sin entrenamiento previo: estado discretizado, recompensa terminal PnL/coste y actualización tabular. Una acción con Q negativo puede pasar a WAIT. No se fuerza exploración para generar operaciones. Los pesos GAN se reentrenan tras reinicio; no se guardan como checkpoint.

Equity se calcula como efectivo + posiciones a coste; no es mark-to-market. Profit factor se muestra como — cuando aún no hay pérdidas. Drawdown se calcula sobre liquidaciones. Empates demo resuelven DOWN; la cuenta live usa exclusivamente los resultados oficiales y reglas del mercado. No hay WS Binance, yfinance, entrenamiento RLCD ni validación walk-forward.

## Desarrollo

```sh
.venv/bin/python -m unittest discover -s tests -v
cd frontend && npm run build
```

REST: GET `/api/state`, GET `/api/health`, POST `/api/pause`; WebSocket `/ws` transmite snapshot cada segundo. Logs: `backend/data/live-events.jsonl`. Cuenta: `backend/data/live.json`, separada de `demo.json`.

Fuentes: [LAYA MLX](https://github.com/rmrodriguezgit/laya-mlx), [libro Polymarket](https://docs.polymarket.com/market-data/prices-order-books), [tasas](https://docs.polymarket.com/trading/fees).

## Simulación exploratoria de $1

`./start-simulation.sh` activa una cuenta separada en `backend/data/live-exploratory.json` y usa cuotas reales. Cada fill debita **exactamente $1 total, tasas incluidas**; nunca sube ese importe para alcanzar el mínimo de tokens. Permite fracciones exclusivamente paper por debajo de ese mínimo, marcadas como BAJO MÍNIMO REAL; no serían órdenes ejecutables en la plataforma. Selecciona el menor ask disponible, máximo una operación por ciclo, y espera si no hay liquidez/saldo o si faltan datos/modelos. No se exige la ventana 30–15s, EV positivo ni aprobación LAYA: se muestran los valores y el rechazo real, sin llamar aprobada a la señal. Su finalidad es ejercitar el simulador; no representa el rendimiento de la estrategia estricta. La cuenta estricta y sus reglas se conservan. No se inventan operaciones históricas ni resultados. Un resultado sin vendedores se muestra como — y no puede recibir fills.


## Perfil actual: GAN + LAYA, $1 por entrada

`start-simulation.sh` ahora activa `LAYA_EXECUTION=gan_laya`. La dirección procede exclusivamente de la GAN (>58% UP, <42% DOWN). La cuenta existente conserva sus operaciones exploratorias etiquetadas como tales; las nuevas filas GAN + LAYA guardan P(UP), aprobación MLX y concordancia técnica por separado. Se requieren modelos conectados, concordancia técnica >70%, aprobación MLX >70%, EV neto >0.05 y permiso de Q-policy. No se elige el token por ser más barato. El importe sigue siendo exactamente $1 total con tasas, una entrada por ciclo, permitiendo fracciones paper bajo mínimo real. En este perfil se evalúa durante el ciclo hasta 5 segundos antes del cierre, sin exigir la ventana estricta 30–15 segundos. La liquidación sigue dependiendo del resultado oficial.


## Corrección 1.0.1: probabilidad estancada y motivos de WAIT

Se reprodujo un colapso de dispersión con la GAN original de 80 pasos: dos de tres semillas generaron P(UP)=0 aun sin movimiento observado. El generador ahora aprende una transformación residual del ruido y añade penalizaciones de media, desviación y cuantiles al objetivo adversarial. Cada entrenamiento audita 4,096 escenarios; sesgo absoluto normalizado >=0.35 o desviación relativa fuera de (0.5,1.8) bloquea entradas. Estos controles detectan degradación de distribución y no demuestran precisión financiera. La probabilidad de inferencia sigue usando 1,000 escenarios y puede ser 0% o 100% cuando todos los escenarios coinciden legítimamente.

El panel muestra aprobación MLX y concordancia técnica como métricas distintas, todos los filtros pendientes, última hora de actualización, edad del último trade BTC y diagnóstico de la GAN. El reloj avanza en el cliente aunque el servidor no responda, y una conexión WS abierta con datos obsoletos deja de aparecer como LIVE. Los umbrales y el importe de $1 no se han reducido.


## Laboratorio prospectivo v1.1.0

El motor registra cada snapshot, incluidos WAIT, rechazos y errores de datos, en `backend/data/live-research.sqlite3` (SQLite WAL). Guarda probabilidades, salud GAN, auditoría MLX, RSI/EMA/delta, referencia spot, timestamp del dato, asks y tamaño visible, tasas, decisión y bloqueos. No reconstruye señales antiguas ni mezcla el historial exploratorio con la nueva cohorte. La cuenta y los filtros de las órdenes de $1 no cambian.

Para comparar GAN sola, GAN + indicadores y GAN + indicadores + LAYA, se fija **la misma primera señal válida entre 30 y 15 segundos antes del cierre**. Sin datos frescos, una cotización disponible o GAN saludable, la vela no entra en la muestra. La falta de ask de la dirección propuesta impide el fill shadow, pero no elimina la señal del cálculo Brier. La señal no se sustituye por otra posterior más favorable. Cada variante usa la misma señal y condición; se omite la política Q de esta comparación para aislar el aporte de indicadores y LAYA. Elegibilidad: umbral GAN >58%/<42%, EV neto >0.05 y, según la variante, concordancia técnica >70% y aprobación MLX >70%. Los fills shadow son fracciones paper de $1 con tasas y liquidez visible; se cuenta cuántos quedan debajo del mínimo real. No son órdenes ejecutadas.

Un resolvedor independiente consulta el resultado oficial incluso en mercados sin operaciones de la cuenta y durante fallos del feed BTC. Sin un ganador oficial, la muestra sigue pendiente. La evaluación muestra PnL neto, profit factor, drawdown, win rate, frecuencia de entrada y un estrés hipotético +$0.01/token (con su propio número de fills). Este estrés no reconstruye el libro posterior ni demuestra fills reales. Brier compara P(UP) con el resultado oficial sobre una observación por vela; la referencia P=50% obtiene 0.25. El gráfico de fiabilidad es descriptivo: no se ha ajustado un calibrador ni realizado una prueba walk-forward con datos históricos.

Las cifras empiezan vacías; se necesita acumular resultados nuevos para valorar el modelo. El recuento de bloqueos usa snapshots correlacionados, no casos independientes. La versión/cohorte evita mezclar protocolos distintos. La auditoría persiste entre reinicios y no se borra al reiniciar una cuenta paper. Los resultados siguen sujetos a la diferencia entre spot Binance y TWAP Chainlink.

Endpoints: GET `/api/research`; GET `/api/research/signals.csv?limit=10000` (máximo 100,000 filas por descarga). El panel exporta las últimas 10,000 filas; el histórico completo queda en SQLite. Ni la base ni los CSV se publican en GitHub.


La v1.1.1 muestra en el histórico la columna **BTC REF. (BINANCE)**: valor `reference` guardado en la posición, correspondiente a la apertura del ciclo Binance. No es el precio spot actual ni la referencia TWAP oficial de Chainlink. Si una posición no contiene esa referencia, se muestra —.


La v1.1.2 añade cierre BTC histórico, hora de cierre y diferencia frente a la referencia Binance en cada operación. Un resolvedor independiente recupera la vela exacta por inicio y fin, verifica que esté cerrada y completa también operaciones antiguas. Mientras no cierre la ventana se muestra En curso; si el dato aún no llega, Pendiente de dato. El precio spot de cierre no determina ni modifica el resultado binario; se conserva el ganador oficial UP/DOWN de Polymarket, cuya fuente es Chainlink TWAP. Los datos nuevos persisten con la cuenta.

### Experimento condicional (offline)

`backend/training/` implementa un ensemble de tres WGAN-GP con contexto causal de
12 variables, objetivo normalizado por volatilidad y horizonte restante, y
calibración logística en un segmento separado. Descarga velas cerradas de un minuto
con `download_minutes` en `data.py`. Reproducir sobre el caché local:

```bash
.venv/bin/python -m backend.training.run --data backend/data/training/btc-1m-1789603200-1792195200.json --out ../analisis-gan --steps 800
```

El checkpoint permanece ignorado en `backend/data/training/`. El resumen
`backend/training/latest_evaluation.json` aparece en el laboratorio del dashboard.
La partición temporal usa 60/20/20 con purga de 20 minutos. No utiliza las dos
operaciones del 17 de octubre para entrenar. Resultado: el candidato no supera
la referencia de difusión y **no se promueve**. No hay backtest de beneficio:
faltan libros de cuotas y liquidaciones oficiales históricas. No modificar umbrales
para acertar retrospectivamente dos pérdidas. Una nueva selección o ajuste requiere
otra muestra futura; este holdout ya ha sido observado.
