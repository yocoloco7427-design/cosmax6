"""
식스센스 TravelMax+
여행지 기후·수질·자외선 데이터를 내 피부 타입과 매칭해주는
게임풍 여행 뷰티 케어 웹앱 MVP
"""
import base64
import html
import json
import random
import re
import time
from pathlib import Path
from urllib.parse import quote as urlquote

import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from io import BytesIO
from PIL import Image

try:
    import anthropic
except ImportError:
    anthropic = None

WAQI_TOKEN = st.secrets.get("WAQI_TOKEN", "")
ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

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
        "geo": "35.6895;139.6917",
        "aqi_station": "japan/shinjuku-ku-/kuni-tokyo--shinjuku-/",
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
        "drugstores": ["마츠모토키요시 신주쿠점", "돈키호테 신주쿠 히가시구치점", "웰시아 신주쿠"],
    },
    "fr": {
        "name": "프랑스 · 파리",
        "flag": "🇫🇷",
        "landmark": "🗼",
        "geo": "48.8566;2.3522",
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
        "drugstores": ["Monoprix 오페라점", "Marionnaud 샹젤리제점", "Sephora 샹젤리제 플래그십"],
    },
    "th": {
        "name": "태국 · 방콕",
        "flag": "🇹🇭",
        "landmark": "🛕",
        "geo": "13.7563;100.5018",
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
        "drugstores": ["Boots 시암파라곤점", "Watsons 아속점", "Eveandboy 센트럴월드점"],
    },
    "ae": {
        "name": "아랍에미리트 · 두바이",
        "flag": "🇦🇪",
        "landmark": "🏙️",
        "geo": "25.2048;55.2708",
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
        "drugstores": ["Boots 두바이몰점", "Life Pharmacy 마리나몰점", "Sephora 두바이몰점"],
    },
    "is": {
        "name": "아이슬란드 · 레이캬비크",
        "flag": "🇮🇸",
        "landmark": "🌋",
        "geo": "64.1466;-21.9426",
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
        "drugstores": ["Lyfja 레이캬비크 다운타운점", "Hagkaup 크링글안점"],
    },
    "us": {
        "name": "미국 · 로스앤젤레스",
        "flag": "🇺🇸",
        "landmark": "🌴",
        "geo": "34.0522;-118.2437",
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
        "drugstores": ["CVS 할리우드점", "Sephora 더그로브점", "Walgreens 산타모니카점"],
    },
    "au": {
        "name": "호주 · 시드니",
        "flag": "🇦🇺",
        "landmark": "🦘",
        "geo": "-33.8688;151.2093",
        "climate": "온대 해양성. 계절이 한국과 반대(12~2월이 한여름)",
        "humidity": "평균 65% (한국과 비슷하나 계절이 반대)",
        "temp_diff": "1월 기준 +14°C (한국은 겨울, 시드니는 한여름)",
        "visa": "전자여행허가(ETA) 필요",
        "flight_time": "약 10시간 30분",
        "water": "연수",
        "water_note": "연수 지역이라 세안 자극은 적은 편, 자외선 대비가 훨씬 중요",
        "uv": "매우 강함 (연중 최고 11+, 오존층이 얇아 세계 최고 수준)",
        "essentials": ["고자차 선크림 (SPF50+/PA++++)", "애프터선 케어 젤", "쿨링 미스트"],
        "trouble": "세계 최고 수준의 자외선으로 인한 광노화·색소침착",
        "hair_tip": "UV 프로텍트 헤어 미스트",
        "drugstores": ["Chemist Warehouse 시드니시티점", "Priceline Pharmacy 피트스트리트점", "Mecca 시드니 QVB점"],
    },
    "cn": {
        "name": "중국 · 상하이",
        "flag": "🇨🇳",
        "landmark": "🐼",
        "geo": "31.2304;121.4737",
        "climate": "습윤 아열대. 여름은 고온다습한 찜통더위, 겨울은 서늘하고 흐림",
        "humidity": "평균 75% (여름 장마철엔 80% 이상)",
        "temp_diff": "여름 기준 +3°C (한국보다 더 무더움)",
        "visa": "무비자 15일 (단기 관광 시)",
        "flight_time": "약 1시간 50분",
        "water": "경수",
        "water_note": "석회질이 있는 경수 지역 — 세안 후 당김 주의, 높은 습도로 유분도 함께 관리",
        "uv": "강함 (여름 최고 9)",
        "essentials": ["유분 조절 클렌징폼", "가벼운 워터 젤 선크림", "제습 헤어 에센스"],
        "trouble": "고온다습으로 인한 유분·모공 트러블, 장마철 악화",
        "hair_tip": "습기 대비 볼륨 컨트롤 헤어 에센스",
        "drugstores": ["Watsons 난징동루점", "Sephora 화이하이루점", "Innisfree IAPM점"],
    },
    "kr": {
        "name": "한국 · 서울",
        "flag": "🇰🇷",
        "landmark": "🏯",
        "geo": "37.5665;126.9780",
        "climate": "온대 대륙성. 사계절이 뚜렷하고 여름 장마·겨울 건조가 특징",
        "humidity": "평균 65% (여름 장마철 습함, 겨울은 매우 건조)",
        "temp_diff": "계절별 변동 매우 큼 (여름 최고 35°C, 겨울 최저 -15°C)",
        "visa": "국내 여행 (비자 불필요)",
        "flight_time": "국내 거점 도시 (이동 불필요)",
        "water": "연수 (아리수)",
        "water_note": "일반 연수라 자극은 적은 편, 미세먼지 노출 후 꼼꼼한 세안 필요",
        "uv": "보통~강함 (여름 최고 8)",
        "essentials": ["미세먼지 딥클렌징폼", "환절기 보습 크림", "데일리 선크림"],
        "trouble": "환절기 급격한 건조·미세먼지로 인한 트러블",
        "hair_tip": "미세먼지 케어 헤어 클렌저",
        "drugstores": ["올리브영 명동점", "롭스 홍대점", "다이소 강남점"],
    },
}

# ----------------------------------------------------------------------
# 포스트잇 "유의사항" — 국가/도시별 피부 리스크. COUNTRIES와 별도 표로 관리해서
# 나라가 늘어나도 COUNTRIES 항목을 안 건드리고 이 표에 한 줄만 추가하면 되게 한다.
# linked_to에 실시간 지표 이름("aqi")을 넣어두면, 그 지표가 실제로 나쁜 날에는
# 포스트잇에서 이 문구를 강조 표시한다(get_air_quality로 그날 값을 확인).
# 아직 이 표에 없는 나라는 COUNTRIES의 기존 trouble 필드를 그대로 쓴다.
# ----------------------------------------------------------------------
SKIN_RISK_NOTES = {
    "kr": {"text": "간절기·환절기 등 계절이 바뀔 때 피부 균형이 쉽게 무너져요", "linked_to": "aqi"},
    "au": {"text": "강한 자외선으로 피부암 발병률이 높아요 — 자외선 차단제는 꼭 챙기세요", "linked_to": None},
    "cn": {"text": "미세먼지로 인한 트러블·모공 막힘에 주의하세요", "linked_to": "aqi"},
}


def get_skin_risk_note(code, country):
    """국가별 피부 유의사항 — SKIN_RISK_NOTES에 있으면 그걸, 없으면 COUNTRIES의
    기존 trouble 필드로 대체한다(아직 별도 표로 옮기지 않은 나라용)."""
    return SKIN_RISK_NOTES.get(code) or {"text": country["trouble"], "linked_to": None}


def _is_aqi_severe(country):
    """이 나라의 실시간 미세먼지(AQI)가 '나쁨'(101 이상) 수준인지 확인한다.
    토큰이 없거나 조회가 실패하면 판단할 수 없으니 강조하지 않는다(False)."""
    feed_path = country.get("aqi_station") or (
        f"geo:{country['geo']}" if country.get("geo") else None
    )
    if not feed_path:
        return False
    aq = get_air_quality(feed_path)
    if not aq or aq.get("aqi") in (None, "-"):
        return False
    try:
        return int(aq["aqi"]) >= 101
    except (TypeError, ValueError):
        return False


# ----------------------------------------------------------------------
# 드럭스토어 & 뷰티스토어 상세 리스트 — 국가/도시별로 급하게 화장품을 살 수
# 있는 실제 매장. 로컬 브랜드는 현지어 표기를 병기하고("local" 필드), 지도
# 검색 링크를 붙여서 "리스트만 보고 못 찾는" 문제를 방지한다. 아직 MVP라
# 상하이/시드니/서울 3개 도시만 채워뒀고, 나머지 국가는 COUNTRIES의 기존
# 단순 문자열 리스트("drugstores")로 계속 표시한다.
# ----------------------------------------------------------------------
DRUGSTORE_CITY_EN = {"cn": "Shanghai", "au": "Sydney", "kr": "Seoul"}

DRUGSTORE_DIRECTORY = {
    "cn": [
        {"kr": "왓슨스", "local": "屈臣氏", "en": "Watsons"},
        {"kr": "세포라", "local": "丝芙兰", "en": "Sephora"},
        {"kr": "하메이", "local": "话梅", "en": "HARMAY"},
        {"kr": "더 컬러리스트", "local": "调色师", "en": "The Colorist"},
        {"kr": "아피오나", "local": "妍丽", "en": "AFIONA"},
        {"kr": "와우컬러", "local": None, "en": "WOW COLOUR"},
    ],
    "au": [
        {"kr": "더블유 코스메틱스", "local": None, "en": "W Cosmetics"},
        {"kr": "라 코스메티크", "local": None, "en": "La Cosmetique"},
        {"kr": "보니크", "local": None, "en": "BONIIK"},
        {"kr": "프라이스라인", "local": None, "en": "Priceline"},
        {"kr": "케미스트 웨어하우스", "local": None, "en": "Chemist Warehouse"},
    ],
    "kr": [
        {"kr": "올리브영", "local": None, "en": "Olive Young"},
    ],
}


def get_drugstore_cards(code):
    """구조화된 드럭스토어 리스트(위 DRUGSTORE_DIRECTORY)가 있는 나라만 카드용
    데이터를 만들어 반환한다. 지도 검색 링크는 영문 상호명 + 영문 도시명으로
    구글맵 검색 URL을 만들어서, 로컬 표기만 보고는 못 찾는 문제를 피한다."""
    stores = DRUGSTORE_DIRECTORY.get(code)
    if not stores:
        return None
    city_en = DRUGSTORE_CITY_EN.get(code, "")
    cards = []
    for store in stores:
        label = store["kr"] + (f" {store['local']}" if store.get("local") else "") + f" / {store['en']}"
        query = urlquote(f"{store['en']} {city_en}".strip())
        cards.append({
            "label": label,
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={query}",
        })
    return cards


# 헤어 아이콘에서 "3WAU 추천 및 구매 사이트로 이동" 버튼이 여는 실제 스토어 링크
THREE_WAU_STORE_URL = (
    "https://3waau.com/?utm_medium=search&utm_source=Naver&utm_campaign=240311_cpc_brandname_pc"
    "&NaPm=ct%3Dmrd6nxqn%7Cci%3DER7fb8525b%2D7b67%2D11f1%2Dbff5%2Dc2fa024ff2a0%7Ctr%3Dsa"
    "%7Chk%3Dc29c3a0ba55ad0fc719c36173a43bbfa8e745111%7Cnacn%3DWSLcBIhX58R0"
)

# ----------------------------------------------------------------------
# 세계지도 (public domain, Wikimedia BlankMap-World-Equirectangular) 위에
# 각 여행지의 geo 위경도를 픽셀 위치로 옮기는 근사 선형식. 도쿄/파리/방콕/두바이/
# 레이캬비크/LA 6개 도시의 실제 위경도와, 지도 이미지에서 육안으로 확인한 픽셀
# 위치를 최소제곱으로 맞춰서 구함 (완벽히 표준적인 정사각도법은 아니라 국가마다
# 손으로 다듬은 지도라 공식만으로 100% 정확하진 않지만, 핀 위치로는 충분함).
_MAP_X_SCALE, _MAP_X_OFFSET = 7.9148, 1245.8989
_MAP_Y_SCALE, _MAP_Y_OFFSET = -7.5120, 738.0763
WORLD_MAP_VIEWBOX_W = 2752.766
# 예전엔 980으로 잘라 남극 여백을 지웠는데, 그 높이에서는 호주·뉴질랜드·남미
# 남부까지 프레임 밖으로 잘려나가 버렸다. 원본 전체 높이를 그대로 써서 지도에
# 안 보이는 땅이 없게 한다.
WORLD_MAP_VIEWBOX_H = 1537.631


def _country_pin_percent(geo_str):
    """'lat;lon' 문자열을 지도 프레임 기준 (left%, top%) 픽셀 위치로 변환."""
    lat_s, lon_s = geo_str.split(";")
    lat, lon = float(lat_s), float(lon_s)
    x = _MAP_X_SCALE * lon + _MAP_X_OFFSET
    y = _MAP_Y_SCALE * lat + _MAP_Y_OFFSET
    return x / WORLD_MAP_VIEWBOX_W * 100, y / WORLD_MAP_VIEWBOX_H * 100


@st.cache_data(show_spinner=False)
def _load_world_map_svg():
    """실제 세계지도 SVG(퍼블릭 도메인)를 낡은 가죽지도(트레저맵) 팔레트로 재색칠해서
    불러온다. 국경선/대륙 모양 데이터는 원본 그대로 두고 색상만 세피아 톤으로 바꾼다.
    우리 6개 여행지 국가만 포인트 컬러로 강조."""
    raw = (ASSETS / "world_map.svg").read_text(encoding="utf-8")
    raw = raw.replace(
        'viewBox="0 0 2752.766 1537.631"',
        f'viewBox="0 0 {WORLD_MAP_VIEWBOX_W} {WORLD_MAP_VIEWBOX_H}"',
    )
    # width/height를 "100%"로 두면 SVG가 고유 크기(intrinsic size) 없는 상태가 되는데,
    # 인라인 <svg>로 쓸 때는 위 .world-map-frame svg{width:100%;height:100%} CSS가
    # 어차피 덮어써서 문제가 없지만, CSS background-image로 쓸 때는 브라우저가 크기를
    # 특정할 기준이 없어 background-size/position 퍼센트 계산이 예측 불가능하게 깨진다
    # (확대 지도 기능에서 실측으로 확인됨). viewBox와 동일한 절대 px 값을 줘서 두 용도
    # 모두에서 같은 좌표계 기준(1 유닛 = 1px)을 갖도록 고정한다.
    raw = re.sub(r'\sheight="[0-9.]+"', f' height="{WORLD_MAP_VIEWBOX_H}"', raw, count=1)
    raw = re.sub(r'\swidth="[0-9.]+"', f' width="{WORLD_MAP_VIEWBOX_W}"', raw, count=1)
    highlight = ",".join(f".{code}" for code in COUNTRIES)
    # 강조할 국가마다 자기 <path>에 직접 클래스가 붙어있는 경우(중국/한국 등 —
    # 이땐 svg path{...} 베이스 규칙과 동일한 요소를 다투므로 클래스 선택자가 더
    # 높은 명시도로 이김)와, 큰 본토 도형은 클래스 없이 상위 <g class="...">에만
    # 클래스가 있고 상속으로만 색이 내려오는 경우(호주 등 — 이땐 자기 자신에게
    # 직접 걸리는 svg path{...} 베이스 규칙이 상속값을 항상 이겨버려 핑크가 전혀
    # 안 먹혔다)가 섞여 있다. `.국가 path`로 자손까지 명시적으로 짚어주면 두
    # 경우 모두 명시도로 베이스 규칙을 이기게 되어 국가마다 다른 이 구조 차이에
    # 상관없이 항상 강조색이 적용된다.
    highlight_desc = ",".join(f".{code} path" for code in COUNTRIES)
    raw = raw.replace(
        "</svg>",
        # 국가 대부분은 class="land ..."로 묶여 있지만, 원본 파일에 class 없이
        # id만 있고 자기 style에 회색을 박아둔 나라가 섞여 있어서(수단 등) .land
        # 클래스만 override하면 그런 나라만 회색으로 튀어 보인다. path 전체에
        # 기본색을 먼저 깔고, 바다/호수/강조국만 그 위에 다시 덮는다.
        # 낡은 가죽지도(트레저맵) 느낌 — 세피아 톤의 육지/바다 + 짙은 갈색 국경선.
        # 강조 국가만 원래 쓰던 핑크로 남겨서 핀 색상과 톤이 이어지게 한다.
        "<style>svg path{fill:#dccb98 !important;stroke:#6b4423 !important;stroke-width:1.1 !important;}"
        ".ocean,.lake{fill:#b9a06d !important;stroke:none !important;}"
        f"{highlight},{highlight_desc}"
        "{fill:#ff6fb8 !important;stroke:#a53d78 !important;}</style></svg>",
    )
    return " ".join(raw.split())


def _aqi_level_label(aqi):
    """WAQI 지수(미국 EPA 기준)를 한글 등급으로 변환."""
    if aqi <= 50:
        return "🟢 좋음"
    if aqi <= 100:
        return "🟡 보통"
    if aqi <= 150:
        return "🟠 민감군 주의"
    if aqi <= 200:
        return "🔴 나쁨"
    if aqi <= 300:
        return "🟣 매우 나쁨"
    return "🟤 위험"


@st.cache_data(show_spinner=False, ttl=1800)
def get_air_quality(feed_path):
    """WAQI(World Air Quality Index) API에서 실시간 미세먼지 지수를 가져온다.

    feed_path는 특정 측정소 경로(예: "japan/shinjuku-ku-/kuni-tokyo--shinjuku-/",
    aqicn.org 도시 페이지 URL과 동일한 형식) 또는 좌표 기반 "geo:lat;lon" 형식.
    """
    if not WAQI_TOKEN:
        return None
    try:
        resp = requests.get(
            f"https://api.waqi.info/feed/{feed_path}/",
            params={"token": WAQI_TOKEN},
            timeout=5,
        )
        data = resp.json()
        if data.get("status") != "ok":
            return None
        d = data["data"]
        iaqi = d.get("iaqi") or {}
        return {
            "aqi": d.get("aqi"),
            "pm25": (iaqi.get("pm25") or {}).get("v"),
            "pm10": (iaqi.get("pm10") or {}).get("v"),
            "station": (d.get("city") or {}).get("name", ""),
        }
    except (requests.RequestException, ValueError, KeyError):
        return None


SKIN_TYPES = ["건성", "지성", "복합성"]
SKIN_TYPE_EXTRAS = ["민감성", "트러블"]
GENDERS = ["여성", "남성", "자유롭게"]
CLOTHING = ["캐주얼", "러블리", "스트릿", "미니멀"]
HAIR_TYPES = ["스트레이트", "웨이브", "컬리", "숏컷"]
AGE_RANGES = ["10대", "20대", "30대", "40대+"]
SKIN_TONES = [
    {"id": "light", "hex": "#FFE0C4", "label": "라이트"},
    {"id": "medium", "hex": "#F2B98A", "label": "미디엄"},
    {"id": "deep", "hex": "#C68858", "label": "딥"},
]

# 피부타입/특이사항 -> 상태 뱃지(이모지+문구). 실사 캐릭터 그래픽 변형 대신
# 텍스트+이모지 뱃지로 피부 상태를 표현한다 — 아래 get_skin_profile()을 통해
# 패스포트 카드뿐 아니라 빠른 팁/AI 추천 등 다른 로직에서도 공통으로 재사용한다.
SKIN_TYPE_BADGES = {
    "건성": {"emoji": "🌾", "text": "푸석 주의 피부"},
    "지성": {"emoji": "✨", "text": "번들거림 주의 피부"},
    "복합성": {"emoji": "🌗", "text": "부위별 밸런스 피부"},
}
SKIN_EXTRA_BADGES = {
    "민감성": {"emoji": "🌸", "text": "민감 케어 필요"},
    "트러블": {"emoji": "🔥", "text": "트러블 케어 필요"},
}

# 캐릭터 미리보기 인형이 옷 스타일별로 입는 색 배합
CLOTHING_STYLES = {
    "캐주얼": {"top": "#4a5d7a", "bottom": "#33333d", "shoe": "#f4f4f4", "sole": "#222222", "skirt": False},
    "러블리": {"top": "#ff9ecb", "bottom": "#fff3e0", "shoe": "#ffffff", "sole": "#ff8fc0", "skirt": True},
    "스트릿": {"top": "#3a3a3a", "bottom": "#5c6b4a", "shoe": "#1a1a1a", "sole": "#ffffff", "skirt": False},
    "미니멀": {"top": "#efe9df", "bottom": "#a8a8a8", "shoe": "#ffffff", "sole": "#cccccc", "skirt": False},
}
HAIR_COLOR = "#4a3428"

PERSONALITY_TRAITS = ["발랄한", "차분한", "모험적인", "감성적인", "도시적인", "자연친화적인", "사교적인", "독립적인"]
TRAVEL_STYLES = ["휴양형", "액티비티형", "맛집탐방형", "문화탐방형", "쇼핑형", "자연탐방형"]
COSMETIC_PREFS = ["저자극", "고보습", "미백", "산뜻한 마무리", "자외선 차단", "안티에이징", "모공 케어", "트러블 케어"]

# 옷장/액세서리 10개 선택지 생성용 색상 팔레트 (이름, hex)
COLOR_PALETTE_10 = [
    ("화이트", "#FFFFFF"), ("베이지", "#E8DCC8"), ("그레이", "#B9B9B9"), ("블랙", "#1C1C1C"),
    ("네이비", "#233158"), ("스카이블루", "#8FD3F4"), ("핑크", "#FFB6D9"), ("레드", "#E14B4B"),
    ("옐로우", "#F4D35E"), ("브라운", "#8B5E3C"),
]


def _build_catalog(prefix, types):
    """색상 10개 x 종류 목록을 돌려가며 짜서 정확히 10개의 (종류+색상) 조합을 만든다.
    shape_idx는 types 안에서 몇 번째 종류인지 — 실제 옷 모양 SVG를 고를 때 씀."""
    items = []
    for i in range(len(COLOR_PALETTE_10)):
        shape_idx = i % len(types)
        type_name = types[shape_idx]
        color_name, hex_color = COLOR_PALETTE_10[i]
        items.append({"id": f"{prefix}_{i:02d}", "label": f"{color_name} {type_name}",
                      "hex": hex_color, "shape_idx": shape_idx})
    return items


CLOSET_CATALOG = {
    "top": {"title": "상의", "icon": "👕",
            "items": _build_catalog("top", ["티셔츠", "니트", "셔츠", "후드티", "블라우스"])},
    "bottom": {"title": "하의", "icon": "👖",
               "items": _build_catalog("bottom", ["청바지", "슬랙스", "반바지", "치마", "레깅스"])},
    "socks": {"title": "양말", "icon": "🧦",
              "items": _build_catalog("socks", ["짧은양말", "긴양말", "니삭스", "레이스양말", "패턴양말"])},
    "shoes": {"title": "신발", "icon": "👟",
              "items": _build_catalog("shoes", ["스니커즈", "로퍼", "부츠", "샌들", "플랫슈즈"])},
    "hat": {"title": "모자", "icon": "🎩",
            "items": _build_catalog("hat", ["캡모자", "버킷햇", "비니", "베레모", "밀짚모자"])},
}
ACCESSORY_CATALOG = {
    "necklace": {"title": "목걸이", "icon": "📿",
                 "items": _build_catalog("necklace", ["체인목걸이", "진주목걸이", "펜던트", "초커", "레이어드목걸이"])},
    "sunglasses": {"title": "선글라스", "icon": "🕶️",
                   "items": _build_catalog("sunglasses", ["라운드형", "캣아이형", "스퀘어형", "오버사이즈형", "스포츠형"])},
    "gloves": {"title": "장갑", "icon": "🧤",
               "items": _build_catalog("gloves", ["니트장갑", "가죽장갑", "레이스장갑", "스포츠장갑", "벙어리장갑"])},
}
ALL_CATALOGS = {**CLOSET_CATALOG, **ACCESSORY_CATALOG}


def _catalog_hex(cat_key, item_id):
    if not item_id:
        return None
    catalog = ALL_CATALOGS.get(cat_key)
    if not catalog:
        return None
    return next((it["hex"] for it in catalog["items"] if it["id"] == item_id), None)


def _catalog_label(cat_key, item_id):
    if not item_id:
        return None
    catalog = ALL_CATALOGS.get(cat_key)
    if not catalog:
        return None
    return next((it["label"] for it in catalog["items"] if it["id"] == item_id), None)


