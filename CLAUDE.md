# CLAUDE.md — Dr. Milton's Surgical Navigation Project

This file provides instructions for Claude when working on this specific project. Keep it short and focused. The detailed technical knowledge lives in the three skills:

- `surgical-navigation-aruco`: technical knowledge about ArUco tracking, pose estimation, bundle adjustment
- `slicer-igt-workflow`: 3D Slicer + SlicerIGT specific knowledge
- `surgical-nav-project-context`: this specific project's setup, file structure, decisions

## Project Description

Surgical navigation system for orthopedic spine surgery. Tracks instruments and patient anatomy with optical (ArUco) markers and visualizes spatial coherence in 3D Slicer. Currently in iteration 2 (replication with improvements).

## Working Style Preferences

### Communication

- Respond in **Spanish** (the user prefers Spanish).
- Be direct and honest, including about uncertainty.
- Don't over-apologize when something doesn't work; focus on diagnosis and fix.
- Push back on assumptions if data suggests otherwise.

### Technical approach

- **Validate quantitatively at each step.** Don't accept "it looks good" as success criteria.
- **One change at a time** when debugging. Don't change multiple things and hope.
- **Diagnostic scripts before fixes.** Inspect what's actually happening before guessing.
- **Hard-won lessons from iteration 1**: see the project-context skill.

### Code style

- Python scripts go in `C:\Dev\PoyectoNavegacion\codigo\`.
- Use venv at `.venv\`.
- Comments in Spanish when explaining decisions, English in code is fine.
- Save outputs (transforms, captures) with descriptive names + metadata.

## Common Commands

```powershell
# Activate environment
cd C:\Dev\PoyectoNavegacion\codigo
.\.venv\Scripts\activate

# Run main tracker (multi-marker)
python tracker.py --config tracker_config.yaml

# Capture dataset for bundle adjustment
python captura_calibracion.py --duracion 60

# Run bundle adjustment
python calibrar_rigid_body.py --max_frames 300

# Pivot calibration
python test_pivote.py --duracion 45
```

## Critical Project-Specific Things to Remember

1. **Use `reference_dodecaedro_calibrado.txt`**, NOT theoretical, after bundle adjustment.
2. **Slicer hierarchy for paired-point registration** is documented in `slicer-igt-workflow` skill — follow it exactly.
3. **Iteration 2 uses marker IDs 1-11**, not 151-161 from iteration 1. Marker 0 is still for the bone reference.
4. **Camera config**: MSMF backend + MJPG codec, otherwise FPS drops to 5.
5. **Don't send video** through pyigtl (set `send_video: false`), it kills performance.

## When the User Says "Continue"

The user typically resumes work mid-task. To handle this:

1. Read the latest files in `C:\Dev\PoyectoNavegacion\codigo\` to understand current state.
2. Check the project-context skill for the typical workflow.
3. Ask one clarifying question if state is ambiguous, then proceed.

## What Has Been Achieved (Reference State)

Iteration 1 final metrics:
- Tracking: 28-30 FPS stable
- Pivot calibration std: 1.7 mm
- Reproducibility: <1 mm in X-Y
- Registration RMS: 3.46 mm
- Visual spatial coherence: working in 3D Slicer

Iteration 2 goal: reproduce this in <6 hours, achieve <2 mm RMS.

## Important Files to Know About

- `tracker.py` — main tracking pipeline (multi-marker rigid body support)
- `tracker_config.yaml` / `tracker_config_v2.yaml` — configuration
- `data/reference_dodecaedro*.txt` — rigid body geometry files
- `StylusTipToDodecaedro.h5` — current pivot calibration loaded in Slicer
- See `surgical-nav-project-context` skill for complete file structure.
