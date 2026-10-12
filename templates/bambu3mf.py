"""Bambu Studio projects (.3mf) of parts made as STL, written by the studio's own command line.

A project is a printer, a system process with the keys this project changes, its filaments, and its plates of
parts, each part laid on its printing face. The command line is handed the system profiles with their `inherits`
and `include` chains folded in, so the project carries the printer's own values - start G-code, speeds and
accelerations, each filament's temperatures, bed heats and density - and slices as the GUI does. The GUI reads
the process as its system preset plus the keys listed as changed, so those keys are listed.

What comes out is checked before it is written: every mesh as it went in (the studio repairs what it thinks is
broken, and drops triangles of no area), every object's own settings at the object, every filament able to stick
to the plate. Then the project is sliced plate by plate, and a plate that cannot print stops the build.

    from bambu3mf import Filament, Part, Plate, Project, Studio, build
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

# the keys an object (or a part of one) may set for itself; the rest are the plate's or the printer's
OBJECT_KEYS = frozenset("""
    adaptive_layer_height alternate_extra_wall apply_scarf_seam_on_circles bottom_color_penetration_layers
    bottom_shell_layers bottom_shell_thickness bottom_surface_density bottom_surface_pattern bridge_angle
    bridge_flow bridge_no_support bridge_speed brim_object_gap brim_type brim_width
    circle_compensation_manual_offset conformal_hub_radius conformal_infill conformal_link_flip_layers
    conformal_link_keep_layers conformal_pole conformal_ray_count conformal_stagger counterbore_hole_bridging
    detect_floating_vertical_shell detect_narrow_internal_solid_infill detect_overhang_wall detect_thin_wall
    elefant_foot_compensation embedding_wall_into_infill enable_circle_compensation enable_height_slowdown
    enable_overhang_speed enable_support enable_support_ironing enforce_support_layers
    ensure_vertical_shell_thickness fill_multiline filter_out_gap_fill flush_into_infill flush_into_objects
    flush_into_support fuzzy_skin fuzzy_skin_first_layer fuzzy_skin_mode fuzzy_skin_noise_type fuzzy_skin_octaves
    fuzzy_skin_persistence fuzzy_skin_point_distance fuzzy_skin_scale fuzzy_skin_thickness gap_infill_speed
    independent_support_layer_height infill_combination infill_direction infill_instead_top_bottom_surfaces
    infill_lock_depth infill_rotate_step infill_shift_step infill_wall_overlap initial_layer_flow_ratio
    inner_wall_line_width inner_wall_speed interface_shells interlocking_beam interlocking_beam_layer_count
    interlocking_beam_width interlocking_boundary_avoidance interlocking_depth interlocking_orientation
    internal_bridge_support_thickness internal_solid_infill_line_width internal_solid_infill_pattern
    internal_solid_infill_speed ironing_direction ironing_flow ironing_inset ironing_pattern ironing_spacing
    ironing_speed ironing_type layer_height line_width locked_skeleton_infill_pattern locked_skin_infill_pattern
    max_bridge_length min_bead_width min_feature_size minimum_sparse_infill_area
    mmu_segmented_region_interlocking_depth mmu_segmented_region_max_width modifier_ignore_infill
    monotonic_travel_into_wall only_one_wall_first_layer outer_wall_line_width outer_wall_speed overhang_1_4_speed
    overhang_2_4_speed overhang_3_4_speed overhang_4_4_speed overhang_totally_speed
    override_filament_scarf_seam_setting periodic_modifier periodic_modifier_apply_layers
    periodic_modifier_skip_layers precise_outer_wall precise_z_height print_flow_ratio raft_contact_distance
    raft_expansion raft_first_layer_density raft_first_layer_expansion raft_layers role_base_wipe_speed
    scarf_angle_threshold seam_gap seam_placement_away_from_overhangs seam_position seam_slope_conditional
    seam_slope_entire_loop seam_slope_gap seam_slope_inner_walls seam_slope_min_length seam_slope_start_height
    seam_slope_steps seam_slope_type skeleton_infill_density skeleton_infill_line_width skin_infill_density
    skin_infill_depth skin_infill_line_width slice_closing_radius slicing_mode slowdown_end_acc slowdown_end_height
    slowdown_end_speed slowdown_start_acc slowdown_start_height slowdown_start_speed small_perimeter_speed
    small_perimeter_threshold smooth_coefficient smooth_speed_discontinuity_area solid_infill_filament
    sparse_infill_anchor sparse_infill_anchor_max sparse_infill_density sparse_infill_filament
    sparse_infill_lattice_angle_1 sparse_infill_lattice_angle_2 sparse_infill_line_width sparse_infill_pattern
    sparse_infill_speed sub_top_surface_pattern support_angle support_base_pattern support_base_pattern_spacing
    support_bottom_interface_spacing support_bottom_z_distance support_critical_regions_only support_expansion
    support_filament support_interface_bottom_layers support_interface_filament support_interface_loop_pattern
    support_interface_not_for_body support_interface_pattern support_interface_spacing support_interface_speed
    support_interface_top_layers support_ironing_direction support_ironing_flow support_ironing_inset
    support_ironing_pattern support_ironing_spacing support_ironing_speed support_line_width
    support_object_first_layer_gap support_object_xy_distance support_on_build_plate_only
    support_remove_small_overhang support_speed support_style support_threshold_angle support_top_z_distance
    support_type symmetric_infill_y_axis thick_bridges top_area_threshold top_color_penetration_layers
    top_one_wall_type top_shell_layers top_shell_thickness top_solid_infill_flow_ratio top_surface_density
    top_surface_line_width top_surface_pattern top_surface_speed tree_support_branch_angle
    tree_support_branch_diameter tree_support_branch_diameter_angle tree_support_branch_distance
    tree_support_wall_count vertical_shell_speed wall_distribution_count wall_filament wall_generator wall_loops
    wall_sequence wall_transition_angle wall_transition_filter_deviation wall_transition_length wipe_speed
    xy_contour_compensation xy_hole_compensation