# 뷰티 패스포트 표지 — 참고 사진(핑크 책 표지 + PASSPORT 문구 + 조개 + 모서리
# 낙서)을 우리 팔레트로 재현한 SVG. 작은 아이콘 버튼과 확대된 표지에 이
# 그래픽을 그대로 재사용해서 "아이콘이 그대로 커진다"가 실제로 맞아떨어지게 한다.
PASSPORT_ICON_SVG = """
<svg viewBox="0 0 200 240" width="200" height="240" xmlns="http://www.w3.org/2000/svg">
  <g transform="rotate(-7 100 130)">
    <path d="M22 30 L152 10 L163 26 L33 46 Z" fill="#ffd9ec"/>
    <rect x="26" y="32" width="148" height="196" rx="16" fill="#ff6fb8" stroke="#6b1638" stroke-width="3.5"/>
    <path d="M158 46 q7 3 3 11" stroke="#6b1638" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M40 214 q-5 6 1 11" stroke="#6b1638" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M48 218 q-5 6 1 11" stroke="#6b1638" stroke-width="3" fill="none" stroke-linecap="round"/>
    <text x="100" y="108" text-anchor="middle" font-family="Gaegu, sans-serif" font-size="27"
          font-weight="700" fill="#ffffff" transform="rotate(-2 100 108)">PASSPORT</text>
    <g transform="translate(100 178)" stroke="#ffffff" stroke-width="2.4" fill="none" stroke-linecap="round">
      <path d="M-30 10c0-20 13-34 30-34s30 14 30 34c0 7-5 12-12 12H-18c-7 0-12-5-12-12Z"/>
      <path d="M0-24v46M-10-21c0 14 2 27 10 41M10-21c0 14-2 27-10 41M-20-16c2 11 7 22 20 34M20-16c-2 11-7 22-20 34"/>
    </g>
  </g>
</svg>
"""
PASSPORT_ICON_URI = "data:image/svg+xml;base64," + base64.b64encode(PASSPORT_ICON_SVG.strip().encode()).decode()

# 피부 궁합 진단 입구 아이콘 — 사용자가 준 참고 사진(유리 플라스크 + 빨간 액체 +
# 코르크 마개)을 재현한 SVG. 작은 상단 아이콘과 진단 화면의 큰 버튼에 그대로 재사용.
POTION_ICON_SVG = """
<svg viewBox="0 0 100 130" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="potionLiquid" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ff8a7a"/>
      <stop offset="55%" stop-color="#f23b3b"/>
      <stop offset="100%" stop-color="#c81e2c"/>
    </linearGradient>
    <linearGradient id="potionCork" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#f0d49a"/>
      <stop offset="100%" stop-color="#c99a5c"/>
    </linearGradient>
  </defs>
  <path d="M42,6 L58,6 L61,22 L39,22 Z" fill="url(#potionCork)" stroke="#7a5a30" stroke-width="2.4"/>
  <line x1="45" y1="10" x2="50" y2="18" stroke="#a97c40" stroke-width="1.4" opacity=".6"/>
  <line x1="52" y1="9" x2="56" y2="17" stroke="#a97c40" stroke-width="1.4" opacity=".6"/>
  <rect x="40" y="21" width="20" height="8" rx="2" fill="#cdeffb" stroke="#5a7d8a" stroke-width="1.8"/>
  <path d="M40,28 L38,41 Q14,53 14,79 Q14,109 50,109 Q86,109 86,79 Q86,53 62,41 L60,28 Z"
        fill="#eaf7fb" stroke="#3a2a1a" stroke-width="3.4" opacity=".95"/>
  <path d="M18,69 Q18,103 50,103 Q82,103 82,69 Q82,59 74,51 L26,51 Q18,59 18,69 Z" fill="url(#potionLiquid)"/>
  <ellipse cx="50" cy="52" rx="24" ry="4" fill="#ff9a8d" opacity=".7"/>
  <circle cx="40" cy="73" r="4.2" fill="#ffb3a3" opacity=".55"/>
  <circle cx="61" cy="87" r="3.2" fill="#ffb3a3" opacity=".5"/>
  <circle cx="34" cy="91" r="2.6" fill="#ffcfc4" opacity=".6"/>
  <path d="M26,53 Q20,70 24,94" stroke="#ffffff" stroke-width="4.5" fill="none"
        stroke-linecap="round" opacity=".55"/>
  <circle cx="30" cy="47" r="3.4" fill="#ffffff" opacity=".7"/>
</svg>
"""
POTION_ICON_URI = "data:image/svg+xml;base64," + base64.b64encode(POTION_ICON_SVG.strip().encode()).decode()

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
if "char_draft" not in st.session_state:
    st.session_state.char_draft = {}
if "passport" not in st.session_state:
    st.session_state.passport = []
if "view" not in st.session_state:
    st.session_state.view = "home"
if "selected_country" not in st.session_state:
    st.session_state.selected_country = None
if "closet_category" not in st.session_state:
    st.session_state.closet_category = None
if "map_globe_opened" not in st.session_state:
    st.session_state.map_globe_opened = False  # 지도 화면에서 지구본을 눌러 펼쳤는지
if "show_page_transition" not in st.session_state:
    st.session_state.show_page_transition = False
if "bubble_specs" not in st.session_state:
    st.session_state.bubble_specs = None
if "show_passport" not in st.session_state:
    st.session_state.show_passport = False
if "passport_page_open" not in st.session_state:
    st.session_state.passport_page_open = False
if "just_opened_passport_page" not in st.session_state:
    st.session_state.just_opened_passport_page = False
if "passport_notes" not in st.session_state:
    st.session_state.passport_notes = []  # 적립된 "나만의 여행 꿀팁" 목록 (각 항목 = 한 줄)
if "passport_stores" not in st.session_state:
    st.session_state.passport_stores = []  # ⭐로 저장한 드럭스토어/뷰티스토어 목록
if "tip_input_counter" not in st.session_state:
    st.session_state.tip_input_counter = 0  # 입력창을 매번 새 위젯으로 만들어 제출 후 비우기 위한 값
if "country_stage" not in st.session_state:
    st.session_state.country_stage = "map"  # "map"(확대 지도+포스트잇) | "scene"(캐릭터+아이콘)
if "active_country_sheet" not in st.session_state:
    st.session_state.active_country_sheet = None  # water/lipstick/shop/hair/carrier 중 열린 바텀시트
if "just_saved_country_sparkle" not in st.session_state:
    st.session_state.just_saved_country_sparkle = False
if "just_entered_country_scene" not in st.session_state:
    st.session_state.just_entered_country_scene = False  # 지도->캐릭터 장면 전환 시 팝인 애니메이션 1회용
if "diagnosis_stage" not in st.session_state:
    st.session_state.diagnosis_stage = "select"  # "select" | "brewing" | "result"
if "diagnosis_country" not in st.session_state:
    st.session_state.diagnosis_country = None
if "diagnosis_result" not in st.session_state:
    st.session_state.diagnosis_result = None


def get_character():
    return st.session_state.character


def get_skin_profile(char):
    """캐릭터의 피부타입/특이사항을 정규화한 프로필 — 뷰티 패스포트 뱃지 표시와
    이후의 모든 추천/진단 로직(빠른 팁, AI 코스메틱 추천, 애프터케어 등)이 공통
    입력값으로 재사용한다. 실사 캐릭터 그래픽 변형 없이 이모지+문구 뱃지로만
    피부 상태를 표현하는 현재 단계의 대체 표현이기도 하다."""
    char = char or {}
    skin_type = char.get("skin_type") or SKIN_TYPES[0]
    extras = list(char.get("skin_type_extra") or [])
    type_badge = SKIN_TYPE_BADGES.get(skin_type, SKIN_TYPE_BADGES[SKIN_TYPES[0]])
    extra_badges = [
        {"key": extra, **SKIN_EXTRA_BADGES[extra]} for extra in extras if extra in SKIN_EXTRA_BADGES
    ]
    return {
        "skin_type": skin_type,
        "extras": extras,
        "skin_tone": char.get("skin_tone") or SKIN_TONES[0]["hex"],
        "badge_emoji": type_badge["emoji"],
        "badge_text": type_badge["text"],
        "extra_badges": extra_badges,
    }


# ----------------------------------------------------------------------
# 피부 궁합 진단 — 규칙 기반 계산. 데이터 출처(환경 데이터)와 계산 로직(궁합
# 점수)을 서로 다른 함수로 분리해뒀다: get_destination_environment_data()는
# 지금은 더미 데이터를 돌려주지만, 나중에 실제 기상/수질 API로 교체할 때 이
# 함수 안쪽만 바꾸면 되고 calculate_skin_compatibility() 쪽은 손댈 필요가
# 없다.
# ----------------------------------------------------------------------
# COUNTRIES의 자유서술형 문구(예: "평균 65% (한국보다 다소 높음)")와 실제
# 값이 어긋나지 않도록, 각 나라 설명에 이미 적힌 숫자를 그대로 옮겨 적었다.
_DESTINATION_ENV_DUMMY = {
    "jp": {"humidity_pct": 65, "uv_index": 8, "water_hardness": "soft"},
    "fr": {"humidity_pct": 40, "uv_index": 4, "water_hardness": "hard"},
    "th": {"humidity_pct": 75, "uv_index": 10, "water_hardness": "hard"},
    "ae": {"humidity_pct": 25, "uv_index": 11, "water_hardness": "hard"},
    "is": {"humidity_pct": 75, "uv_index": 2, "water_hardness": "soft"},
    "us": {"humidity_pct": 45, "uv_index": 8, "water_hardness": "hard"},
    "au": {"humidity_pct": 65, "uv_index": 11, "water_hardness": "soft"},
    "cn": {"humidity_pct": 75, "uv_index": 9, "water_hardness": "hard"},
    "kr": {"humidity_pct": 65, "uv_index": 8, "water_hardness": "soft"},
}


def get_destination_environment_data(country_code):
    """목적지의 기후(습도)·자외선·수질 데이터를 반환한다. 지금은 COUNTRIES의
    문구에서 그대로 옮긴 더미 값이지만, 실제 기상/수질 API로 교체할 지점을
    한곳으로 모아두기 위해 별도 함수로 분리했다."""
    return dict(_DESTINATION_ENV_DUMMY.get(country_code, _DESTINATION_ENV_DUMMY["kr"]))


def _is_light_skin_tone(skin_tone_hex):
    return (skin_tone_hex or "").upper() == SKIN_TONES[0]["hex"].upper()


def calculate_skin_compatibility(user_skin_profile, environment_data):
    """피부타입 x 환경 조건을 규칙 기반으로 계산해 기후/자외선/물 3개 항목과
    그 평균(overall) 궁합 점수(0~100)를 반환한다.

    규칙:
    - 건성 + 습도 30% 이하 -> 기후 궁합 크게 낮음 (건성 + 45% 이하는 약하게)
    - 지성/트러블 + 습도 75% 이상 -> 기후 궁합 낮음 (유분·모공 트러블 위험)
    - 민감성 + 경수 -> 물 궁합 크게 낮음 (건성+경수도 약하게 감점)
    - 자외선지수 8 이상 + 밝은 피부톤 -> 자외선 궁합 크게 낮음
    """
    skin_type = user_skin_profile.get("skin_type")
    extras = user_skin_profile.get("extras") or []
    skin_tone = user_skin_profile.get("skin_tone")

    humidity = environment_data["humidity_pct"]
    uv = environment_data["uv_index"]
    hardness = environment_data["water_hardness"]

    climate = 85
    if skin_type == "건성" and humidity <= 30:
        climate -= 35
    elif skin_type == "건성" and humidity <= 45:
        climate -= 15
    if (skin_type == "지성" or "트러블" in extras) and humidity >= 75:
        climate -= 20
    climate = max(5, min(100, climate))

    water = 85
    if hardness == "hard":
        water -= 20
        if "민감성" in extras:
            water -= 25
        elif skin_type == "건성":
            water -= 10
    water = max(5, min(100, water))

    uv_score = 90
    if uv >= 8:
        uv_score -= 30
        if _is_light_skin_tone(skin_tone):
            uv_score -= 20
    elif uv >= 6:
        uv_score -= 15
    uv_score = max(5, min(100, uv_score))

    overall = round((climate + water + uv_score) / 3)
    return {"climate": climate, "water": water, "uv": uv_score, "overall": overall}


def _compatibility_band(pct):
    """점수 구간별 (색, 한줄 문구)."""
    if pct >= 80:
        return {"color": "#3cb872", "bg": "#e6f8ee", "text": "완전 찰떡궁합!"}
    if pct >= 50:
        return {"color": "#e0982a", "bg": "#fff6e0", "text": "괜찮은 편, 주의 필요"}
    return {"color": "#e0524a", "bg": "#fdeaea", "text": "케어를 단단히 준비해야 해요"}


def _compat_card_line(kind, score, environment_data, user_skin_profile):
    """상세 카드 한 줄 해석 문구."""
    if kind == "climate":
        if score >= 80:
            return "습도가 잘 맞아서 큰 걱정 없이 지낼 수 있어요"
        if score >= 50:
            return "평소보다 살짝 신경 써서 보습/유수분 관리를 하면 좋아요"
        return "습도 차이가 커서 각질·유분 트러블에 특히 대비해야 해요"
    if kind == "water":
        if score >= 80:
            return "수질이 잘 맞아서 세안 자극이 적을 편이에요"
        if score >= 50:
            return "세안 후 당김이 있을 수 있으니 저자극 제품을 챙기세요"
        return "경수 자극이 클 수 있어요 — 클렌징워터·킬레이팅 샴푸를 챙기세요"
    if kind == "uv":
        if score >= 80:
            return "자외선 부담이 적은 지역이라 기본 차단만으로 충분해요"
        if score >= 50:
            return "자외선이 꽤 강해요 — 선크림 재도포를 잊지 마세요"
        return "자외선이 매우 강해요 — 고자차 선크림과 애프터선 케어가 필수예요"
    return ""


def get_passport():
    return st.session_state.passport


def goto(view):
    st.session_state.view = view


# 화면 트리상 "뒤로" 가 어디를 가리키는지 — 히스토리 스택 없이 고정 계층으로 정의
PARENT_VIEW = {
    "character": "home",
    "closet": "character",
    "map": "character",
    "country": "map",
    "aftercare": "map",
    "diagnosis": "map",
}


def render_back_button():
    """모든 화면 좌상단에 뒤로가기 버튼을 표시한다 (홈처럼 상위 화면이 없으면 숨김)."""
    parent = PARENT_VIEW.get(st.session_state.view)
    if not parent:
        return
    html_block(
        """
        <style>
        .st-key-back_btn button {
            position: relative !important; z-index: 999999 !important;
            width: 46px !important; height: 46px !important;
            min-width: 46px !important; max-width: 46px !important;
            min-height: 46px !important; max-height: 46px !important;
            border-radius: 50% !important; padding: 0 !important;
            background: #ffffff !important; border: 3px solid #ff6fb8 !important;
            color: #ff3d97 !important; font-size: 1.4rem !important; font-weight: 900 !important;
            box-shadow: 0 4px 10px rgba(120,40,90,.25);
            transition: transform .12s ease;
        }
        .st-key-back_btn button:hover { transform: translateY(-2px) scale(1.05); }
        .st-key-back_btn button:active { transform: translateY(1px) scale(.97); }
        .st-key-back_btn { position: relative; z-index: 999999; margin: -0.5rem 0 .5rem 0; }
        </style>
        """
    )
    if st.button("←", key="back_btn", help="뒤로 가기"):
        goto(parent)
        st.rerun()


def render_top_icons():
    """홈을 제외한 모든 화면 우상단에 떠 있는 아이콘들 — 회색 사이드바 대신
    쓰는 내비게이션. 뷰티 패스포트는 누르면 st.dialog로 크게 뜬다.

    각 버튼은 자기 key로 생기는 .st-key-<key> 클래스에 바로 position:fixed를
    건다 (예전엔 st.container(key=...)로 한 번 더 감쌌었는데, 그 감싸는
    컨테이너 안에서는 fixed의 기준점이 뷰포트가 아니게 되는 문제가 있어서
    컨테이너 없이 버튼 자체에 직접 건다)."""
    if st.session_state.view == "home":
        return
    html_block(
        f"""
        <style>
        .st-key-nav_map_icon button, .st-key-open_passport_icon button, .st-key-open_diagnosis_icon button {{
            position: fixed !important; top: 60px !important;
            z-index: 99997 !important;
            width: 62px !important; height: 62px !important;
            min-width: 62px !important; max-width: 62px !important;
            min-height: 62px !important; max-height: 62px !important;
            border-radius: 50% !important; padding: 0 !important;
            background: #ffffff !important; border: 3px solid #ff6fb8 !important;
            font-size: 1.8rem !important; box-shadow: 0 4px 10px rgba(120,40,90,.25);
            transition: transform .12s ease;
        }}
        .st-key-nav_map_icon button {{ right: 92px !important; }}
        .st-key-open_passport_icon button {{ right: 16px !important; }}
        .st-key-open_diagnosis_icon button {{ right: 168px !important; }}
        .st-key-nav_map_icon button:hover, .st-key-open_passport_icon button:hover,
        .st-key-open_diagnosis_icon button:hover {{
            transform: translateY(-2px) scale(1.06);
        }}
        .st-key-nav_map_icon button:active, .st-key-open_passport_icon button:active,
        .st-key-open_diagnosis_icon button:active {{
            transform: translateY(1px) scale(.96);
        }}
        /* 뷰티 패스포트 아이콘만 참고 사진 그래픽으로 교체 */
        .st-key-open_passport_icon button {{
            background-image: url('{PASSPORT_ICON_URI}') !important;
            background-size: 155% 155% !important; background-position: center 42% !important;
            background-repeat: no-repeat !important; background-color: #fff8fb !important;
            color: transparent !important; font-size: 0 !important; overflow: hidden !important;
        }}
        /* 피부 궁합 진단 아이콘도 포션 그래픽으로 교체 */
        .st-key-open_diagnosis_icon button {{
            background-image: url('{POTION_ICON_URI}') !important;
            background-size: 105% 105% !important; background-position: center 60% !important;
            background-repeat: no-repeat !important; background-color: #fff8fb !important;
            color: transparent !important; font-size: 0 !important; overflow: hidden !important;
        }}
        </style>
        """
    )
    if st.button("🗺️", key="nav_map_icon", help="여행지 지도"):
        st.session_state.map_globe_opened = True  # 지구본 단계를 건너뛰고 세계지도를 바로 띄움
        goto("map" if get_character() else "character")
        st.rerun()
    if st.button("📔", key="open_passport_icon", help="뷰티 패스포트"):
        st.session_state.show_passport = True
        st.session_state.passport_page_open = False
        st.rerun()
    if st.button("🧪", key="open_diagnosis_icon", help="피부 궁합 진단"):
        if get_character():
            st.session_state.diagnosis_stage = "select"
            goto("diagnosis")
        else:
            goto("character")
        st.rerun()


PASSPORT_FIELD_LABELS = {
    "name": "NAME · 이름",
    "gender": "SEX · 성별",
    "age_range": "AGE · 연령대",
    "skin_type": "SKIN TYPE · 피부 타입",
    "hair_type": "HAIR · 헤어",
    "style": "STYLE · 패션 스타일",
    "travel_style": "TRAVEL STYLE · 여행 성향",
}


def _passport_bio_fields(char):
    """왼쪽 페이지 — 선택한 정보 전부 (여권 기본 페이지처럼 한 곳에 모아서)."""
    rows = ['<div class="p-field"><span class="p-label">NATIONALITY · 국적</span>'
            '<span class="p-value">Republic of Cosmax</span></div>']
    for key, label in PASSPORT_FIELD_LABELS.items():
        value = html.escape(str(char.get(key) or "-"))
        rows.append(f'<div class="p-field"><span class="p-label">{label}</span>'
                    f'<span class="p-value">{value}</span></div>')

    skin_extra = ", ".join(char.get("skin_type_extra") or []) or "-"
    rows.append(f'<div class="p-field"><span class="p-label">SKIN NOTE · 피부 특이사항</span>'
                f'<span class="p-value">{skin_extra}</span></div>')

    profile = get_skin_profile(char)
    badge_chips = [f'<span class="skin-badge">{profile["badge_emoji"]} {html.escape(profile["badge_text"])}</span>']
    for extra_badge in profile["extra_badges"]:
        badge_chips.append(f'<span class="skin-badge skin-badge-extra">{extra_badge["emoji"]} {html.escape(extra_badge["text"])}</span>')
    rows.append(f'<div class="p-field skin-badge-row">{"".join(badge_chips)}</div>')

    personality = ", ".join(char.get("personality") or []) or "-"
    cosmetic = ", ".join(char.get("cosmetic_prefs") or []) or "-"
    outfit = char.get("outfit") or {}
    acc = char.get("accessories") or {}
    equipped = [_catalog_label(k, v) for k, v in {**outfit, **acc}.items() if v]
    equipped_str = ", ".join(equipped) if equipped else "-"
    rows.append(f'<div class="p-field"><span class="p-label">PERSONALITY · 성격 특성</span>'
                f'<span class="p-value">{personality}</span></div>')
    rows.append(f'<div class="p-field"><span class="p-label">COSMETIC PREFS · 화장품 취향</span>'
                f'<span class="p-value">{cosmetic}</span></div>')
    rows.append(f'<div class="p-field"><span class="p-label">EQUIPPED · 착용 중</span>'
                f'<span class="p-value">{equipped_str}</span></div>')
    return "".join(rows)


def _passport_stamps_html(saved):
    if not saved:
        return '<div class="stamp-empty">아직 방문 스탬프가 없어요 — 지도에서 여행지를 저장해보세요 ✈️</div>'
    return "".join(
        f'<div class="stamp"><div class="stamp-flag">{p["flag"]}</div>'
        f'<div class="stamp-name">{p["name"]}</div></div>'
        for p in saved
    )


