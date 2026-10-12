# Bambu Studio 3MF 내부 구조와 CLI

공식 문서에는 3MF 안의 설정 파일 형식이 없다. 기준은 BambuStudio 소스(`src/libslic3r/Format/bbs_3mf.cpp`,
`PresetBundle.cpp`, `PrintConfig.cpp`)와 Mac Bambu Studio 2.08.03 CLI 실험이다.

## Zip 구성

| 경로 | 내용 |
|---|---|
| `3D/3dmodel.model` | build item(개체마다 4×3 transform) + component(부품마다 `p:path` 와 transform). 3MF Production Extension |
| `3D/Objects/object_N.model` | 부품 mesh. 꼭짓점은 부품 중심 기준 좌표 |
| `Metadata/project_settings.config` | JSON. printer·process·filament 를 합친 전체 설정(약 580 key) |
| `Metadata/model_settings.config` | XML. 개체·부품 이름, 개체별 설정, 부품 `mesh_stat`, plate 목록 |
| `Metadata/slice_info.config` | slice 결과(plate 별 `prediction` 초·`weight` g·filament `used_m`/`used_g`). export 만 하면 비어 있다 |
| `Metadata/filament_sequence.json` | plate 별 filament 순서 |
| `Metadata/plate_N.png` 등 | 썸네일. CLI export 는 안 만들고 GUI 가 열 때 다시 그린다 |

## project_settings.config 의 핵심 key

| key | 값 |
|---|---|
| `print_settings_id` / `printer_settings_id` / `filament_settings_id` | preset 이름. GUI 는 이 이름으로 system preset 을 찾는다 |
| `inherits_group` | `[process 의 부모, filament 마다 "", printer 의 부모]` |
| `different_settings_to_system` | 같은 자리 구성의 목록. 각 칸은 바꾼 key 를 `;` 로 이은 문자열. **GUI 는 부모가 있는 preset 에서 이 목록에 없는 key 를 system 값으로 되돌린다** — 바꾼 key 는 반드시 적는다 |
| `curr_bed_type` | `Textured PEI Plate`·`High Temp Plate`·`Engineering Plate`·`Supertack Plate`·`Cool Plate`. 기본값이 Cool Plate 라 P2S 에서는 반드시 지정 |
| `filament_colour` | filament 수만큼 |
| `flush_volumes_matrix` / `flush_volumes_vector` / `filament_map` | CLI 가 4 slot 크기로 남긴다. filament 수에 맞게 자르지 않으면 slice 가 안 된다 |
| `wipe_tower_x` / `wipe_tower_y` | plate 마다 prime tower 모서리. 배치를 arranger 에 맡긴 plate 는 CLI 가 정하고, 고정 배치 plate 는 기본값(165, 250)이 bed 밖이라 지정해야 한다 |

값의 자료형: 대부분 문자열, filament·hotend 별 값은 문자열 list. process override 를 쓸 때 원래 list 인 key 는 list 로 둔다.

## model_settings.config

```xml
<object id="2">
  <metadata key="name" value="bracket"/>        <!-- GUI 에 보이는 이름 -->
  <metadata key="extruder" value="1"/>           <!-- filament 번호 -->
  <metadata key="wall_loops" value="2"/>         <!-- 이 개체만의 설정 -->
  <part id="1" subtype="normal_part" uuid="…">
    <metadata key="name" value="bracket"/>
    <metadata key="source_file" value="p1_1.stl"/>
    <mesh_stat face_count="802" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>
  </part>
</object>
<plate>
  <metadata key="plater_id" value="1"/>
  <metadata key="plater_name" value="parts"/>
  …
</plate>
```

- 개체(object)·부품(part) 설정으로 쓸 수 있는 key 는 `PrintObjectConfig`·`PrintRegionConfig` 소속뿐이다(약 215개,
  `templates/bambu3mf.py` 의 `OBJECT_KEYS`). `initial_layer_speed`·`print_sequence`·`enable_prime_tower`·`curr_bed_type`
  같은 전역 key 를 개체에 적으면 GUI·slicer 가 조용히 무시한다.
- 부품(part) 단위 metadata 는 region key 만 먹는다. 여러 부품으로 된 개체는 개체 단위에 적는다.
- `mesh_stat` 의 `face_count` 가 넣은 삼각형 수와 다르거나 repair 칸이 0 이 아니면 studio 가 mesh 를 고친 것이다.

## CLI

```
BambuStudio --load-settings "machine.json;process.json" --load-filaments "f1.json;f2.json" \
            --load-assemble-list assemble.json --allow-multicolor-oneplate --allow-rotations \
            --export-3mf raw.3mf --outputdir <dir>
BambuStudio --slice 0 --export-3mf sliced.3mf --outputdir <dir> project.3mf     # 프로젝트 그대로 slice
```

- Mac: `/Applications/BambuStudio.app/Contents/MacOS/BambuStudio`, profile `…/Contents/Resources/profiles/BBL`.
- Linux: AppImage 를 `--appimage-extract` 로 풀어 `AppRun` 과 `resources/profiles/BBL` 을 쓴다. AppImage 가 `LC_ALL=C`
  라 한글 경로가 깨지니 `LC_ALL=C.UTF-8` 로 실행한다.
