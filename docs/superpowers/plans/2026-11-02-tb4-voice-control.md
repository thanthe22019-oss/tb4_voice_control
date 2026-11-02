# TB4 Voice Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public ROS 2 Humble repository that lets a user draw semantic regions on a TurtleBot 4 occupancy map, recognize Vietnamese push-to-talk commands with NVIDIA CUDA, and execute the resulting region route through Nav2.

**Architecture:** Copy only the reusable Nav2/map baseline from `tb4_nav2` into a separately versioned `tb4_voice_control` package. Keep map/schema, geometry, parsing, route planning, and route execution as UI-independent Python modules; place PyQt5 map editing and voice runtime in separate entry points, with speech and Nav2 work outside the Qt UI thread. Use a versioned `regions.yaml` as the contract between the offline Map Editor and the runtime voice controller.

**Tech Stack:** Ubuntu 22.04, Python 3.10, ROS 2 Humble, TurtleBot 4 Simulation, Nav2 `BasicNavigator`, PyQt5 5.15, OpenCV 4.5, PyYAML, NumPy, sounddevice, faster-whisper `small`, CTranslate2 CUDA, pytest, ament/colcon.

**Spec:** `docs/superpowers/specs/2026-11-02-tb4-voice-control-design.md`

## Global Constraints

- Target runtime is Ubuntu 22.04 with ROS 2 Humble and TurtleBot 4 Simulation.
- The existing `/home/alex/Interaction/tb4_nav2` repository and its Git history must not be modified.
- The new ROS package, Python import package, local directory, and GitHub repository are all named `tb4_voice_control`.
- Map editing is manual/semi-automatic with PyQt5 + OpenCV; the occupancy image itself is never modified.
- Speech recognition uses local `faster-whisper` model `small` on NVIDIA CUDA for the final demo.
- Runtime input is push-to-talk; continuous listening and LLM parsing are out of scope.
- Semantic region interiors may not overlap; shared boundaries are allowed.
- While a route is active, new speech/text commands are disabled until completion or cancellation.
- Milestone 7 multi-waypoint language is optional and starts only after Tasks 1–10 pass.
- Never commit `.venv-speech/`, downloaded Whisper models, microphone recordings containing private content, `build/`, `install/`, or `log/`.

## Review Focus

- A `map.yaml` with a relative `image`, nonzero origin, `negate`, and trinary thresholds must produce the correct free/occupied mask; pin this in Task 2.
- Polygon interiors that overlap must fail, while polygons that only share an edge must pass; pin this in Task 3.
- Vietnamese aliases that normalize to the same text, including accented/unaccented forms, must be rejected as ambiguous before runtime; pin this in Task 3 and Task 6.
- A second command during navigation must never replace or queue the active route, and cancellation must release the UI for the next command; pin this in Task 7 and Task 9.
- Missing CUDA/model, microphone, AMCL, or Nav2 must yield a visible error and zero goals sent; pin adapters with automated tests in Tasks 7–9 and perform hardware proof in Task 10.

---

## Milestone 0 — Independent clean baseline

### Task 1: Copy, rename, clean, and version the Nav2 baseline

**Files:**
- Preserve: `/home/alex/Interaction/tb4_nav2/**`
- Create: `/home/alex/Interaction/tb4_voice_control/.gitignore`
- Create: `/home/alex/Interaction/tb4_voice_control/LICENSE`
- Create: `/home/alex/Interaction/tb4_voice_control/README.md`
- Create: `/home/alex/Interaction/tb4_voice_control/package.xml`
- Create: `/home/alex/Interaction/tb4_voice_control/setup.py`
- Create: `/home/alex/Interaction/tb4_voice_control/setup.cfg`
- Create: `/home/alex/Interaction/tb4_voice_control/resource/tb4_voice_control`
- Create: `/home/alex/Interaction/tb4_voice_control/tb4_voice_control/__init__.py`
- Create: `/home/alex/Interaction/tb4_voice_control/tb4_voice_control/navigate_goals.py`
- Create: `/home/alex/Interaction/tb4_voice_control/tb4_voice_control/goal_recorder.py`
- Create: `/home/alex/Interaction/tb4_voice_control/launch/tb4_nav2.launch.py`
- Create: `/home/alex/Interaction/tb4_voice_control/launch/tb4_slam.launch.py`
- Create: `/home/alex/Interaction/tb4_voice_control/maps/map.yaml`
- Create: `/home/alex/Interaction/tb4_voice_control/maps/map.pgm`
- Create: `/home/alex/Interaction/tb4_voice_control/config/goals.yaml`
- Create: `/home/alex/Interaction/tb4_voice_control/test/test_navigate_goals.py`
- Create: `/home/alex/Interaction/tb4_voice_control/test/conftest.py`
- Create: `/home/alex/Interaction/tb4_voice_control/test/test_package_identity.py`

