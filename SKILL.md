---
name: bambu-3mf
description: 코드로 만든 STL 부품을 Bambu Lab P2S 로 바로 뽑을 수 있는 Bambu Studio 프로젝트(.3mf)로 만든다. 재질(PLA·PETG·TPU·ABS·CF), plate, process preset, 부품별 설정(벽·infill·support·brim), 출력 방향, plate 배치를 Bambu Studio 번들 profile·Bambu Lab Wiki 근거로 정하고, Studio CLI 로 평탄화한 system profile 을 넣어 export → mesh·설정 검사 → plate 별 slice(시간·무게)까지 한 번에 돌린다. "3MF 만들어줘", "출력 파일 만들어줘", "Bambu Studio 프로젝트로", "바로 뽑을 수 있게", "슬라이스 설정 넣어줘", "필라멘트 뭐로 뽑아", "PETG 로 바꿔", "벽 늘려줘", "출력 시간 얼마나 걸려", make_3mf·build_bambu_project 스크립트를 새로 만들거나 고칠 때 쓴다. 형상 정리는 print-tidy, 뷰어는 design-view 스킬.
---

# bambu-3mf — Bambu Studio 출력 프로젝트 생성

빌드 스크립트가 쓴 STL 을 받아서 P2S 에서 열자마자 slice·출력할 수 있는 3MF 를 만든다. 3MF 는 Bambu Studio 의 CLI 가
쓰고, 스크립트는 그 앞뒤만 맡는다. 앞에서는 system profile 을 평탄화하고 STL 을 출력 방향으로 눕혀 넘긴다. 뒤에서는
GUI 가 읽는 방식대로 설정 목록을 고치고, mesh·설정을 검사하고, plate 마다 slice 해서 시간과 무게를 보고한다.
설정값의 근거는 Bambu Studio 에 들어 있는 system profile, 공개 Bambu Lab Wiki, 실제 출력 경험이고, 요점은
`references/print-settings.md` 에 있다.

| 파일 | 역할 |
|---|---|
| `templates/bambu3mf.py` | 공용 모듈. `Project`·`Plate`·`Part`·`Filament`·`Studio` 를 받아 `build()` 가 export·검사·slice 를 한다. 리포 `scripts/` 에 복사해 쓴다 |
| `templates/make_3mf.py` | 프로젝트별 정의 예시. `PROJECTS` 의 함수가 `Project` 를 돌려준다 |
| `references/print-settings.md` | 재질별 P2S profile 값, 재질 고르기, plate, process 조정 방향, support, warping, 건조 |
| `references/3mf-internals.md` | 3MF zip 구성, 설정 key, CLI 와 assemble list 형식, profile 평탄화, 함정 모음 |
| `scripts/review_3mf.py` | 기존 3MF 검토: GUI 가 쓸 설정, 개체별 설정·형상, flag, GUI 방식 slice 시간·무게 |

## 1. 세팅 절차

1. `templates/bambu3mf.py` 와 `templates/make_3mf.py` 를 리포 `scripts/` 로 복사한다. 의존성은 `numpy` 뿐이다.
2. `config.py` 의 `Settings` 에 세 칸을 합친다. 경로는 config 한 곳에만 둔다.

   ```python
   #: Bambu Studio's command line and the profiles it ships, on this machine (make_3mf.py)
   studio: Path = (Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio") if sys.platform == "darwin"
                   else Path.home() / "apps" / "BambuStudio" / "AppRun")
   studio_profiles: Path = (Path("/Applications/BambuStudio.app/Contents/Resources/profiles/BBL")
                            if sys.platform == "darwin"
                            else Path.home() / "apps" / "BambuStudio" / "resources" / "profiles" / "BBL")
   #: what prints: the STLs build.py writes and the projects make_3mf.py writes from them
   print: Path = REPO / "print"
   ```

   Linux 는 AppImage 를 `--appimage-extract` 로 `~/apps/BambuStudio` 에 풀어 둔다.
3. 재질·plate·process 를 2절 순서로 정하고 `make_3mf.py` 의 `TODO(project)` 자리에 `PROJECTS` 를 채운다.
   프로젝트 하나 = 3MF 하나. 같이 출력할 부품 묶음 단위로 나눈다(예: arm·gripper·tiles).
