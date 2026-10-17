# Quantlabs_G-L

**Quantlabs G&L · LAYA · v1.0.1**

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