**Interfaces:**
- Consumes: the working map, launch files, `navigate_goals.py`, `goal_recorder.py`, and tests from `tb4_nav2`.
- Produces: importable ROS package `tb4_voice_control`; console scripts `navigate_goals` and `record_goal`; unchanged baseline behavior with all package names rewritten.

- [ ] **Step 1: Record baseline source integrity and environment audit**

Run:

```bash
git -C /home/alex/Interaction/tb4_nav2 status --short
git -C /home/alex/Interaction/tb4_nav2 rev-parse HEAD
nvidia-smi
gh auth status -h github.com
```

Expected: source status is clean; save the source commit in the new README. NVIDIA and GitHub checks may fail, but their exact output becomes a Milestone 0 prerequisite record rather than being ignored.

- [ ] **Step 2: Write the failing package identity test**

```python
@pytest.fixture
def project_root():
    return Path(__file__).resolve().parents[1]


def test_package_files_use_new_identity(project_root):
    assert '<name>tb4_voice_control</name>' in (project_root / 'package.xml').read_text()
    assert "package_name = 'tb4_voice_control'" in (project_root / 'setup.py').read_text()
    assert (project_root / 'resource' / 'tb4_voice_control').is_file()


def test_yolo_assets_are_not_copied(project_root):
    assert not (project_root / 'models').exists()
    assert not (project_root / 'notebooks').exists()
    assert not (project_root / 'requirements-yolo.txt').exists()
```

- [ ] **Step 3: Run the identity test and verify it fails before the copy is complete**

Run: `pytest -q test/test_package_identity.py`

Expected: FAIL because the renamed package baseline is not present yet.

- [ ] **Step 4: Copy only the listed baseline files and rewrite package identity**

Do not copy `.git`, `build`, `install`, `log`, `.venv-yolo`, `models`, `notebooks`, `report`, YOLO scripts, YOLO tests, or `yolo_detector.py`. Update `package.xml`, `setup.py`, `setup.cfg`, Python imports, node names, package-share lookups, launch package lookup, and README from `tb4_nav2` to `tb4_voice_control`. Keep `maps/map.pgm`, `maps/map.yaml`, `config/goals.yaml`, both launch files, navigation utilities, and their non-YOLO tests.

- [ ] **Step 5: Run baseline tests and package build**

Run:

```bash
source /opt/ros/humble/setup.bash
pytest -q test/test_package_identity.py test/test_navigate_goals.py
colcon build --base-paths . --packages-select tb4_voice_control --symlink-install
source install/setup.bash
ros2 pkg prefix tb4_voice_control
```

Expected: tests PASS, build succeeds, and prefix ends in `/tb4_voice_control/install/tb4_voice_control`.

- [ ] **Step 6: Initialize the independent repository and commit the baseline**

Run:

```bash
git init -b main
git add .gitignore LICENSE README.md package.xml setup.py setup.cfg resource tb4_voice_control launch maps config test docs
git commit -m "chore: initialize tb4 voice control baseline"
```

Expected: one clean root commit in the new repository; the old repository HEAD and status are unchanged.

- [ ] **Step 7: Create and push the public baseline repository**

Run:

```bash
gh auth status -h github.com
gh auth login -h github.com
gh repo create tb4_voice_control --public --source=. --remote=origin --push
gh repo view --web=false
```

Expected: skip the login command when status is already valid; otherwise complete it interactively. Then create public `tb4_voice_control` under the authenticated account and make local `main` track `origin/main`. The current GitHub CLI token is invalid, so pause here for the user's interactive authentication rather than storing a credential in the repository.

---

## Milestone 1 — Semantic map model and geometry

### Task 2: Implement map metadata, occupancy loading, and coordinate conversion

**Files:**
- Create: `tb4_voice_control/map_model.py`
- Test: `test/test_map_model.py`
- Modify: `package.xml`

**Interfaces:**
- Consumes: ROS map YAML fields `image`, `resolution`, `origin`, `negate`, `occupied_thresh`, `free_thresh`, and mode `trinary`.
- Produces: `MapMetadata`, `OccupancyMap`, `load_occupancy_map(path: Path) -> OccupancyMap`, `pixel_to_ros(pixel: tuple[float, float], metadata: MapMetadata, image_height: int) -> tuple[float, float]`, and `ros_to_pixel(point: tuple[float, float], metadata: MapMetadata, image_height: int) -> tuple[float, float]`.