4. `python scripts/make_3mf.py` 로 만든다. plate 마다 시간·무게·filament 길이가 찍히면 성공이다.
5. README 에 프로젝트 표(파일·plate·재질·시간)와 재생성 명령을 적는다. `print/` 를 커밋하는 리포면 `*.3mf` 도 커밋한다.
6. 사용자가 출력할 파일이면 바탕화면에 복사하거나(`--out ~/Desktop`) 경로를 알려 준다.

### 모듈 사용법

```python
Project(
    plates=[Plate("arm", [
        Part(stl("upper_arm"), down=(0, -1, 0), params={"enable_support": "0"}),
        Part(stl("jaw"), down=(1, 0, 0), params={"brim_type": "outer_only", "brim_width": "5"}),
    ]),
    Plate("tiles", [Part(stl("tile_white"), filament=1, together=1, at=(128, 128)),
                    Part(stl("tile_black"), filament=2, together=1, at=(128, 128))], tower=(30, 180))],
    filaments=[Filament("Bambu PLA Basic @BBL P2S", "#FFFFFF"), Filament("Bambu PLA Basic @BBL P2S", "#000000")],
    process={"wall_loops": "4", "sparse_infill_density": "20%", "sparse_infill_pattern": "gyroid"},
)   # base_process "0.20mm Standard @BBL P2S", printer "Bambu Lab P2S 0.4 nozzle", bed_type "Textured PEI Plate"
```

| 필드 | 뜻 |
|---|---|
| `Part.down` | STL 좌표에서 bed 쪽으로 내려갈 방향. 출력 방향의 정본이므로 overhang 검사·뷰어도 이 값을 본다 |
| `Part.turn` | 눕힌 뒤 수직축 회전(°). arranger 가 다시 돌릴 수 있어서 각도가 중요하면 `at` 과 같이 쓴다 |
| `Part.params` | 이 개체만의 설정. `OBJECT_KEYS` 밖의 key(전역 전용)는 build 가 거부한다 |
| `Part.together` | 같은 번호(1 이상)끼리 한 개체의 여러 부품. 부품마다 filament 가 다를 수 있고 상대 위치를 유지한다 |
| `Part.at` | footprint 중심의 bed 좌표(mm). plate 의 모든 부품에 주거나 모두 비운다(비우면 arranger) |
| `Plate.tower` | 손으로 배치한 plate 에 filament 가 둘 이상이면 prime tower 모서리 좌표가 필요하다 |
| `Project.process` | base process 위에 바꾸는 전역 key. GUI 에서 "바꾼 값"으로 보인다 |

`build()` 는 아래 경우에 멈춘다. GUI 는 모두 말없이 받아들이지만 결과는 틀린다.
- mesh 가 들어간 그대로가 아니다(repair·삼각형 수 차이)
- 개체에 전역 key 를 적었다
- process key 의 철자가 틀렸다
- filament 가 고른 plate 에 붙지 않는다(profile 의 bed 온도 0)
- plate 를 slice 할 수 없다

## 2. 설정 결정 순서

설정은 부품이 하는 일에서 나온다. 같은 PLA 브래킷이라도 서보 비틀림을 받는 것과 보드를 얹기만 하는 것은 벽 수·방향·
재질이 다르다. 순서대로 정하고, 각 단계의 값을 사용자에게 한 줄로 알린다. 재질처럼 기능을 바꾸는 결정은 사용자 확인을 받는다.

0. **부품 카드** — 설정을 고르기 전에 부품마다 아래를 적는다. 리포의 README·설계 문서·빌드 스크립트 docstring·config
   주석·메모리를 읽고, 그래도 모르는 칸은 사용자에게 묻는다. 요약을 `Part.role` 에 한 줄로 남기면 build 보고에 설정과
   같이 찍힌다.
   - 역할: 무엇을 잡고 어디에 붙는가(서보·보드·카메라·손잡이·덮개)
   - 하중: 종류(비틀림·굽힘·충격·압축·오래 걸리는 하중), 방향, 크기
   - 맞물림: 나사(플라스틱에 직접 박는 self-tapping·관통 볼트·열압입 insert), 압입 포켓, 스냅·클립, 미끄럼면,
     bed 에 닿는 끼워맞춤 면
   - 환경: 열원(모터·조명·햇빛), 옥외·습기, 손에 쥐는지, 떨어질 수 있는지
   - 겉모습: 보이는 면, seam 을 숨길 곳
