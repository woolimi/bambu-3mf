#!/usr/bin/env python3
"""What a Bambu Studio project (.3mf) will print with, read the way the GUI reads it, and sliced that way.

The GUI takes a project's process as its system preset plus the keys listed as changed, so that is what is
reported here, with each object's own settings over it and the shape each object stands on the bed with. Flags
mark what the GUI accepts without a word but should be looked at: a plate the printer does not take, keys an
object cannot hold, repaired meshes, a tall part on a small footprint with a narrow brim, support off over
downward faces. The slice is the GUI's: the system printer, process and filaments, flattened, with the listed
changes on top - so its times and weights stand even for a project whose own settings hold the command line's
defaults. On a plate of two filaments or more the purge can come out apart from the GUI's (a slice of the same
2-colour tile: 11 min 1.7 g here, 13 min 2.3 g sliced as written); its time is a guide.

    python3 review_3mf.py project.3mf [more.3mf ...] [--json]

Which settings a part should have depends on what the part does; that judgement is the reviewer's, with this
report as its evidence (SKILL.md section 2).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "templates"))
import bambu3mf as b  # noqa: E402

NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02",
      "p": "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"}
MAC = Path("/Applications/BambuStudio.app/Contents")
LINUX = Path.home() / "apps" / "BambuStudio"
# what a part file names about itself rather than a setting
PART_META = {"name", "matrix", "source_file", "source_object_id", "source_volume_id", "source_offset_x",
             "source_offset_y", "source_offset_z", "extruder"}
# a part this many times taller than the side of its footprint's square wants a wide brim
TALL = 4.0


def transform(text: str | None) -> tuple[np.ndarray, np.ndarray]:
    """A 3MF transform: p' = p @ M + t, the matrix stored row by row."""
    a = [float(v) for v in (text or "1 0 0 0 1 0 0 0 1 0 0 0").split()]
    return np.array(a[:9]).reshape(3, 3), np.array(a[9:])


def values(v) -> list[str]:
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]


def shapes(z: zipfile.ZipFile) -> dict[str, dict]:
    """Each object as it stands on the bed: its size, its lowest point, the area it stands on, and the area of
    its faces turned more than 45 degrees down above the bed (hole ceilings and bridges count too)."""
    root = ET.fromstring(z.read("3D/3dmodel.model"))
    comps = {}
    for obj in root.find("m:resources", NS).findall("m:object", NS):
        c = obj.find("m:components", NS)
        if c is not None:
            comps[obj.get("id")] = [(cc.get(f"{{{NS['p']}}}path").lstrip("/"), cc.get("objectid"),
                                     cc.get("transform")) for cc in c.findall("m:component", NS)]
    meshes, out = {}, {}
    for item in root.find("m:build", NS).findall("m:item", NS):
        oid = item.get("objectid")
        Mi, ti = transform(item.get("transform"))
        tris = []
        for path, sub, ct in comps.get(oid, []):
            if (path, sub) not in meshes:
                for o in ET.fromstring(z.read(path)).find("m:resources", NS).findall("m:object", NS):
                    if o.get("id") == sub:
                        mesh = o.find("m:mesh", NS)
                        v = np.array([[float(e.get(k)) for k in "xyz"] for e in mesh.find("m:vertices", NS)])
                        t = np.array([[int(e.get(k)) for k in ("v1", "v2", "v3")]
                                      for e in mesh.find("m:triangles", NS)])
                        meshes[(path, sub)] = v[t]
            Mc, tc = transform(ct)
            tris.append((meshes[(path, sub)] @ Mc + tc) @ Mi + ti)
        if not tris:
            continue
        t = np.concatenate(tris)
        pts = t.reshape(-1, 3)
        lo, hi = pts.min(0), pts.max(0)
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        area = np.linalg.norm(n, axis=1) / 2
        nz = n[:, 2] / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
        floor = (nz < -0.99) & (np.abs(t[:, :, 2].max(1) - lo[2]) < 0.05)
        down = (nz < -0.7071) & (t[:, :, 2].min(1) > lo[2] + 0.3)
        out[oid] = {"size": [round(float(x), 1) for x in hi - lo], "z0": round(float(lo[2]), 3),
                    "footprint_cm2": round(float(area[floor].sum()) / 100, 2),
                    "down_cm2": round(float(area[down].sum()) / 100, 2)}
    return out


def objects(ms: str) -> list[dict]:
    """model_settings' objects: name, filament, own settings, and each part's own settings and mesh repairs."""
    out = []
    for m in re.finditer(r'<object id="(\d+)">(.*?)</object>', ms, re.S):
        body = m.group(2)
        own = dict(re.findall(r'<metadata key="(\w+)" value="([^"]*)"/>', body.split("<part", 1)[0]))
        parts = []
        for pm in re.finditer(r'<part id="\d+" subtype="(\w+)"[^>]*>(.*?)</part>', body, re.S):
            md = dict(re.findall(r'<metadata key="(\w+)" value="([^"]*)"/>', pm.group(2)))
            stat = re.search(r'<mesh_stat face_count="(\d+)" edges_fixed="(\d+)" degenerate_facets="(\d+)" '
                             r'facets_removed="(\d+)" facets_reversed="(\d+)" backwards_edges="(\d+)"/>', pm.group(2))
            parts.append({"subtype": pm.group(1), "name": md.get("name", "?"),
                          "keys": {k: v for k, v in md.items() if k not in PART_META},
                          "repairs": [int(x) for x in stat.groups()[1:]] if stat else []})
        out.append({"id": m.group(1), "name": own.pop("name", "?"), "filament": own.pop("extruder", "1"),
                    "keys": own, "parts": parts})
    return out