- `--load-assemble-list` 형식:

```json
{"plates": [{"plate_name": "parts", "need_arrange": true, "plate_params": {},
             "objects": [{"path": "/abs/p1_1.stl", "count": 1, "filaments": [1], "assemble_index": [0],
                          "pos_x": [0.0], "pos_y": [0.0], "pos_z": [0.0],
                          "print_params": {"wall_loops": "2"}, "height_ranges": []}]}]}
```

- `plate_name` 은 필수다.
- `need_arrange` 는 plate 단위 값이다. false 면 `pos_x/pos_y` 가 **STL 좌표 원점**이 놓일 bed 좌표가 된다.
- `assemble_index` 가 같은(1 이상) 항목끼리 한 개체의 부품이 되고, 부품끼리의 상대 위치는 유지된다. 0 이면 합치지 않는다.
  번호는 plate 안에서만 묶인다. 다른 plate 의 같은 번호는 별개의 개체가 된다.
- `print_params` 에 모르는 key 를 넣으면 CLI 가 버린다. 전역 key 는 버리지 않고 개체에 남긴다.
- 개체 이름은 `<파일 stem>_1` 로 붙는다.
- `--arrange`·`--load-filament-ids` 경로(STL 을 인자로 나열)도 있지만 plate 를 지정할 수 없어서 arranger 가 남은 부품을
  새 plate 로 넘긴다. plate 를 정해야 하면 assemble list 를 쓴다.

## Profile 평탄화

CLI 는 `--load-settings` 로 받은 JSON 에 적힌 key 만 읽고 나머지는 자체 기본값으로 채운다. system profile JSON 을 그대로
넘기거나 `inherits` 만 적은 user preset 을 넘기면 project_settings 에 기본값이 들어간다. 2026-10-12 측정 결과는 다음과 같다.

| export 방식 | start G-code | 가속 / 외벽 속도 | filament density | 같은 판 slice |
|---|---|---|---|---|
| `inherits` 만 적은 user preset | 46자 | 500 / 60 | 0 | 34분 40초, 0 g |
| 평탄화한 profile | 11,543자 | 10000 / 200 | 1.26 | 20분, 9.18 g |

평탄화 규칙(Bambu `PresetBundle` 과 같은 순서)은 `inherits` 부모 → `include` template(`name`·`type`·`from`·`instantiation`
제외) → 자기 key 다. P2S machine 은 start·end·layer change·filament change G-code 를 `include` template 으로 가져온다.

hotend 변형: P2S profile 은 hotend 종류(Direct Drive Standard / High Flow / E3D High Flow)마다 값을 하나씩 가진 list 를
쓴다(`*_extruder_variant` 가 목록, 첫 값이 Standard). 평탄화한 그대로 넘겨도 단일·다색 plate 모두 slice 되고, GUI 는 프린터의
`nozzle_volume_type` 으로 값을 고른다. 표의 값을 읽을 때는 각 list 의 첫 값이 표준 hotend 값이다.

## 함정 모음

| 증상 | 원인 | 대응 |
|---|---|---|
| GUI 가 "support 없음, 벽 2" 같은 기본값을 보여 줌 | 바꾼 key 가 `different_settings_to_system` 에 없음 | 바꾼 process key 를 0번 칸에 적는다 |
| CLI slice 시간이 실제의 2.5배, 무게 0 g | 평탄화하지 않은 profile 로 export | 평탄화 |
| P2S 프로젝트가 Cool Plate | `curr_bed_type` 기본값 | 지정 |
| 부품이 plate 를 넘쳐 새 plate 로 감 | CLI 기본 bed 200 mm(평탄화하지 않은 machine) 또는 arranger 의 남은 부품 처리 | 평탄화한 machine 은 256×256 이 들어간다. plate 별 배치는 assemble list |
| filament 2개 plate 가 "gcode unprintable error_code 4" | 고정 배치 plate 의 prime tower 가 bed 밖(기본 165, 250) | `wipe_tower_x/y` 지정(`Plate.tower`) |
| `Invalid T command (T65535)` 로그 | P2S end G-code 의 `T65535`(정상) | 무시. 실패 원인은 다른 줄 |
| mesh 삼각형 수가 다름 | studio 가 면적 0 삼각형(float32 에서 꼭짓점 둘이 같은 것)을 버림, 또는 repair | 미리 버리고, repair 가 있으면 빌드를 멈춘다(의도한 공동이 메워진다) |
| 부품이 공중에 떠서 slice | studio 는 개체를 놓인 높이 그대로 slice | 바닥을 z=0 으로 |
| 개체별 설정이 안 먹음 | 여러 부품 개체의 부품 단위에만 적힘, 또는 전역 key | 개체 단위에 적고 `OBJECT_KEYS` 로 검사 |
| 방금 쓴 3MF 를 읽다 깨짐 | studio 가 아직 쓰는 중 | zip 전체를 메모리로 읽은 뒤 쓴다 |
| 생성 스크립트로 다시 만들자 손으로 고친 설정이 사라짐 | 결과 3MF 만 수정 | 설정은 스크립트에 둔다 |
