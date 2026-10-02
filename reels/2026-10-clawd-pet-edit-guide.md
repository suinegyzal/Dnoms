# Clawd Pet 릴스: 로컬 편집 가이드 (Mac)

> 대본·컷표: `reels/2026-10-clawd-pet-tts-adam.md` / 기획: `promo/2026-10-clawd-pet-campaign.md`
> 도구: `reels/tools/clawd_reel.py` (ffmpeg + Pillow) / 설정 예시: `reels/tools/reel.example.json`

결과물: **1080×1920, 30fps, 약 30초, 나레이션 -14 LUFS, 한글 자막과 강조자막이 입혀진 `clawd-reel.mp4`**

```
미디어 폴더/                ← 여기서 모든 명령 실행
├── etc/                    터치바·화면 녹화 클립
├── 녹음/                   직접 녹음한 나레이션
├── reel.json               컷 설정 (예시를 복사해서 수정)
├── work/                   중간 파일 (자동 생성, 지워도 됨)
└── clawd-reel.mp4          완성본
```

---

## 0. 한 번만 하는 세팅

터미널을 열고 순서대로 실행하세요.

```bash
# Homebrew (없을 때만)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# ffmpeg, GitHub CLI, Pillow
brew install ffmpeg gh
python3 -m pip install --user pillow
# "externally-managed-environment" 오류가 나면: python3 -m pip install --user --break-system-packages pillow

# 비공개 저장소 인증 (브라우저가 열리면 GitHub 로그인 → 승인)
gh auth login          # GitHub.com → HTTPS → Login with a web browser

# 저장소 받기
gh repo clone suinegyzal/Dnoms ~/Documents/Dnoms
cd ~/Documents/Dnoms && git checkout claude/busy-albattani-ov60tn
```

편의를 위해 명령 별칭을 만들어 두세요 (터미널 창마다 한 번).

```bash
alias reel="python3 ~/Documents/Dnoms/reels/tools/clawd_reel.py"
cd "미디어 폴더 경로"      # Finder에서 폴더를 터미널 창에 끌어다 놓으면 경로가 입력됨
```

---

## 1. 클립 확인하기

```bash
reel probe
```

- 폴더 안의 모든 영상·녹음의 **길이, 해상도, fps, HDR 여부**가 표로 나옵니다.
- `work/thumbs/`에 클립마다 썸네일이 생깁니다. Finder에서 훑어보고 어떤 클립이 컷표의 몇 번인지 정하세요.

### 컷 배정 (컷표 → reel.json 의 lines 순서)
| # | 나레이션 | 필요한 장면 |
|---|---|---|
| 1 | 요즘 영크크 사이에서, 구형 맥북이 유행이라던데? | 터치바 클로즈업, 타자 치는 Clawd |
| 2 | 터치바에, 얘가 살아서다. | Clawd 폴짝 |
| 3 | 클로드가 일하면, 얘도 일한다. | 위: Claude Code 화면 / 아래: 터치바 (`split`) |
| 4 | 책 읽고, 운동하고, 타자 친다. | 📖 → 🏋️ → 💻 클립 3개 |
| 5 | 허락이 필요하면, 손을 흔든다. | 손 흔들기 |
| 6 | 근데 일이 오래 걸리면… | 땀 흘리는 Clawd + 강조자막 `· 2분` |
| 7 | 나보다 더 화낸다. | 새빨개진 Clawd + 강조자막 `· 10분 💢` |
| 8 | 작업이 끝나면, 완료! | 완료 폴짝 |
| 9 | 쓰다듬고 간식 주면, 점점 친해진다. | 하트 연사 + 간식 (화면 녹화) |
| 10 | 최종 단계는, 영혼의 단짝. | 친밀도 표시 (화면 녹화) |
| 11 | 근데 터치바 없어도 된다. 화면 위에서도 산다. | 데스크톱 위 Clawd 여러 마리 |
| 12 | 무료다. 댓글에 클로드 남기면, 링크 보내준다. | 터치바 Clawd + 큰 CTA 자막 |

> 녹음에 "이 분… 오 분… 십 분." 줄을 넣었다면 6번과 7번 사이에 줄을 하나 추가하고 `· 2분`, `· 5분`, `· 10분 💢` 오버레이를 그 줄에 나눠 넣으세요 (예시는 아래 4번 참고).

---

## 2. reel.json 만들기

```bash
cp ~/Documents/Dnoms/reels/tools/reel.example.json reel.json
open -e reel.json      # 텍스트 편집기로 열기
```

수정할 곳:

1. **`"narration"`**: 녹음 파일 경로. 예: `"녹음/클로드펫_나레이션.m4a"`
2. **각 줄의 `"text"`**: **실제로 녹음한 말 그대로** 적으세요. 이 글자 수로 타이밍을 계산합니다.
   - `\n` = 자막 줄바꿈, `[[단어]]` = 노란색 강조
   - 녹음한 줄 수와 `lines` 개수가 같아야 합니다.
3. **각 줄의 `"clips"`**: `probe`에서 본 파일 경로와 시작 시점(`"in"`, 초).

### 클립 옵션
| 키 | 뜻 | 예 |
|---|---|---|
| `file` | 클립 경로 (reel.json 기준) | `"etc/IMG_1234.MOV"` |
| `in` | 클립에서 쓸 시작 시점(초) | `3.5` |
| `crop` | 화면 일부만 확대 `[x, y, 너비, 높이]` (0~1 비율) | `[0.1, 0.55, 0.8, 0.2]` |
| `speed` | 재생 속도 (2 = 2배속, 0.5 = 슬로우) | `1.5` |
| `max_h` | 가운데 영상 최대 높이(px, 기본 1100) | `900` |
| `layout` | `fit`(기본: 가운데 크게 + 흐린 배경) / `cover`(화면 가득) | `"cover"` |

- 한 줄에 클립을 여러 개 넣으면 그 줄 시간을 **균등하게 나눠** 이어 붙입니다 (4번 컷).
- 줄 단위 `"layout": "split"` + `"top"`, `"bottom"` = 위아래 분할 (3번 컷).

### 터치바 크롭 정하기 (중요)
폰으로 찍은 영상에는 키보드·책상까지 다 나오므로, **Clawd가 있는 터치바 부분만 잘라 가운데에 크게** 놓아야 합니다.

```bash
reel frame etc/IMG_1234.MOV 3      # 3초 지점 프레임 + 0.1 단위 격자
open work/frames/
```

격자 숫자를 읽어서 `crop`을 정하세요. 터치바 전체(가로 36:1)를 다 쓰면 너무 얇으니 **Clawd 주변만 3:1~2:1 비율**로 자르는 걸 추천합니다.
예: Clawd가 오른쪽 위 터치바에 있으면 `"crop": [0.45, 0.30, 0.45, 0.18]`

---

## 3. 녹음 정리 + 자막 타이밍

```bash
reel audio reel.json     # 앞뒤 무음 컷 → 저음 잡음 컷(80Hz) → 잡음 감소 → -14 LUFS (2-pass)
reel retime reel.json    # 녹음 쉼 위치에 맞춰 줄마다 시작·끝 시간 계산
```

`retime` 결과 예:
```
 1    0.00 ~   2.57  (2.57s)  요즘 영크크 사이에서 / 구형 맥북이 유행이라던데?
 2    2.57 ~   4.32  (1.75s)  터치바에 얘가 살아서다
 ...
```

- 글자 수로 예상 위치를 잡고, 녹음에서 **실제로 숨 쉰 곳(무음)** 에 맞춥니다. SRT는 `work/subs.srt`로도 저장됩니다.
- 어긋난 줄이 있으면 QuickTime으로 녹음을 들으며 그 줄이 시작하는 초를 확인하고, reel.json의 해당 줄에 `"start": 12.4`를 넣고 `retime`을 다시 실행하세요.
- 숨소리까지 잘리거나 앞 무음이 남으면 `"audio"`의 `silence_db`를 조정 (-50 = 덜 자름, -40 = 더 자름).
- 잡음 감소가 너무 세서 목소리가 뭉개지면 `denoise_db`를 -20, 잡음이 남으면 -30.

---

## 4. 강조자막 (타이머, CTA)

강조자막은 줄마다 `"overlays"`로 넣고, `from`/`to`는 **그 줄 길이에 대한 비율(0~1)** 입니다.

```json
{ "text": "근데 일이 오래 걸리면…",
  "clips": [...],
  "overlays": [{ "text": "· 2분", "style": "timer", "from": 0.15, "to": 1.0 }] },
{ "text": "[[나보다 더]] 화낸다",
  "clips": [...],
  "overlays": [{ "text": "· 10분 💢", "style": "timer", "color": "#FF3B30" }] }
```

`· 5분`까지 넣고 싶으면 6번 줄을 반으로 나누면 됩니다.
```json
"overlays": [
  { "text": "· 2분", "style": "timer", "from": 0.0, "to": 0.5 },
  { "text": "· 5분", "style": "timer", "from": 0.5, "to": 1.0 }
]
```

| style | 위치 | 용도 |
|---|---|---|
| `sub` | 영상 아래 | 나레이션 자막 (자동) |
| `timer` | 영상 위, 아주 크게 노란색 | `· 2분` → `· 10분 💢` |
| `hook` | 영상 위 | "무료 🎁" 같은 짧은 강조 |
| `cta` | 영상 아래, 반투명 박스 | 마지막 컷 "댓글에 "클로드" 남기면 링크 보내드림" |
| `tag` | 맨 위 작게 | "❤️ 친밀도: 낯가림" 같은 오픈 루프 |