""".split())
# a plate type, and the filament key that holds the bed's heat on it (0: the filament does not stick there)
BED_HEAT = {"Textured PEI Plate": "textured_plate_temp", "High Temp Plate": "hot_plate_temp",
            "Engineering Plate": "eng_plate_temp", "Cool Plate": "cool_plate_temp",
            "Supertack Plate": "supertack_plate_temp"}
# a nozzle by name, and the studio's number for it on a printer of two: the first reaches the bed's left edge,
# the second its right
NOZZLES = {"left": 1, "right": 2}
# what a profile names about itself, not a setting
PROFILE_META = ("name", "type", "from", "instantiation", "inherits", "include")
STL_RECORD = np.dtype([("normal", "<f4", 3), ("tri", "<f4", (3, 3)), ("attr", "<u2")])
DOWN = np.array([0.0, 0.0, -1.0])


@dataclass(frozen=True)
class Studio:
    #: the command line: BambuStudio.app/Contents/MacOS/BambuStudio, or the extracted AppImage's AppRun
    app: Path
    #: the profiles it ships: .../resources/profiles/BBL
    profiles: Path


@dataclass(frozen=True)
class Filament:
    #: a system filament preset, as the studio names it ("Bambu PLA Basic @BBL P2S")
    profile: str
    colour: str = "#FFFFFF"
    #: on a printer of two nozzles (H2D, X2D), the one this filament runs through: "left" or "right". Give
    #: every filament one, or none and let the studio share them out to purge least
    nozzle: str = ""


@dataclass
class Part:
    stl: Path
    #: its filament, counting from 1 in Project.filaments
    filament: int = 1
    #: the direction in the STL's frame that goes down onto the bed; None keeps it as drawn
    down: tuple[float, float, float] | None = None
    #: a turn about the bed's vertical after laying, degrees
    turn: float = 0.0
    #: this object's own settings over the project's process (OBJECT_KEYS only)
    params: dict[str, str] = field(default_factory=dict)
    #: parts sharing a number above 0 become one object of several parts, each in its own filament; the
    #: object is laid down as a whole, so the parts keep their places against each other
    together: int = 0
    #: where the middle of the part's footprint (or its object's) goes on its plate, mm; None leaves it to the
    #: studio's arranger
    at: tuple[float, float] | None = None
    #: the name the studio shows; the STL's stem by default
    name: str = ""
    #: what the part does - what it carries, how it is loaded, what mates with it, where it works - the reason
    #: for its material and settings; printed with the build's report
    role: str = ""


@dataclass
class Plate:
    name: str
    parts: list[Part]
    #: the prime tower's corner, mm, on a plate placed by hand (`at`) that holds two filaments or more; the
    #: arranger finds it a place otherwise
    tower: tuple[float, float] | None = None


@dataclass
class Project:
    plates: list[Plate]
    filaments: list[Filament]
    #: the keys this project changes on the system process
    process: dict[str, str] = field(default_factory=dict)
    base_process: str = "0.20mm Standard @BBL P2S"
    printer: str = "Bambu Lab P2S 0.4 nozzle"
    bed_type: str = "Textured PEI Plate"


@dataclass(frozen=True)
class Sliced:
    plate: str
    minutes: float
    grams: float
    #: metres of each filament the plate uses, by filament number
    metres: dict[int, float]


def flattened(studio: Studio, kind: str, name: str) -> dict:
    """A system profile with its `inherits` chain and its `include` templates folded in, the base's keys first:
    the command line reads only the keys a file names and falls back to its own defaults for the rest."""
    path = studio.profiles / kind / f"{name}.json"
    if not path.is_file():
        raise SystemExit(f"no {kind} profile {name!r} in {studio.profiles}")
    own = json.loads(path.read_text())
    out = flattened(studio, kind, own["inherits"]) if own.get("inherits") else {}
    for template in own.get("include") or []:
        out.update({k: v for k, v in flattened(studio, kind, template).items() if k not in PROFILE_META})
    out.update(own)
    out.pop("inherits", None)
    out.pop("include", None)
    return out


def profiles(project: Project, studio: Studio) -> tuple[dict, dict, list[dict]]:
    """The printer's, the process's and each filament's profile, flattened."""
    return (flattened(studio, "machine", project.printer), flattened(studio, "process", project.base_process),
            [flattened(studio, "filament", f.profile) for f in project.filaments])


