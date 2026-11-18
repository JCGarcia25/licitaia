# MySECOP — Revisión UX, responsive y SEO

Fecha: 18 de noviembre de 2026. Estado: cambios implementados y validados en local; sin commits ni despliegues.
Base de comparación: producción `b04b45d`. Se conservó el trabajo previo del workspace. El build final se ejecutó en una copia aislada y se verificó que los archivos modificados coinciden con el código original.

## Hallazgos y correcciones

- El canónico `/` se heredaba en páginas diferentes. Se retiró del layout raíz y se definieron títulos, descripciones y canónicos propios para inicio y Contacto; títulos absolutos con una sola mención de marca.
- DEV/STG heredaban instrucciones de indexación. La política usa el dominio configurado al construir la aplicación mediante SITE_URL o API_URL, que el flujo de despliegue existente ya proporciona. Solo `mysecop.co` en modo producción habilita indexación pública.
- `robots.txt` permite leer las instrucciones noindex de las páginas HTML; reserva el bloqueo de rastreo para API. No se usa robots.txt como mecanismo de autenticación ni como sustituto de noindex.
- Las páginas de cuenta y privadas, los enlaces de verificación y los documentos legales pendientes reciben noindex; las cabeceras X-Robots-Tag refuerzan esa política en las respuestas servidas por Next. En DEV/STG todas las respuestas de Next reciben noindex. La autorización del backend no cambió.
- El sitemap contiene exclusivamente inicio y Contacto; se excluyen formularios de cuenta, pantallas privadas y páginas legales sin contenido definitivo. Se eliminaron fechas lastModified generadas artificialmente en cada ejecución.
- Se añadió una imagen social PNG 1200×630 generada con Next/OG y referencias explícitas en Open Graph/Twitter. La comprobación HTTP detectó que la herencia de metadatos no conservaba la imagen en todas las páginas; se corrigió antes de cerrar la validación.
- Se actualizó la información estructurada de la organización con razón social, teléfono y correo facilitados por el propietario. Se añadió preconexión a fonts.gstatic.com.
- Navegación pública disponible también en móvil/tableta; enlace para saltar al contenido, landmark main y nombres de navegación distinguibles.
- Botones de planes con alineación inferior consistente y espacio para etiquetas largas. Se reemplazaron enlaces con botones anidados por enlaces con aspecto de botón en landing y oportunidades.
- Preparador de ofertas: una columna hasta 1279 px para evitar paneles demasiado estrechos; acciones y exportaciones en rejillas, textos de estado comprensibles, nombres legibles de borradores y campos etiquetados. Al seleccionar una oferta en la vista estrecha se desplaza al detalle. El texto vacío ya no depende de «a la izquierda».
- Checklist, encabezados, badges y paginación se adaptan a textos largos; controles de al menos 44 px en la aplicación. Los inputs móviles conservan 16 px para evitar zoom automático de Safari.
- Administración: formulario con menos columnas en resoluciones intermedias, campos identificados y correo de cabecera limitado para no desplazar acciones.
- Herramientas internas: controles compatibles con tema oscuro y sin landmarks main anidados. No se modificó su autorización ni se habilitaron funciones DEV fuera de DEV.
- La primera pasada encontró contrastes insuficientes y enlaces distinguibles solo por color. Se corrigieron rojos de error/acciones destructivas, advertencias ámbar en oscuro y subrayados de enlaces dentro de texto.
- La llamada a la prueba de 14 días se corrigió a los 30 días establecidos por el propietario. No se modificaron precios, checkout, licenciamiento ni permisos.

## Validación ejecutada

1. Build de producción de Next: aprobado. TypeScript `tsc --noEmit`: aprobado. `git diff --check -- frontend`: aprobado.
2. `frontend/scripts/verify-seo.mjs`: cuatro entornos (producción, DEV, STG y localhost), verificando canónicos, títulos, sitemap, robots y cabeceras.
3. Primera pasada: 572 comprobaciones de vista; sin desbordamientos ni errores JS, con hallazgos de contraste y enlaces conservados en `initial-findings.json`. Dos rutas ausentes en las muestras iniciales se añadieron a las simulaciones antes de validar resultados SECOP poblados.
4. Pasada corregida: **590 comprobaciones aprobadas**. Son 26 vistas × 11 resoluciones × 2 temas, más 18 comprobaciones de pantallas Free. Cero desbordamientos horizontales, controles fuera del viewport (salvo tablas con scroll propio), errores JS, enlaces con botones anidados o hallazgos axe WCAG A/AA/2.1 AA en las vistas ejercitadas. Ninguna ruta API solicitada quedó sin muestra.
5. Resoluciones: 320×760, 390×844, 640×900, 768×1024, 820×1180, 1024×768, 1280×800, 1440×900, 1920×1080, 2560×1440 y 844×390. Temas claro/oscuro. Chrome real con viewports emulados.
6. Vistas: inicio, Contacto, registro/login, recuperación/verificación de correo, tres páginas legales, resumen, oportunidades SECOP y detalle, ofertas, alertas, perfil, plan, sincronización, manuales, sugerencias, licencia comercial, administración, cotizaciones TVEC, histórico y detalle TVEC, diagnóstico y evaluación interna.
7. Interacciones: apertura/cierre del menú mediante teclado y restauración de foco; apertura del recordatorio y cierre con Escape; datos de prueba con nombres largos y borradores sin espacios. Las API privadas fueron simuladas. No se enviaron mensajes ni correos ni se ejecutaron sincronizaciones.
8. Tras los últimos ajustes exclusivos de títulos y robots, se reconstruyó la aplicación y se ejecutó una comprobación HTTP adicional: páginas 200, un h1 público, un canónico correcto, título con una sola marca, descripción e imagen social en HTML sin ejecutar JS, cabeceras noindex, sitemap y PNG correctos. No se atribuye esa comprobación a tráfico real de Google.

