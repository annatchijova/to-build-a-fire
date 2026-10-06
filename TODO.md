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

## Nivel 1 — Attention Router para un MR

**Estado completo:** un equipo puede usar el Attention Router con un merge request real en un repositorio. El sistema presenta el trabajo humano pendiente, su motivo, los claims/cambios y ubicaciones que lo originan, la capacidad disponible y lo que queda fuera de esa capacidad. El contrato interno contiene mapa del cambio, claims candidatos/afectados, evidencia encontrada/ausente, tareas y provenance. Se integra con GitLab Duo Agent Platform para investigación/falsificación y con CI/verificaciones deterministas para evidencia ejecutable.

**Incluye:**

- Entrada de GitLab para un MR con captura inmutable de base, head y metadatos necesarios; configura capacidad humana disponible para la ventana de revisión.
- Mapa del cambio por archivo/hunk, dependencias e interfaces afectadas; los clasificadores automáticos declaran incertidumbre y enlazan al diff.
- Un contrato versionado interno de `Review Package` con observaciones tipadas, claims, verificaciones, tareas de atención y procedencia.
- Política explícita del repo para superficies protegidas, evidencia requerida, rutas y estimaciones humanas declaradas. Claims de ejemplo: límite de autorización y compatibilidad de contrato.
- Agentes Duo de análisis/falsificación con permisos de sólo lectura. Los agentes pueden sugerir checks y claims, no certificar el resultado.
- Ejecución de verificaciones seleccionadas y registro de revisión, comando/herramienta, versión, resultado, alcance, limitaciones y artefactos.
- Evaluador determinista que aplica policy versionada a evidencia estructurada; el router asigna ruta, demanda de atención y motivo por separado.
- Rutas de atención `COVERED_BY_EVIDENCE`, `TARGETED_REVIEW` y `DEEP_REVIEW`, con minutos y origen de la estimación; si no puede respaldarse una estimación, informa `UNKNOWN`.
- Comparación de demanda de ese MR con capacidad humana declarada para la ventana; la UI distingue tareas cubiertas, pendientes y demanda desconocida.
- Salida legible del Attention Router enlazada al paquete: comentario o vista de MR y comando local para inspeccionar/reproducir la decisión.
- Retención acotada y controlada de datos; nunca enviar secretos ni contexto privado no necesario a modelos externos.

**Criterio de cierre:** una demo conectada a GitLab muestra diffs contrastantes —uno grande dominado por cambios generados/mecánicos y uno pequeño que cruza autorización— junto con controles benignos. El router indica por qué y dónde hace falta atención, la demanda en minutos y qué queda sin cubrir; cada tarea enlaza a sus candidatos, evidencia y alcance. Con evidencia ausente, contradictoria o de otro SHA no marca el claim como cubierto. Un falsifier puede proponer contraejemplos como candidatos, pero no emitir conclusiones. Una persona puede reconstruir el recibo de la decisión. No se publica reducción de esfuerzo sin línea base y medición, ni se afirma “seguro” por la cantidad de líneas resumidas.

**No se considera terminado** si sólo existe una interfaz, un prompt de review, una suma de líneas, un score opaco, un comentario de agente o un demo desconectado del artefacto de decisión.

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

## Nivel 3 — Ciclo de cambio gobernado

**Estado completo:** desde el MR, el equipo puede permitir que agentes propongan reparaciones acotadas, verificarlas, empaquetar el resultado, aplicar gates de release, observar el despliegue y reabrir el flujo ante una regresión. El sistema cubre el ciclo post-código de forma operativa y mantiene gates explícitos para acciones de impacto.

**Incluye:**

- Agente de reparación aislado que propone cambios en rama de trabajo, con permisos y superficies permitidas por policy; nunca modifica su propia policy.
- Vínculo entre MR original, propuesta, nueva revisión y nuevo Review Package; checks se repiten sobre el SHA nuevo.
- CI para tests, contratos, invariantes, dependencias y scanners requeridos por los claims afectados; evidencia no disponible queda marcada como tal.
- Paquete/versionado de release y gate que exige approvals declaradas para merge/despliegue según política.
- Despliegue con identidad de servicio acotada, configuración versionada y referencia al SHA aprobado.
- Monitorización de señales previamente declaradas; una regresión crea un nuevo evento relacionado y reabre evaluación/revisión.
- Registro de gates, approvals, errores, skips, reintentos, deploys y no-ops para reconstruir qué pasó.

**Criterio de cierre:** una reparación propuesta recorre el flujo de verificación y release con aprobación humana cuando la policy la exige. Un test o scanner fallido bloquea según regla; uno no ejecutado no cuenta como limpio. Una regresión post-deploy se vincula al paquete y revisión originales y produce una tarea accionable.

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

1. [ ] Cerrar contrato v1 del Review Package: tipos de claim, observación, evidencia, outcome, SHA y versiones de schema/policy.
2. [ ] Especificar flujo GitLab MR y permisos mínimos disponibles para GitLab Duo Agent Platform.
3. [ ] Acordar el repositorio de demostración y sus claims protegidos (autorización, contrato/API, configuración de seguridad).
4. [ ] Definir verificaciones ejecutables y alcance exacto de cada una para el Nivel 1.
5. [ ] Escribir corpus de MRs con resultados esperados: 2.000 líneas generadas benignas, bump de dependencia, refactor de formato, test faltante, widening de auth en 2 líneas, scanner eliminado, assertion debilitada, umbral de coverage reducido, CI con `|| true` y controles benignos.
6. [ ] Definir oráculos para el corpus: cero cambios críticos sembrados que acaben en `COVERED_BY_EVIDENCE`; cero promociones de observación candidata a conclusión sin evidencia/adjudicación autorizada; informar la tasa de controles benignos escalados y minutos de review frente a línea base por separado; los casos fuera de alcance conservan esa limitación y se enrutan a revisión profunda.
7. [ ] Construir y cerrar el Nivel 1 con su revisión adversarial y evidencia de demo.
8. [ ] Sólo entonces fijar con evidencia el siguiente nivel que se construye y su horizonte real.

El primer nivel que se implemente tiene que ser el Attention Router completo para un MR descrito arriba. Si el hackathon no permite terminar otro nivel, el producto alcanzado sigue siendo una herramienta útil para asignar atención a un MR a la vez.