def read_tris(path: Path) -> np.ndarray:
    data = path.read_bytes()
    count = int(np.frombuffer(data, "<u4", 1, 80)[0]) if len(data) >= 84 else -1
    if len(data) != 84 + 50 * count:
        raise SystemExit(f"{path}: not a binary STL")
    return np.frombuffer(data, STL_RECORD, count, 84)["tri"].astype(np.float64)


def write_tris(tris: np.ndarray, path: Path) -> None:
    rec = np.zeros(len(tris), STL_RECORD)
    rec["tri"] = tris
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    rec["normal"] = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    path.write_bytes(b"bambu3mf".ljust(80, b" ") + np.uint32(len(tris)).tobytes() + rec.tobytes())


def rot_to(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The rotation taking direction a onto direction b."""
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v, c = np.cross(a, b), float(a @ b)
    if np.linalg.norm(v) < 1e-12:
        if c > 0:
            return np.eye(3)
        axis = np.cross(a, [1.0, 0.0, 0.0])
        axis = axis if np.linalg.norm(axis) > 1e-6 else np.cross(a, [0.0, 1.0, 0.0])
        axis /= np.linalg.norm(axis)
        return 2.0 * np.outer(axis, axis) - np.eye(3)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1.0 + c)


def laid(part: Part) -> np.ndarray:
    """The part's triangles turned onto its printing face and about the vertical, with the triangles of no area
    dropped: two corners on one float32 point, which the studio drops on import."""
    tris = read_tris(part.stl)
    rot = np.eye(3) if part.down is None else rot_to(np.asarray(part.down, float), DOWN)
    t = np.radians(part.turn)
    yaw = np.array([[np.cos(t), -np.sin(t), 0.0], [np.sin(t), np.cos(t), 0.0], [0.0, 0.0, 1.0]])
    tris = tris @ (yaw @ rot).T
    f = tris.astype(np.float32)
    flat = np.all(f[:, 0] == f[:, 1], 1) | np.all(f[:, 1] == f[:, 2], 1) | np.all(f[:, 0] == f[:, 2], 1)
    return tris[~flat]


def run(studio: Studio, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    if not studio.app.is_file():
        raise SystemExit(f"Bambu Studio not found at {studio.app}")
    # the AppImage runs with LC_ALL=C, which garbles paths that are not ASCII
    env = None if sys.platform == "darwin" else {**os.environ, "LC_ALL": "C.UTF-8"}
    return subprocess.run([str(studio.app), *args], cwd=cwd, capture_output=True, text=True, env=env)


def check(project: Project) -> None:
    """What the studio would take without a word but not use."""
    n = len(project.filaments)
    for plate in project.plates:
        if not plate.parts:
            raise SystemExit(f"plate {plate.name!r} holds nothing")
        if len({p.at is None for p in plate.parts}) > 1:
            raise SystemExit(f"plate {plate.name!r}: place every part (`at`) or none")
        if plate.parts[0].at is not None and len({p.filament for p in plate.parts}) > 1 and plate.tower is None:
            raise SystemExit(f"plate {plate.name!r} is placed by hand and holds several filaments: "
                             "give it a `tower`, or the prime tower stands off the bed")
        groups: dict[int, list[Part]] = {}
        for p in plate.parts:
            if not 1 <= p.filament <= n:
                raise SystemExit(f"{p.stl.name}: filament {p.filament}, but the project has {n}")
            wrong = sorted(set(p.params) - OBJECT_KEYS)
            if wrong:
                raise SystemExit(f"{p.stl.name}: {', '.join(wrong)} cannot be set on an object - "
                                 "put it in the project's process, or make it a project of its own")
            if p.together:
                groups.setdefault(p.together, []).append(p)
        for k, members in groups.items():
            if any(m.params != members[0].params or m.at != members[0].at for m in members):
                raise SystemExit(f"plate {plate.name!r}, object {k}: its parts must share params and `at`")


def assemble(project: Project, work: Path) -> tuple[list[dict], dict[str, tuple[Part, int]]]:
    """The command line's assemble list, the laid STLs written beside it, and each file's part and triangle count."""
    plates, sent = [], {}
    for i, plate in enumerate(project.plates, start=1):
        laid_parts = [(p, laid(p)) for p in plate.parts]
        # an object's footprint middle at its STL origin, its floor at zero: the studio puts the origin at `at`,
        # and slices an object where it sits, not set down
        lo: dict[int, np.ndarray] = {}
        hi: dict[int, np.ndarray] = {}
        for j, (p, tris) in enumerate(laid_parts):
            key = p.together or -1 - j
            pts = tris.reshape(-1, 3)
            lo[key] = np.minimum(lo.get(key, np.inf), pts.min(0))
            hi[key] = np.maximum(hi.get(key, -np.inf), pts.max(0))
        objects = []
        for j, (p, tris) in enumerate(laid_parts):
            key = p.together or -1 - j
            tris -= [(lo[key][0] + hi[key][0]) / 2, (lo[key][1] + hi[key][1]) / 2, lo[key][2]]
            path = work / f"p{i}_{j + 1}.stl"
            write_tris(tris, path)
            sent[path.name] = (p, len(tris))
            x, y = p.at if p.at is not None else (0.0, 0.0)
            objects.append({"path": str(path), "count": 1, "filaments": [p.filament],
                            "assemble_index": [p.together], "pos_x": [x], "pos_y": [y], "pos_z": [0.0],
                            "print_params": dict(p.params), "height_ranges": []})
        plates.append({"plate_name": plate.name, "need_arrange": plate.parts[0].at is None,
                       "plate_params": {}, "objects": objects})
    return plates, sent


def with_parts(ms: str, sent: dict[str, tuple[Part, int]]) -> str:
    """model_settings with every mesh checked to be as it went in, each object and part named, and each object's
    own settings at the object (a part of an assembled object carries them only on itself)."""
    left = dict(sent)
    wrong = []

    def one_object(m: re.Match) -> str:
        head, body = m.group(1), m.group(2)
        parts = []

        def one_part(pm: re.Match) -> str:
            text = pm.group(0)
            src = re.search(r'<metadata key="source_file" value="([^"]+)"/>', text)
            name = src.group(1) if src else "?"
            if name not in left:
                wrong.append(f"{name}: not one of the parts sent")
                return text
            part, want = left.pop(name)
            parts.append(part)
            stat = re.search(r'<mesh_stat face_count="(\d+)" edges_fixed="(\d+)" degenerate_facets="(\d+)" '
                             r'facets_removed="(\d+)" facets_reversed="(\d+)" backwards_edges="(\d+)"/>', text)
            faces, *fixes = map(int, stat.groups()) if stat else (-1, 0)
            if faces != want or any(fixes):
                wrong.append(f"{part.stl.name}: {want} triangles in, {faces} out, repairs {fixes}")
            label = escape(part.name or part.stl.stem, {'"': "&quot;"})
            return re.sub(r'(<metadata key="name" value=")[^"]*', lambda n: n.group(1) + label, text, count=1)

        body = re.sub(r'<part id="\d+" subtype="normal_part"[^>]*>.*?</part>', one_part, body, flags=re.S)
        if not parts:
            return m.group(0)
        first = parts[0]
        label = escape(first.name or first.stl.stem, {'"': "&quot;"})
        head = re.sub(r'(<metadata key="name" value=")[^"]*', lambda n: n.group(1) + label, head, count=1)
        own = dict(re.findall(r'^\s*<metadata key="(\w+)" value="([^"]*)"/>', body.split("<part", 1)[0], re.M))
        missing = {k: v for k, v in first.params.items() if own.get(k) != str(v)}
        if missing:
            body = "".join(f'\n    <metadata key="{k}" value="{escape(str(v))}"/>' for k, v in missing.items()) + body
        return head + body

    ms = re.sub(r'(<object id="\d+">\s*<metadata key="name" value="[^"]*"/>)(.*?)(?=</object>)', one_object, ms,
                flags=re.S)
    if wrong or left:
        raise SystemExit("the studio changed the parts:\n  " + "\n  ".join(
            wrong + [f"{p.stl.name}: not in the project" for p, _ in left.values()]))
    return ms


def with_settings(cfg: dict, project: Project) -> dict:
    """project_settings as the GUI reads it: the system process and the keys this project changes, the plate,
    and the filaments' colours and purge tables sized to the filaments."""
    n = len(project.filaments)
    unknown = sorted(set(project.process) - set(cfg))
    if unknown:
        raise SystemExit(f"not process settings: {', '.join(unknown)}")
    for k, v in project.process.items():
        cfg[k] = [str(v)] * len(cfg[k]) if isinstance(cfg[k], list) else str(v)
    cfg["print_settings_id"] = project.base_process
    cfg["inherits_group"] = [project.base_process] + [""] * n + [project.printer]
    cfg["different_settings_to_system"] = [";".join(sorted(project.process))] + [""] * n + [""]
    if project.bed_type not in BED_HEAT:
        raise SystemExit(f"bed_type {project.bed_type!r} is not one of {', '.join(BED_HEAT)}")
    cfg["curr_bed_type"] = project.bed_type
    heat = cfg[BED_HEAT[project.bed_type]]
    for f, h in zip(project.filaments, heat):
        if float(h) <= 0:
            raise SystemExit(f"{f.profile} does not stick to the {project.bed_type} (its profile heats it to 0)")
    plates = len(project.plates)
    for k in ("wipe_tower_x", "wipe_tower_y"):
        cfg[k] = (cfg[k] + cfg[k][-1:] * plates)[:plates]
    for i, plate in enumerate(project.plates):
        if plate.tower is not None:
            cfg["wipe_tower_x"][i], cfg["wipe_tower_y"][i] = (f"{v:g}" for v in plate.tower)
    cfg["filament_colour"] = [f.colour for f in project.filaments]
    # the command line leaves the purge tables at the printer's four slots: one row and column a filament, and
    # on a printer of two nozzles a table a nozzle, or the slicer reads past the end of it
    nozzles = len(cfg["nozzle_diameter"])
    cfg["flush_volumes_matrix"] = ["0" if i == j else cfg["flush_volumes_matrix"][1]
                                   for _ in range(nozzles) for i in range(n) for j in range(n)]
    cfg["flush_multiplier"] = (cfg.get("flush_multiplier") or ["1"])[:1] * nozzles
    cfg["flush_volumes_vector"] = cfg["flush_volumes_vector"][:2 * n]
    # how many nozzles of which kind each extruder holds: the GUI has it from the printer, the command line
    # leaves it empty, and a printer of two nozzles then finds none to slice with
    if not any(cfg.get("extruder_nozzle_stats") or []):
        cfg["extruder_nozzle_stats"] = [f"{kind}#{count}" for kind, count
                                        in zip(cfg["nozzle_volume_type"], cfg["extruder_max_nozzle_count"])]
    chosen = [f.nozzle for f in project.filaments]
    if any(chosen):
        if nozzles != 2:
            raise SystemExit(f"{project.printer} has {nozzles} nozzle(s): a filament's `nozzle` is for printers of two")
        if not all(c in NOZZLES for c in chosen):
            raise SystemExit(f"give every filament a nozzle, {' or '.join(NOZZLES)}: {chosen}")
        volume = {k: i for i, k in enumerate(("Standard", "High Flow", "TPU High Flow", "Hybrid", "E3D High Flow"))}
        cfg["filament_map_mode"] = "Manual"
        cfg["filament_map"] = [str(NOZZLES[c]) for c in chosen]
        cfg["filament_nozzle_map"] = [str(NOZZLES[c] - 1) for c in chosen]
        cfg["filament_volume_map"] = [str(volume.get(cfg["nozzle_volume_type"][NOZZLES[c] - 1], 0)) for c in chosen]
    else:
        for k in ("filament_map", "filament_nozzle_map", "filament_volume_map"):
            cfg[k] = (cfg.get(k) or ["1"])[:1] * n
    return cfg


def with_plates(ms: str, cfg: dict) -> str:
    """model_settings with each plate's filament map following the project's: a plate's own map, when it has
    one, stands over the project's."""
    if cfg.get("filament_map_mode") != "Manual":
        return ms
    rows = (f'\n    <metadata key="filament_map_mode" value="Manual"/>'
            f'\n    <metadata key="filament_maps" value="{" ".join(cfg["filament_map"])}"/>'
            f'\n    <metadata key="filament_volume_maps" value="{" ".join(cfg["filament_volume_map"])}"/>')

    def one(m: re.Match) -> str:
        body = re.sub(r'\n\s*<metadata key="(filament_map_mode|filament_maps|filament_volume_maps)" value="[^"]*"/>', "",
                      m.group(2))
        return m.group(1) + rows + body
    return re.sub(r'(<plate>\s*<metadata key="plater_id" value="\d+"/>)(.*?)(?=</plate>)', one, ms, flags=re.S)


def export(project: Project, studio: Studio, out: Path) -> int:
    """The project written to `out` by the studio's command line and checked. Returns the plate count."""
    check(project)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        plates, sent = assemble(project, work)
        (work / "assemble.json").write_text(json.dumps({"plates": plates}))
        machine, process, filament_profiles = profiles(project, studio)
        (work / "machine.json").write_text(json.dumps(machine))
        (work / "process.json").write_text(json.dumps(process))
        filaments = []
        for i, f in enumerate(filament_profiles, start=1):
            (work / f"filament{i}.json").write_text(json.dumps(f))
            filaments.append(str(work / f"filament{i}.json"))
        raw = work / "raw.3mf"
        done = run(studio, ["--load-settings", f"{work / 'machine.json'};{work / 'process.json'}",
                            "--load-filaments", ";".join(filaments),
                            "--load-assemble-list", str(work / "assemble.json"),
                            "--allow-multicolor-oneplate", "--allow-rotations",
                            "--export-3mf", raw.name, "--outputdir", str(work)], work)
        if done.returncode != 0 or not raw.is_file():
            raise SystemExit(f"Bambu Studio export failed ({done.returncode}):\n"
                             f"{done.stdout[-3000:]}\n{done.stderr[-2000:]}")
        # read it all before writing: the studio can still be touching the file it just wrote
        with zipfile.ZipFile(raw) as zin:
            entries = [(item, zin.read(item.filename)) for item in zin.infolist()]
    files = {item.filename: data for item, data in entries}
    ms = with_parts(files["Metadata/model_settings.config"].decode(), sent)
    cfg = with_settings(json.loads(files["Metadata/project_settings.config"]), project)
    if cfg.get("filament_settings_id") != [f.profile for f in project.filaments]:
        raise SystemExit(f"the studio loaded {cfg.get('filament_settings_id')}, "
                         f"not {[f.profile for f in project.filaments]}")
    ms = with_plates(ms, cfg)
    files["Metadata/model_settings.config"] = ms.encode()
    files["Metadata/project_settings.config"] = json.dumps(cfg, indent=4).encode()
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item, _ in entries:
            zout.writestr(item, files[item.filename])
    return ms.count("<plate>")


def sliced(path: Path, studio: Studio) -> list[Sliced]:
    """The project at `path` sliced as it stands, every plate: its time, weight and filament. A plate the studio
    cannot slice stops here with its reasons."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        done = run(studio, ["--slice", "0", "--export-3mf", "sliced.3mf", "--outputdir", tmp,
                            str(path.resolve())], work)
        if done.returncode != 0 or not (work / "sliced.3mf").is_file():
            why = [ln for ln in (done.stdout + done.stderr).splitlines()
                   if "can't be printed" in ln or "Object:" in ln or "error" in ln.lower()]
            raise SystemExit(f"{path.name} does not slice ({done.returncode}):\n  " + "\n  ".join(why[-8:]))
        with zipfile.ZipFile(work / "sliced.3mf") as z:
            info = z.read("Metadata/slice_info.config").decode()
            names = dict(re.findall(r'<metadata key="plater_id" value="(\d+)"/>\s*'
                                    r'<metadata key="plater_name" value="([^"]*)"/>',
                                    z.read("Metadata/model_settings.config").decode()))
    out = []
    for body in re.findall(r"<plate>(.*?)</plate>", info, re.S):
        index = re.search(r'key="index" value="(\d+)"', body).group(1)
        seconds = int(re.search(r'key="prediction" value="(\d+)"', body).group(1))
        grams = float(re.search(r'key="weight" value="([\d.]+)"', body).group(1))
        metres = {int(i): float(m) for i, m in re.findall(r'<filament id="(\d+)"[^>]*used_m="([\d.]+)"', body)}
        out.append(Sliced(names.get(index, index), seconds / 60.0, grams, metres))
    return out


def build(project: Project, studio: Studio, out: Path) -> list[Sliced]:
    """The project written to `out`, checked, and sliced: each plate's time, weight and filament."""
    export(project, studio, out)
    return sliced(out, studio)


def report(out: Path, project: Project, plates: list[Sliced]) -> None:
    """The lines a build prints for one project."""
    changed = ", ".join(f"{k} {v}" for k, v in project.process.items()) or "nothing"
    print(f"{out.name}: {project.printer} / {project.base_process} + {changed} / {project.bed_type}")
    for i, f in enumerate(project.filaments, start=1):
        print(f"  filament {i}: {f.profile} {f.colour}{', ' + f.nozzle + ' nozzle' if f.nozzle else ''}")
    for p, plate in zip(plates, project.plates):
        used = ", ".join(f"f{i} {m:.1f} m" for i, m in sorted(p.metres.items()))
        print(f"  plate {p.plate}: {round(p.minutes) // 60} h {round(p.minutes) % 60:02d} min, {p.grams:.1f} g ({used})")
        for part in plate.parts:
            own = ", ".join(f"{k} {v}" for k, v in part.params.items())
            print(f"    {part.name or part.stl.stem} (f{part.filament}){': ' + part.role if part.role else ''}"
                  f"{' [' + own + ']' if own else ''}")
