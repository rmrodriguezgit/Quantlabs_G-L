# Quantlabs G&L — reglas del proyecto

Por instrucción del propietario, cada actualización debe:

- Incrementar SemVer en `frontend/package.json` y sincronizar `frontend/package-lock.json`.
- Actualizar README con la versión, cambios y validación relevantes.
- Ejecutar las pruebas apropiadas y el build del frontend cuando corresponda.
- Crear un commit después de verificar los cambios; no incluir credenciales, cuentas,
  bases, pesos, entornos virtuales, node_modules ni dist.

La simplificación vive en `refactor/simplify-pipeline`. No fusionar ni publicar
sobre `main` sin autorización explícita posterior. La app en ejecución y su cuenta
permanecen en el checkout original. Las pruebas de la rama usan datos aislados.
No reemplazar la liquidación oficial ni las cuotas verificadas por simulaciones
al fallar un feed. LAYA sigue siendo obligatorio en el perfil `gan_laya` y las
entradas paper siguen siendo de $1, tasas incluidas.

El propietario autorizó el perfil experimental `edge_laya` en esta rama. En él,
LAYA debe estar conectado y puede vetar (confianza <35%); las excepciones bloquean,
no autorizan entradas. Mantener cuenta y motor separados de main, $1 total y
resolución oficial. Q es diagnóstico hasta una validación futura específica.

El propietario autorizó la reingeniería cuantitativa v1.4 en esta rama. El perfil
`quant_laya` usa cuenta aislada, $1 total, controles de EV/RR/riesgo y salidas ATR
paper exclusivamente a bids públicos frescos con profundidad. Nunca inferir un
fill desde el spot BTC ni pagar de nuevo una salida anticipada al llegar la
resolución. LAYA continúa siendo obligatorio y Q diagnóstico. No prometer
rentabilidad ni certificar probabilidades de ruina con la fórmula incompleta
del prompt. Conservar la cuenta y perfil edge anterior sin mezclarlos.
