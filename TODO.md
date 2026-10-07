# TO BUILD A FIRE — Plan por niveles

Este plan construye el producto completo por estados coherentes. Un nivel terminado debe servirle a un equipo por sí mismo y ser una base directa para el siguiente. Si el tiempo disponible no alcanza para cerrar otro nivel, se entrega el último nivel completo y se informa el resto como pendiente.

## Destino

TO BUILD A FIRE asigna atención humana bajo evidencia a equipos que reciben más cambios de los que pueden revisar con cuidado. Sigue cada cambio desde el merge request hasta producción, relaciona el diff con claims protegidos, reúne evidencia acotada y muestra qué trabajo humano queda, por qué y con qué capacidad compite. Puede proponer reparaciones y acciones de release bajo políticas explícitas, y vuelve a abrir la revisión si el monitoreo detecta regresiones. Cada decisión conserva su relación con el cambio, la política y la evidencia que la produjo.

El producto optimiza la asignación de atención humana, no la cantidad de líneas ocultadas ni la cantidad de merges automáticos. El `Review Package` es un contrato interno versionado y con provenance entre componentes; no es el producto ni la decisión que ve el equipo. El producto es el **Attention Router** y su cola de trabajo humano.

## Forma del sistema

```text
GitLab MR / commit
        │
        ▼
Change Mapper agent ──► candidate observations
                              │
                      Evidence Engine
                tests / CI / scanners / ownership
                    contracts / provenance
                              │
                              ▼
           versioned Review Package (internal contract)
                    │                    │
           deterministic policy     Falsifier agent
                    └──────────┬─────────┘
                               ▼
                       Attention Router
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
         COVERED BY       TARGETED          DEEP
          EVIDENCE          REVIEW          REVIEW
                └──────────────┼──────────────┘
                               ▼
                 HUMAN resolves consequence
                 and material uncertainty
```

El `Review Package` es el contrato interno compartido por mapper, motor de evidencia, policy, falsifier y router. Las interfaces presentan la cola y los motivos de atención desde ese resultado; no reimplementan la decisión. El paquete registra revisión base y destino del MR, versión de política y verificaciones, observaciones con origen/alcance/estado, claims afectados y no resueltos, tareas de atención y enlaces a artefactos.

Los agentes de GitLab Duo pueden mapear cambios, investigar, proponer verificaciones, falsar conclusiones y preparar reparaciones. Cada afirmación comienza como `CANDIDATE` con agente, alcance y referencia a la entrada que la originó; sigue siendo una observación no confiable aunque otro agente la repita. El Evidence Engine aporta resultados delimitados; el evaluador determinista aplica política a evidencia estructurada; el Attention Router asigna trabajo. Los agentes no convierten candidatos en conclusiones, no editan la política que los limita ni autorizan sus propias acciones. El texto explicativo se conserva separado de decisiones que puedan habilitar acciones.

El resultado de evidencia y la ruta de atención son ejes distintos. `SUPPORTED`, `UNRESOLVED`, `CONTRADICTED` y `NOT_RUN` describen evidencia. `COVERED_BY_EVIDENCE`, `TARGETED_REVIEW` y `DEEP_REVIEW` describen la atención sugerida. `COVERED_BY_EVIDENCE` no significa que el cambio sea seguro ni autoriza merge: sólo indica que los claims declarados quedaron cubiertos por la evidencia requerida según la policy indicada.

Principio de autoridad: **los agentes producen observaciones; la verificación produce evidencia acotada; la policy enruta atención; las personas resuelven lo que sigue siendo consecuente e incierto.**

Cada tarea humana tiene minutos requeridos con provenance: inicialmente serán una estimación declarada por policy/owner o una observación medida, no una predicción del agente presentada como hecho. Sin estimación suficiente, la demanda es `UNKNOWN`, nunca cero. Desde el Nivel 1 el formato conserva demanda y capacidad; el Nivel 2 agrega y asigna la cola entre personas/equipos. El corte de capacidad debe mostrar el trabajo consecuente que quedó sin atender.

## Invariantes de todos los niveles

Estos requisitos acompañan cada nivel desde el primero que procesa un MR:

- **Identidad del cambio:** cada paquete y verificación se vincula a los SHA exactos de base y destino. Evidencia de otra revisión queda obsoleta y no cuenta como pase.
- **Proveniencia:** cada claim y observación conserva fuente, clase epistémica, alcance, versión de herramienta/política, resultado, limitaciones y referencias a evidencia.
- **Autoridad:** el contenido del MR, comentarios, logs, resultados de herramientas y mensajes de agentes son datos no confiables. Una policy versionada y protegida autoriza decisiones; un agente no puede cambiarla ni autoaprobarse.
- **Incertidumbre visible:** evidencia faltante, contradictoria o inconclusa conserva `UNRESOLVED`, `CONTRADICTED` o `NOT_RUN` y conduce a `TARGETED_REVIEW` o `DEEP_REVIEW`; nunca se convierte silenciosamente en éxito.
- **Alcance honesto:** un test o scanner respalda sólo lo que cubrió. Un pipeline verde, un resumen, un puntaje de confianza o menos líneas no significa “seguro”.
- **Acciones acotadas:** credenciales y permisos se reducen al repo, rama, ruta y acción necesarios. Merge, release, despliegue y rollback obedecen gates explícitos y registran quién o qué los autorizó.
- **Registro re-evaluable:** se conservan las entradas y ramas de cada decisión para que el paquete pueda reconstruirse; las narraciones y métricas de presentación no alteran el resultado.
- **Presupuesto honesto:** toda cola muestra demanda estimada/medida, capacidad declarada, corte y trabajo consecuente pendiente. Lo que quedó debajo del corte no se describe como revisado ni monitoreado.

Los cambios de nivel reciben revisión adversarial propia y comprueban que los invariantes anteriores siguen vigentes. Al terminar el horizonte elegido se hace revisión integrada de todos los niveles y después la verificación integrada.

## Nivel 1 — Un cambio, end to end

**Estado completo:** un MR real en un repo de GitLab recorre un ciclo asistido del post-code lifecycle y llega a una versión desplegada y monitoreada. La demo integra las nueve etapas: **Plan, Create, Verify, Package, Secure, Release, Configure, Monitor y Govern**. El equipo ve atención pendiente, motivos, claims/ubicaciones, evidencia y límites, capacidad humana, gates y provenance. La matriz operativa, criterios de evidencia y permisos están en [`docs/hackathon-path-b.md`](docs/hackathon-path-b.md).

El marco es Path B (proyecto original con licencia MIT) y autonomía Assisted. Duo mapea el cambio y propone; CI comprueba; policy enruta; una persona aprueba cada transición consecuente. El merge y el despliegue conservan gates explícitos. GCP Cloud Run es el destino elegido por la autora para demostrar el bonus de Google Cloud; OIDC evita claves cloud persistentes.

**Criterio de cierre:** el MR real activa un GitLab Duo Agent Platform flow visible en la historia CI/sesiones; se ven checkpoints humanos y aprobaciones protegidas; pruebas y scanners están vinculados al SHA evaluado; el Review Package puede reconstruirse; el release/deploy usa ese SHA y deja evidencia; Cloud Run responde en una URL pública; health/monitoring vincula una regresión con el cambio y reabre atención. La prueba compara cambios contrastantes y controles benignos. Ninguna etapa cuenta por estar sólo en un diagrama o prompt. No se afirma reducción de esfuerzo sin línea base ni se afirma “seguro” por líneas resumidas.

**No se considera terminado** si sólo existe el router local, una interfaz, una pipeline genérica de tests, un comentario de agente o un demo desconectado del flujo, las aprobaciones y el despliegue reales.

## Nivel 2 — Scheduler de atención humana para el equipo

**Estado completo:** el equipo ordena y asigna una cola de MRs según consecuencias sin resolver, expertise/ownership requerida y capacidad humana declarada. Las mismas tareas y semánticas de evidencia del Nivel 1 se conservan al agregar; se ve explícitamente qué queda debajo del corte de capacidad.

**Incluye:**