1. **재질** — 부품 카드의 하중·환경으로 고른다. 기본은 `Bambu PLA Basic @BBL P2S`.
   형상 복원이 필요한 스프링·걸쇠나 60 °C 이상 환경이면 PETG(`Bambu PETG Basic @BBL P2S 0.4 nozzle`),
   유연 부품이면 TPU 95A HF, 내열·옥외는 ASA, 강성·치수 안정은 PLA-CF 를 쓴다. 표는 `references/print-settings.md`.
   profile 이름은 `ls "<profiles>/filament" | grep "@BBL P2S"` 로 확인한다. 이름에 `0.4 nozzle` 이 붙는 재질이 있다.
2. **plate** — P2S 기본 Textured PEI(`Textured PEI Plate`). 바닥면이 매끈해야 하거나 바닥 치수가 중요하면
   Smooth PEI(`High Temp Plate`). P2S 는 Cool Plate 를 지원하지 않는다.
3. **base process** — `0.20mm Standard @BBL P2S`. 표면이 중요하면 `0.16mm High Quality`·`0.12mm High Quality`,
   나사산·스냅처럼 미세한 부품만 모은 프로젝트면 `0.08mm High Quality`, 빨리 뽑을 시제품이면 `0.24mm Standard`.
   목록은 `ls "<profiles>/process" | grep "P2S"`.
4. **전역 override** (`Project.process`) — 프로젝트 부품 대부분의 카드에 공통인 값만 둔다. 3절에서 고른다.
5. **개체별 override** (`Part.params`) — 카드가 다른 부품만. 하중이 큰 부품의 벽·infill 증가, support 가 필요 없는
   부품의 `enable_support 0`, 넘어지기 쉬운 부품의 brim, 하중 없는 부품의 벽·infill 축소.
6. **출력 방향·배치** — 카드의 하중이 층을 벌리지 않게(층과 나란히) 눕힌다. 그다음 overhang·support 가 적게, 바닥 면적이
   넓게, 끼워맞춤 면이 support·brim 에 닿지 않게.
   support 를 켜기 전에 방향부터 바꾼다. 여러 plate 면 plate 하나 = filament 하나가 기본이다(AMS 없이 spool 교체).

## 3. 부품 특성별 기준값

부품 카드의 항목마다 해당하는 줄을 모두 적용한다. 줄끼리 부딪치면 하중·맞물림 쪽을 따른다.