def plates(ms: str, names: dict[str, str]) -> list[dict]:
    out = []
    for body in re.findall(r"<plate>(.*?)</plate>", ms, re.S):
        md = dict(re.findall(r'<metadata key="(\w+)" value="([^"]*)"/>', body.split("<model_instance>", 1)[0]))
        ids = re.findall(r'key="object_id" value="(\d+)"', body)
        out.append({"plate": md.get("plater_id"), "name": md.get("plater_name", ""),
                    "objects": [names.get(i, i) for i in ids]})
    return out


# where the project put each plate's prime tower and how much it purges: the project's own, not a preset's
PLACED = ("wipe_tower_x", "wipe_tower_y", "flush_volumes_matrix", "flush_volumes_vector", "flush_multiplier",
          "extruder_nozzle_stats", "filament_map_mode", "filament_map", "filament_nozzle_map", "filament_volume_map",
          "filament_colour")
# what a key is when no profile names it
DEFAULTS = {"brim_type": "auto_brim"}


def sliced(path: Path, studio: b.Studio, printer: str, base: str, changed: dict, filaments: list[str],
           cfg: dict) -> dict:
    """The project sliced with the system printer, process and filaments and the listed changes."""
    machine = b.flattened(studio, "machine", printer)
    process = b.flattened(studio, "process", base)
    for k, v in changed.items():
        process[k] = [str(v)] * len(process[k]) if isinstance(process.get(k), list) else v
    process.update({k: cfg[k] for k in PLACED if k in cfg})
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "m.json").write_text(json.dumps(machine))
        (work / "p.json").write_text(json.dumps(process))
        files = []
        for i, f in enumerate(filaments):
            (work / f"f{i}.json").write_text(json.dumps(b.flattened(studio, "filament", f)))
            files.append(str(work / f"f{i}.json"))
        run = b.run(studio, ["--load-settings", f"{work / 'm.json'};{work / 'p.json'}",
                             "--load-filaments", ";".join(files), "--slice", "0",
                             "--export-3mf", "s.3mf", "--outputdir", tmp, str(path.resolve())], work)
        if run.returncode != 0 or not (work / "s.3mf").is_file():
            why = [ln.split("]")[-1].strip() for ln in (run.stdout + run.stderr).splitlines()
                   if "rror" in ln or "can't" in ln]
            return {"ok": False, "why": why[-4:]}
        info = zipfile.ZipFile(work / "s.3mf").read("Metadata/slice_info.config").decode()
    out = []
    for body in re.findall(r"<plate>(.*?)</plate>", info, re.S):
        get = lambda k: (re.search(rf'key="{k}" value="([^"]*)"', body) or [None, ""])[1]  # noqa: E731
        out.append({"plate": get("index"), "minutes": round(int(get("prediction") or 0) / 60),
                    "grams": float(get("weight") or 0), "support": get("support_used"),
                    "warnings": re.findall(r'<warning msg="([^"]*)"', body)})
    return {"ok": True, "plates": out}


