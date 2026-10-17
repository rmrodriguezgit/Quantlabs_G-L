# Reglas simplificadas — v1.3.0-rc.1

Solo en `refactor/simplify-pipeline`. No hay merge a main ni cambio del motor 8000.
La rama ahora puede ejecutar un motor propio con `./start-candidate.sh` en 8002.
Antes de lanzarlo, detener cualquier preview que ocupe ese puerto.
Cuenta independiente: `backend/data/live-edge-laya.json`, inicialmente $1,000
paper; auditoría propia `backend/data/live-research.sqlite3`. No copia ni reinicia
la cuenta principal. Arranque habitual con dependencias y modelo MLX disponibles.

## Comparación con Quantlabs-LY-KY-Q

Se revisaron otra vez su motor y servidor: perfil balanced min_edge=0.04,
veto LAYA con corte 0.35, tres ticks de la misma dirección y 20–240s restantes.
La referencia tiene un Q neuronal entrenado en entorno de cuotas simulado y LAYA
opcional. No tenemos evidencia para trasladar esos pesos ni sus ganancias.

Nuestra adaptación usa:

| Condición | Perfil estricto anterior | Experimento edge_laya |
|---|---|---|
| Dirección | P(UP)>58% / <42% | Mayor edge neto admisible entre UP/DOWN |
| Edge | ROI esperado >5% | P(lado) − coste efectivo ≥0.04 por token |
| Indicadores | >70%, precio y momentum obligatorios | Contexto, sin veto técnico automático |
| LAYA | Aprobación >70% | Conectado y sin veto, confianza ≥35% |
| Q | Puede bloquear | Diagnóstico; no filtra ni se presenta como entrenado |
| Persistencia | Una lectura puede disparar | Tres lecturas válidas, misma dirección, ≥2s, huecos ≤5s |
| Ventana | Casi todo el ciclo | 60–280s desde apertura, inclusive |
| Importe | $1 incluidas tasas | $1 incluidas tasas |

El edge es una diferencia en unidades de pago por token, **no el porcentaje de
ROI ni cuatro dólares**. Coste efectivo = ask × (1 + rate × (1−ask)). Se mantiene
el mínimo 0.04 después de tasas. No se añaden odds sintéticas ni se presume
liquidez; sin datos vigentes, modelo sano o LAYA conectado, WAIT. El motor vuelve
a verificar precio, edge, confianza, confirmación, ciclo y libro antes del fill.
Una entrada por ciclo; fracciones bajo mínimo real solo paper, debidamente marcadas.

LAYA recibe un prompt de veto distinto, con indicadores como contexto. Su
confianza choice no es una probabilidad calibrada de ganar. El corte 35% es un
parámetro experimental inspirado en la referencia, no un umbral validado para BTC.
ATR/Fibonacci permanecen descriptivos. Q usa estados edge-laya-v1 y registra
recompensas sin decidir; no se fuerza una falsa comparación con Q_MIN del otro bot.

## Diagnóstico y reproducción histórica

En la muestra consultada de la política actual hubo 3,143 snapshots; el bloqueo
LAYA >70% apareció en 3,132. Son lecturas correlacionadas, no ensayos independientes.

El replay cronológico posterior abarcó 3,213 observaciones y 19 ciclos. Conservó
los precios, tasas, libro visible, primeras tres lecturas válidas y resultados
oficiales. No optimizó los parámetros para elegir un PnL favorable:

- Snapshots con todos los gates estrictos aprobados: 0.
- Entradas experimentales hipotéticas: 19 (4 UP / 15 DOWN).
- 17 resueltas, 2 pendientes: PnL neto −$1.8269; win rate 52.94%.

**Más entradas no implicaron más beneficio.** La prueba reutiliza como proxy las
confianzas MLX del prompt estricto archivado: no existía el nuevo prompt de veto.
No es una reproducción exacta de las nuevas inferencias, ni un holdout, ni una
promesa de frecuencia futura. No reconstruye latencia o profundidad posterior.
Los dos pendientes no se contabilizan como pérdidas ni se rellenan por Binance.

```sh
.venv/bin/python -m backend.replay_simple \
  --db /ruta/a/la/auditoria/original/live-research.sqlite3 \
  --out /ruta/a/replay.json
```

`backend/replay_simple.py` abre esa base en solo lectura. El resultado cambia si
entran observaciones nuevas. El experimento live necesita su propio periodo
prospectivo antes de comparar rentabilidad, drawdown y frecuencia por dirección.

## Presentación y auditoría

La vista 8002 muestra `edge_laya`, reglas activas, edge de UP/DOWN, veto por lado,
Q diagnóstico y la cuenta independiente. El histórico conserva la versión de
reglas, perfil, cuota, referencia BTC, cierre y ganador oficial. La investigación
inicia una cohorte nueva `v1.3.0-rc.1-edge-laya-v1-anchor30to15`.
Su shadow sigue anclado a 30–15s y **omite la confirmación de tres ticks**; no debe
confundirse con las entradas de la cuenta del nuevo motor.

Validación: pruebas de coste neto, compra DOWN sin mayoría GAN, veto obligatorio,
fallo de inferencia, reloj, confirmación, cambio de lado/ciclo, cuota obsoleta,
liquidez, tope $1, resolución y conservación del perfil estricto.

Suite final: 74 pruebas backend y 13 frontend aprobadas, build TypeScript/Vite correcto.
El perfil estricto anterior conserva además la prueba de 1,200 decisiones equivalentes.
