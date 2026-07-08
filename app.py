"""
식스센스 TravelMax+
여행지 기후·수질·자외선 데이터를 내 피부 타입과 매칭해주는
게임풍 여행 뷰티 케어 웹앱 MVP
"""
import base64
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="TravelMax+", page_icon="🧳", layout="wide")

ASSETS = Path(__file__).parent / "assets"


@st.cache_data(show_spinner=False)
def asset_data_uri(filename, mime):
    """Read a bundled asset and return it as a base64 data URI for inline HTML."""
    raw = (ASSETS / filename).read_bytes()
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def html_block(raw):
    """st.markdown(..., unsafe_allow_html=True) but render-safe.

    Streamlit's CommonMark parser mangles raw HTML two ways: (1) a blank line
    closes an open HTML block, and (2) any line indented 4+ spaces is treated
    as an indented code block and shown as literal text. We strip every line
    (killing indentation) and drop blank lines, so the whole snippet stays one
    continuous raw-HTML block that renders instead of printing as code.
    """
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    st.markdown("\n".join(lines), unsafe_allow_html=True)

# ----------------------------------------------------------------------
# 국가 데이터 (지구본 대체 - 지도 카드 방식)
# ----------------------------------------------------------------------
COUNTRIES = {
    "jp": {
        "name": "일본 · 도쿄",
        "flag": "🗾",
        "landmark": "🗼",
        "climate": "온난 습윤. 여름엔 고온다습, 겨울은 건조",
        "humidity": "평균 65% (한국보다 다소 높음)",
        "temp_diff": "여름 기준 +2°C",
        "visa": "무비자 90일",
        "flight_time": "약 2시간 30분",
        "water": "연수",
        "water_note": "한국과 비슷한 연수라 세안 시 큰 자극은 적은 편",
        "uv": "보통~강함 (여름 최고 8)",
        "essentials": ["가벼운 젤 타입 자외선 차단제", "여름철 유분 조절 클렌징폼", "쿨링 미스트"],
        "trouble": "여름철 높은 습도로 인한 유분·모공 트러블",
        "hair_tip": "쓰리와우 저자극 샴푸 (현지 드럭스토어 판매)",
    },
    "fr": {
        "name": "프랑스 · 파리",
        "flag": "🇫🇷",
        "landmark": "🗼",
        "climate": "서안 해양성. 사계절 온화, 겨울철 건조·바람",
        "humidity": "평균 40% (한국보다 낮음, 건조)",
        "temp_diff": "겨울 기준 -3°C",
        "visa": "무비자 90일 (쉥겐)",
        "flight_time": "약 13시간",
        "water": "경수",
        "water_note": "석회질이 많은 경수 지역 — 세안 후 당김·트러블 주의",
        "uv": "낮음~보통",
        "essentials": ["고보습 크림", "미셀라 클렌징워터 (헹굼 불필요)", "립밤·핸드크림"],
        "trouble": "경수로 인한 세안 후 당김, 두피 건조",
        "hair_tip": "경수 전용 킬레이팅 샴푸 추천",
    },
    "th": {
        "name": "태국 · 방콕",
        "flag": "🇹🇭",
        "landmark": "🛕",
        "climate": "열대 몬순. 고온다습, 우기·건기 뚜렷",
        "humidity": "평균 75% (한국보다 매우 높음)",
        "temp_diff": "연중 +8°C",
        "visa": "무비자 30일",
        "flight_time": "약 6시간",
        "water": "경수",
        "water_note": "지역별 편차 큼, 대체로 약경수 — 민감성은 생수 세안 권장",
        "uv": "매우 강함 (연중 9~11)",
        "essentials": ["고자차 선크림 (SPF50+/PA++++)", "가벼운 워터 젤 로션", "쿨링 시트팩"],
        "trouble": "강한 자외선 + 습도로 인한 색소침착, 트러블 동반",
        "hair_tip": "두피 쿨링 샴푸 (더위 대비)",
    },
    "ae": {
        "name": "아랍에미리트 · 두바이",
        "flag": "🇦🇪",
        "landmark": "🏙️",
        "climate": "사막성. 고온 건조, 낮밤 온도차 큼",
        "humidity": "평균 25% (매우 건조)",
        "temp_diff": "여름 기준 +15°C",
        "visa": "무비자 30일",
        "flight_time": "약 9시간 30분",
        "water": "경수",
        "water_note": "석회질 매우 높은 경수 — 민감성 피부는 트러블 위험 높음",
        "uv": "매우 강함 (연중 10 이상)",
        "essentials": ["고보습 앰플", "미네랄 워터 미스트", "고자차 선크림"],
        "trouble": "극건조 + 강한 자외선 콤보로 인한 각질·자극",
        "hair_tip": "경수 대응 헤어 에센스 필수",
    },
    "is": {
        "name": "아이슬란드 · 레이캬비크",
        "flag": "🇮🇸",
        "landmark": "🌋",
        "climate": "한대 해양성. 서늘하고 강풍, 낮은 자외선",
        "humidity": "평균 75% (습하지만 기온이 낮아 체감 건조)",
        "temp_diff": "여름 기준 -12°C",
        "visa": "무비자 90일 (쉥겐)",
        "flight_time": "약 14시간",
        "water": "연수 (미네랄 풍부 지열수)",
        "water_note": "지열수 특유의 유황 성분 — 극도 민감성은 자극 가능",
        "uv": "낮음",
        "essentials": ["고영양 크림", "바람막이용 페이스 오일", "립밤"],
        "trouble": "강풍·저온으로 인한 피부 당김, 각질",
        "hair_tip": "지열수 미네랄 대응 헤어팩",
    },
    "us": {
        "name": "미국 · 로스앤젤레스",
        "flag": "🇺🇸",
        "landmark": "🌴",
        "climate": "지중해성. 건조하고 자외선 강함",
        "humidity": "평균 45%",
        "temp_diff": "여름 기준 +1°C",
        "visa": "ESTA 사전 승인 필요",
        "flight_time": "약 11시간",
        "water": "경수",
        "water_note": "경수 지역 — 장기 체류 시 두피·피부 트러블 누적 가능",
        "uv": "강함 (연중 7~10)",
        "essentials": ["데일리 선크림", "안티옥시던트 세럼", "샤워 필터(장기체류시)"],
        "trouble": "자외선 + 경수 복합 자극",
        "hair_tip": "샤워기 필터 또는 킬레이팅 샴푸",
    },
}