def _passport_dialog_css():
    html_block(
        """
        <style>
        /* role="dialog" 추정이 틀렸음 — 실제 프론트엔드 빌드를 뒤져보니 그
           속성은 팝오버/컬러피커에만 쓰이고 st.dialog 카드에는 안 붙어있었다.
           정확한 클래스명을 모를 때 가장 확실한 방법: data-testid="stDialog"
           안의 모든 div 배경을 통째로 투명화하고, 우리가 정말 원하는 부분
           (.page 등)만 아래에서 다시 명시적으로 색을 되살린다. */
        div[data-testid="stDialog"] div {
            background: transparent !important;
            box-shadow: none !important;
        }
        /* 다이얼로그 좌상단 제목("Beauty Passport" + 아이콘) 숨김 — 닫기(X)
           버튼은 별도 요소라 안 건드림. slot="title"은 프론트엔드 빌드에서
           직접 확인한 실제 속성. */
        div[data-testid="stDialog"] [slot="title"] { display: none !important; }
        .p-body { padding-top: 2px; }
        /* 펼친 책의 왼쪽/오른쪽 페이지 — 크림색 종이 + 가운데 제본선 그림자.
           오른쪽은 꿀팁 삭제 버튼이 필요해서 실제 st.container(key="page_right_card")로
           바꿨다 — 그래서 .page 대신 그 키 클래스에도 똑같이 페이지 박스 스타일을 준다.
           왼쪽보다 짧아 보이던 문제는, 두 페이지 모두 같은 넉넉한 최소 높이로 맞춰서 해결 */
        div[data-testid="stDialog"] .page,
        div[data-testid="stDialog"] .st-key-page_right_card {
            background: #fffaf3 !important; padding: 20px 20px 14px;
            min-height: 620px; box-sizing: border-box; border-style: solid !important;
            box-shadow: 0 18px 36px rgba(120,40,90,.34), inset 0 0 0 2px rgba(255,255,255,.55) !important;
        }
        /* 위/왼쪽은 밝은 핑크(빛을 받는 쪽), 아래/바깥쪽은 진한 로즈(그늘)로
           둘러 가죽 장정처럼 도드라진 느낌을 주고, 제본선 쪽엔 진한 안쪽
           그림자로 접힌 명암을 표현한다 */
        div[data-testid="stDialog"] .page-left {
            border-width: 6px !important;
            border-color: #ffcfe8 #b81862 #b81862 #ffcfe8 !important; /* top right bottom left */
            border-right: none !important; border-radius: 18px 0 0 18px;
            box-shadow:
                inset -18px 0 28px -12px rgba(30,5,30,.45),
                inset 0 3px 0 rgba(255,255,255,.6),
                0 18px 36px rgba(120,40,90,.34) !important;
        }
        div[data-testid="stDialog"] .st-key-page_right_card {
            border-width: 6px !important;
            border-color: #ffcfe8 #b81862 #b81862 #ffcfe8 !important; /* top right bottom left */
            border-left: none !important; border-radius: 0 18px 18px 0;
            box-shadow:
                inset 18px 0 28px -12px rgba(30,5,30,.45),
                inset 0 3px 0 rgba(255,255,255,.6),
                0 18px 36px rgba(120,40,90,.34) !important;
        }
        /* 컨테이너 안 요소(스탬프/제목/꿀팁 줄)끼리 기본 여백이 너무 헐렁해서 좁힘 */
        div[data-testid="stDialog"] .st-key-page_right_card div[data-testid="stVerticalBlock"] {
            gap: 6px !important;
        }
        @keyframes passport-reveal {
            0%   { opacity: 0; transform: translateY(-10px); }
            100% { opacity: 1; transform: translateY(0); }
        }
        .p-photo-row { display: flex; gap: 14px; align-items: center; margin-bottom: 8px; }
        div[data-testid="stDialog"] .p-photo-box {
            width: 86px; height: 108px; flex: 0 0 auto; border-radius: 10px;
            background: linear-gradient(160deg,#3b3f7a,#171933) !important;
            display: flex; align-items: center; justify-content: center; overflow: hidden;
            border: 2px solid #ff6fb8;
        }
        .p-photo-box svg { width: 92%; height: auto; }
        .p-name-big { font-family: 'Gaegu', cursive; font-weight: 700; font-size: 1.9rem; color: #9c2f5c; }
        .p-passport-no { font-family: 'Jua', sans-serif; font-size: 1rem; color: #b26; letter-spacing: 1px; }
        .p-field {
            display: flex; justify-content: space-between; gap: 10px;
            padding: 9px 2px; border-bottom: 1.5px dashed rgba(178,58,110,.3);
            font-family: 'Jua', sans-serif; font-size: 1.05rem;
        }
        .p-label { color: #b23a6e; flex: 0 0 46%; white-space: nowrap; }
        .p-value { color: #4a2035; font-weight: 700; text-align: right; flex: 1; }
        .skin-badge-row { justify-content: flex-start !important; flex-wrap: wrap; gap: 6px; }
        .skin-badge {
            display: inline-flex; align-items: center; gap: 4px;
            font-family: 'Jua', sans-serif; font-size: .92rem; font-weight: 700;
            color: #9c2f5c; background: #ffe3f0; border: 1.5px solid #ff9fd8;
            border-radius: 999px; padding: 4px 12px;
        }
        .skin-badge-extra { color: #7a3c9c; background: #f2e7ff; border-color: #c79bff; }
        .p-section-title {
            font-family: 'Gaegu', cursive; font-weight: 700; color: #9c2f5c;
            font-size: 1.45rem; margin: 16px 0 8px;
        }
        .stamps-grid { display: flex; flex-wrap: wrap; gap: 10px; padding-bottom: 6px; }
        div[data-testid="stDialog"] .stamp {
            width: 76px; text-align: center; padding: 8px 4px;
            border: 2.5px dashed #ff8fc0; border-radius: 12px;
            transform: rotate(-4deg); background: rgba(255,143,192,.06) !important;
        }
        .stamp:nth-child(even) { transform: rotate(3deg); }
        .stamp-flag { font-size: 1.6rem; }
        .stamp-name { font-family: 'Jua', sans-serif; font-size: .8rem; color: #9c2f5c; margin-top: 2px; }
        .stamp-empty { font-family: 'Jua', sans-serif; font-size: 1.05rem; color: #a06; opacity: .8; }
        /* 나만의 여행 꿀팁 — 적립된 항목 한 줄 + 옆의 ✕ 삭제 버튼 */
        .tip-entry {
            font-family: 'Gaegu', cursive; font-size: 1rem; color: #6a3d55;
            background: rgba(255,143,192,.08); border-radius: 8px; padding: 6px 10px;
            margin-bottom: 6px;
        }
        .tip-empty { font-family: 'Jua', sans-serif; font-size: .95rem; color: #a06; opacity: .8; }
        /* 꿀팁/스토어 삭제(✕) 버튼 — key가 del_tip_0, del_store_0... 로 매번 달라지므로
           부분일치 선택자로 전부 한 번에 스타일 준다 */
        div[data-testid="stDialog"] div[class*="st-key-del_tip_"] button,
        div[data-testid="stDialog"] div[class*="st-key-del_store_"] button {
            min-width: 0 !important; width: 30px !important; height: 30px !important;
            padding: 0 !important; border-radius: 50% !important; margin-top: 2px !important;
            background: rgba(255,111,184,.15) !important; border: 1.5px solid #ff8fc0 !important;
            color: #b23a6e !important; font-size: .85rem !important; line-height: 1 !important;
        }
        div[data-testid="stDialog"] div[class*="st-key-del_tip_"] button:hover,
        div[data-testid="stDialog"] div[class*="st-key-del_store_"] button:hover {
            background: rgba(255,111,184,.32) !important;
        }
        /* 여권 맨 아래에 붙는 한 줄 입력창 — 책의 일부처럼 핑크 테두리로 마감 */
        .st-key-tip_input_row { margin-top: -4px !important; margin-bottom: 10px !important; }
        .st-key-tip_input_row input {
            background-color: #fffdf6 !important;
            font-family: 'Gaegu', cursive !important; font-size: 1rem !important;
            color: #6a3d55 !important;
            border: 2px solid #ff9fd8 !important; border-radius: 10px !important;
            padding: 10px 14px !important;
        }
        .st-key-tip_input_row input:focus {
            border-color: #ff6fb8 !important; box-shadow: 0 0 0 3px rgba(255,111,184,.25) !important;
        }
        /* 닫힌 표지: 표지 그림 자체가 버튼 — 다른 글씨/버튼 없이 그림만 크게, 누르면 펼쳐짐.
           이미지는 버튼 자신의 background가 아니라 ::before 가상요소에 얹는다 —
           하트 버튼에서 이미 검증된 방식으로, 버튼 자체의 background/width에 직접
           걸면 Streamlit 내부 스타일에 밀려 안 먹히는 경우가 있었다.
           .st-key-...를 두 번 겹쳐 써서 명시도도 추가로 올려둠. */
        /* 카드/배경 없이 여권 그림 자체만 떠 있게 — 배경은 완전히 투명 */
        .st-key-open_passport_cover.st-key-open_passport_cover button {
            position: relative !important;
            width: 100% !important; height: 480px !important; padding: 0 !important;
            min-width: 0 !important; max-width: none !important;
            border: none !important; border-radius: 0 !important; box-sizing: border-box !important;
            background: transparent !important; box-shadow: none !important;
            color: transparent !important; font-size: 0 !important; overflow: hidden !important;
            transition: transform .15s ease;
        }
        .st-key-open_passport_cover.st-key-open_passport_cover button::before {
            content: ''; position: absolute; inset: 4px;
            background-image: url('__PASSPORT_URI__');
            background-size: contain; background-position: center; background-repeat: no-repeat;
        }
        .st-key-open_passport_cover.st-key-open_passport_cover button:hover { transform: scale(1.02); }
        .st-key-open_passport_cover.st-key-open_passport_cover button:active { transform: scale(.98); }
        </style>
        """.replace("__PASSPORT_URI__", PASSPORT_ICON_URI)
    )


def _dismiss_passport():
    """다이얼로그 기본 X/ESC/바깥 클릭으로 닫았을 때도 show_passport를 꺼준다.

    이걸 안 하면 우리 쪽 상태는 계속 True로 남아있어서, 그 뒤 화면 아무
    곳이나 클릭해 스크립트가 다시 실행될 때마다 여권이 또 뜨는 버그가 생김
    (기본 X는 우리 코드를 거치지 않고 프레임워크가 자체적으로 닫기 때문)."""
    st.session_state.show_passport = False
    st.session_state.passport_page_open = False


@st.dialog("Beauty Passport", width="large", icon="📔", on_dismiss=_dismiss_passport)
def _beauty_passport_dialog():
    _passport_dialog_css()
    char = get_character() or {}
    draft_name = (st.session_state.get("char_draft") or {}).get("name", "").strip()
    if draft_name:
        char = {**char, "name": draft_name}

    if not st.session_state.passport_page_open:
        # 닫힌 표지 — 그림 자체를 누르면 펼쳐진다 (별도 안내 문구/버튼 없음)
        if st.button(" ", key="open_passport_cover", use_container_width=True):
            st.session_state.passport_page_open = True
            st.session_state.just_opened_passport_page = True
            st.rerun()
        return

    doll_svg = character_doll_svg(char) if char else ""
    just_opened = st.session_state.just_opened_passport_page
    reveal_rule = "animation: passport-reveal .4s ease both;" if just_opened else ""
    st.session_state.just_opened_passport_page = False

    # 펼친 여권 — 왼쪽 신원 페이지 / 오른쪽 스탬프+꿀팁 페이지, 책처럼 나란히
    left_page, right_page = st.columns(2, gap=None)

    with left_page:
        html_block(
            f"""
            <div class="page page-left" style="{reveal_rule}">
                <div class="p-photo-row">
                    <div class="p-photo-box">{doll_svg}</div>
                    <div>
                        <div class="p-name-big">{html.escape(char.get("name") or "여행자")}</div>
                        <div class="p-passport-no">NO. COSMAX-0001</div>
                    </div>
                </div>
                {_passport_bio_fields(char)}
            </div>
            """
        )

    with right_page:
        # 오른쪽은 꿀팁마다 ✕ 삭제 버튼이 있어야 해서, 문자열 HTML 한 덩어리가
        # 아니라 실제 st.container(위/아래 왼쪽 페이지와 똑같은 여권 박스로
        # CSS에서 스타일링)로 만들고 그 안에 진짜 버튼들을 넣는다.
        if just_opened:
            html_block('<style>.st-key-page_right_card{animation: passport-reveal .4s ease both;}</style>')
        with st.container(key="page_right_card"):
            html_block(
                f"""
                <div class="p-section-title">✈ VISA STAMPS</div>
                <div class="stamps-grid">{_passport_stamps_html(get_passport())}</div>
                <div class="p-section-title">✏️ 나만의 여행 꿀팁</div>
                """
            )
            notes = st.session_state.passport_notes
            if not notes:
                html_block('<div class="tip-empty">아직 적은 꿀팁이 없어요 — 맨 아래 칸에 적어보세요 ✎</div>')
            else:
                for i, note in enumerate(notes):
                    tip_col, del_col = st.columns([6, 1], gap="small", vertical_alignment="center")
                    with tip_col:
                        html_block(f'<div class="tip-entry">🩷 {html.escape(note)}</div>')
                    with del_col:
                        if st.button("✕", key=f"del_tip_{i}", help="이 꿀팁 삭제"):
                            st.session_state.passport_notes.pop(i)
                            st.rerun()

            html_block('<div class="p-section-title">🛍️ 저장한 뷰티 스토어</div>')
            stores = st.session_state.passport_stores
            if not stores:
                html_block(
                    '<div class="tip-empty">아직 저장한 스토어가 없어요 — '
                    '드럭스토어 목록에서 ⭐을 눌러보세요</div>'
                )
            else:
                for i, s in enumerate(stores):
                    store_col, del_store_col = st.columns([6, 1], gap="small", vertical_alignment="center")
                    with store_col:
                        html_block(f'<div class="tip-entry">{s["flag"]} {html.escape(s["label"])}</div>')
                    with del_store_col:
                        if st.button("✕", key=f"del_store_{i}", help="이 스토어 삭제"):
                            st.session_state.passport_stores.pop(i)
                            st.rerun()

    # 여권 맨 아래에 붙는 한 줄 입력창 — 여기 적고 Enter 치면 위 '나만의 여행
    # 꿀팁' 목록에 새 줄로 쌓인다. key를 매번 바꿔서(tip_input_counter)
    # 제출 후 입력창이 자동으로 비워지게 한다.
    with st.container(key="tip_input_row"):
        new_tip = st.text_input(
            "나만의 여행 꿀팁 추가", key=f"tip_input_{st.session_state.tip_input_counter}",
            placeholder="✎ 나만의 여행 꿀팁을 적고 Enter를 눌러보세요", label_visibility="collapsed",
        )
    if new_tip and new_tip.strip():
        st.session_state.passport_notes.append(new_tip.strip())
        st.session_state.tip_input_counter += 1
        st.rerun()

    if st.button("✕ 닫기", key="close_passport_btn", use_container_width=True):
        st.session_state.show_passport = False
        st.session_state.passport_page_open = False
        st.rerun()


def render_passport_modal():
    """뷰티 패스포트 — Streamlit 공식 st.dialog로 구현 (뷰포트 중앙 고정,
    배경 어둡게, ESC/바깥클릭 닫기까지 프레임워크가 처리해줘서 우리가
    직접 만든 position:fixed 오버레이보다 훨씬 안정적이다).
    show_passport가 True인 한 매 스크립트 실행마다 다이얼로그 함수를 다시
    호출해야 열린 상태가 유지된다 (호출하지 않으면 다음 리런에 닫힘)."""
    if st.session_state.show_passport:
        _beauty_passport_dialog()


BUBBLE_GRID_COLS = 18
BUBBLE_GRID_ROWS = 8
BUBBLE_GRID_SIZE_VH = (30, 43)  # 뷰포트 높이 기준 % — 가로세로 어떤 화면이든 비율 유지


def _organic_radius():
    """완전한 원이 아니라 살짝 삐뚠 방울 모양이 되도록 코너별로 다른 반경."""
    v = [round(random.uniform(46, 54)) for _ in range(8)]
    return f"{v[0]}% {v[1]}% {v[2]}% {v[3]}% / {v[4]}% {v[5]}% {v[6]}% {v[7]}%"


def _generate_bubble_specs():
    """화면을 뒤덮을 기포 배치를 만든다. 무작위 배치가 아니라 격자(grid)로
    깔아서 수학적으로 빈틈이 없도록 하고, 그 위에 작은 기포를 더 얹어
    이음새를 자연스럽게 메꾼다 (자세한 커버리지 검증은 코드 하단 참고).

    큰 기포는 반지름 대비 격자 간격을 좁게 잡아 이웃과 넉넉히 겹치고,
    홀수 행은 반 칸씩 어긋나게(벽돌쌓기) 배치해 대각선 틈까지 막는다.
    각 기포는 도착 후 '쉬는' 위치(top/left)를 갖는다. 덮는 단계에서는 그
    위치까지 아래에서 떠올라 멈추고, 걷히는 단계에서는 같은 위치에서
    시작해 계속 위로 사라진다 — 두 렌더 사이(서버 sleep 경계)에도 기포
    배치가 그대로 이어지도록 st.session_state에 저장해 재사용한다.
    """
    specs = []
    col_pitch = 100 / BUBBLE_GRID_COLS
    row_pitch = 100 / BUBBLE_GRID_ROWS
    # 격자를 화면 경계 바깥으로 한 칸씩 넉넉히 확장 — 안 그러면 가장자리
    # 쪽 기포 중심이 항상 화면 안쪽으로 치우쳐서 테두리에 얇은 틈이 남는다
    # (실측 검증: 확장 전 가장자리 3% 이내에 누락 좌표가 전부 몰려있었음)
    for r in range(-1, BUBBLE_GRID_ROWS + 1):
        row_offset = col_pitch / 2 if r % 2 != 0 else 0
        for c in range(-1, BUBBLE_GRID_COLS + 1):
            left = c * col_pitch + row_offset + random.uniform(-col_pitch * 0.7, col_pitch * 0.7)
            top = r * row_pitch + random.uniform(-row_pitch * 0.65, row_pitch * 0.65)
            specs.append({
                "kind": "lg", "unit": "vh",
                "size": round(random.uniform(*BUBBLE_GRID_SIZE_VH), 1),
                "left": round(left, 1),
                "top": round(top, 1),
                "delay": round(random.uniform(0, 0.25), 2),
                "dur": round(random.uniform(0.5, 0.8), 2),
                "op": round(random.uniform(.92, .99), 2),
                "br": _organic_radius(),
                "hlx": round(random.uniform(22, 36), 1),
                "hly": round(random.uniform(18, 32), 1),
            })
    # 격자 이음새를 메꾸는 보조 기포 (작고 가벼운 렌더링, 개수를 줄여 덜 산만하게)
    for _ in range(80):
        specs.append({
            "kind": "sm", "unit": "px",
            "size": round(random.uniform(30, 110)),
            "left": round(random.uniform(-2, 100), 1),
            "top": round(random.uniform(-2, 100), 1),
            "delay": round(random.uniform(0, 0.3), 2),
            "dur": round(random.uniform(0.45, 0.75), 2),
            "op": round(random.uniform(.88, .98), 2),
        })
    return specs


def _verify_bubble_coverage(specs, viewport_w, viewport_h, grid_n=60):
    """(자체 점검용) 기포들이 실제로 화면을 몇 % 덮는지 좌표 샘플링으로 계산.

    각 큰/작은 기포를 최종 '쉬는' 위치의 원으로 보고, grid_n x grid_n 개의
    표본점이 어느 원 안에 하나라도 들어가는지 검사해 커버리지 비율을 낸다.
    """
    circles = []
    for s in specs:
        diameter_px = s["size"] * (viewport_h / 100) if s["unit"] == "vh" else s["size"]
        # top/left는 요소의 좌상단 모서리 기준이므로 반지름만큼 더해 중심을 구한다
        cx = s["left"] / 100 * viewport_w + diameter_px / 2
        cy = s["top"] / 100 * viewport_h + diameter_px / 2
        circles.append((cx, cy, diameter_px / 2))

    covered = 0
    total = grid_n * grid_n
    for i in range(grid_n):
        for j in range(grid_n):
            px = (i + 0.5) / grid_n * viewport_w
            py = (j + 0.5) / grid_n * viewport_h
            for cx, cy, radius in circles:
                if (px - cx) ** 2 + (py - cy) ** 2 <= radius ** 2:
                    covered += 1
                    break
    return covered / total


def _bubble_layer_css():
    return """
    <style>
    .bubble-layer { position: fixed; inset: 0; z-index: 999999; pointer-events: none; overflow: hidden; }
    .bubble-layer span { position: absolute; border-radius: 50%; }
    /* 큰 기포 — 속이 비치지 않는 불투명한 진주/거품 느낌. 좌상단 밝은
       하이라이트 + 반대편 그늘로 입체감만 살리고, 바탕 자체는 어디서도
       알파가 낮아지지 않게(0.85 이하로 안 내려가게) 해 뒤 화면이 안 비친다 */
    .bubble-layer .b-lg {
        background:
            /* 1) 또렷하고 작은 정반사 하이라이트 — 기포마다 위치가 조금씩 다름(--hlx/--hly) */
            radial-gradient(circle at var(--hlx,28%) var(--hly,24%),
                rgba(255,255,255,.95) 0%, rgba(255,255,255,.5) 7%, rgba(255,255,255,0) 15%),
            /* 2) 은은한 무지개빛(비눗막 특유의 얇은 막 간섭색) */
            radial-gradient(circle at 62% 58%, rgba(255,214,230,.09) 0%, rgba(255,214,230,0) 55%),
            radial-gradient(circle at 38% 66%, rgba(202,255,222,.08) 0%, rgba(202,255,222,0) 50%),
            /* 3) 본체 — 중앙 밝음 -> 중간톤 -> 그늘진 띠 -> 가장자리 프레넬 반사로 다시 밝아짐 */
            radial-gradient(circle at 50% 50%,
                #eef3f6 0%, rgba(214,229,238,.95) 36%, rgba(182,208,226,.96) 60%,
                rgba(112,150,188,.97) 82%, rgba(205,226,240,.95) 93%, rgba(232,242,248,.88) 100%);
        box-shadow:
            inset -12px -12px 20px rgba(90,128,168,.4),
            inset 10px 10px 18px rgba(255,255,255,.4),
            0 4px 10px rgba(20,30,60,.2);
    }
    /* 부드럽게 번진 2차 유리질 반사광(블러 처리) — 사실적인 스피어 렌더링 기법 */
    .bubble-layer .b-lg::before {
        content: ''; position: absolute; inset: 6%; border-radius: 50%;
        background: radial-gradient(circle at 74% 78%, rgba(255,255,255,.5) 0%, rgba(255,255,255,0) 22%);
        filter: blur(2.5px);
    }
    .bubble-layer .b-lg::after {
        content: ''; position: absolute; top: 13%; left: 19%; width: 9%; height: 6%;
        border-radius: 50%; background: rgba(255,255,255,.85); filter: blur(.4px);
    }
    /* 작은 기포 — 성능을 위해 단순한 그라데이션만 (격자 이음새를 메꾸는 용도, 역시 불투명) */
    .bubble-layer .b-sm {
        background: radial-gradient(circle at 32% 28%,
            #eef3f6 0%, rgba(218,233,240,.86) 32%,
            rgba(196,220,235,.92) 70%, rgba(170,200,222,.96) 100%);
        box-shadow: inset -4px -4px 8px rgba(100,138,178,.35), inset 3px 3px 6px rgba(255,255,255,.45);
    }
    .bubble-layer .rise-in {
        animation-name: bubble-rise-in;
        animation-timing-function: cubic-bezier(.22,.7,.32,1);
        animation-fill-mode: both;
    }
    @keyframes bubble-rise-in {
        0%   { transform: translateY(130vh) scale(.35); opacity: 0; }
        18%  { opacity: var(--maxop,.85); }
        100% { transform: translateY(0) scale(1); opacity: var(--maxop,.85); }
    }
    .bubble-layer .rise-out {
        animation-name: bubble-rise-out;
        animation-timing-function: cubic-bezier(.4,0,.2,1);
        animation-fill-mode: both;
    }
    @keyframes bubble-rise-out {
        0%   { transform: translateY(0) scale(1); opacity: var(--maxop,.85); }
        100% { transform: translateY(-130vh) scale(1.15); opacity: 0; }
    }
    @media (prefers-reduced-motion: reduce) {
        .bubble-layer { display: none !important; }
    }
    </style>
    """


def _bubble_spans(specs, phase):
    motion = "rise-in" if phase == "cover" else "rise-out"
    spans = []
    for s in specs:
        size_cls = "b-lg" if s["kind"] == "lg" else "b-sm"
        unit = s.get("unit", "px")
        extra = ""
        if s["kind"] == "lg":
            extra = f'border-radius:{s["br"]}; --hlx:{s["hlx"]}%; --hly:{s["hly"]}%; '
        spans.append(
            f'<span class="{size_cls} {motion}" style="top:{s["top"]}%; left:{s["left"]}%; '
            f'width:{s["size"]}{unit}; height:{s["size"]}{unit}; --maxop:{s["op"]}; {extra}'
            f'animation-delay:{s["delay"]}s; animation-duration:{s["dur"]}s;"></span>'
        )
    return "".join(spans)


def bubble_cover_seconds(specs):
    """덮는 애니메이션이 완전히 끝나는 시점(초) — 이 시간만큼 서버를 sleep해서
    '화면이 기포로 완전히 덮인 뒤에' 다음 화면으로 넘어가도록 맞춘다."""
    return max(s["delay"] + s["dur"] for s in specs) + 0.15


def render_bubble_cover(specs):
    """1단계: 지금 화면 위로 기포가 떠올라 화면을 가득 채우고 그 자리에 멈춘다.
    (예전엔 이 단계를 없애고 걷히는 애니메이션만 남겨뒀었는데, 그 이유였던
    '이전 화면 요소가 안 지워지고 새 화면과 섞이는' 버그는 아래 메인 라우팅의
    st.empty() 슬롯으로 이미 고쳐졌다 — 그래서 원래대로 덮는 단계를 되살린다.)"""
    html_block(_bubble_layer_css() + '<div class="bubble-layer">' + _bubble_spans(specs, "cover") + "</div>")


