# Documentos legales MySECOP — borradores 0.2

Preparados el 17 de noviembre de 2026; actualizados el 18 de noviembre de 2026 con información del operador. **No aprobados, no vigentes y no publicados.**

## Documentos

- [Términos y condiciones](TERMINOS_Y_CONDICIONES.md): reglas del servicio, alcance de resultados, cuentas, planes, contratación y reclamaciones.
- [Política de privacidad](POLITICA_DE_PRIVACIDAD.md): explicación de categorías, usos, navegador, proveedores, seguridad y solicitudes.
- [Política de tratamiento de datos](POLITICA_DE_TRATAMIENTO_DE_DATOS.md): responsable, derechos, procedimiento, conservación y gestión del tratamiento.

Se redactaron para revisión y adaptación a MySECOP; no se copiaron políticas de otra empresa. Los textos no acreditan controles o procedimientos aún no implantados. Se recomienda revisar su versión final con asesoría jurídica colombiana y con quien opera el servicio.

## Información confirmada por el operador

- Responsable: Zorba Games Studios S.A.S., empresa, NIT 902075854, Bogotá, Colombia. Se transcribe la identificación facilitada; no se ha contrastado RUT ni dígito de verificación.
- Contacto: info@zorbagames.com y +57 320 493 0650. Atención de solicitudes: Jorge Hernández. No se le atribuye un cargo de representación legal no informado.
- Sin permanencia; prueba gratuita de 30 días; cobro mensual y renovación automática mediante Mercado Pago.
- Cancelar detiene renovaciones futuras y conserva acceso hasta terminar el período pagado.
- Regla comercial de no devolución por cancelación voluntaria del período ya pagado, con salvedad expresa de derechos y restituciones exigibles por ley. No se redactó como prohibición absoluta de reclamar.
- MySECOP consulta información oficial: no publica convocatorias u ofertas en los sistemas oficiales, no presenta propuestas, no fija precios de contratos públicos y no adjudica ni asigna licitaciones. Esto no impide cobrar la tarifa de la propia suscripción.

## Precios y discrepancias por resolver

La lectura HTTPS de https://mysecop.co el 18/11/2026 confirmó Explorador gratis, Independiente $59.900 COP/mes, Profesional $290.000 COP/mes y Corporativo a la medida. Se incorporaron los importes publicados, sin afirmar que incluyan impuestos. Evidencia resumida en `PRECIOS_Y_CONFIRMACIONES_20261118.json`.

La página pública todavía anuncia «Probar 14 días». La condición suministrada por el operador es **30 días**, que se adoptó en los documentos. Deben alinearse landing, checkout, condiciones de contratación y configuración de prueba antes de publicar los términos finales. No se modificó código o configuración en esta tarea.

La inspección de `backend/app/routers/billing.py` muestra una suscripción Mercado Pago con importe fijo de 59900 COP bajo el nombre «MySECOP Pro». No demuestra que el checkout productivo distinga el plan Profesional publicado por 290000 COP del Independiente de 59900 COP. Se requiere verificar esa correspondencia sin realizar cobros reales; no se cambió la pasarela ni se certificó su funcionamiento a partir de la tabla de precios.

Las afirmaciones públicas de funciones «ilimitadas» también requieren contraste con los cupos efectivos; no se incorporó una garantía ilimitada a estos documentos.

## Información y verificaciones que aún faltan

1. Dirección física para notificaciones del operador. Confirmar identificación completa para publicación, incluido dígito de verificación si corresponde.
2. Suplencia de Jorge Hernández y procedimiento real de recepción, registro, seguimiento y respuesta a solicitudes.
3. Proveedores activos, países, contratos y categorías de datos intercambiados. Mercado Pago ya está identificado; faltan entidad contratada y condiciones concretas. No se presume ubicación de hosting, correo o IA.
4. Calendario de conservación y eliminación por categoría y ciclo de respaldos.
5. Tratamiento de impuestos en precios, si la prueba de 30 días requiere tarjeta y qué funciones incluye, y correspondencia entre oferta y cobro efectivo de cada plan.
6. Evidencia de controles de seguridad, incidentes, recursos de terceros y almacenamiento en navegador activos.
7. Versionado, aceptación y prueba de autorizaciones en formularios, y autorización de cobros recurrentes. No se añadió técnicamente consentimiento por actualizar el texto.
8. Confirmar finalidades comerciales adicionales o entrenamiento con datos de clientes, si se pretenden usar. No se incorporan por silencio del operador.
9. Fecha de vigencia, aprobación y responsables de mantenimiento documental. No se eligió una fecha retroactiva ni se atribuyó aprobación por facilitar datos.

