# TO BUILD A FIRE — Plan por niveles

Este plan construye el producto completo por estados coherentes. Un nivel terminado debe servirle a un equipo por sí mismo y ser una base directa para el siguiente. Si el tiempo disponible no alcanza para cerrar otro nivel, se entrega el último nivel completo y se informa el resto como pendiente.

## Destino

Un sistema para equipos que reciben más cambios de los que pueden revisar con atención. Sigue cada cambio desde el merge request hasta producción, relaciona el diff con claims protegidos del repositorio, reúne evidencia con alcance conocido y dirige a una persona las consecuencias que siguen sin resolver. Puede proponer reparaciones y acciones de release bajo políticas explícitas, y vuelve a abrir la revisión si el monitoreo detecta regresiones. Cada decisión conserva su relación con el cambio, la política y la evidencia que la produjo.

El producto optimiza la asignación de atención humana, no la cantidad de líneas ocultadas ni la cantidad de merges automáticos.

## Forma del sistema

```text
GitLab MR / commit
        │
        ▼
Change map ──► claim candidates ──► evidence plan
                                      │
                           ┌──────────┴──────────┐
                           ▼                     ▼
                  agent investigation    deterministic checks
                           └──────────┬──────────┘
                                      ▼
                         versioned Review Package
                                      │
                             policy evaluator
                 ┌───────────┬────────┼─────────┐
                 ▼           ▼        ▼         ▼
              ALLOW        REVIEW   ABSTAIN    DENY
                 │           │        │         │
                 └───────────┴── human attention ┘
                                      │
                      approved repair / release / monitor
```

El `Review Package` es el contrato compartido entre el motor, CI, comentario o vista del MR, y el registro de auditoría. Ninguna interfaz vuelve a interpretar los hallazgos por su cuenta. El resultado mínimo registra revisión base y destino del MR, versión de política y verificaciones, observaciones con origen/alcance/resultado, claims afectados y no resueltos, outcome y enlaces a artefactos.

Los agentes de GitLab Duo pueden mapear, investigar, proponer verificaciones, falsar conclusiones y preparar reparaciones. Sus salidas son observaciones no confiables; no aprueban claims, no cambian la política que los limita y no autorizan sus propias acciones. Un evaluador determinista aplica política a evidencia estructurada. El texto explicativo se conserva separado del resultado que controla acciones.

## Invariantes de todos los niveles

Estos requisitos acompañan cada nivel desde el primero que procesa un MR:

- **Identidad del cambio:** cada paquete y verificación se vincula a los SHA exactos de base y destino. Evidencia de otra revisión queda obsoleta y no cuenta como pase.
- **Proveniencia:** cada claim y observación conserva fuente, clase epistémica, alcance, versión de herramienta/política, resultado, limitaciones y referencias a evidencia.
- **Autoridad:** el contenido del MR, comentarios, logs, resultados de herramientas y mensajes de agentes son datos no confiables. Una policy versionada y protegida autoriza decisiones; un agente no puede cambiarla ni autoaprobarse.
- **Incertidumbre visible:** evidencia faltante, contradictoria o inconclusa produce `ABSTAIN` o `REVIEW`; nunca se convierte silenciosamente en éxito.
- **Alcance honesto:** un test o scanner respalda sólo lo que cubrió. Un pipeline verde, un resumen, un puntaje de confianza o menos líneas no significa “seguro”.
- **Acciones acotadas:** credenciales y permisos se reducen al repo, rama, ruta y acción necesarios. Merge, release, despliegue y rollback obedecen gates explícitos y registran quién o qué los autorizó.
- **Registro re-evaluable:** se conservan las entradas y ramas de cada decisión para que el paquete pueda reconstruirse; las narraciones y métricas de presentación no alteran el resultado.

Los cambios de nivel reciben revisión adversarial propia y comprueban que los invariantes anteriores siguen vigentes. Al terminar el horizonte elegido se hace revisión integrada de todos los niveles y después la verificación integrada.

## Nivel 1 — Paquete de evidencia para un MR