- [ ] **Step 1: Write failing tests for real-map metadata, relative image resolution, threshold masks, and coordinate round trips**

Tests must assert:

```python
occupancy = load_occupancy_map(Path('maps/map.yaml'))
assert occupancy.image.shape == (1101, 788)
assert occupancy.metadata.resolution == pytest.approx(0.05)
assert occupancy.metadata.origin == pytest.approx((-19.7, -27.5, 0.0))
assert ros_to_pixel(pixel_to_ros((300.25, 700.75), occupancy.metadata, 1101),
                    occupancy.metadata, 1101) == pytest.approx((300.25, 700.75))
```

Add a tiny temporary PGM/YAML fixture for both `negate: 0` and `negate: 1`; assert values above `occupied_thresh` become occupied, below `free_thresh` become free, and middle values remain unknown in `trinary` mode.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest -q test/test_map_model.py`

Expected: FAIL with missing `tb4_voice_control.map_model`.

- [ ] **Step 3: Implement the immutable map model and conversions**

Use these signatures:

```python
@dataclass(frozen=True)
class MapMetadata:
    yaml_path: Path
    image_path: Path
    resolution: float
    origin: tuple[float, float, float]
    negate: bool
    occupied_thresh: float
    free_thresh: float
    mode: str


@dataclass(frozen=True)
class OccupancyMap:
    metadata: MapMetadata
    image: np.ndarray
    free_mask: np.ndarray
    occupied_mask: np.ndarray
    unknown_mask: np.ndarray
```

Reject missing images, nonpositive resolution, malformed origin, unsupported modes, and invalid thresholds with `ValueError` containing the offending field.

- [ ] **Step 4: Run the map tests and full baseline suite**

Run: `pytest -q test/test_map_model.py test/test_navigate_goals.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add package.xml tb4_voice_control/map_model.py test/test_map_model.py
git commit -m "feat: add occupancy map coordinate model"
```

### Task 3: Implement versioned regions, geometry validation, and atomic persistence

**Files:**
- Create: `tb4_voice_control/regions.py`
- Create: `tb4_voice_control/region_validation.py`
- Create: `tb4_voice_control/validate_regions.py`
- Create: `config/regions.yaml`
- Test: `test/test_regions.py`
- Test: `test/test_region_validation.py`
- Modify: `setup.py`

**Interfaces:**
- Consumes: `OccupancyMap` and pixel/ROS conversions from Task 2.
- Produces: `GoalPose`, `Region`, `SemanticMap`, `load_regions(path: Path) -> SemanticMap`, `save_regions(path: Path, document: SemanticMap) -> None`, `ValidationIssue`, `validate_semantic_map(document: SemanticMap, occupancy: OccupancyMap) -> list[ValidationIssue]`, and console script `validate_regions`.

- [ ] **Step 1: Write failing schema and round-trip tests**

Cover `schema_version == 1`, unique IDs, numeric finite goal fields, Unicode names, color channels `0..255`, three-or-more vertices, relative `map.yaml` path, atomic save, and load-save-load equality.

- [ ] **Step 2: Write failing geometry tests**

Assert that validation rejects a self-intersection, goal outside its polygon, goal on occupied/unknown cells, out-of-image vertices, duplicate normalized aliases, and overlapping interiors. Assert that adjacent polygons sharing exactly one edge are valid.

- [ ] **Step 3: Run tests to verify failure**

Run: `pytest -q test/test_regions.py test/test_region_validation.py`

Expected: FAIL with missing region modules.

- [ ] **Step 4: Implement region data and persistence**

Use these signatures:

```python
@dataclass(frozen=True)
class GoalPose:
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    aliases: tuple[str, ...]
    color: tuple[int, int, int]
    polygon_pixels: tuple[tuple[float, float], ...]
    goal: GoalPose


@dataclass(frozen=True)
class SemanticMap:
    schema_version: int
    map_yaml: Path
    frame_id: str
    regions: tuple[Region, ...]
