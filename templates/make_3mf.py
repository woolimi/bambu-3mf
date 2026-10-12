#!/usr/bin/env python3
"""Bambu Studio P2S projects of this repo's prints (TODO(project): what each project holds, in a line or two).

Each project is the P2S with its 0.20 mm Standard process and the keys set below, the Textured PEI plate, and
its filaments; each part lies on its printing face. bambu3mf writes the project with the studio's command line,
checks every mesh and setting went in, and slices every plate, so a plate that would not print stops here.

    python scripts/make_3mf.py [parts] [tiles]     # default: all, into print/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bambu3mf import Filament, Part, Plate, Project, Studio, build, report  # noqa: E402
from config import SETTINGS  # noqa: E402

STUDIO = Studio(SETTINGS.studio, SETTINGS.studio_profiles)
PLA = Filament("Bambu PLA Basic @BBL P2S", "#FFFFFF")
# functional parts: four walls take the load before the infill does; gyroid holds every way
PROCESS = {"wall_loops": "4", "sparse_infill_density": "20%", "sparse_infill_pattern": "gyroid",
           "enable_support": "1", "seam_position": "back"}


def stl(name: str) -> Path:
    return SETTINGS.print / f"{name}.stl"


def parts() -> Project:
    """TODO(project): the parts, each on the face it prints on."""
    return Project(
        plates=[Plate("parts", [
            Part(stl("bracket"), down=(0.0, 0.0, -1.0),
                 role="carries the servo: horn torque twists it, four self-tapping screws into its bosses"),
            Part(stl("cover"), down=(0.0, 0.0, 1.0), params={"wall_loops": "2"},
                 role="covers the board, no load; its outside shows"),
        ])],
        filaments=[PLA],
        process=PROCESS)


def tiles() -> Project:
    """TODO(project): a two-colour tile - one object, the base on filament 1 and the cells on filament 2, so the
    filament changes once, at the top of the base."""
    return Project(
        plates=[Plate("tiles", [
            Part(stl("tile_white"), filament=1, together=1, at=(128.0, 128.0)),
            Part(stl("tile_black"), filament=2, together=1, at=(128.0, 128.0)),
        ], tower=(30.0, 180.0))],
        filaments=[PLA, Filament("Bambu PLA Basic @BBL P2S", "#000000")],
        process={"brim_type": "no_brim"})


PROJECTS = {"parts": parts, "tiles": tiles}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("projects", nargs="*", help=f"which of {', '.join(PROJECTS)} (default: all)")
    ap.add_argument("--out", type=Path, default=SETTINGS.print, help="the folder the projects go in")
    a = ap.parse_args()
    unknown = sorted(set(a.projects) - set(PROJECTS))
    if unknown:
        ap.error(f"no project {', '.join(unknown)}")
    for name in a.projects or PROJECTS:
        project = PROJECTS[name]()
        out = a.out.expanduser() / f"{name}.3mf"
        report(out, project, build(project, STUDIO, out))


if __name__ == "__main__":
    main()
