"""
식스센스 TravelMax+
여행지 기후·수질·자외선 데이터를 내 피부 타입과 매칭해주는
게임풍 여행 뷰티 케어 웹앱 MVP
"""
import streamlit as st

st.set_page_config(page_title="TravelMax+", page_icon="🧳", layout="wide")

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
# 화면 렌더링
# ----------------------------------------------------------------------
def render_home():
    st.title("🧳 TravelMax+")
    st.subheader("여행지 기후·수질·자외선을 내 피부 타입에 맞춰 알려주는 여행 뷰티 케어 앱")
    st.write("내 캐릭터를 만들고, 여행지별 피부 케어 팁과 여권 컬렉션을 모아보세요!")
    if st.button("✈️ 여행 시작하기", type="primary"):
        goto("character")


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
VIEWS = {
    "home": render_home,
    "character": render_character,
    "map": render_map,
    "country": render_country,
    "passport": render_passport,
    "aftercare": render_aftercare,
}
VIEWS.get(st.session_state.view, render_home)()
