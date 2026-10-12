# 출력 설정 근거 — Bambu Lab P2S

수치는 Bambu Studio 2.08.03 에 들어 있는 P2S system profile 을 평탄화해 표준 hotend 값으로 읽은 것이다
(`bambu3mf.flattened` + `one_hotend`). 규칙은 공개된 Bambu Lab Wiki(`https://wiki.bambulab.com/en/...`, 한국어 `/ko/...`)와
실제 출력 경험에서 왔다. 값이 의심스러우면 profile 을 직접 다시 읽는다. profile 이 정본이다.

## 재질별 profile 값 (P2S 0.4 nozzle, Direct Drive Standard)

| profile | nozzle 첫 층/이후 °C | Textured PEI / Smooth PEI / Cool °C | max volumetric mm³/s | fan % | 첫 N 층 fan off | 필요 nozzle HRC | 챔버 °C | 연화 °C |
|---|---|---|---|---|---|---|---|---|
| Bambu PLA Basic @BBL P2S | 220/220 | 55 / 55 / 35 | 21 | 100 | 1 | 3 | 0 | 45 |
| Bambu PLA Matte @BBL P2S | 220/220 | 55 / 55 / 35 | 22 | 100 | 1 | 3 | 0 | 45 |
| Bambu PLA Tough+ @BBL P2S | 245/245 | 55 / 55 / 35 | 21 | 100 | 1 | 3 | 0 | 45 |
| Bambu PLA-CF @BBL P2S 0.4 nozzle | 230/230 | 55 / 55 / 45 | 15 | 100 | 1 | 40 | 0 | 45 |
| Bambu PETG Basic @BBL P2S 0.4 nozzle | 245/250 | 70 / 70 / 0 | 15 | 30–60 | 3 | 3 | 0 | 60 |
| Bambu PETG HF @BBL P2S 0.4 nozzle | 230/245 | 70 / 70 / 0 | 21 | 30–60 | 3 | 3 | 0 | 70 |
| Bambu TPU 95A HF @BBL P2S | 230/230 | 35 / 35 / 30 | 12 | 100 | 1 | 3 | 0 | 30 |
| Bambu ABS @BBL P2S | 260/270 | 90 / 90 / 0 | 16 | 10–60 | 3 | 3 | 65 | 100 |
| Bambu ASA @BBL P2S 0.4 nozzle | 270/270 | 100 / 100 / 0 | 18 | 10–35 | 3 | 3 | 65 | 100 |
| Bambu PC @BBL P2S 0.4 nozzle | 270/280 | 100 / 100 / 0 | 18 | 10–40 | 3 | 3 | 60 | 120 |
| Bambu PA6-CF @BBL P2S | 275/275 | 100 / 100 / 0 | 8 | 10–30 | 3 | 40 | 60 | 170 |
| Bambu PET-CF @BBL P2S | 270/270 | 100 / 100 / 0 | 5 | 1–80 | 3 | 40 | 50 | 185 |

- plate 온도가 0 이면 그 plate 에 못 붙는 재질이다. `bambu3mf` 가 build 단계에서 막는다.
- 필요 HRC 40 은 hardened steel nozzle 이 필요하다는 뜻이다. P2S 기본 nozzle 은 hardened steel(`nozzle_type`)이라 CF 도 바로 된다.
- 챔버 값이 있는 재질(ABS·ASA·PC·PA)은 밀폐 챔버를 데워야 한다. P2S 는 능동 챔버 히터가 없어서 bed 를 높여 미리 데운다.
- 연화 온도(`temperature_vitrification`)가 낮은 재질은 챔버가 뜨거우면 extruder 안에서 물러져 막힌다. Wiki 는 PLA·TPU 는 bed
  45 °C 이상, PETG 는 bed 60 °C 이상일 때 앞문이나 윗유리를 열라고 권한다(`general/filament-guide-material-table`).
- profile 이름 목록: `ls "<profiles>/filament" | grep "@BBL P2S"`. 재질에 따라 `0.4 nozzle` 이 이름에 붙는다.

## 재질 고르기

| 필요한 것 | 재질 | 감수할 것 |
|---|---|---|
| 일반 지그·케이스·시제품 | PLA Basic | 60 °C 근처에서 물러진다. 하중을 오래 받으면 변형이 남는다 |
| PLA 로 충격을 더 | PLA Tough+ | nozzle 온도가 높다 |
| 강성·치수 안정 | PLA-CF | 표면이 거칠고 hardened nozzle |
| 휘었다 돌아오는 스프링·걸쇠, 차 안·햇빛 정도의 열 | PETG Basic / HF | 습기에 약해 건조 필요, PLA 보다 warping 이 쉽다. Cool Plate 불가 |
| 유연 부품(패드·그립) | TPU 95A HF | 느리고, 매우 습기에 약하다. support 는 PLA 로 |
| 내열·옥외 | ASA (옥외) / ABS / PC (고내열·고강도) | 밀폐·예열, glue, 냄새·VOC |
| 고강성·고내열 구조 부품 | PA6-CF / PET-CF | 건조 필수, glue, 비싸다 |

성능이 높은 재질일수록 온도·밀폐·건조 조건이 까다로워진다. 기능이 PLA 로 충분하면 PLA 를 쓴다.

## Plate