def render_bubble_clear():
    """2단계: (다음 화면이 막 렌더된 시점) 같은 배치의 기포가 이미 화면을 덮은
    채로 시작해서 위로 빠져나가며 걷힌다 — 그래야 전환 순간 새 화면이
    비치치 않고, 기포가 걷힌 뒤에야 드러난다."""
    if not st.session_state.show_page_transition:
        return
    st.session_state.show_page_transition = False
    specs = st.session_state.bubble_specs
    st.session_state.bubble_specs = None
    if not specs:
        return
    html_block(_bubble_layer_css() + '<div class="bubble-layer">' + _bubble_spans(specs, "clear") + "</div>")


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
    # 티끌(tiny) — 아주 작은 조각구름 다수, 느리게(90~130s)
    (2, 55, 96, -5, 0.55, 2, "far"), (10, 45, 108, -35, 0.5, 1, "far"),
    (17, 60, 100, -70, 0.55, 2, "far"), (25, 50, 118, -18, 0.5, 1, "far"),
    (33, 65, 92, -50, 0.55, 2, "far"), (41, 45, 112, -88, 0.5, 1, "far"),
    (49, 55, 104, -28, 0.55, 2, "far"), (57, 50, 122, -63, 0.5, 1, "far"),
    (65, 60, 96, -8, 0.55, 2, "far"), (72, 45, 110, -95, 0.5, 1, "far"),
    (80, 55, 100, -40, 0.55, 2, "far"), (87, 50, 114, -73, 0.5, 1, "far"),
    (93, 60, 106, -20, 0.55, 2, "far"),
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

    /* Streamlit 기본 헤더/툴바/메뉴는 투명해도 클릭을 그대로 가로챈다.
       사이드바를 없앤 뒤로가기·우상단 아이콘이 그 영역과 겹쳐 먹통이 되는
       원인이었음 — 완전히 숨겨서 아래 우리 버튼들이 클릭을 받게 한다. */
    header[data-testid="stHeader"],
    div[data-testid="stToolbar"],
    #MainMenu {
        visibility: hidden !important;
        pointer-events: none !important;
    }

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

    /* 캐릭터 만들기 · 기본 탭 — 이름/성별/연령대/피부타입 등 라벨·버튼 글씨 확대 */
    .st-key-char_basic_tab .stMarkdown p {
        font-size: 1.25rem !important;
        font-weight: 800 !important;
    }
    .st-key-char_basic_tab label p {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
    }
    .st-key-char_basic_tab .stTextInput input {
        font-size: 1.15rem !important;
    }
    .st-key-char_basic_tab .stButton button {
        font-size: 1.1rem !important;
    }

    /* 캐릭터 만들기 페이지 — 전체를 살짝 위로 올리고, 상단 탭(기본/옷장/취향) 글씨 확대 */
    .st-key-character_page {
        margin-top: -2.2rem !important;
    }
    .st-key-character_page .stTabs [data-testid="stTab"],
    .st-key-character_page .stTabs [data-testid="stTab"] * {
        font-size: 1.6rem !important;
        font-weight: 800 !important;
        line-height: 1.4 !important;
    }
    .st-key-character_page .stTabs [data-testid="stTab"] {
        padding: 0.8rem 1.2rem !important;
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

# 8비트 픽셀 하트 (start-game 다이얼로그의 타이틀 아이콘 · 하트 버튼에 사용)
_HEART_OUTER = [
    "011000110",
    "111101111",
    "111111111",
    "111111111",
    "011111110",
    "001111100",
    "000111000",
    "000010000",
]
_HEART_INNER = [
    "0110110",
    "1111111",
    "1111111",
    "0111110",
    "0011100",
    "0001000",
]


def _pixel_heart_uri(cell, outer_color, inner_color=None):
    """OUTER 격자를 outer_color로, 그 안쪽에 1칸 오프셋으로 INNER 격자를 inner_color로 겹쳐
    그려 8비트풍 하트 스프라이트(윤곽선 있는 하트)를 만들고 data URI로 반환한다."""
    rects = [
        f'<rect x="{c*cell}" y="{r*cell}" width="{cell}" height="{cell}" fill="{outer_color}"/>'
        for r, row in enumerate(_HEART_OUTER) for c, v in enumerate(row) if v == "1"
    ]
    if inner_color:
        rects += [
            f'<rect x="{(c+1)*cell}" y="{(r+1)*cell}" width="{cell}" height="{cell}" fill="{inner_color}"/>'
            for r, row in enumerate(_HEART_INNER) for c, v in enumerate(row) if v == "1"
        ]
    w, h = len(_HEART_OUTER[0]) * cell, len(_HEART_OUTER) * cell
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">{"".join(rects)}</svg>'
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


HEART_ICON_PURPLE = _pixel_heart_uri(3, "#a98be0")
HEART_ICON_PINK = _pixel_heart_uri(3, "#ff8fc0")
HEART_ICON_LIGHT = _pixel_heart_uri(3, "#ffd2e6")
HEART_BUTTON_URI = _pixel_heart_uri(6, "#b23a6e", "#fff0f6")


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
            height: min(84vh, 800px);
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
                inset 0 0 36px 8px rgba(170,220,255,.5),
                0 0 26px 4px rgba(255,255,255,.35),
                0 0 74px 18px rgba(120,190,255,.68),
                0 46px 80px rgba(20,40,90,.58);
            animation: earth-float 7s ease-in-out infinite;
        }}
        /* 회전하는 지구 텍스처 (equirectangular 가로 스크롤 = 자전) — 밝기·채도 보정 */
        .earth .tex {{
            position: absolute; inset: 0; border-radius: 50%;
            background-image: url('{earth}');
            background-size: 960px 480px;
            background-repeat: repeat-x;
            background-position: 0 center;
            filter: brightness(1.24) contrast(1.1) saturate(1.2);
            animation: spin-earth 34s linear infinite;
        }}
        @keyframes spin-earth {{
            from {{ background-position: 0 center; }}
            to   {{ background-position: -960px center; }}
        }}
        /* 구 입체감 레이어1: 라이팅(좌상단 주광원 + 우하단 코어 섀도우 + 가장자리 앰비언트 오클루전) */
        .earth .shade {{
            position: absolute; inset: 0; border-radius: 50%; z-index: 2;
            pointer-events: none;
            background:
                radial-gradient(circle at 28% 24%,
                    rgba(255,255,255,.7) 0%, rgba(255,255,255,.22) 11%, rgba(255,255,255,0) 27%),
                radial-gradient(circle at 70% 76%,
                    rgba(0,0,0,0) 24%, rgba(2,6,24,.4) 58%, rgba(1,3,16,.94) 100%),
                radial-gradient(circle at 50% 50%,
                    rgba(3,8,28,0) 46%, rgba(3,8,28,.32) 80%, rgba(1,3,14,.78) 100%);
        }}
        /* 구 입체감 레이어2: 프레넬 림 라이트 + 하이라이트 + 반대편 보조광(파란 바운스) */
        .earth .gloss {{
            position: absolute; inset: 0; border-radius: 50%; z-index: 3;
            pointer-events: none;
            box-shadow:
                inset 9px 9px 28px rgba(210,238,255,.65),
                inset -6px -8px 24px rgba(110,175,255,.4),
                inset 0 0 44px rgba(255,255,255,.14);
            background:
                radial-gradient(ellipse 34% 20% at 31% 21%,
                    rgba(255,255,255,.9) 0%, rgba(255,255,255,.35) 38%, rgba(255,255,255,0) 68%),
                radial-gradient(ellipse 60% 44% at 76% 80%,
                    rgba(50,110,220,.4) 0%, rgba(50,110,220,0) 70%),
                radial-gradient(circle at 50% 50%,
                    rgba(140,205,255,0) 82%, rgba(140,205,255,.5) 96%, rgba(160,215,255,.75) 100%);
            mix-blend-mode: screen;
        }}
        /* 구 입체감 레이어3: 미세한 대기 스월(회전과 함께 은은하게 흐르는 하이라이트) */
        .earth .sheen {{
            position: absolute; inset: -6%; border-radius: 50%; z-index: 4;
            pointer-events: none; opacity: .5; mix-blend-mode: soft-light;
            background: conic-gradient(from 0deg,
                rgba(255,255,255,0) 0deg, rgba(255,255,255,.5) 18deg, rgba(255,255,255,0) 55deg,
                rgba(255,255,255,0) 200deg, rgba(255,255,255,.3) 230deg, rgba(255,255,255,0) 265deg,
                rgba(255,255,255,0) 360deg);
            animation: sheen-spin 34s linear infinite;
        }}
        @keyframes sheen-spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
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
        /* div 태그 + !important: Streamlit 기본 <p> 타이포그래피 규칙이 명시도가 더 높아
           일반 클래스 font-size를 눌러 이겨버리는 문제를 막기 위함 (실측 확인된 버그) */
        div.hero-sub {{
            position: absolute !important; left: 50% !important; top: 76% !important;
            transform: translateX(-50%) !important;
            width: auto !important; max-width: 94% !important;
            white-space: nowrap !important;
            text-align: center !important;
            font-family: 'Gamja Flower', 'Jua', cursive !important;
            font-size: clamp(1.1rem,2.3vw,1.8rem) !important;
            font-weight: 700 !important; line-height: 1.35 !important;
            color: #6a3d8a !important; z-index: 6 !important;
            padding: 0 !important;
            background: none !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            text-shadow: 0 2px 0 rgba(255,255,255,.85), 0 1px 10px rgba(255,255,255,.6) !important;
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

        @media (prefers-reduced-motion: reduce) {{
            .earth, .earth .tex, .earth-shadow, .atmos, .plane-main, .plane-bg, .trail {{ animation: none !important; }}
        }}
        </style>

        <div class="stage">
            <div class="atmos"></div>
            <div class="earth-shadow"></div>
            <div class="earth">
                <div class="tex"></div>
                <div class="shade"></div>
                <div class="gloss"></div>
                <div class="sheen"></div>
            </div>
            <div class="plane-bg">{PLANE_SIDE_SVG}</div>
            <div class="plane-main">
                {PLANE_SIDE_SVG}
                <span class="trail"></span>
            </div>
            <h1 class="hero-title">{title}</h1>
            <div class="hero-sub">기후 · 수질 · 자외선을 내 피부에 맞춰 알려주는 여행 뷰티 케어 ✈️</div>
        </div>
        """
    )

    # start-game 다이얼로그 + 하트 버튼을 하나의 진짜 컨테이너 안에 함께 그린다.
    # (버튼과 장식 HTML을 각각 따로 그리면 버튼이 자기 크기로 좁게 감싸져
    #  다이얼로그와 이어붙는 넓은 띠 모양이 깨진다 — 반드시 같은 DOM 박스 안에 있어야 함)
    with st.container(key="start_dialog"):
        html_block(
            f"""
            <style>
            .st-key-start_dialog {{
                max-width: 360px !important; margin: 0 auto 1rem !important;
                position: relative !important; top: -90px !important;
                font-family: 'Press Start 2P', 'Jua', cursive;
                border: 4px solid #b23a6e !important; border-radius: 10px !important;
                overflow: hidden !important; background: #ffe6f0 !important;
                box-shadow: 0 10px 26px rgba(120,40,90,.3);
                animation: dialog-in .8s cubic-bezier(.2,1.6,.35,1) 2.9s both;
            }}
            .st-key-start_dialog .titlebar {{
                display: flex; align-items: center; justify-content: space-between;
                padding: 10px 12px; margin: -1px -1px 0; background: linear-gradient(90deg,#ff9dc4,#ff7fb8);
            }}
            .st-key-start_dialog .titlebar .hearts {{ display: flex; gap: 7px; }}
            .st-key-start_dialog .titlebar .hearts img {{ width: 18px; height: auto; image-rendering: pixelated; }}
            .st-key-start_dialog .titlebar .checker {{
                width: 18px; height: 18px; background-color: #fff;
                background-image:
                    linear-gradient(45deg,#b23a6e 25%,transparent 25%,transparent 75%,#b23a6e 75%),
                    linear-gradient(45deg,#b23a6e 25%,transparent 25%,transparent 75%,#b23a6e 75%);
                background-size: 9px 9px; background-position: 0 0, 4.5px 4.5px;
            }}
            .st-key-start_dialog .body {{
                padding: 26px 12px 10px; text-align: center;
                color: #9c2f5c; font-size: clamp(1.05rem,2.6vw,1.6rem);
                text-shadow: 2px 2px 0 #fff; letter-spacing: 2px;
            }}
            @keyframes dialog-in {{
                0%   {{ opacity: 0; transform: translateY(34px) scale(.85); }}
                100% {{ opacity: 1; transform: translateY(0)    scale(1); }}
            }}
            /* 버튼을 감싸는 실제 래퍼가 어느 계층인지 버전마다 다를 수 있어 여러 후보
               선택자에 전부 flex-center를 건다. :has(button)으로 버튼을 담은 박스만
               한정해서, 위쪽 title/body 마크다운 박스의 세로 배치는 건드리지 않는다 */
            .st-key-start_dialog > div:has(button),
            .st-key-start_dialog [data-testid="element-container"]:has(button),
            .st-key-start_dialog [data-testid="stButton"],
            .st-key-start_dialog .stButton {{
                width: 100% !important;
                display: flex !important;
                justify-content: center !important;
                align-items: center !important;
            }}
            .st-key-start_dialog .stButton {{
                padding: 4px 0 20px !important; margin: 0 !important;
            }}
            .st-key-start_dialog .stButton button {{
                width: 150px !important; height: 50px !important;
                min-width: 150px !important; max-width: 150px !important;
                min-height: 50px !important; max-height: 50px !important;
                padding: 0 !important; margin: 0 auto !important;
                box-sizing: border-box !important; overflow: hidden !important;
                background: #fff0f6 !important; border: 3px solid #b23a6e !important;
                border-radius: 8px !important; box-shadow: inset 0 0 0 2px #ffd0e6;
                position: relative !important; display: block !important;
                transition: transform .1s ease;
            }}
            /* 라벨 텍스트는 스크린리더용으로만 남기고 시각적으로는 완전히 접어버려 —
               안 그러면 숨긴 긴 라벨이 줄바꿈되며 버튼 상자가 찌그러져 보인다 */
            .st-key-start_dialog .stButton button * {{
                font-size: 0 !important; line-height: 0 !important;
                color: transparent !important; margin: 0 !important; padding: 0 !important;
            }}
            .st-key-start_dialog .stButton button:hover {{ transform: translateY(-2px); }}
            .st-key-start_dialog .stButton button:active {{ transform: translateY(1px); }}
            .st-key-start_dialog .stButton button::before {{
                content: ''; position: absolute; left: 50%; top: 50%;
                width: 40px; height: 34px; transform: translate(-50%,-50%);
                background-image: url('{HEART_BUTTON_URI}');
                background-size: contain; background-repeat: no-repeat;
                image-rendering: pixelated;
            }}
            @media (prefers-reduced-motion: reduce) {{
                .st-key-start_dialog {{ animation: none !important; }}
            }}
            </style>
            <div class="titlebar">
                <span class="hearts">
                    <img src="{HEART_ICON_PURPLE}" alt=""/>
                    <img src="{HEART_ICON_PINK}" alt=""/>
                    <img src="{HEART_ICON_LIGHT}" alt=""/>
                </span>
                <span class="checker"></span>
            </div>
            <div class="body">start game?</div>
            """
        )
        start_clicked = st.button("하트를 눌러 여행 시작", key="start_heart_btn")

    if start_clicked:
        specs = _generate_bubble_specs()
        st.session_state.bubble_specs = specs
        render_bubble_cover(specs)
        time.sleep(bubble_cover_seconds(specs))
        st.session_state.show_page_transition = True
        goto("character")
        st.rerun()


# ----------------------------------------------------------------------
# 캐릭터 미리보기 인형 (3D 토이 느낌의 SVG) — 선택한 옵션을 실시간으로 반영
# ----------------------------------------------------------------------
def _shade(hex_color, factor):
    """hex 색에 factor를 곱해 그라데이션 색을 만든다 (1보다 작으면 어둡게,
    크면 밝게 — 구체감을 주는 하이라이트/그림자 색 둘 다 이 함수로 만든다)."""
    hex_color = (hex_color or "#cccccc").lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, min(255, int(c * factor))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _hair_back(hair_type):
    if hair_type == "웨이브":
        return ('<path d="M94,78 Q94,26 150,24 Q206,26 206,78 L206,230 '
                'Q214,240 204,248 Q212,256 200,258 L200,96 Q200,64 150,62 '
                'Q100,64 100,96 L100,258 Q88,256 96,248 Q86,240 94,230 Z" fill="url(#hairGrad)"/>')
    if hair_type == "컬리":
        pts = [(92, 84, 30), (112, 58, 28), (150, 48, 30), (188, 58, 28), (208, 84, 30),
               (96, 124, 26), (204, 124, 26), (106, 160, 24), (194, 160, 24), (150, 168, 24)]
        return "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#hairGrad)"/>' for x, y, r in pts)
    if hair_type == "숏컷":
        return ('<path d="M96,80 Q96,28 150,26 Q204,28 204,80 L204,150 '
                'Q204,162 192,158 L192,98 Q192,66 150,64 Q108,66 108,98 '
                'L108,158 Q96,162 96,150 Z" fill="url(#hairGrad)"/>')
    # 스트레이트 (기본값)
    return ('<path d="M94,78 Q94,26 150,24 Q206,26 206,78 L206,250 '
            'Q206,262 194,262 L194,96 Q194,64 150,62 Q106,64 106,96 '
            'L106,262 Q94,262 94,250 Z" fill="url(#hairGrad)"/>')


def _hair_front(hair_type):
    if hair_type == "컬리":
        pts = [(112, 74, 20), (150, 66, 22), (188, 74, 20)]
        return "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#hairGrad)"/>' for x, y, r in pts)
    return '<path d="M98,92 Q150,52 202,92 L202,76 Q150,40 98,76 Z" fill="url(#hairGrad)"/>'


def character_doll_svg(draft):
    skin = draft.get("skin_tone") or SKIN_TONES[0]["hex"]
    hair_type = draft.get("hair_type") or HAIR_TYPES[0]
    style = draft.get("style") or CLOTHING[0]
    style_conf = CLOTHING_STYLES[style]
    outfit = draft.get("outfit") or {}
    acc = draft.get("accessories") or {}

    top_hex = _catalog_hex("top", outfit.get("top")) or style_conf["top"]
    bottom_hex = _catalog_hex("bottom", outfit.get("bottom")) or style_conf["bottom"]
    shoe_hex = _catalog_hex("shoes", outfit.get("shoes")) or style_conf["shoe"]
    hat_hex = _catalog_hex("hat", outfit.get("hat"))
    socks_hex = _catalog_hex("socks", outfit.get("socks"))
    necklace_hex = _catalog_hex("necklace", acc.get("necklace"))
    sunglasses_hex = _catalog_hex("sunglasses", acc.get("sunglasses"))
    gloves_hex = _catalog_hex("gloves", acc.get("gloves"))

    skin_dark = _shade(skin, 0.82)
    skin_light = _shade(skin, 1.18)
    top_dark = _shade(top_hex, 0.78)
    top_light = _shade(top_hex, 1.2)
    bottom_dark = _shade(bottom_hex, 0.78)
    hair_dark = _shade(HAIR_COLOR, 0.7)
    glove_dark = _shade(gloves_hex or skin, 0.8)
    hand_fill = "url(#gloveGrad)" if gloves_hex else "url(#skinGrad)"

    use_skirt = style_conf["skirt"] and not outfit.get("bottom")
    if use_skirt:
        legs_svg = (
            f'<path d="M105,278 L195,278 L216,358 L84,358 Z" fill="url(#bottomGrad)" '
            f'stroke="{bottom_dark}" stroke-width="2" stroke-opacity=".5"/>'
            f'<rect x="118" y="344" width="20" height="46" rx="9" fill="url(#skinGrad)"/>'
            f'<rect x="162" y="344" width="20" height="46" rx="9" fill="url(#skinGrad)"/>'
        )
    else:
        legs_svg = (
            f'<rect x="112" y="278" width="32" height="102" rx="14" fill="url(#bottomGrad)" '
            f'stroke="{bottom_dark}" stroke-width="2" stroke-opacity=".5"/>'
            f'<rect x="156" y="278" width="32" height="102" rx="14" fill="url(#bottomGrad)" '
            f'stroke="{bottom_dark}" stroke-width="2" stroke-opacity=".5"/>'
        )

    socks_svg = ""
    if socks_hex and not use_skirt:
        socks_svg = (
            f'<rect x="112" y="352" width="32" height="16" fill="{socks_hex}"/>'
            f'<rect x="156" y="352" width="32" height="16" fill="{socks_hex}"/>'
        )

    hat_svg = ""
    if hat_hex:
        hat_dark = _shade(hat_hex, 0.85)
        hat_svg = (
            f'<path d="M92,72 Q150,20 208,72 L208,88 Q150,62 92,88 Z" fill="{hat_hex}" '
            f'stroke="{hat_dark}" stroke-width="2"/>'
            f'<ellipse cx="150" cy="88" rx="60" ry="9" fill="{hat_dark}"/>'
        )

    necklace_svg = ""
    if necklace_hex:
        necklace_svg = (
            f'<path d="M126,168 Q150,190 174,168" stroke="{necklace_hex}" stroke-width="5" '
            f'fill="none" stroke-linecap="round"/>'
            f'<circle cx="150" cy="188" r="6" fill="{necklace_hex}"/>'
        )

    sunglasses_svg = ""
    if sunglasses_hex:
        sunglasses_svg = (
            f'<rect x="118" y="103" width="28" height="17" rx="8" fill="{sunglasses_hex}"/>'
            f'<rect x="154" y="103" width="28" height="17" rx="8" fill="{sunglasses_hex}"/>'
            f'<rect x="146" y="108" width="8" height="4" fill="{sunglasses_hex}"/>'
        )

    glove_defs = (
        f'<linearGradient id="gloveGrad" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{gloves_hex}"/><stop offset="1" stop-color="{glove_dark}"/>'
        f'</linearGradient>' if gloves_hex else ""
    )

    return f'''
    <svg class="doll-svg" viewBox="0 0 300 420" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="skinGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="{skin}"/><stop offset="1" stop-color="{skin_dark}"/>
            </linearGradient>
            <radialGradient id="skinHeadGrad" cx="36%" cy="28%" r="78%">
                <stop offset="0" stop-color="{skin_light}"/>
                <stop offset="55%" stop-color="{skin}"/>
                <stop offset="100%" stop-color="{skin_dark}"/>
            </radialGradient>
            <linearGradient id="topGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="{top_hex}"/><stop offset="1" stop-color="{top_dark}"/>
            </linearGradient>
            <radialGradient id="topRadGrad" cx="34%" cy="16%" r="88%">
                <stop offset="0" stop-color="{top_light}"/>
                <stop offset="60%" stop-color="{top_hex}"/>
                <stop offset="100%" stop-color="{top_dark}"/>
            </radialGradient>
            <linearGradient id="bottomGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="{bottom_hex}"/><stop offset="1" stop-color="{bottom_dark}"/>
            </linearGradient>
            <linearGradient id="hairGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="{HAIR_COLOR}"/><stop offset="1" stop-color="{hair_dark}"/>
            </linearGradient>
            {glove_defs}
        </defs>
        <ellipse cx="150" cy="402" rx="88" ry="17" fill="rgba(20,20,40,.32)"/>
        {legs_svg}
        {socks_svg}
        <ellipse cx="128" cy="378" rx="24" ry="13" fill="{shoe_hex}" stroke="{style_conf['sole']}" stroke-width="4"/>
        <ellipse cx="172" cy="378" rx="24" ry="13" fill="{shoe_hex}" stroke="{style_conf['sole']}" stroke-width="4"/>
        <rect x="98" y="172" width="104" height="112" rx="36" fill="url(#topRadGrad)" stroke="{top_dark}" stroke-width="2" stroke-opacity=".5"/>
        <ellipse cx="126" cy="196" rx="20" ry="30" fill="#ffffff" opacity=".2" transform="rotate(-16 126 196)"/>
        <rect x="8" y="182" width="92" height="26" rx="13" fill="url(#topGrad)" transform="rotate(-12 100 195)"/>
        <rect x="200" y="182" width="92" height="26" rx="13" fill="url(#topGrad)" transform="rotate(12 200 195)"/>
        <circle cx="10" cy="214" r="16" fill="{hand_fill}"/>
        <circle cx="290" cy="214" r="16" fill="{hand_fill}"/>
        {_hair_back(hair_type)}
        <circle cx="150" cy="115" r="54" fill="url(#skinHeadGrad)" stroke="{skin_dark}" stroke-width="2" stroke-opacity=".4"/>
        <ellipse cx="130" cy="98" rx="15" ry="10" fill="#ffffff" opacity=".25"/>
        {_hair_front(hair_type)}
        {hat_svg}
        {necklace_svg}
        <circle cx="132" cy="112" r="4.5" fill="#3a2a20"/>
        <circle cx="168" cy="112" r="4.5" fill="#3a2a20"/>
        {sunglasses_svg}
        <circle cx="112" cy="126" r="9" fill="#ff9ab3" opacity=".35"/>
        <circle cx="188" cy="126" r="9" fill="#ff9ab3" opacity=".35"/>
        <path d="M136,130 Q150,140 164,130" stroke="#3a2a20" stroke-width="3" fill="none" stroke-linecap="round"/>
    </svg>
    '''


def _doll_3d_params(draft):
    """캐릭터 만들기 화면의 실제 3D(Three.js) 미리보기에 넘길 색상/옵션 값.
    character_doll_svg와 같은 카탈로그 조회 로직을 쓰지만, 음영은 SVG처럼
    직접 계산하지 않고(3D 조명이 실시간으로 계산해줌) 원색만 넘긴다."""
    skin = draft.get("skin_tone") or SKIN_TONES[0]["hex"]
    hair_type = draft.get("hair_type") or HAIR_TYPES[0]
    style = draft.get("style") or CLOTHING[0]
    style_conf = CLOTHING_STYLES[style]
    outfit = draft.get("outfit") or {}
    acc = draft.get("accessories") or {}
    return {
        "skin": skin,
        "hair": HAIR_COLOR,
        "hairType": hair_type,
        "top": _catalog_hex("top", outfit.get("top")) or style_conf["top"],
        "bottom": _catalog_hex("bottom", outfit.get("bottom")) or style_conf["bottom"],
        "shoe": _catalog_hex("shoes", outfit.get("shoes")) or style_conf["shoe"],
        "skirt": bool(style_conf["skirt"] and not outfit.get("bottom")),
        "hat": _catalog_hex("hat", outfit.get("hat")),
        "socks": _catalog_hex("socks", outfit.get("socks")),
        "necklace": _catalog_hex("necklace", acc.get("necklace")),
        "sunglasses": _catalog_hex("sunglasses", acc.get("sunglasses")),
        "gloves": _catalog_hex("gloves", acc.get("gloves")),
    }


_DOLL_3D_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body { margin: 0; padding: 0; overflow: hidden; background: transparent; }
  #stage { width: 100%; height: 100%; }
</style>
</head>
<body>
<div id="stage"></div>
<script src="https://unpkg.com/three@0.128.0/build/three.min.js"></script>
<script src="https://unpkg.com/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const CHAR = __CHAR_JSON__;
const stage = document.getElementById('stage');
const width = window.innerWidth;
const height = window.innerHeight;

// --- 참고로 받은 "3D 스틱맨" 클립아트처럼: 몸통 하나로 매끈하게, 어깨/팔꿈치/
//     무릎에는 둥근 관절 볼을 두는 단순한 구조로 다시 리깅한다.
//     발밑(y=0)부터 위로 부위 길이를 누적해서 위치를 계산 — 좌표 하드코딩 없이
//     쌓아 올려야 부위 사이가 뜨거나 겹치지 않는다.
const FOOT_R = 0.19;
const SHIN_LEN = 0.55, THIGH_LEN = 0.58, LIMB_R = 0.135;
const TORSO_LEN = 0.95, TORSO_R = 0.40;
const NECK_LEN = 0.08, NECK_R = 0.16;
const HEAD_R = 0.40;
const LEG_X = 0.19;
const JOINT_R = 0.145;

let _y = FOOT_R * 0.5;
const shinY = _y + SHIN_LEN / 2; _y += SHIN_LEN;
const kneeY = _y;
const thighY = _y + THIGH_LEN / 2; _y += THIGH_LEN;
const torsoY = _y + TORSO_LEN / 2; _y += TORSO_LEN;
const neckY = _y + NECK_LEN / 2; _y += NECK_LEN;
const headY = _y + HEAD_R;
const shoulderY = torsoY + TORSO_LEN * 0.42;
const totalTop = headY + HEAD_R;
const midY = totalTop * 0.5;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(28, width / height, 0.1, 100);
camera.position.set(0, midY + totalTop * 0.06, totalTop * 2.25);
camera.lookAt(0, midY, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(width, height);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
stage.appendChild(renderer.domElement);

scene.add(new THREE.AmbientLight(0xbfd4ff, 0.6));

const key = new THREE.DirectionalLight(0xfff3e0, 1.3);
key.position.set(-3.2, 5, 4.5);
key.castShadow = true;
key.shadow.mapSize.set(1024, 1024);
key.shadow.radius = 6;
scene.add(key);

const rim = new THREE.DirectionalLight(0x9fc4ff, 0.9);
rim.position.set(3.5, 3.2, -4);
scene.add(rim);

const fill = new THREE.DirectionalLight(0xffffff, 0.3);
fill.position.set(2, 1, 4);
scene.add(fill);

function makeMat(hex, opts) {
    opts = opts || {};
    return new THREE.MeshPhysicalMaterial(Object.assign({
        color: hex, roughness: 0.45, clearcoat: 0.4, clearcoatRoughness: 0.2, metalness: 0.02,
    }, opts));
}

function makeCapsule(radius, length, mat) {
    const g = new THREE.Group();
    const cyl = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, length, 20, 1, true), mat);
    cyl.castShadow = true;
    g.add(cyl);
    const capGeo = new THREE.SphereGeometry(radius, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2);
    const top = new THREE.Mesh(capGeo, mat);
    top.position.y = length / 2; top.castShadow = true;
    g.add(top);
    const bot = new THREE.Mesh(capGeo, mat);
    bot.position.y = -length / 2; bot.rotation.x = Math.PI; bot.castShadow = true;
    g.add(bot);
    return g;
}

function headSurfacePoint(dx, dy, inset) {
    inset = inset === undefined ? 0.92 : inset;
    const r2 = HEAD_R * HEAD_R - dx * dx - dy * dy;
    const dz = Math.sqrt(Math.max(0.02, r2)) * inset;
    return new THREE.Vector3(dx, headY + dy, dz);
}

const doll = new THREE.Group();
const bottomMat = makeMat(CHAR.bottom, { roughness: 0.7, clearcoat: 0.12 });
const shoeMat = makeMat(CHAR.shoe, { roughness: 0.3, clearcoat: 0.55 });
const topMat = makeMat(CHAR.top, { roughness: 0.5, clearcoat: 0.35 });
const skinMat = makeMat(CHAR.skin, { roughness: 0.4, clearcoat: 0.5 });

// --- 다리: 허벅지 - 무릎(둥근 관절 볼) - 정강이 - 발, 스커트면 허벅지 자리를
//     치마로 바꾸고 다리는 맨살로.
[-LEG_X, LEG_X].forEach((x) => {
    if (CHAR.skirt) {
        const bareLeg = makeCapsule(LIMB_R * 0.95, SHIN_LEN + THIGH_LEN * 0.55, skinMat);
        bareLeg.position.set(x, shinY, 0);
        doll.add(bareLeg);
    } else {
        const thigh = makeCapsule(LIMB_R, THIGH_LEN, bottomMat);
        thigh.position.set(x, thighY, 0);
        doll.add(thigh);
        const knee = new THREE.Mesh(new THREE.SphereGeometry(JOINT_R, 16, 12), bottomMat);
        knee.position.set(x, kneeY, 0);
        knee.castShadow = true;
        doll.add(knee);
        const shin = makeCapsule(LIMB_R * 0.9, SHIN_LEN, bottomMat);
        shin.position.set(x, shinY, 0);
        doll.add(shin);
    }
    if (CHAR.socks && !CHAR.skirt) {
        const sock = new THREE.Mesh(
            new THREE.CylinderGeometry(LIMB_R * 1.1, LIMB_R, FOOT_R * 0.8, 16),
            makeMat(CHAR.socks, { roughness: 0.75, clearcoat: 0.1 })
        );
        sock.position.set(x, FOOT_R * 0.85, 0);
        doll.add(sock);
    }
    const foot = new THREE.Mesh(new THREE.SphereGeometry(FOOT_R, 18, 14), shoeMat);
    foot.scale.set(1, 0.55, 1.55);
    foot.position.set(x, FOOT_R * 0.32, 0.08);
    foot.castShadow = true;
    doll.add(foot);
});

if (CHAR.skirt) {
    const skirtTopY = thighY + THIGH_LEN / 2;
    const skirtBottomY = thighY - THIGH_LEN * 0.15;
    const skirt = new THREE.Mesh(
        new THREE.CylinderGeometry(TORSO_R * 0.7, TORSO_R * 1.35, skirtTopY - skirtBottomY, 20, 1, true),
        bottomMat
    );
    skirt.position.y = (skirtTopY + skirtBottomY) / 2;
    skirt.castShadow = true;
    doll.add(skirt);
}

// --- 몸통: 한 덩어리 캡슐 하나로 매끈하게 (예전엔 가슴/허리/골반을 따로
//     쌓아서 이어붙인 자국이 두드러져 보였다).
const torso = makeCapsule(TORSO_R, TORSO_LEN, topMat);
torso.position.y = torsoY;
torso.scale.set(1.02, 1, 0.85);
doll.add(torso);

const neck = makeCapsule(NECK_R, NECK_LEN, skinMat);
neck.position.y = neckY;
doll.add(neck);

// --- 팔: 어깨(관절 볼) - 위팔 - 팔꿈치(관절 볼) - 아래팔 - 손, 자연스럽게
//     아래로 늘어뜬 자세 (T자 포즈 아님).
function buildArm(sign) {
    const pivot = new THREE.Group();
    pivot.position.set(sign * TORSO_R * 0.9, shoulderY, 0);

    const shoulderBall = new THREE.Mesh(new THREE.SphereGeometry(JOINT_R, 16, 12), topMat);
    shoulderBall.castShadow = true;
    pivot.add(shoulderBall);

    const upperLen = 0.42, foreLen = 0.4, r = LIMB_R * 0.85;
    const upper = makeCapsule(r, upperLen, topMat);
    upper.position.y = -upperLen / 2;
    pivot.add(upper);

    const forearmPivot = new THREE.Group();
    forearmPivot.position.y = -upperLen;
    pivot.add(forearmPivot);

    const elbowBall = new THREE.Mesh(new THREE.SphereGeometry(JOINT_R * 0.82, 16, 12), topMat);
    elbowBall.castShadow = true;
    forearmPivot.add(elbowBall);

    const forearm = makeCapsule(r * 0.9, foreLen, topMat);
    forearm.position.y = -foreLen / 2;
    forearmPivot.add(forearm);

    const handMat = makeMat(CHAR.gloves || CHAR.skin, {
        roughness: CHAR.gloves ? 0.65 : 0.4,
        clearcoat: CHAR.gloves ? 0.15 : 0.45,
    });
    const hand = new THREE.Mesh(new THREE.SphereGeometry(r * 1.3, 14, 10), handMat);
    hand.scale.set(1, 0.85, 0.7);
    hand.position.y = -foreLen - r * 0.4;
    hand.castShadow = true;
    forearmPivot.add(hand);

    pivot.rotation.z = sign * 0.26;
    forearmPivot.rotation.z = sign * -0.12;
    return pivot;
}
[-1, 1].forEach((sign) => doll.add(buildArm(sign)));

if (CHAR.necklace) {
    const neckMat = makeMat(CHAR.necklace, { roughness: 0.25, clearcoat: 0.7, metalness: 0.4 });
    const ring = new THREE.Mesh(new THREE.TorusGeometry(NECK_R * 1.25, 0.022, 10, 28, Math.PI * 1.3), neckMat);
    ring.position.set(0, torsoY + TORSO_LEN / 2 + 0.01, TORSO_R * 0.5);
    ring.rotation.x = Math.PI * 0.46;
    doll.add(ring);
}

// --- 머리: 매끈한 구 + 아주 단순한 표정(눈 두 개 + 웃는 입)만.
//     눈썹/콧방울/볼터치처럼 잘게 쪼개진 부품을 늘어놓으면 오히려 지저분해
//     보인다는 피드백을 받아서 최소한으로 줄였다.
const head = new THREE.Mesh(new THREE.SphereGeometry(HEAD_R, 32, 24), skinMat);
head.position.y = headY;
head.scale.set(0.98, 1.04, 0.96);
head.castShadow = true;
doll.add(head);

const eyeMat = makeMat(0x3a2a20, { roughness: 0.3, clearcoat: 0.6 });
[-1, 1].forEach((sign) => {
    const eye = new THREE.Mesh(new THREE.SphereGeometry(0.042, 12, 10), eyeMat);
    eye.scale.set(0.85, 1.15, 0.5);
    eye.position.copy(headSurfacePoint(sign * 0.15, 0.03, 0.95));
    doll.add(eye);
});

const mouthMat = makeMat(0xb35a5a, { roughness: 0.5, clearcoat: 0.3 });
const mouth = new THREE.Mesh(new THREE.TorusGeometry(0.065, 0.011, 8, 20, Math.PI * 0.5), mouthMat);
mouth.position.copy(headSurfacePoint(0, -0.14, 0.93));
mouth.rotation.z = Math.PI * 1.25;
doll.add(mouth);

// --- 머리카락: 정면에 얼굴이 드러나는 구멍을 남기고 옆/뒤만 덮는 돔 하나로
//     단순하게. 길이별로 따로 붙였던 다발/컬 조각이 카메라 각도에 따라
//     한쪽만 거대하게 튀어나와 보이는 문제가 있어서 없앴다.
const hairMat = makeMat(CHAR.hair, { roughness: 0.55, clearcoat: 0.15 });
const faceHalf = 0.75;
const domeThetaLen = (CHAR.hairType === '숏컷') ? Math.PI * 0.55
    : (CHAR.hairType === '컬리') ? Math.PI * 0.7
    : Math.PI * 0.92;
const hairDome = new THREE.Mesh(
    new THREE.SphereGeometry(
        HEAD_R * (CHAR.hairType === '컬리' ? 1.12 : 1.05), 28, 20,
        Math.PI / 2 + faceHalf, Math.PI * 2 - faceHalf * 2,
        0, domeThetaLen
    ),
    hairMat
);
hairDome.position.y = headY;
hairDome.castShadow = true;
doll.add(hairDome);

if (CHAR.hat) {
    const hatMat = makeMat(CHAR.hat, { roughness: 0.6, clearcoat: 0.2 });
    const brim = new THREE.Mesh(new THREE.CylinderGeometry(HEAD_R * 1.35, HEAD_R * 1.4, 0.05, 24), hatMat);
    brim.position.y = headY + HEAD_R * 0.6;
    doll.add(brim);
    const crown = new THREE.Mesh(
        new THREE.SphereGeometry(HEAD_R * 1.08, 20, 16, 0, Math.PI * 2, 0, Math.PI * 0.5),
        hatMat
    );
    crown.position.y = headY + HEAD_R * 0.6;
    doll.add(crown);
}

if (CHAR.sunglasses) {
    const glassMat = makeMat(CHAR.sunglasses, { roughness: 0.1, clearcoat: 0.9, metalness: 0.1 });
    [-1, 1].forEach((sign) => {
        const lens = new THREE.Mesh(new THREE.SphereGeometry(0.125, 16, 12), glassMat);
        lens.scale.set(1, 0.8, 0.35);
        lens.position.copy(headSurfacePoint(sign * 0.16, 0.03, 1.0));
        doll.add(lens);
    });
}

scene.add(doll);

const shadowPlane = new THREE.Mesh(
    new THREE.PlaneGeometry(3, 3),
    new THREE.ShadowMaterial({ opacity: 0.3 })
);
shadowPlane.rotation.x = -Math.PI / 2;
shadowPlane.position.y = -0.01;
shadowPlane.receiveShadow = true;
scene.add(shadowPlane);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enablePan = false;
controls.enableZoom = false;
controls.minPolarAngle = Math.PI / 2 - 0.3;
controls.maxPolarAngle = Math.PI / 2 + 0.08;
controls.autoRotate = true;
controls.autoRotateSpeed = 1.4;
controls.target.set(0, midY, 0);

const bobBaseY = doll.position.y;
function animate() {
    requestAnimationFrame(animate);
    doll.position.y = bobBaseY + Math.sin(Date.now() * 0.0012) * 0.035;
    controls.update();
    renderer.render(scene, camera);
}
animate();

window.addEventListener('resize', () => {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
});
</script>
</body>
</html>
"""


def render_doll_stage(draft):
    """캐릭터 만들기 화면의 큰 미리보기 — 카드/배경 없이 실제 Three.js(WebGL)로
    조명·그림자·재질까지 계산해서 렌더링한다 (SVG 평면 그림이 아니라 진짜 3D)."""
    char_json = json.dumps(_doll_3d_params(draft))
    components.html(
        _DOLL_3D_HTML.replace("__CHAR_JSON__", char_json),
        height=560,
        scrolling=False,
    )


# ----------------------------------------------------------------------
# 선택 칩 헬퍼 — 누르면 바로 반영, 다시 누르면 선택 해제(토글)
# ----------------------------------------------------------------------
def _toggle_single(key, value):
    draft = st.session_state.char_draft
    draft[key] = None if draft.get(key) == value else value


def _toggle_multi(key, value):
    draft = st.session_state.char_draft
    current = set(draft.get(key) or [])
    if value in current:
        current.discard(value)
    else:
        current.add(value)
    draft[key] = sorted(current)


def chip_row(label, options, key, multi=False, per_row=4):
    st.markdown(f"**{label}**" + ("  ·  복수 선택 가능" if multi else ""))
    draft = st.session_state.char_draft
    selected_set = set(draft.get(key) or []) if multi else {draft.get(key)}
    for start in range(0, len(options), per_row):
        row = options[start:start + per_row]
        cols = st.columns(len(row))
        for col, opt in zip(cols, row):
            with col:
                is_selected = opt in selected_set
                if st.button(opt, key=f"chip_{key}_{opt}",
                             type="primary" if is_selected else "secondary",
                             use_container_width=True):
                    if multi:
                        _toggle_multi(key, opt)
                    else:
                        _toggle_single(key, opt)
                    st.rerun()


def skin_tone_row():
    st.markdown("**피부 톤**")
    draft = st.session_state.char_draft
    cols = st.columns(len(SKIN_TONES))
    for col, tone in zip(cols, SKIN_TONES):
        with col:
            selected = draft.get("skin_tone") == tone["hex"]
            ring = "4px solid #ff6fb8" if selected else "3px solid rgba(0,0,0,.08)"
            html_block(
                f'<div style="width:100%;aspect-ratio:2.6/1;border-radius:12px;'
                f'background:{tone["hex"]};border:{ring};box-shadow:0 3px 8px rgba(0,0,0,.12);"></div>'
            )
            if st.button(tone["label"], key=f"chip_tone_{tone['id']}", use_container_width=True):
                _toggle_single("skin_tone", tone["hex"])
                st.rerun()


def closet_link_row(title, cat_key, bucket):
    """옷/액세서리 항목 버튼 — 누르면 30개 선택지가 있는 하위 페이지로 이동.
    이미 뭔가 착용 중이면 옆에 '벗기기' 버튼이 나타나 바로 선택을 취소할 수 있다."""
    draft = st.session_state.char_draft
    item_id = (draft.get(bucket) or {}).get(cat_key)
    catalog = ALL_CATALOGS[cat_key]
    current_label = _catalog_label(cat_key, item_id) or "선택 안 함"
    swatch_hex = _catalog_hex(cat_key, item_id) or "#eeeeee"
    col_sw, col_btn, col_off = st.columns([1, 3.3, 1])
    with col_sw:
        html_block(
            f'<div style="width:100%;aspect-ratio:1;border-radius:10px;background:{swatch_hex};'
            f'border:2px solid rgba(0,0,0,.1);display:flex;align-items:center;justify-content:center;'
            f'font-size:1.3rem;">{catalog["icon"]}</div>'
        )
    with col_btn:
        if st.button(f"{title} · {current_label}", key=f"open_closet_{cat_key}", use_container_width=True):
            st.session_state.closet_category = cat_key
            goto("closet")
            st.rerun()
    with col_off:
        if item_id:
            if st.button("벗기기", key=f"unequip_{cat_key}", use_container_width=True):
                bucket_dict = dict(draft.get(bucket) or {})
                bucket_dict[cat_key] = None
                draft[bucket] = bucket_dict
                st.rerun()


def render_character():
    with st.container(key="character_page"):
        _render_character_body()


def _render_character_body():
    st.title("👤 캐릭터 만들기")

    draft = st.session_state.char_draft
    if not draft and get_character():
        st.session_state.char_draft = dict(get_character())
        draft = st.session_state.char_draft

    left, right = st.columns([1, 1.3])

    with left:
        render_doll_stage(draft)

    with right:
        tab_basic, tab_closet, tab_taste = st.tabs(["✨ 기본", "👗 옷장 · 액세서리", "🧭 취향"])

        with tab_basic, st.container(key="char_basic_tab"):
            draft["name"] = st.text_input(
                "이름", value=draft.get("name", ""), placeholder="캐릭터 이름을 입력하세요",
                key="char_name_input", max_chars=12,
            )
            chip_row("성별", GENDERS, "gender")
            chip_row("연령대", AGE_RANGES, "age_range")
            chip_row("피부 타입 (택 1)", SKIN_TYPES, "skin_type")
            chip_row("피부 특이사항 (해당되면 선택)", SKIN_TYPE_EXTRAS, "skin_type_extra", multi=True)
            skin_tone_row()
            chip_row("헤어 스타일", HAIR_TYPES, "hair_type")
            chip_row("패션 스타일", CLOTHING, "style")

        with tab_closet:
            st.caption("항목을 누르면 30가지 선택지가 있는 화면으로 이동해요.")
            st.markdown("**옷**")
            for cat_key in ["top", "bottom", "socks", "shoes", "hat"]:
                closet_link_row(CLOSET_CATALOG[cat_key]["title"], cat_key, "outfit")
            st.divider()
            st.markdown("**액세서리**")
            for cat_key in ["necklace", "sunglasses", "gloves"]:
                closet_link_row(ACCESSORY_CATALOG[cat_key]["title"], cat_key, "accessories")

        with tab_taste:
            chip_row("성격 특성", PERSONALITY_TRAITS, "personality", multi=True)
            chip_row("여행 성향", TRAVEL_STYLES, "travel_style")
            chip_row("선호하는 화장품 특성", COSMETIC_PREFS, "cosmetic_prefs", multi=True)

        st.divider()
        if st.button("캐릭터 완성! →", type="primary", use_container_width=True):
            st.session_state.character = {
                "name": (draft.get("name") or "").strip() or "여행자",
                "gender": draft.get("gender") or GENDERS[0],
                "skin_type": draft.get("skin_type") or SKIN_TYPES[0],
                "skin_type_extra": list(draft.get("skin_type_extra") or []),
                "skin_tone": draft.get("skin_tone") or SKIN_TONES[0]["hex"],
                "hair_type": draft.get("hair_type") or HAIR_TYPES[0],
                "age_range": draft.get("age_range") or AGE_RANGES[0],
                "style": draft.get("style") or CLOTHING[0],
                "outfit": dict(draft.get("outfit") or {}),
                "accessories": dict(draft.get("accessories") or {}),
                "personality": list(draft.get("personality") or []),
                "travel_style": draft.get("travel_style"),
                "cosmetic_prefs": list(draft.get("cosmetic_prefs") or []),
            }
            specs = _generate_bubble_specs()
            st.session_state.bubble_specs = specs
            render_bubble_cover(specs)
            time.sleep(bubble_cover_seconds(specs))
            st.session_state.show_page_transition = True
            goto("map")
            st.rerun()


# ----------------------------------------------------------------------
# 옷장/액세서리 아이템 아이콘 — 색깔 사각형이 아니라 실제 옷 모양처럼 보이는
# SVG 실루엣. 카테고리마다 종류(예: 상의의 티셔츠/니트/셔츠/후드티/블라우스)별로
# 모양이 다르고, 색은 아이템의 hex를 그대로 입힌다.
# ----------------------------------------------------------------------
def _top_tshirt(hex_, dark):
    return (f'<path d="M35,28 Q50,40 65,28 L71,37 L85,46 L78,61 L66,52 L66,86 L34,86 L34,52 '
            f'L22,61 L15,46 L29,37 Z" fill="{hex_}" stroke="{dark}" stroke-width="2"/>')


def _top_knit(hex_, dark):
    body = (f'<path d="M35,30 Q50,40 65,30 L72,40 L84,48 L77,60 L67,53 L67,80 L33,80 L33,53 '
            f'L23,60 L16,48 L28,40 Z" fill="{hex_}" stroke="{dark}" stroke-width="2"/>')
    ribs = "".join(f'<line x1="{33+n*3}" y1="79" x2="{33+n*3}" y2="83" stroke="{dark}" stroke-width="1.4"/>'
                   for n in range(12))
    return body + ribs


def _top_shirt(hex_, dark):
    body = (f'<path d="M36,29 L50,38 L64,29 L71,38 L84,47 L77,60 L67,52 L67,85 L33,85 L33,52 '
            f'L23,60 L16,47 L29,38 Z" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
            f'<path d="M50,38 L44,30 L36,29 Z" fill="{dark}" opacity=".55"/>'
            f'<path d="M50,38 L56,30 L64,29 Z" fill="{dark}" opacity=".55"/>')
    placket = f'<line x1="50" y1="42" x2="50" y2="83" stroke="{dark}" stroke-width="1.4"/>'
    buttons = "".join(f'<circle cx="50" cy="{48+n*9}" r="1.6" fill="{dark}"/>' for n in range(4))
    return body + placket + buttons


def _top_hoodie(hex_, dark):
    hood = f'<path d="M38,26 Q50,16 62,26 Q66,34 58,36 Q50,30 42,36 Q34,34 38,26 Z" fill="{dark}" opacity=".65"/>'
    body = (f'<path d="M37,32 Q50,42 63,32 L71,42 L85,51 L78,64 L67,56 L67,86 L33,86 L33,56 '
            f'L22,64 L15,51 L29,42 Z" fill="{hex_}" stroke="{dark}" stroke-width="2"/>')
    strings = (f'<line x1="46" y1="40" x2="45" y2="54" stroke="{dark}" stroke-width="1.6"/>'
               f'<line x1="54" y1="40" x2="55" y2="54" stroke="{dark}" stroke-width="1.6"/>')
    pocket = f'<path d="M38,68 Q50,74 62,68" fill="none" stroke="{dark}" stroke-width="1.6"/>'
    return hood + body + strings + pocket


def _top_blouse(hex_, dark):
    body = (f'<path d="M37,30 Q50,40 63,30 L74,40 Q84,46 80,54 Q73,58 66,50 L66,84 L34,84 L34,50 '
            f'Q27,58 20,54 Q16,46 26,40 Z" fill="{hex_}" stroke="{dark}" stroke-width="2"/>')
    bow = f'<circle cx="50" cy="36" r="3.4" fill="{dark}" opacity=".7"/>'
    return body + bow


def _bottom_jeans(hex_, dark):
    waist = f'<rect x="30" y="18" width="40" height="8" rx="2" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    loops = "".join(f'<rect x="{x}" y="16" width="3" height="6" fill="{dark}"/>' for x in (34, 47, 63))
    legs = (f'<path d="M31,26 L30,86 L45,86 L49,40 L51,40 L55,86 L70,86 L69,26 Z" '
            f'fill="{hex_}" stroke="{dark}" stroke-width="2"/>')
    # 실제 청바지 특유의 대비되는(주황빛) 스티치 — 슬랙스와 구분되는 포인트
    seams = (f'<line x1="37" y1="30" x2="34" y2="84" stroke="#d9922e" stroke-width="1.3" stroke-dasharray="2,2" opacity=".85"/>'
             f'<line x1="63" y1="30" x2="66" y2="84" stroke="#d9922e" stroke-width="1.3" stroke-dasharray="2,2" opacity=".85"/>')
    pockets = (f'<path d="M35,30 Q40,34 44,30" fill="none" stroke="{dark}" stroke-width="1.4"/>'
               f'<path d="M56,30 Q60,34 65,30" fill="none" stroke="{dark}" stroke-width="1.4"/>')
    return waist + loops + legs + seams + pockets


def _bottom_slacks(hex_, dark):
    waist = f'<rect x="30" y="18" width="40" height="7" rx="2" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    legs = (f'<path d="M31,25 L29,86 L44,86 L49,38 L51,38 L56,86 L71,86 L69,25 Z" '
            f'fill="{hex_}" stroke="{dark}" stroke-width="2"/>')
    creases = (f'<line x1="38" y1="30" x2="35" y2="84" stroke="{dark}" stroke-width="1" opacity=".5"/>'
               f'<line x1="62" y1="30" x2="65" y2="84" stroke="{dark}" stroke-width="1" opacity=".5"/>')
    return waist + legs + creases


def _bottom_shorts(hex_, dark):
    waist = f'<rect x="30" y="20" width="40" height="8" rx="2" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    legs = (f'<path d="M31,28 L28,58 L46,58 L49,44 L51,44 L54,58 L72,58 L69,28 Z" '
            f'fill="{hex_}" stroke="{dark}" stroke-width="2"/>')
    seams = (f'<line x1="38" y1="32" x2="36" y2="56" stroke="{dark}" stroke-width="1" opacity=".5"/>'
             f'<line x1="62" y1="32" x2="64" y2="56" stroke="{dark}" stroke-width="1" opacity=".5"/>')
    return waist + legs + seams


def _bottom_skirt(hex_, dark):
    return (f'<path d="M40,20 L60,20 L82,84 L18,84 Z" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
            f'<line x1="50" y1="26" x2="50" y2="78" stroke="{dark}" stroke-width="1" opacity=".4"/>'
            f'<line x1="38" y1="30" x2="30" y2="80" stroke="{dark}" stroke-width="1" opacity=".4"/>'
            f'<line x1="62" y1="30" x2="70" y2="80" stroke="{dark}" stroke-width="1" opacity=".4"/>')


def _bottom_leggings(hex_, dark):
    waist = f'<rect x="33" y="18" width="34" height="7" rx="2" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    legs = (f'<path d="M34,25 L33,90 L45,90 L49,40 L51,40 L55,90 L67,90 L66,25 Z" '
            f'fill="{hex_}" stroke="{dark}" stroke-width="2"/>')
    stripe = (f'<line x1="36" y1="28" x2="35" y2="88" stroke="{dark}" stroke-width="1" opacity=".45"/>'
              f'<line x1="64" y1="28" x2="65" y2="88" stroke="{dark}" stroke-width="1" opacity=".45"/>')
    return waist + legs + stripe


def _sock_base(hex_, dark, cuff_top):
    return (f'<path d="M38,{cuff_top} L64,{cuff_top} L64,68 L84,68 Q90,68 89,76 L86,84 L38,84 Z" '
            f'fill="{hex_}" stroke="{dark}" stroke-width="2"/>')


def _socks_ankle(hex_, dark):
    return _sock_base(hex_, dark, 52)


def _socks_knee(hex_, dark):
    return _sock_base(hex_, dark, 16)


def _socks_knit(hex_, dark):
    base = _sock_base(hex_, dark, 16)
    ribs = "".join(f'<line x1="39" y1="{20+n*7}" x2="63" y2="{20+n*7}" stroke="{dark}" '
                   f'stroke-width="1.2" opacity=".5"/>' for n in range(7))
    return base + ribs


def _socks_lace(hex_, dark):
    base = _sock_base(hex_, dark, 40)
    scallops = "".join(f'<circle cx="{40+n*6}" cy="40" r="3" fill="{hex_}" stroke="{dark}" '
                       f'stroke-width="1"/>' for n in range(5))
    return base + scallops


def _socks_pattern(hex_, dark):
    base = _sock_base(hex_, dark, 30)
    dots = "".join(f'<circle cx="{cx}" cy="{cy}" r="2.2" fill="{dark}" opacity=".6"/>'
                   for cx, cy in [(45, 38), (55, 45), (46, 52), (57, 58), (48, 64)])
    return base + dots


def _shoes_sneakers(hex_, dark):
    body = (f'<path d="M10,72 Q10,58 28,56 L60,52 Q72,50 80,58 L90,62 Q92,68 88,72 Z" '
            f'fill="{hex_}" stroke="{dark}" stroke-width="2"/>')
    sole = f'<path d="M8,72 L90,72 Q92,80 84,80 L14,80 Q8,80 8,72 Z" fill="#f4f4f4" stroke="{dark}" stroke-width="1.6"/>'
    laces = "".join(f'<line x1="{40+n*7}" y1="55" x2="{47+n*7}" y2="62" stroke="{dark}" stroke-width="1.4"/>'
                    for n in range(3))
    return body + sole + laces


def _shoes_loafers(hex_, dark):
    body = (f'<path d="M10,70 Q12,56 30,55 L62,54 Q76,54 84,62 L90,68 Q90,74 82,74 L12,74 Z" '
            f'fill="{hex_}" stroke="{dark}" stroke-width="2"/>')
    sole = f'<rect x="9" y="74" width="82" height="6" rx="3" fill="#f4f4f4" stroke="{dark}" stroke-width="1.4"/>'
    strap = (f'<rect x="34" y="60" width="24" height="6" rx="2" fill="{dark}" opacity=".7"/>'
             f'<rect x="43" y="60" width="6" height="6" fill="{dark}"/>')
    return body + sole + strap


def _shoes_boots(hex_, dark):
    body = (f'<path d="M30,20 L66,20 L66,58 L84,64 Q92,68 88,74 L12,74 Q10,66 20,60 L30,56 Z" '
            f'fill="{hex_}" stroke="{dark}" stroke-width="2"/>')
    sole = f'<rect x="9" y="74" width="82" height="7" rx="3" fill="#3a3a3a" stroke="{dark}" stroke-width="1.4"/>'
    zip_ = f'<line x1="60" y1="24" x2="60" y2="56" stroke="{dark}" stroke-width="1.2" opacity=".5"/>'
    return body + sole + zip_


def _shoes_sandals(hex_, dark):
    sole = f'<path d="M10,68 Q10,78 22,78 L78,78 Q90,78 90,68 Q90,60 78,60 L22,60 Q10,60 10,68 Z" ' \
           f'fill="{hex_}" opacity=".9" stroke="{dark}" stroke-width="2"/>'
    # 스트랩이 밑창과 같은 색조라서 어두운 색 아이템일 때 안 보이던 문제 —
    # 색과 상관없이 항상 보이도록 크림색 바탕 + 어두운 중심선 이중선으로 그림
    strap_pts = [(22, 60, 40, 40), (40, 60, 22, 40), (34, 60, 34, 38)]
    straps = "".join(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#fffaf3" stroke-width="5" stroke-linecap="round"/>'
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{dark}" stroke-width="2" stroke-linecap="round"/>'
        for x1, y1, x2, y2 in strap_pts
    )
    return sole + straps


def _shoes_flats(hex_, dark):
    body = (f'<path d="M10,70 Q12,58 30,57 L64,56 Q78,56 84,64 Q86,70 78,72 L14,72 Z" '
            f'fill="{hex_}" stroke="{dark}" stroke-width="2"/>')
    sole = f'<rect x="10" y="72" width="76" height="4" rx="2" fill="#f4f4f4" stroke="{dark}" stroke-width="1.2"/>'
    bow = f'<circle cx="30" cy="62" r="3" fill="{dark}" opacity=".7"/>'
    return body + sole + bow


def _hat_cap(hex_, dark):
    crown = f'<path d="M20,55 Q20,25 50,25 Q80,25 80,55 Z" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    brim = f'<path d="M50,55 Q75,55 88,50 Q90,58 78,62 L50,58 Z" fill="{dark}" opacity=".75"/>'
    button = f'<circle cx="50" cy="27" r="2.4" fill="{dark}"/>'
    return crown + brim + button


def _hat_bucket(hex_, dark):
    crown = f'<ellipse cx="50" cy="35" rx="26" ry="18" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    brim = f'<ellipse cx="50" cy="56" rx="40" ry="12" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    return brim + crown


def _hat_beanie(hex_, dark):
    dome = f'<path d="M22,58 Q22,20 50,18 Q78,20 78,58 Z" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    cuff = f'<rect x="22" y="48" width="56" height="12" rx="4" fill="{dark}" opacity=".55"/>'
    pom = f'<circle cx="50" cy="16" r="5" fill="{hex_}" stroke="{dark}" stroke-width="1.6"/>'
    return dome + cuff + pom


def _hat_beret(hex_, dark):
    disc = f'<ellipse cx="48" cy="42" rx="34" ry="20" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    folds = "".join(f'<line x1="62" y1="28" x2="{30+n*8}" y2="{50+n*2}" stroke="{dark}" '
                    f'stroke-width="1" opacity=".35"/>' for n in range(4))
    stem = f'<circle cx="62" cy="26" r="2.6" fill="{dark}"/>'
    return disc + folds + stem


def _hat_straw(hex_, dark):
    brim = f'<ellipse cx="50" cy="55" rx="42" ry="10" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    crown = f'<path d="M32,55 Q32,30 50,28 Q68,30 68,55 Z" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    band = f'<rect x="32" y="48" width="36" height="5" fill="{dark}" opacity=".6"/>'
    weave = "".join(f'<line x1="{28+n*9}" y1="48" x2="{28+n*9}" y2="62" stroke="{dark}" '
                    f'stroke-width="1" opacity=".3"/>' for n in range(8))
    return brim + weave + crown + band


def _necklace_chain(hex_, dark):
    pts = [(24, 30), (30, 44), (38, 54), (50, 58), (62, 54), (70, 44), (76, 30)]
    links = "".join(f'<circle cx="{x}" cy="{y}" r="4" fill="none" stroke="{hex_}" stroke-width="2.6"/>'
                    for x, y in pts)
    return links


def _necklace_pearl(hex_, dark):
    pts = [(24, 28), (30, 42), (37, 53), (50, 58), (63, 53), (70, 42), (76, 28)]
    pearls = "".join(f'<circle cx="{x}" cy="{y}" r="5" fill="{hex_}" stroke="{dark}" stroke-width="1"/>'
                     for x, y in pts)
    return pearls


def _necklace_pendant(hex_, dark):
    cord = f'<path d="M24,26 Q50,60 76,26" fill="none" stroke="{dark}" stroke-width="1.8"/>'
    gem = f'<path d="M46,56 L54,56 L58,68 L50,80 L42,68 Z" fill="{hex_}" stroke="{dark}" stroke-width="1.6"/>'
    return cord + gem


def _necklace_choker(hex_, dark):
    band = f'<path d="M30,32 Q50,48 70,32" fill="none" stroke="{hex_}" stroke-width="7" stroke-linecap="round"/>'
    charm = f'<circle cx="50" cy="44" r="3.2" fill="{dark}"/>'
    return band + charm


def _necklace_layered(hex_, dark):
    l1 = f'<path d="M26,26 Q50,42 74,26" fill="none" stroke="{hex_}" stroke-width="2.4"/>'
    l2 = f'<path d="M24,28 Q50,54 76,28" fill="none" stroke="{hex_}" stroke-width="2.4"/>'
    l3 = f'<path d="M22,30 Q50,68 78,30" fill="none" stroke="{hex_}" stroke-width="2.4"/>'
    return l1 + l2 + l3


def _sun_round(hex_, dark):
    lenses = (f'<circle cx="34" cy="50" r="16" fill="{hex_}" stroke="{dark}" stroke-width="2.4"/>'
              f'<circle cx="66" cy="50" r="16" fill="{hex_}" stroke="{dark}" stroke-width="2.4"/>')
    bridge = f'<line x1="50" y1="47" x2="50" y2="47" stroke="{dark}" stroke-width="3"/>' \
             f'<path d="M46,47 Q50,44 54,47" fill="none" stroke="{dark}" stroke-width="2.4"/>'
    temples = (f'<line x1="18" y1="46" x2="6" y2="40" stroke="{dark}" stroke-width="2.4"/>'
               f'<line x1="82" y1="46" x2="94" y2="40" stroke="{dark}" stroke-width="2.4"/>')
    return lenses + bridge + temples


def _sun_cat(hex_, dark):
    left = f'<path d="M14,52 Q14,38 30,38 L44,42 Q46,52 40,58 Q26,62 14,52 Z" fill="{hex_}" stroke="{dark}" stroke-width="2.2"/>'
    right = f'<path d="M86,52 Q86,38 70,38 L56,42 Q54,52 60,58 Q74,62 86,52 Z" fill="{hex_}" stroke="{dark}" stroke-width="2.2"/>'
    bridge = f'<path d="M44,45 Q50,42 56,45" fill="none" stroke="{dark}" stroke-width="2.2"/>'
    return left + right + bridge


def _sun_square(hex_, dark):
    lenses = (f'<rect x="16" y="38" width="30" height="22" rx="4" fill="{hex_}" stroke="{dark}" stroke-width="2.2"/>'
              f'<rect x="54" y="38" width="30" height="22" rx="4" fill="{hex_}" stroke="{dark}" stroke-width="2.2"/>')
    bridge = f'<line x1="46" y1="47" x2="54" y2="47" stroke="{dark}" stroke-width="2.4"/>'
    return lenses + bridge


def _sun_oversized(hex_, dark):
    lenses = (f'<rect x="10" y="32" width="36" height="30" rx="10" fill="{hex_}" stroke="{dark}" stroke-width="2.6"/>'
              f'<rect x="54" y="32" width="36" height="30" rx="10" fill="{hex_}" stroke="{dark}" stroke-width="2.6"/>')
    bridge = f'<line x1="46" y1="46" x2="54" y2="46" stroke="{dark}" stroke-width="3"/>'
    return lenses + bridge


def _sun_sport(hex_, dark):
    return (f'<path d="M8,50 Q8,34 30,32 Q50,30 70,32 Q92,34 92,50 Q92,60 78,60 Q50,64 22,60 '
            f'Q8,60 8,50 Z" fill="{hex_}" stroke="{dark}" stroke-width="2.4"/>'
            f'<path d="M46,40 Q50,38 54,40" fill="none" stroke="{dark}" stroke-width="1.6" opacity=".6"/>')


def _glove_base(hex_, dark, extra=""):
    palm = f'<rect x="32" y="42" width="32" height="38" rx="12" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    fingers = "".join(
        f'<rect x="{x}" y="16" width="7" height="30" rx="3.4" fill="{hex_}" stroke="{dark}" stroke-width="1.6"/>'
        for x in (33, 43, 53, 63)
    )
    thumb = f'<rect x="18" y="46" width="16" height="9" rx="4" fill="{hex_}" stroke="{dark}" stroke-width="1.6"/>'
    return palm + fingers + thumb + extra


