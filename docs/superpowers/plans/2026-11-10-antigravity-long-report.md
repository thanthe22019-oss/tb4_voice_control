# Bài thực hành 7 Long-form Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a detailed Vietnamese LaTeX report for the completed Bài thực hành 7 codebase while keeping unverified live results explicitly pending.

**Architecture:** Reuse the read-only UET/TurtleBot 4 LaTeX template as a visual scaffold, then rewrite the content into focused files for segmentation, semantic mapping, Gemini speech, command routing, Nav2, verification, and demo evidence. Verified repository artifacts are embedded; live screenshots and results use named placeholders until the user performs acceptance testing.

**Tech Stack:** LaTeX/pdfLaTeX, Vietnamese T5 fonts, TikZ, longtable, repository Markdown/YAML/Python evidence, Antigravity CLI

**Spec:** `docs/superpowers/specs/2026-11-10-antigravity-long-report-design.md`

## Global Constraints

- Write in Vietnamese and preserve the established UET/TurtleBot 4 visual style.
- The report may be long; do not enforce the obsolete 1–2 page limit.
- Treat the previous report directory as read-only and write only under `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/` plus the Antigravity task artifact.
- Do not modify ROS/Python application source, configuration, maps, tests, or existing artifacts.
- State only verified automated results; mark every unverified live result with `\pending`.
- Never copy or print API keys, captured WAV files, conversation text, or private credentials.
- Keep GitHub and video links as explicit placeholders until real public URLs exist.

## Review Focus

- The stale branch/worktree wording in `PROJECT_STATUS.md` must not appear as current report status; verify current facts from `git` and the merged evidence sections.
- The 3.2-second diagnostic must not be described as successful Vietnamese recognition; retain the accuracy limitation.
- Historical CUDA/Whisper work must not be presented as the final runtime provider.
- Automated skip/warning counts must be explained and never converted into failures or live passes.
- Figure placeholders must remain compilable when screenshots are absent and must name exact evidence to capture.

---

### Task 1: Create the report scaffold

**Files:**
- Create: `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/main.tex`
- Create: `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/preamble.tex`
- Create: `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/references.bib`
- Create: `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/Logo_UET.png`
- Create: `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/images/README.md`
- Create: `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/*.tex`

**Interfaces:**
- Consumes: the read-only previous TurtleBot 4 report template named in the spec.
- Produces: a compilable multi-file LaTeX skeleton with `\reportfigure` and `\pending` macros.

- [ ] Create an Antigravity task artifact containing all tasks in this plan.
- [ ] Copy only reusable template assets and rewrite title metadata/task title for Bài thực hành 7.
- [ ] Define content files for objectives/architecture, segmentation/editor, semantic map, Gemini speech, parser/Nav2, operation, verification, demo results, and conclusion/references.
- [ ] Run pdfLaTeX once; resolve structural, package, encoding, and missing-file fatal errors while allowing named image placeholders.

### Task 2: Write the technical chapters from repository evidence

**Files:**
- Modify: `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/*.tex`
- Create: `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/images/segmented_map.png`

**Interfaces:**
- Consumes: `README.md`, `PROJECT_STATUS.md`, `docs/DEMO.md`, `docs/TEST_MATRIX.md`, `config/regions.yaml`, `config/voice.yaml`, `maps/map.yaml`, Python source boundaries, and `artifacts/segmented_map.png`.
- Produces: technically accurate Vietnamese chapters and one verified segmented-map figure.

- [ ] Explain the manual/semi-automatic segmentation design and why polygon editing works for both rooms and open spaces.
- [ ] Document the editor workflow and actual semantic region table, including IDs, aliases, and goal poses.
- [ ] Explain pixel/world coordinates using the map metadata without inventing map measurements.
- [ ] Document the final Gemini-only pipeline, privacy boundary, specialized-response decoding, and actionable errors.
- [ ] Document command parsing, multi-leg route rules, unknown-region rejection, cancellation, and Nav2 execution.
- [ ] Include exact operator commands from the repository, checking paths/model names against current files.

### Task 3: Write results, pending evidence, and submission guidance

**Files:**
- Modify: `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/*.tex`
- Create: `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/HUONG_DAN.md`
- Create: `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/HUONG_DAN_CHUP_ANH.md`

**Interfaces:**
- Consumes: verified counts and pending matrix from Task 2 source documents.
- Produces: automated-results table, manual-acceptance table, exact screenshot checklist, public-link placeholders, limitations, and conclusion draft.

- [ ] Record only the merged automated proof: 317 pytest passed/12 skipped/two inherited warnings, 11 SDK acceptance passed, and colcon 329/0/0/12.
- [ ] Describe the 3.2-second diagnostic as response-contract evidence only, with transcript accuracy pending.
- [ ] Add `\pending` rows for editor live proof, three Vietnamese commands, invalid region, multi-leg routing, cancellation, obstacle avoidance, GitHub, and video.
- [ ] Create exact screenshot filenames and capture instructions; do not fabricate images.
- [ ] Draft the conclusion so verified implementation is distinguished from pending operational acceptance.

### Task 4: Compile and audit the deliverable

**Files:**
- Modify only report files created by Tasks 1–3.

**Interfaces:**
- Consumes: complete report source.
- Produces: compiled PDF if the toolchain exists, clean logs, and an auditable handoff.

- [ ] Run pdfLaTeX twice with `-interaction=nonstopmode -halt-on-error`; if unavailable, record the exact missing package/tool instead of claiming compilation.
- [ ] Inspect the log for undefined controls/references and fix report-local issues.
- [ ] Confirm all missing live screenshots render as intentional placeholders.
- [ ] Run `git diff --check` and a literal credential-prefix scan excluding `.git`, `.venv-speech`, build outputs, and Antigravity task artifacts.
- [ ] Search for unsupported claims such as completed live navigation, recognized Vietnamese transcripts, or public links; replace them with `\pending` where evidence is absent.
- [ ] Report created files, PDF path/page count if built, remaining placeholders, and the exact next actions for the user.