**Estado completo:** una persona puede procesar un merge request real en un repositorio y recibir un paquete útil antes de leer el diff entero. El sistema presenta comportamiento cambiado, claims candidatos/afectados, pruebas aplicables, evidencia encontrada y ausente, consecuencias sin resolver y ubicaciones concretas para el reviewer. Se integra con GitLab Duo Agent Platform para investigación y con CI/verificaciones deterministas para evidencia ejecutable.

**Incluye:**

- Entrada de GitLab para un MR con captura inmutable de base, head y metadatos necesarios.
- Mapa del cambio por archivo/hunk, dependencias e interfaces afectadas; los clasificadores automáticos declaran incertidumbre y enlazan al diff.
- Un contrato versionado de `Review Package` con observaciones tipadas, claims, verificaciones, decisión y procedencia.
- Política explícita del repo para superficies protegidas y evidencia requerida. Claims de ejemplo: límite de autorización y compatibilidad de contrato.
- Agentes Duo de análisis/falsificación con permisos de sólo lectura. Los agentes pueden sugerir checks y claims, no certificar el resultado.
- Ejecución de verificaciones seleccionadas y registro de revisión, comando/herramienta, versión, resultado, alcance, limitaciones y artefactos.
- Evaluador determinista que emite `ALLOW`, `REVIEW`, `ABSTAIN` o `DENY`, con la regla y evidencia que explican la rama.
- Salida legible enlazada al mismo paquete: comentario o vista de MR y comando local para inspeccionar/reproducir el reporte.
- Retención acotada y controlada de datos; nunca enviar secretos ni contexto privado no necesario a modelos externos.

**Criterio de cierre:** una demo conectada a GitLab muestra dos MRs contrastantes: un diff grande dominado por cambios generados/mecánicos y uno pequeño que cruza autorización. El sistema dirige atención al claim consecuente, enlaza evidencia y alcance; con evidencia ausente o de otro SHA se abstiene. El reviewer puede reconstruir el outcome desde el paquete. Medir la superficie marcada para revisión no se presenta como porcentaje de seguridad ni como ahorro de tiempo hasta contar con una línea base.

**No se considera terminado** si sólo existe una interfaz, un prompt de review, una suma de líneas, un score opaco, un comentario de agente o un demo desconectado del artefacto de decisión.

## Nivel 2 — Cola de atención para el equipo

**Estado completo:** un equipo usa los paquetes del Nivel 1 para ordenar y asignar una cola de MRs según consecuencias sin resolver, expertise/ownership requerida y capacidad humana declarada. Se ve explícitamente qué queda debajo del corte de capacidad.

**Incluye:**

- Vista de cola que agrega Review Packages sin reanalizar ni cambiar sus decisiones.
- Reglas de orden visibles y reproducibles basadas en consecuencias y claims afectados; no un score único sin factores explicables.
- Resolución de ownership desde `CODEOWNERS` y políticas de repo, mostrando de dónde salió cada asignación sugerida.
- Presupuesto de atención por equipo/turno y corte explícito: cantidad atendible, cantidad pendiente y antigüedad del trabajo debajo del corte.
- Registro de aceptación, reasignación, corrección, rechazo y motivo del reviewer como nuevas observaciones atribuibles.
- Métricas segmentadas de tiempo hasta revisión, dismiss rate, reaperturas y falsos positivos adjudicados. Los promedios no ocultan bandas de mayor consecuencia.

**Criterio de cierre:** ante una cola con diffs grandes mecánicos y diffs pequeños consecuentes, el equipo puede ver por qué se ordenaron así, quién puede revisar cada claim y qué quedó sin atender según capacidad. Cambiar el orden o adjudicar un hallazgo mantiene el paquete original y deja una decisión nueva trazable.

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
5. [ ] Escribir corpus de casos esperados: grande/mecánico, pequeño/consecuente, benignos, evidencia faltante, SHA obsoleto, policy contradictoria y prompt injection en MR/logs.
6. [ ] Construir y cerrar el Nivel 1 con su revisión adversarial y evidencia de demo.
7. [ ] Sólo entonces fijar con evidencia el siguiente nivel que se construye y su horizonte real.

El primer nivel que se implemente tiene que ser el paquete de MR completo descrito arriba. Si el hackathon no permite terminar otro nivel, el producto alcanzado sigue siendo una herramienta útil para revisar un MR a la vez.
