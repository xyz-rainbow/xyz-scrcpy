# Checklist de implementación multiplataforma (fases 0–6)

Documentación interna para el equipo. Este checklist replica las tareas del plan de Cursor (**Windows monitor + uv / multiplataforma**). Al añadir o cerrar ítems, actualiza también el plan en el IDE si sigues usando ese flujo, para evitar deriva.

**Convención de IDs**: `phase{Fase}-{Orden}-{tema}` (coincide con los todos del plan).

---

## Resultado global (definición de hecho)

- [ ] **Linux**: instalar desde clone o release `.tar.gz`; `python3 install_xyz.py`; servicio user + alias + monitor con el contrato actual.
- [ ] **Windows**: instalar desde clone o release `.zip`; `uv` + `.venv`; tarea programada ejecuta **monitor**; launcher sin Git Bash obligatorio.
- [ ] **Releases**: tag `v*` publica dos assets (Linux + Windows) + checksums; versión única desde `pyproject.toml`.
- [ ] **CI**: verde en `ubuntu-latest` y `windows-latest`.

---

## Fase 0 — Fundamentos del repo y dependencias

**Objetivo**: una fuente de verdad para versión y deps; árbol del repo alineado con instalador y `uv`.

**Salida**: `py_compile` de entrypoints sin error; README con estructura mínima del repo.

- [ ] `phase0-01-pyproject-core` — Crear `pyproject.toml`: nombre del proyecto, versión (fija o dinámica), `requires-python`, deps runtime (p. ej. `psutil`), opcional `readme` como metadata.
- [ ] `phase0-02-requirements-uv-sync` — Alinear `.requirements.txt` / `uv`: contenido mínimo o `-e .`; que `installer.bat` y la documentación instalen las mismas deps que `pyproject`.
- [ ] `phase0-03-vendor-policy-readme` — Documentar en README política de `vendor/` (Opción A/B) y impacto en tamaño de release Linux vs Windows.
- [ ] `phase0-04-gitignore-gitattributes` — Revisar `.gitignore` (`.venv`, `dist`, `build`); opcional `.gitattributes` `eol=lf` para `*.py`.
- [ ] `phase0-05-readme-layout-stub` — README: sección breve estructura (`bin/`, `install_xyz.py`, `systemd/`, `docs/`, `tests/`).

---

## Fase 1 — CI multiplataforma

**Objetivo**: cada PR refleja Linux y Windows antes de refactors grandes.

**Salida**: CI verde en ambos runners; comandos reproducibles localmente.

- [ ] `phase1-01-ci-workflow-file` — Añadir `.github/workflows/ci.yml` (o equivalente) en `push` / PR.
- [ ] `phase1-02-ci-ubuntu-job` — Job `ubuntu-latest`: `py_compile` entrypoints, `unittest discover`, tests que requieran `bash` si aplica.
- [ ] `phase1-03-ci-windows-job` — Job `windows-latest`: mismos `py_compile` / `unittest`; estrategia explícita para tests que requieran `bash`.
- [ ] `phase1-04-ci-commands-doc` — Documentar en README o en comentarios del workflow los comandos locales equivalentes a CI.

---

## Fase 2 — Monitor unificado (Python + stub bash)

**Objetivo**: un solo bucle monitor en Python; Linux entra por `monitor.sh` → `monitor.py`.

**Salida**: tests de monitor en verde en Linux y Windows; smoke Linux (systemd, popup, logs).

- [ ] `phase2-01-monitor-py-skeleton` — `bin/monitor.py`: `REPO_DIR`, `PYTHONPATH`/`bin`, config via `config_loader`, bucle principal y `sleep`.
- [ ] `phase2-02-monitor-py-adb-serials` — Lectura seriales `adb`, persistencia de estado, conteo de dispositivos (paridad `monitor.sh`).
- [ ] `phase2-03-monitor-py-pause-cooldown` — Pausa/reconexión portada, `open_cooldown_seconds`, ficheros epoch bajo `tempfile`.
- [ ] `phase2-04-monitor-py-antispam` — Detección de procesos menú/scrcpy/monitor (psutil o capa única), razones de bloqueo.
- [ ] `phase2-05-monitor-py-terminal-linux` — Cadena gnome-terminal → fallbacks Linux (paridad `monitor.sh`).
- [ ] `phase2-06-monitor-py-terminal-windows` — `Start-Process` PowerShell/cmd para `menu.py`, geometría y `PATH` a `vendor`.
- [ ] `phase2-07-monitor-sh-stub` — `monitor.sh`: stub mínimo `exec python3 …/monitor.py`; validar `bash -n`.
- [ ] `phase2-08-tests-monitor-behavior` — `tests/test_monitor_behavior.py`: invocar `python` sobre `monitor.py`; rutas cooldown bajo `tempfile`.
- [ ] `phase2-09-check-script-pycompile-monitor` — `check_and_repair` (sh o py): incluir `py_compile` de `monitor.py` en quick/full.
- [ ] `phase2-10-linux-regression-smoke` — Checklist manual Linux: `systemctl --user`, popup con USB, logs; sin regresión del contrato systemd.

---

## Fase 3 — Checks, launcher y repair portables

**Objetivo**: pre-arranque y reparación sin Git Bash obligatorio en Windows; Linux conserva contrato vía delegación si el `.sh` llama a Python.

**Salida**: `unittest` verde en ambos OS; `check_and_repair.sh` / `repair_xyz.sh` en Linux con comportamiento esperado.