```

Write YAML through a temporary file in the destination directory, then replace the destination atomically. Preserve Unicode and mapping order.

- [ ] **Step 5: Implement geometry validation and the CLI**

Use OpenCV point/polygon primitives for containment. For overlap, rasterize each polygon at map resolution, erode each mask by one pixel to remove its boundary, and reject any intersection of the remaining interiors; this permits a shared edge while rejecting meaningful pixel-area overlap. The CLI exits `0` for a valid file and `2` after printing every issue for an invalid file.

- [ ] **Step 6: Add three initial regions around the existing three Nav2 goals**

Use the editor-independent conversion helpers to locate each existing goal on the map, inspect the occupancy image, and define conservative non-overlapping polygons over free space. Use IDs `zone_a`, `zone_b`, `zone_c`; names `Khu vực A/B/C`. Store canonical aliases only—such as `A`, `khu vực A`, and `phòng thí nghiệm` for the selected laboratory region—then let the parser generate accent-insensitive lookup keys so `phong thi nghiem` works without duplicating the alias in YAML.

- [ ] **Step 7: Run validation and tests**

Run:

```bash
pytest -q test/test_regions.py test/test_region_validation.py
python3 -m tb4_voice_control.validate_regions config/regions.yaml
```

Expected: PASS and `3 valid regions`.

- [ ] **Step 8: Commit**

```bash
git add setup.py config/regions.yaml tb4_voice_control/regions.py tb4_voice_control/region_validation.py tb4_voice_control/validate_regions.py test/test_regions.py test/test_region_validation.py
git commit -m "feat: add semantic region data model"
```

---

## Milestone 2 — Visual Map Editor

### Task 4: Build the editable map canvas and undoable document state

**Files:**
- Create: `tb4_voice_control/editor_document.py`
- Create: `tb4_voice_control/map_canvas.py`
- Test: `test/test_editor_document.py`
- Test: `test/test_map_canvas.py`
- Modify: `package.xml`

**Interfaces:**
- Consumes: `OccupancyMap`, `SemanticMap`, `Region`, and validation interfaces from Tasks 2–3.
- Produces: `EditorDocument` with `add_region`, `update_region`, `delete_region`, `undo`, `redo`; and `MapCanvas(QGraphicsView)` signals `polygon_completed`, `vertex_moved`, `goal_changed`, `selection_changed`, `cursor_position_changed`.

- [ ] **Step 1: Write failing document tests**

Test add/update/delete followed by undo and redo, dirty-state transitions, stable selection by region ID, and no mutation of the frozen source model.

- [ ] **Step 2: Write failing Qt offscreen canvas tests**

With `QT_QPA_PLATFORM=offscreen`, load a tiny map and simulate clicks to close a polygon, select it, move one vertex, place a goal, zoom, and emit pixel/ROS cursor coordinates.

- [ ] **Step 3: Run tests to verify failure**

Run: `QT_QPA_PLATFORM=offscreen pytest -q test/test_editor_document.py test/test_map_canvas.py`

Expected: FAIL with missing editor modules.

- [ ] **Step 4: Implement command-based document history**

Limit history to 100 commands. A command stores only the affected region before/after state; selection and view zoom are not persisted to YAML.

- [ ] **Step 5: Implement `MapCanvas`**

Use a `QGraphicsScene` with the occupancy image at native pixel coordinates, translucent `QGraphicsPolygonItem` overlays, draggable vertex handles, a goal marker plus yaw arrow, and mouse modes `select`, `draw_polygon`, `place_goal`, `pan`. Escape cancels an in-progress draw; Enter or clicking the first vertex closes it.

- [ ] **Step 6: Run tests**

Run: `QT_QPA_PLATFORM=offscreen pytest -q test/test_editor_document.py test/test_map_canvas.py`

Expected: PASS without an X display.

- [ ] **Step 7: Commit**

```bash
git add package.xml tb4_voice_control/editor_document.py tb4_voice_control/map_canvas.py test/test_editor_document.py test/test_map_canvas.py
git commit -m "feat: add editable semantic map canvas"
```

### Task 5: Complete the Map Editor window, validation workflow, and image export

**Files:**
- Create: `tb4_voice_control/map_editor.py`
- Create: `tb4_voice_control/map_render.py`
- Test: `test/test_map_editor.py`
- Test: `test/test_map_render.py`
- Modify: `setup.py`
- Modify: `config/regions.yaml`
- Create: `artifacts/segmented_map.png`

**Interfaces:**
- Consumes: editor document/canvas from Task 4 and semantic validation from Task 3.
- Produces: `MapEditorWindow`, `render_segmented_map(occupancy: OccupancyMap, semantic_map: SemanticMap) -> np.ndarray`, `map_render.main()`, and console scripts `map_editor` and `render_segmented_map`.

- [ ] **Step 1: Write failing window workflow tests**

Test opening a map/regions file, selecting a region, editing ID/name/aliases/color, disabling save on validation errors, focusing the first error, saving a valid document, and prompting on close with unsaved changes.

- [ ] **Step 2: Write failing deterministic render test**

Render a synthetic map twice and assert identical pixels, visible translucent fill, label placement, goal dot, yaw arrow, and unchanged source occupancy array.

- [ ] **Step 3: Run tests to verify failure**

Run: `QT_QPA_PLATFORM=offscreen pytest -q test/test_map_editor.py test/test_map_render.py`

Expected: FAIL with missing modules.

- [ ] **Step 4: Implement `MapEditorWindow`**

Provide toolbar modes, region list with visibility checkboxes, property form, zoom controls, undo/redo, status bar pixel/ROS coordinates, Open, Save, Save As, and Export Image actions. Validate on every property/geometry commit and again before save.

- [ ] **Step 5: Implement deterministic OpenCV export**

Use the stored RGB color, fixed 35% alpha, region name at polygon centroid, and a high-contrast goal/yaw marker. Export without changing `map.pgm`.

- [ ] **Step 6: Run editor tests and export the real artifact**

Run:

```bash
QT_QPA_PLATFORM=offscreen pytest -q test/test_map_editor.py test/test_map_render.py
ros2 run tb4_voice_control render_segmented_map config/regions.yaml artifacts/segmented_map.png
file artifacts/segmented_map.png
```

Expected: tests PASS; output is a PNG at `788 x 1101` with three labeled regions.

- [ ] **Step 7: Commit**

```bash
git add setup.py config/regions.yaml artifacts/segmented_map.png tb4_voice_control/map_editor.py tb4_voice_control/map_render.py test/test_map_editor.py test/test_map_render.py
git commit -m "feat: add visual semantic map editor"
```

---

## Milestone 3 — Deterministic Vietnamese commands

### Task 6: Implement normalization, command parsing, and region route planning

**Files:**
- Create: `tb4_voice_control/command_parser.py`
- Create: `tb4_voice_control/route_planner.py`
- Test: `test/test_command_parser.py`
- Test: `test/test_route_planner.py`

**Interfaces:**
- Consumes: `SemanticMap`, region aliases, and current AMCL `(x, y)` pose.
- Produces: `Intent`, `VoiceCommand`, `normalize_text(text: str, strip_diacritics: bool = False) -> str`, `parse_command(text: str, semantic_map: SemanticMap) -> VoiceCommand`, `find_current_region(point_ros: tuple[float, float], semantic_map: SemanticMap, occupancy: OccupancyMap) -> Region | None`, and `plan_route(command: VoiceCommand, current_region_id: str | None) -> tuple[str, ...]`.

- [ ] **Step 1: Write failing parser tests**

Cover:

```python
assert parse_command('Đi đến khu vực A.', regions).destination_id == 'zone_a'
assert parse_command('di chuyen toi khu b', regions).destination_id == 'zone_b'
assert parse_command('Di chuyển từ A đến B', regions).source_id == 'zone_a'
```

Also assert longest-alias matching, Unicode normalization, punctuation/case/spacing tolerance, unknown region, duplicate normalized alias, missing destination, and multiple conflicting destinations. Errors use typed `CommandError` codes rather than text matching.

- [ ] **Step 2: Write failing route tests**

Assert GO_TO(B) gives `[B]`, GO_TO(B) while already in B gives `[]`, FROM_TO(A, B) outside A gives `[A, B]`, FROM_TO(A, B) inside A gives `[B]`, and a point on a shared boundary is resolved deterministically by treating boundary-only membership as no current region.

- [ ] **Step 3: Run tests to verify failure**

Run: `pytest -q test/test_command_parser.py test/test_route_planner.py`

Expected: FAIL with missing parser/planner modules.

- [ ] **Step 4: Implement the parser**

Use enum values `GO_TO` and `FROM_TO`; patterns recognize `đi|di chuyển`, `đến|tới`, and `từ ... đến|tới ...`. Resolve aliases after the grammar separates source and destination so the letter `A` cannot accidentally match arbitrary text. Do not guess on ambiguity.

- [ ] **Step 5: Implement route planning and current-region lookup**

Convert the ROS point to image pixels and use strict polygon-interior membership. A point only on a boundary returns no region, avoiding arbitrary ownership of shared edges.

- [ ] **Step 6: Run tests and commit**

Run: `pytest -q test/test_command_parser.py test/test_route_planner.py`

Expected: PASS.

```bash
git add tb4_voice_control/command_parser.py tb4_voice_control/route_planner.py test/test_command_parser.py test/test_route_planner.py
git commit -m "feat: parse Vietnamese region commands"
```

---

## Milestone 4 — Nav2 route execution

### Task 7: Extract a testable route executor and implement the Nav2 backend

**Files:**
- Create: `tb4_voice_control/route_executor.py`
- Create: `tb4_voice_control/nav2_backend.py`
- Test: `test/test_route_executor.py`
- Test: `test/test_nav2_backend.py`
- Modify: `tb4_voice_control/navigate_goals.py`

**Interfaces:**
- Consumes: ordered `Region` objects from Task 6 and the existing Nav2 readiness/pose logic.
- Produces: `NavigationBackend` protocol, `RouteState`, `LegProgress`, `RouteExecutor.start(region_ids: tuple[str, ...]) -> bool`, `RouteExecutor.cancel() -> None`, `BasicNavigatorBackend`, status callback, and current-pose callback.

- [ ] **Step 1: Write failing pure executor tests with a fake backend**

Test ordered execution, per-leg progress, stop-on-reject, stop-on-timeout, cancel, empty route, and refusal of a second `start()` while state is `RUNNING`. After success/failure/cancel, assert a later command can start.

- [ ] **Step 2: Write failing backend mapping tests**

With stubs for `BasicNavigator`, assert region goal `(x, y, yaw)` becomes a `PoseStamped` in frame `map`, readiness checks AMCL/lifecycle/action availability, feedback is mapped to `LegProgress`, and an unavailable dependency sends no goal.

- [ ] **Step 3: Run tests to verify failure**

Run: `pytest -q test/test_route_executor.py test/test_nav2_backend.py`

Expected: FAIL with missing executor/backend modules.

- [ ] **Step 4: Implement the pure route state machine**

Keep Qt and ROS imports out of `route_executor.py`. Use a `threading.Event` for cancellation and callbacks for state/progress; guard start/cancel transitions with a lock.

- [ ] **Step 5: Extract and implement `BasicNavigatorBackend`**

Move reusable readiness, pose conversion, timeout, and feedback behavior out of `navigate_goals.py`; retain its CLI by making it call the same backend. Preserve Ctrl+C cancellation and exit codes.

- [ ] **Step 6: Run navigation tests and commit**

Run: `pytest -q test/test_route_executor.py test/test_nav2_backend.py test/test_navigate_goals.py`

Expected: PASS.

```bash
git add tb4_voice_control/route_executor.py tb4_voice_control/nav2_backend.py tb4_voice_control/navigate_goals.py test/test_route_executor.py test/test_nav2_backend.py test/test_navigate_goals.py
git commit -m "feat: execute semantic routes through Nav2"
```

---

## Milestone 5 — GPU speech and Voice Runtime UI

### Task 8: Add isolated push-to-talk recording and faster-whisper transcription

**Files:**
- Create: `requirements-speech.txt`
- Create: `scripts/setup_speech_venv.sh`
- Create: `scripts/run_voice_control.sh`
- Create: `config/voice.yaml`
- Create: `tb4_voice_control/audio_capture.py`
- Create: `tb4_voice_control/speech.py`
- Test: `test/test_audio_capture.py`
- Test: `test/test_speech.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: microphone audio at 16 kHz mono and configuration `model_size`, `device`, `compute_type`, `language`.
- Produces: `AudioRecorder.start()`, `AudioRecorder.stop() -> np.ndarray`, `TranscriptionResult(text: str, language: str, duration_seconds: float)`, and `WhisperTranscriber.transcribe(samples: np.ndarray, sample_rate: int) -> TranscriptionResult`.