- Vista de Attention Router que agrega tareas de Review Packages sin reinterpretar evidencia ni cambiar sus decisiones.
- Orden reproducible por consecuencias, incertidumbre, tiempo requerido, expertise y capacidad; muestra los factores y el corte en lugar de ocultarlos en un score único.
- Resolución de ownership desde `CODEOWNERS` y políticas de repo, mostrando de dónde salió cada asignación sugerida.
- Presupuesto de atención por equipo/turno: capacidad en minutos, demanda total, minutos cubiertos, carga pendiente y antigüedad del trabajo debajo del corte.
- Registro de aceptación, reasignación, corrección, rechazo y motivo del reviewer como nuevas observaciones atribuibles.
- Métricas segmentadas de tiempo hasta revisión, dismiss rate, reaperturas y falsos positivos adjudicados. La fatiga de reviewers por alertas ruidosas es un costo del sistema. Los promedios no ocultan bandas de mayor consecuencia.

**Criterio de cierre:** ante una cola con diffs grandes mecánicos y diffs pequeños consecuentes, el equipo puede ver demanda frente a capacidad en minutos, por qué se ordenaron así, quién puede revisar cada claim y qué quedó sin atender. Cambiar el orden o adjudicar un hallazgo mantiene el paquete original y deja una decisión nueva trazable.

## Nivel 3 — Reparación y re-evaluación bajo aprobación humana

**Estado completo:** el flujo que ya cubre el ciclo de Nivel 1 también puede proponer una reparación acotada, evaluarla como un cambio nuevo, y enlazar verificación, release, despliegue, monitorización y re-apertura con la decisión original.

**Incluye:**

- Agente de reparación aislado que propone cambios en rama de trabajo, con permisos y superficies permitidas por policy; nunca modifica su propia policy.
- Vínculo entre MR original, propuesta, nueva revisión y nuevo Review Package; checks se repiten sobre el SHA nuevo.
- CI para tests, contratos, invariantes, dependencias y scanners requeridos por los claims afectados; evidencia no disponible queda marcada como tal.
- Paquete/versionado de release y gate que exige approvals declaradas para merge/despliegue según política.
- Despliegue con identidad de servicio acotada, configuración versionada y referencia al SHA aprobado.
- Monitorización de señales previamente declaradas; una regresión crea un nuevo evento relacionado y reabre evaluación/revisión.
- Registro de gates, approvals, errores, skips, reintentos, deploys y no-ops para reconstruir qué pasó.

**Criterio de cierre:** una reparación propuesta nunca modifica su policy ni se autoaprueba. Cada SHA nuevo recibe sus propias verificaciones/paquete; la reparación necesita aprobación humana según policy. Un test o scanner fallido bloquea según regla; uno no ejecutado no cuenta como limpio. Una regresión post-deploy se vincula a los paquetes y revisiones originales y produce una tarea accionable.

## Nivel 4 — Atención y evidencia entre repositorios

**Estado completo:** una organización coordina claims, políticas, contratos y dependencias entre repositorios relacionados, observa la carga de revisión a escala y mejora los procesos a partir de resultados adjudicados.

**Incluye:**

- Registro de repositorios y relaciones de dependencia/contrato con versiones y responsables.
- Resolución de claims compartidos y análisis de impacto cuando un cambio de un repo altera consumidores de otros.
- Políticas compatibles por repo/equipo, con excepciones acotadas, justificación, expiración y revisión periódica.
- Analítica de cola y esfuerzo basada en resultados observados y decisiones humanas, con cohortes, controles y límites declarados.
- Recomendaciones de ajuste o automatización emitidas como propuestas revisables. La calibración jamás elimina silenciosamente una evidencia o aprobación requerida.
- Reporte de nivel de servicio de atención: capacidad, cola no trabajada, edades y consecuencias pendientes.

**Criterio de cierre:** un cambio contractual en un repositorio muestra sus consumidores afectados, policies y paquetes relacionados. Las métricas pueden mostrar ahorro o reducción de carga sólo contra una línea base documentada; separan cobertura de evidencia, outcomes y trabajo humano realmente realizado.

## Qué adoptamos de los proyectos relacionados