def review(path: Path, studio: b.Studio) -> dict:
    z = zipfile.ZipFile(path)
    cfg = json.loads(z.read("Metadata/project_settings.config"))
    ms = z.read("Metadata/model_settings.config").decode()
    printer = cfg["printer_settings_id"]
    base = cfg["print_settings_id"]
    if not (studio.profiles / "process" / f"{base}.json").is_file():
        base = (cfg.get("inherits_group") or [base])[0] or base
    filaments = cfg.get("filament_settings_id") or []
    listed = [k for k in ((cfg.get("different_settings_to_system") or [""])[0] or "").split(";") if k]
    system = b.flattened(studio, "process", base)
    changed = {k: cfg[k] for k in listed if k in cfg and k not in b.PROFILE_META and k != "compatible_printers"}
    machine = b.flattened(studio, "machine", printer)
    model = studio.profiles / "machine" / f"{machine.get('printer_model', '')}.json"
    refused = json.loads(model.read_text()).get("not_support_bed_type", "") if model.is_file() else ""
    bed = cfg.get("curr_bed_type", "Cool Plate")
    heat_key = b.BED_HEAT.get(bed, "")
    heats = [str(b.flattened(studio, "filament", f).get(heat_key, ["?"])[0]) for f in filaments]
    flags = []
    if set(listed) - set(changed):
        flags.append(f"listed as changed but not settings: {sorted(set(listed) - set(changed))}")
    if bed in refused.split(";"):
        flags.append(f"plate {bed!r}, which {printer} does not take; the bed would heat to {heats} °C")
    for f, h in zip(filaments, heats):
        if h in ("0", "?"):
            flags.append(f"{f} does not stick to the {bed}")
    eff = {**system, **changed}
    objs = objects(ms)
    shape = shapes(z)
    for o in objs:
        own = o["keys"]
        o["shape"] = shape.get(o["id"], {})
        setting = lambda k: own.get(k, values(eff.get(k, DEFAULTS.get(k, "?")))[0])  # noqa: E731
        o["settings"] = {k: setting(k) for k in ("layer_height", "wall_loops", "sparse_infill_density",
                                                    "sparse_infill_pattern", "enable_support", "brim_type",
                                                    "brim_width")}
        wrong = sorted(set(own) - b.OBJECT_KEYS - {"face_count"})
        if wrong:
            flags.append(f"{o['name']}: keys an object cannot hold {wrong}")
        for p in o["parts"]:
            if any(p["repairs"]):
                flags.append(f"{o['name']}/{p['name']}: mesh repaired {p['repairs']}")
        s = o["shape"]
        if not s:
            continue
        h, fp = s["size"][2], s["footprint_cm2"]
        brim = o["settings"]["brim_type"]
        width = float(o["settings"]["brim_width"] or 0)
        if fp > 0 and h / (fp ** 0.5 * 10) > TALL and (brim == "no_brim" or width < 5):
            flags.append(f"{o['name']}: {h} mm tall on {fp} cm² with brim {brim} {width:g} mm")
        if abs(s["z0"]) > 0.05:
            flags.append(f"{o['name']}: lowest point at z {s['z0']}")
        if o["settings"]["enable_support"] == "0" and s["down_cm2"] > 1:
            flags.append(f"{o['name']}: support off over {s['down_cm2']} cm² of faces turned down (check overhangs)")
        if o["settings"]["sparse_infill_pattern"] == "lightning":
            flags.append(f"{o['name']}: lightning infill holds only the top")
    names = {o["id"]: o["name"] for o in objs}
    return {"file": str(path), "printer": printer, "process": base, "filaments": filaments,
            "colours": cfg.get("filament_colour"), "bed": bed, "bed_heat": heats, "changed": changed,
            "changed_to_system_value": [k for k in changed if values(system.get(k)) == values(changed[k])],
            "plates": plates(ms, names), "objects": objs, "flags": flags,
            "slice": sliced(path, studio, printer, base, changed, filaments, cfg)}


def show(r: dict) -> None:
    print(f"\n{Path(r['file']).name}: {r['printer']} / {r['process']} / {r['bed']} (bed {', '.join(r['bed_heat'])} °C)")
    print(f"  filaments: {', '.join(f'{f} {c}' for f, c in zip(r['filaments'], r['colours'] or []))}")
    print(f"  changed: {', '.join(f'{k} {v}' for k, v in r['changed'].items()) or 'nothing'}")
    if r["changed_to_system_value"]:
        print(f"  (same as the system value: {', '.join(r['changed_to_system_value'])})")
    sl = {p["plate"]: p for p in r["slice"].get("plates", [])}
    for pl in r["plates"]:
        s = sl.get(pl["plate"], {})
        t = f"{s['minutes'] // 60} h {s['minutes'] % 60:02d} min, {s['grams']:.1f} g" if s else "not sliced"
        print(f"  plate {pl['plate']} {pl['name']!r}: {t}{' ' + str(s['warnings']) if s.get('warnings') else ''}")
        for name in pl["objects"]:
            o = next(x for x in r["objects"] if x["name"] == name)
            st, sh = o["settings"], o["shape"]
            print(f"    {name:32s} {sh.get('size')} mm, stands on {sh.get('footprint_cm2')} cm²; "
                  f"layer {st['layer_height']} walls {st['wall_loops']} {st['sparse_infill_density']} "
                  f"{st['sparse_infill_pattern']} support {st['enable_support']} brim {st['brim_type']} "
                  f"{st['brim_width']}{'  own: ' + str(o['keys']) if o['keys'] else ''}")
    if not r["slice"]["ok"]:
        print(f"  does not slice: {r['slice']['why']}")
    for f in r["flags"]:
        print(f"  ! {f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("projects", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true", help="one JSON line a project")
    ap.add_argument("--studio", type=Path, help="Bambu Studio's command line (default: this machine's)")
    ap.add_argument("--profiles", type=Path, help="its profiles/BBL folder (default: this machine's)")
    a = ap.parse_args()
    mac = sys.platform == "darwin"
    studio = b.Studio(a.studio or (MAC / "MacOS/BambuStudio" if mac else LINUX / "AppRun"),
                      a.profiles or (MAC / "Resources/profiles/BBL" if mac else LINUX / "resources/profiles/BBL"))
    for path in a.projects:
        r = review(path, studio)
        print(json.dumps(r, ensure_ascii=False)) if a.json else show(r)


if __name__ == "__main__":
    main()
