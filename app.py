import json
from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta

import requests
import streamlit as st


# -----------------------------
# Date helpers
# -----------------------------
def today_kr() -> date:
    return date.today()

def dday_string(target: date) -> str:
    delta = (target - today_kr()).days
    if delta > 0:
        return f"D-{delta}"
    if delta == 0:
        return "D-Day"
    return f"D+{abs(delta)}"

def season_from_month(m: int) -> str:
    if m in (12, 1, 2):
        return "겨울"
    if m in (3, 4, 5):
        return "봄"
    if m in (6, 7, 8):
        return "여름"
    return "가을"


# -----------------------------
# Weather via Open-Meteo (free, no key)
# -----------------------------
@dataclass
class WeatherInfo:
    city: str
    country: str
    lat: float
    lon: float
    temp_min: float | None
    temp_max: float | None
    precipitation_prob_max: float | None
    summary: str

def geocode_city(city: str) -> dict | None:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(
        url,
        params={"name": city, "count": 1, "language": "ko", "format": "json"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    return results[0] if results else None

def fetch_weather(lat: float, lon: float, target: date) -> tuple[float | None, float | None, float | None]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_min,temperature_2m_max,precipitation_probability_max",
        "timezone": "Asia/Seoul",
        "start_date": target.isoformat(),
        "end_date": target.isoformat(),
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    daily = data.get("daily") or {}
    tmin = (daily.get("temperature_2m_min") or [None])[0]
    tmax = (daily.get("temperature_2m_max") or [None])[0]
    pmax = (daily.get("precipitation_probability_max") or [None])[0]
    return tmin, tmax, pmax

def weather_summary(tmin, tmax, pmax) -> str:
    if tmin is None or tmax is None:
        return "예보 범위 밖이거나 데이터가 없어요."
    parts = [f"🌡️ {tmin:.0f}° ~ {tmax:.0f}°"]
    if pmax is not None:
        parts.append(f"🌧️ 강수확률(최대) {pmax:.0f}%")
    return " · ".join(parts)


# -----------------------------
# Mock AI (no payment needed)
# -----------------------------
def mock_generate_styling(user: dict, weather: WeatherInfo, trip_date: date) -> dict:
    """
    OpenAI 없이도 UI/플로우 테스트 가능하도록 더미 JSON 생성.
    사용자 입력(성별/스타일/일정/계절/날씨)을 반영해 결과가 그럴듯하게 바뀌도록 구성.
    """
    dest = f"{weather.city}, {weather.country}".strip().strip(",")
    dday = dday_string(trip_date)
    one_liner = weather.summary if weather.summary else "날씨 정보 없음"

    # 날씨 기반 간단 룰
    cold = (weather.temp_max is not None and weather.temp_max <= 10) or (user["season"] == "겨울")
    hot = (weather.temp_max is not None and weather.temp_max >= 25) or (user["season"] == "여름")
    rainy = (weather.precipitation_prob_max is not None and weather.precipitation_prob_max >= 50)

    style = user["style_pref"]
    itinerary = user["itinerary"]

    # 스타일별 키 아이템
    style_map = {
        "미니멀": ["오프화이트 톤 니트/셔츠", "슬랙스", "가죽 로퍼/스니커즈", "미니 크로스백"],
        "빈티지": ["트위드/코듀로이", "레트로 데님", "메리제인/로퍼", "스카프"],
        "스트릿": ["오버사이즈 후디", "카고 팬츠", "볼캡", "하이탑 스니커즈"],
        "캐주얼": ["맨투맨", "데님", "화이트 스니커즈", "에코백"],
        "클래식": ["트렌치/블레이저", "셔츠", "테일러드 팬츠", "가죽 벨트"],
        "러블리": ["플로럴 원피스/블라우스", "가디건", "발레 플랫", "진주 포인트"],
        "고프코어": ["바람막이", "기능성 팬츠", "트레킹 슈즈", "버킷햇"],
        "시티보이/시티걸": ["오버핏 코트", "와이드 팬츠", "심플 스니커즈", "토트백"],
    }
    base_keys = style_map.get(style, ["베이직 탑", "베이직 팬츠", "스니커즈", "가방"])

    # 조건별 추가 아이템
    weather_add = []
    if cold:
        weather_add += ["이너 히트텍", "울 머플러", "방풍 아우터"]
    if hot:
        weather_add += ["린넨 셔츠", "통기성 좋은 반바지/스커트", "선글라스"]
    if rainy:
        weather_add += ["우산", "방수 재킷", "방수 스니커즈/커버"]

    # 일정 기반
    tpo_add = []
    if "레스토랑" in itinerary or "저녁" in itinerary:
        tpo_add += ["포인트 액세서리", "깔끔한 아우터/셔츠"]
    if "박물관" in itinerary or "투어" in itinerary or "산책" in itinerary:
        tpo_add += ["편한 신발", "가벼운 크로스백"]

    # 3개 코디 구성
    outfits = []

    outfits.append({
        "title": f"{style} 데이-투어 룩",
        "vibe_keywords": [style, "활동성", "사진발", "레이어드" if cold else "가벼움"],
        "items": {
            "top": [base_keys[0], "기본 티/셔츠"],
            "bottom": [base_keys[1]],
            "outer": ["가벼운 자켓/가디건"] + (["코트/패딩"] if cold else []),
            "shoes": [base_keys[2], "편한 양말"],
            "accessories": [base_keys[3], "선글라스" if hot else "모자"]
        },
        "key_items": list(dict.fromkeys(base_keys + weather_add))[:5],
        "why_recommended": (
            f"{one_liner} 기준으로 활동량이 많은 일정({itinerary})에 맞춰 "
            f"편안함을 우선하면서도 {style} 무드가 살아나도록 핵심 아이템을 배치했어요. "
            f"사진에는 상의 톤/실루엣이 잘 보이게 구성했고, 이동 중 체감온도 변화를 고려해 레이어링 여지를 남겼습니다."
        ),
        "packing_checklist": list(dict.fromkeys([
            "상/하의 여벌 1벌", "속옷/양말", "파우치(세면/화장)", "충전기/보조배터리",
            "선크림", "향수/미니 향", "우비/우산" if rainy else "접이식 에코백",
            "여권/신분증", "카드/현금", "물티슈", "상비약", "머플러" if cold else "선글라스",
        ]))[:14],
    })

    outfits.append({
        "title": "저녁 식사 & 야경 룩",
        "vibe_keywords": [style, "깔끔", "무드", "디테일"],
        "items": {
            "top": ["셔츠/니트(단정한 톤)", "이너 탑"],
            "bottom": ["슬랙스/미디 스커트(무난한 컬러)"],
            "outer": ["블레이저/트렌치(사진에 실루엣 강조)"] + (["울 코트"] if cold else []),
            "shoes": ["로퍼/단정한 스니커즈"] + (["방수 신발" if rainy else ""] if True else []),
            "accessories": ["작은 귀걸이/시계", "미니백"],
        },
        "key_items": list(dict.fromkeys(["블레이저/트렌치", "단정한 상의", "로퍼", "미니백"] + tpo_add + weather_add))[:5],
        "why_recommended": (
            "저녁에는 조명 아래에서 소재감이 예쁘게 보이는 아이템이 잘 먹어요. "
            f"그래서 {style} 톤을 유지하면서도 단정한 상·하의와 구조감 있는 아우터로 ‘사진발’을 챙겼습니다. "
            f"{'비 예보가 있어서 방수 포인트를 더했고, ' if rainy else ''}"
            f"{'기온이 낮을 수 있어 보온 레이어를 추가했어요.' if cold else '너무 답답하지 않게 통기성을 확보했어요.'}"
        ),
        "packing_checklist": list(dict.fromkeys([
            "단정한 상의 1", "단정한 하의 1", "아우터", "향/데오드란트",
            "미니 액세서리", "여분 스타킹/양말", "숙소 슬리퍼", "헤어 제품",
            "우산" if rainy else "손수건", "핸드크림", "립밤", "카메라/짐벌(선택)"
        ]))[:14],
    })

    outfits.append({
        "title": "공항/이동 최적화 룩",
        "vibe_keywords": ["편안함", "레이어링", "미니멀", "기내"],
        "items": {
            "top": ["맨투맨/후디 또는 니트", "이너 티"],
            "bottom": ["밴딩 팬츠/조거 또는 와이드 팬츠"],
            "outer": ["가벼운 바람막이/가디건"] + (["두꺼운 겉옷"] if cold else []),
            "shoes": ["슬립온/스니커즈(탈착 편한)"],
            "accessories": ["목베개(선택)", "큰 토트/백팩", "이어폰"],
        },
        "key_items": list(dict.fromkeys(["편한 팬츠", "레이어링 가능한 상의", "큰 가방", "이어폰"] + weather_add))[:5],
        "why_recommended": (
            "이동은 ‘편안함+체온 조절’이 핵심이에요. "
            f"{one_liner}를 고려해 쉽게 벗고 입을 수 있는 레이어링으로 구성했고, "
            "공항 보안/기내에서 불편하지 않도록 신발과 가방 동선을 최적화했습니다."
        ),
        "packing_checklist": list(dict.fromkeys([
            "여권/탑승권", "목베개(선택)", "이어폰", "담요/가디건",
            "마스크", "손소독제", "보조배터리", "멀티어댑터(해외)",
            "작은 물병", "간식", "수면안대(선택)", "압박양말(선택)",
            "우산" if rainy else "선글라스",
        ]))[:14],
    })

    # 전체 팁
    tips = {
        "layering": "실내·실외 온도차가 크면 얇은 이너 + 중간 레이어 + 아우터 조합이 가장 안전해요.",
        "photo_spots_style": f"{dest}의 배경색을 고려해 상의는 너무 어두운 톤만 쓰기보다 포인트 컬러/밝은 톤을 1개 섞어주면 사진이 살아나요."
    }

    return {
        "destination_card": {
            "destination": dest,
            "dday": dday,
            "weather_one_liner": one_liner
        },
        "outfits": outfits,
        "tips": tips,
    }


# -----------------------------
# UI helpers
# -----------------------------
def inject_css():
    st.markdown(
        """
<style>
.trip-card {
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 18px;
  padding: 16px 16px;
  background: rgba(255,255,255,0.04);
}
.card-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 4px;
}
.badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.10);
  margin-right: 6px;
  font-size: 12px;
}
.item-chip {
  display: inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.14);
  margin: 4px 6px 0 0;
  font-size: 12px;
}
.small-muted {
  opacity: 0.75;
  font-size: 13px;
}
</style>
        """,
        unsafe_allow_html=True,
    )

def render_destination_card(dest_card: dict):
    st.markdown(
        f"""
<div class="trip-card">
  <div class="card-title">🧳 {dest_card.get('destination','목적지')}</div>
  <div style="margin: 8px 0;">
    <span class="badge">{dest_card.get('dday','D-Day')}</span>
    <span class="badge">{dest_card.get('weather_one_liner','날씨 정보')}</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

def render_outfit_card(outfit: dict, idx: int):
    st.markdown(
        f"""
<div class="trip-card">
  <div class="card-title">👗 {idx+1}. {outfit.get('title','코디')}</div>
  <div class="small-muted">무드: {" · ".join(outfit.get("vibe_keywords", [])[:6])}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    items = outfit.get("items", {})
    cols = st.columns(2)
    with cols[0]:
        st.subheader("착장 구성")
        for cat in ["top", "bottom", "outer", "shoes", "accessories"]:
            vals = [v for v in (items.get(cat, []) or []) if v]
            if vals:
                st.write(f"**{cat.upper()}**")
                for v in vals:
                    st.markdown(f"<span class='item-chip'>{v}</span>", unsafe_allow_html=True)
    with cols[1]:
        st.subheader("핵심 아이템")
        for v in outfit.get("key_items", []):
            st.markdown(f"<span class='item-chip'>{v}</span>", unsafe_allow_html=True)

    st.subheader("추천 이유")
    st.write(outfit.get("why_recommended", ""))

def render_checklist(outfit: dict, key_prefix: str):
    st.subheader("🧾 가상 캐리어 체크리스트")
    items = outfit.get("packing_checklist", [])
    if not items:
        st.info("체크리스트가 비어 있어요.")
        return
    for i, item in enumerate(items):
        k = f"{key_prefix}_{i}"
        st.checkbox(item, key=k)

def moodboard_links(destination: str, style_pref: str):
    st.subheader("🖼️ 무드 보드 레퍼런스(링크)")
    q = f"{destination} {style_pref} ootd"
    links = [
        ("Google 이미지 검색", f"https://www.google.com/search?tbm=isch&q={requests.utils.quote(q)}"),
        ("Pinterest 검색", f"https://www.pinterest.com/search/pins/?q={requests.utils.quote(q)}"),
        ("Instagram 해시태그", f"https://www.instagram.com/explore/tags/{requests.utils.quote(style_pref.replace(' ',''))}/"),
    ]
    for name, url in links:
        st.link_button(name, url)


# -----------------------------
# App
# -----------------------------
st.set_page_config(page_title="Tripfit (No-Pay Test)", page_icon="🧳", layout="wide")
inject_css()

st.title("🧳 Tripfit (결제 없이 테스트 버전)")
st.caption("OpenAI 없이도 ‘전체 UI/플로우’를 테스트할 수 있는 MVP입니다. (코디는 더미 생성)")

st.divider()

left, right = st.columns([1, 1])

with left:
    st.subheader("1) 여행 정보 입력")
    destination = st.text_input("목적지(도시명)", placeholder="예: 파리, 도쿄, 서울")
    trip_date = st.date_input("여행 날짜", value=today_kr() + relativedelta(days=7))
    itinerary = st.text_area("일정/상황(TPO)", placeholder="예: 박물관 투어 + 저녁 레스토랑 + 야간 산책", height=100)

with right:
    st.subheader("2) 사용자 정보 입력")
    gender = st.selectbox("성별", ["여성", "남성", "기타/선호없음"])
    age_group = st.selectbox("나이대", ["10대", "20대", "30대", "40대", "50대+"])
    style_pref = st.selectbox("스타일 성향", ["미니멀", "빈티지", "스트릿", "캐주얼", "클래식", "러블리", "고프코어", "시티보이/시티걸"])
    season = st.selectbox("계절(선택)", ["자동(날짜 기준)", "봄", "여름", "가을", "겨울"])

user = {
    "gender": gender,
    "age_group": age_group,
    "style_pref": style_pref,
    "season": season_from_month(trip_date.month) if season == "자동(날짜 기준)" else season,
    "itinerary": itinerary.strip() if itinerary.strip() else "일정 정보 없음(일반 여행)",
}

st.divider()

colA, colB = st.columns([1, 2])
with colA:
    st.subheader("3) 생성")
    generate_btn = st.button("✨ 코디 추천 받기(더미)", use_container_width=True)

with colB:
    st.info("현재 버전은 **OpenAI 호출 없이** 코디 결과를 생성합니다. 결제/키 없이 UI 테스트 가능해요.")

if generate_btn:
    if not destination.strip():
        st.error("목적지를 입력해주세요.")
        st.stop()

    # Geocode
    try:
        geo = geocode_city(destination.strip())
        if not geo:
            st.error("목적지를 찾지 못했어요. 도시명을 더 정확히 입력해보세요.")
            st.stop()
        city = geo.get("name", destination.strip())
        country = geo.get("country", "")
        lat = float(geo["latitude"])
        lon = float(geo["longitude"])
    except Exception as e:
        st.error(f"지오코딩 오류: {e}")
        st.stop()

    # Weather
    try:
        tmin, tmax, pmax = fetch_weather(lat, lon, trip_date)
        summary = weather_summary(tmin, tmax, pmax)
        w = WeatherInfo(
            city=city, country=country, lat=lat, lon=lon,
            temp_min=tmin, temp_max=tmax, precipitation_prob_max=pmax,
            summary=summary
        )
    except Exception as e:
        st.warning(f"날씨 API 호출 실패. 날씨 없이 더미 코디 생성합니다. ({e})")
        w = WeatherInfo(
            city=city, country=country, lat=lat, lon=lon,
            temp_min=None, temp_max=None, precipitation_prob_max=None,
            summary="날씨 데이터 없음"
        )

    # Forecast range note
    if (trip_date - today_kr()).days > 16:
        st.warning("여행 날짜가 예보 범위(대개 16일)를 넘어갈 수 있어요. 기온/강수 정보가 비거나 부정확할 수 있습니다.")

    # Mock generate
    result = mock_generate_styling(user, w, trip_date)

    # Persist (for checkbox state)
    st.session_state["latest_result"] = result
    st.session_state["latest_destination"] = f"{w.city}, {w.country}".strip().strip(",")

# Render results
result = st.session_state.get("latest_result")
if result:
    st.subheader("결과")
    dest_card = result.get("destination_card", {})
    render_destination_card(dest_card)

    outfits = result.get("outfits", [])
    if not outfits:
        st.warning("코디 결과가 비어 있어요. 다시 시도해보세요.")
        st.stop()

    st.divider()
    st.subheader("👚 추천 여행 룩 (카드 슬라이드)")

    tabs = st.tabs([f"룩 {i+1}" for i in range(len(outfits))])
    for i, (tab, outfit) in enumerate(zip(tabs, outfits)):
        with tab:
            render_outfit_card(outfit, i)
            st.divider()
            render_checklist(outfit, key_prefix=f"check_{i}")

    st.divider()
    st.subheader("🧠 추가 팁")
    tips = result.get("tips", {})
    if tips:
        st.write("**레이어링**:", tips.get("layering", ""))
        st.write("**사진발 포인트**:", tips.get("photo_spots_style", ""))

    st.divider()
    moodboard_links(st.session_state.get("latest_destination", destination), style_pref)

    st.caption("※ 본 버전은 결제 없이 테스트를 위해 더미 코디를 생성합니다. 실제 AI 적용은 이후 옵션으로 추가하면 됩니다.")
