# MySECOP — Revisión UX, adaptación y estilo

Fecha: 17 de noviembre de 2026. Base de comparación: develop bfa5104. Cambios locales conservados en el proyecto; sin commits ni despliegues.

## Hallazgos y correcciones

- La navegación móvil mostraba todos los enlaces permanentemente y desplazaba el contenido. Se sustituyó por un menú modal nativo con cierre por Escape, confinamiento de foco del navegador, retorno al disparador y cierre al pasar a escritorio. Se conserva la barra lateral de escritorio y el acceso administrativo condicionado a la cuenta existente.
- Se incorporó un enlace para saltar al contenido y se identifica la página activa en la navegación.
- Los seis filtros SECOP se estrechaban desde 768 px. Ahora usan una columna en teléfono, dos en tablet y tres en pantallas amplias. Se añadieron nombres accesibles a los controles.
- Controles compartidos y cambio de tema con altura mínima de 44 px. Campos de 16 px en teléfono para evitar el zoom automático de Safari. Formularios de acceso y registro con menor relleno móvil, región principal, autocompletado y etiquetas para mostrar contraseña.
- Selector de fuentes en tres columnas móviles, cabecera pública adaptada y acciones del perfil que pueden cambiar de línea.
- Enlaces que contenían un botón se sustituyeron, donde la estructura era simple, por enlaces con apariencia de botón. Se mantiene una función compartida de estilos compatible con componentes de servidor y cliente.
- Mejor contraste del texto turquesa sobre fondos claros, títulos de beneficios y botón WhatsApp. Foco de teclado más visible y transiciones respetuosas con movimiento reducido.
- Se retiraron reglas generales que ocultaban el desbordamiento horizontal o centraban todos los enlaces móviles.
- «Dashboard» pasa a «Resumen», con encabezado y orientación. «Triage» pasa a «estado de seguimiento», «worker» se expresa como espera de actualización e «in-app» como «en MySECOP». Se explica cobertura como porcentaje de análisis actualizados, separado del grado de compatibilidad.
- Texto TVEC más sencillo, singular «1 cotización», mensaje de sugerencias sin promesa de ganar procesos y aviso de fuentes que contempla cotizaciones e históricos.
- Las consultas periódicas de presencia y cobertura usan el cliente de segundo plano existente; conservan autenticación y errores sin activar el bloqueo visual global durante lecturas pasivas.

## Verificación

- `npm run build`: correcto; sin avisos de compilación en el registro guardado.
- `tsc --noEmit`: correcto. `git diff --check`: correcto.
- Chrome real con Next compilado y API simulada: flujo TVEC en 320×760, 390×844, 768×1024, 820×1180, 1024×768, 1280×800, 1440×900, 1920×1080 y 844×390. Pruebas aprobadas: navegación móvil y Escape, recuperación del foco, liberación del desplazamiento, cabecera compacta, ausencia de desbordamiento horizontal, búsquedas, actualización, espera, errores, reintento, paginación e histórico existentes.
- 60 combinaciones públicas: landing, contacto, inicio de sesión, registro y restablecimiento; seis tamaños y temas claro/oscuro. Sin desbordamiento horizontal y sin infracciones detectadas por axe-core 4.10.3 en reglas WCAG 2 A/AA y 2.1 AA evaluadas. Se detectaron problemas de contraste en la primera pasada y se corrigieron antes de repetir la auditoría.
- Revisión visual de capturas móviles de acceso y TVEC. Evidencia en `backend/benchmarks/ux-responsive/`.
- No se enviaron consultas de contacto, mensajes WhatsApp ni ingestas reales. No se ejecutó la suite backend: no se modificaron servicios, modelos ni cálculos del backend. Las pruebas del navegador usan respuestas sintéticas y no sustituyen pruebas de integración del backend.

## Límites y pendientes

La revisión automatizada cubre páginas públicas y el recorrido TVEC descrito. No constituye certificación de accesibilidad, aprobación visual de cada pantalla privada ni prueba en dispositivos físicos. Faltan validación con Safari/iOS y Android reales, teclado virtual, lector de pantalla, zoom del navegador al 200 %, y recorridos completos con datos reales de perfil, ofertas, pliegos y administración. La versión Free y permisos administrativos requieren además validación específica; las pruebas privadas descritas usan una cuenta Pro ficticia.

Antes de una aprobación comercial conviene contrastar con la configuración real nombres de planes, cupos, duración de prueba, frecuencia de sincronización y afirmaciones como «cero oportunidades perdidas». No se cambiaron precios, cupos, licenciamiento ni promesas comerciales durante esta intervención. Los enlaces legales con destino `#` de la landing siguen pendientes de disponer de documentos y destinos reales. Los modales anteriores ajenos al menú no recibieron una auditoría completa de foco.

## Reproducción

Con dependencias frontend, Next compilado, Python con Playwright/httpx y Chrome disponibles, ejecutar desde la raíz del repositorio:

```sh
npm --prefix frontend run build
PLAYWRIGHT_CHROMIUM_EXECUTABLE="/ruta/a/Chrome" python backend/scripts/e2e_ux_responsive.py
AXE_CORE_PATH="/ruta/a/axe-core/axe.min.js" PLAYWRIGHT_CHROMIUM_EXECUTABLE="/ruta/a/Chrome" python backend/scripts/e2e_ux_public.py
```

`axe-core` se preparó en un directorio temporal, sin añadir dependencias al producto. Cada script inicia un servidor Next local aislado, intercepta la API y termina el proceso al finalizar. Los registros de shell incluyen el aviso del entorno RVM «operation not permitted: ps»; no se ocultó y no impidió compilación o pruebas.

## Publicación y reversión

Estado: listo para revisión local y posterior validación DEV; no publicado. No se realizaron commits, conexiones SSH al servidor ni cambios en STG/producción. Para publicar, usar el flujo GitHub Actions existente. Para revertir, restaurar únicamente los archivos enumerados contra la base bfa5104 o aplicar el parche inverso, conservando cambios previos del usuario. No hay migraciones ni datos que revertir.

## Archivos de implementación y pruebas

- `frontend/app/(private)/app/alertas/page.tsx`
- `frontend/app/(private)/app/ayuda/page.tsx`
- `frontend/app/(private)/app/layout.tsx`
- `frontend/app/(private)/app/page.tsx`
- `frontend/app/(private)/app/perfil/page.tsx`
- `frontend/app/globals.css`
- `frontend/app/iniciar-sesion/page.tsx`
- `frontend/app/page.tsx`
- `frontend/app/registro/page.tsx`
- `frontend/app/restablecer-contrasena/page.tsx`
- `frontend/components/contact-form.tsx`
- `frontend/components/match-progress.tsx`
- `frontend/components/secop-opportunities.tsx`
- `frontend/components/source-selector.tsx`
- `frontend/components/theme.tsx`
- `frontend/components/tvec-quotations.tsx`
- `frontend/components/tvec-refresh-button.tsx`
- `frontend/components/ui.tsx`
- `frontend/lib/button-styles.ts`
- `backend/scripts/e2e_ux_responsive.py`
- `backend/scripts/e2e_ux_public.py`