- [ ] **Step 1: Write failing recorder tests with a fake sounddevice stream**

Assert start/stop lifecycle, 16 kHz mono float32 concatenation, refusal to stop before start, maximum recording duration, and visible `AudioDeviceError` when no input device opens.

- [ ] **Step 2: Write failing transcriber tests with a fake Whisper model**

Assert lazy model load, exact configuration `small/CUDA/float16/vi`, segment concatenation, empty transcript handling, and typed `SpeechModelError` without invoking parser/Nav2 when model initialization fails.

- [ ] **Step 3: Run tests to verify failure**

Run: `pytest -q test/test_audio_capture.py test/test_speech.py`

Expected: FAIL with missing audio/speech modules.

- [ ] **Step 4: Implement audio and speech adapters**

Do not import `faster_whisper` until the first transcription, so non-speech tests and Map Editor work without the speech environment. Default configuration:

```yaml
sample_rate: 16000
max_record_seconds: 15
model_size: small
device: cuda
compute_type: float16
language: vi
```

- [ ] **Step 5: Implement reproducible speech environment scripts**

`setup_speech_venv.sh` creates `.venv-speech` with `--system-site-packages`, installs `requirements-speech.txt`, checks `sounddevice`, imports `faster_whisper`, and prints a final CUDA preflight command. `run_voice_control.sh` sources ROS, `install/setup.bash`, activates the venv, then runs `ros2 run tb4_voice_control voice_control`.