SKIN_TYPES = ["건성", "지성", "복합성", "민감성", "트러블"]
GENDERS = ["여성", "남성", "자유롭게"]
CLOTHING = ["캐주얼", "러블리", "스트릿", "미니멀"]
HAIR_TYPES = ["스트레이트", "웨이브", "컬리", "숏컷"]
AGE_RANGES = ["10대", "20대", "30대", "40대+"]
SKIN_TONES = [
    {"id": "light", "hex": "#FFE0C4", "label": "라이트"},
    {"id": "medium", "hex": "#F2B98A", "label": "미디엄"},
    {"id": "deep", "hex": "#C68858", "label": "딥"},
]

AFTERCARE_ADVICE = {
    "트러블": {
        "pack": "티트리 진정 팩",
        "routine": ["저자극 클렌징으로 노폐물 제거", "진정 토너로 pH 밸런스 회복",
                    "티트리/시카 앰플로 트러블 부위 집중 케어", "산화아연 함유 밤으로 재생 보호"],
    },
    "건조": {
        "pack": "고보습 시트팩",
        "routine": ["미온수 세안 + 저자극 클렌징", "히알루론산 토너로 수분 채우기",
                    "고보습 앰플 겹겹이 레이어링", "세라마이드 크림으로 수분 밀봉"],
    },
    "붉어짐": {
        "pack": "카밍 콜라겐 팩",
        "routine": ["차가운 물로 진정 세안", "판테놀/병풀 토너 사용",
                    "저자극 무향 제품으로 전환", "냉장 보관한 진정 크림 사용"],
    },
    "칙칙함": {
        "pack": "비타민 브라이트닝 팩",
        "routine": ["약산성 각질 케어 (주 1회)", "비타민C 세럼으로 톤업",
                    "자외선 차단 재도포 습관화", "숙면과 수분 섭취 병행"],
    },
}

# ----------------------------------------------------------------------
# 세션 상태 초기화
# ----------------------------------------------------------------------
if "character" not in st.session_state:
    st.session_state.character = None
if "passport" not in st.session_state:
    st.session_state.passport = []
if "view" not in st.session_state:
    st.session_state.view = "home"
if "selected_country" not in st.session_state:
    st.session_state.selected_country = None


def get_character():
    return st.session_state.character


def get_passport():
    return st.session_state.passport


def goto(view):
    st.session_state.view = view