- [ ] `phase3-01-check-repair-py` — `bin/check_and_repair.py`: quick/full, timeouts, log sanitizado, `PASS` / `FAIL_OPEN` / `PASS_AFTER_REPAIR`.
- [ ] `phase3-02-check-repair-sh-delegate` — `check_and_repair.sh` delega en `check_and_repair.py` manteniendo salida esperada por `launch_with_checks`.
- [ ] `phase3-03-launch-with-checks-py` — `bin/launch_with_checks.py`: checks, prompts fail-open, URL issue, full checks en background, arranque del menú.
- [ ] `phase3-04-write-launcher-windows-cmd` — `install_xyz` `write_launcher` Windows: `.cmd` apunta a venv `python` + `launch_with_checks.py` (sin `bash`).
- [ ] `phase3-05-launch-linux-strategy` — Decisión documentada: Linux sigue con `launch_with_checks.sh` o migra a `.py` con paridad probada.
- [ ] `phase3-06-repair-windows` — `repair_xyz.py` (o `.ps1`): kill menú/monitor, validación, reinicio `schtasks` del monitor.
- [ ] `phase3-07-tests-shell-flows` — `test_shell_flows`: skip sin `bash` en Windows o rutas que ejecuten scripts Python.

---

## Fase 4 — Instalador Windows y menú

**Objetivo**: Windows instalado como Linux: tarea = monitor, `.cmd` sin `bash`, `uv` + `.venv` en `install_dir`, `PATH` a `vendor`.

**Salida**: instalación limpia en Windows real o VM; alias abre menú; USB dispara popup; sin `ImportError` por deps.

- [ ] `phase4-01-install-uv-post-copy` — `install_xyz`: tras `copy_project` en Windows, `uv venv` + `uv pip install` en `install_dir`; error claro si no hay `uv`.
- [ ] `phase4-02-install-schtasks-monitor` — `install_service` Windows: `schtasks` `/tr` `python[w]` … `install_dir/bin/monitor.py`, `cwd` = `install_dir`.
- [ ] `phase4-03-install-path-vendor-logging` — Tarea Windows: `PATH` prepend `vendor`; logging del monitor a `config/scrcpy.log` o `monitor.log`.
- [ ] `phase4-04-install-linux-deps-psutil` — `install_xyz` Linux: si hace falta `psutil`, `pip install --user` o documentado sin romper flujo solo-`python3`.
- [ ] `phase4-05-menu-restart-kill` — `menu.py` RESTART: matar `scrcpy` por serial de forma multiplataforma (p. ej. `psutil`); probar en Linux.

---

## Fase 5 — Documentación, limpieza y wrappers

**Objetivo**: un solo relato usuario/mantenedor; `.bat` delgados; `patch_menu` deprecado si aplica.

**Salida**: smoke Linux repetido; instalación manual desde clone en ambos SO según README.

- [ ] `phase5-01-readme-install-per-os` — README: tabla instalación Linux (systemd, `python3`) y Windows (`uv`, tarea, sin Git Bash).
- [ ] `phase5-02-changelog` — `CHANGELOG.md` primera entrada alineada a la versión de `pyproject`.
- [ ] `phase5-03-bat-wrappers` — `installer.bat` y `start.bat` delgados hacia `install_xyz` / `.venv\Scripts\python`.
- [ ] `phase5-04-patch-menu-deprecate` — `patch_menu.py`: no-op documentado o eliminar si `menu.py` es única fuente.
- [ ] `phase5-05-unittest-readme-validation` — Revisión final tests + comandos de validación en README; repetir smoke `phase2-10-linux-regression-smoke`.

---

## Fase 6 — Releases por sistema operativo

**Objetivo**: tag `v*` publica dos assets + checksums + notas.

**Salida**: smoke instalando solo desde `tar.gz` y `.zip` (sin `git clone`).

- [ ] `phase6-01-release-workflow` — Workflow release en tag `v*`; depende de CI verde; permisos `contents: write`.
- [ ] `phase6-02-artifact-linux-tar` — Empaquetar `tar.gz` Linux con exclusiones (DLL/exe Windows en `vendor` si aplica).
- [ ] `phase6-03-artifact-windows-zip` — Empaquetar `zip` Windows según política `vendor` de Fase 0.
- [ ] `phase6-04-checksums-release-notes` — `SHA256SUMS` + cuerpo del release (requisitos `uv`, `adb`, comandos de verificación).
- [ ] `phase6-05-smoke-from-artifacts` — Instalación smoke solo desde artefactos en Linux y Windows.

---

## Índice rápido ID → fase

| Rango de IDs | Fase |
|--------------|------|
| `phase0-01` … `phase0-05` | 0 |
| `phase1-01` … `phase1-04` | 1 |
| `phase2-01` … `phase2-10` | 2 |
| `phase3-01` … `phase3-07` | 3 |
| `phase4-01` … `phase4-05` | 4 |
| `phase5-01` … `phase5-05` | 5 |
| `phase6-01` … `phase6-05` | 6 |

---

## Orden de fases (dependencias)

```mermaid
flowchart LR
  F0[Fase0]
  F1[Fase1]
  F2[Fase2]
  F3[Fase3]
  F4[Fase4]
  F5[Fase5]
  F6[Fase6]
  F0 --> F1 --> F2 --> F3 --> F4 --> F5 --> F6
```

Las fases 2–4 pueden trabajarse en ramas paralelas con coordinación; no integrar Fase 4 antes de tener monitor y checks estables en CI.