- [ ] **Step 6: Run adapter tests and commit**

Run: `pytest -q test/test_audio_capture.py test/test_speech.py`

Expected: PASS without requiring a physical microphone or model download.

```bash
git add .gitignore requirements-speech.txt scripts/setup_speech_venv.sh scripts/run_voice_control.sh config/voice.yaml tb4_voice_control/audio_capture.py tb4_voice_control/speech.py test/test_audio_capture.py test/test_speech.py
git commit -m "feat: add CUDA Whisper push-to-talk adapters"
```

### Task 9: Build the Voice Runtime UI and integrate the full command pipeline

**Files:**
- Create: `tb4_voice_control/runtime_controller.py`
- Create: `tb4_voice_control/qt_workers.py`
- Create: `tb4_voice_control/voice_app.py`
- Test: `test/test_runtime_controller.py`
- Test: `test/test_voice_app.py`
- Modify: `setup.py`
- Modify: `package.xml`

**Interfaces:**
- Consumes: audio/transcriber from Task 8, parser/planner from Task 6, route executor from Task 7, and `config/regions.yaml`.
- Produces: `RuntimeController.process_text(text: str) -> None`, `SpeechWorker`, `NavigationWorker`, `VoiceControlWindow`, and console script `voice_control`.

- [ ] **Step 1: Write failing controller integration tests with all external adapters faked**

