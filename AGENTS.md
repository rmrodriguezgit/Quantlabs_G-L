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
