import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 112
FPS = 30
SLIDE_S = 3.0
HOLD_S = 2.6
FADE_S = SLIDE_S - HOLD_S
N_SLIDES = 4
LOOP_S = SLIDE_S * N_SLIDES
TOTAL_FRAMES = int(LOOP_S * FPS)

FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
FONT_REG = r"C:\Windows\Fonts\malgun.ttf"

logo_font = ImageFont.truetype(FONT_BOLD, 28)
tag_font = ImageFont.truetype(FONT_BOLD, 20)
cta_font = ImageFont.truetype(FONT_BOLD, 20)
adtag_font = ImageFont.truetype(FONT_BOLD, 13)

SLIDES = [
    "글로벌 No.1 코스메틱 R&D·제조 파트너",
    "전 세계 3,500개 브랜드가 선택한 기술력",
    "당신의 여행 피부 데이터로 다음 혁신을 만듭니다",
    "글로벌 코스메틱 R&D의 시작, 코스맥스와 함께",
]


def lerp(a, b, t):
    return a + (b - a) * t


def gradient_bg(shift=0.0):
    """135deg diagonal gradient navy -> blue, matching the CSS banner colors."""
    c0 = np.array([13, 27, 61], dtype=np.float32)     # #0d1b3d
    c1 = np.array([28, 49, 112], dtype=np.float32)    # #1c3170
    c2 = np.array([46, 80, 184], dtype=np.float32)    # #2e50b8
    xx, yy = np.meshgrid(np.linspace(0, 1, W), np.linspace(0, 1, H))
    diag = (xx + yy) / 2.0
    diag = np.clip(diag + shift, 0, 1)
    img = np.zeros((H, W, 3), dtype=np.float32)
    m1 = diag < 0.55
    t1 = np.clip(diag / 0.55, 0, 1)
    m2 = ~m1
    t2 = np.clip((diag - 0.55) / 0.45, 0, 1)
    for ch in range(3):
        img[..., ch] = np.where(m1, lerp(c0[ch], c1[ch], t1), lerp(c1[ch], c2[ch], t2))
    return img


BG = gradient_bg()


def add_sheen(frame_bgr, t):
    period = 4.0
    phase = (t % period) / period
    band_center = lerp(-0.3, 1.3, phase)
    xx = np.linspace(0, 1, W)
    dist = np.abs(xx - band_center)
    intensity = np.clip(1 - dist / 0.18, 0, 1) ** 2 * 40
    sheen_row = intensity[np.newaxis, :, np.newaxis]
    out = frame_bgr.astype(np.float32) + sheen_row
    return np.clip(out, 0, 255)


def render_slide_layer(text):
    """Render one slide's text (logo + tagline) onto a transparent RGBA layer."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    pad_left = 34
    d.text((pad_left, 26), "COSMAX", font=logo_font, fill=(255, 255, 255, 255))
    d.text((pad_left, 58), text, font=tag_font, fill=(235, 240, 255, 255))
    return layer


def compose_frame(t):
    idx = int(t // SLIDE_S) % N_SLIDES
    seg = t % SLIDE_S
    base_rgb = np.array(Image.fromarray(BG.astype(np.uint8), "RGB"))
    base = Image.fromarray(base_rgb, "RGB").convert("RGBA")

    if seg < HOLD_S:
        layer = render_slide_layer(SLIDES[idx])
        base = Image.alpha_composite(base, layer)
    else:
        blend = (seg - HOLD_S) / FADE_S
        cur_layer = render_slide_layer(SLIDES[idx])
        nxt_layer = render_slide_layer(SLIDES[(idx + 1) % N_SLIDES])
        cur_arr = np.array(cur_layer).astype(np.float32)
        nxt_arr = np.array(nxt_layer).astype(np.float32)
        cur_arr[..., 3] *= max(0.0, 1 - blend)
        nxt_arr[..., 3] *= max(0.0, blend)
        cur_layer = Image.fromarray(cur_arr.astype(np.uint8), "RGBA")
        nxt_layer = Image.fromarray(nxt_arr.astype(np.uint8), "RGBA")
        base = Image.alpha_composite(base, cur_layer)
        base = Image.alpha_composite(base, nxt_layer)

    # AD tag pill / CTA / progress bar — drawn on their OWN transparent layer, then
    # alpha_composite'd onto base in one shot. PIL's ImageDraw always *pokes* pixel
    # values (even in "RGBA" mode) instead of blending, so a translucent fill drawn
    # straight onto `base` would overwrite the destination alpha too and come out
    # fully opaque, hiding the white "AD" text drawn on top of it. Compositing a
    # separate layer is the only way to get real translucency here.
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rounded_rectangle((16, 6, 58, 23), radius=8, fill=(255, 255, 255, 60))
    blink_on = (t % 1.2) < 0.6
    dot_color = (255, 77, 109, 255) if blink_on else (255, 77, 109, 70)
    d.ellipse((22, 11, 28, 17), fill=dot_color)
    d.text((32, 7), "AD", font=adtag_font, fill=(255, 255, 255, 255))

    # CTA pill on the right, vertically centered
    cta_text = "자세히 보기 →"
    bbox = d.textbbox((0, 0), cta_text, font=cta_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cta_w, cta_h = tw + 36, 40
    cta_x0 = W - cta_w - 28
    cta_y0 = (H - cta_h) // 2
    d.rounded_rectangle((cta_x0, cta_y0, cta_x0 + cta_w, cta_y0 + cta_h), radius=cta_h // 2, fill=(255, 255, 255, 255))
    d.text((cta_x0 + 18, cta_y0 + (cta_h - th) // 2 - bbox[1]), cta_text, font=cta_font, fill=(36, 64, 143, 255))

    # bottom progress bar for current slide segment
    prog = min(seg / SLIDE_S, 1.0)
    d.rectangle((0, H - 3, W, H), fill=(255, 255, 255, 45))
    d.rectangle((0, H - 3, int(W * prog), H), fill=(255, 255, 255, 230))

    base = Image.alpha_composite(base, overlay)

    rgb = np.array(base.convert("RGB")).astype(np.float32)
    rgb = add_sheen(rgb, t)
    bgr = cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
    return bgr


def write_video(path, fourcc_str):
    fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
    writer = cv2.VideoWriter(path, fourcc, FPS, (W, H))
    if not writer.isOpened():
        print(f"FAILED to open writer for {fourcc_str}")
        return False
    for i in range(TOTAL_FRAMES):
        t = i / FPS
        frame = compose_frame(t)
        writer.write(frame)
    writer.release()
    return True


if __name__ == "__main__":
    import sys
    out_path = sys.argv[1] if len(sys.argv) > 1 else "cosmax_banner.mp4"
    fourcc_str = sys.argv[2] if len(sys.argv) > 2 else "avc1"
    ok = write_video(out_path, fourcc_str)
    print("wrote:", out_path, "ok:", ok)
