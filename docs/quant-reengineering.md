# v1.4.0-rc.1 · Reingeniería cuantitativa experimental

Branch `refactor/simplify-pipeline`, sin merge a main. Solo paper trading.

## Diagnóstico y decisiones

La GAN predice spot Binance y no el TWAP Chainlink que liquida el contrato. No hay calibración prospectiva suficiente para tratar sus probabilidades como verdaderas. Cambiar filtros no crea alpha. Q no está validado para este perfil y sigue siendo diagnóstico. El replay del perfil anterior aumentó entradas, pero perdió dinero. Las nuevas reglas buscan disciplina verificable y no una promesa de rentabilidad.

El principal riesgo operativo era valorar EV sin imponer un payoff mínimo, carecer de presupuestos de pérdida/exposición y confundir indicadores BTC con órdenes de un contrato binario. El riesgo máximo de una compra sigue siendo el dólar completo. También había dos consultas MLX secuenciales con prompts grandes; en la primera medición live cuantitativa, LAYA tomó ~1745ms y el loop ~2311ms. El nuevo adaptador agrupa dos preguntas direccionales independientes en una llamada, con evidencia compacta, sin reutilizar la aprobación del otro lado. La telemetría muestra la latencia medida, sin atribuir a esta máquina los benchmarks de un M3 Max.

La ingestión REST pública continúa; no se declara migrada a WebSocket. Timeout de red 8s, timestamps/identidad por feed y revalidación de quotes antes del fill. Una demora bloquea entradas; no genera precios de respaldo. Salidas observadas se procesan antes de GAN/MLX. Ingestión e inferencia siguen dentro de un loop; no se presenta como una arquitectura de baja latencia certificada ni como lista para operar dinero real.

## Matemática aplicada al instrumento

Para ask `a`, deslizamiento reservado `s=0.005` USD/token y tasa publicada `f`:

- Fill paper conservador `q = a+s`; rechazar si q≥1.
- Coste por token `c = q + f*q*(1-q)`; tokens de $1: `1/c`.
- Pérdida máxima L=$1; ganancia terminal R=`1/c−1` dólares.
- `EV = p*R − (1−p)*L = p/c−1` por $1.
- `R/R = R/L = 1/c−1`; exige ≥2. Esto implica c≤1/3: rechazará contratos caros aun con P alta. Es más restrictivo que v1.3, por requisito del nuevo prompt.
- Edge neto `p−c≥0.04`. Se evalúan UP y DOWN separadamente, se aplican todos los filtros y se elige el mayor edge admisible.
- Half-Kelly `0.5*(p−c)/(1−c)`, acotado a un presupuesto de 2% del capital. No es un tamaño óptimo demostrado con P no calibrada.

El dimensionamiento spot `riesgo/(distancia stop*valor punto)` se aplica a instrumentos lineales. Aquí no se usa una distancia BTC para subestimar el riesgo del token: la pérdida máxima es el desembolso completo. Por la instrucción vigente del propietario se mantiene **$1 total**; el presupuesto dinámico no aumenta la orden. Fracción de presupuesto `clip(1% / max(1, ATR/spot/0.1%), 0.5%, 1%)`. Si ATR o Half-Kelly no permiten $1, se espera. No se impone un mínimo de riesgo de 0.5% que obligue a subir el dólar.

## Controles obligatorios y gestión

`quant_laya` exige todos los controles edge anteriores: datos y quote elegido ≤5s, identidad de ventana, GAN saludable, LAYA real ≥35% sin error, misma dirección en tres lecturas durante ≥2s, ventana 60–280s y una entrada por ciclo. No se fuerza DOWN al rechazar UP. El porcentaje LAYA es un veto de consistencia, no una probabilidad financiera.

Además impone R/R terminal ≥2, EV>0, ATR cerrado válido, presupuesto ATR y Kelly, exposición máxima total 2%, pérdida realizada del día UTC más riesgo abierto y nueva operación ≤2%, drawdown realizado histórico más riesgo abierto y nueva operación <5%. Las posiciones abiertas se presupuestan a pérdida total; no se valoran como si los stops garantizaran salida. Los timestamps de resolución/salida se persisten para calcular el día correcto. Pausar entradas no desactiva salidas ni liquidación oficial.