| 카드의 특성 | 설정·재질 | 근거 |
|---|---|---|
| 서보 혼 비틀림, 외팔보 굽힘처럼 반복되는 큰 하중 | `wall_loops` 4–5, `sparse_infill_density` 25–40% gyroid·cubic, 하중이 층과 나란히 걸리게 눕힘 | 벽이 하중 대부분을 받는다. FDM 은 층 사이(Z)가 층 안보다 몇 배 약하다 |
| 하중을 받는 일반 기능 부품(PLA) | `wall_loops` 4, `sparse_infill_density` 20–25% gyroid, `enable_support` 1(tree auto), `seam_position` back | 로봇 팔·마운트·그리퍼 부품에 써 온 값 |
| 플라스틱에 직접 박는 self-tapping 나사 | 구멍 둘레가 벽으로 차게 `wall_loops` 3 이상(0.4 nozzle 에서 1.2 mm 이상) | 나사산이 infill 이 아니라 벽에 물려야 한다 |
| 압입 포켓·서보 자리·끼워맞춤 | `precise_outer_wall` 1, 그 면에 support·brim 이 닿지 않는 방향, 구멍 보정은 설계 clearance 와 맞춤 | 치수가 기능이다 |
| 모터·조명 옆, 차 안처럼 50 °C 가까이 | PETG 이상(PLA profile 의 연화 온도 45 °C, PETG 60–70 °C) | 오래 데워진 PLA 는 하중 아래에서 처진다 |
| 손에 쥐고 다루거나 떨어질 수 있는 부품 | 벽 4, infill 25%. 자주 떨어지면 PLA Tough+ 나 PETG | 충격은 벽과 인성이 받는다 |
| 덮개·외관·하중 없는 받침 | 벽 2–3, infill 15%, seam back 또는 aligned | system 기본(벽 2·15%)으로 충분 |
| 나사산·스냅·노브 | `layer_height` 0.08, `sparse_infill_density` 100% (개체별) 또는 0.08mm High Quality 프로젝트 | 출력한 노브·너트·체결 부품이 그대로 맞았다 |
| 스프링처럼 휘었다 돌아와야 하는 부품 | PETG | PLA 는 오래 휜 채로 두면 변형이 남는다 |
| 옆면을 누르거나 옆 포켓에 끼우는 부품 | lightning 금지. cubic·gyroid | lightning 은 윗면만 받쳐서 마커 큐브가 타일을 누를 때 부러졌다 |
| 키 크고 바닥이 좁은 부품 | `brim_type` outer_only, `brim_width` 3–10, `brim_object_gap` 0 | 높이 99 mm·바닥 1.1 cm² 인 그리퍼 jaw 는 brim 없이 넘어졌다 |
| 끼워맞춤 면이 바닥에 닿는 부품·타일 | `brim_type` no_brim | brim 이 끼워맞춤 면을 망친다 |
| 1–2 mm 얇은 판(타일) | `wall_loops` 2 (개체별) | 1.4 mm 마커 타일 |
| support 가 필요 없는 부품 | `enable_support` 0 (개체별) | 전역 support 가 불필요한 흔적을 남긴다 |
| 나사 머리 자리(counterbore) 바닥 | `counterbore_hole_bridging` partiallybridge | counterbore 바닥 bridge 가 support 없이 선다 |
| 빨리·가볍게(형상 유지 검사용) | `layer_height` 0.28 또는 0.24 Standard, infill 5–10% supportcubic, top 3 / bottom 2 | 40 mm 큐브 23분 → 15분(layer 가 가장 큰 효과) |
| 0.05–0.1 mm 의 의도한 틈 | `slice_closing_radius` 0.02 | 기본 0.049 는 0.098 mm 미만 틈을 메운다 |

- 구멍 보정: 설계에서 clearance 를 이미 준 부품은 `enable_circle_compensation`·
  `xy_hole_compensation` 을 기본 0 으로 둔다. 둘 다 켜면 이중 보정이 된다. 설계 치수 그대로 뽑아 맞추려면
  `enable_circle_compensation` 1 을 쓰고 tolerance test 로 확인한다.
- 벽 6 겹·infill 50% 를 넘기면 warping 위험이 커진다(Wiki). 그 이상이 필요하면 재질을 바꾼다.
- `initial_layer_speed`(첫 층 속도)·`curr_bed_type`·`print_sequence`·`enable_prime_tower` 는 전역 전용이다. 한
  부품만 다르게 하려면 프로젝트를 나눈다.

## 4. 검증

1. `make_3mf.py` 출력: plate 마다 시간·무게가 나와야 한다. 시간이 0 이거나 무게가 0 g 이면 profile 이 덜 들어간 것이다.
2. 처음 만든 프로젝트는 사용자에게 Bambu Studio 로 열어 확인을 요청한다. 확인할 항목은 다음과 같다.
   - process 가 `0.20mm Standard @BBL P2S` 에 바꾼 key 가 표시된 상태인지
   - plate 가 Textured PEI 인지
   - 개체 옆 톱니 아이콘에 개체별 설정이 있는지
   - GUI Slice 시간이 스크립트가 보고한 시간과 비슷한지
3. 출력 방향은 3D 뷰어나 overhang 검사로 본다. `Part.down` 을 바꿨으면 overhang 검사를 다시 돌린다.
4. 형상을 바꾸지 않았으면 3MF 를 다시 만들지 않는다(커밋 노이즈).

