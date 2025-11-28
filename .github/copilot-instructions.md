# Copilot / AI Agent Instructions for `fz_adr_match_dev`

Short, actionable guidance so an AI coding agent can be immediately productive working on this QGIS plugin.

## Big picture
- **Type:** QGIS Python plugin (single-plugin folder). Main entry is `fz_adr_match.py` which defines `FzAdrMatchPlugin(iface)` and implements `initGui`, `unload`, `run`.
- **Purpose:** 地址标准化与管网匹配（currently a scaffold that shows a message box in `run`).
- **Resources & UI:** Icons and resources live in `icons/`, `resources.qrc` (compiled to `resources_rc.py`). UI/menus are registered via `iface`.

## Key files to inspect
- `fz_adr_match.py` — plugin logic and lifecycle (guarded imports to allow safe static analysis).
- `metadata.txt` — QGIS plugin metadata (id, version, description used by QGIS).
- `resources.qrc` / `resources_rc.py` — resource bundle; `resources_rc.py` is the compiled output.
- `icons/` — SVG/png icons; `fz_adr_match.py` resolves icons with `os.path.join(self.plugin_dir, 'icons', '...')`.
- `README.md` — project overview; keep it in sync when changing public behavior.

## Important patterns & conventions (project-specific)
- The plugin uses a single class `FzAdrMatchPlugin` that accepts `iface` and registers actions in `initGui` and cleans up in `unload`.
- Actions are collected into `self.actions` and removed in `unload` with `iface.removePluginMenu` / `iface.removeToolBarIcon`.
- Guard imports for offline/static work: top-level `try/except ImportError` sets `QGIS_AVAILABLE` and stores the import error — code raises `RuntimeError` in `__init__` if not available. When writing tests or running static analysis, mock `qgis`/`qgis.PyQt`.
- Use `self.plugin_dir = os.path.dirname(__file__)` for filesystem paths — keep this pattern when adding templates or bundled data.

## Build / dev / debug workflows (concrete commands)
- Compile resources (run from the plugin directory):
```
pyrcc5 -o resources_rc.py resources.qrc
```
If your environment uses PyQt6, use `pyrcc6` accordingly.
- Install/try locally in QGIS:
  - Option A: copy the plugin folder into QGIS plugins path (example working path for this repo):
    `C:\Users\<you>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\fz_adr_match_dev`
  - Option B: zip the plugin folder (top-level files in zip) and use QGIS: *Plugins → Install from ZIP*.
- Restart QGIS or enable the plugin in *Plugins → Manage and Install Plugins* after installing.
- Quick runtime checks:
  - Use `print()` for simple debugging — messages appear in QGIS Python Console and QGIS log output.
  - Use `QMessageBox` or `iface.messageBar().pushMessage()` for visible user notifications.

## Testing guidance
- There are no automated tests in the repo. To run code outside QGIS, mock the `qgis` modules in tests: e.g. `sys.modules['qgis'] = mock_pkg` and provide minimal `PyQt` classes or use `monkeypatch` in pytest.
- Because `fz_adr_match.py` raises `RuntimeError` when QGIS imports fail, tests should either run inside QGIS's Python or patch `QGIS_AVAILABLE=True` and inject a fake `iface` object implementing `addToolBarIcon`, `addPluginToMenu`, etc.

## Integration & external dependencies
- Runtime dependency: QGIS (PyQt + QGIS Python API). No third-party PyPI deps are referenced.
- Native resources: `resources.qrc` compiled to `resources_rc.py` — regenerate when icons/resources change.

## Packaging & publishing notes
- For publishing to QGIS plugin repo or GitHub: create a zip of the plugin folder (no nested parent folder), include `metadata.txt` and compiled `resources_rc.py`.
- Consider adding a `.gitignore` to exclude `__pycache__/`, `.idea/`, and generated files if you prefer not to commit them.

## Concrete examples from this codebase
- Action creation in `fz_adr_match.py`:`self.action = QAction(QIcon(icon_path), "地址标准化匹配", self.iface.mainWindow())` and then `self.iface.addToolBarIcon(self.action)`; remove it in `unload` by iterating `self.actions`.
- Resource compile example (run in repo root where `resources.qrc` lives): `pyrcc5 -o resources_rc.py resources.qrc`.

## What an AI agent can safely change
- Small feature additions to `run()` that keep the plugin lifecycle patterns (register in `initGui`, clean in `unload`).
- Add new helper modules under the plugin folder and import them from `fz_adr_match.py` using `self.plugin_dir` when loading file-based templates.

## What to avoid / not discoverable automatically
- Do not assume a pure-PyPI test runner will work without mocking QGIS; the environment must either mimic QGIS or run inside QGIS Python.
- Avoid changing `metadata.txt` keys format — QGIS expects specific fields.

---
If any section is unclear or you want this file in English instead, tell me which parts to expand (testing examples, resource-build CI, or packaging steps) and I will iterate.