Assert transcript → command → route → executor flow; unknown/ambiguous/empty input sends zero goals; current region changes FROM_TO route; active route rejects a second text command; cancel returns to idle; model/microphone/Nav2 errors remain visible and send zero goals.

- [ ] **Step 2: Write failing Qt offscreen UI tests**

Assert the window displays connection/GPU state, transcript, parsed intent, route queue, current leg/progress, success/error, and valid region names. Simulate press/release of “Giữ để nói”; while navigating, assert record/text controls are disabled and Cancel is enabled; after cancel/completion, assert controls re-enable.

- [ ] **Step 3: Run tests to verify failure**

Run: `QT_QPA_PLATFORM=offscreen pytest -q test/test_runtime_controller.py test/test_voice_app.py`

Expected: FAIL with missing runtime modules.

- [ ] **Step 4: Implement the UI-independent runtime controller**

Expose callbacks/signals for transcript, command, route, state, progress, and error. Accept text input as a diagnostic path through the exact same parser/planner/Nav2 pipeline as a transcript.

- [ ] **Step 5: Implement Qt workers and `VoiceControlWindow`**

Run transcription and route execution in dedicated `QThread` workers. Never update widgets from worker threads; use Qt signals. Closing the window cancels an active route, joins workers with a bounded timeout, and shuts down ROS once.

