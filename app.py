"""
식스센스 TravelMax+
여행지 기후·수질·자외선 데이터를 내 피부 타입과 매칭해주는
게임풍 여행 뷰티 케어 웹앱 MVP
"""
import base64
import html
import json
import math
import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote as urlquote

import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from io import BytesIO
from PIL import Image, ImageFilter, ImageStat

try:
    import anthropic
except ImportError:
    anthropic = None

WAQI_TOKEN = st.secrets.get("WAQI_TOKEN", "")
ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")
OPENWEATHER_API_KEY = st.secrets.get("OPENWEATHER_API_KEY", "")

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
        "flag": "🇯🇵",
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
        "essentials": ["가벼운 젤 타입 자외선 차단제", "여름철 유분 조절 클렌징폼", "쿨링 미스트",
                       "저자극 폼클렌저", "산뜻한 토너 패드", "가벼운 수분 로션"],
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
        "essentials": ["고보습 크림", "미셀라 클렌징워터 (헹굼 불필요)", "립밤·핸드크림",
                       "고보습 세럼", "저자극 클렌징 밀크", "겨울용 페이스 오일"],
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
        "essentials": ["고자차 선크림 (SPF50+/PA++++)", "가벼운 워터 젤 로션", "쿨링 시트팩",
                       "쿨링 바디 미스트", "유분 흡수 파우더", "저자극 폼클렌저"],
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
        "essentials": ["고보습 앰플", "미네랄 워터 미스트", "고자차 선크림",
                       "고보습 립밤", "진정 수딩젤", "쿨링 아이패치"],
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
        "essentials": ["고영양 크림", "바람막이용 페이스 오일", "립밤",
                       "저자극 수분크림", "핸드크림", "진정 미스트"],
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
        "essentials": ["데일리 선크림", "안티옥시던트 세럼", "샤워 필터(장기체류시)",
                       "고보습 크림", "저자극 클렌저", "립밤"],
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
        "essentials": ["고자차 선크림 (SPF50+/PA++++)", "애프터선 케어 젤", "쿨링 미스트",
                       "비타민C 세럼", "저자극 수딩크림", "핸드크림"],
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
        "essentials": ["유분 조절 클렌징폼", "가벼운 워터 젤 선크림", "제습 헤어 에센스",
                       "저자극 토너", "쿨링 시트마스크", "핸드크림"],
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
        "essentials": ["미세먼지 딥클렌징폼", "환절기 보습 크림", "데일리 선크림",
                       "저자극 진정 토너", "비타민C 세럼", "쿨링 아이크림"],
        "trouble": "환절기 급격한 건조·미세먼지로 인한 트러블",
        "hair_tip": "미세먼지 케어 헤어 클렌저",
        "drugstores": ["올리브영 명동점", "롭스 홍대점", "다이소 강남점"],
    },
}

# 무료로 바로 열려 있는 여행지(호주/일본/중국/한국/미국). 나머지는 기본 잠금 —
# 코인으로 해제하면 st.session_state.unlocked_countries에 코드가 쌓인다.
FREE_COUNTRY_CODES = {"au", "jp", "cn", "kr", "us"}
UNLOCK_COST_COINS = 50

# 옷장/액세서리 각 카테고리의 첫 번째 아이템(항상 화이트 계열, _build_catalog가
# COLOR_PALETTE_10 순서대로 만들어서 인덱스 0 = 화이트)만 무료 — 나머지 9개는
# 코인으로 해제. st.session_state.unlocked_closet_items에 해제한 item id가 쌓인다
# (id가 카테고리별 prefix로 이미 전역에서 고유해서 카테고리 구분 없이 하나의
# set으로 관리해도 된다).
CLOSET_UNLOCK_COST_COINS = 20


def is_country_unlocked(code):
    return code in FREE_COUNTRY_CODES or code in st.session_state.unlocked_countries


def is_closet_item_unlocked(item_id, index):
    return index == 0 or item_id in st.session_state.unlocked_closet_items


# 기내 액체류 반입 규정 — 캐리어 담기 서비스에서 쓰는 판정 기준.
# 개별 용기는 100ml 이하만, 전체 합은 1L(1000ml) 이하만 반입 가능하다는
# 실제 국제 항공 보안 규정(투명 지퍼백 규정)을 그대로 반영한 상수.
LIQUID_CONTAINER_LIMIT_ML = 100
LIQUID_TOTAL_LIMIT_ML = 1000
CARRIER_VOLUME_PRESETS = [30, 50, 100]


def _judge_liquid_item(volume_ml):
    """개별 용기 하나의 반입 가능 여부를 판정한다. (allowed, 사유) 튜플을 반환."""
    if volume_ml <= 0:
        return False, "용량을 입력해주세요"
    if volume_ml > LIQUID_CONTAINER_LIMIT_ML:
        return False, f"개별 용기 {LIQUID_CONTAINER_LIMIT_ML}ml 초과라 기내 반입이 불가해요"
    return True, "개별 용기 100ml 이하로 반입 가능해요"


def _add_carrier_item(name, volume_ml):
    allowed, reason = _judge_liquid_item(volume_ml)
    st.session_state.carrier_items.append(
        {"name": name, "volume_ml": volume_ml, "allowed": allowed, "reason": reason}
    )
    st.toast("✅ 반입 가능! 캐리어에 담았어요" if allowed else f"❌ 반입 불가: {reason}")


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
# 국가별 실제 판매 제품 큐레이션 — 구매본부에서 선정한 실제 세포라 판매 제품
# (호주 세포라 기준, 26.7.10 자료). 피부 맞춤 추천(💄 아이콘)에서 이 표가 있는
# 나라는 반드시 이 목록 "안에서만" 골라 추천한다 — 이름/브랜드/성분을 새로
# 지어내지 않는다. good_for/good_for_extras는 각 제품 공식 페이지의 성분·설명을
# 조사해서 매긴 태그이고, fragrance_free=False인 제품은 향료 알러젠이 포함돼
# 있어(체리블라썸 크림, 비타 토닝 크림) 민감성 사용자에겐 추천하지 않는다.
# 이미지는 assets/au_products/에 저장한 실제 제품 사진(브랜드 공식/입점몰 출처).
# ----------------------------------------------------------------------
AU_PRODUCT_CATALOG = [
    {"id": "au01", "brand": "Anua", "name": "하트리프 77 수딩 토너", "category": "토너",
     "image": "au_products/au01_heartleaf_toner.png",
     "url": "https://www.sephora.com.au/products/anua-heartleaf-77-soothing-toner",
     "key_ingredients": ["하트리프(어성초) 77%", "판테놀", "병풀추출물"],
     "good_for": ["건성", "지성", "복합성"], "good_for_extras": ["민감성", "트러블"],
     "fragrance_free": True,
     "description": "약산성 진정 토너 — 자극받고 예민해진 피부를 가라앉히고 수분을 채워줘요."},
    {"id": "au02", "brand": "Anua", "name": "라이스 70 글로우 밀키 토너", "category": "토너",
     "image": "au_products/au02_rice_milky_toner.png",
     "url": "https://www.sephora.com.au/products/anua-rice-70-glow-milky-toner",
     "key_ingredients": ["라이스브랜워터 70%", "나이아신아마이드", "세라마이드"],
     "good_for": ["건성", "지성", "복합성"], "good_for_extras": [],
     "fragrance_free": True,
     "description": "가벼운 밀키 토너 — 유수분 밸런스를 잡아주면서 은은한 광채를 더해줘요."},
    {"id": "au03", "brand": "Innisfree", "name": "볼캐닉 PHA 포어 리파이닝 토너", "category": "토너",
     "image": "au_products/au03_volcanic_pha_toner.png",
     "url": "https://www.sephora.com.au/products/innisfree-volcanic-pha-pore-refining-toner",
     "key_ingredients": ["화산송이 파우더", "PHA(글루코노락톤)", "아르기닌"],
     "good_for": ["지성", "복합성"], "good_for_extras": [],
     "fragrance_free": True,
     "description": "저자극 PHA로 묵은 각질과 모공 속 노폐물을 부드럽게 정돈해줘요."},
    {"id": "au04", "brand": "Innisfree", "name": "그린티 엔자임 비타민C 브라이트닝 토너 패드", "category": "토너",
     "image": "au_products/au04_greentea_vitc_pads.png",
     "url": "https://www.sephora.com.au/products/innisfree-green-tea-enzyme-vitamin-c-brightening-toner-pads",
     "key_ingredients": ["나이아신아마이드", "비타민C(마그네슘아스코빌포스페이트)", "마데카소사이드"],
     "good_for": ["건성", "지성", "복합성"], "good_for_extras": ["민감성"],
     "fragrance_free": True,
     "description": "패드 타입 브라이트닝 토너 — 칙칙해진 톤을 환하게 정돈하는 데 도움을 줘요."},
    {"id": "au05", "brand": "Anua", "name": "PDRN 히알루론산 캡슐 100 세럼", "category": "세럼",
     "image": "au_products/au05_pdrn_capsule_serum.png",
     "url": "https://www.sephora.com.au/products/anua-pdrn-hyaluronic-acid-capsule-100-serum",
     "key_ingredients": ["PDRN", "히알루론산 11종 복합", "판테놀"],
     "good_for": ["건성", "복합성"], "good_for_extras": ["민감성", "트러블"],
     "fragrance_free": True,
     "description": "PDRN과 다중 히알루론산으로 속부터 촉촉하게 채워 물광 피부를 만들어줘요."},
    {"id": "au06", "brand": "Anua", "name": "나이아신아마이드 10 TXA 3 세럼", "category": "세럼",
     "image": "au_products/au06_niacinamide_txa_serum.png",
     "url": "https://www.sephora.com.au/products/anua-niacinamide-10-txa-3-serum",
     "key_ingredients": ["나이아신아마이드 10%", "트라넥사믹애씨드(TXA) 3%", "병풀추출물"],
     "good_for": ["건성", "지성", "복합성"], "good_for_extras": ["민감성", "트러블"],
     "fragrance_free": True,
     "description": "자외선 자극 후 남는 색소침착·잡티를 톤업하는 데 도움을 줘요 — 여행 중 트러블 흔적 케어에 좋아요."},
    {"id": "au07", "brand": "Innisfree", "name": "그린티 세라마이드 밀크 배리어 에센스", "category": "에센스",
     "image": "au_products/au07_greentea_ceramide_essence.png",
     "url": "https://www.sephora.com.au/products/innisfree-green-tea-ceramide-milk-barrier-essence",
     "key_ingredients": ["세라마이드NP", "그린티추출물", "나이아신아마이드"],
     "good_for": ["건성", "지성", "복합성"], "good_for_extras": ["민감성", "트러블"],
     "fragrance_free": True,
     "description": "토너·에센스·로션 3-in-1 — 손상되기 쉬운 피부 장벽을 채워주는 데 도움을 줘요."},
    {"id": "au08", "brand": "d'Alba", "name": "화이트 트러플 더블 레이어 리바이탈라이징 세럼", "category": "세럼",
     "image": "au_products/au08_truffle_double_serum.png",
     "url": "https://www.sephora.com.au/products/dalba-white-truffle-double-layer-revitalizing-serum",
     "key_ingredients": ["화이트 트러플추출물", "나이아신아마이드", "아데노신"],
     "good_for": ["건성", "복합성"], "good_for_extras": [],
     "fragrance_free": False,
     "description": "세럼+오일 더블 레이어 — 탄력과 광채를 더해주는 안티에이징 세럼이에요."},
    {"id": "au09", "brand": "Anua", "name": "PDRN 히알루론산 100 모이스처라이징 크림", "category": "크림",
     "image": "au_products/au09_pdrn_cream.png",
     "url": "https://www.sephora.com.au/products/anua-pdrn-hyaluronic-acid-100-moisturizing-cream",
     "key_ingredients": ["PDRN", "히알루론산 복합", "스쿠알란"],
     "good_for": ["건성", "복합성"], "good_for_extras": ["민감성"],
     "fragrance_free": True,
     "description": "장시간 지속되는 고보습 크림 — 건조해지기 쉬운 여행지에서 장벽 케어에 좋아요."},
    {"id": "au10", "brand": "Innisfree", "name": "그린티 시드 히알루론 크림", "category": "크림",
     "image": "au_products/au10_greentea_seed_cream.png",
     "url": "https://www.sephora.com.au/products/innisfree-green-tea-seed-hyaluronic-cream",
     "key_ingredients": ["그린티시드오일", "히알루론산", "세라마이드NP"],
     "good_for": ["건성", "복합성"], "good_for_extras": ["민감성", "트러블"],
     "fragrance_free": True,
     "description": "건조하고 결이 무너진 피부에 수분과 장벽 케어를 더해주는 데일리 크림이에요."},
    {"id": "au11", "brand": "Innisfree", "name": "체리블라썸 글로우 젤리 크림", "category": "크림",
     "image": "au_products/au11_cherryblossom_cream.png",
     "url": "https://www.sephora.com.au/products/innisfree-cherry-blossom-glow-jelly-cream",
     "key_ingredients": ["체리블라썸(벚꽃)추출물", "나이아신아마이드", "베타인"],
     "good_for": ["지성", "복합성"], "good_for_extras": [],
     "fragrance_free": False,
     "description": "산뜻한 젤리 텍스처로 톤업과 수분감을 동시에 — 가볍게 바르는 브라이트닝 크림이에요."},
    {"id": "au12", "brand": "d'Alba", "name": "비타 토닝 캡슐 크림", "category": "크림",
     "image": "au_products/au12_vita_toning_cream.png",
     "url": "https://www.sephora.com.au/products/dalba-vita-toning-capsule-cream",
     "key_ingredients": ["화이트트러플·비타민C 복합", "나이아신아마이드", "아데노신"],
     "good_for": ["건성", "지성", "복합성"], "good_for_extras": [],
     "fragrance_free": False,
     "description": "캡슐+크림 듀얼 텍스처 — 칙칙한 톤과 잔주름 케어를 동시에 잡아주는 크림이에요."},
    {"id": "au13", "brand": "Anua", "name": "라이스 70 인텐시브 모이스처라이징 밀크", "category": "로션",
     "image": "au_products/au13_rice_milk_lotion.png",
     "url": "https://www.sephora.com.au/products/anua-rice-70-intensive-moisturizing-milk",
     "key_ingredients": ["라이스브랜워터 70%", "세라마이드 복합", "아데노신"],
     "good_for": ["건성", "지성", "복합성"], "good_for_extras": ["민감성"],
     "fragrance_free": True,
     "description": "가볍게 흡수되는 로션 — 칙칙함 없이 촉촉한 유광 피부로 정돈해줘요."},
    {"id": "au14", "brand": "d'Alba", "name": "더블 세럼 올인원 멀티밤", "category": "로션",
     "image": "au_products/au14_multibalm.png",
     "url": "https://www.sephora.com.au/products/dalba-double-serum-all-in-one-multi-balm",
     "key_ingredients": ["비건 콜라겐", "세라마이드", "화이트트러플·비타민C"],
     "good_for": ["건성", "지성", "복합성"], "good_for_extras": ["민감성", "트러블"],
     "fragrance_free": True,
     "description": "저자극 올인원 멀티밤 — 로션 대신 얼굴 전체에 가볍게 겹겹이 발라도 좋아요."},
]