ATR(14) usa Wilder y OHLC cerrados. Se congela en cada entrada. El BTC de entrada es distinto de la referencia de apertura de la ventana y ambos se conservan:

- UP: stop en entrada BTC −2 ATR; TP en entrada +4 ATR.
- DOWN: stop en entrada +2 ATR; TP en entrada −4 ATR.
- Trailing: tras avanzar 2 ATR, salida al retroceder 2 ATR desde el mejor spot observado.
- No se asume haber visto el máximo intravela entre muestras. Al dispararse una salida queda persistida; si falta bid fresco, condición/slug correctos o tamaño para todos los tokens, sigue ABIERTA. Reintenta antes del vencimiento. Fill de venta = bid−0.005; descuenta tasa de salida.
- Salida `EXITED` / VENDIDA PAPER conserva BTC, bid, momento, motivo, tasa y PnL. El resultado oficial posterior se guarda para auditoría sin volver a pagar. Sin venta al vencimiento, espera resultado oficial; nunca se liquida por spot Binance.

EV/RR de entrada son escenarios terminales de mantener el contrato; no afirman describir la estrategia con salidas anticipadas. El rendimiento gestionado requiere datos prospectivos nuevos.

## Riesgo de ruina: corrección del prompt

`((1−p)/(1+b))**N` no puede certificar ruina: no contiene capital ni stake y disminuye con N incluso al sumar exposición. No se utiliza como control. Se implementa una DP exacta de primer paso a horizonte **100 operaciones**, con stake fijo $1, capital disponible, payoff binario constante, probabilidad iid constante y barrera "no poder financiar el siguiente $1". Exige probabilidad modelada <0.0001 (0.01%). Antes se resta de forma conservadora todo el riesgo de posiciones abiertas utilizando cash.

Con $1000 y 100 operaciones de $1, perderlas todas no causa esa ruina; devuelve 0 por construcción. No es riesgo de drawdown, de plataforma, de pérdida a largo plazo ni garantía probabilística del modelo. La incertidumbre GAN, dependencia de operaciones y cambios de cuotas quedan fuera. Los controles de exposición y drawdown son independientes de esa cifra.

## Indicadores y LAYA / MLX

SMA50/SMA200 y su cruce necesitan 201 velas cerradas, MACD EMA12−EMA26 con señal EMA9 y Bollinger SMA20±2 desviaciones poblacionales. RSI, EMA9/21, delta y momentum se conservan. Los primeros indicadores usan cierres completos; el contexto direccional actual de RSI/EMA incorpora el precio disponible, claramente separado. Fibonacci sigue descriptivo; ATR se incorpora al presupuesto y gestión. Ninguno se convierte en un voto obligatorio adicional sin evidencia.

