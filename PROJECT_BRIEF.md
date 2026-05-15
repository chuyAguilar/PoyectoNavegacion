# Project Brief — Dr. Milton's Surgical Navigation System

**Copy this as the "Project Instructions" when creating the new Project in Cowork.**

---

## Project Overview

I'm working on a surgical navigation system for orthopedic spine surgery. The system tracks surgical instruments and patient anatomy using optical ArUco markers and a webcam, then visualizes the spatial coherence in 3D Slicer (medical imaging software).

The goal is to make a 3D model of the patient's bone appear correctly aligned with the physical bone, so that when I move a tracked stylus, I see in real-time where its tip is relative to the model.

## Hardware

- USB webcam (SVPRO, AR0234 sensor, 640x480 @ 30 FPS)
- 3D-printed bone phantom (spine vertebra with cylindrical features)
- 3D-printed dodecahedron stylus with 11 ArUco markers as rigid body
- Single ArUco marker (ID 0) glued to bone phantom
- Puluz light box for controlled illumination

## Software Stack

- Python 3.11 + OpenCV 4.13 + scipy + pyigtl (custom tracking pipeline)
- 3D Slicer 5.4 + SlicerIGT (visualization and registration)
- OpenIGTLink protocol (port 18944) for communication

## Project Status

**Iteration 1** (completed in 4 days):
- Built working pipeline from scratch
- Sub-2mm pivot calibration
- 3.46 mm RMS for paired-point registration
- Visual spatial coherence demonstrated

**Iteration 2** (current):
- Replicate the system to consolidate learning
- Migrate marker IDs from 151-161 to 1-11 (cleaner numbering)
- Validate procedure at each step
- Reduce replication time from 4 days to ~6 hours
- Improve registration RMS to <2 mm

## Workspace

- Code location: `C:\Dev\PoyectoNavegacion\codigo\`
- Python venv: `.venv\` inside that folder
- Output files: same folder (transforms, captures, calibrations)
- 3D Slicer runs as separate desktop application

## Available Skills

I've installed three custom skills for this project:

1. **surgical-navigation-aruco**: technical knowledge about ArUco tracking, IPPE_SQUARE, multi-marker rigid bodies, bundle adjustment, pivot calibration
2. **slicer-igt-workflow**: 3D Slicer + SlicerIGT specific workflows, transformation hierarchies, paired-point registration procedure
3. **surgical-nav-project-context**: this project's specific file structure, conventions, current state, historical decisions

## How I Work

- I respond best to **direct, honest** communication.
- I prefer **Spanish** for our conversations.
- I value **quantitative validation** at each step, not just visual inspection.
- I sometimes resume work mid-task — read recent files to understand state.
- I may have 3D Slicer open on the side; you can't directly control it, but you can:
  - Generate Python scripts I paste into Slicer's Python console
  - Read Slicer scene files (.mrml) from disk if needed
  - Suggest UI steps for me to do manually

## What I Need from You

1. **Maintain technical rigor** — don't accept "looks good" as validation.
2. **Diagnose before fixing** — inspect data before proposing changes.
3. **Reference the skills** — when in doubt about ArUco tracking or Slicer specifics, the skills have detailed knowledge.
4. **Be honest about uncertainty** — if you're not sure, say so.
5. **Help me think through trade-offs** — when there are multiple approaches, lay them out.

## Current Working State

See files in the project folder. The latest reference geometry is `data/reference_dodecaedro_calibrado.txt` (iteration 1, IDs 151-161). For iteration 2, new files are being prepared with IDs 1-11.

The skill `surgical-nav-project-context` has the complete file structure and current metrics.

---

## First Things to Do When You Start

1. Read the contents of `C:\Dev\PoyectoNavegacion\codigo\` to understand current state.
2. Check which iteration we're in (iter 1 = IDs 151-161, iter 2 = IDs 1-11).
3. Ask me what we're working on today.