def _glove_knit(hex_, dark):
    ribs = "".join(f'<line x1="34" y1="{68+n*4}" x2="62" y2="{68+n*4}" stroke="{dark}" '
                   f'stroke-width="1" opacity=".5"/>' for n in range(3))
    return _glove_base(hex_, dark, ribs)


def _glove_leather(hex_, dark):
    seams = "".join(f'<line x1="{x}" y1="18" x2="{x}" y2="44" stroke="{dark}" stroke-width="1" opacity=".4"/>'
                    for x in (36.5, 46.5, 56.5, 66.5))
    strap = f'<rect x="40" y="74" width="16" height="4" fill="{dark}" opacity=".7"/>'
    return _glove_base(hex_, dark, seams + strap)


def _glove_lace(hex_, dark):
    dots = "".join(f'<circle cx="{34+n*6}" cy="76" r="1.6" fill="{dark}" opacity=".6"/>' for n in range(6))
    return _glove_base(hex_, dark, dots)


def _glove_sport(hex_, dark):
    panels = "".join(f'<line x1="33" y1="{22+n*8}" x2="63" y2="{22+n*8}" stroke="{dark}" '
                     f'stroke-width="1" opacity=".4"/>' for n in range(3))
    strap = f'<rect x="30" y="70" width="34" height="6" fill="{dark}" opacity=".7"/>'
    return _glove_base(hex_, dark, panels + strap)