# ----------------------------------------------------------------------
# 전역 테마 — 파스텔 하늘 + 크고 다양한 구름이 많이 둥둥
# 모든 화면 공통. 아이콘/버튼 클릭 시 view 가 바뀌며 화면이 전환된다.
# ----------------------------------------------------------------------
# 서로 다른 3가지 뭉게구름 실루엣 (SVG)
CLOUD_SHAPES = [
    '<svg viewBox="0 0 230 120" xmlns="http://www.w3.org/2000/svg"><g fill="#ffffff">'
    '<ellipse cx="70" cy="80" rx="54" ry="34"/><ellipse cx="122" cy="60" rx="60" ry="46"/>'
    '<ellipse cx="172" cy="82" rx="46" ry="30"/><ellipse cx="44" cy="88" rx="34" ry="24"/>'
    '<rect x="42" y="80" width="146" height="32" rx="16"/></g></svg>',
    '<svg viewBox="0 0 180 140" xmlns="http://www.w3.org/2000/svg"><g fill="#ffffff">'
    '<ellipse cx="92" cy="58" rx="56" ry="50"/><ellipse cx="52" cy="92" rx="40" ry="34"/>'
    '<ellipse cx="128" cy="90" rx="44" ry="38"/><rect x="38" y="86" width="104" height="36" rx="18"/></g></svg>',
    '<svg viewBox="0 0 210 90" xmlns="http://www.w3.org/2000/svg"><g fill="#ffffff">'
    '<ellipse cx="58" cy="56" rx="40" ry="24"/><ellipse cx="112" cy="46" rx="50" ry="32"/>'
    '<ellipse cx="158" cy="58" rx="36" ry="22"/><rect x="38" y="56" width="130" height="22" rx="11"/></g></svg>',
]

# 패럴랙스 3레이어 — 원경(far): 작고 느리고 흐릿 / 중경(mid) / 근경(near): 크고 빠르고 선명
# (top%, width px, duration s, delay s, opacity, shape idx, depth)
CLOUD_LAYOUT = [
    # 원경 (far) — 느림(100~120s), 작고 흐릿
    (6, 120, 118, -10, 0.6, 2, "far"), (20, 100, 108, -60, 0.55, 2, "far"),
    (38, 140, 120, -30, 0.6, 1, "far"), (58, 110, 112, -85, 0.55, 2, "far"),
    (74, 130, 116, -45, 0.6, 1, "far"), (88, 100, 104, -95, 0.5, 2, "far"),
    # 중경 (mid) — 보통(64~82s)
    (12, 220, 74, -20, 0.82, 1, "mid"), (30, 250, 80, -50, 0.85, 0, "mid"),
    (48, 210, 68, -8, 0.8, 1, "mid"), (66, 240, 78, -62, 0.84, 0, "mid"),
    (82, 200, 70, -35, 0.8, 1, "mid"),
    # 근경 (near) — 빠름(38~52s), 크고 선명
    (4, 380, 46, -6, 0.97, 0, "near"), (34, 420, 52, -40, 0.98, 0, "near"),
    (54, 340, 42, -22, 0.95, 1, "near"), (78, 400, 50, -55, 0.96, 0, "near"),
    (92, 320, 40, -12, 0.94, 1, "near"),
]


