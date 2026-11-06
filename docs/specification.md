# GetItDone

## Project Overview

**Name**: GetItDone  
**Description**: A lightweight, open-source Windows desktop-embedded widget application for personal project management, functioning directly on the Windows desktop background with story → task hierarchy and status tracking.

**Core Philosophy**: Simple, offline-first, Python-based project management tool embedded directly into the Windows desktop background. Upon system login (via Windows startup registry), the UI paints onto the desktop background so users can view, click, and interact with stories and tasks right on their desktop wallpaper.

---

## Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.10+ | Rapid development, easy to understand, minimal licensing concerns |
| **GUI Framework** | PyQt6 | Modern UI, GPL-licensed (compatible with open-source goals) |
| **Data Storage** | JSON file (`tasks.json`) | Human-readable, easy to edit, no database setup required |
| **License** | GPL v3 | Compatible with PyQt6 GPL, ensures project remains open source |
| **Auto-Start & Integration** | Windows Registry (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`) + Desktop Layer Positioning | Automatically launches on login and anchors as a desktop-background widget. |

---

## Feature Specifications & Clarifications

### Core Features

1. **Desktop Background Embedding (Wallpaper Widget)**
   - Frameless, non-activating or desktop-anchored window flags (`Qt.WindowType.FramelessWindowHint`, `Qt.WindowType.WindowStaysOnBottomHint`, or positioning on the desktop screen geometry).
   - Covers the full desktop area (`QScreen.availableGeometry()`), with stories laid out as cards in as many columns as the screen width allows.
   - Accessible immediately upon logging into Windows.

2. **Story Management**
   - Create, edit, and delete stories.
   - Each story contains a list of tasks.
   - Stories displayed in main scrollable panel, expandable/collapsible.

3. **Task Hierarchy & Data Model**
   - Structure: `Story` → `Tasks`
   - Tasks have three distinct status states:
     - `todo` (Gray / Pending)
     - `inprogress` (Blue / Active)
     - `close` (Green / Completed)
   - Clicking a story expands/collapses its task list inline. Single-expand recommended for clean desktop layout.

4. **Status Workflow**
   - Linear progression: `todo` → `inprogress` → `close` → (loops back to `todo` on click).
   - Visual status indicators with color coding.
   - Click to cycle status or right-click context menu.

5. **System Tray & Auto-Start**
   - Windows Startup registration option so it appears automatically upon user login.
   - System tray icon for quick access, settings, or exit.

6. **Data Persistence & Error Handling**
   - Stored in single JSON file: `~/.getitdone/tasks.json` (fallback to local directory if home directory is unwritable).
   - Auto-save immediately upon any modification.
   - **Error Handling**: If `tasks.json` is missing or corrupted, initialize with an empty default template structure.

### Out-of-Scope (Explicitly Not Included)
- ✗ Jira/External API integration
- ✗ User accounts or authentication
- ✗ Cloud synchronization / Multi-user collaboration
- ✗ Advanced reporting, analytics, or mobile apps

---

## UI/UX Design

### Desktop Widget Layout & Interaction
```
+--------------------------------------------------------------+
|  GetItDone                             3 stories · 5/11 done |
|--------------------------------------------------------------|
|  +------------------------+  +------------------------+       |
|  | ▼ Project Proposal 3/4 |  | ▼ Website Redesign 1/3 |       |
|  |   [✓] Write brief      |  |   [✓] Audit site       |       |
|  |   [◉] Research reqs    |  |   [◉] Wireframe page   |       |
|  |   [ ] Define milestone |  |                        |       |
|  +------------------------+  +------------------------+       |
|  +------------------------+  +------------------------+       |
|  | ▶ Home Office Setup    |  | ▶ Q3 Roadmap           |       |
|  +------------------------+  +------------------------+       |
|                                                              |
|  [ + Add Story ]                                    [ Settings ] |
+--------------------------------------------------------------+
```
*(Full-desktop dashboard, translucent over the wallpaper; column count adapts to screen width, 1–4.)*

---

## Data Structure (JSON Format)

```json
{
  "version": "1.0",
  "last_modified": "2026-01-15T10:30:00",
  "stories": [
    {
      "id": "story-1",
      "title": "Project Proposal",
      "description": "Initial project planning and scope definition",
      "tasks": [
        {
          "id": "task-1-1",
          "title": "Write project brief",
          "status": "todo",
          "created": "2026-01-15T09:00:00",
          "modified": "2026-01-15T09:00:00"
        }
      ]
    }
  ]
}
```

### Key Data Fields & Validation
- `version` (string): Schema version for future migration support.
- `id` (string): Unique identifier (UUIDv4 or timestamp-based hash).
- `title` (string): Required, non-empty.
- `status` (string): Must be strictly `"todo"`, `"inprogress"`, or `"close"`.
- ISO 8601 datetime strings for `created` and `modified`.

---

## Development Architecture & Modules

```
GetItDone/
├── src/
│   └── getitdone/
│       ├── __init__.py       # Version and package metadata
│       ├── __main__.py       # Entry point: QApplication setup, CLI flags
│       ├── py.typed          # PEP 561 marker for type checkers
│       ├── models.py         # Data classes (Workspace, Story, Task) - no Qt
│       ├── storage.py        # JSON load/save, path resolution, recovery
│       ├── service.py        # WorkspaceService: the UI's persistence seam
│       ├── dev.py            # Demo-data seeding for --dev
│       └── ui/
│           ├── __init__.py   # Lazy re-exports
│           ├── theme.py      # Palette, stylesheet, layout constants
│           ├── widgets.py    # StatusDot, TaskRow, StoryWidget
│           └── main_window.py # MainWindow: desktop shell and columns
├── tests/                    # pytest suite (headless, offscreen Qt)
├── docs/                     # This specification and the implementation plan
├── .github/workflows/        # CI: lint, type check, test, build
├── pyproject.toml            # Single source of truth: deps, version, tooling
├── LICENSE                   # GPL v3 license
└── README.md                 # End-user documentation
```

---

## Pitfalls & Best Practices to Avoid

1. **Desktop Layer Focus & Stealing**: When acting as a desktop background widget, ensure window flags (`Qt.WindowType.WindowStaysOnBottomHint`, `Qt.WindowType.FramelessWindowHint`) are correctly configured so it doesn't steal focus from normal application windows or get minimized when clicking "Show Desktop" (Win + D).
2. **Corrupted JSON Recovery**: Wrap JSON parsing in `try...except (json.JSONDecodeError, IOError)` to prevent startup crashes.
3. **Auto-Start Registry Handling**: Safely write/read to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` with fallback error handling.
4. **GPL v3 Compliance**: Retain license notices in source files and distribute `LICENSE`.

---

## Quick Start Commands

```bash
# Clone repository
git clone https://github.com/abhijeetmkumbhar/GetItDone.git
cd GetItDone

# Install dependencies
pip install -e ".[dev]"

# Run application
python -m getitdone
```