def _glove_mitten(hex_, dark):
    pouch = f'<path d="M34,80 L34,50 Q34,20 50,20 Q66,20 66,50 L66,80 Z" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    thumb = f'<path d="M34,58 Q18,56 18,46 Q18,38 28,40 L34,46 Z" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    cuff = f'<rect x="32" y="74" width="36" height="8" rx="3" fill="{dark}" opacity=".5"/>'
    return pouch + thumb + cuff


GARMENT_SHAPES = {
    "top": [_top_tshirt, _top_knit, _top_shirt, _top_hoodie, _top_blouse],
    "bottom": [_bottom_jeans, _bottom_slacks, _bottom_shorts, _bottom_skirt, _bottom_leggings],
    "socks": [_socks_ankle, _socks_knee, _socks_knit, _socks_lace, _socks_pattern],
    "shoes": [_shoes_sneakers, _shoes_loafers, _shoes_boots, _shoes_sandals, _shoes_flats],
    "hat": [_hat_cap, _hat_bucket, _hat_beanie, _hat_beret, _hat_straw],
    "necklace": [_necklace_chain, _necklace_pearl, _necklace_pendant, _necklace_choker, _necklace_layered],
    "sunglasses": [_sun_round, _sun_cat, _sun_square, _sun_oversized, _sun_sport],
    "gloves": [_glove_knit, _glove_leather, _glove_lace, _glove_sport, _glove_mitten],
}


def item_icon_svg(cat_key, item):
    """옷장/액세서리 아이템 하나를 실제 옷 모양과 비슷한 SVG 아이콘으로 그린다."""
    shapes = GARMENT_SHAPES.get(cat_key)
    hex_ = item["hex"]
    # 흰색·아주 밝은 아이템은 테두리가 안 보여서 카드에 묻히니 살짝 어둡게, 나머진 그림자색으로
    dark = _shade(hex_, 0.55) if hex_.upper() not in ("#FFFFFF",) else "#c9c4bd"
    if not shapes:
        return f'<circle cx="50" cy="50" r="30" fill="{hex_}" stroke="{dark}" stroke-width="2"/>'
    fn = shapes[item.get("shape_idx", 0) % len(shapes)]
    return (f'<svg viewBox="0 0 100 100" width="100%" height="100%" style="display:block;" '
            f'xmlns="http://www.w3.org/2000/svg">{fn(hex_, dark)}</svg>')


def render_closet():
    cat_key = st.session_state.closet_category
    catalog = ALL_CATALOGS.get(cat_key)
    if not catalog:
        goto("character")
        st.rerun()
        return

    bucket = "accessories" if cat_key in ACCESSORY_CATALOG else "outfit"
    draft = st.session_state.char_draft
    current = (draft.get(bucket) or {}).get(cat_key)

    left, right = st.columns([1, 1.3])
    with left:
        render_doll_stage(draft)
    with right:
        st.title(f"{catalog['icon']} {catalog['title']} 고르기")
        st.caption("원하는 아이템을 눌러보세요. 같은 아이템을 다시 누르면 선택이 해제돼요.")

        items = catalog["items"]
        per_row = 5
        for start in range(0, len(items), per_row):
            row_items = items[start:start + per_row]
            cols = st.columns(per_row)
            for col, item in zip(cols, row_items):
                with col:
                    selected = current == item["id"]
                    border = "4px solid #ff6fb8" if selected else "3px solid rgba(0,0,0,.08)"
                    shadow = "0 0 0 3px #fff, 0 6px 14px rgba(255,111,184,.4)" if selected else "0 3px 8px rgba(0,0,0,.1)"
                    icon_svg = item_icon_svg(cat_key, item)
                    html_block(
                        f'<div style="width:100%;aspect-ratio:1;border-radius:14px;background:#faf7f2;'
                        f'display:flex;align-items:center;justify-content:center;padding:10px;box-sizing:border-box;'
                        f'border:{border};box-shadow:{shadow};">{icon_svg}</div>'
                    )
                    if st.button(item["label"], key=f"pick_{item['id']}", use_container_width=True):
                        bucket_dict = dict(draft.get(bucket) or {})
                        bucket_dict[cat_key] = None if bucket_dict.get(cat_key) == item["id"] else item["id"]
                        draft[bucket] = bucket_dict
                        st.rerun()

        st.divider()
        if st.button("← 캐릭터로 돌아가기", type="primary", use_container_width=True):
            goto("character")
            st.rerun()


_MAP_GLOBE_MAX_PX = 540  # clamp()의 최댓값 — 텍스처 background-size(2배)와 항상 같이 맞춰줘야 함