Los `[PENDIENTE...]` son campos de trabajo, no contenido listo para usuarios. No deben publicarse sin completar y validar. Los documentos no afirman que borrar la cuenta, exportar toda la información o controlar automáticamente términos de reclamos sean funciones ya disponibles.

## Base funcional revisada

| Tema | Evidencia en el código | Tratamiento en los borradores |
|---|---|---|
| Contacto | `backend/app/routers/contact.py` | Mensajes almacenados y envío por correo según configuración |
| Cuenta | `backend/app/routers/auth.py` | Datos de registro, contraseña con hash y comunicaciones según SMTP |
| Sesión y tema | `frontend/lib/api.ts`, `frontend/components/theme.tsx` | Almacenamiento local/de sesión; no se promete ausencia de cookies |
| Visitas y presencia | `backend/app/routers/admin.py`, `frontend/components/landing-visit.tsx` | Se explican registros de actividad y medición propia |
| Documentos | `backend/app/routers/documents.py` | Permisos y contenido aportado; no se promete cierre automático de cuenta |
| IA configurable | `backend/app/agents/pliegos.py`, `backend/app/services/embeddings.py` | Se describe la posibilidad de proveedores; activación, países y contratos pendientes |
| Suscripciones | `backend/app/routers/billing.py` | Condiciones suministradas por el operador; importes de la web y correspondencia de cobros pendiente; sin cambios de licencia |

La revisión de código no equivale a inventario del entorno productivo ni verificación contractual de sus proveedores.

## Fuentes oficiales consultadas

- [Ley 1581 de 2012 — Función Pública](https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=49981&success=true): derechos y tratamiento de datos.
- [Artículo 14 — compilación MinTIC](https://normograma.mintic.gov.co/mintic/compilacion/docs/ley_1581_2012.htm): consultas.
- [Ley 1581 — copia oficial IDEAM](https://www.ideam.gov.co/sites/default/files/normatividad/ley_1581_de_2012.pdf): reclamos y términos del artículo 15.
- [Decreto 1074 de 2015 — compilación Colpensiones](https://normativa.colpensiones.gov.co/colpens/docs/pdf/decreto_1074_2015_pr026.pdf): contenido mínimo de la política y aviso de privacidad.
- [Orientación SIC sobre políticas](https://sedeelectronica.sic.gov.co/publicaciones/boletin-juridico/concepto/politicas-de-tratamiento-de-datos-personales).
- [Ley 1480 de 2011 — Función Pública](https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=44306) y [Ley 2439 de 2024](https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=257116): contratación y protección al consumidor en comercio electrónico, cuando corresponda.

La consulta incluyó resultados indexados oficiales; algunas aperturas directas respondieron 403, 502 o timeout. No se afirma haber recuperado íntegramente todos los textos consolidados. La revisión final debe comprobar modificaciones, aplicabilidad y normativa vigente; se evitó fijar excepciones automáticas al retracto o reglas de devolución sin esa comprobación.

## Publicación posterior

Las páginas informativas `/legal/...` existentes se conservaron. No se sustituyeron por borradores ni se desplegó a DEV, STG o producción. Al recibir los datos y aprobar las versiones, podrán integrarse en esas rutas, enlazarse desde los formularios correspondientes y comprobarse su lectura en móvil y escritorio. No hubo commits ni cambios de código del producto en esta tarea.

## Registro de actualización del 18 de noviembre de 2026

Se actualizaron los tres textos y este índice con los datos suministrados por el operador y la tabla pública de precios. Se verificaron consistencia de identidad, correo, teléfono y plazos comerciales entre documentos, y referencias locales. La edición es documental: no se ejecutaron cobros, no se enviaron comunicaciones, no se hicieron commits y no se publicó en ningún entorno.