### 기존 3MF 검토

이미 만든 3MF 는 `scripts/review_3mf.py <file.3mf> ...` 로 읽는다. 이 도구는 GUI 가 쓰는 값을 보여 준다. GUI 와
같은 방식(system profile + 바꾼 key + 개체 설정)으로 plate 마다 slice 한 시간·무게, 개체마다 크기·바닥 면적·실제 설정,
그리고 flag 를 낸다. flag 는 미지원 plate, 개체에 둘 수 없는 key, mesh repair, 좁은 바닥 + 좁은 brim, support 를 끈
개체의 아래로 향한 면이다.

도구는 숫자만 낸다. 설정이 맞는지는 부품 카드로 판단한다.
1. 개체 목록으로 부품마다 카드를 만든다(2절 0단계).
2. 카드와 실제 설정을 3절 표로 맞춰 본다. 부품마다 "역할 · 현재 설정 · 판정 · 권고" 한 줄로 정리한다.
3. flag 는 카드와 함께 해석한다. 아래로 향한 면 면적에는 구멍 천장과 bridge 도 들어가므로 overhang 검사·뷰어로 확인한다.
4. 고칠 값은 3MF 가 아니라 생성 스크립트에 넣고 다시 만든다.

## 5. 기존 스크립트 이전

`inherits` 만 적은 user preset 을 CLI 에 넘기는 스크립트는 project_settings 에 CLI 기본값을 남긴다.
start G-code 는 46자이고, 가속 500, 외벽 60 mm/s, filament density 0, plate Cool Plate 가 된다. GUI 는 열 때 system
preset 으로 되돌려서 출력에는 문제가 없었지만, 파일만으로 slice 하면 시간이 2.5배로 나오고 무게는 0 g 이다
(`references/3mf-internals.md` "Profile 평탄화").

그런 스크립트를 고칠 일이 생기면 그때 `bambu3mf.py` 로 옮긴다. 옮길 때는 다음 순서를 따른다.
- 설정 dict(`PROCESS`·`*_OVERRIDE`)를 `Project.process`·`Part.params` 로 옮긴다.
- 출력 방향 표(`FACES`)를 `Part.down`·`turn` 으로 옮긴다.
- plate 구성을 `Plate` 로 옮긴다.
- `MACHINE` bed override, `PER_FILAMENT` 채우기, 개체 metadata regex 주입, 이름 되돌리기는 모듈이 하므로 지운다.
- 마지막 plate 빈자리 채우기, 고정 배치 간격 검사처럼 리포에만 있는 기능은 `make_3mf.py` 쪽에 남긴다.
- 옮긴 뒤 같은 STL 로 만든 이전·이후 3MF 를 GUI 에서 slice 해 시간·무게를 비교한다.

## 6. 스킬 유지 규칙

- 어느 리포에서든 `bambu3mf.py` 의 버그를 고치거나 범용 기능을 더하면 `templates/bambu3mf.py` 도 고치고, scratch 에서
  `templates/make_3mf.py` 로 단일 PLA·PLA+PETG·2색 조립 개체 세 경우를 실제로 build 해 확인한다.
- 새 재질·plate·부품 유형에서 얻은 기준값은 3절 표에 근거와 함께 추가한다.
- Bambu Studio 를 올린 뒤에는 템플릿을 한 번 돌려 본다. CLI 동작(assemble list, 변형 key 목록, `OBJECT_KEYS`)이
  바뀌었을 수 있다. 확인한 버전: Mac Bambu Studio 2.08.03.66.
- Bambu Studio 를 올리면 `references/print-settings.md` 의 profile 표를 다시 뽑아 대조한다.
- 이 스킬은 GitHub `woolimi/bambu-3mf` 로 공개돼 있다. 고치면 `~/vault/scripts/publish-skill.sh bambu-3mf "<영어 커밋 메시지>"` 로
  공개 리포에 반영한다. 특정 프로젝트 이름·경로·비공개 자료(Academy 강좌 본문 등)는 넣지 않는다.