def inject_theme():
    style = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Jua&family=Gaegu:wght@700&family=Gamja+Flower&display=swap');

    /* 파스텔 하늘 그라데이션 (하늘색 → 라벤더 → 핑크) */
    .stApp {
        background: linear-gradient(180deg,#BFE7FF 0%,#DCEEFF 30%,#F1E2FF 65%,#FFE2F0 100%);
        background-attachment: fixed;
    }
    .block-container { padding-top: 2rem; }

    /* 구름 패럴랙스 레이어 (화면 전체를 덮고, 클릭은 통과) */
    .sky-layer { position: fixed; inset: 0; overflow: hidden; pointer-events: none; z-index: 0; }
    .sky-layer .cloud {
        position: absolute; left: -35vw;
        animation-name: drift; animation-timing-function: linear; animation-iteration-count: infinite;
        will-change: transform;
    }
    .sky-layer .cloud svg { width: 100%; height: auto; display: block; }
    /* depth 별 흐림·그림자로 원근감 */
    .sky-layer .cloud.far  { filter: blur(2px)   drop-shadow(0 8px 10px rgba(120,150,210,.16)); }
    .sky-layer .cloud.mid  { filter: blur(.4px)  drop-shadow(0 13px 15px rgba(120,150,210,.24)); }
    .sky-layer .cloud.near { filter: drop-shadow(0 18px 20px rgba(120,150,210,.3)); }
    @keyframes drift {
        from { transform: translateX(-35vw); }
        to   { transform: translateX(145vw); }
    }

    /* 폴리포켓풍 캡슐 버튼 (primary) */
    .stButton > button[kind="primary"] {
        font-family: 'Jua', sans-serif;
        font-size: 1.3rem;
        border-radius: 999px;
        padding: 0.65rem 2.4rem;
        border: 4px solid #fff;
        background: linear-gradient(90deg,#FF9FD8,#FF6FB8);
        color: #fff;
        box-shadow: 0 7px 0 #E0489A, 0 12px 20px rgba(255,111,184,.45);
        transition: transform .12s ease, box-shadow .12s ease;
        animation: btn-pulse 1.8s ease-in-out infinite;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) scale(1.03);
        box-shadow: 0 9px 0 #E0489A, 0 16px 24px rgba(255,111,184,.55);
    }
    .stButton > button[kind="primary"]:active { transform: translateY(5px); box-shadow: 0 2px 0 #E0489A; }
    @keyframes btn-pulse { 0%,100%{ transform: scale(1); } 50%{ transform: scale(1.03); } }

    @media (prefers-reduced-motion: reduce) {
        .cloud, .stButton > button[kind="primary"] { animation: none !important; }
    }
    </style>
    """
    clouds = ['<div class="sky-layer">']
    for top, w, dur, delay, op, shape, depth in CLOUD_LAYOUT:
        clouds.append(
            f'<span class="cloud {depth}" style="top:{top}%; width:{w}px; opacity:{op}; '
            f'animation-duration:{dur}s; animation-delay:{delay}s;">{CLOUD_SHAPES[shape]}</span>'
        )
    clouds.append("</div>")
    html_block(style + "".join(clouds))


# ----------------------------------------------------------------------
# 화면 렌더링
# ----------------------------------------------------------------------
# 실사풍 여객기 — 측면(기수 왼쪽·주황 꼬리)
PLANE_SIDE_SVG = """
<svg class="plane-svg" viewBox="0 0 250 120" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="body" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff"/><stop offset="0.45" stop-color="#f0f4f9"/><stop offset="1" stop-color="#b9c5d4"/>
    </linearGradient>
    <linearGradient id="tail" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ffb04d"/><stop offset="1" stop-color="#ff5e62"/>
    </linearGradient>
    <linearGradient id="wingF" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#e3e9f1"/><stop offset="1" stop-color="#93a1b5"/>
    </linearGradient>
    <linearGradient id="eng" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#e8edf3"/><stop offset="1" stop-color="#8b98ab"/>
    </linearGradient>
  </defs>
  <path d="M126 60 L214 42 L176 70 Z" fill="#aab6c6" opacity="0.65"/>
  <path d="M182 58 L232 46 L206 66 Z" fill="url(#wingF)" stroke="#8492a6" stroke-width="0.6"/>
  <path d="M176 56 L206 14 L222 18 L204 58 Z" fill="url(#tail)" stroke="#e8663c" stroke-width="0.6"/>
  <path d="M16 66 C 44 55 96 51 160 55 L 214 50 C 232 49 232 63 213 64 L 162 70 C 100 78 48 78 16 66 Z" fill="url(#body)" stroke="#93a1b5" stroke-width="0.8"/>
  <path d="M16 66 C 26 59 34 57 42 57 C 40 66 40 68 44 74 C 33 74 23 71 16 66 Z" fill="url(#tail)"/>
  <path d="M30 61 C 36 59 41 59 45 60 L 43 65 C 39 64 34 64 30 65 Z" fill="#33465e"/>
  <g fill="#33465e">
    <circle cx="62" cy="61" r="2.1"/><circle cx="74" cy="60.4" r="2.1"/><circle cx="86" cy="60" r="2.1"/><circle cx="98" cy="59.8" r="2.1"/>
    <circle cx="110" cy="59.7" r="2.1"/><circle cx="122" cy="59.8" r="2.1"/><circle cx="134" cy="60" r="2.1"/><circle cx="146" cy="60.4" r="2.1"/><circle cx="158" cy="61" r="2.1"/>
  </g>
  <path d="M96 66 L150 68 L172 100 L120 78 Z" fill="url(#wingF)" stroke="#7d8ca1" stroke-width="0.8"/>
  <ellipse cx="128" cy="82" rx="15" ry="7" fill="url(#eng)" stroke="#7d8ca1" stroke-width="0.7"/>
  <ellipse cx="114" cy="82" rx="3.6" ry="6" fill="#2f3d52"/>
  <path d="M40 58 C 90 53 150 53 208 53" stroke="rgba(255,255,255,.85)" stroke-width="2" fill="none" stroke-linecap="round"/>
</svg>
"""

def _title_letters():
    """자유분방하게 — 글자마다 색·기울기 다르게, 순차 등장."""
    line1 = [("식", "#FF5D8F", -8), ("스", "#FF9E3D", 5), ("센", "#2FC4B5", -5), ("스", "#4EA8FF", 7)]
    line2 = [("트", "#FF5D8F", -6), ("레", "#FF8A3D", 5), ("블", "#FFC13B", -7),
             ("맥", "#2FC4B5", 6), ("스", "#A66BFF", -5), ("+", "#2FB4FF", 9)]
    out = ['<span class="tline six">']
    d = 0.1
    for ch, color, rot in line1:
        out.append(f'<span class="ltr" style="--rot:{rot}deg;">'
                   f'<span class="brand" style="color:{color}; animation-delay:{d:.2f}s;">{ch}</span></span>')
        d += 0.1
    out.append('</span><br/><span class="tline tm">')
    for ch, color, rot in line2:
        out.append(f'<span class="ltr" style="--rot:{rot}deg;">'
                   f'<span class="brand" style="color:{color}; animation-delay:{d:.2f}s;">{ch}</span></span>')
        d += 0.1
    out.append("</span>")
    return "".join(out)


def render_home():
    earth = asset_data_uri("earth_map.webp", "image/webp")
    title = _title_letters()
    html_block(
        f"""
        <style>
        .stage {{
            position: relative;
            width: 100%;
            height: min(90vh, 820px);
            margin: 0 auto;
            perspective: 1400px;
            overflow: hidden;
        }}

        /* ---- 대기광(atmosphere) — 파란 프레넬 림 ---- */
        .atmos {{
            position: absolute; left: 50%; top: 36%;
            width: clamp(360px,52vw,560px); height: clamp(360px,52vw,560px);
            transform: translate(-50%,-50%);
            border-radius: 50%; z-index: 2;
            background: radial-gradient(circle,
                rgba(140,200,255,.55) 44%,
                rgba(120,185,255,.42) 55%,
                rgba(120,185,255,.12) 64%,
                rgba(120,185,255,0) 73%);
            animation: atmos 4s ease-in-out infinite;
            pointer-events: none;
        }}
        @keyframes atmos {{
            0%,100% {{ transform: translate(-50%,-50%) scale(1);    opacity:.9; }}
            50%     {{ transform: translate(-50%,-50%) scale(1.05); opacity:1; }}
        }}

        /* ---- 3D 렌더링 느낌의 지구 (자전) ---- */
        .earth {{
            position: absolute; left: 50%; top: 36%;
            width: clamp(300px,44vw,480px); height: clamp(300px,44vw,480px);
            transform: translate(-50%,-50%);
            border-radius: 50%; z-index: 3; overflow: hidden;
            box-shadow:
                inset 0 0 30px 6px rgba(150,210,255,.35),
                0 0 60px 14px rgba(120,190,255,.6),
                0 40px 70px rgba(20,40,90,.55);
            animation: earth-float 7s ease-in-out infinite;
        }}
        /* 회전하는 지구 텍스처 (equirectangular 가로 스크롤 = 자전) */
        .earth .tex {{
            position: absolute; inset: 0; border-radius: 50%;
            background-image: url('{earth}');
            background-size: 960px 480px;
            background-repeat: repeat-x;
            background-position: 0 center;
            animation: spin-earth 34s linear infinite;
        }}
        @keyframes spin-earth {{
            from {{ background-position: 0 center; }}
            to   {{ background-position: -960px center; }}
        }}
        /* 구 입체감 레이어1: 강한 명암(구 라이팅) — 좌상단 광원, 우하단 그림자 */
        .earth .shade {{
            position: absolute; inset: 0; border-radius: 50%; z-index: 2;
            pointer-events: none;
            background:
                radial-gradient(circle at 30% 26%,
                    rgba(255,255,255,.55) 0%, rgba(255,255,255,.18) 12%, rgba(255,255,255,0) 30%),
                radial-gradient(circle at 68% 74%,
                    rgba(0,0,0,0) 30%, rgba(2,6,24,.34) 66%, rgba(1,3,16,.9) 100%),
                radial-gradient(circle at 50% 50%,
                    rgba(3,8,28,0) 52%, rgba(3,8,28,.3) 82%, rgba(1,3,14,.7) 100%);
        }}
        /* 구 입체감 레이어2: 프레넬 림 라이트(가장자리 파란 빛) + 광택 하이라이트 */
        .earth .gloss {{
            position: absolute; inset: 0; border-radius: 50%; z-index: 3;
            pointer-events: none;
            box-shadow:
                inset 6px 6px 22px rgba(180,225,255,.5),
                inset -4px -6px 20px rgba(120,180,255,.35);
            background:
                radial-gradient(ellipse 42% 26% at 34% 24%,
                    rgba(255,255,255,.6) 0%, rgba(255,255,255,0) 70%);
            mix-blend-mode: screen;
        }}
        @keyframes earth-float {{
            0%,100% {{ transform: translate(-50%,-50%) translateY(0); }}
            50%     {{ transform: translate(-50%,-50%) translateY(-16px); }}
        }}
        .earth-shadow {{
            position: absolute; left: 50%; top: 66%;
            width: clamp(210px,30vw,340px); height: 30px;
            transform: translateX(-50%);
            border-radius: 50%; z-index: 1;
            background: radial-gradient(ellipse, rgba(60,50,110,.42) 0%, rgba(60,50,110,0) 72%);
            animation: eshadow 7s ease-in-out infinite;
        }}
        @keyframes eshadow {{
            0%,100% {{ transform: translateX(-50%) scale(1);   opacity:.8; }}
            50%     {{ transform: translateX(-50%) scale(.85); opacity:.55; }}
        }}

        /* ---- 장식 이모지 ---- */
        .deco {{
            position: absolute; z-index: 2;
            filter: drop-shadow(0 4px 4px rgba(0,0,0,.12));
            animation: bob 3.6s ease-in-out infinite;
        }}
        @keyframes bob {{
            0%,100% {{ transform: translateY(0) rotate(-6deg); }}
            50%     {{ transform: translateY(-14px) rotate(6deg); }}
        }}

        /* ---- 타이틀 — 자유분방한 손글씨, 글자마다 색·기울기, 땅! 등장 ---- */
        .hero-title {{
            position: absolute; left: 50%; top: 52%;
            transform: translate(-50%,-50%);
            width: 100%; text-align: center; margin: 0;
            line-height: .95; z-index: 6; pointer-events: none;
        }}
        .hero-title .tline {{ display: block; }}
        .hero-title .ltr {{ display: inline-block; transform: rotate(var(--rot)); }}
        .hero-title .brand {{
            display: inline-block;
            font-family: 'Gaegu', 'Jua', cursive;
            font-weight: 700;
            -webkit-text-stroke: 7px #ffffff;
            paint-order: stroke fill;
            text-shadow:
                0 6px 0 rgba(120,60,110,.35),
                0 10px 22px rgba(30,5,30,.45);
            animation: slam 2.2s cubic-bezier(.16,1.55,.3,1) both;
        }}
        .hero-title .six .brand {{ font-size: clamp(2.6rem,7vw,5rem); margin: 0 .02em; }}
        .hero-title .tm  .brand {{ font-size: clamp(4rem,12.5vw,9rem); margin: 0 .015em; }}
        @keyframes slam {{
            0%   {{ opacity:0; transform: scale(3.6) translateY(-90px); filter: blur(6px); }}
            22%  {{ opacity:1; }}
            40%  {{ transform: scale(.78) translateY(0); filter: blur(0); }}
            55%  {{ transform: scale(1.16); }}
            68%  {{ transform: scale(.95); }}
            80%  {{ transform: scale(1.05); }}
            90%  {{ transform: scale(.99); }}
            100% {{ transform: scale(1); }}
        }}
        .hero-sub {{
            position: absolute; left: 50%; top: 85%;
            transform: translateX(-50%);
            width: 100%; text-align: center;
            font-family: 'Gamja Flower', 'Jua', cursive;
            font-size: clamp(1.2rem,2.6vw,1.85rem);
            color: #6a3d8a; z-index: 6;
            text-shadow: 0 2px 0 rgba(255,255,255,.85);
            animation: rise .9s ease 2.6s both;
        }}
        @keyframes rise {{ from{{ opacity:0; transform: translateX(-50%) translateY(18px);}} to{{ opacity:1; transform: translateX(-50%) translateY(0);}} }}

        /* ---- 비행기(메인) — 오른쪽 끝 → 왼쪽 끝, 빠르게 직선 비행 ---- */
        .plane-main {{
            position: absolute; top: 15%; left: 106%;
            width: clamp(160px,21vw,280px); z-index: 7;
            animation: fly-main 7s ease-in-out infinite;
            will-change: left;
        }}
        .plane-main .plane-svg {{ width: 100%; height: auto; display: block; filter: drop-shadow(0 10px 10px rgba(20,40,90,.32)); }}
        .plane-main .trail {{
            position: absolute; right: -4px; top: 50%; z-index: -1;
            width: clamp(110px,15vw,200px); height: 3px; transform: translateY(-6px);
            background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,.9));
            border-radius: 3px;
            box-shadow: 0 11px 0 rgba(255,255,255,.5), 0 -9px 0 rgba(255,255,255,.45);
            animation: trail-flick .5s ease-in-out infinite alternate;
        }}
        @keyframes trail-flick {{ from{{opacity:.35;}} to{{opacity:.8;}} }}
        @keyframes fly-main {{
            0%   {{ left: 106%; opacity: 0; }}
            5%   {{ opacity: 1; }}
            42%  {{ left: -30%; opacity: 1; }}
            43%  {{ opacity: 0; }}
            100% {{ left: -30%; opacity: 0; }}
        }}

        /* ---- 비행기(배경) — 같은 방향, 더 작고 느리게, 다른 타이밍 ---- */
        .plane-bg {{
            position: absolute; top: 7%; left: 110%;
            width: clamp(64px,8vw,110px); z-index: 1; opacity: .5;
            animation: fly-bg 12s linear infinite;
            will-change: left;
        }}
        .plane-bg .plane-svg {{ width: 100%; height: auto; display: block; filter: drop-shadow(0 6px 6px rgba(20,40,90,.2)); }}
        @keyframes fly-bg {{
            0%   {{ left: 110%; opacity: 0; }}
            8%   {{ opacity: .5; }}
            74%  {{ left: -22%; opacity: .5; }}
            76%  {{ opacity: 0; }}
            100% {{ left: -22%; opacity: 0; }}
        }}

        /* ---- 시작 버튼 — 타이틀 애니메이션이 끝난 뒤 등장 (약 2.9초 후) ---- */
        .stButton > button[kind="primary"] {{
            font-size: 1.75rem;
            padding: 0.95rem 3.4rem;
            border-width: 5px;
            box-shadow: 0 10px 0 #E0489A, 0 18px 30px rgba(255,111,184,.5);
            animation: btn-in .8s cubic-bezier(.2,1.6,.35,1) 2.9s both,
                       btn-pulse 2s ease-in-out 3.8s infinite;
        }}
        @keyframes btn-in {{
            0%   {{ opacity:0; transform: translateY(46px) scale(.55); pointer-events:none; }}
            100% {{ opacity:1; transform: translateY(0)    scale(1);   pointer-events:auto; }}
        }}

        @media (prefers-reduced-motion: reduce) {{
            .earth, .earth .tex, .earth-shadow, .atmos, .plane-main, .plane-bg, .deco, .trail,
            .stButton > button[kind="primary"] {{ animation: none !important; }}
        }}
        </style>

        <div class="stage">
            <span class="deco" style="top:5%;  left:8%;  font-size:2.6rem; animation-delay:.0s;">🌈</span>
            <span class="deco" style="top:44%; left:4%;  font-size:2.2rem; animation-delay:1.0s;">💕</span>
            <span class="deco" style="top:10%; right:26%; font-size:1.8rem; animation-delay:.3s;">⭐</span>
            <span class="deco" style="bottom:9%;  left:13%; font-size:2.1rem; animation-delay:.8s;">🗼</span>
            <span class="deco" style="bottom:7%;  right:14%; font-size:2.1rem; animation-delay:1.3s;">🏰</span>
            <span class="deco" style="bottom:20%; left:45%; font-size:1.9rem; animation-delay:.6s;">🕌</span>
            <div class="atmos"></div>
            <div class="earth-shadow"></div>
            <div class="earth">
                <div class="tex"></div>
                <div class="shade"></div>
                <div class="gloss"></div>
            </div>
            <div class="plane-bg">{PLANE_SIDE_SVG}</div>
            <div class="plane-main">
                {PLANE_SIDE_SVG}
                <span class="trail"></span>
            </div>
            <h1 class="hero-title">{title}</h1>
            <p class="hero-sub">기후 · 수질 · 자외선을 내 피부에 맞춰 알려주는 여행 뷰티 케어 ✈️</p>
        </div>
        """
    )

    left, mid, right = st.columns([1, 1, 1])
    with mid:
        if st.button("✈️ 여행 시작하기", type="primary", use_container_width=True):
            goto("character")
            st.rerun()


def render_character():
    st.title("👤 캐릭터 만들기")
    char = get_character() or {}
    with st.form("character_form"):
        gender = st.radio("성별", GENDERS, horizontal=True,
                           index=GENDERS.index(char.get("gender", GENDERS[0])))
        skin_type = st.selectbox("피부 타입", SKIN_TYPES,
                                  index=SKIN_TYPES.index(char.get("skin_type", SKIN_TYPES[0])))
        clothing = st.selectbox("스타일", CLOTHING,
                                 index=CLOTHING.index(char.get("clothing", CLOTHING[0])))
        hair_type = st.selectbox("헤어 타입", HAIR_TYPES,
                                  index=HAIR_TYPES.index(char.get("hair_type", HAIR_TYPES[0])))
        age_range = st.selectbox("연령대", AGE_RANGES,
                                  index=AGE_RANGES.index(char.get("age_range", AGE_RANGES[0])))

        st.write("피부 톤")
        tone_cols = st.columns(len(SKIN_TONES))
        for col, tone in zip(tone_cols, SKIN_TONES):
            with col:
                st.markdown(
                    f'<div style="width:100%;height:40px;border-radius:8px;'
                    f'background:{tone["hex"]};border:1px solid #ddd;"></div>',
                    unsafe_allow_html=True,
                )
                st.caption(tone["label"])
        tone_labels = [t["label"] for t in SKIN_TONES]
        current_tone = next((t["label"] for t in SKIN_TONES if t["hex"] == char.get("skin_tone")), tone_labels[0])
        skin_tone_label = st.radio("톤 선택", tone_labels, horizontal=True,
                                    index=tone_labels.index(current_tone), label_visibility="collapsed")

        submitted = st.form_submit_button("캐릭터 완성! →", type="primary")
        if submitted:
            skin_tone_hex = next(t["hex"] for t in SKIN_TONES if t["label"] == skin_tone_label)
            st.session_state.character = {
                "gender": gender,
                "skin_type": skin_type,
                "clothing": clothing,
                "hair_type": hair_type,
                "age_range": age_range,
                "skin_tone": skin_tone_hex,
            }
            goto("map")
            st.rerun()


def render_map():
    if not get_character():
        goto("character")
        st.rerun()
        return

    st.title("🗺️ 여행지 지도")
    st.caption("관심있는 여행지를 눌러 상세 정보를 확인하세요")
    codes = list(COUNTRIES.keys())
    cols = st.columns(3)
    for i, code in enumerate(codes):
        c = COUNTRIES[code]
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"### {c['flag']} {c['landmark']}")
                st.markdown(f"**{c['name']}**")
                st.caption(c["climate"])
                if st.button("자세히 보기", key=f"detail_{code}", use_container_width=True):
                    st.session_state.selected_country = code
                    goto("country")
                    st.rerun()


def render_country():
    code = st.session_state.selected_country
    country = COUNTRIES.get(code)
    if not get_character():
        goto("character")
        st.rerun()
        return
    if not country:
        goto("map")
        st.rerun()
        return

    char = get_character()
    st.title(f"{country['flag']} {country['name']}")

    if country["water"] == "경수" and char["skin_type"] in ("민감성", "트러블"):
        st.warning(
            f"⚠ {char['skin_type']} 피부는 이 지역의 경수 때문에 트러블 위험이 높아요. "
            f"저자극 클렌징워터를 꼭 챙기세요."
        )

    col1, col2 = st.columns(2)
    with col1:
        st.metric("기후", country["climate"])
        st.metric("습도", country["humidity"])
        st.metric("기온 차", country["temp_diff"])
        st.metric("비자", country["visa"])
        st.metric("비행 시간", country["flight_time"])
    with col2:
        st.metric("수질", f"{country['water']}")
        st.caption(country["water_note"])
        st.metric("자외선", country["uv"])
        st.markdown("**필수 아이템**")
        for item in country["essentials"]:
            st.write(f"- {item}")
        st.markdown(f"**주의할 트러블:** {country['trouble']}")
        st.markdown(f"**헤어 팁:** {country['hair_tip']}")

    st.divider()
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("⬅ 지도로 돌아가기"):
            goto("map")
            st.rerun()
    with nav_col2:
        already_saved = code in [p["code"] for p in get_passport()]
        if already_saved:
            st.success("📘 이미 여권에 저장됨")
        else:
            if st.button("📘 여권에 저장", type="primary"):
                st.session_state.passport.append({
                    "code": code,
                    "name": country["name"],
                    "flag": country["flag"],
                    "tip": country["essentials"][0],
                })
                st.rerun()


def render_passport():
    st.title("📘 내 여행 여권")
    passport = get_passport()
    if not passport:
        st.info("아직 저장한 여행지가 없어요. 지도에서 여행지를 둘러보세요!")
        if st.button("🗺️ 지도로 가기"):
            goto("map")
            st.rerun()
        return

    for p in passport:
        with st.container(border=True):
            st.markdown(f"### {p['flag']} {p['name']}")
            st.caption(f"챙길 것: {p['tip']}")


def render_aftercare():
    st.title("💧 애프터케어")
    st.caption("여행 후 피부 상태에 맞는 케어 루틴을 확인하세요")
    symptom = st.selectbox("지금 피부 상태는 어떤가요?", list(AFTERCARE_ADVICE.keys()))
    if st.button("케어 루틴 보기", type="primary"):
        advice = AFTERCARE_ADVICE[symptom]
        st.subheader(f"추천 팩: {advice['pack']}")
        st.markdown("**케어 루틴**")
        for i, step in enumerate(advice["routine"], 1):
            st.write(f"{i}. {step}")


# ----------------------------------------------------------------------
# 사이드바 내비게이션
# ----------------------------------------------------------------------
with st.sidebar:
    st.title("🧴 TravelMax+")
    character = get_character()
    if character:
        st.caption(f"{character['gender']} · {character['skin_type']} 피부")
        if st.button("🗺️ 지도", use_container_width=True):
            goto("map")
            st.rerun()
        if st.button(f"📘 여권 ({len(get_passport())})", use_container_width=True):
            goto("passport")
            st.rerun()
        if st.button("💧 애프터케어", use_container_width=True):
            goto("aftercare")
            st.rerun()
        st.divider()
        if st.button("👤 캐릭터 다시 설정", use_container_width=True):
            goto("character")
            st.rerun()
    else:
        st.caption("캐릭터를 먼저 만들어보세요!")

# ----------------------------------------------------------------------
# 화면 라우팅
# ----------------------------------------------------------------------
inject_theme()

VIEWS = {
    "home": render_home,
    "character": render_character,
    "map": render_map,
    "country": render_country,
    "passport": render_passport,
    "aftercare": render_aftercare,
}
VIEWS.get(st.session_state.view, render_home)()