def _map_globe_gate():
    """지도 화면의 기본 화면 — 홈 화면의 자전하는 지구를 그대로 가져오되, 살짝 더
    입체적으로(그림자/하이라이트를 조금 더 진하게). 누르면 세계지도가 지구 위에 뜬다
    (다른 페이지로 넘어가는 게 아니라 st.dialog로 배경이 어두워지며 펼쳐짐 — 아래
    _world_map_dialog). 홈 화면 자체의 애니메이션(render_home)은 그대로 두고
    별도로 복사해서 씀.

    처음엔 지구 그림을 html_block으로 따로 그리고 그 위에 투명 버튼을 겹쳐서 클릭을
    받으려 했는데, 실제로는 안 눌리는 버그가 있었다(두 요소를 따로 겹치다 보니 위치/
    높이 계산이 어긋난 것으로 추정). 그래서 여권 표지 버튼과 같이 이미 검증된 방식으로
    바꿈 — 버튼 자기 자신에 ::before/::after로 그림을 입혀서 "그림 = 버튼"이 되게
    하면 겹침 문제 자체가 생길 수 없다."""
    earth = asset_data_uri("earth_map.webp", "image/webp")
    tex_w, tex_h = _MAP_GLOBE_MAX_PX * 2, _MAP_GLOBE_MAX_PX
    html_block(
        f"""
        <style>
        .map-globe-hint {{
            text-align: center; font-family: 'Jua', sans-serif; font-size: 1.5rem;
            font-weight: 700; color: #5a4a7a; margin: 4px 0 6px;
        }}
        /* 버튼 자체가 아니라 버튼을 감싸는 st-key wrapper를 flex로 중앙 정렬한다 —
           Streamlit이 위젯을 자체적으로 flex 컨테이너에 넣는 경우가 있어서, 버튼에
           margin:auto만 주면 안 먹히고 왼쪽에 붙어버리는 문제가 있었다. */
        .st-key-open_world_map {{
            display: flex !important; justify-content: center !important; width: 100% !important;
        }}
        .st-key-open_world_map.st-key-open_world_map button {{
            position: relative !important;
            width: clamp(330px,69vw,{_MAP_GLOBE_MAX_PX}px) !important;
            height: clamp(330px,69vw,{_MAP_GLOBE_MAX_PX}px) !important;
            min-width: 0 !important; max-width: none !important;
            border-radius: 50% !important; border: none !important; padding: 0 !important;
            margin: 14px auto 6px !important; display: block !important;
            background: transparent !important; overflow: hidden !important;
            /* 구 입체감: 좌상단 프레넬 하이라이트(밝게) + 우하단 코어 섀도우(어둡게)로
               텍스처 위에 실제 조명을 얹어 구체처럼 보이게 함 (아래 ::after의 평평한
               라디얼 그라데이션만으로는 입체감이 약했던 문제 보완) */
            box-shadow:
                inset 10px 10px 30px rgba(215,240,255,.65),
                inset -8px -10px 26px rgba(10,20,55,.6),
                inset 0 0 46px rgba(255,255,255,.12),
                inset 0 0 30px 6px rgba(170,220,255,.3),
                0 0 24px 5px rgba(255,255,255,.4),
                0 0 64px 16px rgba(120,190,255,.72),
                0 40px 68px rgba(20,40,90,.62);
            animation: map-earth-float 7s ease-in-out infinite;
            transition: transform .15s ease;
            cursor: pointer;
        }}
        .st-key-open_world_map.st-key-open_world_map button:hover {{ transform: scale(1.04); }}
        .st-key-open_world_map.st-key-open_world_map button:active {{ transform: scale(.97); }}
        .st-key-open_world_map.st-key-open_world_map button::before {{
            content: ''; position: absolute; inset: 0; border-radius: 50%;
            background-image: url('{earth}');
            background-size: {tex_w}px {tex_h}px; background-repeat: repeat-x;
            background-position: 0 center;
            filter: brightness(1.55) contrast(1.22) saturate(1.28);
            animation: spin-earth-map 30s linear infinite;
        }}
        /* mix-blend-mode: multiply를 쓰면 흰색 하이라이트가 곱연산으로 사라져버려
           그림자만 남고 평평해 보였다 — 일반(normal) 합성으로 밝기/어둠을 함께 얹고,
           가장자리 앰비언트 오클루전 + 테두리 프레넬 림 라이트를 추가해 구체감을 강화 */
        .st-key-open_world_map.st-key-open_world_map button::after {{
            content: ''; position: absolute; inset: 0; border-radius: 50%;
            background:
                radial-gradient(ellipse 30% 17% at 30% 22%, rgba(255,255,255,.95) 0%, rgba(255,255,255,.4) 38%, rgba(255,255,255,0) 68%),
                radial-gradient(circle at 70% 76%, rgba(2,6,24,0) 15%, rgba(2,6,24,.58) 52%, rgba(1,3,16,.97) 100%),
                radial-gradient(circle at 50% 50%, rgba(3,8,28,0) 42%, rgba(3,8,28,.3) 80%, rgba(1,3,14,.72) 100%),
                radial-gradient(circle at 50% 50%, rgba(150,210,255,0) 86%, rgba(150,210,255,.4) 96%, rgba(120,190,255,.18) 100%);
        }}
        @keyframes spin-earth-map {{ from{{background-position:0 center;}} to{{background-position:-{tex_w}px center;}} }}
        @keyframes map-earth-float {{ 0%,100%{{transform:translateY(0);}} 50%{{transform:translateY(-14px);}} }}
        @media (prefers-reduced-motion: reduce) {{
            .st-key-open_world_map.st-key-open_world_map button,
            .st-key-open_world_map.st-key-open_world_map button::before {{ animation: none !important; }}
        }}
        </style>
        <div class="map-globe-hint">🌍 지구를 눌러 세계지도를 펼쳐보세요</div>
        """
    )
    if st.button(" ", key="open_world_map"):
        st.session_state.map_globe_opened = True
        st.rerun()


def _dismiss_world_map():
    """다이얼로그 기본 X/ESC/바깥 클릭으로 닫았을 때도 상태를 꺼준다 — 뷰티
    패스포트에서 겪었던 것과 같은 '닫아도 계속 뜨는' 버그를 막기 위함."""
    st.session_state.map_globe_opened = False


@st.dialog("🗺️ 여행지 지도", width="large", on_dismiss=_dismiss_world_map)
def _world_map_dialog():
    """지구를 누르면 배경이 어두워지며 이 위에 세계지도가 뜬다 (페이지 이동이 아니라
    지구 '위에 뜨는' 느낌을 위해 st.dialog 사용 — 뷰티 패스포트와 같은 방식).
    핀을 누르면 예전 카드의 '자세히 보기'와 동일하게 국가 상세 화면으로 이동.

    카드 자체는 실제 낡은 가죽/양피지 지도(트레저맵)처럼 보이도록 스타일링한다 —
    다이얼로그 기본 흰 배경/제목을 지우고, 세피아 톤 배경 + 두꺼운 갈색 테두리 +
    말려있는 종이 느낌의 위아래 롤러 + 나침반 장식을 얹은 우리만의 카드로 대체."""
    svg = _load_world_map_svg()
    pin_rules = []
    for code, c in COUNTRIES.items():
        if not c.get("geo"):
            continue
        x_pct, y_pct = _country_pin_percent(c["geo"])
        pin_rules.append(f'.st-key-pin_{code} {{ left:{x_pct:.2f}%; top:{y_pct:.2f}%; }}')

    html_block(
        """
        <style>
        /* 다이얼로그 기본 흰 카드를 훨씬 크게, 그리고 우리 스타일로 뒤집어 씌운다 */
        div[data-testid="stDialog"] [slot="title"] { display: none !important; }
        div[data-testid="stDialog"] > div {
            max-width: min(94vw, 1520px) !important;
            width: min(94vw, 1520px) !important;
            max-height: 92vh !important; overflow-y: auto !important;
            background: transparent !important; box-shadow: none !important;
        }
        .st-key-map_scroll_card {
            position: relative;
            margin: 10px 6px 26px;
            padding: 30px 34px 22px;
            border-radius: 16px;
            background:
                radial-gradient(ellipse at 28% 18%, rgba(255,248,222,.55) 0%, rgba(255,248,222,0) 46%),
                linear-gradient(160deg, #ecd9a8 0%, #d8b876 45%, #bf9457 100%);
            border: 5px solid #7a4a23;
            box-shadow:
                inset 0 0 0 3px rgba(255,244,214,.55),
                inset 0 0 70px rgba(93,58,20,.32),
                0 26px 50px rgba(35,18,5,.5);
            /* 지구를 누르는 순간 지도가 뿅 켜지는 느낌이 너무 갑작스럽다는 피드백 —
               두루마리 지도가 펼쳐지듯 위에서 살짝 튕기며 커지는 등장 애니메이션을 준다 */
            transform-origin: top center;
            animation: map-scroll-unroll .6s cubic-bezier(.22,.85,.32,1.15) both;
        }
        @keyframes map-scroll-unroll {
            0%   { opacity: 0; transform: scale(.22) translateY(-40px); }
            55%  { opacity: 1; transform: scale(1.04) translateY(6px); }
            78%  { transform: scale(.98) translateY(-2px); }
            100% { opacity: 1; transform: scale(1) translateY(0); }
        }
        @media (prefers-reduced-motion: reduce) {
            .st-key-map_scroll_card { animation: none !important; }
        }
        .st-key-map_scroll_card::before,
        .st-key-map_scroll_card::after {
            content: ''; position: absolute; left: -16px; right: -16px; height: 24px;
            background: linear-gradient(180deg, #92622f, #4d3018);
            border-radius: 12px;
            box-shadow: 0 3px 8px rgba(0,0,0,.45), inset 0 2px 3px rgba(255,255,255,.2);
        }
        .st-key-map_scroll_card::before { top: -12px; }
        .st-key-map_scroll_card::after { bottom: -12px; }
        .scroll-compass {
            position: absolute; right: 18px; bottom: 16px; font-size: 2.4rem;
            opacity: .45; transform: rotate(8deg); pointer-events: none;
            filter: drop-shadow(0 2px 2px rgba(0,0,0,.35));
        }
        .scroll-title {
            text-align: center; font-family: Georgia, 'Times New Roman', serif;
            font-weight: 800; font-size: 1.9rem; color: #5c3612;
            text-shadow: 0 1px 0 rgba(255,255,255,.4); letter-spacing: .5px;
            margin: 0 0 2px;
        }
        .scroll-subtitle {
            text-align: center; font-family: 'Jua', sans-serif; font-size: 1.02rem;
            color: #6e4c26; margin: 0 0 16px;
        }
        .st-key-world_map_area { position: relative !important; width: 100% !important; }
        .world-map-frame {
            position: relative; width: 100%;
            aspect-ratio: 2752.766 / 1537.631;
            border-radius: 10px; overflow: hidden;
            border: 3px solid #6b4423;
            box-shadow: inset 0 0 24px rgba(60,36,10,.45);
        }
        .world-map-frame svg { display: block; width: 100%; height: 100%; }
        .st-key-world_map_area div[class*="st-key-pin_"] {
            position: absolute !important; transform: translate(-50%,-100%) !important;
            z-index: 6 !important;
        }
        """
        + " ".join(pin_rules) +
        """
        div[class*="st-key-pin_"] button {
            width: 38px !important; height: 38px !important; min-width: 0 !important;
            border-radius: 50% !important; padding: 0 !important;
            background: #fff8e6 !important; border: 3px solid #ff6fb8 !important;
            box-shadow: 0 4px 8px rgba(60,30,10,.5) !important;
            font-size: 1.15rem !important;
            transition: transform .15s ease;
        }
        div[class*="st-key-pin_"] button:hover { transform: scale(1.15) !important; }
        .st-key-close_world_map button {
            background: linear-gradient(180deg,#4d3320,#241407) !important;
            color: #f1dfb8 !important; border: 2px solid #8a5a2e !important;
            font-family: 'Jua', sans-serif !important; font-weight: 700 !important;
            letter-spacing: 1px;
        }
        .st-key-close_world_map button:hover {
            background: linear-gradient(180deg,#5c3f28,#2c1a0c) !important;
        }
        </style>
        """
    )

    with st.container(key="map_scroll_card"):
        html_block(
            """
            <div class="scroll-title">🗺️ 여행지 지도</div>
            <div class="scroll-subtitle">핀을 눌러 여행지 상세 정보를 확인하세요</div>
            """
        )
        with st.container(key="world_map_area"):
            html_block(
                f'<div class="world-map-frame">{svg}'
                '<div class="scroll-compass">🧭</div></div>'
            )
            for code, c in COUNTRIES.items():
                if not c.get("geo"):
                    continue
                if st.button(c["flag"], key=f"pin_{code}", help=c["name"]):
                    st.session_state.selected_country = code
                    st.session_state.country_stage = "map"
                    st.session_state.active_country_sheet = None
                    goto("country")
                    st.rerun()

        if st.button("나가기", key="close_world_map", use_container_width=True):
            st.session_state.map_globe_opened = False
            st.rerun()


def render_map():
    if not get_character():
        goto("character")
        st.rerun()
        return

    _map_globe_gate()
    if st.session_state.map_globe_opened:
        _world_map_dialog()


def _quick_skin_tip(char, country):
    """규칙 기반(즉시 응답) 피부타입×현지 기후 추천 — 포스트잇과 쇼핑 시트에서 재사용.
    get_skin_profile()이 반환하는 정규화된 프로필을 입력값으로 쓴다."""
    profile = get_skin_profile(char)
    base = {
        "건성": "고보습 크림·오일로 수분 방어막을 단단히 챙기세요",
        "지성": "가벼운 젤·워터 타입으로 유분 밸런스를 잡아주세요",
        "복합성": "부위별로 보습과 유분 조절 제품을 나눠 쓰는 게 좋아요",
    }
    tips = [base.get(profile["skin_type"], base["복합성"])]
    if "민감성" in profile["extras"]:
        tips.append("저자극·무향 성분 위주로 챙기세요")
    if "트러블" in profile["extras"]:
        tips.append("살리실릭·티트리 등 트러블 케어 성분을 곁들이면 좋아요")
    if country.get("essentials"):
        tips.append(f"현지 추천템: {country['essentials'][0]}")
    return tips


@st.cache_data(show_spinner=False, ttl=86400)
def _cached_ai_cosmetic_recommendation(skin_type, extras_key, prefs_key, country_code):
    country = COUNTRIES[country_code]
    prompt = (
        "너는 여행 뷰티 코디네이터야. 아래 여행자 정보와 목적지 기후를 보고 "
        "챙기면 좋은 화장품을 한국어로 짧게 추천해줘.\n\n"
        f"[여행자] 피부타입: {skin_type} / 피부 특이사항: {', '.join(extras_key) or '없음'} / "
        f"선호 화장품 특성: {', '.join(prefs_key) or '없음'}\n"
        f"[목적지] {country['name']} — 기후: {country['climate']} / 습도: {country['humidity']} / "
        f"자외선: {country['uv']} / 수질: {country['water']} ({country['water_note']}) / "
        f"주의할 트러블: {country['trouble']}\n\n"
        "형식: 제품 카테고리 3~4개를 각각 한 줄로, 필요한 이유를 짧게 붙여서 "
        "'- '로 시작하는 불릿 리스트로만 답해. 다른 설명은 붙이지 마."
    )
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def get_ai_cosmetic_recommendation(char, country_code):
    """AI 추천에 성공하면 텍스트를, 키가 없거나 호출이 실패하면 None을 반환한다
    (호출부는 None이면 규칙 기반 _quick_skin_tip으로 대체 표시).
    get_skin_profile()의 정규화된 프로필을 입력값으로 써서 다른 추천 로직과
    같은 피부타입/특이사항 판단 기준을 공유한다."""
    if not ANTHROPIC_API_KEY or anthropic is None:
        return None
    profile = get_skin_profile(char)
    try:
        return _cached_ai_cosmetic_recommendation(
            profile["skin_type"],
            tuple(sorted(profile["extras"])),
            tuple(sorted(char.get("cosmetic_prefs") or [])),
            country_code,
        )
    except Exception:
        return None


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
    if st.session_state.country_stage == "scene":
        _render_country_scene_stage(country, char, code)
    else:
        _render_country_map_stage(country, char, code)

    if st.session_state.active_country_sheet:
        _country_action_sheet(country, char, code)


COUNTRY_ZOOM_SCALE = 5.5  # 확대 지도의 세로 기준 확대 배율
COUNTRY_CROP_ASPECT = 2.15  # 확대 지도 크롭의 가로:세로 비율 (버튼이 옆으로 넓은 배너 모양이라)


@st.cache_data(show_spinner=False)
def _load_world_map_png():
    """미리 렌더링해 둔 세계지도 PNG(assets/world_map_render.png)를 불러온다.

    브라우저 CSS(background-size로 500%+ 확대한 SVG 배경)로 나라별 확대 지도를
    직접 만들어봤는데, 이 SVG가 너무 크고 복잡해서 그렇게 확대해 그리면 크로미움이
    일부 영역을 빈 배경색으로 잘라먹는 렌더링 버그가 실측으로 확인됐다(작은 나라뿐
    아니라 지도 좌표 산출에 쓰인 미국조차 중앙에서 크게 벗어나 보였음). 그래서 확대는
    브라우저가 아니라 서버(PIL)에서 미리 렌더링된 큰 PNG를 잘라 하는 방식으로 바꿨다 —
    이 PNG는 _load_world_map_svg()의 결과를 그대로(현재 COUNTRIES 강조 상태 기준)
    스크린샷 렌더링해 만든 것이라, COUNTRIES 강조국이 바뀌면 이 파일도 다시 만들어야
    강조색이 최신 상태로 반영된다(핀 클릭/전체 지도 다이얼로그는 여전히 실시간 SVG를
    쓰므로 그쪽은 항상 최신이다)."""
    return Image.open(ASSETS / "world_map_render.png").convert("RGB")


@st.cache_data(show_spinner=False)
def _country_zoom_crop_uri(country_code):
    """해당 나라의 위경도를 중심으로 미리 렌더링된 세계지도 PNG를 잘라 data URI로 반환."""
    country = COUNTRIES[country_code]
    img = _load_world_map_png()
    img_w, img_h = img.size
    x_pct, y_pct = _country_pin_percent(country["geo"])
    cx, cy = x_pct / 100 * img_w, y_pct / 100 * img_h

    crop_h = img_h / COUNTRY_ZOOM_SCALE
    crop_w = crop_h * COUNTRY_CROP_ASPECT
    left = min(max(cx - crop_w / 2, 0), img_w - crop_w)
    top = min(max(cy - crop_h / 2, 0), img_h - crop_h)
    crop = img.crop((int(left), int(top), int(left + crop_w), int(top + crop_h)))

    buf = BytesIO()
    crop.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _render_country_map_stage(country, char, code):
    """1단계 — 그 나라만 확대된 지도 + 옆에 붙은 포스트잇(환경/피부타입 추천/유의사항).
    지도 자체가 곧 버튼(다른 화면에서 이미 검증된 '그림=버튼' 방식) — 탭하면 2단계로."""
    st.title(f"{country['flag']} {country['name']}")

    zoom_uri = _country_zoom_crop_uri(code)
    tips = _quick_skin_tip(char, country)
    risk = get_skin_risk_note(code, country)
    risk_alert = risk["linked_to"] == "aqi" and _is_aqi_severe(country)

    html_block(
        f"""
        <style>
        .st-key-country_stage_wrap {{ position: relative !important; }}
        .st-key-enter_country_scene {{ width: 100% !important; }}
        .st-key-enter_country_scene button {{
            position: relative !important; width: 100% !important;
            height: clamp(340px, 64vh, 580px) !important;
            border-radius: 18px !important; border: 4px solid #6b4423 !important;
            overflow: hidden !important; padding: 0 !important;
            background-color: #dccb98 !important;
            background-image: url('{zoom_uri}') !important;
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
            box-shadow: inset 0 0 40px rgba(60,36,10,.5), 0 14px 30px rgba(60,30,10,.35) !important;
            transition: transform .15s ease;
        }}
        .st-key-enter_country_scene button:hover {{ transform: scale(1.008); }}
        /* 탭하면 살짝 오래 눌린 것처럼 확 쪼그라들었다가(쏙 들어감), 다음 화면이
           뜨면서 scene-pop-in으로 팝 튀어나오듯 확대돼 나오는(쏙 나옴) 느낌을 낸다 */
        .st-key-enter_country_scene button:active {{
            transform: scale(.72) !important; transition: transform .16s cubic-bezier(.4,0,.6,1) !important;
        }}
        .st-key-enter_country_scene button::after {{
            content: '👆 탭해서 캐릭터 만나기'; position: absolute; left: 50%; bottom: 14px;
            transform: translateX(-50%); font-family: 'Jua', sans-serif; font-size: .95rem;
            color: #fff; background: rgba(40,20,10,.55); padding: 6px 14px; border-radius: 999px;
            white-space: nowrap;
        }}
        .country-sticky-note {{
            position: absolute; top: 4%; right: 2%; width: min(460px, 62%);
            background: #fff7c2; padding: 26px 26px 22px; border-radius: 6px 22px 22px 6px;
            box-shadow: 5px 10px 22px rgba(0,0,0,.32); transform: rotate(2deg);
            font-family: 'Gaegu', cursive; color: #4a3a1a; pointer-events: none; z-index: 5;
        }}
        .country-sticky-note::before {{
            content: '📌'; position: absolute; top: -20px; left: 20px; font-size: 2rem;
            transform: rotate(-15deg);
        }}
        .note-title {{ font-weight: 700; font-size: 1.9rem; margin-bottom: 10px; }}
        .note-section {{ font-weight: 700; font-size: 1.25rem; margin: 14px 0 4px; color: #8a5a10; }}
        .note-line {{ font-size: 1.25rem; line-height: 1.5; margin: 0 0 4px; }}
        .note-line.risk-alert {{
            color: #c0392b; font-weight: 800; background: rgba(230,60,60,.14);
            border-radius: 8px; padding: 6px 8px; margin: 0 -8px 4px;
            animation: risk-alert-pulse 1.6s ease-in-out infinite;
        }}
        @keyframes risk-alert-pulse {{
            0%, 100% {{ background: rgba(230,60,60,.14); }}
            50% {{ background: rgba(230,60,60,.28); }}
        }}
        </style>
        """
    )

    with st.container(key="country_stage_wrap"):
        risk_class = "note-line risk-alert" if risk_alert else "note-line"
        risk_text = ("🔴 오늘 미세먼지 나쁨 — " if risk_alert else "") + risk["text"]
        html_block(
            f"""
            <div class="country-sticky-note">
                <div class="note-title">{country["flag"]} {country["name"]}</div>
                <div class="note-section">🌡 환경</div>
                <div class="note-line">기온 {html.escape(country["temp_diff"])}</div>
                <div class="note-line">습도 {html.escape(country["humidity"])}</div>
                <div class="note-line">자외선 {html.escape(country["uv"])}</div>
                <div class="note-line">수질 {html.escape(country["water"])} · {html.escape(country["water_note"])}</div>
                <div class="note-section">🧴 내 피부에 좋은 것</div>
                {''.join(f'<div class="note-line">· {html.escape(t)}</div>' for t in tips)}
                <div class="note-section">⚠ 유의사항</div>
                <div class="{risk_class}">{html.escape(risk_text)}</div>
            </div>
            """
        )
        if st.button(" ", key="enter_country_scene"):
            st.session_state.country_stage = "scene"
            st.session_state.just_entered_country_scene = True
            st.rerun()

    if st.button("⬅ 지도로 돌아가기", key="back_to_world_map"):
        goto("map")
        st.rerun()