El repositorio [laya-mlx](https://github.com/rmrodriguezgit/laya-mlx) documenta decisiones tipadas `choice`, `score`, `noul`, inferencia MLX local y batching de preguntas. Se utiliza `predict` con dos preguntas choice UP/DOWN. Su confianza no está calibrada para trading. Este entorno ya tenía runtime y checkpoint; no se descargaron pesos en Git. No se afirma que el port incluya entrenamiento RLCD ni que el equipo esté usando GPU por tener MLX. No se activa compilación sin medir beneficio y estabilidad.

## Fuentes externas verificadas y limitaciones

Consultadas el 17-10-2026:

- [Polymarket: tasas](https://docs.polymarket.com/trading/fees): fórmula por tokens `C*f*p*(1-p)`. Se usa la tasa efectiva del mercado y solo el esquema v1/exponente1 que reconoce el adaptador; versiones desconocidas bloquean. Tasas modeladas continuas conservadoras; no replica redondeo de protocolo a cinco decimales ni órdenes reales.
- [Polymarket: bids y asks](https://docs.polymarket.com/market-data/prices-order-books): compra al ask y venta al bid; no se usa midpoint para simular venta.
- [Laya MLX README](https://github.com/rmrodriguezgit/laya-mlx): API, batching y límites del checkpoint. Los benchmarks publicados no son mediciones de este sistema.
- [Control de drawdown, Barmish y Hsieh](https://arxiv.org/abs/1710.01503): motivación para separar drawdown de ruina. No se atribuye al paper una garantía para este bot binario.

Los cuatro enlaces X del prompt no entregaron contenido verificable (403/cache miss): [ruonchain1](https://x.com/ruonchain1/status/2106033120294416850), [dan1ro0](https://x.com/dan1ro0/status/2085766554407317704), [rohonchain](https://x.com/rohonchain/status/2101311813908652069), [silvanrec](https://x.com/silvanrec/status/2111069723907559831). No se extrajeron estrategias ni alpha inventado de esos enlaces. No se añadió un feed on-chain con señales ficticias.

## Replay y métricas

`python -m backend.replay_quant --db RUTA_SQLITE --out reporte.json` abre SQLite solo lectura. Política congelada, split por ciclos completos 80/20, sin búsqueda de parámetros. Solo se liquidan posiciones para el presupuesto cuando `resolved_at` ya era conocido; resultados futuros únicamente puntúan al final. Reciclar cohortes observadas no hace al tramo final una validación prospectiva independiente.

Snapshot de prueba: 4128 observaciones, 25 ciclos. Primer tramo: 10 entradas posibles, 8 resueltas, +$0.9912, win rate25%, Sharpe0.0580, Sortino0.1431, MDD0.2992%, PF1.1652. Tramo final: 3 entradas posibles, 2 resueltas, −$2, win rate0%, Sharpe indefinido (sin dispersión), Sortino−1, MDD0.2%, PF0. Tres posiciones pendientes entre ambos tramos. Estrés adicional de +1¢ por token con las mismas entradas: +$0.5744 / −$2 respectivamente. No se promovió un modelo por esos resultados.

Faltan bids completos: todas esas cifras describen mantener hasta resolución, **no** el rendimiento de stops/trailing/TP. Confianzas MLX archivadas son proxy, no inferencia retrospectiva del nuevo prompt. Excluye snapshots sin ATR/frescura/liquidez; comisiones según mercado y deslizamiento reservado de entrada 0.5¢/token. El estrés de 1¢ adicional es análisis de sensibilidad, no reconstrucción de slippage histórico real.

Métricas live: Sharpe por trade = media de PnL/stake dividida por desviación muestral; Sortino = media dividida por raíz de la media de retornos negativos cuadrados, objetivo0. Sin anualización de trades irregulares, mínimo2 y denominador>0. Win rate usa PnL positivo, incluyendo ventas anticipadas. PF y MDD de la cuenta persisten; curva al coste para abiertas, no mark-to-market.

## Arranque y validación

```sh
./start-candidate.sh  # quant_laya por defecto, http://127.0.0.1:8002/
# Perfil anterior conservado:
LAYA_EXECUTION=edge_laya ./start-candidate.sh
```

Cuenta nueva aislada `backend/data/live-quant-laya.json`, inicio $1000 paper. Cuenta edge previa conservada en `live-edge-laya.json`; no se reseteó ni mezcló. Para continuar una cuenta, iniciar su perfil. La auditoría SQLite usa cohorte nueva `v1.4.0-rc.1-quant-risk-v1`. `main`/8000 no se modifica.

Validación: 90 pruebas backend, 16 frontend (5 paridad, 8 mercado y 3 UI cuantitativa), TypeScript y build. Casos de fee/slippage/EV/RR, ruina con capital y primer paso, límites de capital, chequeo independiente de fill, stops UP/DOWN, trailing, bid obsoleto/equivocado/sin liquidez, latch persistente, pausa, vencimiento, no doble pago tras resolución, contexto cerrado y aprobaciones MLX independientes. El servidor y WebSocket se verifican con feeds reales; siguen siendo experimentales.

## Verificación prospectiva al reanudar

Snapshot live del 17-10-2026, alrededor de las 15:04 America/Mexico_City: 24 entradas paper de $1 conservadas al reiniciar, 23 resueltas y 1 abierta. PnL realizado $-11.7809, win rate 13.04%, profit factor 0.4110, MDD realizado 1.4967%. No se borraron pérdidas ni se ajustaron umbrales para ocultarlas. Este resultado es negativo y no permite declarar rentabilidad. Los stops ATR no sustituyen la necesidad de calibrar la predicción para el contrato oficial.

Última muestra de telemetría: LAYA 691ms, ingesta 563ms, loop 1257ms. Es una muestra puntual, no un benchmark P50/P95 ni un SLA de 1s. Backend en 8002, datos/modelos conectados, sin error de feed en esa muestra.