- **Crucible:** el artefacto único como contrato de integración y las pruebas con mutantes/controles para probar que el sistema detecta sus propios errores. Aplicación: `Review Package` compartido y corpus de MRs adversariales con resultado esperado.
- **Stylometry-CI:** analizadores modulares conectados a CI pueden actuar como proveedores de observaciones. Su perfilado de autoría y su score compuesto no son la base de decisión de este producto: la anomalía de estilo no demuestra impacto del cambio ni autoría maliciosa.
- **Koine:** la sincronización bloque a bloque es útil para README inglés/español, sobre todo para preservar código y comandos y evidenciar traducciones desactualizadas. Es mantenimiento documental separado del motor de revisión.
- **Skills de gobernanza y evidencia:** los límites del agente, la procedencia de claims, determinismo, evaluación con controles negativos y costo de falsas alarmas se aplican en todos los niveles, no como etapas finales de hardening.

## Orden de construcción y pendientes

1. [x] Cerrar el contrato local v1 del Review Package y su router. La carga confiable de policy y autenticación de artefactos siguen pendientes.
2. [x] Definir un contrato de entrega que separa los cuatro niveles de producto de las nueve etapas del hackathon y cubre el camino Path B/Assisted end to end (`docs/hackathon-path-b.md`).
3. [x] Confirmar capacidades observadas: el rol custom **Developer + AI** creó, habilitó y editó el custom flow; `Assign reviewer` disparó una sesión y se ejerció Modify/Approve. La UI no dejó seleccionar el service account por `missing default namespace`, por lo que se asignó vía API. La disponibilidad de `agent-config.yml` y la garantía de gates de merge/deploy siguen pendientes.
4. [ ] Fijar demo repo/claims protegidos, proteger la rama por defecto, policy protegida y ownership de configuración. Usar el proyecto Showcase o acordar un proyecto GitLab de demo enlazado; el repo GitHub sigue siendo el proyecto original.
5. [ ] Completar el Flow Registry v1 de Duo: se validó y ejecutó un mapper de sólo lectura con fetch determinista de metadata/diffs, feedback Modify y aprobación humana antes de una nota interna. El control crítico !2 también llegó al checkpoint humano sobre su SHA aislado. Falta crear el Falsifier separado, integrar observaciones con el router y verificar gates protegidos de merge/deploy. Cualquier agente futuro con herramientas debe exigir `require_tool_approval: true` y carecer de escrituras preaprobadas.
6. [ ] Completar CI por una ruta real del MR: además de la captura del control benigno !1, snapshots de !2 midieron `DEEP_REVIEW` con una ruta fuera de scope y `TARGETED_REVIEW` tras aislarla a `src/auth.py`. El claim de autorización siguió `UNRESOLVED` por falta de `authorization-invariants`. `main` está protegida y `TBAF_MR_IID` se eliminó después de cada captura. Falta sumar verificaciones/scanners vinculados con alcance y gates, y preservar las fronteras de confianza.
7. [ ] Implementar release/configure/deploy a Cloud Run con protección GitLab, OIDC de vida corta, configuración versionada y referencia al SHA aprobado.
8. [ ] Implementar health/monitoring y re-apertura enlazada; documentar las nueve etapas con evidencia ejecutada y una demo pública contrastante.
9. [ ] Corpus de MRs con resultados esperados: !1 ejercitó una escalación de un cambio benigno no mapeado; !2 ejercitó un control sintético de autorización y el contraste entre `DEEP_REVIEW` (path adicional fuera de scope) y `TARGETED_REVIEW` (path aislado). Agregar diff generado benigno de 2.000 líneas, dependencia, formato, test faltante, scanner eliminado, assertion debilitada, umbral reducido, CI con `|| true` y más controles benignos.
10. [ ] Cerrar Nivel 1 con revisión adversarial integrada y verificación del recorrido completo. Reportar falsos positivos y minutos contra línea base por separado; no afirmar mejora sin medirla.
11. [ ] Preparar materiales Path B: URL de proyecto original, cambios de automatización/despliegue realizados desde 2026-10-05, URL GitLab pública, URL Cloud Run, historial de pipeline y video YouTube público de menos de tres minutos.
12. [ ] Sólo después del cierre de Nivel 1, seleccionar horizonte y construir Nivel 2 (scheduler multi-MR), luego Nivel 3 y Nivel 4.

El primer nivel que se implemente es el recorrido Assisted end to end de un cambio: las nueve etapas con evidencia real y gates humanos. Si el hackathon no permite terminar el Nivel 2, queda como producto útil ese recorrido de un MR desde evaluación hasta deployment/monitoring; no se rebaja a una pipeline de tests presentada como integración.