- [ ] **Step 6: Register the console entry point and run tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen pytest -q test/test_runtime_controller.py test/test_voice_app.py
source /opt/ros/humble/setup.bash
colcon build --base-paths . --packages-select tb4_voice_control --symlink-install
```

Expected: tests and build PASS.

- [ ] **Step 7: Commit**

```bash
git add setup.py package.xml tb4_voice_control/runtime_controller.py tb4_voice_control/qt_workers.py tb4_voice_control/voice_app.py test/test_runtime_controller.py test/test_voice_app.py
git commit -m "feat: add voice navigation runtime UI"
```

---

## Milestone 6 — End-to-end proof, documentation, and final public delivery

### Task 10: Package launch/config assets and prove all required scenarios

**Files:**
- Create: `launch/voice_navigation.launch.py`
- Create: `docs/DEMO.md`
- Create: `docs/TEST_MATRIX.md`
- Create: `docs/evidence/` runtime logs and screenshots without private audio
- Create: `report/BAO_CAO_BAI_7.html`
- Create: `report/BAO_CAO_BAI_7.pdf`
- Modify: `README.md`
- Modify: `setup.py`
- Modify: `package.xml`
- Test: `test/test_install_assets.py`

**Interfaces:**
- Consumes: all previous tasks plus real TurtleBot 4 simulation, microphone, NVIDIA GPU, and GitHub authentication.
- Produces: installed maps/config/launch/artifacts, documented start commands, evidence for each acceptance criterion, short PDF report, and public GitHub repository.

- [ ] **Step 1: Write the failing installed-assets test**

Assert `setup.py` installs launch, maps, config, artifacts, and resource files; assert the `navigate_goals`, `record_goal`, `validate_regions`, `map_editor`, `render_segmented_map`, and `voice_control` console entry points exist; assert README includes prerequisites, build, Map Editor, CUDA speech setup, Nav2 startup, voice demo, error recovery, and repository structure.

- [ ] **Step 2: Run the test to verify failure**

Run: `pytest -q test/test_install_assets.py`

Expected: FAIL until every required asset and document is declared.

- [ ] **Step 3: Implement launch and packaging**

`voice_navigation.launch.py` starts/reuses the TurtleBot 4 warehouse Nav2 baseline and starts `voice_control` with `regions_file`, `voice_config`, and `use_sim_time` arguments. Do not start a second simulator/Nav2 instance when the user chooses `start_nav2:=false`.

- [ ] **Step 4: Run the complete automated proof**

Run:

```bash
source /opt/ros/humble/setup.bash
pytest -q
colcon build --base-paths . --packages-select tb4_voice_control --symlink-install
colcon test --base-paths . --packages-select tb4_voice_control --event-handlers console_direct+
colcon test-result --verbose
```

Expected: all pytest/ament tests PASS, build PASS, zero failed colcon tests.

- [ ] **Step 5: Resolve hardware prerequisites and prove CUDA speech**

Run:

```bash
nvidia-smi
./scripts/setup_speech_venv.sh
./scripts/run_voice_control.sh
```

Expected: NVIDIA GPU and driver are visible; Whisper reports `device=cuda`, model `small`, compute type `float16`; three Vietnamese phrases transcribe to the intended region aliases. If `nvidia-smi` still fails, stop and repair the driver/runtime before claiming Milestone 5 complete.

- [ ] **Step 6: Perform the simulation acceptance matrix**

Record evidence for:

1. Map Editor shows and edits three labeled regions, then reloads them.
2. “Đi đến khu vực A” reaches A.
3. “Đi đến phòng thí nghiệm” reaches the region carrying that alias.
4. “Di chuyển từ khu vực A đến khu vực B” visits A then B when outside A.
5. The same FROM_TO command sends only B when already inside A.
6. A nonexistent region shows an error and sends no goal.
7. A new command is disabled during navigation; Cancel stops the active route.
8. Nav2 replans around a simulation obstacle.

Save timestamped terminal logs and screenshots in `docs/evidence/`; put the video recording checklist in `docs/DEMO.md` rather than committing a large video unless explicitly desired.

- [ ] **Step 7: Complete README and the 1–2 page report**

The report must include objective, manual polygon segmentation and pixel/ROS formula, faster-whisper CUDA pipeline, deterministic command grammar, Nav2 integration, one segmented-map figure, test table, limitations, and results. Keep the source as print-styled HTML, then generate and verify the PDF:

```bash
libreoffice --headless --convert-to pdf --outdir report report/BAO_CAO_BAI_7.html
file report/BAO_CAO_BAI_7.pdf
```

Expected: a readable 1–2 page PDF.

- [ ] **Step 8: Re-run the complete proof and commit deliverables**

Run the commands from Step 4 again.

Expected: PASS after documentation/packaging changes.

```bash
git add README.md package.xml setup.py launch docs report artifacts config maps scripts requirements-speech.txt resource tb4_voice_control test
git commit -m "docs: complete TurtleBot 4 voice navigation demo"
git status --short
```

Expected: clean working tree.

- [ ] **Step 9: Push final evidence and verify the public repository**

Run:

```bash
git push origin main
gh repo view --web=false
```

Expected: the public repository created in Task 1 shows the final `main`, required files, report PDF, and a clean README landing page.

---

## Milestone 7 — Optional multi-waypoint extension

### Task 11: Parse ordered “qua … rồi đến …” waypoints without changing the executor

**Files:**
- Modify: `tb4_voice_control/command_parser.py`
- Modify: `tb4_voice_control/route_planner.py`
- Modify: `tb4_voice_control/voice_app.py`
- Modify: `test/test_command_parser.py`
- Modify: `test/test_route_planner.py`
- Modify: `docs/DEMO.md`

**Interfaces:**
- Consumes: the existing ordered route interface from Task 7.
- Produces: a `MULTI_STOP` command carrying ordered region IDs; route executor remains unchanged.

- [ ] **Step 1: Write failing multi-stop tests**

Assert “Đi từ phòng A qua hành lang C rồi đến phòng B” parses as `[A, C, B]`; when already in A, planned route is `[C, B]`; repeated adjacent regions collapse; unknown or ambiguous intermediate regions fail without sending goals.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest -q test/test_command_parser.py test/test_route_planner.py`

Expected: FAIL because multi-stop grammar is not implemented.

- [ ] **Step 3: Implement only the grammar and route display changes**

Reuse existing alias resolution and `RouteExecutor`; do not add another navigation path.

- [ ] **Step 4: Run full tests and commit**

Run: `QT_QPA_PLATFORM=offscreen pytest -q`

Expected: PASS.

```bash
git add tb4_voice_control/command_parser.py tb4_voice_control/route_planner.py tb4_voice_control/voice_app.py test/test_command_parser.py test/test_route_planner.py docs/DEMO.md
git commit -m "feat: support spoken multi-stop routes"
```

