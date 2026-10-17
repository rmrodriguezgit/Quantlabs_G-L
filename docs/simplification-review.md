# Revisión de simplificación — v1.2.3-rc.1

Rama `refactor/simplify-pipeline`, basada en v1.2.2. No fusionada ni desplegada
sobre la app live. Se revisó Quantlabs-LY-KY-Q v0.1.0 el 17 de octubre de 2026:
README, motor MLX, servidor y frontend. El árbol consultado fue
`37d9d20a6ea3af1e60ca5361ae578b0dcbd9745d`.

## Qué aporta la referencia

Su frontend separa App, tipos, formato, hook de conexión y componentes de reloj,
probabilidades, libro, sizing e histórico. Su objeto Decision reúne los resultados
de la evaluación. Son patrones útiles para reducir la complejidad del coordinador.

Fuentes: [App](https://github.com/rmrodriguezgit/Quantlabs-LY-KY-Q/blob/main/frontend/src/App.tsx),
[conexión](https://github.com/rmrodriguezgit/Quantlabs-LY-KY-Q/blob/main/frontend/src/useLaya.ts),
[motor](https://github.com/rmrodriguezgit/Quantlabs-LY-KY-Q/blob/main/backend/laya_mlx_engine.py).

## Diferencias que desaconsejan reemplazar el motor directamente

| Área | Referencia revisada | Decisión para esta rama |
|---|---|---|
| Cuotas no disponibles | `PolyFeed.get` devuelve None y `Runtime.tick` genera odds simuladas | Conservar bloqueo de entradas y asks reales verificados |
| Resolución | `_resolve` compara precio local con strike al cambiar ventana | Conservar resolución oficial CLOB, aunque llegue después |
| LAYA | Gate opcional; una excepción de inferencia deja veto=False | Conservar auditoría independiente UP/DOWN y bloqueo sin aprobación |
| Capital | Kelly por perfil y comisión manual | Conservar $1 total y tasas/letras del libro en el perfil principal |
| Predicción | GAN condicional MLX con contexto y checkpoints | No cambiar modelo sin nueva comparación temporal y oficial |

Fuentes: [servidor](https://github.com/rmrodriguezgit/Quantlabs-LY-KY-Q/blob/main/backend/server.py),
[decisión y gate](https://github.com/rmrodriguezgit/Quantlabs-LY-KY-Q/blob/main/backend/laya_mlx_engine.py).
La revisión es estática; no se ejecutó ni se evaluó financieramente el otro bot.
No hay evidencia para afirmar que sea más rentable o rápido.

## Cambios realizados

- `main.tsx` pasa de 16,461 bytes con dashboard/conexión/tipos a un arranque React
  de 200 bytes. `App.tsx` queda en unos 9 KB y compone componentes independientes.
- Se separan contratos, formato, gráfico, conexión, pipeline e histórico.
- Q calcula una sola vez el lado propuesto y reutiliza los costes/EV ya calculados
  de UP y DOWN. Se conserva el comportamiento del resumen WAIT en entradas válidas.
- Se mantienen API, interfaz, historial, fuentes, tasas, GAN, dos auditorías LAYA,
  ATR/Fibonacci shadow, evidencia, cuenta y reglas de $1.
- Las instrucciones persistentes de versionado, README y commits quedan en AGENTS.

Esto simplifica responsabilidades; no reduce necesariamente el número total de
líneas. Los fixtures de regresión añaden código solo de test. El bundle pasó de
262.02 KB (gzip 81.50 KB) a 262.30 KB (gzip 81.63 KB): no hay mejora de tamaño.
No se afirma una mejora de latencia o de PnL por reorganizar el código.

## Verificación

- 61 pruebas backend aprobadas, incluida igualdad de 1,200 decisiones contra Q
  v1.2.2, con UP/DOWN/WAIT, límites de probabilidad, tasas, cuotas ausentes,
  distintos scores y actualizaciones de Q tras recompensas.
- 8 pruebas del mercado binario aprobadas.
- 5 pruebas de HTML idéntico contra el pipeline/histórico anterior, en tres perfiles,
  filtros, referencias/cierres, pausa, datos obsoletos y modelo desconectado.
- TypeScript/Vite compila correctamente.
- El checkout principal sigue en `main`, limpio y sin cambiar la instalación live.
  Las pruebas Python se ejecutaron con el intérprete ya instalado, pero importando
  el backend de la rama y usando sus archivos de datos aislados.

El siguiente paso antes de fusionar es una prueba de integración prolongada en un
puerto y cuenta separados, incluyendo reconexión y varias transiciones de vela.
Las pruebas actuales justifican revisar el refactor, no dar por probada su operación
live continua ni una mejora financiera. No se realizó el merge.