def _render_country_scene_stage(country, char, code):
    """2단계 — 배경은 랜드마크(디자인 요소, 클릭 불가) + 캐릭터가 중앙,
    그 위에 6개 아이콘. 각 아이콘은 화면 전환 없이 바텀시트(다이얼로그)를 연다."""
    st.title(f"{country['flag']} {country['name']}")

    doll_svg = character_doll_svg(char)
    already_saved = code in [p["code"] for p in get_passport()]
    just_saved = st.session_state.just_saved_country_sparkle
    sparkle_rule = "animation: country-sparkle-burst 1s ease both;" if just_saved else ""
    st.session_state.just_saved_country_sparkle = False
    # 지도 단계에서 막 넘어온 경우에만 한 번 "쏙 하고 튀어나오는" 팝인 애니메이션을 준다
    # (탭 순간 지도 쪼그라드는 느낌은 위 :active 트랜지션이 맡고, 여기서는 그 다음 화면이
    # 작은 점에서 확 튀어나오는 느낌을 완성한다)
    just_entered = st.session_state.just_entered_country_scene
    pop_rule = "animation: scene-pop-in .5s cubic-bezier(.22,1.4,.36,1) both;" if just_entered else ""
    st.session_state.just_entered_country_scene = False

    html_block(
        f"""
        <style>
        .st-key-country_scene_stage {{ position: relative !important; }}
        .scene-stage {{
            position: relative; width: 100%; height: clamp(420px, 74vh, 680px);
            border-radius: 22px; overflow: hidden; margin-bottom: 10px;
            background: linear-gradient(160deg, #ffd9ec 0%, #cfe8ff 55%, #fff3d6 100%);
            box-shadow: inset 0 0 0 4px rgba(255,255,255,.6), 0 16px 32px rgba(120,60,90,.25);
            {pop_rule}
        }}
        @keyframes scene-pop-in {{
            0%   {{ transform: scale(.05); opacity: 0; }}
            55%  {{ transform: scale(1.08); opacity: 1; }}
            75%  {{ transform: scale(.96); }}
            100% {{ transform: scale(1); }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .scene-stage {{ animation: none !important; }}
        }}
        .scene-landmark-bg {{
            position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
            font-size: min(60vw, 420px); opacity: .12; pointer-events: none; user-select: none;
        }}
        .scene-doll-box {{
            position: absolute; left: 50%; top: 52%; transform: translate(-50%,-50%);
            width: min(46vw, 260px); pointer-events: none; z-index: 2; opacity: .55;
            filter: drop-shadow(0 18px 20px rgba(60,30,60,.28));
        }}
        .scene-doll-box svg {{ width: 100%; height: auto; display: block; }}
        .st-key-country_scene_stage div[class*="st-key-icn_"] {{
            position: absolute !important; z-index: 6 !important;
        }}
        /* left는 캐릭터가 있는 중앙(50%) 기준 아이콘 "중심" 좌표 -- translateX(-50%)로
           아이콘 자기 폭(84px)만큼의 오프셋을 상쇄해야 좌우가 실제로 대칭이 된다.
           (예전엔 left가 아이콘의 왼쪽 모서리 기준이라 84px만큼 오른쪽으로 치우쳐
           보였음 -- 오른쪽 아이콘이 캐릭터에 더 가깝게 보이던 원인) */
        .st-key-icn_water {{ top: 4%; left: 15%; transform: translateX(-50%); }}
        .st-key-icn_lipstick {{ top: 4%; left: 85%; transform: translateX(-50%); }}
        .st-key-icn_shop {{ top: 43%; left: 5%; transform: translateX(-50%); }}
        .st-key-icn_hair {{ top: 43%; left: 95%; transform: translateX(-50%); }}
        .st-key-icn_carrier {{ top: 84%; left: 15%; transform: translateX(-50%); }}
        .st-key-icn_star {{ top: 84%; left: 85%; transform: translateX(-50%); }}
        div[class*="st-key-icn_"] button {{
            width: 84px !important; height: 84px !important; min-width: 0 !important;
            border-radius: 50% !important; padding: 0 !important; font-size: 2.3rem !important;
            background: #ffffff !important; border: 4px solid #ff9fd8 !important;
            box-shadow: 0 8px 18px rgba(120,40,90,.35) !important;
            transition: transform .12s ease;
        }}
        div[class*="st-key-icn_"] button:hover {{ transform: scale(1.12) translateY(-2px); }}
        div[class*="st-key-icn_"] button:active {{ transform: scale(.94); }}
        .st-key-icn_star button {{
            {"background: linear-gradient(160deg,#ffe27a,#ffb347) !important; border-color:#ff9a1f !important;" if already_saved else ""}
        }}
        .scene-sparkle {{
            position: absolute; inset: 0; pointer-events: none; z-index: 8;
            background: radial-gradient(circle at 50% 52%, rgba(255,240,150,.9) 0%, rgba(255,240,150,0) 55%);
            {sparkle_rule}
        }}
        @keyframes country-sparkle-burst {{
            0% {{ opacity: 0; transform: scale(.6); }}
            35% {{ opacity: 1; transform: scale(1.15); }}
            100% {{ opacity: 0; transform: scale(1.6); }}
        }}
        </style>
        """
    )

    with st.container(key="country_scene_stage"):
        html_block(
            f"""
            <div class="scene-stage">
                <div class="scene-landmark-bg">{country["landmark"]}</div>
                <div class="scene-doll-box">{doll_svg}</div>
                <div class="scene-sparkle"></div>
            </div>
            """
        )
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            if st.button("💧", key="icn_water", help="기후·수질 정보"):
                st.session_state.active_country_sheet = "water"
                st.rerun()
        with c2:
            if st.button("💄", key="icn_lipstick", help="피부 맞춤 추천"):
                st.session_state.active_country_sheet = "lipstick"
                st.rerun()
        with c3:
            if st.button("🛍️", key="icn_shop", help="드럭스토어"):
                st.session_state.active_country_sheet = "shop"
                st.rerun()
        with c4:
            if st.button("💇", key="icn_hair", help="헤어 케어"):
                st.session_state.active_country_sheet = "hair"
                st.rerun()
        with c5:
            if st.button("🎒", key="icn_carrier", help="캐리어 담기"):
                st.session_state.active_country_sheet = "carrier"
                st.rerun()
        with c6:
            if st.button("⭐", key="icn_star", help="패스포트에 저장"):
                if already_saved:
                    st.toast("📘 이미 패스포트에 저장되어 있어요", icon="📘")
                else:
                    st.session_state.passport.append({
                        "code": code,
                        "name": country["name"],
                        "flag": country["flag"],
                        "tip": country["essentials"][0],
                    })
                    st.session_state.just_saved_country_sparkle = True
                    st.toast("⭐ 패스포트에 저장됨!", icon="⭐")
                st.rerun()

    nav1, nav2 = st.columns(2)
    with nav1:
        if st.button("🗺️ 정보 다시 보기", key="back_to_country_map"):
            st.session_state.country_stage = "map"
            st.rerun()
    with nav2:
        if st.button("⬅ 지도로 돌아가기", key="back_to_world_map_from_scene"):
            goto("map")
            st.rerun()


def _dismiss_country_sheet():
    """다이얼로그 기본 X/ESC/바깥 클릭으로 닫혀도 상태를 꺼준다 — 다른 다이얼로그와 동일한 패턴."""
    st.session_state.active_country_sheet = None


def _bottom_sheet_css():
    html_block(
        """
        <style>
        div[data-testid="stDialog"] [slot="title"] { display: none !important; }
        div[data-testid="stDialog"] div { background: transparent !important; box-shadow: none !important; }
        div[data-testid="stDialog"] > div {
            position: fixed !important; left: 50% !important; bottom: 0 !important; top: auto !important;
            transform: translateX(-50%) !important; margin: 0 !important;
            max-width: min(94vw, 640px) !important; width: min(94vw, 640px) !important;
            max-height: 82vh !important; overflow-y: auto !important;
            border-radius: 22px 22px 0 0 !important;
            animation: sheet-slide-up .28s ease both;
        }
        @keyframes sheet-slide-up {
            from { transform: translate(-50%, 100%); }
            to   { transform: translate(-50%, 0); }
        }
        /* 위 "div[data-testid='stDialog'] div"가 태그 2개짜리라 명시도가
           (0,1,2)라서 클래스 하나뿐인 규칙(0,1,0)로는 못 이긴다 — 뷰티 패스포트의
           .page 규칙과 동일하게 dialog 속성 선택자를 앞에 한 번 더 붙여 명시도를
           (0,2,1)로 올려야 실제로 크림색이 보인다. */
        div[data-testid="stDialog"] .st-key-country_sheet_card {
            background: #fffaf3 !important; border-radius: 22px 22px 0 0 !important;
            padding: 0 !important; box-shadow: 0 -10px 30px rgba(120,40,90,.22) !important;
            min-height: 240px; overflow: hidden;
        }
        /* 여행 컨셉에 맞춰 항공권(보딩패스) 느낌으로 — 색상 헤더(칩 아이콘 + 제목 +
           나라 스탬프) 아래 점선 절취선을 두고, 본문은 그 밑에 붙는 티켓 하단부처럼.
           그라데이션은 아이콘마다 달라서 인라인 style로 못 박을 수 없어 CSS 변수로
           건네받는데, 그 값을 실제로 칠하는 background 선언은 위 카드와 같은 이유로
           dialog 속성 선택자를 붙여 명시도를 올려야 인라인이 아니라 진짜로 먹는다. */
        div[data-testid="stDialog"] .sheet-ticket-header {
            position: relative; padding: 22px 26px 18px; color: #fff;
            border-radius: 22px 22px 0 0;
            display: flex; align-items: center; gap: 14px;
            background: var(--ticket-accent) !important;
        }
        .sheet-ticket-icon {
            font-size: 2.4rem; line-height: 1;
            filter: drop-shadow(0 3px 4px rgba(0,0,0,.28));
        }
        .sheet-ticket-title {
            font-family: 'Gaegu', cursive; font-weight: 700; font-size: 1.42rem;
        }
        .sheet-ticket-sub {
            font-family: 'Jua', sans-serif; font-size: .78rem; opacity: .9;
            letter-spacing: .5px; margin-top: 3px;
        }
        .sheet-ticket-stamp {
            position: absolute; right: 22px; top: 16px; font-size: 1.9rem;
            opacity: .55; transform: rotate(10deg);
            filter: drop-shadow(0 2px 2px rgba(0,0,0,.25));
        }
        .sheet-perf {
            position: relative; height: 0; margin: 0 22px;
            border-top: 3px dashed rgba(255,255,255,.6);
        }
        .sheet-perf::before, .sheet-perf::after {
            content: ''; position: absolute; top: -11px; width: 22px; height: 22px;
            border-radius: 50%; background: #fffaf3;
        }
        .sheet-perf::before { left: -33px; }
        .sheet-perf::after { right: -33px; }
        .sheet-body { padding: 20px 26px 26px; }
        .sheet-title {
            font-family: 'Gaegu', cursive; font-weight: 700; font-size: 1.4rem;
            color: #9c2f5c; margin-bottom: 10px;
        }
        .st-key-close_country_sheet button {
            border-radius: 999px !important; font-family: 'Jua', sans-serif !important;
        }
        </style>
        """
    )


_SHEET_THEME = {
    "water":    {"accent": "linear-gradient(135deg, #3f9fd6 0%, #7cc6ec 100%)", "label": "CLIMATE PASS"},
    "lipstick": {"accent": "linear-gradient(135deg, #ff5fa8 0%, #ff9ecb 100%)", "label": "BEAUTY PASS"},
    "shop":     {"accent": "linear-gradient(135deg, #9b6bdb 0%, #c3a4ec 100%)", "label": "SHOPPING PASS"},
    "hair":     {"accent": "linear-gradient(135deg, #2fb08a 0%, #7fd6b4 100%)", "label": "HAIR CARE PASS"},
    "carrier":  {"accent": "linear-gradient(135deg, #ff9f43 0%, #ffc27a 100%)", "label": "PACKING PASS"},
}


@st.dialog("여행 정보", width="large", on_dismiss=_dismiss_country_sheet)
def _country_action_sheet(country, char, code):
    _bottom_sheet_css()
    kind = st.session_state.active_country_sheet
    icons = {"water": "💧", "lipstick": "💄", "shop": "🛍️", "hair": "💇", "carrier": "🎒"}
    titles = {
        "water": "기후 · 수질 정보",
        "lipstick": "피부 맞춤 추천",
        "shop": "드럭스토어 & 추천템",
        "hair": "헤어 케어",
        "carrier": "캐리어 담기",
    }
    theme = _SHEET_THEME.get(kind, _SHEET_THEME["water"])
    with st.container(key="country_sheet_card"):
        html_block(
            f"""
            <div class="sheet-ticket-header" style="--ticket-accent:{theme['accent']};">
                <div class="sheet-ticket-icon">{icons.get(kind, "✈️")}</div>
                <div>
                    <div class="sheet-ticket-title">{titles.get(kind, "")}</div>
                    <div class="sheet-ticket-sub">{theme['label']} · {html.escape(country['name'])}</div>
                </div>
                <div class="sheet-ticket-stamp">{country['flag']}</div>
            </div>
            <div class="sheet-perf"></div>
            """
        )
        with st.container(key="sheet_body"):
            _render_country_sheet_body(kind, country, char, code)

        if st.button("✕ 닫기", key="close_country_sheet", use_container_width=True):
            st.session_state.active_country_sheet = None
            st.rerun()


def _render_country_sheet_body(kind, country, char, code):
    if kind == "water":
        skin_notes = char.get("skin_type_extra") or []
        if country["water"] == "경수" and skin_notes:
            st.warning(
                f"⚠ {', '.join(skin_notes)} 피부는 이 지역의 경수 때문에 트러블 위험이 높아요. "
                f"저자극 클렌징워터를 꼭 챙기세요."
            )
        st.metric("기후", country["climate"])
        st.metric("습도", country["humidity"])
        st.metric("자외선", country["uv"])
        st.metric("수질", country["water"])
        st.caption(country["water_note"])
        feed_path = country.get("aqi_station") or (
            f"geo:{country['geo']}" if country.get("geo") else None
        )
        aq = get_air_quality(feed_path) if feed_path else None
        if aq and aq.get("aqi") not in (None, "-"):
            try:
                aqi_val = int(aq["aqi"])
                st.metric("미세먼지 (AQI)", f"{aqi_val} · {_aqi_level_label(aqi_val)}")
                pm_parts = []
                if aq.get("pm25") is not None:
                    pm_parts.append(f"PM2.5 {aq['pm25']}㎍/㎥")
                if aq.get("pm10") is not None:
                    pm_parts.append(f"PM10 {aq['pm10']}㎍/㎥")
                if pm_parts:
                    st.caption(" · ".join(pm_parts))
            except (TypeError, ValueError):
                pass

    elif kind == "lipstick":
        with st.spinner("피부 맞춤 추천을 준비하고 있어요..."):
            rec = get_ai_cosmetic_recommendation(char, code)
        if rec:
            st.markdown(rec)
            st.caption("✨ AI가 피부타입과 현지 기후를 분석해 추천했어요")
        else:
            st.caption("AI 추천을 불러오지 못해 기본 추천으로 보여드려요")
            for t in _quick_skin_tip(char, country):
                st.write(f"- {t}")

    elif kind == "shop":
        st.markdown("**🧳 필수 아이템**")
        for item in country["essentials"]:
            st.write(f"- {item}")
        st.markdown("**📍 현지 드럭스토어**")
        cards = get_drugstore_cards(code)
        if cards:
            saved_labels = {
                s["label"] for s in st.session_state.passport_stores if s["code"] == code
            }
            for i, card in enumerate(cards):
                is_saved = card["label"] in saved_labels
                name_col, map_col, star_col = st.columns([5, 2, 1], vertical_alignment="center")
                with name_col:
                    st.write(card["label"])
                with map_col:
                    st.link_button("🗺️ 지도", card["maps_url"], use_container_width=True)
                with star_col:
                    if st.button("💛" if is_saved else "⭐", key=f"save_store_{code}_{i}",
                                 help="뷰티 패스포트에서 빼기" if is_saved else "뷰티 패스포트에 저장"):
                        if is_saved:
                            st.session_state.passport_stores = [
                                s for s in st.session_state.passport_stores
                                if not (s["code"] == code and s["label"] == card["label"])
                            ]
                        else:
                            st.session_state.passport_stores.append({
                                "code": code, "flag": country["flag"],
                                "label": card["label"], "maps_url": card["maps_url"],
                            })
                            st.toast(f"⭐ {card['label']} 저장됨!", icon="⭐")
                        st.rerun()
        else:
            for store in country.get("drugstores") or []:
                st.write(f"- {store}")
        st.markdown("**🧴 내 피부에 맞는 추천**")
        for t in _quick_skin_tip(char, country):
            st.write(f"- {t}")

    elif kind == "hair":
        st.write(country["hair_tip"])
        st.link_button("3WAU에서 추천 제품 보러 가기 →", THREE_WAU_STORE_URL, use_container_width=True)

    elif kind == "carrier":
        st.info("🧳 캐리어 담기 서비스는 준비 중이에요! 조금만 기다려주세요 ✨")


def render_aftercare():
    st.title("💧 애프터케어")
    st.caption("여행 후 피부 상태에 맞는 케어 루틴을 확인하세요")
    profile = get_skin_profile(get_character())
    symptom_options = list(AFTERCARE_ADVICE.keys())
    if "트러블" in profile["extras"]:
        default_symptom = "트러블"
    elif profile["skin_type"] == "건성":
        default_symptom = "건조"
    else:
        default_symptom = symptom_options[0]
    default_index = symptom_options.index(default_symptom) if default_symptom in symptom_options else 0
    symptom = st.selectbox("지금 피부 상태는 어떤가요?", symptom_options, index=default_index)
    if st.button("케어 루틴 보기", type="primary"):
        advice = AFTERCARE_ADVICE[symptom]
        st.subheader(f"추천 팩: {advice['pack']}")
        st.markdown("**케어 루틴**")
        for i, step in enumerate(advice["routine"], 1):
            st.write(f"{i}. {step}")


# ----------------------------------------------------------------------
# 피부 궁합 진단 — 국가를 최종 선택하기 전에 들어가는 진단 단계.
# select(도시 고르기) -> brewing(포션 진행 애니메이션) -> result(궁합 스코어)
# 3단계를 diagnosis_stage로 관리한다. MVP는 서울/상하이/시드니 3개 도시만.
# ----------------------------------------------------------------------
DIAGNOSIS_MVP_CODES = ["kr", "cn", "au"]


def render_diagnosis():
    if not get_character():
        goto("character")
        st.rerun()
        return
    stage = st.session_state.diagnosis_stage
    if stage == "brewing":
        _render_diagnosis_brewing()
    elif stage == "result":
        _render_diagnosis_result()
    else:
        _render_diagnosis_select()


def _render_diagnosis_select():
    st.title("🧪 피부 궁합 진단")
    html_block(
        """
        <style>
        .diag-copy {
            text-align: center; font-family: 'Jua', sans-serif; font-size: 1.35rem;
            color: #5a3d7a; margin: 4px 0 20px;
        }
        .diag-city-card {
            aspect-ratio: 1; border-radius: 16px; background: #ffffff;
            display: flex; align-items: center; justify-content: center;
            font-size: 2.6rem; box-shadow: 0 3px 8px rgba(0,0,0,.1);
        }
        .diag-brew-hint {
            text-align: center; font-family: 'Jua', sans-serif; color: #8a5a10; margin-top: -2px;
        }
        </style>
        <div class="diag-copy">내 피부, 어디랑 잘 맞을까? 🔮</div>
        """
    )

    selected = st.session_state.diagnosis_country
    cols = st.columns(len(DIAGNOSIS_MVP_CODES))
    for col, code in zip(cols, DIAGNOSIS_MVP_CODES):
        country = COUNTRIES[code]
        with col:
            is_sel = selected == code
            border = "4px solid #ff6fb8" if is_sel else "3px solid rgba(0,0,0,.08)"
            html_block(f'<div class="diag-city-card" style="border:{border};">{country["flag"]}</div>')
            if st.button(country["name"], key=f"diag_pick_{code}", use_container_width=True):
                st.session_state.diagnosis_country = None if is_sel else code
                st.rerun()

    if selected:
        html_block(
            f"""
            <style>
            .st-key-diag_brew_btn.st-key-diag_brew_btn button {{
                position: relative !important;
                width: 140px !important; height: 182px !important; margin: 18px auto 4px !important;
                display: block !important; background: transparent !important; border: none !important;
                background-image: url('{POTION_ICON_URI}') !important;
                background-size: contain !important; background-repeat: no-repeat !important;
                background-position: center !important;
                color: transparent !important; font-size: 0 !important;
                transition: transform .15s ease;
            }}
            .st-key-diag_brew_btn.st-key-diag_brew_btn button:hover {{ transform: scale(1.06) translateY(-3px); }}
            .st-key-diag_brew_btn.st-key-diag_brew_btn button:active {{ transform: scale(.93); }}
            </style>
            """
        )
        if st.button(" ", key="diag_brew_btn"):
            st.session_state.diagnosis_stage = "brewing"
            st.rerun()
        html_block('<div class="diag-brew-hint">🧪 포션을 눌러 궁합을 확인해보세요</div>')


def _render_diagnosis_brewing():
    code = st.session_state.diagnosis_country
    country = COUNTRIES.get(code) or {}
    st.title("🧪 피부 궁합 진단")
    html_block(
        f"""
        <style>
        @keyframes potion-shake {{
            0%,100% {{ transform: rotate(0deg); }}
            25%     {{ transform: rotate(-6deg); }}
            75%     {{ transform: rotate(6deg); }}
        }}
        .diag-potion-shake {{ display: inline-block; width: 140px; animation: potion-shake .5s ease-in-out infinite; }}
        .diag-brewing {{ text-align: center; padding: 20px 0 6px; }}
        .diag-brewing-label {{
            font-family: 'Jua', sans-serif; font-size: 1.1rem; color: #5a3d7a; margin-top: 10px;
        }}
        </style>
        <div class="diag-brewing">
            <div class="diag-potion-shake">{POTION_ICON_SVG}</div>
            <div class="diag-brewing-label">{country.get("flag","")} {country.get("name","")}와의 궁합을 확인하는 중...</div>
        </div>
        """
    )

    bar = st.progress(0)
    pct_slot = st.empty()
    steps = 25
    for i in range(steps + 1):
        pct = int(i / steps * 100)
        bar.progress(pct / 100)
        pct_slot.markdown(
            f'<div style="text-align:center;font-family:\'Jua\',sans-serif;font-size:1.7rem;'
            f'color:#ff6fb8;">{pct}%</div>',
            unsafe_allow_html=True,
        )
        time.sleep(0.1)  # steps=25 x 0.1s = 총 2.5초

    st.session_state.diagnosis_stage = "result"
    st.rerun()


def _render_diagnosis_result():
    code = st.session_state.diagnosis_country
    country = COUNTRIES.get(code)
    char = get_character()
    if not country:
        st.session_state.diagnosis_stage = "select"
        st.rerun()
        return

    env = get_destination_environment_data(code)
    profile = get_skin_profile(char)
    cached = st.session_state.diagnosis_result
    if not cached or cached.get("code") != code:
        scores = calculate_skin_compatibility(profile, env)
        st.session_state.diagnosis_result = {"code": code, **scores}
    result = st.session_state.diagnosis_result
    overall = result["overall"]
    band = _compatibility_band(overall)

    st.title(f"{country['flag']} {country['name']}")

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=overall,
        number={"suffix": "%", "font": {"size": 42}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": band["color"], "thickness": 0.28},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 50], "color": "#fdeaea"},
                {"range": [50, 80], "color": "#fff6e0"},
                {"range": [80, 100], "color": "#e6f8ee"},
            ],
        },
    ))
    fig.update_layout(
        height=240, margin=dict(l=20, r=20, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", font={"family": "sans-serif"},
    )
    st.plotly_chart(fig, use_container_width=True)

    html_block(
        f'<div style="text-align:center;font-family:\'Jua\',sans-serif;font-size:1.4rem;'
        f'color:{band["color"]};margin:-6px 0 18px;">{html.escape(band["text"])}</div>'
    )

    cards = [
        ("🌡️", "기후 궁합", result["climate"], "climate"),
        ("☀️", "자외선 궁합", result["uv"], "uv"),
        ("💧", "물 궁합", result["water"], "water"),
    ]
    cols = st.columns(3)
    for col, (emoji, label, score, kind) in zip(cols, cards):
        with col:
            line = _compat_card_line(kind, score, env, profile)
            html_block(
                f"""
                <div style="background:#fff;border-radius:16px;padding:16px 12px;
                     text-align:center;box-shadow:0 4px 10px rgba(0,0,0,.08);height:100%;
                     box-sizing:border-box;">
                    <div style="font-size:1.8rem;">{emoji}</div>
                    <div style="font-family:'Jua',sans-serif;font-weight:700;margin:6px 0;">{label}</div>
                    <div style="font-family:'Jua',sans-serif;font-size:1.3rem;color:{band["color"]};">{score}%</div>
                    <div style="font-size:.82rem;color:#666;margin-top:6px;line-height:1.4;">{html.escape(line)}</div>
                </div>
                """
            )

    st.write("")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("그래도 갈래요 → 준비물 보기", key="diag_go_country", type="primary", use_container_width=True):
            st.session_state.selected_country = code
            st.session_state.country_stage = "map"
            st.session_state.active_country_sheet = None
            goto("country")
            st.rerun()
    with b2:
        if st.button("다른 나라 볼래요", key="diag_pick_other", use_container_width=True):
            st.session_state.diagnosis_country = None
            st.session_state.diagnosis_result = None
            st.session_state.diagnosis_stage = "select"
            st.rerun()

    already_saved = code in [p["code"] for p in get_passport()]
    if st.button("⭐ 궁합 결과 저장", key="diag_save_passport", use_container_width=True):
        if already_saved:
            st.toast("📘 이미 패스포트에 저장되어 있어요", icon="📘")
        else:
            st.session_state.passport.append({
                "code": code, "name": country["name"], "flag": country["flag"],
                "tip": country["essentials"][0], "compat_score": overall,
            })
            st.toast("⭐ 패스포트에 저장됨!", icon="⭐")
        st.rerun()


# ----------------------------------------------------------------------
# 사이드바는 어떤 화면에서도 쓰지 않는다 — 대신 우상단 아이콘(지도/애프터케어/
# 뷰티 패스포트)과 뒤로가기 버튼으로 내비게이션한다.
# ----------------------------------------------------------------------
st.markdown(
    '<style>section[data-testid="stSidebar"], div[data-testid="stSidebarCollapsedControl"] '
    "{ display: none !important; } </style>",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# 화면 라우팅
# ----------------------------------------------------------------------
inject_theme()

VIEWS = {
    "home": render_home,
    "character": render_character,
    "closet": render_closet,
    "map": render_map,
    "country": render_country,
    "aftercare": render_aftercare,
    "diagnosis": render_diagnosis,
}
render_bubble_clear()
render_passport_modal()
render_back_button()
render_top_icons()

# 화면(view)을 st.empty() 슬롯 하나에 넣어서 그린다. 예전에는 VIEWS[...]()를
# 바로 호출했는데, 캐릭터 만들기(탭+위젯이 아주 많음)에서 지도(위젯이 훨씬
# 적음)처럼 화면 크기가 크게 차이나는 화면으로 넘어갈 때 이전 화면의 일부
# 요소가 안 지워지고 새 화면과 뒤섞여 남는 버그가 실제 브라우저에서 확인됐다
# (Streamlit이 재실행 사이에 "안 쓰는 만큼 지우기"를 완전히 못 하는 것으로
# 보임). st.empty()는 그 자리에 새로 그리면 이전 내용을 확실히 통째로 비우고
# 다시 그리도록 설계된 API라 이 문제를 원천적으로 피할 수 있다.
_view_slot = st.empty()
with _view_slot.container():
    VIEWS.get(st.session_state.view, render_home)()
