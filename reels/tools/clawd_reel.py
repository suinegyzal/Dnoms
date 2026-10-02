#!/usr/bin/env python3
"""Clawd Pet 릴스 편집 도구 (ffmpeg + Pillow).

사용법 (미디어 폴더에서 실행):
  python3 clawd_reel.py probe [폴더]      클립 목록 + 썸네일(work/thumbs) 만들기
  python3 clawd_reel.py frame 클립 초      크롭 좌표용 격자 프레임(work/frames) 뽑기
  python3 clawd_reel.py audio reel.json   녹음 앞뒤 무음 자르기 + 잡음 감소 + -14 LUFS
  python3 clawd_reel.py retime reel.json  녹음에 맞춰 자막 타이밍 계산 (work/subs.srt)
  python3 clawd_reel.py build reel.json   9:16 릴스 렌더링 (--draft 빠른 미리보기)
  python3 clawd_reel.py all reel.json     audio → retime → build
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys

W, H, FPS = 1080, 1920, 30
MEDIA_EXT = {".mov", ".mp4", ".m4v", ".m4a", ".wav", ".mp3", ".aac", ".caf", ".aiff", ".aif"}
HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}

KO_FONTS = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
EMOJI_FONTS = [
    "/System/Library/Fonts/Apple Color Emoji.ttc",
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
]

# 자막 스타일. 오버레이마다 size/color/y 를 덮어쓸 수 있음.
STYLES = {
    "sub":   {"size": 64,  "color": "#FFFFFF", "stroke": 8, "y": 1470, "box": None},
    "timer": {"size": 130, "color": "#FFD400", "stroke": 10, "y": 430, "box": None},
    "cta":   {"size": 88,  "color": "#FFFFFF", "stroke": 10, "y": 1480, "box": "#000000B0"},
    "hook":  {"size": 84,  "color": "#FFFFFF", "stroke": 9, "y": 420, "box": None},
    "tag":   {"size": 46,  "color": "#FFFFFF", "stroke": 0, "y": 230, "box": "#00000099"},
}
HIGHLIGHT = "#FFD400"


# ---------------------------------------------------------------- 공통

def die(msg):
    print(f"\n[오류] {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd, quiet=True):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(" ".join(f"'{c}'" if " " in c else c for c in cmd), file=sys.stderr)
        print(p.stderr[-3000:], file=sys.stderr)
        die("ffmpeg 실행 실패 (위 로그 참고)")
    if not quiet:
        print(p.stderr)
    return p


def need_tools():
    for t in ("ffmpeg", "ffprobe"):
        if not shutil.which(t):
            die(f"{t} 가 없습니다. 맥: brew install ffmpeg")


def ffprobe(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                        "-show_streams", "-show_format", path], capture_output=True, text=True)
    if p.returncode != 0:
        return None
    return json.loads(p.stdout)


def media_info(path):
    j = ffprobe(path)
    if not j:
        return None
    info = {"duration": float(j["format"].get("duration", 0) or 0), "video": None, "audio": False}
    for s in j["streams"]:
        if s["codec_type"] == "audio":
            info["audio"] = True
        if s["codec_type"] == "video" and info["video"] is None and s.get("disposition", {}).get("attached_pic") != 1:
            w, h = s.get("width", 0), s.get("height", 0)
            rot = 0
            for sd in s.get("side_data_list", []) or []:
                if "rotation" in sd:
                    rot = int(sd["rotation"])
            rot = int(s.get("tags", {}).get("rotate", rot))
            if abs(rot) % 180 == 90:
                w, h = h, w
            num, den = (s.get("avg_frame_rate", "0/1") + "/1").split("/")[:2]
            fps = float(num) / float(den) if float(den) else 0
            info["video"] = {"w": w, "h": h, "fps": round(fps, 2),
                             "hdr": s.get("color_transfer") in HDR_TRANSFERS}
    return info


def load_cfg(path):
    if not os.path.exists(path):
        die(f"{path} 가 없습니다. reel.example.json 을 복사해서 만드세요.")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    base = os.path.dirname(os.path.abspath(path))
    cfg["_base"] = base
    cfg["_work"] = os.path.join(base, cfg.get("work_dir", "work"))
    os.makedirs(cfg["_work"], exist_ok=True)
    return cfg


def P(cfg, rel):
    rel = os.path.expanduser(rel)
    return rel if os.path.isabs(rel) else os.path.join(cfg["_base"], rel)


# ---------------------------------------------------------------- probe / frame

def cmd_probe(folder="."):
    need_tools()
    thumbs = os.path.join(folder, "work", "thumbs")
    os.makedirs(thumbs, exist_ok=True)
    rows = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "work" and not d.startswith(".")]
        for fn in sorted(files):
            if os.path.splitext(fn)[1].lower() not in MEDIA_EXT:
                continue
            path = os.path.join(root, fn)
            info = media_info(path)
            if not info:
                continue
            rel = os.path.relpath(path, folder)
            v = info["video"]
            if v:
                kind = f"영상 {v['w']}x{v['h']} {v['fps']}fps" + (" HDR" if v["hdr"] else "")
                t = min(info["duration"] / 2, 3)
                out = os.path.join(thumbs, rel.replace(os.sep, "__") + ".jpg")
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", path,
                                "-frames:v", "1", "-vf", "scale=480:-2", out])
            else:
                kind = "오디오"
            rows.append((rel, info["duration"], kind))
    if not rows:
        die("미디어 파일을 못 찾았습니다.")
    print(f"{'파일':<50} {'길이':>7}  종류")
    for rel, d, kind in rows:
        print(f"{rel:<50} {d:7.1f}s  {kind}")
    print(f"\n썸네일: {thumbs}  (Finder에서 열어 어떤 컷인지 확인)")


def cmd_frame(clip, t="1"):
    need_tools()
    from PIL import Image, ImageDraw
    os.makedirs("work/frames", exist_ok=True)
    out = os.path.join("work/frames", os.path.basename(clip) + f"_{t}s.png")
    run(["ffmpeg", "-y", "-ss", str(t), "-i", clip, "-frames:v", "1", out])
    im = Image.open(out).convert("RGB")
    d = ImageDraw.Draw(im)
    font = get_font(max(18, im.width // 60))
    for i in range(1, 10):
        x, y = im.width * i // 10, im.height * i // 10
        d.line([(x, 0), (x, im.height)], fill=(255, 0, 255), width=2)
        d.line([(0, y), (im.width, y)], fill=(255, 0, 255), width=2)
        d.text((x + 4, 4), f"{i/10:.1f}", fill=(255, 255, 0), font=font)
        d.text((4, y + 4), f"{i/10:.1f}", fill=(255, 255, 0), font=font)
    im.save(out)
    print(f"{out}\n격자 숫자(0~1)를 보고 crop: [x, y, 너비, 높이] 를 정하세요. 예: [0.1, 0.55, 0.8, 0.2]")


# ---------------------------------------------------------------- 오디오

def cmd_audio(cfg):
    need_tools()
    src = P(cfg, cfg["narration"])
    if not os.path.exists(src):
        die(f"녹음 파일이 없습니다: {src}")
    a = cfg.get("audio", {})
    sil = a.get("silence_db", -45)
    lufs = a.get("lufs", -14)
    nr = a.get("denoise_db", -25)
    trim = (f"silenceremove=start_periods=1:start_threshold={sil}dB:start_silence=0.08,"
            f"areverse,silenceremove=start_periods=1:start_threshold={sil}dB:start_silence=0.25,areverse")
    clean = f"{trim},highpass=f=80,afftdn=nf={nr}"
    tmp = os.path.join(cfg["_work"], "narration_trim.wav")
    run(["ffmpeg", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "48000", "-af", clean, tmp])
    # loudnorm 2-pass
    p = run(["ffmpeg", "-i", tmp, "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
    m = json.loads(p.stderr[p.stderr.rfind("{"):p.stderr.rfind("}") + 1])
    ln = (f"loudnorm=I={lufs}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    out = os.path.join(cfg["_work"], "narration_clean.wav")
    run(["ffmpeg", "-y", "-i", tmp, "-af", ln, "-ar", "48000", out])
    before, after = media_info(src)["duration"], media_info(out)["duration"]
    p = run(["ffmpeg", "-i", out, "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    got = json.loads(p.stderr[p.stderr.rfind("{"):p.stderr.rfind("}") + 1])["input_i"]
    print(f"녹음 정리 완료: {out}\n  길이 {before:.2f}s → {after:.2f}s, 음량 {got} LUFS (목표 {lufs})")


# ---------------------------------------------------------------- 자막 타이밍

def silences(path, db, dur):
    p = run(["ffmpeg", "-i", path, "-af", f"silencedetect=noise={db}dB:d={dur}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    return list(zip(starts, ends))


def weight(text):
    t = re.sub(r"\[\[|\]\]", "", text)
    return len(re.sub(r"[\s\W]", "", t)) + 2 * len(re.findall(r"[,…]|\.\.\.", t)) + 1


def cmd_retime(cfg):
    need_tools()
    audio = os.path.join(cfg["_work"], "narration_clean.wav")
    if not os.path.exists(audio):
        cmd_audio(cfg)
    total = media_info(audio)["duration"]
    lines = cfg["lines"]
    n = len(lines)
    a = cfg.get("audio", {})
    gaps = silences(audio, a.get("gap_db", -35), a.get("gap_min", 0.18))
    # 글자 수 비례로 예상 경계를 잡고, 가장 가까운 쉼(무음 구간)에 순서대로 맞춘다 (DP)
    ws = [weight(l["text"]) for l in lines]
    acc, est = 0, []
    for w in ws[:-1]:
        acc += w
        est.append(total * acc / sum(ws))
    k, g = len(est), len(gaps)
    cut = [e for e in est]
    if g >= k > 0:
        INF = float("inf")
        snap = [gp[1] - 0.08 for gp in gaps]  # 다음 말 시작 직전
        dp = [[INF] * (g + 1) for _ in range(k + 1)]
        choice = [[False] * (g + 1) for _ in range(k + 1)]
        for j in range(g + 1):
            dp[0][j] = 0
        for i in range(1, k + 1):
            for j in range(1, g + 1):
                skip = dp[i][j - 1]
                take = dp[i - 1][j - 1] + abs(snap[j - 1] - est[i - 1])
                if take <= skip:
                    dp[i][j], choice[i][j] = take, True
                else:
                    dp[i][j] = skip
        i, j = k, g
        while i > 0:
            if choice[i][j]:
                cut[i - 1] = snap[j - 1]
                i -= 1
            j -= 1
    else:
        print(f"[주의] 쉼이 {g}개라 줄 수({n})보다 적어서 글자 수 비례로만 나눴습니다.")
    for i, l in enumerate(lines):  # 수동 지정값 우선
        if i > 0 and "start" in l:
            cut[i - 1] = float(l["start"])
    tail = cfg.get("tail", 0.8)
    bounds = [0.0] + cut + [total + tail]
    timing = [[round(bounds[i], 3), round(bounds[i + 1], 3)] for i in range(n)]
    with open(os.path.join(cfg["_work"], "timing.json"), "w") as f:
        json.dump(timing, f)
    srt = []
    for i, (l, (s, e)) in enumerate(zip(lines, timing), 1):
        srt.append(f"{i}\n{srt_t(s)} --> {srt_t(e)}\n{strip_marks(l['text'])}\n")
    with open(os.path.join(cfg["_work"], "subs.srt"), "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    print(f"녹음 {total:.2f}s, 릴스 전체 {total + tail:.2f}s\n")
    for i, (l, (s, e)) in enumerate(zip(lines, timing), 1):
        print(f"{i:>2}  {s:6.2f} ~ {e:6.2f}  ({e - s:4.2f}s)  {strip_marks(l['text']).replace(chr(10), ' / ')}")
    print(f"\nSRT: {os.path.join(cfg['_work'], 'subs.srt')}")
    print('어긋난 줄은 reel.json 의 해당 줄에 "start": 초 를 넣고 다시 retime 하세요.')
    return timing


def srt_t(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def strip_marks(t):
    return t.replace("[[", "").replace("]]", "")


# ---------------------------------------------------------------- 텍스트 PNG

_font_cache = {}


def get_font(size, path=None):
    from PIL import ImageFont
    key = (size, path)
    if key in _font_cache:
        return _font_cache[key]
    cands = [path] if path else KO_FONTS
    for fp in cands:
        if not fp or not os.path.exists(fp):
            continue
        best = None
        for idx in range(0, 20):
            try:
                f = ImageFont.truetype(fp, size, index=idx)
            except OSError:
                break
            fam, sty = f.getname()
            score = (("KR" in fam) or ("Gothic" in fam)) * 10 + \
                {"Heavy": 5, "ExtraBold": 5, "Black": 4, "Bold": 4, "SemiBold": 2}.get(sty, 0)
            if best is None or score > best[0]:
                best = (score, f)
        if best:
            _font_cache[key] = best[1]
            return best[1]
    die("한글 폰트를 못 찾았습니다. reel.json 에 \"font\": \"폰트 경로\" 를 지정하세요.")


_emoji_font = []


def emoji_font(cfg_path=None):
    from PIL import ImageFont
    if _emoji_font:
        return _emoji_font[0]
    for fp in ([cfg_path] if cfg_path else []) + EMOJI_FONTS:
        if fp and os.path.exists(fp):
            for s in (160, 137, 109, 96, 64):
                try:
                    _emoji_font.append(ImageFont.truetype(fp, s))
                    return _emoji_font[0]
                except OSError:
                    continue
    _emoji_font.append(None)
    return None


def is_emoji(ch):
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or o in (0x200D, 0xFE0F, 0x2764)


def runs_of(line):
    """[(text, is_emoji, highlight)]"""
    out, hl = [], False
    for part in re.split(r"(\[\[|\]\])", line):
        if part == "[[":
            hl = True
            continue
        if part == "]]":
            hl = False
            continue
        buf, cur = "", None
        for ch in part:
            e = is_emoji(ch)
            if cur is not None and e != cur and not (cur and ord(ch) in (0x200D, 0xFE0F)):
                out.append((buf, cur, hl))
                buf = ""
            buf += ch
            cur = e if not (cur and ord(ch) in (0x200D, 0xFE0F)) else cur
        if buf:
            out.append((buf, cur, hl))
    return out


def render_text_png(text, style, out, cfg):
    from PIL import Image, ImageDraw
    st = dict(STYLES[style["style"]])
    st.update({k: v for k, v in style.items() if k in ("size", "color", "y", "stroke", "box")})
    font = get_font(st["size"], cfg.get("font") and P(cfg, cfg["font"]))
    ef = emoji_font(cfg.get("emoji_font") and P(cfg, cfg["emoji_font"]))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lines = text.split("\n")
    lh = int(st["size"] * 1.28)
    # 각 줄 너비 측정
    def measure(line):
        wsum = 0
        for t, e, _ in runs_of(line):
            if e:
                wsum += int(st["size"] * 1.15) * len([c for c in t if ord(c) not in (0x200D, 0xFE0F)]) if ef else 0
            else:
                wsum += int(font.getlength(t))
        return wsum
    widths = [measure(l) for l in lines]
    total_h = lh * len(lines)
    top = int(st["y"] - total_h / 2)
    d = ImageDraw.Draw(img)
    if st.get("box"):
        pad = int(st["size"] * 0.45)
        bw = max(widths) + pad * 2
        c = st["box"].lstrip("#")
        rgba = tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + ((int(c[6:8], 16),) if len(c) == 8 else (255,))
        d.rounded_rectangle([(W - bw) / 2, top - pad * 0.6, (W + bw) / 2, top + total_h + pad * 0.4],
                            radius=int(st["size"] * 0.4), fill=rgba)
    for li, (line, lw) in enumerate(zip(lines, widths)):
        x = (W - lw) // 2
        y = top + li * lh
        for t, e, hl in runs_of(line):
            if e:
                if not ef:
                    continue
                for ch in re.findall(r".(?:️)?(?:‍.(?:️)?)*", t):
                    g = Image.new("RGBA", (ef.size * 2, ef.size * 2), (0, 0, 0, 0))
                    ImageDraw.Draw(g).text((0, 0), ch, font=ef, embedded_color=True)
                    bb = g.getbbox()
                    if not bb:
                        continue
                    g = g.crop(bb)
                    es = int(st["size"] * 1.05)
                    g = g.resize((int(g.width * es / g.height), es), Image.LANCZOS)
                    img.alpha_composite(g, (x + int(st["size"] * 0.05), y + int(st["size"] * 0.12)))
                    x += int(st["size"] * 1.15)
            else:
                color = HIGHLIGHT if hl else st["color"]
                d.text((x, y), t, font=font, fill=color,
                       stroke_width=st["stroke"], stroke_fill="#000000")
                x += int(font.getlength(t))
    img.save(out)


# ---------------------------------------------------------------- 영상

def tonemap_filter():
    p = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
    if " zscale " not in p.stdout:
        return ""
    return ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
            "tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")


def clip_chain(cfg, clip, tm):
    """클립별 앞단 필터: HDR 톤매핑, 크롭, 속도."""
    info = media_info(P(cfg, clip["file"]))
    pre = tm if (info and info["video"] and info["video"]["hdr"]) else ""
    crop = ""
    if clip.get("crop"):
        x, y, w, h = clip["crop"]
        crop = f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},"
    speed = float(clip.get("speed", 1))
    sp = f"setpts=PTS/{speed}," if speed != 1 else ""
    return pre, crop, sp


def segment(cfg, i, line, t0, t1, tm, draft):
    work = cfg["_work"]
    out = os.path.join(work, f"seg_{i:02}.mp4")
    dur = t1 - t0
    layout = line.get("layout", "fit")
    inputs, filt = [], []
    fps = f"fps={FPS}"

    def add_input(clip, length):
        f = P(cfg, clip["file"])
        if not os.path.exists(f):
            die(f"{i + 1}번 줄 클립이 없습니다: {f}")
        speed = float(clip.get("speed", 1))
        inputs.extend(["-stream_loop", "-1", "-ss", str(clip.get("in", 0)), "-t", f"{length * speed + 0.5:.3f}", "-i", f])
        return inputs.count("-i") - 1

    if layout == "split":
        top, bot = line["top"], line["bottom"]
        a, b = add_input(top, dur), add_input(bot, dur)
        p1, c1, s1 = clip_chain(cfg, top, tm)
        p2, c2, s2 = clip_chain(cfg, bot, tm)
        bg = f"[{b}:v]{p2}{c2}{s2}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.25,{fps},setsar=1[bg]"
        fa = f"[{a}:v]{p1}{c1}{s1}scale={W}:860:force_original_aspect_ratio=decrease,{fps},setsar=1[ta]"
        fb = f"[{b}:v]{p2}{c2}{s2}scale={W}:640:force_original_aspect_ratio=decrease,{fps},setsar=1[tb]"
        filt = [bg, fa, fb,
                "[bg][ta]overlay=(W-w)/2:(940-h)/2+120[x]",
                "[x][tb]overlay=(W-w)/2:1000+(640-h)/2,trim=duration={:.3f}[v]".format(dur)]
    else:
        clips = line["clips"]
        parts = []
        each = dur / len(clips)
        for ci, clip in enumerate(clips):
            idx = add_input(clip, each)
            pre, crop, sp = clip_chain(cfg, clip, tm)
            src = f"[{idx}:v]{pre}{crop}{sp}split[s{ci}a][s{ci}b]"
            if (clip.get("layout") or layout) == "cover":
                filt += [f"[{idx}:v]{pre}{crop}{sp}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},{fps},setsar=1,trim=duration={each:.3f},setpts=PTS-STARTPTS[p{ci}]"]
            else:
                maxh = int(clip.get("max_h", 1100))
                filt += [src,
                         f"[s{ci}a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.25,{fps},setsar=1[bg{ci}]",
                         f"[s{ci}b]scale={W}:{maxh}:force_original_aspect_ratio=decrease,{fps},setsar=1[fg{ci}]",
                         f"[bg{ci}][fg{ci}]overlay=(W-w)/2:(H-h)/2+{int(clip.get('y_offset', -40))},trim=duration={each:.3f},setpts=PTS-STARTPTS[p{ci}]"]
            parts.append(f"[p{ci}]")
        filt.append(f"{''.join(parts)}concat=n={len(parts)}:v=1:a=0[v]")
    preset = ["-preset", "ultrafast", "-crf", "30"] if draft else ["-preset", "medium", "-crf", "18"]
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[v]",
         "-t", f"{dur:.3f}", "-an", "-c:v", "libx264", *preset, "-pix_fmt", "yuv420p", "-r", str(FPS), out])
    return out


def cmd_build(cfg, draft=False):
    need_tools()
    try:
        import PIL  # noqa: F401
    except ImportError:
        die("Pillow 가 필요합니다: python3 -m pip install pillow")
    work = cfg["_work"]
    audio = os.path.join(work, "narration_clean.wav")
    tpath = os.path.join(work, "timing.json")
    if not os.path.exists(audio):
        cmd_audio(cfg)
    if not os.path.exists(tpath):
        cmd_retime(cfg)
    timing = json.load(open(tpath))
    lines = cfg["lines"]
    if len(timing) != len(lines):
        timing = cmd_retime(cfg)
    total = timing[-1][1]
    tm = tonemap_filter()

    print("1/3 컷 렌더링")
    segs = []
    for i, (line, (t0, t1)) in enumerate(zip(lines, timing)):
        print(f"  {i + 1:>2}/{len(lines)} {t1 - t0:4.2f}s  {strip_marks(line['text']).splitlines()[0]}")
        segs.append(segment(cfg, i, line, t0, t1, tm, draft))
    lst = os.path.join(work, "segs.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(s)}'\n" for s in segs)
    video = os.path.join(work, "video.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video])

    print("2/3 자막 이미지")
    overlays = []  # (png, start, end)
    n = 0
    for i, (line, (t0, t1)) in enumerate(zip(lines, timing)):
        span = t1 - t0
        if not line.get("hide_sub"):
            png = os.path.join(work, f"txt_{n:03}.png"); n += 1
            st = {"style": "sub"}
            if line.get("layout") == "split":
                st["y"] = 1760
            st.update(line.get("sub_style", {}))
            render_text_png(line["text"], st, png, cfg)
            overlays.append((png, t0, t1))
        for ov in line.get("overlays", []):
            png = os.path.join(work, f"txt_{n:03}.png"); n += 1
            render_text_png(ov["text"], ov, png, cfg)
            s = t0 + span * float(ov.get("from", 0))
            e = t0 + span * float(ov.get("to", 1))
            if ov.get("hold_to_end"):
                e = total
            overlays.append((png, s, e))
    for ov in cfg.get("global_overlays", []):
        png = os.path.join(work, f"txt_{n:03}.png"); n += 1
        render_text_png(ov["text"], ov, png, cfg)
        overlays.append((png, float(ov.get("start", 0)), float(ov.get("end", total))))

    print("3/3 합치기 + 오디오")
    inputs = ["-i", video, "-i", audio]
    bgm = cfg.get("bgm")
    if bgm:
        inputs += ["-stream_loop", "-1", "-i", P(cfg, bgm)]
    for png, _, _ in overlays:
        inputs += ["-i", png]
    first_png = 3 if bgm else 2
    chain, cur = [], "[0:v]"
    for k, (png, s, e) in enumerate(overlays):
        nxt = f"[o{k}]"
        chain.append(f"{cur}[{first_png + k}:v]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})'{nxt}")
        cur = nxt
    chain.append(f"{cur}format=yuv420p[vout]")
    fade = f"afade=t=out:st={total - 0.4:.3f}:d=0.4"
    if bgm:
        vol = cfg.get("bgm_db", -24)
        chain.append(f"[1:a]apad,atrim=0:{total:.3f}[nar]")
        chain.append(f"[2:a]volume={vol}dB,atrim=0:{total:.3f}[bg]")
        chain.append(f"[nar][bg]amix=inputs=2:normalize=0,loudnorm=I={cfg.get('audio', {}).get('lufs', -14)}:TP=-1.5,{fade}[aout]")
    else:
        chain.append(f"[1:a]apad,atrim=0:{total:.3f},{fade}[aout]")
    out = P(cfg, cfg.get("output", "clawd-reel.mp4"))
    if draft:
        out = os.path.splitext(out)[0] + "-draft.mp4"
    preset = ["-preset", "ultrafast", "-crf", "30"] if draft else ["-preset", "slow", "-crf", "18"]
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(chain), "-map", "[vout]", "-map", "[aout]",
         "-t", f"{total:.3f}", "-c:v", "libx264", *preset, "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out])
    print(f"\n완성: {out}  ({total:.1f}s, {W}x{H})")
    if not 25 <= total <= 35:
        print("[참고] 기획 길이(약 30초)와 차이가 큽니다. 녹음 속도나 tail 값을 확인하세요.")


# ---------------------------------------------------------------- main

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    c = a[0]
    if c == "probe":
        cmd_probe(a[1] if len(a) > 1 else ".")
    elif c == "frame":
        if len(a) < 2:
            die("사용법: frame 클립경로 초")
        cmd_frame(a[1], a[2] if len(a) > 2 else "1")
    elif c in ("audio", "retime", "build", "all"):
        cfg = load_cfg(a[1] if len(a) > 1 and not a[1].startswith("-") else "reel.json")
        draft = "--draft" in a
        if c == "audio":
            cmd_audio(cfg)
        elif c == "retime":
            cmd_retime(cfg)
        elif c == "build":
            cmd_build(cfg, draft)
        else:
            cmd_audio(cfg)
            cmd_retime(cfg)
            cmd_build(cfg, draft)
    else:
        die(f"모르는 명령: {c}")


if __name__ == "__main__":
    main()