- 마지막 줄은 `"hide_sub": true`로 나레이션 자막을 숨기고 CTA만 크게 보여줍니다.
- 위치·크기 조정: 오버레이에 `"y": 400`(세로 중심 px), `"size": 100`을 추가.
- 영상 전체에 계속 보이는 문구는 최상위 `"global_overlays": [{ "text": "❤️ 낯가림", "style": "tag", "start": 0, "end": 3 }]`.

---

## 5. 렌더링

```bash
reel build reel.json --draft    # 빠른 미리보기 → clawd-reel-draft.mp4 (화질 낮음)
open clawd-reel-draft.mp4
reel build reel.json            # 최종본 → clawd-reel.mp4
```

- 클립·자막·오버레이를 고칠 때마다 `build`만 다시 돌리면 됩니다. 녹음이나 `text`를 바꿨다면 `retime`부터.
- 처음부터 한 번에: `reel all reel.json`
- (선택) BGM: reel.json 최상위에 `"bgm": "bgm/chiptune.mp3", "bgm_db": -24` → 나레이션 아래로 깔리고 전체를 다시 -14 LUFS로 맞춥니다.

### 레이아웃 (1080×1920)
```
┌──────────────┐
│   · 10분 💢   │  ← timer / hook (y≈430)
│              │
│▓▓▓ 터치바 ▓▓▓│  ← 가운데 크게 (fit), 뒤는 같은 영상을 흐리게
│              │
│ 나보다 더 화낸다 │  ← sub (y≈1470)
└──────────────┘
```
인스타 하단 UI(캡션·버튼)가 아래쪽 ~300px를 가리므로 자막은 그 위에 둡니다.

---

## 6. 업로드 전 체크

- [ ] 길이 28~33초, 첫 프레임부터 터치바 Clawd가 보임 (3초 훅)
- [ ] 자막이 녹음과 글자까지 일치 (맞춤법·띄어쓰기)
- [ ] `· 2분` → `· 10분 💢`이 6~7번 컷에 보임
- [ ] 마지막 컷 CTA: 댓글에 "클로드" 남기면 링크 보내드림
- [ ] 폰 이어폰으로 들었을 때 소리가 작거나 찢어지지 않음
- [ ] 캡션에 비공식 팬 프로젝트 고지 (기획서 4번 캡션 그대로)

---

## 문제 해결

| 증상 | 해결 |
|---|---|
| 아이폰 영상 색이 물 빠진 듯 회색 | HDR 영상입니다. 도구가 자동으로 톤매핑하지만 `zscale` 필터가 없으면 건너뜁니다. 사진 앱에서 내보내기 → "호환성 우선"으로 다시 저장하거나, 다음부터 카메라 설정 → 포맷 → HDR 비디오 끄기 |
| 💢 🎁 같은 이모지가 안 보임 | reel.json에 `"emoji_font": "/System/Library/Fonts/Apple Color Emoji.ttc"` 지정. 그래도 안 되면 이모지를 빼고 글자만 사용 |
| 자막 폰트를 바꾸고 싶음 | `"font": "~/Library/Fonts/Pretendard-ExtraBold.otf"`처럼 절대 경로 지정 (기본: Apple SD Gothic Neo 굵은 체) |
| 클립이 짧아서 컷이 모자람 | 자동 반복 재생됩니다. 어색하면 `"speed": 0.8`로 늘리거나 다른 클립 추가 |
| 컷이 말보다 살짝 늦게/빠르게 바뀜 | 해당 줄에 `"start"`를 0.1초 단위로 조정 후 `retime` → `build` |
| `ffmpeg 실행 실패` | 위에 출력된 로그의 마지막 줄을 Claude에게 붙여넣기 |

---

## Claude Code로 맡기기 (선택)

Mac에서 미디어 폴더를 열어 Claude Code(데스크톱 앱 또는 `claude`)를 실행하고 아래를 붙여넣으면, 위 과정을 대신 진행합니다.

```
~/Documents/Dnoms/reels/2026-10-clawd-pet-edit-guide.md 가이드대로 이 폴더의 etc(영상)와 녹음 폴더로
Clawd Pet 릴스를 만들어줘. reel probe로 클립 목록과 썸네일을 먼저 보여주고, 어떤 클립이 몇 번 컷인지
애매한 건 나한테 물어봐. 자막은 녹음 내용에 맞추고, 2분/10분은 강조자막으로. 결과는 clawd-reel.mp4.
```