| `curr_bed_type` | GUI 이름 | filament 의 bed 온도 key | 쓰는 경우 |
|---|---|---|---|
| `Textured PEI Plate` | Textured PEI Plate | `textured_plate_temp` | P2S 기본. PLA·PETG·TPU 가 glue 없이 붙고 식으면 떨어진다 |
| `High Temp Plate` | Smooth PEI Plate / High Temp Plate | `hot_plate_temp` | 바닥면이 매끈해야 할 때. PETG 는 판 보호용 glue |
| `Engineering Plate` | Engineering Plate | `eng_plate_temp` | glue 를 발라 거의 모든 재질 |
| `Supertack Plate` | Bambu Cool Plate SuperTack | `supertack_plate_temp` | 낮은 온도로 PLA·PETG 를 강하게 잡을 때 |
| `Cool Plate` | Cool Plate | `cool_plate_temp` | **P2S 미지원**(machine model `not_support_bed_type`). Studio 의 기본값이라 지정하지 않으면 이 값이 들어간다 |

Textured PEI 는 IPA 보다 따뜻한 물과 주방세제로 씻는다(Wiki `filament-acc/acc/plates`).

## Process 기본값과 조정 방향

`0.20mm Standard @BBL P2S` 기본값: 벽 2, 윗면 5층·아랫면 3층, infill 15% grid, support 꺼짐(켜면 tree(auto), 기준 각 30°),
brim 폭 5 mm, seam aligned, wall generator classic, `slice_closing_radius` 0.049.

| 목적 | 조정 |
|---|---|
| 강도 | 벽부터 늘린다(3–4). 벽이 하중 대부분을 받아서 infill 보다 효과가 크다. infill 은 gyroid·cubic 처럼 방향을 덜 타는 패턴으로 20–40%. 하중이 층을 벌리지 않게(층과 나란히) 눕힌다. FDM 은 층 사이(Z)가 층 안(XY)보다 몇 배 약하다. Wiki 는 벽 6 이하·infill 50% 이하를 권한다(넘으면 warping) |
| 표면 | `0.16mm`·`0.12mm High Quality` preset. 넓은 윗면은 `ironing_type` top. 둥근 윗면은 `top_one_wall_type` "not apply" |
| 속도·재료 절약 | layer 0.24–0.28(0.4 nozzle 에서 0.3 이상은 volumetric 한계). infill 5–10% supportcubic, top 3·bottom 2. lightning 은 윗면만 받쳐서 옆에서 힘을 받는 부품에는 쓰지 않는다 |
| 미세 형상 | 0.08 mm layer, 나사산·스냅은 100% infill. 0.08 은 압출 오차에 민감해서 필요한 부품만 |
| line width 보다 얇은 벽 | `wall_generator` arachne |
| 0.1 mm 미만의 의도한 틈 | `slice_closing_radius` 를 줄인다(기본 0.049 면 0.098 mm 보다 좁은 틈이 메워진다) |

volumetric flow 는 line width × layer height × 속도다. slicer 는 `filament_max_volumetric_speed` 를 넘는 경로를 자동으로
늦추지만, 출력 중에 프린터 화면의 Speed Mode 를 올리면 이 제한이 적용되지 않는다(Wiki `knowledge-sharing/volumetric-speed`).

## Support

- 방향부터 바꿔 support 를 줄인다. support 는 표면에 흔적을 남기고 시간을 늘린다.
- `support_type` tree(auto) 가 기본 선택지다. 넓고 평평한 overhang 은 normal(auto) 나 `support_style` tree_hybrid.
- 같은 재질 support 의 `support_top_z_distance` 는 layer height 정도(0.2)로 둔다. 0 은 전용 support filament 를 interface 에만
  쓸 때만 가능하다(Wiki `software/bambu-studio/support`). P2S 는 nozzle 이 하나라 support filament 를 interface 에만 쓰면
  filament 교체가 줄어든다.
- 필요 없는 부품은 개체별 `enable_support` 0 으로 끈다.
- PA 계열과 PVA support 는 습기를 먹으면 떼기 어려워서 출력 직후 뗀다.

## 넘어짐·warping

- 바닥이 좁고 키 큰 부품은 brim(`brim_type` outer_only, 폭 5–10 mm, `brim_object_gap` 0)을 준다. 바닥 1.1 cm² 에 높이 99 mm 인
  부품이 brim 없이 출력 중에 넘어진 적이 있다.
- 모서리만 들리면 `brim_type` brim_ears. 첫 층 bed 를 5–10 °C 올리거나 첫 몇 층 fan 을 끈다(filament 설정).
- 끼워맞춤 면이 바닥에 닿는 부품·얇은 타일은 brim 이 그 면을 망치므로 `no_brim`.
- PETG·ABS 계열은 PLA 보다 warping 이 쉽다. 벽·infill 을 과하게 올리면 수축 응력이 커진다.

## 건조

PLA 외 대부분의 재질은 출력 전에 말린다. 습한 filament 는 stringing·기포·층간 약화를 만든다. 재질별 온도·시간은 Wiki
`filament-acc/filament/dry-filament` 의 표를 따른다(P2S bed 건조·오븐·AMS 2 Pro·AMS HT 별 값이 있다).

## 더 읽을 곳

- Wiki: `general/filament-guide-material-table`(재질별 plate·nozzle·glue 호환과 bed 온도), `bambu-studio/parameter`
  (파라미터 색인), `software/bambu-studio/how-to-set-slicing-parameters`(Global·Object·Part·Modifier 범위),
  `software/bambu-studio/support`, `software/bambu-studio/auto-brim`, `x2d/troubleshooting/preventing-warping-p2s-x2d`
- Bambu Lab Academy(`https://bambulab.com/en/support/academy`, 무료·로그인 필요): Bambu Lab Filament, Bambu Studio,
  Bambu Lab P2S 강좌. 재질과 slicer 설정을 체계적으로 배우기 좋다.