El build no produjo advertencias de Next. La shell local emitió `/Users/jorgehernandez/.rvm/scripts/rvm:29: operation not permitted: ps`; corresponde a la inicialización del entorno, no a un fallo de la aplicación. No se ocultaron los hallazgos iniciales de accesibilidad. No se volvió a ejecutar la suite backend: no se cambió lógica backend, modelos ni migraciones; el único archivo backend añadido es el script QA.

## Límites y pendientes

- No existe una garantía de indexación perfecta o posición en buscadores. No se accedió a Search Console ni se enviaron URLs/sitemap. Después de desplegar: comprobar las URL canónicas en producción, enviar `https://mysecop.co/sitemap.xml` desde una propiedad autorizada e inspeccionar inicio y Contacto.
- La matriz cubre tamaños representativos, no todas las resoluciones posibles. No se probaron dispositivos físicos, Safari/Firefox, todas las combinaciones de zoom o todos los estados de cada formulario. Cero hallazgos automáticos no certifica accesibilidad total.
- No se midieron Core Web Vitals de usuarios reales ni se declara una puntuación Lighthouse. La carga de Inter continúa dependiendo de Google Fonts.
- Las comprobaciones responsive privadas usan API sintética, no prueban persistencia ni entregas SMTP en producción. No se alteraron bases, datos o servicios remotos.
- Las páginas legales siguen pendientes de contenido definitivo y permanecen fuera del sitemap. No se publicaron borradores como políticas vigentes.
- Se conservaron los precios y prestaciones existentes; su consistencia comercial entre landing, planes y checkout requiere una revisión comercial separada. La corrección de 30 días cambia el texto, no la implementación de facturación.

## Reproducción

Desde frontend, construir con `NEXT_PUBLIC_SITE_URL=https://mysecop.co npm run build`; ejecutar `node scripts/verify-seo.mjs` y `npx tsc --noEmit`. Después ejecutar `backend/scripts/e2e_ux_seo.py` con un Python que disponga de Playwright/httpx, Chrome y AXE_CORE_PATH. El script inicia/cierra su propio servidor local y usa muestras sintéticas. `UX_SEO_EVIDENCE` fija el directorio de resultados y `UX_SEO_HTTP_ONLY=1` limita la ejecución a SEO/HTTP.

## Evidencia y archivos

Evidencia: `backend/benchmarks/ux-seo-20261118/`: resultados iniciales y finales, capturas, logs de build y HTTP, imagen social. Resumen y hashes SHA-256 en `MYSECOP_UX_RESPONSIVE_SEO_20261118.json`.

Archivos modificados o añadidos en esta revisión:

- `frontend/app/(private)/app/admin/page.tsx`
- `frontend/app/(private)/app/diagnostico-compatibilidad/page.tsx`
- `frontend/app/(private)/app/evaluacion-interna/page.tsx`
- `frontend/app/(private)/app/layout.tsx`
- `frontend/app/(private)/app/ofertas/page.tsx`
- `frontend/app/(private)/app/sincronizacion/page.tsx`
- `frontend/app/contacto/page.tsx`
- `frontend/app/globals.css`
- `frontend/app/iniciar-sesion/layout.tsx`
- `frontend/app/layout.tsx`
- `frontend/app/legal/[documento]/page.tsx`
- `frontend/app/page.tsx`
- `frontend/app/registro/layout.tsx`
- `frontend/app/robots.ts`
- `frontend/app/sitemap.ts`
- `frontend/components/contact-form.tsx`
- `frontend/components/secop-opportunities.tsx`
- `frontend/components/ui.tsx`
- `frontend/lib/button-styles.ts`
- `frontend/next.config.mjs`
- `frontend/lib/seo.ts`
- `frontend/app/(private)/layout.tsx`
- `frontend/app/restablecer-contrasena/layout.tsx`
- `frontend/app/verificar-correo/layout.tsx`
- `frontend/app/opengraph-image.tsx`
- `frontend/scripts/verify-seo.mjs`
- `backend/scripts/e2e_ux_seo.py`

## Despliegue y reversión

Listo para validación en DEV mediante el flujo existente. No se desplegó ni se crearon commits durante esta tarea. Son cambios de frontend, metadatos y QA, sin migraciones. Para revertir tras una promoción futura, restaurar estos archivos desde la versión anterior y reconstruir la imagen frontend mediante el mismo flujo; no se requiere revertir datos. Los cambios de indexación solo llegan a los buscadores después del despliegue y de nuevos rastreos.

## Referencias

- [Google: indexación móvil](https://developers.google.com/search/docs/crawling-indexing/mobile/mobile-sites-mobile-first-indexing).
- [Google: construir y enviar sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).
- [Google: noindex y acceso de los rastreadores](https://developers.google.com/search/docs/crawling-indexing/block-indexing).
- [Google: límites de indexación y sitemap](https://developers.google.com/search/help/crawling-index-faq).