# ----------------------------------------------------------------------
# 중국 큐레이션 제품 (구매본부 자료, 26.7.10). 세포라 호주 자료와 달리 제품별
# 구매 URL이 없고 브랜드별 유통 채널(공식몰/왓슨스/도우인 등)만 있어서, 각
# 제품에 "url" 대신 "store_note"를 둔다 — 렌더링 쪽에서 url이 없으면 링크
# 버튼 대신 이 채널 안내를 캡션으로 보여준다. 완미(玛丽艳)·완미日记(Perfect
# Diary)는 일반 매장/세포라·왓슨스에 없다는 원자료의 경고를 store_note에
# 그대로 남겨서 사용자가 오인하지 않게 한다. 이미지는 원본 PDF에서 직접
# 추출한 실제 제품 사진(assets/cn_products/).
# ----------------------------------------------------------------------
CN_PRODUCT_CATALOG = [
    {"id": "cn01", "brand": "Chando(자연당)", "name": "히말라야 빙하 보습 토너", "category": "토너",
     "image": "cn_products/cn01_chando_himalaya_toner.png", "url": None,
     "store_note": "왓슨스(중국)·苏宁易购·백화점 CS매장·도우인 라이브커머스 — 중국 내 오프라인 접근성 가장 좋음",
     "key_ingredients": ["히말라야 빙하수"], "good_for": ["건성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "히말라야 빙하수로 산뜻하게 수분을 채워주는 토너예요."},
    {"id": "cn02", "brand": "Chando(자연당)", "name": "미니 퍼플보틀 리페어 에센스 (7세대)", "category": "세럼",
     "image": "cn_products/cn02_chando_purple_essence.png", "url": None,
     "store_note": "왓슨스(중국)·苏宁易购·백화점 CS매장·도우인 라이브커머스",
     "key_ingredients": ["기원 리페어 복합 성분"], "good_for": ["건성", "지성", "복합성"], "good_for_extras": ["트러블"],
     "fragrance_free": None,
     "description": "지친 피부 장벽을 회복하는 데 도움을 주는 리페어 에센스예요."},
    {"id": "cn03", "brand": "Chando(자연당)", "name": "백금 콜라겐 리페어 크림", "category": "크림",
     "image": "cn_products/cn03_chando_collagen_cream.png", "url": None,
     "store_note": "왓슨스(중국)·苏宁易购·백화점 CS매장·도우인 라이브커머스",
     "key_ingredients": ["콜라겐"], "good_for": ["건성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "콜라겐 성분으로 탄력과 리프팅감을 더해주는 크림이에요."},
    {"id": "cn04", "brand": "Chando(자연당)", "name": "실크 선크림 (가벼운 워터리 타입)", "category": "선크림",
     "image": "cn_products/cn04_chando_sunscreen.png", "url": None,
     "store_note": "왓슨스(중국)·苏宁易购·백화점 CS매장·도우인 라이브커머스",
     "key_ingredients": [], "good_for": ["건성", "지성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "가볍고 산뜻하게 발리는 데일리 선크림이에요."},
    {"id": "cn05", "brand": "Chando(자연당)", "name": "쥬송 안티에이징 여행용 4종 세트", "category": "기타",
     "image": "cn_products/cn05_chando_travel_set.png", "url": None,
     "store_note": "왓슨스(중국)·苏宁易购·백화점 CS매장·도우인 라이브커머스",
     "key_ingredients": ["쥬송(시더) 오일"], "good_for": ["건성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "토너·세럼·크림·아이크림 4종 여행용 세트 — 안티에이징 라인을 한 번에 체험해볼 수 있어요."},
    {"id": "cn06", "brand": "Marie Anne(완미)", "name": "자윤 토너", "category": "토너",
     "image": "cn_products/cn06_marieanne_toner.png", "url": None,
     "store_note": "⚠ 완미 공식몰에서만 구매 가능 — 일반 매장 판매 없음",
     "key_ingredients": [], "good_for": ["건성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "촉촉하게 결을 정돈해주는 자윤 토너예요."},
    {"id": "cn07", "brand": "Marie Anne(완미)", "name": "딥 모이스처 데이크림", "category": "크림",
     "image": "cn_products/cn07_marieanne_daycream.png", "url": None,
     "store_note": "⚠ 완미 공식몰에서만 구매 가능 — 일반 매장 판매 없음",
     "key_ingredients": [], "good_for": ["건성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "낮 동안 깊은 보습감을 유지해주는 데이크림이에요."},
    {"id": "cn08", "brand": "Marie Anne(완미)", "name": "화이트닝 클리어 선크림", "category": "선크림",
     "image": "cn_products/cn08_marieanne_sunscreen.png", "url": None,
     "store_note": "⚠ 완미 공식몰에서만 구매 가능 — 일반 매장 판매 없음",
     "key_ingredients": [], "good_for": ["건성", "지성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "화이트닝 케어와 자외선 차단을 함께 챙기는 선크림이에요."},
    {"id": "cn09", "brand": "Perfect Diary(완미日记)", "name": "메이크업 전 보습 프라이머 크림", "category": "크림",
     "image": "cn_products/cn09_perfectdiary_primer_cream.png", "url": None,
     "store_note": "⚠ 세포라·왓슨스 미입점 — 자체 브랜드 매장/온라인몰에서만 구매 가능",
     "key_ingredients": [], "good_for": ["지성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "메이크업 전 산뜻하게 보습해주는 프라이머 크림이에요."},
    {"id": "cn10", "brand": "Perfect Diary(완미日记)", "name": "청량 선크림 SPF50 (여름용)", "category": "선크림",
     "image": "cn_products/cn10_perfectdiary_sunscreen.png", "url": None,
     "store_note": "⚠ 세포라·왓슨스 미입점 — 자체 브랜드 매장/온라인몰에서만 구매 가능",
     "key_ingredients": [], "good_for": ["지성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "끈적임 없이 산뜻한 여름용 고자차 선크림이에요."},
    {"id": "cn11", "brand": "Perfect Diary(완미日记)", "name": "「방생막」 정화 립스틱", "category": "기타",
     "image": "cn_products/cn11_perfectdiary_lipstick.png", "url": None,
     "store_note": "⚠ 세포라·왓슨스 미입점 — 자체 브랜드 매장/온라인몰에서만 구매 가능",
     "key_ingredients": [], "good_for": ["건성", "지성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "촉촉한 발림감의 틴트 립스틱 — 색조로 산뜻한 포인트를 더해줘요."},
    {"id": "cn12", "brand": "OLEVA(오로페이)", "name": "수분 정수 토너 (습포용)", "category": "토너",
     "image": "cn_products/cn12_oleva_toner.png", "url": "https://www.sephora.cn",
     "store_note": "세포라 차이나(프리미엄 라인)·백화점 매장·CS전문점·天猫/JD 온라인몰",
     "key_ingredients": [], "good_for": ["건성", "복합성"], "good_for_extras": ["민감성"],
     "fragrance_free": None,
     "description": "촉촉한 습포 타입으로 결을 가라앉혀주는 정수 토너예요."},
    {"id": "cn13", "brand": "OLEVA(오로페이)", "name": "임팩트 부스팅 에센스", "category": "세럼",
     "image": "cn_products/cn13_oleva_essence.png", "url": "https://www.sephora.cn",
     "store_note": "세포라 차이나·백화점 매장·CS전문점·天猫/JD 온라인몰",
     "key_ingredients": [], "good_for": ["건성", "지성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "생기와 활력을 더해주는 부스팅 에센스예요."},
    {"id": "cn14", "brand": "OLEVA(오로페이)", "name": "스킨 어피니티 모이스처라이징 크림", "category": "크림",
     "image": "cn_products/cn14_oleva_cream.png", "url": "https://www.sephora.cn",
     "store_note": "세포라 차이나·백화점 매장·CS전문점·天猫/JD 온라인몰",
     "key_ingredients": [], "good_for": ["건성", "복합성"], "good_for_extras": ["민감성"],
     "fragrance_free": None,
     "description": "피부 친화적인 저자극 포뮬러로 촉촉함을 채워주는 크림이에요."},
    {"id": "cn15", "brand": "OLEVA(오로페이)", "name": "라이트 텍스처 무자극 선크림", "category": "선크림",
     "image": "cn_products/cn15_oleva_sunscreen.png", "url": "https://www.sephora.cn",
     "store_note": "세포라 차이나·백화점 매장·CS전문점·天猫/JD 온라인몰",
     "key_ingredients": [], "good_for": ["지성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "SPF50+/PA+++ 가벼운 텍스처로 부담 없이 매일 바를 수 있는 선크림이에요."},
    {"id": "cn16", "brand": "OLEVA(오로페이)", "name": "금윤 안티에이징 아이크림", "category": "기타",
     "image": "cn_products/cn16_oleva_eyecream.png", "url": "https://www.sephora.cn",
     "store_note": "세포라 차이나·백화점 매장·CS전문점·天猫/JD 온라인몰",
     "key_ingredients": [], "good_for": ["건성", "복합성"], "good_for_extras": [],
     "fragrance_free": None,
     "description": "눈가 주름과 탄력을 케어해주는 안티에이징 아이크림이에요."},
]

# 큐레이션 카탈로그가 있는 나라만 등록 — 국가 추가 시 이 표에 한 줄만 추가하면
# get_curated_product_recommendation()이 자동으로 그 나라 페이지에서만 동작한다.
COUNTRY_PRODUCT_CATALOGS = {
    "au": AU_PRODUCT_CATALOG,
    "cn": CN_PRODUCT_CATALOG,
}


def _curated_catalog_prompt_block(catalog):
    lines = []
    for p in catalog:
        lines.append(
            f"- id:{p['id']} | {p['brand']} {p['name']} ({p['category']}) | "
            f"성분: {', '.join(p['key_ingredients'])} | 적합 피부타입: {', '.join(p['good_for']) or '전체'} | "
            f"적합 특이사항: {', '.join(p['good_for_extras']) or '해당없음'} | "
            f"무향(fragrance-free): {'예' if p['fragrance_free'] else '아니오'}"
        )
    return "\n".join(lines)


@st.cache_data(show_spinner=False, ttl=86400)
def _cached_curated_product_recommendation(skin_type, extras_key, prefs_key, country_code):
    catalog = COUNTRY_PRODUCT_CATALOGS[country_code]
    country = COUNTRIES[country_code]
    prompt = (
        "너는 여행 뷰티 코디네이터야. 아래는 이 여행지에서 실제로 판매 중인 스킨케어 "
        "제품 목록이야. 이 목록 '안에서만' 여행자의 피부타입/특이사항/선호와 이 여행지 "
        "기후에 가장 잘 맞는 제품을 정확히 3개 골라줘. 목록에 없는 제품/브랜드/성분을 "
        "새로 지어내면 안 돼.\n\n"
        f"[제품 목록]\n{_curated_catalog_prompt_block(catalog)}\n\n"
        f"[여행자] 피부타입: {skin_type} / 피부 특이사항: {', '.join(extras_key) or '없음'} / "
        f"선호 화장품 특성: {', '.join(prefs_key) or '없음'}\n"
        f"[목적지 기후] {country['name']} — {country['climate']} / 자외선: {country['uv']} / "
        f"수질: {country['water']} ({country['water_note']})\n\n"
        '다른 설명 없이 순수 JSON 배열만 출력해: [{"id":"au01","reason":"추천 이유 한 문장"}, ...] '
        "reason은 한국어로, 왜 이 여행자 피부와 이 여행지에 맞는지 한 문장으로 써."
    )
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def _rule_based_curated_picks(catalog, skin_type, extras):
    """AI를 못 쓰거나 실패했을 때의 대체 로직 — 같은 카탈로그 안에서 점수로 고른다.
    민감성인데 향료가 든 제품(fragrance_free=False)은 감점해서 사실상 제외한다."""
    def score(p):
        s = 2 if skin_type in p["good_for"] else 0
        for e in extras:
            if e in p["good_for_extras"]:
                s += 1
            if e == "민감성" and p["fragrance_free"] is False:
                s -= 5
        return s

    ranked = sorted(catalog, key=score, reverse=True)
    picks, seen_categories = [], set()
    for p in ranked:
        if p["category"] in seen_categories:
            continue
        picks.append({**p, "reason": f"{skin_type} 피부에 잘 맞는 {p['category']}로 골라봤어요."})
        seen_categories.add(p["category"])
        if len(picks) == 3:
            break
    return picks


def get_curated_product_recommendation(char, country_code):
    """이 나라에 실제 제품 큐레이션(COUNTRY_PRODUCT_CATALOGS)이 있으면 그 목록
    '안에서만' 골라 (제품, 추천 이유) 리스트를 반환하고, 없는 나라는 None을
    반환한다(호출부는 None이면 기존 자유형 AI 추천으로 대체 표시).
    AI 호출이 가능하면 AI가 이유까지 골라주고, 안 되거나 실패하면 같은
    카탈로그에서 규칙 기반으로 골라 사진은 항상 뜨도록 보장한다."""
    catalog = COUNTRY_PRODUCT_CATALOGS.get(country_code)
    if not catalog:
        return None

    baseline = get_skin_baseline(char)
    skin_type = baseline.get("skin_type") or SKIN_TYPES[0]
    extras = baseline.get("extras") or []
    prefs = char.get("cosmetic_prefs") or []
    by_id = {p["id"]: p for p in catalog}

    if ANTHROPIC_API_KEY and anthropic is not None:
        try:
            raw = _cached_curated_product_recommendation(
                skin_type, tuple(sorted(extras)), tuple(sorted(prefs)), country_code
            )
            data = json.loads(raw)
            picks = [
                {**by_id[item["id"]], "reason": item.get("reason", "")}
                for item in data if item.get("id") in by_id
            ][:3]
            if picks:
                return picks
        except Exception:
            pass

    return _rule_based_curated_picks(catalog, skin_type, extras)


# ----------------------------------------------------------------------
# 피부 맞춤 추천 — "한국에서 이 나라로 떠나기 전에 챙겨가면 좋은 제품".
# 위 COUNTRY_PRODUCT_CATALOGS(현지 판매 제품)와는 반대 방향으로, 실제 올리브영
# 판매 제품(RECOVERY_PRODUCT_CATALOG, 7일 복귀 프로그램과 같은 표를 공유)
# 중에서 여행자의 피부 프로필 + 목적지 기후 특성에 맞는 걸 고른다. 카탈로그
# 자체가 국가와 무관하게 하나뿐이라 모든 국가 페이지에서 동작한다.
# ----------------------------------------------------------------------
def _travel_prep_catalog_prompt_block():
    lines = []
    for p in RECOVERY_PRODUCT_CATALOG:
        lines.append(
            f"- id:{p['id']} | {p['brand']} {p['name']} ({p['texture']}) | "
            f"성분: {', '.join(p['key_ingredients']) or '해당없음'} | "
            f"어울리는 고민: {', '.join(p['target_concern'])}"
        )
    return "\n".join(lines)


@st.cache_data(show_spinner=False, ttl=86400)
def _cached_travel_prep_recommendation(skin_type, extras_key, country_code):
    country = COUNTRIES[country_code]
    prompt = (
        "너는 여행 뷰티 코디네이터야. 아래는 한국 올리브영에서 실제로 판매 중인 스킨케어 "
        "제품 목록이야. 여행자가 이 목적지로 떠나기 전에 한국에서 미리 챙겨가면 좋은 제품을 "
        "이 목록 '안에서만' 정확히 3개 골라줘. 목록에 없는 제품/브랜드/성분을 새로 지어내면 "
        "안 돼.\n\n"
        f"[제품 목록]\n{_travel_prep_catalog_prompt_block()}\n\n"
        f"[여행자] 피부타입: {skin_type} / 피부 특이사항: {', '.join(extras_key) or '없음'}\n"
        f"[목적지 기후] {country['name']} — {country['climate']} / 자외선: {country['uv']} / "
        f"습도: {country['humidity']} / 수질: {country['water']} ({country['water_note']})\n\n"
        '다른 설명 없이 순수 JSON 배열만 출력해: [{"id":"p1","reason":"추천 이유 한 문장"}, ...] '
        "reason은 한국어로, 왜 이 여행자 피부와 이 목적지 여행 전에 챙겨가면 좋은지 한 문장으로 써."
    )
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


@st.cache_data(show_spinner=False, ttl=86400)
def _cached_travel_prep_recommendation_scan(
    hydration, redness, pore_visibility, texture_evenness, oiliness, country_code
):
    country = COUNTRIES[country_code]
    prompt = (
        "너는 여행 뷰티 코디네이터야. 아래는 한국 올리브영에서 실제로 판매 중인 스킨케어 "
        "제품 목록이야. 여행자가 이 목적지로 떠나기 전에 한국에서 미리 챙겨가면 좋은 제품을 "
        "이 목록 '안에서만' 정확히 3개 골라줘. 목록에 없는 제품/브랜드/성분을 새로 지어내면 "
        "안 돼.\n\n"
        f"[제품 목록]\n{_travel_prep_catalog_prompt_block()}\n\n"
        f"[여행자 얼굴 스캔 결과 (0~100)] 수분감: {hydration} / 붉은기: {redness} / "
        f"모공 가시성: {pore_visibility} / 결 균일도: {texture_evenness} / 유분감: {oiliness}\n"
        f"[목적지 기후] {country['name']} — {country['climate']} / 자외선: {country['uv']} / "
        f"습도: {country['humidity']} / 수질: {country['water']} ({country['water_note']})\n\n"
        '다른 설명 없이 순수 JSON 배열만 출력해: [{"id":"p1","reason":"추천 이유 한 문장"}, ...] '
        "reason은 한국어로, 왜 이 스캔 결과와 이 목적지 여행 전에 챙겨가면 좋은지 한 문장으로 써."
    )
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def _travel_prep_concern_tags(baseline, country):
    """여행자 피부 프로필 + 목적지 기후 특성을 RECOVERY_PRODUCT_CATALOG의
    target_concern 태그로 변환한다(규칙 기반 대체 로직용). 카메라 스캔을 했으면
    자가응답 피부타입/특이사항 대신 스캔 5개 지표를 우선한다 — 스캔 전후로
    추천 제품이 달라지게 하는 핵심 분기."""
    tags = []
    if baseline["baseline_source"] == "camera_scan":
        if baseline["hydration"] <= 40:
            tags.append("건조")
        if baseline["redness"] >= 60:
            tags.append("자극/붉음")
        if baseline["oiliness"] >= 60:
            tags.append("모공")
        if baseline["pore_visibility"] >= 60 or baseline["texture_evenness"] <= 40:
            tags.append("피부결/각질")
    else:
        skin_type = baseline.get("skin_type")
        extras = baseline.get("extras") or []
        for e in extras:
            if e == "민감성":
                tags.append("자극/붉음")
            if e == "트러블":
                tags.append("트러블")
        if skin_type == "건성":
            tags.append("건조")
    if "강함" in (country.get("uv") or ""):
        tags.append("칙칙함/톤")
    if (country.get("humidity") or "").startswith("평균 2") or "매우 건조" in (country.get("humidity") or ""):
        tags.append("건조")
    if country.get("water") == "경수":
        tags.append("트러블")
    if "매우 강함" in (country.get("uv") or "") or "매우 높은" in (country.get("water_note") or ""):
        tags.append("자극/붉음")
    if not tags:
        tags.append("피로/장벽")
    return tags


def _rule_based_travel_prep_picks(baseline, country):
    tags = _travel_prep_concern_tags(baseline, country)
    reason_prefix = "스캔 결과에 맞춰" if baseline["baseline_source"] == "camera_scan" else "피부 프로필에 맞춰"

    def score(p):
        return sum(1 for t in tags if t in p["target_concern"])

    ranked = sorted(RECOVERY_PRODUCT_CATALOG, key=score, reverse=True)
    picks, seen_textures = [], set()
    for p in ranked:
        if p["texture"] in seen_textures:
            continue
        picks.append({**p, "reason": f"{reason_prefix} {country['name']} 여행 전 챙겨가면 좋은 {p['texture']}로 골라봤어요."})
        seen_textures.add(p["texture"])
        if len(picks) == 3:
            break
    return picks


def get_travel_prep_recommendation(char, country_code):
    """한국 올리브영 제품(RECOVERY_PRODUCT_CATALOG) 중, 이 나라로 떠나기 전에
    챙겨가면 좋은 제품을 추천한다 — 큐레이션 카탈로그 유무와 무관하게 모든
    국가에서 동작한다. 카메라 스캔을 했으면 자가응답 대신 스캔 5개 지표를
    입력값으로 써서 스캔 전후로 추천 결과가 달라진다."""
    baseline = get_skin_baseline(char)
    country = COUNTRIES[country_code]
    by_id = {p["id"]: p for p in RECOVERY_PRODUCT_CATALOG}

    if ANTHROPIC_API_KEY and anthropic is not None:
        try:
            if baseline["baseline_source"] == "camera_scan":
                raw = _cached_travel_prep_recommendation_scan(
                    baseline["hydration"], baseline["redness"], baseline["pore_visibility"],
                    baseline["texture_evenness"], baseline["oiliness"], country_code,
                )
            else:
                skin_type = baseline.get("skin_type") or SKIN_TYPES[0]
                extras = baseline.get("extras") or []
                raw = _cached_travel_prep_recommendation(skin_type, tuple(sorted(extras)), country_code)
            data = json.loads(raw)
            picks = [
                {**by_id[item["id"]], "reason": item.get("reason", "")}
                for item in data if item.get("id") in by_id
            ][:3]
            if picks:
                return picks
        except Exception:
            pass

    return _rule_based_travel_prep_picks(baseline, country)


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


# 헤어 아이콘에서 "3WAAU 추천 및 구매 사이트로 이동" 버튼이 여는 실제 스토어 링크
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


_LIVE_WEATHER_CACHE_TTL = 1800


def _soft_cached_fetch(session_key, cache_key, fetch_fn):
    """API 호출 결과를 세션별로 캐싱하되, 실패(None)는 절대 캐시에 남기지 않는다.
    st.cache_data(ttl=1800)로 실패까지 그대로 캐싱했더니, 한 번 타임아웃/에러가 나면
    새로고침 버튼을 눌러도 30분 동안 "--"만 보이는 문제가 있었다 — 실패하면 다음
    호출(새로고침이든 재방문이든)에서 바로 재시도하고, 그 사이엔 마지막으로 성공한
    값이라도 있으면 그걸 보여준다(완전히 비어 보이는 것보다 낫다)."""
    cache = st.session_state.setdefault(session_key, {})
    entry = cache.get(cache_key)
    if entry and time.time() - entry["ts"] < _LIVE_WEATHER_CACHE_TTL:
        return entry["data"]
    fresh = fetch_fn()
    if fresh is not None:
        cache[cache_key] = {"data": fresh, "ts": time.time()}
        return fresh
    return entry["data"] if entry else None


def get_live_weather(geo):
    """실시간 기온·습도·자외선 지수를 가져온다. geo는 COUNTRIES[code]["geo"] 형식의
    "lat;lon" 문자열. One Call API 3.0(/data/3.0/onecall)은 별도 유료 구독이 있어야만
    쓸 수 있어서(무료 키는 401), 기본 키로도 되는 두 엔드포인트로 나눠 받는다 —
    기온·습도는 현재 날씨 API(/data/2.5/weather), 자외선은 UV 인덱스 API
    (/data/2.5/uvi)."""
    if not OPENWEATHER_API_KEY or not geo:
        return None

    def _fetch():
        try:
            lat, lon = geo.split(";")
            weather_resp = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "kr"},
                timeout=5,
            )
            weather_data = weather_resp.json()
            main = weather_data.get("main")
            if not main:
                return None
            weather0 = (weather_data.get("weather") or [{}])[0]
            result = {
                "temp": main.get("temp"),
                "humidity": main.get("humidity"),
                "uvi": None,
                "condition": weather0.get("main", ""),
                "description": weather0.get("description", ""),
            }
            uvi_resp = requests.get(
                "https://api.openweathermap.org/data/2.5/uvi",
                params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY},
                timeout=5,
            )
            if uvi_resp.status_code == 200:
                result["uvi"] = uvi_resp.json().get("value")
            return result
        except (requests.RequestException, ValueError, KeyError):
            return None

    return _soft_cached_fetch("_live_weather_cache", geo, _fetch)


def get_live_air_pollution(geo):
    """OpenWeatherMap 대기오염 API에서 실시간 미세먼지(PM2.5/PM10)·대기질 지수를 가져온다.
    geo는 COUNTRIES[code]["geo"] 형식의 "lat;lon" 문자열."""
    if not OPENWEATHER_API_KEY or not geo:
        return None

    def _fetch():
        try:
            lat, lon = geo.split(";")
            resp = requests.get(
                "https://api.openweathermap.org/data/2.5/air_pollution",
                params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY},
                timeout=5,
            )
            data = resp.json()
            entry = (data.get("list") or [None])[0]
            if not entry:
                return None
            components = entry.get("components") or {}
            return {
                "aqi": (entry.get("main") or {}).get("aqi"),
                "pm2_5": components.get("pm2_5"),
                "pm10": components.get("pm10"),
            }
        except (requests.RequestException, ValueError, KeyError):
            return None

    return _soft_cached_fetch("_live_air_pollution_cache", geo, _fetch)


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

# 여행 후 피부 복귀 프로그램 입구 아이콘 — 사용자가 준 참고 사진(둥근 지붕이
# 그대로 벽으로 이어지는 퍼리윙클/라벤더 블루 3D 하우스 + 2x2 둥근 사각형
# 창문)을 재현한 SVG.
HOME_ICON_SVG = """
<svg viewBox="0 0 200 190" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="homeBody" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#d3d9ff"/>
      <stop offset="50%" stop-color="#a5b2f7"/>
      <stop offset="100%" stop-color="#7c8bee"/>
    </linearGradient>
  </defs>
  <path d="M100,10
           C107,10 114,13 119,19
           L183,84
           C193,94 193,111 178,117
           C167,121 156,118 149,109
           L149,163
           C149,176 139,186 126,186
           L74,186
           C61,186 51,176 51,163
           L51,109
           C44,118 33,121 22,117
           C7,111 7,94 17,84
           L81,19
           C86,13 93,10 100,10 Z"
        fill="url(#homeBody)"/>
  <ellipse cx="70" cy="46" rx="30" ry="16" fill="#ffffff" opacity=".22"/>
  <g fill="#f4f6ff">
    <rect x="70" y="118" width="27" height="27" rx="8"/>
    <rect x="103" y="118" width="27" height="27" rx="8"/>
    <rect x="70" y="151" width="27" height="27" rx="8"/>
    <rect x="103" y="151" width="27" height="27" rx="8"/>
  </g>
</svg>
"""
HOME_ICON_URI = "data:image/svg+xml;base64," + base64.b64encode(HOME_ICON_SVG.strip().encode()).decode()

# 얼굴 스캔하기 아이콘 — 뷰파인더 모서리 브래킷 + 얼굴 실루엣 + 스캔 라인.
FACE_SCAN_ICON_SVG = """
<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="scanFace" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffd9ee"/>
      <stop offset="100%" stop-color="#ff9fd8"/>
    </linearGradient>
    <linearGradient id="scanLine" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#ff6fb8" stop-opacity="0"/>
      <stop offset="50%" stop-color="#ff2f9e"/>
      <stop offset="100%" stop-color="#ff6fb8" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <path d="M10,26 L10,14 Q10,8 16,8 L28,8" fill="none" stroke="#c2409c" stroke-width="5" stroke-linecap="round"/>
  <path d="M90,26 L90,14 Q90,8 84,8 L72,8" fill="none" stroke="#c2409c" stroke-width="5" stroke-linecap="round"/>
  <path d="M10,74 L10,86 Q10,92 16,92 L28,92" fill="none" stroke="#c2409c" stroke-width="5" stroke-linecap="round"/>
  <path d="M90,74 L90,86 Q90,92 84,92 L72,92" fill="none" stroke="#c2409c" stroke-width="5" stroke-linecap="round"/>
  <circle cx="50" cy="45" r="17" fill="url(#scanFace)" stroke="#c2409c" stroke-width="2.4"/>
  <path d="M35,58 Q50,72 65,58 L65,66 Q50,80 35,66 Z" fill="url(#scanFace)" stroke="#c2409c" stroke-width="2.4"/>
  <circle cx="43" cy="43" r="2.6" fill="#7a3060"/>
  <circle cx="57" cy="43" r="2.6" fill="#7a3060"/>
  <path d="M46,50 Q50,53 54,50" stroke="#7a3060" stroke-width="2" fill="none" stroke-linecap="round"/>
  <rect x="8" y="49" width="84" height="4" rx="2" fill="url(#scanLine)"/>
</svg>
"""
FACE_SCAN_ICON_URI = "data:image/svg+xml;base64," + base64.b64encode(FACE_SCAN_ICON_SVG.strip().encode()).decode()

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
# 여행 후 피부 복귀 프로그램 — 제품 카탈로그.
# 추천 엔진(generate_recovery_program 등)은 반드시 이 표에 있는 제품만 골라야
# 한다 — 이름/브랜드/성분/효능을 절대 새로 지어내지 않는다. 각 제품의
# key_ingredients/description은 화장품법상 허용되는 범위의 표현만 쓴다
# ("완화를 도와줄 수 있어요" 류) — "치료/제거/재생" 같은 의약품 오인 표현 금지.
# 실제 올리브영 판매 제품(코스맥스 제조, oliveyoung_skincare_cosmax_images.csv
# 기준, 26.7.10)으로 교체 — brand/image/url/price는 모두 그 자료에서 그대로
# 가져왔고, texture/target_concern/key_ingredients는 제품명에 명시된 포뮬러
# 이름을 근거로만 태깅했다(없는 효능 지어내지 않음). 카탈로그에 눈가 전용
# 제품(다크서클)이 없어서 "다크서클" concern은 매칭되는 제품이 없을 수 있다.
# ----------------------------------------------------------------------
RECOVERY_PRODUCT_CATALOG = [
    {"id": "p1", "brand": "브링그린", "name": "티트리 시카 수딩 토너", "texture": "토너",
     "target_concern": ["자극/붉음", "트러블"], "key_ingredients": ["티트리오일", "시카(센텔라아시아티카)"],
     "description": "예민하고 트러블이 신경 쓰이는 피부를 가볍게 가라앉히는 데 도움을 줄 수 있는 토너예요.",
     "price": "27,000", "image": "oy_products/oy01_bringgreen_teatree_cica_toner.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000189181"},
    {"id": "p2", "brand": "아비브", "name": "어성초 카밍 토너 스킨부스터", "texture": "토너",
     "target_concern": ["자극/붉음"], "key_ingredients": ["어성초추출물"],
     "description": "자극받아 예민해진 피부에 수분과 진정감을 더해주는 데 도움을 줄 수 있는 토너예요.",
     "price": "23,000", "image": "oy_products/oy02_abib_hoja_calming_toner.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000146589"},
    {"id": "p3", "brand": "파티온", "name": "노스카나인 트러블 클리어 토너", "texture": "토너",
     "target_concern": ["트러블"], "key_ingredients": ["약산성 포뮬러"],
     "description": "약산성으로 자극을 줄이면서 트러블이 신경 쓰이는 피부를 정돈하는 데 도움을 줄 수 있는 토너예요.",
     "price": "23,000", "image": "oy_products/oy03_partion_noscanine_toner.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000182787"},
    {"id": "p4", "brand": "더랩바이블랑두", "name": "올리고 히알루론산 딥 토너", "texture": "토너",
     "target_concern": ["건조", "피로/장벽"], "key_ingredients": ["올리고 히알루론산"],
     "description": "속보습이 필요한 건조한 피부에 수분을 채워주는 데 도움을 줄 수 있는 딥 토너예요.",
     "price": "37,000", "image": "oy_products/oy04_thelab_oligo_hyaluron_toner.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000207054"},
    {"id": "p5", "brand": "닥터디퍼런트", "name": "스케일링 토너 (지성용)", "texture": "토너",
     "target_concern": ["모공", "피부결/각질"], "key_ingredients": ["각질 케어 포뮬러"],
     "description": "묵은 각질과 모공 속 노폐물을 부드럽게 정돈하는 데 도움을 줄 수 있는 스케일링 토너예요.",
     "price": "32,000", "image": "oy_products/oy05_drdifferent_scaling_toner.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000217777"},
    {"id": "p6", "brand": "아누아", "name": "복숭아 나이아신아마이드 에센스 토너", "texture": "토너",
     "target_concern": ["칙칙함/톤", "피부 톤 불균일"], "key_ingredients": ["나이아신아마이드"],
     "description": "칙칙해진 톤을 환하게 정돈하는 데 도움을 줄 수 있는 에센스 토너예요.",
     "price": "25,000", "image": "oy_products/oy06_anua_peach_niacinamide_toner.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000210050"},
    {"id": "p7", "brand": "아비브", "name": "글루타치온좀 잡티 토너 스킨부스터", "texture": "토너",
     "target_concern": ["기미"], "key_ingredients": ["글루타치온"],
     "description": "또렷해진 잡티가 신경 쓰일 때 톤을 정돈하는 데 도움을 줄 수 있는 토너예요.",
     "price": "23,000", "image": "oy_products/oy07_abib_glutathione_toner.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000227666"},
    {"id": "p8", "brand": "메디힐", "name": "마데카소사이드 흔적 리페어 세럼", "texture": "세럼",
     "target_concern": ["자극/붉음", "피부결/각질"], "key_ingredients": ["마데카소사이드"],
     "description": "자극받은 흔적이 남은 피부결을 가볍게 가라앉히는 데 도움을 줄 수 있는 세럼이에요.",
     "price": "36,900", "image": "oy_products/oy08_mediheal_madeca_serum.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000211119"},
    {"id": "p9", "brand": "메디힐", "name": "비타민씨 브라이트닝 세럼", "texture": "세럼",
     "target_concern": ["칙칙함/톤", "피부 톤 불균일", "기미", "자극 성분 재도입"],
     "key_ingredients": ["비타민C(아스코르빈산)"],
     "description": "톤 개선에 도움을 줄 수 있는 비타민C 세럼이에요. 자극감이 있을 수 있어 서서히 늘려가며 사용하는 걸 권해요.",
     "price": "22,000", "image": "oy_products/oy09_mediheal_vitaminc_serum.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000192699"},
    {"id": "p10", "brand": "파티온", "name": "노스카나인 트러블 세럼", "texture": "세럼",
     "target_concern": ["트러블"], "key_ingredients": ["약산성 포뮬러"],
     "description": "트러블이 신경 쓰이는 부위를 진정시키는 데 도움을 줄 수 있는 세럼이에요.",
     "price": "38,000", "image": "oy_products/oy10_partion_noscanine_serum.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000219717"},
    {"id": "p11", "brand": "일소", "name": "펩타이드 3엑스 모공톡스 탄력 앰플", "texture": "앰플",
     "target_concern": ["모공", "피부결/각질"], "key_ingredients": ["펩타이드"],
     "description": "넓어진 모공과 거칠어진 결을 정돈하는 데 도움을 줄 수 있는 탄력 앰플이에요.",
     "price": "28,000", "image": "oy_products/oy11_ilso_peptide_pore_ampoule.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000258824"},
    {"id": "p12", "brand": "퍼셀", "name": "픽셀바이옴 유산균 원액", "texture": "앰플",
     "target_concern": ["피로/장벽"], "key_ingredients": ["유산균 발효 원액"],
     "description": "지친 피부 장벽을 채워주는 데 도움을 줄 수 있는 장벽 강화 앰플이에요.",
     "price": "28,000", "image": "oy_products/oy12_percell_biome_ampoule.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000208860"},
    {"id": "p13", "brand": "이지듀", "name": "기미잡티앰플", "texture": "앰플",
     "target_concern": ["기미"], "key_ingredients": [],
     "description": "기미·잡티가 신경 쓰이는 부위를 집중 케어하는 데 도움을 줄 수 있는 앰플이에요.",
     "price": "49,000", "image": "oy_products/oy13_easydew_pigment_ampoule.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000188493"},
    {"id": "p14", "brand": "닥터자르트", "name": "시카페어 인텐시브 수딩 리페어 크림", "texture": "크림",
     "target_concern": ["자극/붉음", "피로/장벽"], "key_ingredients": ["시카(센텔라아시아티카)"],
     "description": "자극받아 지친 피부를 강도 높게 진정시키는 데 도움을 줄 수 있는 크림이에요.",
     "price": "50,000", "image": "oy_products/oy14_drjart_cicapair_cream.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000218592"},
    {"id": "p15", "brand": "아누아", "name": "피디알엔 히알루론산 100 수분 크림", "texture": "크림",
     "target_concern": ["건조", "피로/장벽"], "key_ingredients": ["PDRN", "히알루론산"],
     "description": "건조하고 지친 피부에 수분과 광채를 더해주는 데 도움을 줄 수 있는 크림이에요.",
     "price": "32,000", "image": "oy_products/oy15_anua_pdrn_hyaluron_cream.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000222703"},
    {"id": "p16", "brand": "파티온", "name": "노스카나인 트러블 크림", "texture": "크림",
     "target_concern": ["트러블"], "key_ingredients": ["약산성 포뮬러"],
     "description": "트러블이 신경 쓰이는 피부 장벽을 겹겹이 채워주는 데 도움을 줄 수 있는 크림이에요.",
     "price": "32,000", "image": "oy_products/oy16_partion_noscanine_cream.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000219716"},
    {"id": "p17", "brand": "바이오힐보", "name": "판테셀 리페어시카 크림", "texture": "크림",
     "target_concern": ["자극/붉음", "피로/장벽"], "key_ingredients": ["판테놀", "시카(센텔라아시아티카)"],
     "description": "예민하고 지친 피부를 진정시키며 채워주는 데 도움을 줄 수 있는 크림이에요.",
     "price": "32,000", "image": "oy_products/oy17_biohealboh_pantheal_cica_cream.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000189248"},
    {"id": "p18", "brand": "구달", "name": "어성초 히알루론 수딩 크림", "texture": "크림",
     "target_concern": ["자극/붉음", "건조"], "key_ingredients": ["어성초추출물", "히알루론산"],
     "description": "예민하고 건조해진 피부를 진정시키며 수분을 채워주는 데 도움을 줄 수 있는 크림이에요.",
     "price": "30,000", "image": "oy_products/oy18_goodal_hoja_hyaluron_cream.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000257128"},
    {"id": "p19", "brand": "라운드랩", "name": "1025 독도 로션", "texture": "로션",
     "target_concern": ["정상 루틴", "건조"], "key_ingredients": ["자작나무 수액"],
     "description": "저자극으로 매일 가볍게 수분을 채워주는 데 도움을 줄 수 있는 데일리 로션이에요.",
     "price": "39,000", "image": "oy_products/oy19_roundlab_dokdo_lotion.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000161508"},
    {"id": "p20", "brand": "아누아", "name": "어성초 77 히알루론산 수분 진정 로션", "texture": "로션",
     "target_concern": ["건조", "자극/붉음", "정상 루틴"], "key_ingredients": ["어성초추출물", "히알루론산"],
     "description": "건조하고 예민한 피부에 수분과 진정감을 함께 더해주는 데 도움을 줄 수 있는 로션이에요.",
     "price": "28,000", "image": "oy_products/oy20_anua_hoja_hyaluron_lotion.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000248426"},
    {"id": "p21", "brand": "닥터자르트", "name": "세라마이딘 스킨 베리어 모이스처라이징 밀키 로션", "texture": "로션",
     "target_concern": ["피로/장벽", "정상 루틴"], "key_ingredients": ["세라마이드"],
     "description": "지친 피부 장벽을 채워 72시간 보습감을 유지하는 데 도움을 줄 수 있는 로션이에요.",
     "price": "50,000", "image": "oy_products/oy21_drjart_ceramidin_lotion.png",
     "url": "https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A000000198090"},
]

# ----------------------------------------------------------------------
# 전략 미션 — 국가별 규제 충돌: 추천 제품의 특정 성분이 목적지 국가에서 반입 시
# 별도 확인·주의가 필요한 경우를 안내한다. 지금은 중국만 채워져 있고, 나중에
# 일본·미국·EU 등을 추가할 때는 이 dict에 국가 코드만 늘리면 된다. source는
# 화면에 그대로 노출해서 규제 정보의 출처를 투명하게 보여준다(투명성 UI).
# ----------------------------------------------------------------------
COUNTRY_INGREDIENT_CAUTIONS = {
    "cn": {
        "PDRN": {
            "reason": "연어 유래 DNA 추출물(생물유래 원료)이 포함돼 있어 중국 세관의 "
                      "생물유래 제품 반입 규정에 따라 개인 휴대량이라도 별도 확인을 "
                      "요구받을 수 있어요.",
            "source": "중국 해관총서(세관) 생물유래 제품 반입 규정 기준 — 통관 전 "
                      "현지 세관의 최신 안내를 다시 확인하세요.",
        },
    },
}


def get_ingredient_caution(country_code, key_ingredients):
    """제품의 key_ingredients 중 목적지 국가의 반입 주의 성분과 일치하는 첫 번째
    항목을 (성분명, {reason, source}) 튜플로 반환한다. 없으면 None."""
    cautions = COUNTRY_INGREDIENT_CAUTIONS.get(country_code) or {}
    for ing in key_ingredients:
        if ing in cautions:
            return ing, cautions[ing]
    return None


def _country_ingredient_warning_products(country_code):
    """이 나라에서 반입 주의가 필요한 제품을 카탈로그 전체에서 찾아
    (제품, 성분명, caution) 리스트로 반환한다 — 국가 지도 단계의 경고 포스트잇용."""
    cautions = COUNTRY_INGREDIENT_CAUTIONS.get(country_code) or {}
    if not cautions:
        return []
    results = []
    for p in RECOVERY_PRODUCT_CATALOG:
        hit = get_ingredient_caution(country_code, p["key_ingredients"])
        if hit:
            results.append((p, hit[0], hit[1]))
    return results

# 우선순위 규칙 — 숫자가 작을수록 먼저 케어(급함). 나중에 조정하고 싶으면
# 이 표만 바꾸면 된다(코드 로직에는 하드코딩 안 함).
RECOVERY_CONCERN_PRIORITY_TIER = {
    "자극/붉음": 1,
    "트러블": 2,
    "건조": 3,
    "피부결/각질": 3,
    "모공": 3,
    "칙칙함/톤": 4,
    "피부 톤 불균일": 4,
    "기미": 4,
    "다크서클": 4,
}
RECOVERY_SEVERITY_BY_TIER = {1: 5, 2: 4, 3: 3, 4: 2}

# "빠른 추가" 칩 목록 — 여행 중 고민 기록 화면(01단계)에서 원터치로 추가할 수
# 있는 고민 카테고리. 값은 모두 RECOVERY_PRODUCT_CATALOG의 target_concern과
# 일치해야 제품이 매칭된다.
RECOVERY_QUICK_ADD_CHIPS = [
    "피부 톤 불균일", "기미", "건조", "트러블", "모공", "다크서클", "자극/붉음", "칙칙함/톤",
]

# 여행 후 설문조사 5문항 — 각 옵션이 가리키는 target_concern 키로 로직이
# 연결된다. 문항은 서로 독립적이라 여러 개를 동시에 "해당"으로 고를 수 있다.
RECOVERY_SURVEY_QUESTIONS = [
    {
        "id": "tone", "prompt": "나는 여행 후 피부톤이",
        "options": [
            {"label": "칙칙해졌다", "concern": "칙칙함/톤"},
            {"label": "붉어졌다", "concern": "자극/붉음"},
        ],
    },
    {
        "id": "trouble", "prompt": "나는 여행 동안 트러블이",
        "options": [
            {"label": "생겼다", "concern": "트러블"},
            {"label": "안 생겼다", "concern": None},
        ],
    },
    {
        "id": "texture", "prompt": "나는 여행 후 피부결이",
        "options": [
            {"label": "거칠어졌다", "concern": "피부결/각질"},
            {"label": "그대로다", "concern": None},
        ],
    },
    {
        "id": "sensitive", "prompt": "나는 여행 후 피부가",
        "options": [
            {"label": "예민해지고 자극에 쉽게 반응한다", "concern": "자극/붉음"},
            {"label": "평소와 비슷하다", "concern": None},
        ],
    },
    {
        "id": "dry", "prompt": "나는 여행 후 피부가",
        "options": [
            {"label": "건조하고 각질이 일어난다", "concern": "건조"},
            {"label": "그렇지 않다", "concern": None},
        ],
    },
    {
        "id": "tone_uneven", "prompt": "나는 여행 후 피부 톤이",
        "options": [
            {"label": "부분적으로 불균일해졌다", "concern": "피부 톤 불균일"},
            {"label": "고르게 유지됐다", "concern": None},
        ],
    },
    {
        "id": "pigment", "prompt": "나는 여행 후 기미/잡티가",
        "options": [
            {"label": "또렷해졌다", "concern": "기미"},
            {"label": "그대로다", "concern": None},
        ],
    },
    {
        "id": "pore", "prompt": "나는 여행 후 모공이",
        "options": [
            {"label": "넓어지고 두드러진다", "concern": "모공"},
            {"label": "그렇지 않다", "concern": None},
        ],
    },
    {
        "id": "darkcircle", "prompt": "나는 여행 후 다크서클이",
        "options": [
            {"label": "더 진해졌다", "concern": "다크서클"},
            {"label": "그대로다", "concern": None},
        ],
    },
]

# 여행 로그(방문 국가의 환경 데이터) × 설문 concern을 연결해 문구를 조금 더
# 구체적으로 바꿔주는 규칙 — 예: 자외선이 강한 나라를 다녀왔고 "칙칙함/톤"을
# 겪었다면 단순 미백이 아니라 자외선 손상 회복 관점으로 안내한다.
RECOVERY_TRIP_CONTEXT_NOTES = [
    {"concern": "칙칙함/톤", "when": lambda c: "강함" in (c.get("uv") or ""),
     "note": "자외선 노출이 많았던 여행이라 톤 케어와 함께 자외선 손상 회복에도 신경 써보면 좋아요."},
    {"concern": "건조", "when": lambda c: (c.get("humidity") or "").startswith("평균 2") or "매우 건조" in (c.get("humidity") or ""),
     "note": "습도가 낮은 지역을 다녀와서 평소보다 건조가 심할 수 있어요. 보습은 평소보다 한 단계 더 챙겨보세요."},
    {"concern": "트러블", "when": lambda c: c.get("water") == "경수",
     "note": "경수 지역을 다녀온 영향으로 트러블이 났을 수 있어요. 저자극 클렌징을 며칠 더 유지해보세요."},
    {"concern": "자극/붉음", "when": lambda c: "매우 강함" in (c.get("uv") or "") or "매우 높은" in (c.get("water_note") or ""),
     "note": "환경 자극이 컸던 여행지였어요. 진정 루틴을 평소보다 여유롭게 잡아보세요."},
]


def _recovery_match_score(product, concern_key):
    """제품의 target_concern이 이 날의 concern과 얼마나 맞는지 점수화.
    정확히 일치하면 3점, 부분 문자열로 겹치면(예: '톤') 1점, 아니면 0점."""
    if not concern_key:
        return 0
    if concern_key in product["target_concern"]:
        return 3
    if any(k in concern_key or concern_key in k for k in product["target_concern"]):
        return 1
    return 0


def _recovery_pick_product(concern_key, last_product_id, streak):
    """concern에 가장 잘 맞는 제품을 고르되, 같은 제품이 3일 연속(streak>=2에서
    또 고르면 3일째)이 되면 다음으로 잘 맞는 제품으로 대체한다."""
    scored = sorted(
        RECOVERY_PRODUCT_CATALOG,
        key=lambda p: _recovery_match_score(p, concern_key),
        reverse=True,
    )
    for product in scored:
        would_extend_streak = product["id"] == last_product_id
        if would_extend_streak and streak >= 2:
            continue
        return product
    return scored[0]


def compute_recovery_stressor_ranking(logged_issues):
    """빈도x심각도 점수로 내림차순 정렬 — 1순위가 primary_stressor."""
    ranked = [dict(issue, score=issue["frequency"] * issue["severity"]) for issue in logged_issues]
    ranked.sort(key=lambda i: i["score"], reverse=True)
    return ranked


def get_recovery_trip_context_note(concern_key, country):
    """이 concern과 여행지 환경 데이터가 맞물리는 규칙이 있으면 그 문구를 반환."""
    if not country:
        return None
    for rule in RECOVERY_TRIP_CONTEXT_NOTES:
        if rule["concern"] == concern_key and rule["when"](country):
            return rule["note"]
    return None


def generate_recovery_program(logged_issues, flight_hours, minimal_ingredients, country=None):
    """설문에서 뽑아낸 logged_issues로 7일 복귀 프로그램을 생성한다.
    입력 데이터 처리 규칙(우선순위 산정 -> 1~2일 primary -> 3~4일 secondary ->
    5~6일 정상 복귀/재도입 판단 -> 7일 셀프체크)을 그대로 따른다."""
    ranking = compute_recovery_stressor_ranking(logged_issues)
    if not ranking:
        return {"ranking": [], "days": []}

    primary = ranking[0]
    secondary = ranking[1] if len(ranking) > 1 else ranking[0]
    long_flight = flight_hours >= 3
    max_severity = max(i["severity"] for i in logged_issues)
    cautious_reintro = max_severity >= 4 or minimal_ingredients

    day_defs = [
        {
            "day": 1,
            "concern": "피로/장벽" if long_flight else primary["issue"],
            "label": "피로/장벽 회복" if long_flight else f"{primary['issue']} 집중 케어",
            "badge": "장거리 비행 회복 우선" if long_flight else None,
        },
        {"day": 2, "concern": primary["issue"], "label": f"{primary['issue']} 집중 케어"},
        {"day": 3, "concern": secondary["issue"], "label": f"{secondary['issue']} 케어"},
        {"day": 4, "concern": secondary["issue"], "label": f"순한 루틴 전환 · {secondary['issue']} 마무리"},
        {"day": 5, "concern": "정상 루틴", "label": "정상 루틴 복귀 준비"},
        {
            "day": 6, "concern": "자극 성분 재도입", "label": "자극 성분 재도입 검토",
            "note": (
                "피부가 아직 예민할 수 있어요. 비타민C·AHA/BHA 같은 활성 성분은 다음 주로 미루고 "
                "저자극 루틴을 유지해보세요."
                if cautious_reintro else
                "자극 반응이 크지 않았어요. 가벼운 농도로 서서히 재도입해볼 수 있어요."
            ),
        },
        {"day": 7, "concern": None, "label": "상태 점검 (셀프 체크)"},
    ]

    last_product_id, streak = None, 0
    days = []
    for d in day_defs:
        product = None
        if d["concern"]:
            product = _recovery_pick_product(d["concern"], last_product_id, streak)
            streak = streak + 1 if product["id"] == last_product_id else 1
            last_product_id = product["id"]
        else:
            last_product_id, streak = None, 0
        context_note = get_recovery_trip_context_note(d["concern"], country) if d["concern"] else None
        days.append({**d, "product": product, "context_note": context_note})

    return {"ranking": ranking, "primary": primary, "secondary": secondary, "days": days}


def build_recovery_logged_issues(answers):
    """설문 답변(질문id -> 고른 옵션의 concern 값)을 빈도/심각도가 있는
    logged_issues 리스트로 변환한다. 같은 concern을 두 문항 이상에서 골랐으면
    frequency가 올라가서(예: 붉어짐+예민함 모두 선택) 우선순위 점수도 커진다."""
    counts = {}
    for concern in answers.values():
        if not concern:
            continue
        counts[concern] = counts.get(concern, 0) + 1
    issues = []
    for concern, frequency in counts.items():
        tier = RECOVERY_CONCERN_PRIORITY_TIER.get(concern, 4)
        issues.append({
            "issue": concern,
            "frequency": frequency,
            "severity": RECOVERY_SEVERITY_BY_TIER.get(tier, 2),
        })
    return issues


# ----------------------------------------------------------------------
# 출발 전 · 귀국 후 스캔 비교 — 설문 기록뿐 아니라 이 두 사진도 우선순위 분석에
# 함께 반영한다. analyze_skin_scan()의 더미 규칙 기반 지표(수분감/붉은기/모공
# 가시성/결 균일도/유분감, 0~100)를 여행 전/후 각각 구해서 변화량(after-before)을
# 계산하고, 변화가 뚜렷한 지표만 골라 설문과 같은 issue/frequency/severity
# 형태로 바꿔 logged_issues에 합친다.
# ----------------------------------------------------------------------
def compute_photo_comparison_deltas(before_image, after_image):
    before = analyze_skin_scan({"front": before_image})
    after = analyze_skin_scan({"front": after_image})
    return {k: after[k] - before[k] for k in after}


_PHOTO_DELTA_CONCERN_RULES = [
    ("redness", "자극/붉음", lambda d: d >= 15),
    ("hydration", "건조", lambda d: d <= -15),
    ("oiliness", "모공", lambda d: d >= 15),
    ("texture_evenness", "피부결/각질", lambda d: d <= -15),
]


def photo_deltas_to_logged_issues(deltas):
    """사진 비교 변화량을 설문과 같은 형태의 logged_issues로 바꾼다. 변화가
    뚜렷한(임계치 이상) 지표만 반영하고, 심각도는 변화 크기에 비례해 3~5로 잡는다."""
    issues = []
    for key, concern, is_significant in _PHOTO_DELTA_CONCERN_RULES:
        d = deltas.get(key, 0)
        if is_significant(d):
            severity = min(5, max(3, round(abs(d) / 15) + 2))
            issues.append({"issue": concern, "frequency": 2, "severity": severity})
    return issues


def merge_logged_issues(base_issues, extra_issues):
    """같은 concern이면 frequency는 더하고 severity는 더 큰 쪽을 취해 합친다
    (설문 기반 고민 기록에 사진 비교로 발견된 고민을 겹치지 않게 반영)."""
    merged = {i["issue"]: dict(i) for i in base_issues}
    for extra in extra_issues:
        key = extra["issue"]
        if key in merged:
            merged[key]["frequency"] += extra["frequency"]
            merged[key]["severity"] = max(merged[key]["severity"], extra["severity"])
        else:
            merged[key] = dict(extra)
    return list(merged.values())


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
if "carrier_items" not in st.session_state:
    st.session_state.carrier_items = []  # 캐리어 담기 서비스에서 담은 액체류 목록
if "carrier_container_volume" not in st.session_state:
    st.session_state.carrier_container_volume = 100  # 용기 탭의 용량 입력값(프리셋 버튼이 갱신)
if "carrier_product_volume" not in st.session_state:
    st.session_state.carrier_product_volume = 100  # 제품 탭의 용량 입력값
if "passport_carrier_checklist" not in st.session_state:
    st.session_state.passport_carrier_checklist = []  # "체크리스트로 저장"한 캐리어 목록 스냅샷
if "passport_recovery_pages" not in st.session_state:
    st.session_state.passport_recovery_pages = []  # 저장된 7일 복귀 프로그램 — 페이지 단위 리스트(각 페이지=프로그램 목록)
if "passport_view_page" not in st.session_state:
    st.session_state.passport_view_page = 0  # 0=기본 페이지(신원/스탬프/꿀팁 등), 1..N=복귀 프로그램 페이지
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
    st.session_state.diagnosis_stage = "scan"  # "scan" | "brewing" | "result"
if "diagnosis_country" not in st.session_state:
    st.session_state.diagnosis_country = None
if "diagnosis_result" not in st.session_state:
    st.session_state.diagnosis_result = None
if "expanded_country_note" not in st.session_state:
    st.session_state.expanded_country_note = None  # None | "info"(노란 포스트잇) | "warning"(분홍 포스트잇) — 눌러서 크게 띄운 포스트잇
if "recovery_stage" not in st.session_state:
    st.session_state.recovery_stage = "pick_trip"  # pick_trip|survey|concern_log|priority|analyzing|result
if "recovery_trip_code" not in st.session_state:
    st.session_state.recovery_trip_code = None
if "recovery_trip_start" not in st.session_state:
    st.session_state.recovery_trip_start = None
if "recovery_trip_end" not in st.session_state:
    st.session_state.recovery_trip_end = None
if "recovery_answers" not in st.session_state:
    st.session_state.recovery_answers = {}  # 문항 id -> 고른 concern (또는 None)
if "recovery_flight_hours" not in st.session_state:
    st.session_state.recovery_flight_hours = 3.0
if "recovery_logged_issues" not in st.session_state:
    st.session_state.recovery_logged_issues = []  # [{issue, frequency, severity}, ...] 편집 가능한 고민 기록
if "recovery_minimal_ingredients" not in st.session_state:
    st.session_state.recovery_minimal_ingredients = False
if "recovery_program" not in st.session_state:
    st.session_state.recovery_program = None
if "recovery_used_photo_comparison" not in st.session_state:
    st.session_state.recovery_used_photo_comparison = False  # 우선순위 계산에 사진 비교를 반영했는지
if "skin_scan" not in st.session_state:
    st.session_state.skin_scan = None  # 카메라 스캔(정면+좌우 3장) 분석 결과, 없으면 자가응답 기반
if "skin_scan_ui_open" not in st.session_state:
    st.session_state.skin_scan_ui_open = False
if "skin_scan_step" not in st.session_state:
    st.session_state.skin_scan_step = 0  # 0=정면, 1=왼쪽, 2=오른쪽
if "skin_scan_photos" not in st.session_state:
    st.session_state.skin_scan_photos = {}
if "skin_scan_widget_key" not in st.session_state:
    st.session_state.skin_scan_widget_key = 0  # camera_input 리마운트(재촬영)용 카운터
if "skin_scan_analyzing" not in st.session_state:
    st.session_state.skin_scan_analyzing = False  # 3장 다 찍은 직후 "분석 중" 연출 표시 여부
if "diagnosis_scan_cam_open" not in st.session_state:
    st.session_state.diagnosis_scan_cam_open = False  # 궁합 진단 얼굴 스캔 단계에서 카메라 위젯 노출 여부
if "coins" not in st.session_state:
    st.session_state.coins = 9999  # 베타 단계 임시 초기값 — 추후 실제 0부터 시작하도록 변경 필요
if "coin_history" not in st.session_state:
    st.session_state.coin_history = []  # 코인 적립 내역 — 뷰티 패스포트에서 표시
if "show_ad_reward" not in st.session_state:
    st.session_state.show_ad_reward = False
if "current_ad_video" not in st.session_state:
    st.session_state.current_ad_video = None
if "unlocked_countries" not in st.session_state:
    st.session_state.unlocked_countries = set()  # 코인으로 잠금 해제한 여행지 코드
if "unlocked_closet_items" not in st.session_state:
    st.session_state.unlocked_closet_items = set()  # 코인으로 잠금 해제한 옷장/액세서리 item id
if "confirming_closet_unlock" not in st.session_state:
    st.session_state.confirming_closet_unlock = None  # 언락 확인 문구를 보여줄 item id (없으면 None)
if "confirming_unlock" not in st.session_state:
    st.session_state.confirming_unlock = None  # 언락 확인 문구를 보여줄 국가 코드 (없으면 None)
if "coin_celebration_amount" not in st.session_state:
    st.session_state.coin_celebration_amount = None  # 코인 획득 폭죽 애니메이션에 표시할 금액
if "unlock_burst_active" not in st.session_state:
    st.session_state.unlock_burst_active = None  # 잠금 해제 연출이 재생 중인 국가 코드 (없으면 None)


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
# 얼굴 스캔으로 baseline 갱신 — 정면/왼쪽/오른쪽 3장을 찍으면 온보딩 자가응답
# 대신 이 스캔 결과를 추천 매트릭스의 우선 입력값으로 쓴다. Streamlit은 실시간
# 프레임 분석/자동 캡처를 지원하지 않으므로 st.camera_input()으로 매 각도마다
# "촬영 버튼을 눌러 셀피 찍기" 방식으로 구현했다. analyze_skin_scan()은 지금은
# 이미지 밝기/채도/대비 통계로부터 유도한 더미 규칙 기반 추정치이며, 실제 피부
# 분석 비전 모델/API로 교체할 때 이 함수 내부만 바꾸면 된다(호출부는 photos=
# {"front","left","right"} 입력과 반환 dict 구조만 알면 됨).
# ----------------------------------------------------------------------
SCAN_ANGLES = [
    {"key": "front", "label": "정면", "guide": "카메라를 정면으로 보고 찍어주세요"},
    {"key": "left", "label": "왼쪽 얼굴", "guide": "고개를 살짝 왼쪽으로 돌려 옆모습을 찍어주세요"},
    {"key": "right", "label": "오른쪽 얼굴", "guide": "고개를 살짝 오른쪽으로 돌려 옆모습을 찍어주세요"},
]

# 셀피처럼 보이도록 카메라 미리보기를 좌우반전(거울 모드)한다. 분석에 쓰는
# 실제 픽셀 데이터는 그대로 두고(밝기/대비 통계에 영향 없음) 화면 표시만 CSS로
# 반전한다. 촬영 직후 크게 뜨는 정지 이미지 미리보기는 부담스럽다는 피드백을
# 받아 아예 숨기고, 그 자리는 글(진행 안내 문구)만 보이게 한다.
_CAMERA_MIRROR_CSS = """
<style>
[data-testid="stCameraInput"] video { transform: scaleX(-1) !important; }
[data-testid="stCameraInput"] img { display: none !important; }
</style>
"""


def _scan_quality_check(image):
    """촬영된 이미지가 분석하기에 너무 어둡거나/너무 밝거나/흔들렸는지를
    이미지 통계로 대략 판단한다. 기준 미달이면 (False, 안내문구)를 반환."""
    gray = image.convert("L")
    brightness = ImageStat.Stat(gray).mean[0]
    if brightness < 60:
        return False, "💡 조명이 어두워요. 조명이 밝은 곳에서 다시 찍어주세요"
    if brightness > 215:
        return False, "💡 빛이 너무 강해요. 조명을 조절하고 다시 찍어주세요"
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edges = edges.crop((1, 1, edges.width - 1, edges.height - 1))  # 컨볼루션 경계 아티팩트 제외
    sharpness = ImageStat.Stat(edges).stddev[0] ** 2
    if sharpness < 60:
        return False, "📷 사진이 흔들렸어요. 흔들리지 않게 다시 찍어주세요"
    return True, ""


def _single_scan_metrics(image):
    gray = image.convert("L")
    stat = ImageStat.Stat(gray)
    contrast = stat.stddev[0]
    saturation = ImageStat.Stat(image.convert("HSV")).mean[1]
    r, g, b = ImageStat.Stat(image.convert("RGB")).mean
    return {
        "hydration": max(5, min(95, round(70 - contrast * 0.6))),
        "redness": max(5, min(95, round((r - (g + b) / 2) * 1.4 + 40))),
        "pore_visibility": max(5, min(95, round(contrast * 1.1))),
        "texture_evenness": max(5, min(95, round(100 - contrast * 0.9))),
        "oiliness": max(5, min(95, round(saturation / 255 * 100))),
    }


def analyze_skin_scan(photos):
    """정면/왼쪽/오른쪽 3장(photos: {"front","left","right"} -> PIL Image)을
    종합해 hydration/redness/pore_visibility/texture_evenness/oiliness
    (0~100)를 추정한다. 모공·결은 측면에서 더 잘 드러난다고 보고 좌우 사진
    평균을 우선 쓰고, 없으면 있는 각도들의 평균으로 대체한다."""
    per_angle = {angle: _single_scan_metrics(img) for angle, img in photos.items()}
    all_angles = list(per_angle.keys())
    sides = [a for a in ("left", "right") if a in per_angle]

    def avg(key, angles):
        vals = [per_angle[a][key] for a in angles if a in per_angle]
        return round(sum(vals) / len(vals)) if vals else 50

    return {
        "hydration": avg("hydration", ["front"] if "front" in per_angle else all_angles),
        "redness": avg("redness", all_angles),
        "pore_visibility": avg("pore_visibility", sides or all_angles),
        "texture_evenness": avg("texture_evenness", sides or all_angles),
        "oiliness": avg("oiliness", all_angles),
    }


def get_skin_baseline(char):
    """추천 로직이 공통으로 쓰는 피부 baseline. 카메라 스캔 결과가 있으면 그
    5개 지표를 자가응답 피부타입보다 우선해서 쓰고 baseline_source=
    "camera_scan"으로 표시하고, 없으면 온보딩 자가응답 프로필만으로
    baseline_source="self_reported"를 반환한다."""
    profile = get_skin_profile(char)
    scan = st.session_state.get("skin_scan")
    if scan:
        return {**profile, **scan, "baseline_source": "camera_scan"}
    return {**profile, "baseline_source": "self_reported"}


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


# 뷰티 패스포트 한 페이지에 담을 수 있는 복귀 프로그램 개수 — 실제 여권처럼
# "한 페이지 = 프로그램 하나"로 자리가 한정되어 있다는 느낌을 주기 위해 1로 둔다.
PASSPORT_RECOVERY_PAGE_CAPACITY = 1


def save_recovery_program_to_passport(entry):
    """7일 복귀 프로그램을 뷰티 패스포트에 저장한다. 마지막 페이지가 이미 꽉 찼으면
    (PASSPORT_RECOVERY_PAGE_CAPACITY 도달) 새 페이지를 만들어 그쪽에 담고, 그
    새 페이지로 자동으로 넘어가서 보여준다. 반환값은 1부터 시작하는 복귀 페이지
    번호(여권 전체 페이지 번호로는 +1, 기본 페이지가 1페이지라서)."""
    pages = st.session_state.passport_recovery_pages
    if not pages or len(pages[-1]) >= PASSPORT_RECOVERY_PAGE_CAPACITY:
        pages.append([])
    pages[-1].append(entry)
    recovery_page_no = len(pages)
    st.session_state.passport_view_page = recovery_page_no
    return recovery_page_no


def goto(view):
    st.session_state.view = view


# 화면 트리상 "뒤로" 가 어디를 가리키는지 — 히스토리 스택 없이 고정 계층으로 정의
PARENT_VIEW = {
    "character": "home",
    "closet": "character",
    "map": "character",
    "country": "map",
    "aftercare": "map",
    "diagnosis": "country",
    "recovery": "map",
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
        .st-key-nav_map_icon button, .st-key-open_passport_icon button {{
            position: fixed !important; top: 60px !important;
            z-index: 99997 !important;
            width: 62px !important; height: 62px !important;
            min-width: 62px !important; max-width: 62px !important;
            min-height: 62px !important; max-height: 62px !important;
            border-radius: 0 !important; padding: 0 !important;
            background: transparent !important; border: none !important;
            font-size: 3.6rem !important; box-shadow: none !important;
            filter: drop-shadow(0 4px 8px rgba(120,40,90,.35));
            transition: transform .12s ease;
        }}
        .st-key-nav_map_icon button {{ right: 92px !important; }}
        .st-key-open_passport_icon button {{ right: 16px !important; }}
        /* Streamlit이 버튼 글자를 <p>로 한 번 더 감싸는데 그 <p>가 자체 font-size를
           갖고 있어서 button에 준 font-size가 상속되지 않는다 — <p>까지 직접 키운다 */
        /* 전역 보조 버튼 글씨 크기 규칙(button[kind="secondary"][kind="secondary"] p)이
           명시도가 더 높아서 이 규칙을 씹어버리는 문제가 있었다 -- 같은 트릭(속성
           선택자 반복)으로 명시도를 그보다 더 높여서 이겨야 실제로 커진다. */
        .st-key-nav_map_icon.st-key-nav_map_icon button[kind="secondary"][kind="secondary"] p {{
            font-size: 3.6rem !important; line-height: 1 !important;
        }}
        .st-key-nav_map_icon button:hover, .st-key-open_passport_icon button:hover {{
            transform: translateY(-2px) scale(1.06);
        }}
        .st-key-nav_map_icon button:active, .st-key-open_passport_icon button:active {{
            transform: translateY(1px) scale(.96);
        }}
        /* 뷰티 패스포트 아이콘만 참고 사진 그래픽으로 교체 — 원형 배경/테두리 없이
           그래픽 자체(이미 자체적으로 핑크색 여권 모양) 전체가 잘리지 않고
           버튼 영역 안에 꽉 차게 contain으로 키운다 */
        .st-key-open_passport_icon button {{
            background-image: url('{PASSPORT_ICON_URI}') !important;
            background-size: contain !important; background-position: center !important;
            background-repeat: no-repeat !important; background-color: transparent !important;
            color: transparent !important; font-size: 0 !important;
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


AD_VIDEOS_DIR = ASSETS / "ads"
AD_VIDEO_EXTS = (".mp4", ".webm", ".mov", ".m4v")
AD_REWARD_COINS = 10


def _list_ad_videos():
    """assets/ads/ 폴더에 넣어둔 광고 영상 파일을 전부 찾는다 — 개수 제한 없이
    폴더에 있는 만큼(3~5개든 몇 개든) 그대로 랜덤 재생 후보가 된다.
    캐싱하지 않는다 — st.cache_data를 쓰면 폴더에 파일을 나중에 추가해도
    서버를 재시작하기 전까지 예전(비어있던) 결과가 계속 반환되는 문제가 있었다."""
    if not AD_VIDEOS_DIR.exists():
        return []
    return sorted(str(p) for p in AD_VIDEOS_DIR.iterdir() if p.suffix.lower() in AD_VIDEO_EXTS)


def _dismiss_ad_reward():
    """기본 X/바깥 클릭으로 닫아도 '떠 있는 채로 남는' 버그를 막기 위해 상태를 정리한다
    (뷰티 패스포트 다이얼로그에서 쓴 것과 같은 패턴)."""
    st.session_state.show_ad_reward = False
    st.session_state.current_ad_video = None


@st.dialog("🎬 광고 보고 코인 받기", on_dismiss=_dismiss_ad_reward)
def _ad_reward_dialog():
    videos = _list_ad_videos()
    if not videos:
        st.warning("아직 등록된 광고 영상이 없어요. assets/ads/ 폴더에 영상 파일을 넣어주세요.")
        return
    video_path = st.session_state.current_ad_video or random.choice(videos)
    st.session_state.current_ad_video = video_path
    st.video(video_path, autoplay=True)
    st.caption("영상을 다 보셨다면 아래에서 코인을 받아보세요")
    if st.button(f"🎁 {AD_REWARD_COINS}코인 받기", key="claim_ad_reward", type="primary", use_container_width=True):
        st.session_state.coins += AD_REWARD_COINS
        st.session_state.coin_history.append({
            "amount": AD_REWARD_COINS,
            "label": "🎬 광고 시청",
            "when": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        st.session_state.show_ad_reward = False
        st.session_state.current_ad_video = None
        st.session_state.coin_celebration_amount = AD_REWARD_COINS
        st.rerun()


COIN_CELEBRATION_COLORS = ["#FF6FB8", "#FFD86F", "#7CE0C1", "#8FB8FF", "#FFA63D", "#C79BFF", "#FF8AA8"]


def render_coin_celebration():
    """코인을 받은 바로 다음 rerun에 화면 정중앙에서 한 번만 터지는 폭죽(컨페티) +
    큰 축하 문구. coin_celebration_amount를 곧바로 None으로 되돌려서 그 다음
    상호작용부터는(다이얼로그가 이미 닫힌 뒤이므로) 다시 나타나지 않게 한다
    (다른 화면의 just_* 1회성 플래그와 같은 패턴)."""
    amount = st.session_state.coin_celebration_amount
    if not amount:
        return
    st.session_state.coin_celebration_amount = None

    pieces = []
    n = 26
    for i in range(n):
        angle = math.radians((360 / n) * i + random.uniform(-10, 10))
        dist = random.uniform(200, 360)
        dx = round(math.cos(angle) * dist, 1)
        dy = round(math.sin(angle) * dist, 1)
        size = round(random.uniform(8, 15), 1)
        color = random.choice(COIN_CELEBRATION_COLORS)
        delay = round(random.uniform(0, 0.12), 2)
        dur = round(random.uniform(0.8, 1.15), 2)
        rot = round(random.uniform(180, 640))
        pieces.append(
            f'<span class="confetti-piece" style="--dx:{dx}px; --dy:{dy}px; --rot:{rot}deg; '
            f'width:{size}px; height:{size}px; background:{color}; '
            f'animation-delay:{delay}s; animation-duration:{dur}s;"></span>'
        )

    html_block(
        f"""
        <style>
        .coin-celebration-layer {{
            position: fixed; inset: 0; z-index: 999998; pointer-events: none;
            display: flex; align-items: center; justify-content: center; overflow: hidden;
        }}
        .confetti-piece {{
            position: absolute; top: 50%; left: 50%; border-radius: 3px;
            transform: translate(-50%,-50%);
            animation-name: confetti-burst; animation-timing-function: cubic-bezier(.2,.7,.3,1);
            animation-fill-mode: both;
        }}
        @keyframes confetti-burst {{
            0%   {{ transform: translate(-50%,-50%) rotate(0deg); opacity: 1; }}
            70%  {{ opacity: 1; }}
            100% {{
                transform: translate(calc(-50% + var(--dx)), calc(-50% + var(--dy))) rotate(var(--rot));
                opacity: 0;
            }}
        }}
        .coin-celebration-text {{
            position: relative; z-index: 2; text-align: center; padding: 0 6vw;
            font-family: 'Jua', sans-serif; font-weight: 900; color: #ff3d97;
            font-size: clamp(2.1rem, 8vw, 4.4rem);
            -webkit-text-stroke: 4px #fff; paint-order: stroke fill;
            text-shadow:
                0 3px 0 #fff0f7,
                0 7px 0 #ffb3d9,
                0 11px 0 #ff85c2,
                0 15px 0 #e0559f,
                0 22px 34px rgba(120,20,70,.55);
            animation: coin-text-pop 2s cubic-bezier(.22,1.4,.36,1) both;
        }}
        @keyframes coin-text-pop {{
            0%   {{ transform: scale(.2) rotate(-4deg); opacity: 0; }}
            35%  {{ transform: scale(1.15) rotate(-4deg); opacity: 1; }}
            50%  {{ transform: scale(1) rotate(-4deg); }}
            82%  {{ transform: scale(1) rotate(-4deg); opacity: 1; }}
            100% {{ transform: scale(.85) rotate(-4deg); opacity: 0; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .confetti-piece, .coin-celebration-text {{ animation: none !important; }}
        }}
        </style>
        <div class="coin-celebration-layer">
            {"".join(pieces)}
            <div class="coin-celebration-text">🎉 {amount}코인을 획득하셨습니다!!! 🎉</div>
        </div>
        """
    )


def render_ad_reward_button():
    """우상단 아이콘 바로 아래에 떠 있는 '광고보고 코인 받기' 버튼 (홈 화면은 제외,
    render_top_icons와 같은 기준). 누르면 assets/ads/ 폴더의 영상 중 하나를
    무작위로 골라 다이얼로그로 재생하고, 다 보면 코인을 지급한다.
    적립 내역은 뷰티 패스포트(_passport_bio_fields)에서 함께 확인할 수 있다."""
    if st.session_state.view == "home":
        return
    html_block(
        """
        <style>
        .st-key-watch_ad_btn { position: fixed !important; top: 128px !important; right: 16px !important; z-index: 99997 !important; width: auto !important; }
        .st-key-watch_ad_btn button {
            width: auto !important; min-width: 0 !important; max-width: none !important;
            border-radius: 999px !important;
            padding: 0.3rem 0.7rem !important; font-family: 'Jua', sans-serif !important;
            font-size: 0.68rem !important; font-weight: 700 !important;
            border: 2px solid #fff !important; white-space: nowrap !important;
            background: linear-gradient(90deg,#FFD86F,#FFA63D) !important; color: #5a3410 !important;
            box-shadow: 0 3px 8px rgba(180,110,20,.4) !important;
            transition: transform .12s ease;
        }
        .st-key-watch_ad_btn button:hover { transform: translateY(-2px) scale(1.03); }
        .st-key-watch_ad_btn button:active { transform: translateY(1px) scale(.97); }
        </style>
        """
    )
    if st.button("🎬 광고보고 코인 받기", key="watch_ad_btn"):
        videos = _list_ad_videos()
        st.session_state.current_ad_video = random.choice(videos) if videos else None
        st.session_state.show_ad_reward = True
        st.rerun()
    if st.session_state.show_ad_reward:
        _ad_reward_dialog()


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
    rows.append('<div class="p-field"><span class="p-label">COINS · 보유 코인</span>'
                f'<span class="p-value">🪙 {st.session_state.coins:,}</span></div>')
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
           둘 중 짧은 쪽이 항상 긴 쪽 높이에 맞춰지도록(고정 min-height 대신) 컬럼
           체인 전체를 flex로 늘려준다 — Streamlit이 각 컬럼 내부에
           stColumn > stVerticalBlock > stLayoutWrapper 로 감싸는데, 이 LayoutWrapper가
           flex-grow:0(auto)라서 바깥 컬럼이 이미 같은 높이로 늘어나 있어도 안쪽의
           진짜 페이지 박스는 자기 내용물 높이만큼만 차지하고 멈춰 있었다. */
        div[data-testid="stDialog"] div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] {
            display: flex !important;
            flex: 1 1 auto !important;
            flex-direction: column !important;
        }
        /* 왼쪽 페이지(.page)는 st.container가 아니라 html_block(raw markdown)이라
           stLayoutWrapper 대신 stElementContainer > stMarkdown > (익명 div) >
           stMarkdownContainer 체인을 거친다 — 이쪽은 flex가 아니라 block 요소들이라
           height:100%를 각 단계마다 명시해 위(stVerticalBlock, 이미 늘어나 있음)의
           높이를 그대로 이어받게 한다. */
        div[data-testid="stDialog"] div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"],
        div[data-testid="stDialog"] div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"] > div[data-testid="stMarkdown"],
        div[data-testid="stDialog"] div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"] > div[data-testid="stMarkdown"] > div,
        div[data-testid="stDialog"] div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"] > div[data-testid="stMarkdown"] > div > div[data-testid="stMarkdownContainer"] {
            height: 100% !important;
            box-sizing: border-box !important;
        }
        div[data-testid="stDialog"] .page,
        div[data-testid="stDialog"] .st-key-page_right_card {
            background: #fffaf3 !important; padding: 20px 20px 14px;
            flex: 1 1 auto !important; height: 100%; min-height: 200px;
            box-sizing: border-box; border-style: solid !important;
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
        /* 저장된 "여행 후 복귀 프로그램" 페이지에서 쓰는 우선순위/7일 카드도
           맨 위 블랭킷 규칙 때문에 배경이 날아가서 다시 살려준다. */
        div[data-testid="stDialog"] .recovery-rank-card,
        div[data-testid="stDialog"] .recovery-day-card {
            background: #131a2b !important;
        }
        div[data-testid="stDialog"] .recovery-rank-track { background: #232b40 !important; }
        div[data-testid="stDialog"] .recovery-badge-primary { background: #3d3315 !important; }
        div[data-testid="stDialog"] .recovery-badge-secondary { background: #123329 !important; }
        div[data-testid="stDialog"] .recovery-day-num { background: #ff6fb8 !important; }
        div[data-testid="stDialog"] .recovery-day-badge { background: #2b2440 !important; }
        div[data-testid="stDialog"] .recovery-note { background: #3d3315 !important; }
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

    recovery_pages = st.session_state.passport_recovery_pages
    total_pages = 1 + len(recovery_pages)  # 1페이지=기본(신원/스탬프/꿀팁), 그 뒤로 복귀 프로그램 페이지
    if st.session_state.passport_view_page > total_pages - 1:
        st.session_state.passport_view_page = total_pages - 1
    current = st.session_state.passport_view_page

    doll_svg = character_doll_svg(char) if char else ""
    just_opened = st.session_state.just_opened_passport_page
    reveal_rule = "animation: passport-reveal .4s ease both;" if just_opened else ""
    st.session_state.just_opened_passport_page = False

    # 펼친 여권 — 왼쪽/오른쪽 페이지, 책처럼 나란히. 기본 페이지(신원+스탬프+꿀팁
    # 등)는 그대로 두고, 저장된 복귀 프로그램은 뒤에 별도 페이지로 넘겨서 본다.
    # 오른쪽 페이지 팝인 애니메이션 스타일은 컬럼을 나누기 전에 한 번만 찍어둔다 —
    # 컬럼 안(right_page)에서 조건부로 찍으면 별도의 stElementContainer 형제가
    # 생겨서 그만큼 flex-grow 공간을 나눠 먹어가는 바람에 카드 높이가 짧아지는
    # 버그가 있었다(양쪽 페이지 높이 안 맞던 문제의 원인 중 하나).
    if just_opened:
        html_block('<style>.st-key-page_right_card{animation: passport-reveal .4s ease both;}</style>')
    left_page, right_page = st.columns(2, gap=None)

    if current > 0:
        entry = recovery_pages[current - 1][0]
        with left_page:
            html_block(
                f"""
                <div class="page page-left" style="{reveal_rule}">
                    <div class="p-section-title">🏠 여행 후 복귀 프로그램</div>
                    <div class="tip-entry">{html.escape(entry['trip_label'])}</div>
                    <div class="tip-entry" style="opacity:.65;">저장일 · {html.escape(entry['saved_at'])}</div>
                    <div class="p-section-title">우선순위</div>
                    {_recovery_ranking_card_html(entry['ranking'])}
                </div>
                """
            )
        with right_page:
            with st.container(key="page_right_card"):
                html_block('<div class="p-section-title">7일 여정표</div>')
                html_block(_RECOVERY_DAY_CARD_CSS)
                for d in entry["days"]:
                    html_block(_recovery_day_card_html(d))
                if st.button("✕ 이 프로그램 삭제", key=f"del_recovery_page_{current}", use_container_width=True):
                    recovery_pages.pop(current - 1)
                    st.session_state.passport_view_page = max(0, current - 1)
                    st.rerun()
    else:
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

                html_block(f'<div class="p-section-title">🪙 코인 적립 내역 (보유 {st.session_state.coins:,}코인)</div>')
                history = st.session_state.coin_history
                if not history:
                    html_block(
                        '<div class="tip-empty">아직 적립 내역이 없어요 — '
                        '좌하단 "광고보고 코인 받기"를 눌러보세요 🎬</div>'
                    )
                else:
                    for coin_entry in reversed(history[-10:]):
                        amount = coin_entry["amount"]
                        sign = "+" if amount >= 0 else ""
                        html_block(
                            f'<div class="tip-entry">{html.escape(coin_entry["label"])} {sign}{amount}코인 '
                            f'<span style="opacity:.6;font-size:.85em;">· {html.escape(coin_entry["when"])}</span></div>'
                        )

                html_block('<div class="p-section-title">🧳 캐리어 체크리스트</div>')
                checklist = st.session_state.passport_carrier_checklist
                if not checklist:
                    html_block(
                        '<div class="tip-empty">아직 저장한 체크리스트가 없어요 — '
                        '캐리어 담기에서 "체크리스트로 저장"을 눌러보세요 🧳</div>'
                    )
                else:
                    checklist_total = sum(i["volume_ml"] for i in checklist)
                    html_block(f'<div class="tip-entry">총 {len(checklist)}개 · {checklist_total:.0f}ml</div>')
                    for item in checklist:
                        badge = "✅" if item["allowed"] else "❌"
                        html_block(
                            f'<div class="tip-entry">{badge} {html.escape(item["name"])} · '
                            f'{item["volume_ml"]:.0f}ml</div>'
                        )

    if total_pages > 1:
        nav_prev, nav_mid, nav_next = st.columns([1, 2, 1])
        with nav_prev:
            if st.button("◀ 이전 장", disabled=current == 0, use_container_width=True, key="passport_prev_page"):
                st.session_state.passport_view_page -= 1
                st.rerun()
        with nav_mid:
            st.markdown(
                f"<div style='text-align:center;color:#8a6a9a;font-weight:600;padding-top:8px;'>"
                f"{current + 1} / {total_pages} 페이지</div>",
                unsafe_allow_html=True,
            )
        with nav_next:
            if st.button(
                "다음 장 ▶", disabled=current == total_pages - 1, use_container_width=True, key="passport_next_page",
            ):
                st.session_state.passport_view_page += 1
                st.rerun()

    if current == 0:
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
    @import url('https://fonts.googleapis.com/css2?family=Jua&family=Gaegu:wght@700&family=Gamja+Flower&family=Share+Tech+Mono&display=swap');

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

    /* 보조(secondary) 버튼 — 선택 칩(성별/연령대/피부타입 등)과 "뒤로가기"류 액션
       버튼이 회색 테두리의 기본 Streamlit 버튼 그대로였다. 앱 톤(핑크 테두리 +
       Jua 폰트 + 살짝 뜨는 그림자)에 맞춰 카드형으로 바꾸되, primary 캡슐 버튼처럼
       튀지는 않게 절제한다. */
    .stButton > button[kind="secondary"] {
        font-family: 'Jua', sans-serif;
        font-size: 1.15rem;
        padding: 0.6rem 1rem;
        border-radius: 14px;
        border: 2px solid #ffd3ea;
        background: #ffffff;
        color: #6a4a6a;
        box-shadow: 0 3px 0 rgba(255,159,216,.35), 0 4px 10px rgba(120,60,110,.1);
        transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease;
    }
    /* Streamlit이 버튼 글자를 stMarkdownContainer > p로 한 번 더 감싸는데, 그 p에
       자체 font-size(14px)가 실려 있어서 button에 준 font-size가 상속되지 않는다.
       거기다 그 규칙도 !important라 일반 선택자로는 이길 수 없어서, 선택자를
       구체적으로 두 번 반복해 명시도를 올려야 실제로 이긴다. */
    div[data-testid="stButton"] button[kind="secondary"] [data-testid="stMarkdownContainer"] p,
    div[data-testid="stButton"] button[kind="secondary"][kind="secondary"] p {
        font-size: 1.15rem !important;
    }
    .stButton > button[kind="secondary"]:hover {
        border-color: #ff9fd8;
        transform: translateY(-1px);
        box-shadow: 0 4px 0 rgba(255,159,216,.45), 0 6px 14px rgba(120,60,110,.16);
    }
    .stButton > button[kind="secondary"]:active {
        transform: translateY(2px);
        box-shadow: 0 1px 0 rgba(255,159,216,.35), 0 2px 6px rgba(120,60,110,.1);
    }

    /* 파일 업로더(여행 전/후 사진 비교) — 기본 회색 점선 박스 대신 앱 톤의
       파스텔 점선 카드 + 둥근 업로드 버튼으로 */
    [data-testid="stFileUploaderDropzone"] {
        border-radius: 16px !important;
        border: 2.5px dashed #ffb3d9 !important;
        background: #fff6fb !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        font-family: 'Jua', sans-serif !important;
        border-radius: 999px !important;
        border: 2px solid #ff9fd8 !important;
        background: #ffffff !important;
        color: #ff3d97 !important;
        box-shadow: 0 2px 6px rgba(120,60,110,.15) !important;
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
    "111111111",
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
    line2 = [("트", "#FF5D8F", -6), ("래", "#FF8A3D", 5), ("블", "#FFC13B", -7),
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
    col_sw, col_btn, col_off = st.columns([1, 3.3, 1], vertical_alignment="center")
    with col_sw:
        html_block(
            f'<div style="width:100%;height:3.4rem;display:flex;align-items:center;'
            f'justify-content:center;font-size:4rem;line-height:1;overflow:visible;">{catalog["icon"]}</div>'
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
            row_items = list(enumerate(items))[start:start + per_row]
            cols = st.columns(per_row)
            for col, (idx, item) in zip(cols, row_items):
                with col:
                    unlocked_item = is_closet_item_unlocked(item["id"], idx)
                    selected = unlocked_item and current == item["id"]
                    border = "4px solid #ff6fb8" if selected else "3px solid rgba(0,0,0,.08)"
                    shadow = "0 0 0 3px #fff, 0 6px 14px rgba(255,111,184,.4)" if selected else "0 3px 8px rgba(0,0,0,.1)"
                    icon_svg = item_icon_svg(cat_key, item)
                    lock_badge = (
                        '<div style="position:absolute;top:6px;right:6px;width:26px;height:26px;'
                        'border-radius:50%;background:#fff;border:2px solid #ff6fb8;display:flex;'
                        'align-items:center;justify-content:center;font-size:14px;'
                        'box-shadow:0 2px 4px rgba(0,0,0,.25);z-index:2;">🔒</div>'
                        if not unlocked_item else ""
                    )
                    icon_opacity = "opacity:.45;filter:grayscale(.3);" if not unlocked_item else ""
                    html_block(
                        f'<div style="position:relative;width:100%;aspect-ratio:1;border-radius:14px;'
                        f'background:#faf7f2;display:flex;align-items:center;justify-content:center;'
                        f'padding:10px;box-sizing:border-box;border:{border};box-shadow:{shadow};">'
                        f'<div style="width:100%;height:100%;{icon_opacity}">{icon_svg}</div>'
                        f'{lock_badge}</div>'
                    )
                    btn_label = item["label"] if unlocked_item else f"🔒 {item['label']}"
                    if st.button(btn_label, key=f"pick_{item['id']}", use_container_width=True):
                        if unlocked_item:
                            bucket_dict = dict(draft.get(bucket) or {})
                            bucket_dict[cat_key] = None if bucket_dict.get(cat_key) == item["id"] else item["id"]
                            draft[bucket] = bucket_dict
                        else:
                            st.session_state.confirming_closet_unlock = item["id"]
                        st.rerun()

        confirming_id = st.session_state.confirming_closet_unlock
        confirming_item = next((i for i in items if i["id"] == confirming_id), None)
        if confirming_item:
            st.divider()
            st.markdown(
                f"**{confirming_item['label']}** — {CLOSET_UNLOCK_COST_COINS}코인을 사용하여 오픈하시겠습니까?"
            )
            c1, c2 = st.columns(2)
            with c1:
                can_afford = st.session_state.coins >= CLOSET_UNLOCK_COST_COINS
                if st.button("예", key="confirm_closet_unlock_yes", type="primary",
                             use_container_width=True, disabled=not can_afford):
                    st.session_state.coins -= CLOSET_UNLOCK_COST_COINS
                    st.session_state.unlocked_closet_items.add(confirming_id)
                    st.session_state.coin_history.append({
                        "amount": -CLOSET_UNLOCK_COST_COINS,
                        "label": f"👕 {confirming_item['label']} 잠금 해제",
                        "when": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                    st.session_state.confirming_closet_unlock = None
                    st.rerun()
                if not can_afford:
                    st.caption("코인이 부족해요 — 광고를 보고 코인을 모아보세요 🎬")
            with c2:
                if st.button("아니오", key="confirm_closet_unlock_no", use_container_width=True):
                    st.session_state.confirming_closet_unlock = None
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
        /* 지구 + 여행 후 복귀 아이콘을 같이 담는 바깥 행 — 아이콘을 지구 오른쪽에
           절대좌표로 앉히기 위한 기준점(position:relative)이 필요해서 만든다. */
        .st-key-globe_stage_row {{ position: relative !important; width: 100% !important; }}
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
        /* 여행 후 피부 복귀 프로그램 아이콘 — 지구 오른쪽 가장자리와 화면(컨테이너)
           오른쪽 끝 사이의 "정중앙"에 절대좌표로 배치한다.
           지구 오른쪽 가장자리 = 50% + halfGlobe, 화면 오른쪽 끝 = 100%이므로
           그 중점 = 75% + halfGlobe/2. left는 이 중점 값을 그대로 쓰고, 아이콘
           자신은 translate(-50%,-50%)로 가로/세로 모두 그 점을 중심으로 앉힌다
           (전에는 지구 바로 옆에 28px만 띄워서 너무 붙어 보였다).
           Streamlit이 각 위젯의 element-container에 기본으로 position:relative를
           걸어두기 때문에, 버튼에 position:absolute를 줘도 기준점(containing
           block)이 globe_stage_row가 아니라 이 바로 위 element-container가 되어버려
           지구 옆이 아니라 자기 자리(지구 아래, 왼쪽 정렬)에 그대로 눌러앉는 버그가
           있었다 — element-container의 position을 static으로 되돌려 기준점이 한 단계
           위 globe_stage_row(position:relative)로 올라가도록 고쳤다. */
        .st-key-open_recovery_from_globe {{ position: static !important; }}
        .st-key-open_recovery_from_globe.st-key-open_recovery_from_globe button {{
            position: absolute !important;
            top: calc(14px + clamp(165px, 34.5vw, {_MAP_GLOBE_MAX_PX // 2}px)) !important;
            left: calc(75% + clamp(165px, 34.5vw, {_MAP_GLOBE_MAX_PX // 2}px) / 2) !important;
            transform: translate(-50%, -50%) !important;
            width: clamp(72px, 10vw, 108px) !important; height: clamp(72px, 10vw, 108px) !important;
            min-width: 0 !important; max-width: none !important;
            border-radius: 0 !important; border: none !important; padding: 0 !important;
            background: none !important;
            background-image: url('{HOME_ICON_URI}') !important;
            background-size: contain !important; background-position: center !important;
            background-repeat: no-repeat !important;
            color: transparent !important; font-size: 0 !important; overflow: visible !important;
            filter: drop-shadow(0 4px 10px rgba(120,40,90,.25));
            transition: transform .12s ease;
            z-index: 5;
        }}
        .st-key-open_recovery_from_globe.st-key-open_recovery_from_globe button:hover {{
            transform: translate(-50%, -50%) scale(1.06) !important;
        }}
        .st-key-open_recovery_from_globe.st-key-open_recovery_from_globe button:active {{
            transform: translate(-50%, -50%) scale(.96) !important;
        }}
        </style>
        <div class="map-globe-hint">🌍 지구를 눌러 세계지도를 펼쳐보세요</div>
        """
    )
    with st.container(key="globe_stage_row"):
        if st.button(" ", key="open_world_map"):
            st.session_state.map_globe_opened = True
            st.rerun()
        if st.button(" ", key="open_recovery_from_globe", help="여행 후 피부 복귀 프로그램"):
            st.session_state.recovery_stage = "pick_trip"
            goto("recovery")
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
                pin_label = c["flag"] if is_country_unlocked(code) else "🔒"
                pin_help = c["name"] if is_country_unlocked(code) else f"{c['name']} · 잠김 (코인 {UNLOCK_COST_COINS}개로 해제)"
                if st.button(pin_label, key=f"pin_{code}", help=pin_help):
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
    get_skin_baseline()이 반환하는 baseline을 입력값으로 쓴다 — 카메라 스캔
    결과가 있으면 자가응답 피부타입 대신 스캔 5개 지표를 우선한다."""
    baseline = get_skin_baseline(char)
    tips = []
    if baseline["baseline_source"] == "camera_scan":
        if baseline["hydration"] <= 40:
            tips.append("고보습 크림·오일로 수분 방어막을 단단히 챙기세요")
        if baseline["oiliness"] >= 60:
            tips.append("가벼운 젤·워터 타입으로 유분 밸런스를 잡아주세요")
        if baseline["redness"] >= 60:
            tips.append("저자극·무향 성분 위주로 챙기세요")
        if baseline["pore_visibility"] >= 60 or baseline["texture_evenness"] <= 40:
            tips.append("살리실릭·티트리 등 모공·결 케어 성분을 곁들이면 좋아요")
        if not tips:
            tips.append("전반적으로 균형 잡힌 피부예요, 기본 보습만 챙기면 충분해요")
    else:
        base = {
            "건성": "고보습 크림·오일로 수분 방어막을 단단히 챙기세요",
            "지성": "가벼운 젤·워터 타입으로 유분 밸런스를 잡아주세요",
            "복합성": "부위별로 보습과 유분 조절 제품을 나눠 쓰는 게 좋아요",
        }
        tips.append(base.get(baseline["skin_type"], base["복합성"]))
        if "민감성" in baseline["extras"]:
            tips.append("저자극·무향 성분 위주로 챙기세요")
        if "트러블" in baseline["extras"]:
            tips.append("살리실릭·티트리 등 트러블 케어 성분을 곁들이면 좋아요")
    if country.get("essentials"):
        tips.append(f"현지 추천템: {country['essentials'][0]}")
    return tips


def _render_skin_scan_section():
    """피부 맞춤 추천 시트 상단에 붙는 얼굴 스캔 UI. 정면→왼쪽→오른쪽 순서로
    한 장씩 st.camera_input()으로 촬영을 받는다(실시간 프레임 분석/자동 캡처는
    Streamlit이 지원하지 않아 매 각도마다 촬영 버튼을 누르는 방식). 스캔은
    선택 사항이라 하지 않아도 온보딩 자가응답 기반 추천은 항상 그대로 동작한다."""
    if st.session_state.skin_scan_analyzing:
        with st.spinner("🔍 피부 스캔 분석 중..."):
            time.sleep(random.uniform(2.0, 3.0))
            st.session_state.skin_scan = analyze_skin_scan(st.session_state.skin_scan_photos)
        st.session_state.skin_scan_analyzing = False
        st.session_state.skin_scan_ui_open = False
        st.toast("✅ 3장 스캔 완료! 더 정확한 추천으로 갱신했어요")
        st.rerun()
        return

    if st.session_state.skin_scan:
        st.success("📸 카메라 스캔(정면·좌우) 기반으로 추천을 갱신했어요")
        if st.button("다시 스캔하기", key="skin_scan_retake_all"):
            st.session_state.skin_scan = None
            st.session_state.skin_scan_photos = {}
            st.session_state.skin_scan_step = 0
            st.session_state.skin_scan_ui_open = True
            st.session_state.skin_scan_widget_key += 1
            st.rerun()
        st.divider()
        return

    if not st.session_state.skin_scan_ui_open:
        if st.button(
            "🤳 내 피부 스캔하고 더 정확한 추천 받기",
            key="skin_scan_open_btn",
            use_container_width=True,
        ):
            st.session_state.skin_scan_ui_open = True
            st.session_state.skin_scan_step = 0
            st.session_state.skin_scan_photos = {}
            st.rerun()
        st.divider()
        return

    step = st.session_state.skin_scan_step
    angle = SCAN_ANGLES[step]
    st.caption(f"📸 {step + 1}/3 · {angle['label']} — {angle['guide']}")
    html_block(_CAMERA_MIRROR_CSS)
    photo = st.camera_input(
        angle["label"],
        key=f"skin_scan_cam_{angle['key']}_{st.session_state.skin_scan_widget_key}",
        label_visibility="collapsed",
    )
    if photo is not None:
        img = Image.open(photo).convert("RGB")
        ok, msg = _scan_quality_check(img)
        if not ok:
            st.warning(msg)
            if st.button("다시 찍기", key=f"skin_scan_retry_{angle['key']}"):
                st.session_state.skin_scan_widget_key += 1
                st.rerun()
        else:
            st.session_state.skin_scan_photos[angle["key"]] = img
            if step + 1 < len(SCAN_ANGLES):
                st.session_state.skin_scan_step += 1
                st.session_state.skin_scan_widget_key += 1
            else:
                st.session_state.skin_scan_analyzing = True
            st.rerun()
    if st.button("취소", key="skin_scan_cancel_btn"):
        st.session_state.skin_scan_ui_open = False
        st.session_state.skin_scan_photos = {}
        st.session_state.skin_scan_step = 0
        st.rerun()
    st.divider()


def _render_unlock_burst_stage(country, code):
    """잠금 해제 버튼을 누른 바로 다음 rerun에 표시 — 방금까지 자물쇠가 떠 있던
    '같은 핑크 박스'(.locked-stage, 크기/위치 그대로)가 그 자리에서 점점 세게
    떨리며 하얗게 변하고, 다 하얘지는 순간 자물쇠가 사라지며 폭죽과 무지개색
    큰 문구가 터진다. 별도 오버레이 박스를 새로 띄우는 게 아니라 같은 박스를
    이어서 그리는 것이라 화면 한가운데 작은 박스가 갑자기 나타나는 문제가 없다.
    화면 전환 버블/바텀시트와 같은 '재생 시간만큼 sleep 후 rerun' 패턴을 쓴다."""
    st.title(f"{country['flag']} {country['name']}")

    SHAKE_S = 1.1  # 흔들림+화이트아웃이 끝나는 시점 — 폭죽/문구가 이 시점에 맞춰 터진다
    HOLD_S = 1.8   # 폭죽·문구가 다 보인 다음 실제 페이지로 넘어가기 전 대기 시간
    pieces = []
    n = 40  # 폭죽 조각 수를 늘리고 더 멀리·크게 날려서 훨씬 화려하게 "터지는" 느낌을 낸다
    for i in range(n):
        angle = math.radians((360 / n) * i + random.uniform(-12, 12))
        dist = random.uniform(220, 460)
        dx = round(math.cos(angle) * dist, 1)
        dy = round(math.sin(angle) * dist, 1)
        size = round(random.uniform(10, 22), 1)
        color = random.choice(COIN_CELEBRATION_COLORS)
        delay = SHAKE_S + round(random.uniform(0, 0.12), 2)
        dur = round(random.uniform(0.9, 1.4), 2)
        rot = round(random.uniform(200, 760))
        radius = "50%" if i % 3 == 0 else "3px"
        pieces.append(
            f'<span class="unlock-confetti-piece" style="--dx:{dx}px; --dy:{dy}px; --rot:{rot}deg; '
            f'width:{size}px; height:{size}px; background:{color}; border-radius:{radius}; '
            f'animation-delay:{delay}s; animation-duration:{dur}s;"></span>'
        )

    html_block(
        f"""
        <style>
        .locked-stage {{
            position: relative; width: 100%; height: clamp(420px, 74vh, 680px);
            border-radius: 22px; margin-bottom: 14px; overflow: hidden;
            background: linear-gradient(160deg, #ffe9f3 0%, #ffd3e7 55%, #ffbadc 100%);
            box-shadow: inset 0 0 0 4px rgba(255,255,255,.55), 0 16px 32px rgba(150,50,100,.25);
            display: flex; align-items: center; justify-content: center;
            animation: unlock-box-pulse {SHAKE_S}s ease-in-out both;
        }}
        /* 박스 자체는 스케일(중심 기준)로만 살짝 들썩여서 절대 좌우로 밀리지
           않게 하고, 흔들리는 느낌은 자물쇠 이모지 쪽에서 회전으로만 표현한다
           (translate를 쓰면 박스/이모지가 카드 밖으로 밀려 나가 왼쪽으로 쏠려
           보이는 문제가 있었음 — 회전·스케일은 중심이 고정이라 그 문제가 없다) */
        @keyframes unlock-box-pulse {{
            0%, 100% {{ transform: scale(1); }}
            20%  {{ transform: scale(1.006); }}
            40%  {{ transform: scale(1.002); }}
            60%  {{ transform: scale(1.014); }}
            80%  {{ transform: scale(1.006); }}
            92%  {{ transform: scale(1.022); }}
        }}
        .unlock-whiteout {{
            position: absolute; inset: 0; background: #fff; opacity: 0; z-index: 1;
            animation: unlock-whiteout-in {SHAKE_S}s ease-in forwards;
        }}
        @keyframes unlock-whiteout-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        .unlock-lock-icon {{
            position: relative; z-index: 2; font-size: min(32vw, 190px); line-height: 1;
            filter: drop-shadow(0 12px 20px rgba(150,50,100,.35));
            transform-origin: 50% 50%;
            animation:
                unlock-icon-shake {SHAKE_S - 0.15}s ease-in-out both,
                unlock-icon-vanish .3s ease-in {SHAKE_S - 0.15}s both;
        }}
        @keyframes unlock-icon-shake {{
            0%   {{ transform: rotate(0deg); }}
            10%  {{ transform: rotate(-3deg); }}
            20%  {{ transform: rotate(3deg); }}
            30%  {{ transform: rotate(-5deg); }}
            40%  {{ transform: rotate(5deg); }}
            50%  {{ transform: rotate(-7deg); }}
            60%  {{ transform: rotate(7deg); }}
            70%  {{ transform: rotate(-9deg); }}
            80%  {{ transform: rotate(9deg); }}
            90%  {{ transform: rotate(-12deg); }}
            100% {{ transform: rotate(0deg); }}
        }}
        @keyframes unlock-icon-vanish {{
            0%   {{ transform: scale(1) rotate(0deg); opacity: 1; }}
            100% {{ transform: scale(0) rotate(35deg); opacity: 0; }}
        }}
        .unlock-shockwave {{
            position: absolute; top: 50%; left: 50%; z-index: 2;
            width: 40px; height: 40px; margin: -20px 0 0 -20px;
            border-radius: 50%; border: 6px solid #fff;
            opacity: 0;
            animation: unlock-shockwave-ring .7s cubic-bezier(.1,.7,.3,1) {SHAKE_S}s both;
        }}
        @keyframes unlock-shockwave-ring {{
            0%   {{ transform: scale(.3); opacity: .9; }}
            100% {{ transform: scale(9); opacity: 0; }}
        }}
        .unlock-confetti-piece {{
            position: absolute; top: 50%; left: 50%; border-radius: 3px; z-index: 3;
            transform: translate(-50%,-50%); opacity: 0;
            animation-name: unlock-confetti-burst; animation-timing-function: cubic-bezier(.15,.75,.25,1);
            animation-fill-mode: both;
        }}
        @keyframes unlock-confetti-burst {{
            0%   {{ transform: translate(-50%,-50%) scale(1) rotate(0deg); opacity: 1; }}
            60%  {{ opacity: 1; }}
            100% {{
                transform: translate(calc(-50% + var(--dx)), calc(-50% + var(--dy))) scale(.6) rotate(var(--rot));
                opacity: 0;
            }}
        }}
        .unlock-burst-text {{
            position: relative; z-index: 4; text-align: center; padding: 0 4vw;
            font-family: 'Jua', sans-serif; font-weight: 900;
            font-size: clamp(2.8rem, 11.5vw, 6.4rem);
            background: linear-gradient(90deg,#ff3d97,#ff9f1c,#ffe94d,#4ade80,#38bdf8,#a78bfa,#ff3d97);
            background-size: 300% auto; -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent; color: transparent;
            -webkit-text-stroke: 4px rgba(255,255,255,.95); paint-order: stroke fill;
            filter: drop-shadow(0 10px 22px rgba(120,20,70,.4));
            opacity: 0;
            animation:
                unlock-text-pop .85s cubic-bezier(.2,1.8,.35,1) {SHAKE_S}s both,
                unlock-text-wiggle 1.8s ease-in-out {SHAKE_S + 0.85}s infinite,
                unlock-text-rainbow 1.2s linear {SHAKE_S}s infinite;
        }}
        @keyframes unlock-text-pop {{
            0%   {{ transform: scale(.1) rotate(-10deg); opacity: 0; }}
            50%  {{ transform: scale(1.35) rotate(4deg); opacity: 1; }}
            70%  {{ transform: scale(.9) rotate(-3deg); }}
            85%  {{ transform: scale(1.1) rotate(1.5deg); }}
            100% {{ transform: scale(1) rotate(0deg); opacity: 1; }}
        }}
        @keyframes unlock-text-wiggle {{
            0%, 100% {{ transform: scale(1) rotate(0deg); }}
            25%      {{ transform: scale(1.05) rotate(-2deg); }}
            50%      {{ transform: scale(1) rotate(0deg); }}
            75%      {{ transform: scale(1.05) rotate(2deg); }}
        }}
        @keyframes unlock-text-rainbow {{
            0%   {{ background-position: 0% 50%; }}
            100% {{ background-position: 300% 50%; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .locked-stage, .unlock-whiteout, .unlock-lock-icon, .unlock-shockwave,
            .unlock-confetti-piece, .unlock-burst-text {{ animation: none !important; opacity: 1; }}
        }}
        </style>
        <div class="locked-stage">
            <div class="unlock-whiteout"></div>
            <div class="unlock-lock-icon">🔒</div>
            <div class="unlock-shockwave"></div>
            {"".join(pieces)}
            <div class="unlock-burst-text">오픈되었습니다!!</div>
        </div>
        """
    )
    time.sleep(SHAKE_S + HOLD_S)
    st.session_state.unlock_burst_active = None
    st.rerun()


def _render_country_locked(country, code):
    """잠긴 여행지 화면 — 파스텔 핑크 배경에 자물쇠만 크게 보이고, 포스트잇/지도/
    포션 같은 다른 정보는 전부 가린다. '50코인 사용하여 오픈하기' -> 예/아니오 확인
    -> 예를 누르면 코인을 차감하고 st.session_state.unlocked_countries에 코드를
    남겨 이후로는 계속 잠금 없이 볼 수 있다."""
    st.title(f"{country['flag']} {country['name']}")
    html_block(
        """
        <style>
        .locked-stage {
            position: relative; width: 100%; height: clamp(420px, 74vh, 680px);
            border-radius: 22px; margin-bottom: 14px;
            background: linear-gradient(160deg, #ffe9f3 0%, #ffd3e7 55%, #ffbadc 100%);
            box-shadow: inset 0 0 0 4px rgba(255,255,255,.55), 0 16px 32px rgba(150,50,100,.25);
            display: flex; align-items: center; justify-content: center;
        }
        .locked-icon {
            font-size: min(32vw, 190px); line-height: 1;
            filter: drop-shadow(0 12px 20px rgba(150,50,100,.35));
        }
        .unlock-confirm-text {
            text-align: center; font-family: 'Jua', sans-serif; font-size: 1.25rem;
            color: #9c2f5c; margin: 4px 0 14px;
        }
        </style>
        <div class="locked-stage"><div class="locked-icon">🔒</div></div>
        """
    )

    if st.session_state.confirming_unlock == code:
        html_block(
            f'<div class="unlock-confirm-text">{UNLOCK_COST_COINS}코인을 사용하여 오픈하시겠습니까?</div>'
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("예", key="confirm_unlock_yes", type="primary", use_container_width=True):
                st.session_state.coins -= UNLOCK_COST_COINS
                st.session_state.unlocked_countries.add(code)
                st.session_state.coin_history.append({
                    "amount": -UNLOCK_COST_COINS,
                    "label": f"{country['flag']} {country['name']} 잠금 해제",
                    "when": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                st.session_state.confirming_unlock = None
                st.session_state.unlock_burst_active = code
                st.rerun()
        with c2:
            if st.button("아니오", key="confirm_unlock_no", use_container_width=True):
                st.session_state.confirming_unlock = None
                st.rerun()
    else:
        can_afford = st.session_state.coins >= UNLOCK_COST_COINS
        if st.button(f"{UNLOCK_COST_COINS}코인 사용하여 오픈하기", key="unlock_country_btn",
                     type="primary", use_container_width=True, disabled=not can_afford):
            st.session_state.confirming_unlock = code
            st.rerun()
        if not can_afford:
            st.caption("코인이 부족해요 — 광고를 보고 코인을 모아보세요 🎬")
        if st.button("⬅ 지도로 돌아가기", key="back_from_locked", use_container_width=True):
            goto("map")
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

    if st.session_state.unlock_burst_active == code:
        _render_unlock_burst_stage(country, code)
        return

    if not is_country_unlocked(code):
        _render_country_locked(country, code)
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


def _weather_condition_emoji(condition_main):
    """OpenWeatherMap의 weather[0].main(영문 대분류)을 날씨 이모지로 변환."""
    return {
        "Clear": "☀️", "Clouds": "⛅", "Rain": "🌧️", "Drizzle": "🌦️",
        "Thunderstorm": "⛈️", "Snow": "❄️", "Mist": "🌫️", "Fog": "🌫️",
        "Haze": "🌫️", "Dust": "🌫️", "Sand": "🌫️", "Smoke": "🌫️", "Tornado": "🌪️",
    }.get(condition_main, "🌡️")


def _pm_grade(aqi_1to5):
    """OpenWeatherMap 대기질 지수(1~5)를 좋음/보통/나쁨 3단계 + 색 이모지로 단순화."""
    if aqi_1to5 in (1, 2):
        return "🟢", "좋음"
    if aqi_1to5 == 3:
        return "🟡", "보통"
    if aqi_1to5 in (4, 5):
        return "🔴", "나쁨"
    return "", ""


def _render_country_title_with_clock(country, live_weather, live_pollution):
    """국가/도시 이름 바로 옆(같은 줄)에 놓는 실시간 기온·습도·자외선·미세먼지 패널.
    사용자가 준 참고 사진(나무 프레임 안에 크림색으로 빛나는 7세그먼트 LED 디지털
    시계) 느낌을 내려고, 어두운 창 안에 따뜻한 크림색 글로우 숫자를 넣고 나무
    톤 프레임으로 감쌌다. 값을 못 가져온 자리는 "--"로 비워둔다.

    st.title()을 st.columns로 옆에 나란히 놓으면 컬럼이 나라 이름 글자 수와 무관하게
    항상 화면 폭의 고정 비율을 차지해서, 이름이 짧은 나라(예: "한국 · 서울")에서는
    시계가 이름과 한참 떨어진 오른쪽 끝에 붙어 보이는 문제가 있었다 — 그래서 제목
    글자 자체도 st.title 대신 이 함수 안에서 커스텀 <h1>으로 그려서, 시계와 같은
    flex row 안에 넣어 항상 글자 바로 옆에 붙게 만들었다(폭은 내용에 맞춰 줄어듦).
    <h1> 스타일은 Streamlit 기본 st.title의 실측 스타일(44px/700/#31333F)을 그대로
    옮겨서 원래 제목과 똑같아 보이게 했다."""
    temp_val = f'{live_weather["temp"]:.0f}°' if live_weather and live_weather.get("temp") is not None else "--"
    humidity_val = f'{live_weather["humidity"]}%' if live_weather and live_weather.get("humidity") is not None else "--"
    uv_val = f'{live_weather["uvi"]:.0f}' if live_weather and live_weather.get("uvi") is not None else "--"
    pm_val = (
        f'{live_pollution["pm2_5"]:.0f}' if live_pollution and live_pollution.get("pm2_5") is not None else "--"
    )
    weather_emoji = _weather_condition_emoji(live_weather.get("condition")) if live_weather else "🌡️"
    weather_desc = (live_weather.get("description") or "--") if live_weather else "--"
    pm_emoji, pm_label = _pm_grade(live_pollution.get("aqi")) if live_pollution else ("", "")

    def _cell(label, value, sub=None):
        sub_html = f'<div class="live-digit-sub">{html.escape(sub)}</div>' if sub else ""
        return (
            f'<div class="live-digit-cell"><div class="live-digit-value">{html.escape(str(value))}</div>'
            f'{sub_html}'
            f'<div class="live-digit-label">{html.escape(label)}</div></div>'
        )

    cells = (
        _cell("날씨", weather_emoji, sub=weather_desc)
        + _cell("TEMP", temp_val)
        + _cell("HUMID", humidity_val)
        + _cell("UV", uv_val)
        + _cell("PM2.5", pm_val, sub=(f"{pm_emoji} {pm_label}" if pm_label else None))
    )

    # 새로고침 버튼을 누른 직후 한 번만 시계 패널에 반짝이는 테두리 플래시를
    # 준다 — "업데이트를 눌렀는데 포스트잇이 반짝인다"는 지적처럼, 업데이트
    # 피드백은 실제로 갱신되는 시계 쪽에 있어야 한다(포스트잇의 유의사항 pulse는
    # 미세먼지 경보용으로 항상 따로 도는 애니메이션이라 이것과는 무관하다).
    just_refreshed = st.session_state.get("just_refreshed_live_clock", False)
    st.session_state.just_refreshed_live_clock = False
    flash_rule = "animation: live-clock-flash .7s ease;" if just_refreshed else ""

    with st.container(key="live_clock_wrap"):
        html_block(
            f"""
            <style>
            .st-key-live_clock_wrap {{ margin-bottom: 6px; }}
            .country-title-row {{ display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }}
            .country-title-text {{
                font-family: "Source Sans", sans-serif; font-size: 44px; font-weight: 700;
                color: rgb(49, 51, 63); margin: 0; line-height: 52.8px;
            }}
            .live-clock-frame {{
                display: inline-flex; gap: 10px; background: linear-gradient(160deg,#d8bd8e,#a9814f);
                border-radius: 14px; padding: 12px 16px;
                box-shadow: 0 8px 18px rgba(90,60,20,.35), inset 0 2px 0 rgba(255,255,255,.3);
                border: 3px solid #8a6a3f; {flash_rule}
            }}
            @keyframes live-clock-flash {{
                0%   {{ box-shadow: 0 0 0 7px rgba(255,255,255,.85), 0 8px 18px rgba(90,60,20,.35); }}
                100% {{ box-shadow: 0 0 0 0 rgba(255,255,255,0), 0 8px 18px rgba(90,60,20,.35); }}
            }}
            .live-digit-cell {{
                background: #26221e; border-radius: 8px; padding: 8px 14px 6px; text-align: center;
                box-shadow: inset 0 2px 6px rgba(0,0,0,.6); min-width: 62px;
            }}
            .live-digit-value {{
                font-family: 'Share Tech Mono', monospace; font-size: 1.6rem; font-weight: 700;
                color: #f5f1e0; text-shadow: 0 0 6px rgba(245,241,224,.85), 0 0 16px rgba(245,241,224,.5);
                letter-spacing: 1px; line-height: 1.1;
            }}
            .live-digit-sub {{
                font-family: 'Jua', sans-serif; font-size: .68rem; color: #f5f1e0;
                margin-top: 2px; white-space: nowrap;
            }}
            .live-digit-label {{
                font-family: 'Jua', sans-serif; font-size: .58rem; color: #cbb98a;
                margin-top: 2px; letter-spacing: .5px;
            }}
            .st-key-refresh_live_weather button {{
                width: 34px !important; height: 34px !important; min-width: 0 !important;
                border-radius: 50% !important; padding: 0 !important; font-size: 1rem !important;
                background: #fff !important; border: 2px solid #ff9fd8 !important;
                box-shadow: 0 3px 8px rgba(120,60,110,.28) !important; color: #ff6fb8 !important;
                transition: transform .2s ease; margin-top: 6px;
            }}
            .st-key-refresh_live_weather button:hover {{ transform: rotate(90deg) scale(1.08); }}
            .st-key-refresh_live_weather button:active {{ transform: rotate(180deg) scale(.92); }}
            </style>
            <div class="country-title-row">
                <h1 class="country-title-text">{html.escape(country['flag'])} {html.escape(country['name'])}</h1>
                <div class="live-clock-frame">{cells}</div>
            </div>
            """
        )
        if st.button("🔄", key="refresh_live_weather", help="실시간 정보 새로고침"):
            st.session_state["_live_weather_cache"] = {}
            st.session_state["_live_air_pollution_cache"] = {}
            st.session_state.just_refreshed_live_clock = True
            st.rerun()


def _country_info_note_body(country, tips, risk_class, risk_text):
    """안내(노란) 포스트잇의 내용 — 작은 카드와 크게 보기 다이얼로그가 그대로 재사용한다."""
    return f"""
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
    """


def _country_warning_note_body(wp, wing, winfo):
    """경고(분홍) 포스트잇의 내용 — 작은 카드와 크게 보기 다이얼로그가 그대로 재사용한다."""
    return f"""
    <div class="note-title">⚠️ 반입 주의</div>
    <div class="note-line" style="font-weight:700;">{html.escape(wp["brand"])} · {html.escape(wp["name"])}</div>
    <div class="note-line">성분: {html.escape(wing)}</div>
    <div class="note-section">왜 주의해야 하나요?</div>
    <div class="note-line">{html.escape(winfo["reason"])}</div>
    <div class="note-section">출처</div>
    <div class="note-line" style="font-size:1.05rem;opacity:.85;">{html.escape(winfo["source"])}</div>
    """


def _dismiss_expanded_country_note():
    st.session_state.expanded_country_note = None


@st.dialog(" ", width="large", on_dismiss=_dismiss_expanded_country_note)
def _expanded_country_note_dialog(which, info_body, warning_body):
    """포스트잇을 눌렀을 때 같은 내용을 화면 중앙에 훨씬 크게 띄운다 — 포스트잇
    디자인/색은 그대로 두고 글자와 카드만 확대해서 겹쳐서 안 보이던 내용을
    편하게 읽을 수 있게 한다."""
    is_warning = which == "warning"
    body = warning_body if is_warning else info_body
    css_class = "country-warning-note" if is_warning else "country-sticky-note"
    html_block(
        f"""
        <style>
        div[data-testid="stDialog"] [slot="title"] {{ display: none !important; }}
        div[data-testid="stDialog"] > div {{
            max-width: min(94vw, 640px) !important; width: min(94vw, 640px) !important;
        }}
        .expanded-note-card {{
            position: static !important; top: auto !important; right: auto !important;
            width: auto !important; max-width: 100% !important;
            padding: 34px 34px 26px; border-radius: 18px;
            font-family: 'Gaegu', cursive; transform: none !important;
            box-shadow: 0 20px 50px rgba(0,0,0,.4);
        }}
        .expanded-note-card.country-sticky-note {{ background: #fff7c2; color: #4a3a1a; }}
        .expanded-note-card.country-warning-note {{ background: #ffe3df; color: #7a2020; }}
        .expanded-note-card .note-title {{ font-size: 2.6rem; margin-bottom: 16px; }}
        .expanded-note-card .note-section {{ font-size: 1.6rem; margin: 20px 0 6px; }}
        .expanded-note-card .note-line {{ font-size: 1.6rem; line-height: 1.6; margin: 0 0 6px; }}
        </style>
        <div class="expanded-note-card {css_class}">{body}</div>
        """
    )
    if st.button("✕ 닫기", key="close_expanded_note", use_container_width=True):
        st.session_state.expanded_country_note = None
        st.rerun()


def _render_country_map_stage(country, char, code):
    """1단계 — 그 나라만 확대된 지도 + 옆에 붙은 포스트잇(환경/피부타입 추천/유의사항).
    지도 자체가 곧 버튼(다른 화면에서 이미 검증된 '그림=버튼' 방식) — 탭하면 2단계로."""
    # 국가/도시 이름 바로 옆에 복고풍 디지털시계 느낌의 패널로 실시간 기온·습도·
    # 자외선·미세먼지를 보여준다(참고 사진의 나무 프레임 LED 시계 스타일). 포스트잇
    # 팝업 쪽은 원래 문구 그대로 두고 건드리지 않는다.
    live_weather = get_live_weather(country.get("geo"))
    live_pollution = get_live_air_pollution(country.get("geo"))
    _render_country_title_with_clock(country, live_weather, live_pollution)

    zoom_uri = _country_zoom_crop_uri(code)
    tips = _quick_skin_tip(char, country)
    risk = get_skin_risk_note(code, country)
    risk_alert = risk["linked_to"] == "aqi" and _is_aqi_severe(country)

    html_block(
        f"""
        <style>
        .st-key-country_stage_wrap {{ position: relative !important; }}
        /* Streamlit이 html_block() 하나마다 만드는 stElementContainer 래퍼에
           기본으로 position:relative를 주는데, 그 래퍼 자체는 높이가 0이라
           (내용물인 포스트잇이 absolute라 정상 흐름에 안 잡힘) 포스트잇의
           top:%가 이 래퍼(0px) 기준으로 계산돼 늘 0으로 뭉개지는 버그가 있었다.
           :has()로 포스트잇을 담은 래퍼만 짚어 static으로 되돌려서, 포스트잇의
           위치 기준이 진짜 원하는 조상(country_stage_wrap)이 되게 한다. */
        .st-key-country_stage_wrap > div:has(.country-sticky-note),
        .st-key-country_stage_wrap > div:has(.country-warning-note) {{
            position: static !important;
        }}
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
        /* 전략 미션(국가별 규제 충돌) — 반입 주의 경고 포스트잇. 기존 안내 포스트잇과
           약 절반쯓 겹치도록 아래-왼쪽으로 offset을 줬고, 색을 빨간 계열로 달리해서
           "경고"라는 걸 한눈에 구분할 수 있게 했다. 내용이 길어도 넘치지 않도록
           기존 노트보다 폭을 조금 더 넓게 잡는다. */
        .country-warning-note {{
            position: absolute; top: 30%; right: 20%; width: min(480px, 66%);
            background: #ffe3df; padding: 26px 26px 22px; border-radius: 22px 6px 6px 22px;
            box-shadow: 6px 12px 26px rgba(0,0,0,.35); transform: rotate(-3deg);
            font-family: 'Gaegu', cursive; color: #7a2020; pointer-events: none; z-index: 7;
        }}
        /* 포스트잇을 겹쳐 보이게 하는 CSS만으로는(위치/회전/래퍼 이슈) 클릭
           영역을 안정적으로 맞추기 어려워서, 포스트잇 바로 아래 자연스러운
           위치에 작고 눈에 보이는 버튼을 따로 둔다 — 겹침/좌표 계산 없이
           항상 확실하게 눌린다. */
        .st-key-note_open_info button, .st-key-note_open_warning button {{
            font-family: 'Jua', sans-serif; font-size: 1rem;
        }}
        .country-warning-note::before {{
            content: '⚠️'; position: absolute; top: -20px; right: 24px; font-size: 2rem;
            transform: rotate(12deg);
        }}
        .country-warning-note .note-title {{ color: #c0392b; }}
        .country-warning-note .note-section {{ color: #a83226; }}
        /* 화면 왼쪽에 크게 반짝이는 포션 버튼 — 지도 자체가 버튼(enter_country_scene)
           이라 그 위에 올라오도록 z-index를 확실히 더 높게 준다. 포션은 은은하게
           빛나는 글로우(potion-glow-pulse)로, 옆의 별들은 각기 다른 타이밍으로
           반짝여서(sparkle-twinkle) "반짝반짝" 느낌을 낸다. */
        .st-key-open_country_potion {{
            position: absolute !important; top: 32%; left: 4%; z-index: 30 !important;
        }}
        .st-key-open_country_potion.st-key-open_country_potion button {{
            position: relative !important; width: 120px !important; height: 156px !important;
            min-width: 0 !important; background: transparent !important; border: none !important;
            padding: 0 !important; background-image: url('{POTION_ICON_URI}') !important;
            background-size: contain !important; background-repeat: no-repeat !important;
            background-position: center !important; color: transparent !important; font-size: 0 !important;
            animation: potion-glow-pulse 1.8s ease-in-out infinite;
        }}
        .st-key-open_country_potion.st-key-open_country_potion button:hover {{ transform: scale(1.08); }}
        .st-key-open_country_potion.st-key-open_country_potion button:active {{ transform: scale(.92); }}
        @keyframes potion-glow-pulse {{
            0%, 100% {{
                filter: drop-shadow(0 0 6px rgba(255,214,120,.55)) drop-shadow(0 0 14px rgba(255,111,184,.4));
                transform: scale(1);
            }}
            50% {{
                filter: drop-shadow(0 0 18px rgba(255,214,120,.95)) drop-shadow(0 0 30px rgba(255,111,184,.65));
                transform: scale(1.06);
            }}
        }}
        /* 반짝이는 별을 독립된 <span>으로 절대좌표(top/left %)를 줘서 배치했었는데,
           그 span의 위치 기준(가장 가까운 relative 조상)이 실제로는 포션 버튼과
           달라서 퍼센트가 서로 다른 박스를 기준으로 계산돼 포션에서 한참 떨어져
           보이는 버그가 있었다. 포션 버튼 자신의 ::before/::after로 붙이면 그
           버튼 자체가 기준 박스가 되어 항상 포션과 겹치게 붙어있는게 보장된다. */
        .st-key-open_country_potion.st-key-open_country_potion button::before,
        .st-key-open_country_potion.st-key-open_country_potion button::after {{
            content: '✨'; position: absolute; font-size: 1.8rem; line-height: 1; pointer-events: none;
            z-index: 29; animation: sparkle-twinkle 1.5s ease-in-out infinite;
            /* 버튼 자체가 글자를 숨기려고 color: transparent를 쓰고 있어서, 이 이모지도
               상속으로 투명해져 안 보이는 버그가 있었다 — 명시적으로 색을 되살린다. */
            color: initial !important; -webkit-text-fill-color: initial !important;
            filter: drop-shadow(0 0 4px rgba(255,255,255,.9));
        }}
        .st-key-open_country_potion.st-key-open_country_potion button::before {{
            top: -10px; left: -14px; animation-delay: 0s;
        }}
        .st-key-open_country_potion.st-key-open_country_potion button::after {{
            top: 58%; left: 80%; animation-delay: .6s;
        }}
        @keyframes sparkle-twinkle {{
            0%, 100% {{ opacity: .35; transform: scale(.7) rotate(0deg); }}
            50%      {{ opacity: 1;   transform: scale(1.2) rotate(20deg); }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .st-key-open_country_potion.st-key-open_country_potion button {{ animation: none !important; }}
            .st-key-open_country_potion.st-key-open_country_potion button::before,
            .st-key-open_country_potion.st-key-open_country_potion button::after {{ animation: none !important; }}
        }}
        </style>
        """
    )

    ingredient_warnings = _country_ingredient_warning_products(code)
    risk_class = "note-line risk-alert" if risk_alert else "note-line"
    risk_text = ("🔴 오늘 미세먼지 나쁨 — " if risk_alert else "") + risk["text"]
    info_body = _country_info_note_body(country, tips, risk_class, risk_text)
    warning_body = None
    if ingredient_warnings:
        wp, wing, winfo = ingredient_warnings[0]
        warning_body = _country_warning_note_body(wp, wing, winfo)

    with st.container(key="country_stage_wrap"):
        html_block(f'<div class="country-sticky-note">{info_body}</div>')
        if warning_body:
            html_block(f'<div class="country-warning-note">{warning_body}</div>')
        if st.button(" ", key="open_country_potion", help="포션을 눌러 피부 궁합 확인하기"):
            st.session_state.diagnosis_country = code
            st.session_state.diagnosis_stage = "scan"
            st.session_state.diagnosis_result = None
            goto("diagnosis")
            st.rerun()
        if st.button(" ", key="enter_country_scene"):
            st.session_state.country_stage = "scene"
            st.session_state.just_entered_country_scene = True
            st.rerun()

    note_btn_cols = st.columns(2) if warning_body else st.columns(1)
    with note_btn_cols[0]:
        if st.button("🔍 안내 포스트잇 크게 보기", key="note_open_info", use_container_width=True):
            st.session_state.expanded_country_note = "info"
            st.rerun()
    if warning_body:
        with note_btn_cols[1]:
            if st.button("🔍 반입 주의 포스트잇 크게 보기", key="note_open_warning", use_container_width=True):
                st.session_state.expanded_country_note = "warning"
                st.rerun()

    if st.button("⬅ 지도로 돌아가기", key="back_to_world_map"):
        goto("map")
        st.rerun()

    if st.session_state.expanded_country_note == "warning" and not warning_body:
        st.session_state.expanded_country_note = None
    if st.session_state.expanded_country_note:
        _expanded_country_note_dialog(st.session_state.expanded_country_note, info_body, warning_body)


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
            margin-bottom: 10px;
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
            font-size: min(60vw, 420px); opacity: .3; pointer-events: none; user-select: none;
        }}
        .scene-doll-box {{
            position: absolute; left: 50%; top: 52%; transform: translate(-50%,-50%);
            width: min(46vw, 260px); pointer-events: none; z-index: 2; opacity: 1;
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
        .st-key-icn_water {{ top: 5%; left: 27%; transform: translateX(-50%); }}
        .st-key-icn_lipstick {{ top: 5%; left: 73%; transform: translateX(-50%); }}
        .st-key-icn_shop {{ top: 39%; left: 15%; transform: translateX(-50%); }}
        .st-key-icn_hair {{ top: 39%; left: 85%; transform: translateX(-50%); }}
        .st-key-icn_carrier {{ top: 66%; left: 27%; transform: translateX(-50%); }}
        .st-key-icn_star {{ top: 66%; left: 73%; transform: translateX(-50%); }}
        /* 흰 원 배경 없이 이모지만 크게 — 자리에서 계속 살짝 흔들리도록 각자
           다른 딜레이로 같은 float 애니메이션을 건다(딜레이를 다르게 줘야 6개가
           똑같이 맞춰 움직이지 않고 자연스럽게 제각각 흔들린다). transform은
           애니메이션이 매 프레임 덮어써서 :hover/:active로는 못 건드리니,
           눌림 피드백은 filter(밝기)로 대신한다. */
        /* Streamlit이 버튼 글자를 <p>로 한 번 더 감싸는데, 그 <p>에 자체
           font-size(14px)가 박혀 있어서 button에 준 font-size가 상속되지 않고
           씹혀버린다 — 실제 이모지를 담은 p 태그까지 직접 짚어서 키운다. */
        /* 전역 보조 버튼 글씨 크기 규칙(button[kind="secondary"][kind="secondary"] p)이
           명시도가 더 높아서 이 규칙을 씹어버리는 문제가 있었다 -- 같은 트릭(속성
           선택자 반복)으로 명시도를 그보다 더 높여서 이겨야 실제로 커진다. */
        div[class*="st-key-icn_"] button[kind="secondary"][kind="secondary"] p {{
            font-size: clamp(3.8rem, 7.4vw, 9.2rem) !important; line-height: 1 !important;
        }}
        div[class*="st-key-icn_"] button {{
            width: clamp(90px, 14vw, 190px) !important; height: clamp(90px, 14vw, 190px) !important; min-width: 0 !important;
            padding: 0 !important;
            background: transparent !important; border: none !important; box-shadow: none !important;
            filter: drop-shadow(0 6px 10px rgba(60,30,60,.35));
            transition: filter .12s ease;
            animation: icon-float 3.2s ease-in-out infinite;
        }}
        div[class*="st-key-icn_"] button:hover {{ filter: drop-shadow(0 6px 10px rgba(60,30,60,.35)) brightness(1.15); }}
        div[class*="st-key-icn_"] button:active {{ filter: drop-shadow(0 6px 10px rgba(60,30,60,.35)) brightness(.85); }}
        @keyframes icon-float {{
            0%, 100% {{ transform: translateY(0) rotate(-5deg); }}
            50%      {{ transform: translateY(-10px) rotate(5deg); }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            div[class*="st-key-icn_"] button {{ animation: none !important; }}
        }}
        .st-key-icn_water button {{ animation-delay: 0s; }}
        .st-key-icn_lipstick button {{ animation-delay: .5s; }}
        .st-key-icn_shop button {{ animation-delay: 1s; }}
        .st-key-icn_hair button {{ animation-delay: 1.5s; }}
        .st-key-icn_carrier button {{ animation-delay: 2s; }}
        .st-key-icn_star button {{ animation-delay: 2.5s; }}
        .st-key-icn_star button {{
            {"filter: drop-shadow(0 0 14px rgba(255,190,60,.95)) !important;" if already_saved else ""}
        }}
        /* 저장 애니메이션이 없는 평소에도 opacity 기본값이 1이라 이 노란
           글로우가 캐릭터 위에 늘 얹혀서 색이 계속 뿌옇게 바래 보이던 버그가
           있었다 — 저장 순간 반짝일 때만 보이게 기본값을 0으로 둔다. */
        .scene-sparkle {{
            position: absolute; inset: 0; pointer-events: none; z-index: 8; opacity: 0;
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
        /* 하단에 딱 붙어서 눈에 잘 안 띈다는 피드백 — 화면 정중앙에 뜨도록 바꾸고,
           바닥에서 슬라이드업하던 애니메이션도 살짝 튕기며 커지는 팝인으로 교체.
           카드도 훨씬 크게, 글자도 전체적으로 키워서 가독성을 올렸다. */
        div[data-testid="stDialog"] > div {
            position: fixed !important; left: 50% !important; top: 50% !important; bottom: auto !important;
            transform: translate(-50%, -50%) !important; margin: 0 !important;
            max-width: min(96vw, 840px) !important; width: min(96vw, 840px) !important;
            max-height: 92vh !important; overflow-y: auto !important;
            border-radius: 18px !important;
            animation: sheet-pop-in .32s cubic-bezier(.2,.9,.3,1.25) both;
        }
        @keyframes sheet-pop-in {
            from { opacity: 0; transform: translate(-50%, -50%) scale(.88); }
            to   { opacity: 1; transform: translate(-50%, -50%) scale(1); }
        }
        /* 첨부 이미지처럼 낡은 양피지 두루마리 느낌 — 세계지도 다이얼로그에서 쓴
           것과 같은 세피아 팔레트 + 위아래 말린 종이 롤을 그대로 가져와 톤을
           통일한다. 위 "div[data-testid='stDialog'] div"가 태그 2개짜리라 명시도가
           (0,1,2)라서 클래스 하나뿐인 규칙(0,1,0)로는 못 이긴다 — dialog 속성
           선택자를 앞에 한 번 더 붙여 명시도를 (0,2,1)로 올려야 실제로 색이 보인다. */
        div[data-testid="stDialog"] .st-key-country_sheet_card {
            position: relative;
            background:
                radial-gradient(ellipse at 28% 12%, rgba(255,248,222,.55) 0%, rgba(255,248,222,0) 46%),
                linear-gradient(160deg, #f3e3bd 0%, #dcb876 45%, #c69a5c 100%) !important;
            border: 5px solid #7a4a23 !important; border-radius: 18px !important;
            padding: 0 !important;
            box-shadow:
                inset 0 0 0 3px rgba(255,244,214,.5),
                inset 0 0 60px rgba(93,58,20,.28),
                0 24px 60px rgba(40,20,5,.45) !important;
            min-height: 240px; overflow: visible;
            margin: 16px 4px 22px;
        }
        div[data-testid="stDialog"] .st-key-country_sheet_card::before,
        div[data-testid="stDialog"] .st-key-country_sheet_card::after {
            content: ''; position: absolute; left: -14px; right: -14px; height: 22px;
            background: linear-gradient(180deg, #8a5a2e, #4d3018);
            border-radius: 11px; box-shadow: 0 3px 8px rgba(0,0,0,.4);
        }
        div[data-testid="stDialog"] .st-key-country_sheet_card::before { top: -11px; }
        div[data-testid="stDialog"] .st-key-country_sheet_card::after { bottom: -11px; }
        .sheet-ticket-header {
            position: relative; padding: 30px 32px 6px;
            display: flex; align-items: center; gap: 18px;
        }
        .sheet-ticket-icon {
            font-size: 2.6rem; line-height: 1; flex-shrink: 0; width: 68px; height: 68px;
            border-radius: 50%; display: flex; align-items: center; justify-content: center;
            background: var(--ticket-accent);
            box-shadow: 0 6px 14px rgba(60,30,10,.4), inset 0 0 0 3px rgba(255,255,255,.5);
        }
        .sheet-ticket-title {
            font-family: 'Gaegu', cursive; font-weight: 700; font-size: 2.6rem;
            color: #4a2f12; text-shadow: 0 1px 0 rgba(255,255,255,.4);
        }
        .sheet-ticket-sub {
            font-family: 'Jua', sans-serif; font-size: 1.2rem; color: #6e4c26;
            letter-spacing: .4px; margin-top: 4px; opacity: .9;
        }
        .sheet-ticket-stamp {
            position: absolute; right: 30px; top: 22px; font-size: 2.6rem;
            opacity: .55; transform: rotate(10deg);
            filter: drop-shadow(0 2px 2px rgba(0,0,0,.3));
        }
        .sheet-divider {
            text-align: center; color: #a5713b; font-size: 1.2rem; letter-spacing: 10px;
            margin: 14px 0 4px; opacity: .6;
        }
        .st-key-sheet_body { padding: 10px 32px 32px; }
        /* 본문에 쓰는 st.write/st.markdown 텍스트도 전체적으로 키워서 가독성 개선 —
           한 차례 더 키워달라는 요청으로 대폭 확대 */
        .st-key-sheet_body p, .st-key-sheet_body li,
        .st-key-sheet_body div[data-testid="stMarkdownContainer"] {
            font-size: 1.55rem !important; line-height: 1.7 !important; color: #4a2f12 !important;
        }
        .st-key-sheet_body div[data-testid="stMarkdownContainer"] strong { font-size: 1.6rem !important; }
        .st-key-sheet_body div[data-testid="stCaptionContainer"] p { font-size: 1.3rem !important; }
        /* 큐레이션 제품의 "~에서 보기" 링크 버튼 — 시트 안의 다른 기본 버튼
           (예: 피부 스캔 버튼, .stButton > button[kind="secondary"])과 같은
           흰 배경 + 핑크 테두리 필 스타일로 통일한다 */
        .st-key-sheet_body [class*="st-key-travel_prep_link_"],
        .st-key-sheet_body [class*="st-key-curated_link_"] {
            width: auto !important; display: block !important; margin: 2px 0 10px !important;
        }
        .st-key-sheet_body [class*="st-key-travel_prep_link_"] [data-testid="stLinkButton"],
        .st-key-sheet_body [class*="st-key-curated_link_"] [data-testid="stLinkButton"] {
            width: auto !important;
        }
        .st-key-sheet_body [class*="st-key-travel_prep_link_"] a[data-testid^="stBaseLinkButton"],
        .st-key-sheet_body [class*="st-key-curated_link_"] a[data-testid^="stBaseLinkButton"] {
            font-family: 'Jua', sans-serif;
            width: auto !important; min-width: 0 !important;
            padding: .25rem .8rem !important;
            background: #ffffff !important;
            border: 2px solid #ffd3ea !important;
            border-radius: 999px !important;
            box-shadow: 0 3px 0 rgba(255,159,216,.35), 0 4px 10px rgba(120,60,110,.1) !important;
            transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease;
        }
        .st-key-sheet_body [class*="st-key-travel_prep_link_"] a[data-testid^="stBaseLinkButton"] p,
        .st-key-sheet_body [class*="st-key-curated_link_"] a[data-testid^="stBaseLinkButton"] p {
            color: #6a4a6a !important;
            font-weight: 700 !important;
            font-size: .85rem !important;
        }
        .st-key-sheet_body [class*="st-key-travel_prep_link_"] a[data-testid^="stBaseLinkButton"]:hover,
        .st-key-sheet_body [class*="st-key-curated_link_"] a[data-testid^="stBaseLinkButton"]:hover {
            border-color: #ff9fd8 !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 0 rgba(255,159,216,.45), 0 6px 14px rgba(120,60,110,.16) !important;
        }
        .st-key-sheet_body [class*="st-key-travel_prep_link_"] a[data-testid^="stBaseLinkButton"]:active,
        .st-key-sheet_body [class*="st-key-curated_link_"] a[data-testid^="stBaseLinkButton"]:active {
            transform: translateY(2px);
            box-shadow: 0 1px 0 rgba(255,159,216,.35), 0 2px 6px rgba(120,60,110,.1) !important;
        }
        /* 기존 st.metric 스택은 라벨/숫자만 덜렁 나열돼 밋밋했다 — 아이콘 달린
           작은 통계 타일 그리드로 바꿔서 한눈에 훑어볼 수 있게 함 */
        .stat-grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 14px;
            margin: 6px 0 18px;
        }
        .stat-grid.stat-grid-3 { grid-template-columns: 1fr 1fr 1fr; }
        .stat-tile {
            background: linear-gradient(160deg, #fffaf0 0%, #fbeecb 100%);
            border: 1.5px solid rgba(122,74,35,.35); border-radius: 14px;
            padding: 16px 18px;
        }
        .stat-tile-icon { font-size: 1.8rem; margin-bottom: 4px; }
        .stat-tile-label {
            font-family: 'Jua', sans-serif; font-size: 1.15rem; color: #8a5a10;
            letter-spacing: .3px; text-transform: uppercase; opacity: .9;
        }
        .stat-tile-value {
            font-family: 'Gaegu', cursive; font-weight: 700; font-size: 1.75rem;
            color: #4a2f12; margin-top: 4px; line-height: 1.4;
        }
        .stat-tile-value.stat-tile-alert { color: #c0392b; }
        .sheet-note {
            font-family: 'Jua', sans-serif; font-size: 1.3rem; color: #6e4c26;
            margin: 4px 2px 16px; line-height: 1.55;
        }
        .st-key-close_country_sheet button {
            border-radius: 999px !important; font-family: 'Jua', sans-serif !important;
            font-weight: 700 !important; font-size: 1.4rem !important; border: none !important;
            background: linear-gradient(180deg,#4d3320,#241407) !important; color: #f1dfb8 !important;
            padding: 10px 0 !important;
        }
        .st-key-close_country_sheet button:hover {
            background: linear-gradient(180deg,#5c3f28,#2c1a0c) !important;
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
            <div class="sheet-ticket-header">
                <div class="sheet-ticket-icon" style="--ticket-accent:{theme['accent']};">{icons.get(kind, "✈️")}</div>
                <div>
                    <div class="sheet-ticket-title">{titles.get(kind, "")}</div>
                    <div class="sheet-ticket-sub">{theme['label']} · {html.escape(country['name'])}</div>
                </div>
                <div class="sheet-ticket-stamp">{country['flag']}</div>
            </div>
            <div class="sheet-divider">❖ ❖ ❖</div>
            """
        )
        with st.container(key="sheet_body"):
            _render_country_sheet_body(kind, country, char, code)

        if st.button("✕ 닫기", key="close_country_sheet", use_container_width=True):
            st.session_state.active_country_sheet = None
            st.rerun()


def _render_carrier_packing(country):
    """캐리어 담기 서비스 — 기내 액체류 반입 규정(개별 용기 100ml 이하 · 총합 1L 이하)
    체크 기능. [제품] 탭은 국가 상세 페이지에서 추천된 essentials 목록에서 고르고,
    [용기] 탭은 프리셋 용량 버튼(30/50/100ml) 또는 직접 입력으로 담는다. 담을 때마다
    개별 용기 기준으로 즉시 반입 가능/불가를 판정하고, 전체 목록의 총 용량이
    1L를 넘으면 상단에 경고 배너를 띄운다."""
    items = st.session_state.carrier_items
    total_ml = sum(i["volume_ml"] for i in items)

    if total_ml > LIQUID_TOTAL_LIMIT_ML:
        st.error(
            f"⚠️ 총 용량 {total_ml:.0f}ml — 1L({LIQUID_TOTAL_LIMIT_ML}ml)를 초과했어요! "
            "투명 지퍼백 규정을 초과할 수 있으니 일부를 줄여주세요."
        )
    st.caption("✈️ 기내 액체류는 개별 용기 100ml 이하 · 총합 1L(1000ml) 이하만 반입할 수 있어요")

    tab_product, tab_container = st.tabs(["제품", "용기(용량별)"])

    with tab_product:
        essentials = country.get("essentials") or []
        if essentials:
            product_name = st.selectbox("제품 선택", essentials, key="carrier_product_select")
        else:
            product_name = st.text_input("제품명", key="carrier_product_name_input")
        st.number_input(
            "용량 (ml)", min_value=1, max_value=1000, value=100, step=10, key="carrier_product_volume"
        )
        if st.button("캐리어에 담기", key="carrier_add_product_btn", use_container_width=True):
            _add_carrier_item(product_name, st.session_state.carrier_product_volume)
            st.rerun()

    with tab_container:
        st.write("프리셋 용량")
        preset_cols = st.columns(len(CARRIER_VOLUME_PRESETS))
        for col, preset in zip(preset_cols, CARRIER_VOLUME_PRESETS):
            with col:
                if st.button(f"{preset}ml", key=f"carrier_preset_{preset}", use_container_width=True):
                    st.session_state.carrier_container_volume = preset
                    st.rerun()
        st.number_input(
            "용량 (ml)", min_value=1, max_value=1000, value=100, step=10, key="carrier_container_volume"
        )
        if st.button("캐리어에 담기", key="carrier_add_container_btn", use_container_width=True):
            volume = st.session_state.carrier_container_volume
            _add_carrier_item(f"{volume:.0f}ml 용기", volume)
            st.rerun()

    st.divider()
    st.markdown(f"**담은 목록** · 총 {len(items)}개 · 총 {total_ml:.0f}ml")
    if not items:
        st.caption("아직 담은 액체류가 없어요")
    else:
        for i, item in enumerate(items):
            name_col, vol_col, badge_col, del_col = st.columns(
                [4, 2, 3, 1], vertical_alignment="center"
            )
            with name_col:
                st.write(item["name"])
            with vol_col:
                st.write(f"{item['volume_ml']:.0f}ml")
            with badge_col:
                st.write("✅ 반입 가능" if item["allowed"] else f"❌ {item['reason']}")
            with del_col:
                if st.button("✕", key=f"carrier_del_{i}", help="목록에서 빼기"):
                    st.session_state.carrier_items.pop(i)
                    st.rerun()

    if st.button(
        "📋 체크리스트로 저장", key="carrier_save_checklist_btn",
        use_container_width=True, disabled=not items,
    ):
        st.session_state.passport_carrier_checklist = list(items)
        st.toast("📔 뷰티 패스포트에 체크리스트를 저장했어요")


def _render_country_sheet_body(kind, country, char, code):
    if kind == "water":
        skin_notes = char.get("skin_type_extra") or []
        if country["water"] == "경수" and skin_notes:
            st.warning(
                f"⚠ {', '.join(skin_notes)} 피부는 이 지역의 경수 때문에 트러블 위험이 높아요. "
                f"저자극 클렌징워터를 꼭 챙기세요."
            )
        html_block(
            f"""
            <div class="stat-grid">
                <div class="stat-tile">
                    <div class="stat-tile-icon">🌤️</div>
                    <div class="stat-tile-label">기후</div>
                    <div class="stat-tile-value">{html.escape(country['climate'])}</div>
                </div>
                <div class="stat-tile">
                    <div class="stat-tile-icon">💧</div>
                    <div class="stat-tile-label">습도</div>
                    <div class="stat-tile-value">{html.escape(country['humidity'])}</div>
                </div>
                <div class="stat-tile">
                    <div class="stat-tile-icon">☀️</div>
                    <div class="stat-tile-label">자외선</div>
                    <div class="stat-tile-value">{html.escape(country['uv'])}</div>
                </div>
                <div class="stat-tile">
                    <div class="stat-tile-icon">🚰</div>
                    <div class="stat-tile-label">수질</div>
                    <div class="stat-tile-value">{html.escape(country['water'])}</div>
                </div>
            </div>
            <div class="sheet-note">{html.escape(country['water_note'])}</div>
            """
        )
        feed_path = country.get("aqi_station") or (
            f"geo:{country['geo']}" if country.get("geo") else None
        )
        aq = get_air_quality(feed_path) if feed_path else None
        if aq and aq.get("aqi") not in (None, "-"):
            try:
                aqi_val = int(aq["aqi"])
                is_bad = aqi_val >= 101
                pm_parts = []
                if aq.get("pm25") is not None:
                    pm_parts.append(f"PM2.5 {aq['pm25']}㎍/㎥")
                if aq.get("pm10") is not None:
                    pm_parts.append(f"PM10 {aq['pm10']}㎍/㎥")
                pm_line = f'<div class="sheet-note">{" · ".join(pm_parts)}</div>' if pm_parts else ""
                html_block(
                    f"""
                    <div class="stat-grid" style="grid-template-columns:1fr;">
                        <div class="stat-tile">
                            <div class="stat-tile-icon">🌫️</div>
                            <div class="stat-tile-label">실시간 미세먼지 (AQI)</div>
                            <div class="stat-tile-value {'stat-tile-alert' if is_bad else ''}">
                                {aqi_val} · {_aqi_level_label(aqi_val)}
                            </div>
                        </div>
                    </div>
                    {pm_line}
                    """
                )
            except (TypeError, ValueError):
                pass

    elif kind == "lipstick":
        _render_skin_scan_section()
        baseline = get_skin_baseline(char)
        st.caption(f"✈️ {country['name']}로 떠나기 전, 한국에서 챙겨가면 좋은 제품이에요")
        with st.spinner("피부 맞춤 추천을 준비하고 있어요..."):
            travel_prep = get_travel_prep_recommendation(char, code)
        for p in travel_prep:
            img_uri = asset_data_uri(p["image"], "image/png")
            caution = get_ingredient_caution(code, p["key_ingredients"])
            title_attr = ""
            card_border = ""
            warn_badge = ""
            if caution:
                ing, info = caution
                title_attr = f' title="⚠️ {html.escape(country["name"])} 반입 주의: {html.escape(info["reason"])}"'
                card_border = "border:2px solid #f3b7ae;"
                warn_badge = (
                    '<div style="margin-top:6px;font-size:.9rem;font-weight:700;color:#c0392b;">'
                    f'⚠️ {html.escape(country["name"])} 반입 주의 · {html.escape(ing)} 성분 포함'
                    "(마우스를 올려 확인)</div>"
                )
            html_block(
                f"""
                <div{title_attr} style="display:flex;gap:18px;align-items:flex-start;background:#fff;
                    border-radius:16px;padding:16px;margin-bottom:10px;
                    box-shadow:0 2px 8px rgba(0,0,0,.08);{card_border}">
                    <img src="{img_uri}" style="width:104px;height:104px;object-fit:contain;
                        border-radius:12px;background:#faf7f2;flex:0 0 auto;">
                    <div style="flex:1;min-width:0;">
                        <div style="font-weight:700;font-size:1.2rem;">{html.escape(p['brand'])} · {html.escape(p['name'])}</div>
                        <div style="font-size:.95rem;color:#888;margin:4px 0 8px;">{html.escape(p['texture'])} · {html.escape(', '.join(p['key_ingredients'][:2]))}</div>
                        <div style="font-size:1rem;color:#4a2f12;line-height:1.5;margin-bottom:6px;">{html.escape(p['description'])}</div>
                        <div style="font-size:.95rem;color:#9c2f5c;">✨ {html.escape(p.get('reason') or '')}</div>
                        {warn_badge}
                    </div>
                </div>
                """
            )
            st.link_button("올리브영에서 보기 →", p["url"], key=f"travel_prep_link_{code}_{p['id']}")
            if caution:
                ing, info = caution
                with st.expander(f"⚠️ {ing} 성분 반입 주의 — 자세히 보기"):
                    st.warning(info["reason"])
                    alt = next(
                        (a for a in travel_prep
                         if a["id"] != p["id"] and not get_ingredient_caution(code, a["key_ingredients"])),
                        None,
                    )
                    if alt:
                        st.markdown(f"**대체 추천**: {alt['brand']} · {alt['name']} (해당 성분 없음)")
                    st.caption(f"출처: {info['source']}")
        st.caption("✨ 피부 baseline과 현지 기후를 분석해 골라봤어요")
        if baseline["baseline_source"] == "self_reported":
            st.caption("📝 자가 응답 기반 추천이라 스캔보다 정확도가 낮을 수 있어요")

    elif kind == "shop":
        st.markdown("**🧳 필수 아이템**")
        for item in country["essentials"]:
            st.write(f"- {item}")

        curated = get_curated_product_recommendation(char, code)
        if curated:
            st.markdown("**🛍️ 추천 제품**")
            st.caption("✨ 이 여행지에서 실제로 구매할 수 있는 제품 중 피부 프로필에 맞는 걸 골라봤어요")
            for p in curated:
                img_uri = asset_data_uri(p["image"], "image/png")
                html_block(
                    f"""
                    <div style="display:flex;gap:14px;align-items:center;background:#fff;
                        border-radius:14px;padding:12px;margin-bottom:8px;
                        box-shadow:0 2px 8px rgba(0,0,0,.08);">
                        <img src="{img_uri}" style="width:72px;height:72px;object-fit:contain;
                            border-radius:10px;background:#faf7f2;flex:0 0 auto;">
                        <div style="flex:1;min-width:0;">
                            <div style="font-weight:700;font-size:.95rem;">{html.escape(p['brand'])} · {html.escape(p['name'])}</div>
                            <div style="font-size:.78rem;color:#888;margin:2px 0;">{html.escape(p['category'])} · {html.escape(', '.join(p['key_ingredients'][:2]))}</div>
                            <div style="font-size:.85rem;color:#9c2f5c;">{html.escape(p.get('reason') or p['description'])}</div>
                        </div>
                    </div>
                    """
                )
                if p.get("url"):
                    st.link_button("사러 가기 →", p["url"], key=f"curated_link_{p['id']}")
                elif p.get("store_note"):
                    st.caption(f"🏪 **이 제품은 여기서**: {p['store_note']}")

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
        st.link_button("3WAAU에서 추천 제품 보러 가기 →", THREE_WAU_STORE_URL, use_container_width=True)

    elif kind == "carrier":
        _render_carrier_packing(country)


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
# 여행 후 피부 복귀 프로그램 — 여행 "중"이 아니라 귀국한 뒤의 피부를 챙기는
# 별도 흐름. 지구본 옆 🏠 아이콘으로 언제든 들어올 수 있고, 내부적으로
# pick_trip(기준 여행/날짜 고르기) -> survey(문항) -> concern_log(고민 기록
# 확인·수정) -> priority(우선순위 확인) -> analyzing(분석 연출) -> result(7일
# 프로그램) 6단계를 recovery_stage로 관리한다.
# ----------------------------------------------------------------------
def render_recovery():
    if not get_character():
        goto("character")
        st.rerun()
        return
    stage = st.session_state.recovery_stage
    if stage == "survey":
        _render_recovery_survey()
    elif stage == "concern_log":
        _render_recovery_concern_log()
    elif stage == "priority":
        _render_recovery_priority()
    elif stage == "analyzing":
        _render_recovery_analyzing()
    elif stage == "result":
        _render_recovery_result()
    else:
        _render_recovery_pick_trip()


def _render_recovery_pick_trip():
    st.title("🏠 여행 후 피부 복귀 프로그램")
    st.caption("여독이 풀리는 시점의 피부를 챙겨봐요. 먼저 어떤 여행을 기준으로 할지 골라주세요.")
    saved = get_passport()
    if saved:
        labels = [f"{p['flag']} {p['name']}" for p in saved]
        choice = st.selectbox(
            "어떤 여행을 기준으로 할까요? (⭐ 즐겨찾기한 여행만 표시돼요)", labels, index=len(labels) - 1,
        )
        st.session_state.recovery_trip_code = saved[labels.index(choice)]["code"]
    else:
        st.warning("먼저 지도에서 여행지를 ⭐ 즐겨찾기해야 설문을 시작할 수 있어요.")
        st.session_state.recovery_trip_code = None

    col1, col2 = st.columns(2)
    with col1:
        start_default = st.session_state.recovery_trip_start or (datetime.now().date() - timedelta(days=7))
        st.session_state.recovery_trip_start = st.date_input("출발일", value=start_default)
    with col2:
        end_default = st.session_state.recovery_trip_end or datetime.now().date()
        if end_default < st.session_state.recovery_trip_start:
            end_default = st.session_state.recovery_trip_start
        st.session_state.recovery_trip_end = st.date_input(
            "귀국일", value=end_default, min_value=st.session_state.recovery_trip_start,
        )
    nights = max((st.session_state.recovery_trip_end - st.session_state.recovery_trip_start).days, 0)
    st.caption(f"{nights}박 {nights + 1}일 여행이었네요.")

    st.session_state.recovery_flight_hours = st.slider(
        "비행 시간(시간)", 0.0, 20.0, st.session_state.recovery_flight_hours, 0.5,
    )
    st.caption("비행시간이 3시간 이상이면 Day 1은 다른 고민보다 피로·장벽 회복을 먼저 배정해요.")
    if st.button(
        "설문 시작 →", type="primary", use_container_width=True,
        disabled=not st.session_state.recovery_trip_code,
    ):
        st.session_state.recovery_answers = {}
        st.session_state.recovery_stage = "survey"
        st.rerun()


def _render_recovery_survey():
    st.title("🏠 여행 후 설문조사")
    st.caption("해당되는 것을 골라주세요 — 문항마다 독립적이라 여러 개를 동시에 골라도 괜찮아요")
    answers = st.session_state.recovery_answers
    for q in RECOVERY_SURVEY_QUESTIONS:
        st.markdown(f"**{q['prompt']}**")
        chosen_idx = answers.get(q["id"])
        cols = st.columns(len(q["options"]))
        for i, (col, opt) in enumerate(zip(cols, q["options"])):
            with col:
                is_selected = chosen_idx == i
                if st.button(opt["label"], key=f"recov_{q['id']}_{i}",
                             type="primary" if is_selected else "secondary",
                             use_container_width=True):
                    st.session_state.recovery_answers[q["id"]] = i
                    st.rerun()

    answered = len(answers)
    total = len(RECOVERY_SURVEY_QUESTIONS)
    all_answered = answered == total
    if not all_answered:
        st.caption(f"{answered}/{total}문항 응답했어요")
    if st.button("고민 기록 확인 →", type="primary", use_container_width=True, disabled=not all_answered):
        concerns_map = {q["id"]: q["options"][answers[q["id"]]]["concern"] for q in RECOVERY_SURVEY_QUESTIONS}
        st.session_state.recovery_logged_issues = build_recovery_logged_issues(concerns_map)
        st.session_state.recovery_minimal_ingredients = concerns_map.get("sensitive") == "자극/붉음"
        st.session_state.recovery_stage = "concern_log"
        st.rerun()
    if st.button("⬅ 여행 다시 고르기", key="recovery_back_to_pick"):
        st.session_state.recovery_stage = "pick_trip"
        st.rerun()


def _render_recovery_concern_log():
    st.caption("01 · 여행 중 고민 기록")
    st.title("어떤 게 힘들었나요?")
    st.caption("얼마나 자주 신경 쓰였는지(빈도)와 얼마나 심했는지(심각도)를 매겨두세요. 설문 답변으로 자동 채워졌고, 자유롭게 고쳐도 돼요.")

    issues = st.session_state.recovery_logged_issues
    remove_idx = None
    for idx, issue in enumerate(issues):
        score = issue["frequency"] * issue["severity"]
        c_name, c_freq, c_sev, c_del = st.columns([3, 1.3, 1.3, 0.6])
        c_name.markdown(f"**{html.escape(issue['issue'])}**  \n:gray[score {score}]")
        issue["frequency"] = c_freq.number_input("빈도", 1, 10, issue["frequency"], key=f"log_freq_{idx}")
        issue["severity"] = c_sev.number_input("심각도", 1, 5, issue["severity"], key=f"log_sev_{idx}")
        c_del.write("")
        if c_del.button("✕", key=f"log_del_{idx}"):
            remove_idx = idx
    if remove_idx is not None:
        issues.pop(remove_idx)
        st.rerun()
    if issues:
        st.divider()

    st.markdown("**빠른 추가**")
    existing = {i["issue"] for i in issues}
    remaining_chips = [c for c in RECOVERY_QUICK_ADD_CHIPS if c not in existing]
    if remaining_chips:
        chip_cols = st.columns(4)
        for i, chip in enumerate(remaining_chips):
            if chip_cols[i % 4].button(chip, key=f"log_chip_{chip}", use_container_width=True):
                tier = RECOVERY_CONCERN_PRIORITY_TIER.get(chip, 4)
                issues.append({"issue": chip, "frequency": 2, "severity": RECOVERY_SEVERITY_BY_TIER.get(tier, 2)})
                st.rerun()
    else:
        st.caption("모든 항목을 이미 추가했어요.")

    st.markdown("**직접 추가**")
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    custom_label = c1.text_input(
        "고민을 입력하세요 (예: 피부 톤 불균일)", key="log_custom_label", label_visibility="collapsed",
    )
    custom_freq = c2.number_input("빈도", 1, 10, 3, key="log_custom_freq")
    custom_sev = c3.number_input("심각도", 1, 5, 3, key="log_custom_sev")
    if c4.button("추가", key="log_custom_add", use_container_width=True) and custom_label.strip():
        issues.append({"issue": custom_label.strip(), "frequency": custom_freq, "severity": custom_sev})
        st.rerun()

    st.divider()
    st.markdown("### 출발 전 · 귀국 후 스캔 비교")
    st.caption("두 장을 올리면 나란히 비교해보고, 우선순위 분석에도 함께 반영해요.")
    up1, up2 = st.columns(2)
    with up1:
        before_photo = st.file_uploader("여행 전 사진", type=["png", "jpg", "jpeg"], key="recov_before_photo")
        if before_photo:
            st.image(before_photo, use_container_width=True)
    with up2:
        after_photo = st.file_uploader("귀국 후 사진", type=["png", "jpg", "jpeg"], key="recov_after_photo")
        if after_photo:
            st.image(after_photo, use_container_width=True)
    st.caption(
        "두 장 다 올리면 피부 변화를 추정해 설문 기록과 함께 우선순위 계산에 반영해요. "
        "참고용 추정치이며 의학적 진단이 아니니, 트러블이나 붉음이 계속되면 피부과 상담을 받아보세요."
    )

    st.divider()
    nav1, nav2 = st.columns(2)
    with nav1:
        if st.button("⬅ 설문 다시 하기", use_container_width=True):
            st.session_state.recovery_stage = "survey"
            st.rerun()
    with nav2:
        if st.button("우선순위 확인 →", type="primary", use_container_width=True, disabled=not issues):
            if before_photo and after_photo:
                before_img = Image.open(before_photo).convert("RGB")
                after_img = Image.open(after_photo).convert("RGB")
                deltas = compute_photo_comparison_deltas(before_img, after_img)
                photo_issues = photo_deltas_to_logged_issues(deltas)
                st.session_state.recovery_logged_issues = merge_logged_issues(issues, photo_issues)
                st.session_state.recovery_used_photo_comparison = bool(photo_issues)
            else:
                st.session_state.recovery_used_photo_comparison = False
            st.session_state.recovery_stage = "priority"
            st.rerun()


_RECOVERY_RANK_CARD_CSS = """
<style>
.recovery-rank-card { background:#131a2b; border-radius:18px; padding:24px 26px; margin:8px 0 20px; }
.recovery-rank-row { margin-bottom:20px; }
.recovery-rank-row:last-child { margin-bottom:0; }
.recovery-rank-head { display:flex; align-items:center; gap:10px; color:#eef1fb; font-size:1.3rem;
    margin-bottom:9px; flex-wrap:wrap; }
.recovery-rank-name { font-weight:700; }
.recovery-rank-score { margin-left:auto; color:#9aa1b8; font-size:1.02rem; }
.recovery-badge { font-size:.85rem; font-weight:700; letter-spacing:.03em; padding:4px 10px; border-radius:6px; }
.recovery-badge-primary { background:#3d3315; color:#f5c344; }
.recovery-badge-secondary { background:#123329; color:#3ecf9e; }
.recovery-rank-track { background:#232b40; border-radius:6px; height:8px; overflow:hidden; }
.recovery-rank-fill { height:100%; border-radius:6px; }
</style>
"""


def _recovery_ranking_card_html(ranking):
    max_score = max((r["score"] for r in ranking), default=1) or 1
    rows_html = ""
    for idx, r in enumerate(ranking):
        badge_html, bar_color = "", "#8a8fa3"
        if idx == 0:
            badge_html = '<span class="recovery-badge recovery-badge-primary">PRIMARY</span>'
            bar_color = "#f5c344"
        elif idx == 1:
            badge_html = '<span class="recovery-badge recovery-badge-secondary">SECONDARY</span>'
            bar_color = "#3ecf9e"
        pct = round(r["score"] / max_score * 100)
        rows_html += f"""
        <div class="recovery-rank-row">
            <div class="recovery-rank-head">{badge_html}<span class="recovery-rank-name">{html.escape(r['issue'])}</span>
                <span class="recovery-rank-score">{r['score']}점 (빈도{r['frequency']}×심각도{r['severity']})</span></div>
            <div class="recovery-rank-track"><div class="recovery-rank-fill" style="width:{pct}%;background-color:{bar_color};"></div></div>
        </div>"""
    return f'{_RECOVERY_RANK_CARD_CSS}<div class="recovery-rank-card">{rows_html}</div>'


# 결과 화면과 뷰티 패스포트의 저장된 프로그램 페이지 양쪽에서 재사용하는
# "7일 여정표" 카드 스타일 — 한 군데서만 정의해 두 화면의 디자인이 어긋나지
# 않게 한다.
_RECOVERY_DAY_CARD_CSS = """
<style>
.recovery-day-card { background:#131a2b; border-radius:16px; padding:20px 24px; margin-bottom:16px; }
.recovery-day-top { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:8px; }
.recovery-day-num { background:#ff6fb8; color:#fff; font-weight:800; border-radius:8px;
    padding:4px 12px; font-size:1.1rem; }
.recovery-day-label { color:#eef1fb; font-weight:700; font-size:1.35rem; }
.recovery-day-badge { margin-left:auto; background:#2b2440; color:#c9a6ff; font-size:.95rem;
    padding:3px 11px; border-radius:6px; }
.recovery-product-row { display:flex; gap:14px; align-items:center; margin-top:6px; }
.recovery-product-img { width:72px; height:72px; object-fit:contain; border-radius:10px;
    background:#fff; flex:0 0 auto; }
.recovery-product-body { flex:1; min-width:0; }
.recovery-product-name { color:#ffd9ec; font-weight:700; font-size:1.15rem; }
.recovery-product-meta { color:#9aa1b8; font-size:1rem; margin:3px 0 8px; }
.recovery-product-desc { color:#d8dcec; font-size:1.1rem; line-height:1.6; }
.recovery-note { margin-top:12px; background:#3d3315; border-left:3px solid #f5c344;
    padding:10px 14px; border-radius:8px; color:#f5c344; font-weight:600; font-size:1.05rem; }
.recovery-context { margin-top:8px; color:#f5c344; font-size:1rem; }
</style>
"""


def _recovery_day_card_html(d):
    badge_html = (
        f'<span class="recovery-day-badge">✈ {html.escape(d["badge"])}</span>' if d.get("badge") else ""
    )
    product_html = ""
    if d["product"]:
        p = d["product"]
        img_uri = asset_data_uri(p["image"], "image/png")
        meta_bits = [p["texture"]] + list(p["key_ingredients"])
        product_html = f"""
        <div class="recovery-product-row">
            <img class="recovery-product-img" src="{img_uri}">
            <div class="recovery-product-body">
                <div class="recovery-product-name">🧴 {html.escape(p['brand'])} · {html.escape(p['name'])}</div>
                <div class="recovery-product-meta">{' · '.join(html.escape(k) for k in meta_bits)}</div>
                <div class="recovery-product-desc">{html.escape(p['description'])}</div>
            </div>
        </div>
        """
    note_html = f'<div class="recovery-note">💬 {html.escape(d["note"])}</div>' if d.get("note") else ""
    context_html = (
        f'<div class="recovery-context">✈️ {html.escape(d["context_note"])}</div>'
        if d.get("context_note") else ""
    )
    return f"""
    <div class="recovery-day-card">
        <div class="recovery-day-top">
            <span class="recovery-day-num">DAY {d['day']}</span>
            <span class="recovery-day-label">{html.escape(d['label'])}</span>
            {badge_html}
        </div>
        {product_html}
        {note_html}
        {context_html}
    </div>
    """


def _render_recovery_priority():
    st.caption("02 · 우선순위")
    st.title("무엇부터 케어할까요")
    st.caption("점수 = 빈도 × 심각도. 가장 높은 두 가지가 primary·secondary stressor가 돼요.")

    ranking = compute_recovery_stressor_ranking(st.session_state.recovery_logged_issues)
    html_block(_recovery_ranking_card_html(ranking))

    nav1, nav2 = st.columns(2)
    with nav1:
        if st.button("⬅ 고민 기록 수정", use_container_width=True):
            st.session_state.recovery_stage = "concern_log"
            st.rerun()
    with nav2:
        if st.button("7일 프로그램 만들기 →", type="primary", use_container_width=True):
            st.session_state.recovery_stage = "analyzing"
            st.rerun()


def _render_recovery_analyzing():
    st.title("🔎 피부 상태를 분석하고 필요한 제품을 추천중입니다")
    html_block(
        """
        <style>
        @keyframes recov-potion-shake {
            0%,100% { transform: rotate(0deg); }
            25%     { transform: rotate(-6deg); }
            75%     { transform: rotate(6deg); }
        }
        .recov-analyzing-icon { display:block; margin:6px auto 0; width:120px;
            animation: recov-potion-shake .5s ease-in-out infinite; }
        </style>
        """
        + f'<div class="recov-analyzing-icon">{POTION_ICON_SVG}</div>'
    )

    bar = st.progress(0)
    pct_slot = st.empty()
    step_slot = st.empty()
    steps_text = [
        "여행 중 고민 데이터를 확인하는 중...",
        "우선순위 stressor를 계산하는 중...",
        "카탈로그에서 맞는 제품을 매칭하는 중...",
        "7일 프로그램을 구성하는 중...",
    ]
    n = 34
    for i in range(n + 1):
        pct = int(i / n * 100)
        bar.progress(pct / 100)
        pct_slot.markdown(
            f'<div style="text-align:center;font-family:\'Jua\',sans-serif;font-size:1.7rem;'
            f'color:#ff6fb8;">{pct}%</div>',
            unsafe_allow_html=True,
        )
        step_slot.caption(steps_text[min(i * len(steps_text) // (n + 1), len(steps_text) - 1)])
        time.sleep(0.1)  # n=34 x 0.1s = 3.4초

    code = st.session_state.recovery_trip_code
    country = COUNTRIES.get(code) if code else None
    st.session_state.recovery_program = generate_recovery_program(
        st.session_state.recovery_logged_issues,
        st.session_state.recovery_flight_hours,
        st.session_state.recovery_minimal_ingredients,
        country,
    )
    st.session_state.recovery_stage = "result"
    st.rerun()


def _render_recovery_result():
    st.title("🏠 나만의 7일 피부 복귀 프로그램")
    code = st.session_state.recovery_trip_code
    country = COUNTRIES.get(code) if code else None
    trip_bits = []
    if country:
        trip_bits.append(f"{country['flag']} {country['name']}")
    start, end = st.session_state.recovery_trip_start, st.session_state.recovery_trip_end
    if start and end:
        nights = max((end - start).days, 0)
        trip_bits.append(f"{start:%Y.%m.%d} ~ {end:%Y.%m.%d} ({nights}박{nights + 1}일)")
    if trip_bits:
        st.caption(" · ".join(trip_bits) + " 여행을 기준으로 짜봤어요")

    program = st.session_state.recovery_program
    if not program or not program["days"]:
        st.success("여행 중 특별히 힘들었던 피부 고민이 없었네요! 평소 루틴을 가볍게 유지해보세요 ✨")
    else:
        st.markdown("### 우선순위")
        if st.session_state.recovery_used_photo_comparison:
            st.caption("📸 출발 전 · 귀국 후 사진 비교 결과도 함께 반영했어요")
        html_block(_recovery_ranking_card_html(program["ranking"]))

        st.markdown("### 7일 여정표")
        html_block(_RECOVERY_DAY_CARD_CSS)
        for d in program["days"]:
            html_block(_recovery_day_card_html(d))
            if d["product"]:
                p = d["product"]
                st.link_button(f"🛍️ {p['brand']} {p['name']} 올리브영에서 보기 →", p["url"],
                                use_container_width=True, key=f"recov_link_{d['day']}_{p['id']}")
            if d["day"] == 7 and not d["product"]:
                st.checkbox("붉은기가 남아있나요?", key="recov_check_1")
                st.checkbox("당김·건조함이 남아있나요?", key="recov_check_2")
                st.checkbox("트러블 자리가 진정됐나요?", key="recov_check_3")
                st.caption("셀프 체크만 하는 날이에요. 꼭 필요하면 평소 쓰던 보습제 정도만 가볍게 사용하세요.")

        st.divider()
        if st.button("🩷 뷰티 패스포트에 저장", key="recov_save_to_passport", use_container_width=True):
            entry = {
                "trip_label": " · ".join(trip_bits) if trip_bits else "여행 기록 없음",
                "ranking": program["ranking"],
                "days": program["days"],
                "saved_at": datetime.now().strftime("%Y.%m.%d"),
            }
            recovery_page_no = save_recovery_program_to_passport(entry)
            st.success(f"뷰티 패스포트 {recovery_page_no + 1}페이지에 저장했어요! 📔 열어서 확인해보세요.")

    st.divider()
    nav1, nav2 = st.columns(2)
    with nav1:
        if st.button("🔁 설문 다시 하기", use_container_width=True):
            st.session_state.recovery_answers = {}
            st.session_state.recovery_logged_issues = []
            st.session_state.recovery_used_photo_comparison = False
            st.session_state.recovery_stage = "survey"
            st.rerun()
    with nav2:
        if st.button("⬅ 지도로 돌아가기", key="recovery_back_to_map", use_container_width=True):
            goto("map")
            st.rerun()


# ----------------------------------------------------------------------
# 피부 궁합 진단 — 여행지 지도에서 국가/도시를 고른 뒤(country_stage="map")
# 화면 왼쪽의 반짝이는 포션을 누르면 들어오는 진단 단계.
# scan(얼굴 스캔하기) -> brewing(포션 진행 애니메이션) -> result(궁합 스코어)
# 3단계를 diagnosis_stage로 관리한다. diagnosis_country는 지도에서 고른
# 국가 코드가 이미 채워져 들어온다(별도의 나라 선택 그리드는 없음).
# ----------------------------------------------------------------------
def _josa_wa_gwa(word):
    """받침 유무에 따라 '와'/'과' 조사를 고른다 (받침 없으면 '와', 있으면 '과')."""
    if not word:
        return "와"
    code = ord(word[-1]) - 0xAC00
    if 0 <= code <= 11171:
        return "과" if code % 28 != 0 else "와"
    return "와"


def _diagnosis_title(country):
    """진단 화면 제목 — 국기/가운뎃점 없이 "OO OO와 나의 피부 궁합 진단" 형태로."""
    name = (country.get("name") or "").replace(" · ", " ").strip()
    return f"{name}{_josa_wa_gwa(name)} 나의 피부 궁합 진단"


def render_diagnosis():
    if not get_character():
        goto("character")
        st.rerun()
        return
    if not st.session_state.diagnosis_country:
        # 지도에서 국가를 고르지 않고는 들어올 수 없는 화면 — 안전하게 지도로
        goto("map")
        st.session_state.map_globe_opened = True
        st.rerun()
        return
    # camera_input의 촬영된 정지 이미지(iframe 내부 img)가 scan 단계를 벗어난
    # 뒤에도 DOM에 남아 옅게 비쳐 보이는 문제가 있다 -- 이 img를 숨기는 CSS 규칙이
    # scan 단계 렌더링에만 있으면 단계가 바뀌면서 규칙 자체도 함께 사라져 버려서,
    # 이 뷰에 있는 동안은 항상 숨겨지도록 여기서 단계와 무관하게 매번 주입한다.
    html_block(_CAMERA_MIRROR_CSS)
    stage = st.session_state.diagnosis_stage
    # scan 단계의 camera_input(iframe 기반 커스텀 컴포넌트)이 다음 단계로 넘어갈 때
    # 완전히 지워지지 않고 옅게 남아 보이는 문제가 있어(Streamlit이 재실행 사이에
    # "안 쓰는 만큼 지우기"를 완전히 못 하는 것으로 보임 -- 최상단 VIEWS 라우팅에서도
    # 같은 이유로 st.empty()를 씀), 단계 전환마다 st.empty()로 통째로 새로 그린다.
    stage_slot = st.empty()
    with stage_slot.container():
        if stage == "analyzing":
            _render_diagnosis_analyzing()
        elif stage == "brewing":
            _render_diagnosis_brewing()
        elif stage == "result":
            _render_diagnosis_result()
        else:
            _render_diagnosis_scan()


def _render_diagnosis_scan():
    """정면->왼쪽->오른쪽 3장을 한 장씩 촬영받는다. 세 장이 다 모이면 analyze_skin_scan()
    으로 분석해 공용 skin_scan baseline에 저장하고 analyzing 단계로 넘어간다."""
    code = st.session_state.diagnosis_country
    country = COUNTRIES.get(code) or {}
    st.title(_diagnosis_title(country))
    html_block(
        f"""
        <style>
        .diag-scan-copy {{
            text-align: center; font-family: 'Jua', sans-serif; font-size: 1.2rem;
            color: #5a3d7a; margin: 4px 0 22px;
        }}
        .st-key-diag_scan_btn {{ align-self: center !important; }}
        .st-key-diag_scan_btn.st-key-diag_scan_btn button {{
            position: relative !important;
            width: 160px !important; height: 160px !important; margin: 6px 0 10px !important;
            display: block !important; border-radius: 50% !important;
            background: linear-gradient(160deg,#ffe9f3,#ffd2ea) !important;
            border: 4px solid #ff9fd8 !important;
            box-shadow: 0 8px 20px rgba(255,111,184,.35) !important;
            color: transparent !important; font-size: 0 !important;
            transition: transform .15s ease;
        }}
        .st-key-diag_scan_btn.st-key-diag_scan_btn button::before {{
            content: ""; position: absolute; inset: 30px;
            background-image: url('{FACE_SCAN_ICON_URI}');
            background-size: contain; background-repeat: no-repeat; background-position: center;
        }}
        .st-key-diag_scan_btn.st-key-diag_scan_btn button:hover {{ transform: scale(1.06); }}
        .st-key-diag_scan_btn.st-key-diag_scan_btn button:active {{ transform: scale(.93); }}
        .diag-scan-hint {{
            text-align: center; font-family: 'Jua', sans-serif; color: #8a5a10; margin-top: 2px;
        }}
        .diag-scan-step-label {{
            text-align: center; font-family: 'Jua', sans-serif; color: #5a3d7a; margin-bottom: 6px;
        }}
        .st-key-diag_scan_cam {{
            align-self: center !important; width: min(380px, 92vw) !important;
        }}
        .st-key-diag_scan_cancel {{ align-self: center !important; width: min(380px, 92vw) !important; }}
        </style>
        <div class="diag-scan-copy">포션이 완성됐어요! 얼굴을 스캔해서<br>이 여행지와의 궁합을 확인해볼까요?</div>
        """
    )
    if not st.session_state.diagnosis_scan_cam_open:
        if st.button("📷", key="diag_scan_btn", help="얼굴 스캔하기"):
            st.session_state.diagnosis_scan_cam_open = True
            st.session_state.skin_scan_step = 0
            st.session_state.skin_scan_photos = {}
            st.rerun()
        html_block('<div class="diag-scan-hint">👆 얼굴 스캔하기</div>')
        return

    step = st.session_state.skin_scan_step
    angle = SCAN_ANGLES[step]
    html_block(
        _CAMERA_MIRROR_CSS
        + f'<div class="diag-scan-step-label">📸 {step + 1}/3 · {angle["label"]} — {angle["guide"]}</div>'
    )
    with st.container(key="diag_scan_cam"):
        photo = st.camera_input(
            angle["label"],
            key=f"diag_scan_cam_input_{angle['key']}_{st.session_state.skin_scan_widget_key}",
            label_visibility="collapsed",
        )
    if photo is not None:
        img = Image.open(photo).convert("RGB")
        ok, msg = _scan_quality_check(img)
        if not ok:
            st.warning(msg)
            if st.button("다시 찍기", key="diag_scan_retry"):
                st.session_state.skin_scan_widget_key += 1
                st.rerun()
        else:
            st.session_state.skin_scan_photos[angle["key"]] = img
            if step + 1 < len(SCAN_ANGLES):
                st.session_state.skin_scan_step += 1
                st.session_state.skin_scan_widget_key += 1
            else:
                st.session_state.skin_scan = analyze_skin_scan(st.session_state.skin_scan_photos)
                st.session_state.diagnosis_scan_cam_open = False
                st.session_state.diagnosis_stage = "analyzing"
            st.rerun()
    if st.button("취소", key="diag_scan_cancel"):
        st.session_state.diagnosis_scan_cam_open = False
        st.session_state.skin_scan_step = 0
        st.session_state.skin_scan_photos = {}
        st.rerun()


def _render_diagnosis_analyzing():
    """3장 촬영이 끝난 뒤 브루잉으로 넘어가기 전에 잠깐 보여주는 스캔 완료 단계.
    게이지가 가득 차고 완료 문구 1초, 분석 시작 문구 2초, 스캔+설문 결합 안내
    문구 2초를 차례로 보여준 뒤 기존 brewing 단계로 그대로 넘어간다
    (brewing/result 로직은 손대지 않음). 촬영된 얼굴 사진은 화면에 크게 띄우지
    않고 글로만 진행 상황을 안내한다."""
    code = st.session_state.diagnosis_country
    country = COUNTRIES.get(code) or {}
    st.title(_diagnosis_title(country))
    bar = st.progress(0)
    msg_slot = st.empty()
    steps = 20
    for i in range(steps + 1):
        bar.progress(i / steps)
        time.sleep(0.04)
    msg_slot.markdown(
        "<div style=\"text-align:center;font-family:'Jua',sans-serif;font-size:1.4rem;"
        "color:#3cb872;margin-top:16px;\">✅ 스캔이 완료되었습니다</div>",
        unsafe_allow_html=True,
    )
    time.sleep(1)
    msg_slot.markdown(
        "<div style=\"text-align:center;font-family:'Jua',sans-serif;font-size:1.4rem;"
        "color:#5a3d7a;margin-top:16px;\">🔍 분석을 시작합니다</div>",
        unsafe_allow_html=True,
    )
    time.sleep(2)
    msg_slot.markdown(
        "<div style=\"text-align:center;font-family:'Jua',sans-serif;font-size:1.2rem;"
        "color:#5a3d7a;margin-top:16px;\">스캔한 정보와 이전 설문 정보를 결합하여<br>"
        "궁합분석을 진행중입니다.</div>",
        unsafe_allow_html=True,
    )
    time.sleep(2)
    st.session_state.diagnosis_stage = "brewing"
    st.rerun()


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
            <div class="diag-brewing-label">얼굴을 스캔해서 {country.get("flag","")} {country.get("name","")}와의 궁합을 분석하는 중...</div>
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
        st.session_state.diagnosis_country = None
        goto("map")
        st.session_state.map_globe_opened = True
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
            st.session_state.country_stage = "scene"  # 확대 지도 단계를 건너뛰고 6개 아이콘 화면으로 바로 이동
            st.session_state.active_country_sheet = None
            goto("country")
            st.rerun()
    with b2:
        if st.button("다른 나라 볼래요", key="diag_pick_other", use_container_width=True):
            st.session_state.diagnosis_country = None
            st.session_state.diagnosis_result = None
            goto("map")
            st.session_state.map_globe_opened = True
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
    "recovery": render_recovery,
}
render_bubble_clear()
render_passport_modal()
render_back_button()
render_top_icons()
render_ad_reward_button()
render_coin_celebration()

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
