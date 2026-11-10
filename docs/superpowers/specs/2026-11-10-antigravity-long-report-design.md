# Bài thực hành 7 Long-form Report Design

## Intent

Create a detailed Vietnamese LaTeX report for Bài thực hành 7, using the same
UET/TurtleBot 4 visual style as the previous submissions. The report may be
long; the earlier 1–2 page limit is explicitly superseded by the student's
instruction on 2026-11-10.

## Audience and output

- Audience: the course instructor and teaching staff.
- Author metadata: reuse the existing UET template values for Thân Thế Trí
  Dũng, MSSV 23020730, class QH-2023-I/CQ-E-RE, unless the user later edits
  them.
- Output directory:
  `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/`.
- Primary deliverables: editable LaTeX sources, image checklist, build/readme
  instructions, references, and a compiled PDF when the local TeX toolchain is
  available.

## Reference template

Use the structure, typography, title-page style, logo, code blocks, figure
placeholder macro, and Vietnamese conventions from:

`/home/alex/Interaction/Universal_Robots_ROS2_GZ_Simulation/deliverables/Bao_cao_TurtleBot4_SLAM_Nav2_23020730/`

The reference is read-only. Copy only reusable assets and rewrite all technical
content for this project. Do not overwrite or edit the previous report.

## Required content

1. Title page and assignment objectives.
2. Overall architecture: map/UI → semantic regions → microphone → Gemini →
   command parser → route executor → Nav2.
3. Manual and semi-automatic map segmentation rationale for rooms, corridors,
   and open spaces.
4. Map Editor UI workflow: polygons, labels/aliases, valid goals, save/reload,
   and segmented-map export.
5. Pixel-to-ROS coordinate relation using `map.yaml`, plus the actual three
   region IDs/names/goals from `config/regions.yaml`.
6. Vietnamese speech pipeline using `gemini-3.5-transcribe`, mono 16 kHz WAV,
   push-to-talk, secure environment-variable configuration, response decoding,
   timeout/error handling, and the reason local NVIDIA inference was removed.
7. Command parsing for GO_TO, FROM_TO, aliases such as “phòng thí nghiệm”,
   nonexistent regions, route sequencing, cancellation, and Nav2
   `NavigateToPose` execution.
8. Installation, build, launch, map-editing, region-reselection, and testing
   commands drawn from the current repository.
9. Verified automated evidence from merged `main`: 317 pytest passed,
   12 skipped, two inherited warnings; 11 explicit SDK acceptance tests passed;
   colcon reported 329 tests, zero errors/failures, 12 skipped.
10. Live diagnostic history may state that the dedicated model returned a
    specialized response in roughly 3.2 seconds, but must explicitly say this
    did not establish Vietnamese transcript accuracy.
11. A manual-acceptance table covering three voice commands, invalid region,
    editor save/reload, multi-leg routing, cancellation, obstacle avoidance,
    public GitHub URL, and demo video.
12. Conclusion, limitations, future work, and references.

## Evidence policy

- Never invent a transcript, navigation success, latency measurement, UI
  screenshot, public URL, or video result.
- Label every unverified live item with the existing `\pending` macro and an
  exact instruction for replacing it after testing.
- Automated test results may be stated as completed because they were verified
  on merged `main`.
- Do not include any API key, credential-shaped token, captured WAV, private
  conversation text, or unpublished video in the report directory.
- Historical Whisper/CUDA material may be discussed only as an architectural
  decision history, not as evidence for the final Gemini runtime.

## Figures

Include the existing `artifacts/segmented_map.png` as verified project output.
Create placeholders for the original occupancy map visualization, Map Editor,
Voice Control UI, recognized commands, invalid-region handling, RViz route,
multi-leg route, and obstacle avoidance. Every placeholder must name the exact
future file and what evidence the screenshot must show.

## Chosen approach

Use the full multi-section LaTeX report pattern from the previous TurtleBot 4
submission. A condensed 1–2 page report and a Markdown-first report were
rejected because the user explicitly requested the familiar long-form format
and removed the page limit.

## Acceptance

- LaTeX sources are structurally complete and compile without fatal errors when
  the required TeX packages are installed.
- The report is internally consistent with current project files and merged
  test evidence.
- Pending live items remain visibly pending and cannot be mistaken for passes.
- No secrets or private audio are present.
- The report does not alter application source code or project configuration.

