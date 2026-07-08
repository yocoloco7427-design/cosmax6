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
# 전역 테마 — 폴리포켓/모동숲 느낌의 파스텔 하늘 + 구름 둥둥 애니메이션
# 모든 화면 공통. 아이콘/버튼 클릭 시 view 가 바뀌며 화면이 전환된다.
# ----------------------------------------------------------------------
def inject_theme():
    html_block(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Jua&family=Gaegu:wght@700&display=swap');

        /* 파스텔 하늘 그라데이션 (하늘색 → 라벤더 → 핑크) */
        .stApp {
            background: linear-gradient(180deg,#BFE7FF 0%,#DCEEFF 30%,#F1E2FF 65%,#FFE2F0 100%);
            background-attachment: fixed;
        }
        .block-container { padding-top: 2rem; }

        /* 구름 + 반짝이 레이어 (화면 전체를 덮고, 클릭은 통과) */
        .sky-layer {
            position: fixed; inset: 0; overflow: hidden;
            pointer-events: none; z-index: 0;
        }
        .sky-layer .cloud {
            position: absolute; left: -25vw;
            filter: drop-shadow(0 8px 10px rgba(255,190,225,.35));
            animation-name: drift; animation-timing-function: linear;
            animation-iteration-count: infinite;
        }
        .sky-layer .twinkle {
            position: absolute;
            animation: twinkle 2.6s ease-in-out infinite;
        }
        @keyframes drift {
            from { transform: translateX(-25vw); }
            to   { transform: translateX(130vw); }
        }
        @keyframes twinkle {
            0%,100% { opacity:.25; transform: scale(.8); }
            50%     { opacity:1;   transform: scale(1.2); }
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
        .stButton > button[kind="primary"]:active {
            transform: translateY(5px); box-shadow: 0 2px 0 #E0489A;
        }
        @keyframes btn-pulse { 0%,100%{ transform: scale(1); } 50%{ transform: scale(1.03); } }

        @media (prefers-reduced-motion: reduce) {
            .cloud, .twinkle, .stButton > button[kind="primary"] { animation: none !important; }
        }
        </style>

        <div class="sky-layer">
            <span class="cloud" style="top:6%;  font-size:5rem;   animation-duration:62s; animation-delay:-5s;">☁️</span>
            <span class="cloud" style="top:16%; font-size:3.2rem; animation-duration:48s; animation-delay:-22s; opacity:.85;">☁️</span>
            <span class="cloud" style="top:32%; font-size:6.2rem; animation-duration:78s; animation-delay:-42s; opacity:.9;">☁️</span>
            <span class="cloud" style="top:54%; font-size:3.8rem; animation-duration:55s; animation-delay:-12s; opacity:.8;">☁️</span>
            <span class="cloud" style="top:70%; font-size:5.4rem; animation-duration:68s; animation-delay:-33s; opacity:.85;">☁️</span>
            <span class="cloud" style="top:84%; font-size:3rem;   animation-duration:50s; animation-delay:-52s; opacity:.75;">☁️</span>
            <span class="twinkle" style="top:10%; left:20%; font-size:1.4rem; animation-delay:.2s;">✨</span>
            <span class="twinkle" style="top:22%; left:78%; font-size:1.1rem; animation-delay:1.1s;">💫</span>
            <span class="twinkle" style="top:62%; left:12%; font-size:1.2rem; animation-delay:.7s;">⭐</span>
            <span class="twinkle" style="top:75%; left:85%; font-size:1.3rem; animation-delay:1.6s;">✨</span>
        </div>
        """
    )


# ----------------------------------------------------------------------
# 화면 렌더링
# ----------------------------------------------------------------------
# 3D 느낌의 실사 여객기 (측면, 기수 왼쪽 · 주황 꼬리 — 참고 사진 기반)
PLANE_SVG = """
<svg class="plane" viewBox="0 0 250 120" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="body" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="0.45" stop-color="#f0f4f9"/>
      <stop offset="1" stop-color="#b9c5d4"/>
    </linearGradient>
    <linearGradient id="tail" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ffb04d"/>
      <stop offset="1" stop-color="#ff5e62"/>
    </linearGradient>
    <linearGradient id="wingF" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#e3e9f1"/>
      <stop offset="1" stop-color="#93a1b5"/>
    </linearGradient>
    <linearGradient id="engine" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#e8edf3"/>
      <stop offset="1" stop-color="#8b98ab"/>
    </linearGradient>
  </defs>
  <!-- 뒤쪽 날개 (멀리, 흐리게) -->
  <path d="M126 60 L214 42 L176 70 Z" fill="#aab6c6" opacity="0.65"/>
  <!-- 수평 꼬리날개 -->
  <path d="M182 58 L232 46 L206 66 Z" fill="url(#wingF)" stroke="#8492a6" stroke-width="0.6"/>
  <!-- 수직 꼬리날개 (주황) -->
  <path d="M176 56 L206 14 L222 18 L204 58 Z" fill="url(#tail)" stroke="#e8663c" stroke-width="0.6"/>
  <!-- 동체 -->
  <path d="M16 66
           C 44 55 96 51 160 55
           L 214 50
           C 232 49 232 63 213 64
           L 162 70
           C 100 78 48 78 16 66 Z"
        fill="url(#body)" stroke="#93a1b5" stroke-width="0.8"/>
  <!-- 기수 주황 포인트 -->
  <path d="M16 66 C 26 59 34 57 42 57 C 40 66 40 68 44 74 C 33 74 23 71 16 66 Z" fill="url(#tail)"/>
  <!-- 조종석 창 -->
  <path d="M30 61 C 36 59 41 59 45 60 L 43 65 C 39 64 34 64 30 65 Z" fill="#33465e"/>
  <!-- 창문 줄 -->
  <g fill="#33465e">
    <circle cx="62" cy="61" r="2.1"/><circle cx="74" cy="60.4" r="2.1"/>
    <circle cx="86" cy="60" r="2.1"/><circle cx="98" cy="59.8" r="2.1"/>
    <circle cx="110" cy="59.7" r="2.1"/><circle cx="122" cy="59.8" r="2.1"/>
    <circle cx="134" cy="60" r="2.1"/><circle cx="146" cy="60.4" r="2.1"/>
    <circle cx="158" cy="61" r="2.1"/>
  </g>
  <!-- 앞쪽 날개 (가까이, 아래로 스윕) -->
  <path d="M96 66 L150 68 L172 100 L120 78 Z" fill="url(#wingF)" stroke="#7d8ca1" stroke-width="0.8"/>
  <!-- 엔진 나셀 -->
  <ellipse cx="128" cy="82" rx="15" ry="7" fill="url(#engine)" stroke="#7d8ca1" stroke-width="0.7"/>
  <ellipse cx="114" cy="82" rx="3.6" ry="6" fill="#2f3d52"/>
  <!-- 동체 하이라이트 -->
  <path d="M40 58 C 90 53 150 53 208 53" stroke="rgba(255,255,255,.85)" stroke-width="2" fill="none" stroke-linecap="round"/>
</svg>
"""


def render_home():
    earth = asset_data_uri("earth.webp", "image/webp")
    html_block(
        f"""
        <style>
        .stage {{
            position: relative;
            width: 100%;
            height: min(80vh, 660px);
            margin: 0 auto;
            perspective: 1400px;
            overflow: hidden;
        }}

        /* ---- 대기광(atmosphere) ---- */
        .atmos {{
            position: absolute; left: 50%; top: 34%;
            width: clamp(280px,42vw,420px); height: clamp(280px,42vw,420px);
            transform: translate(-50%,-50%);
            border-radius: 50%; z-index: 2;
            background: radial-gradient(circle,
                rgba(150,205,255,.55) 40%,
                rgba(150,205,255,.28) 58%,
                rgba(150,205,255,0) 72%);
            animation: atmos 4s ease-in-out infinite;
            pointer-events: none;
        }}
        @keyframes atmos {{
            0%,100% {{ transform: translate(-50%,-50%) scale(1);    opacity:.9; }}
            50%     {{ transform: translate(-50%,-50%) scale(1.06); opacity:1; }}
        }}

        /* ---- 사실적 3D 지구 (구 모양) ---- */
        .earth {{
            position: absolute; left: 50%; top: 34%;
            width: clamp(210px,32vw,320px); height: clamp(210px,32vw,320px);
            transform: translate(-50%,-50%);
            border-radius: 50%; z-index: 3;
            background-image: url('{earth}');
            background-size: cover; background-position: center;
            box-shadow:
                inset -26px -22px 60px rgba(2,6,25,.72),
                inset 20px 16px 45px rgba(255,255,255,.22),
                0 0 42px 8px rgba(120,190,255,.55),
                0 26px 46px rgba(20,40,90,.45);
            animation: earth-float 7s ease-in-out infinite;
        }}
        /* 스페큘러 하이라이트(빛 반사) — 구 입체감 */
        .earth::after {{
            content: ''; position: absolute; inset: 0; border-radius: 50%;
            background: radial-gradient(circle at 33% 27%,
                rgba(255,255,255,.5) 0%,
                rgba(255,255,255,.15) 16%,
                rgba(255,255,255,0) 34%);
        }}
        @keyframes earth-float {{
            0%,100% {{ transform: translate(-50%,-50%) translateY(0)    rotate(-1.5deg); }}
            50%     {{ transform: translate(-50%,-50%) translateY(-16px) rotate(1.5deg); }}
        }}
        .earth-shadow {{
            position: absolute; left: 50%; top: 62%;
            width: clamp(150px,24vw,240px); height: 26px;
            transform: translateX(-50%);
            border-radius: 50%; z-index: 1;
            background: radial-gradient(ellipse, rgba(60,50,110,.4) 0%, rgba(60,50,110,0) 72%);
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

        /* ---- 타이틀 — 지구 '앞쪽'에 크게, 땅! 등장 ---- */
        .hero-title {{
            position: absolute; left: 50%; top: 50%;
            transform: translate(-50%,-50%);
            width: 100%; text-align: center; margin: 0;
            line-height: 1.02; z-index: 6;
            pointer-events: none;
        }}
        .hero-title .brand {{
            display: inline-block;
            font-family: 'Jua', sans-serif;
            -webkit-text-stroke: 3px #ffffff;
            paint-order: stroke fill;
            color: #ff4fa0;
            text-shadow:
                0 3px 0 #d63384,
                0 6px 10px rgba(60,20,60,.45);
        }}
        .hero-title .six {{
            font-size: clamp(1.9rem,5vw,3.2rem);
            animation: slam .7s cubic-bezier(.18,1.5,.35,1) .05s both;
        }}
        .hero-title .tm {{
            font-size: clamp(3rem,8.6vw,6rem);
            color: #ff3d97;
            animation: slam .8s cubic-bezier(.18,1.5,.35,1) .28s both;
        }}
        .hero-title .plus {{ color: #35b6ff; -webkit-text-stroke-color:#fff; }}
        @keyframes slam {{
            0%   {{ opacity:0; transform: scale(2.6) translateY(-46px); filter: blur(3px); }}
            55%  {{ opacity:1; transform: scale(.88) translateY(0);     filter: blur(0); }}
            72%  {{ transform: scale(1.07); }}
            86%  {{ transform: scale(.97); }}
            100% {{ transform: scale(1); }}
        }}
        .hero-sub {{
            position: absolute; left: 50%; top: 80%;
            transform: translateX(-50%);
            width: 100%; text-align: center;
            font-family: 'Jua', sans-serif;
            font-size: clamp(.9rem,2vw,1.35rem);
            color: #6a3d8a; z-index: 6;
            text-shadow: 0 2px 0 rgba(255,255,255,.75);
            animation: rise 1s ease .9s both;
        }}
        @keyframes rise {{ from{{ opacity:0; transform: translateX(-50%) translateY(18px);}} to{{ opacity:1; transform: translateX(-50%) translateY(0);}} }}

        /* ---- 비행기 — 지구 오른쪽 '뒤'에서 등장 → 글자 앞 통과 → 왼쪽 '뒤'로 ---- */
        .plane-wrap {{
            position: absolute; top: 30%; left: 100%;
            width: clamp(120px,17vw,190px);
            display: flex; align-items: center;
            animation: fly 9s ease-in-out infinite;
            will-change: left, transform, z-index;
        }}
        .plane {{ width: 100%; height: auto; filter: drop-shadow(0 8px 8px rgba(20,40,90,.3)); }}
        .trail {{
            position: absolute; right: -6px; top: 50%; z-index: -1;
            width: clamp(80px,12vw,150px); height: 3px;
            transform: translateY(-6px);
            background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,.9));
            border-radius: 3px;
            box-shadow: 0 9px 0 rgba(255,255,255,.55), 0 -7px 0 rgba(255,255,255,.5);
            animation: trail-flick .5s ease-in-out infinite alternate;
        }}
        @keyframes trail-flick {{ from{{opacity:.4;}} to{{opacity:.85;}} }}
        @keyframes fly {{
            0%   {{ left: 100%; transform: translateY(-10px); z-index: 2; opacity: 0; }}
            8%   {{ opacity: 1; }}
            30%  {{ left: 60%;  transform: translateY(6px);  z-index: 2; }}   /* 지구 뒤 */
            40%  {{ z-index: 9; }}                                            /* 앞으로 */
            50%  {{ left: 40%;  transform: translateY(18px); z-index: 9; }}   /* 글자 앞 통과 */
            62%  {{ z-index: 9; }}
            70%  {{ left: 26%;  transform: translateY(26px); z-index: 2; }}   /* 다시 뒤로 */
            92%  {{ opacity: 1; }}
            100% {{ left: -20%; transform: translateY(36px); z-index: 2; opacity: 0; }}
        }}

        @media (prefers-reduced-motion: reduce) {{
            .earth, .earth-shadow, .atmos, .plane-wrap, .deco, .trail {{ animation: none !important; }}
        }}
        </style>

        <div class="stage">
            <span class="deco" style="top:5%;  left:8%;  font-size:2.1rem; animation-delay:.0s;">🌈</span>
            <span class="deco" style="top:11%; right:9%; font-size:1.6rem; animation-delay:.5s;">✨</span>
            <span class="deco" style="top:40%; left:4%;  font-size:1.8rem; animation-delay:1.0s;">💕</span>
            <span class="deco" style="top:8%;  right:26%; font-size:1.4rem; animation-delay:.3s;">⭐</span>
            <span class="deco" style="bottom:9%;  left:13%; font-size:1.7rem; animation-delay:.8s;">🗼</span>
            <span class="deco" style="bottom:7%;  right:14%; font-size:1.7rem; animation-delay:1.3s;">🏰</span>
            <span class="deco" style="bottom:20%; left:44%; font-size:1.5rem; animation-delay:.6s;">🕌</span>
            <div class="atmos"></div>
            <div class="earth-shadow"></div>
            <div class="earth"></div>
            <div class="plane-wrap">
                {PLANE_SVG}
                <span class="trail"></span>
            </div>
            <h1 class="hero-title">
                <span class="brand six">식스센스</span><br/>
                <span class="brand tm">트레블맥스<span class="plus">+</span></span>
            </h1>
            <p class="hero-sub">기후 · 수질 · 자외선을 내 피부에 맞춰 알려주는 여행 뷰티 케어</p>
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
