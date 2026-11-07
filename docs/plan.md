# GetItDone - Implementation Plan

This implementation plan breaks down the development of **GetItDone** into sequential, atomic steps. AI agents or developers should complete each step, test it, mark it as completed (`[x]`), and proceed to the next step.

---

## Phase 1: Foundation & Data Models
- [x] **Step 1.1: Declare dependencies in `pyproject.toml`**
  - `PyQt6>=6.5.0` in `[project.dependencies]`; tooling in the `dev` extra.
- [x] **Step 1.2: Implement `src/getitdone/models.py`**
  - Define `Task` data class (`id`, `title`, `status`, `created`, `modified`).
  - Define `Story` data class (`id`, `title`, `description`, `tasks` list).
  - Define `Workspace` (the whole document) with serialization helpers.
  - Tolerant `from_dict()` parsing so corrupt files degrade instead of raising.
- [x] **Step 1.3: Implement `src/getitdone/storage.py` (JSON Persistence & Error Recovery)**
  - Default storage path (`~/.getitdone/tasks.json`, falling back to `%LOCALAPPDATA%/GetItDone` - never inside the package).
  - `load_data()` with `try...except (json.JSONDecodeError, IOError)` fallback to an empty workspace.
  - `save_data(data)` atomic auto-save (temp file + `os.replace`).
  - Corrupt files are quarantined (`*.corrupt-<timestamp>`) rather than deleted.

---

## Phase 2: Core Desktop Widget UI & Window Management
- [x] **Step 2.1: Implement `src/getitdone/ui/main_window.py` (Desktop Widget Setup)**
  - Create `MainWindow` inheriting from `QWidget`.
  - Apply PyQt window flags for desktop background integration (`Qt.WindowType.FramelessWindowHint`, `Qt.WindowType.WindowStaysOnBottomHint`).
  - Cover the full desktop area (`QScreen.availableGeometry()`).
- [x] **Step 2.2: Implement Story & Task UI Components in `src/getitdone/ui/widgets.py`**
  - Scrollable area containing story cards, distributed across columns.
  - Expandable/collapsible inline task lists (single-expand accordion style).
  - Color-coded status indicators (`todo`: gray, `inprogress`: blue, `close`: green).
  - Click-to-cycle status workflow (`todo` → `inprogress` → `close` → `todo`).
- [x] **Step 2.3: Adaptive Column Layout**
  - Column count derived from screen width (1–4), re-flowed on resize/DPI change.
  - Visual constants and stylesheet centralised in `src/getitdone/ui/theme.py`.
- [x] **Step 2.4: Project Structure & Test Suite**
  - Package layout (`src/getitdone/`, `src/getitdone/ui/`, `tests/`, `docs/`).
  - `pyproject.toml` with packaging metadata and the `getitdone` entry point.
  - Headless pytest suite covering models, storage, and UI behavior.

---

## Phase 3: Interactivity, Management, & System Tray
- [ ] **Step 3.1: Story & Task CRUD Dialogs / Actions**
  - Add Story button & dialog (currently emits `add_story_requested`).
  - Add Task under story button & inline input.
  - Edit / Delete story and task actions.
  - Right-click context menu.
- [ ] **Step 3.2: System Tray & Auto-Start Integration**
  - Add `QSystemTrayIcon` with context menu (Show/Hide, Settings, Exit).
  - Implement Windows Registry auto-start toggle (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
- [ ] **Step 3.3: Desktop Icon Coexistence**
  - The full-screen widget currently covers desktop icons.
  - Decide between an inset region or `WindowTransparentForInput` on empty areas.

---

## Phase 4: Entry Point, Polish & Distribution
- [ ] **Step 4.1: Finish `getitdone/__main__.py`**
  - Entry point exists (`python -m getitdone`, `--dev`, `--top`).
  - Remaining: single-instance lock, startup error dialog, graceful exit.
- [ ] **Step 4.2: Desktop-Layer Embedding**
  - Windows: optional `WorkerW` parenting so the widget survives Win+D. *(not started)*
  - Linux/X11: **done** - `_NET_WM_WINDOW_TYPE_DESKTOP` via `ui/x11.py` puts the
    widget in the desktop layer, where it survives "Show Desktop", is visible on
    every workspace (`_NET_WM_STATE_STICKY`), and still accepts clicks.
    Falls back to `WindowStaysOnBottomHint` off X11, or on request via
    `--no-desktop`. Verified under GNOME 46 / XWayland.
- [ ] **Step 4.3: Testing & Verification**
  - Expand the pytest suite alongside each Phase 3 feature.
  - Manual pass: auto-save, positioning, status cycling, focus behaviour.
- [x] **Step 4.4: Create `LICENSE` & `README.md`**
  - GPL v3 license text and end-user documentation.
- [ ] **Step 4.5: Packaging**
  - Build a distributable (PyInstaller or `pipx`), verify the `getitdone` command.

