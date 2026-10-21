# bambu-3mf

![Eight STL parts built into a two-plate P2S project, opened and sliced in Bambu Studio, then reviewed](docs/demo.gif)

Give Claude Code your STL parts and get Bambu Studio projects (`.3mf`) that open ready to print: the printer's real
start G-code, speeds and filament data, settings for each part chosen from what that part does, and the time and
weight of every plate. Bambu Studio's own command line writes, checks and slices each project. Left to itself, that
command line writes 500 mm/s² acceleration, filament density 0 and a Cool Plate into the file; the skill flattens the
system profiles first so it does not.

Built for the **Bambu Lab P2S**; also builds and slices for the X1 Carbon, P1S, A1, A1 mini, H2S, H2D and X2D.

Checking a 3MF you already have needs no Claude: `python3 scripts/review_3mf.py part.3mf` prints the settings the
GUI will print with, flags what to look at, and slices it.

The skill's documents (`SKILL.md`, `references/`) are written in Korean. Technical terms and every setting key are
left in English. The Python module and its docstrings are in English.

## What it does

- **Projects from real profiles.** The system profiles (`inherits` chain and `include` templates) are flattened
  and narrowed to the printer's own hotend before they go to the CLI. The project file then carries the printer's
  real start G-code, speeds and filament data. Studio's CLI otherwise falls back to its defaults: 500 mm/s²
  acceleration, filament density 0, Cool Plate.
- **Settings the GUI keeps.** Changed process keys are listed in `different_settings_to_system`, so Bambu Studio
  shows them as changes on top of the system preset instead of resetting them.
- **Per-part control.** Orientation (`down`, `turn`), per-object settings, multi-part / multi-colour objects,
  fixed or arranged placement, the prime tower position, and the left or right nozzle on two-nozzle printers.
- **Checks before writing.** The build stops if the studio repaired or dropped triangles, if a global-only key was
  set on an object, if a process key is misspelled, if a filament cannot stick to the chosen plate, or if a plate
  does not slice. On success it prints each plate's time, weight and filament length.
- **Settings from what each part does.** Before any setting, each part gets a card: what it carries, how it is
  loaded, what mates with it (self-tapping screws, press-fit pockets, snaps, faces on the bed), and where it works
  (heat, outdoors, in the hand). Material, walls, infill, support, brim and orientation follow from the card.
  `Part.role` keeps the card's summary next to the settings in the build report. P2S profile values and rules
  of thumb are in `references/print-settings.md`.
- **Review of existing projects.** `scripts/review_3mf.py` reads any `.3mf` the way the GUI does: the system
  preset plus the listed changes, each object's own settings and footprint, and a slice with the flattened
  system profiles. It flags plates the printer does not take, keys an object cannot hold, repaired meshes,
  tall parts on narrow brims, and support turned off over downward faces.
- **Internals.** Project-file structure, the CLI's assemble list, and the pitfalls found on the way are in
  `references/3mf-internals.md`.

## Install

As a Claude Code plugin:

```
/plugin install bambu-3mf --marketplace woolimi/bambu-3mf
```

Before Claude Code 2.1.275, add the marketplace first:

```
/plugin marketplace add woolimi/bambu-3mf
/plugin install bambu-3mf@bambu-3mf
```

Or as a plain skill:

```bash
git clone https://github.com/woolimi/bambu-3mf ~/.claude/skills/bambu-3mf
```

Requirements:
- Bambu Studio. Tested with 2.08.03 on macOS. On Linux, extract the AppImage with `--appimage-extract`.
- Python 3.9+ with `numpy`.

## Use

Ask Claude Code for a 3MF of your printed parts ("make a 3MF of these parts", "출력 파일 만들어줘") or for a
review of one ("review this 3MF", "이 3MF 검토해줘"), or run the review from a clone of this repo:

```bash
python3 bambu-3mf/scripts/review_3mf.py print/*.3mf
```

To write projects from your own build:

1. Copy `templates/bambu3mf.py` and `templates/make_3mf.py` into your repo's `scripts/`.
2. Add `studio`, `studio_profiles` and `print` paths to your `config.py` (`SKILL.md` §1 has the snippet).
3. Describe your projects in `make_3mf.py`.
4. Run `python scripts/make_3mf.py`.

```python
from pathlib import Path
from bambu3mf import Filament, Part, Plate, Project, Studio, build, report

studio = Studio(Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"),
                Path("/Applications/BambuStudio.app/Contents/Resources/profiles/BBL"))
project = Project(
    plates=[Plate("parts", [
        Part(Path("print/bracket.stl"), down=(0, 0, -1)),
        Part(Path("print/jaw.stl"), down=(1, 0, 0), params={"brim_type": "outer_only", "brim_width": "5"}),
    ])],
    filaments=[Filament("Bambu PLA Basic @BBL P2S", "#FFFFFF")],
    process={"wall_loops": "4", "sparse_infill_density": "20%", "sparse_infill_pattern": "gyroid"},
)
out = Path("print/parts.3mf")
report(out, project, build(project, studio, out))
```

The defaults are a P2S with a 0.4 mm nozzle, `0.20mm Standard @BBL P2S` and the Textured PEI plate. Set `printer`,
`base_process` and the filament presets for another printer.

| Tested (0.4 nozzle, build and slice through the CLI) | Notes |
|---|---|
| P2S, X1 Carbon, P1S, A1, A1 mini, H2S | single nozzle |
| H2D, X2D | two nozzles; `Filament(..., nozzle="left" / "right")` assigns each filament, or leave all empty for the studio's choice |

Opened in the GUI and printed: P2S only. macOS is tested; Linux paths are built in (extracted AppImage) and Windows
needs the studio's paths passed in; neither has been run yet.

## Related

[print-part-design](https://github.com/woolimi/print-part-design) comes before this skill: a browser 3D viewer for
parts made in code, fit checks for servos and boards, and shape cleanup for printing. Its STL output is what
`bambu-3mf` takes in.

## License

MIT. The setting-key lists in `bambu3mf.py` follow BambuStudio's `PrintConfig` (AGPL-3.0) and name its options.
No BambuStudio code is included.
