import json
from dataclasses import dataclass
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

import requests
import streamlit as st
from openai import OpenAI


# -----------------------------
# Utils: date & d-day
# -----------------------------
def today_kr() -> date:
    # Streamlit 서버 timezone이 다를 수 있어도 MVP에서는 local date 기준으로 충분
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
# Weather via Open-Meteo (free)
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
    r = requests.get(url, params={"name": city, "count": 1, "language": "ko", "format": "json"}, timeout=15)
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    return results[0] if results else None

def fetch_weather(lat: float, lon: float, target: date) -> tuple[float | None, float | None, float | None]:
    """
    target date 기준 일별 최저/최고기온, 강수확률(가능 시)을 가져옵니다.
    - Open-Meteo forecast는 일반적으로 16일 내 예보가 유리합니다.
    - 그 이상이면 데이터가 비거나 정확도가 떨어질 수 있어, 앱에서 안내 문구를 띄웁니다.
    """
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
        return "해당 날짜의 예보 데이터를 가져오지 못했어요(예보 범위 밖일 수 있어요)."
    parts = [f"🌡️ {tmin:.0f}° ~ {tmax:.0f}°"]
    if pmax is not None:
        parts.append(f"🌧️ 강수확률(최대) {pmax:.0f}%")
    return " · ".join(parts)


# -----------------------------
# OpenAI styling generation (JSON)
# -----------------------------
def build_prompt(user, weather: WeatherInfo, trip_date: date) -> str:
    return f"""
너는 여행 전문 패션 코디네이터다.
여행지의 날씨, 일정, 사용자의 스타일 취향을 종합적으로 고려해
실용적이면서도 사진에 잘 어울리는 여행 코디를 추천해야 한다.
각 코디에는 반드시 추천 이유와 핵심 아이템을 포함하라.

[사용자 입력]
- 목적지: {weather.city}, {weather.country}
- 여행 날짜: {trip_date.isoformat()} ({dday_string(trip_date)})
- 성별: {user['gender']}
- 나이대: {user['age_group']}
- 스타일 성향: {user['style_pref']}
- 계절: {user['season']}
- 여행 상황/일정: {user['itinerary']}

[날씨 요약]
- {weather.summary}

[출력 형식: 반드시 JSON으로만 출력]
{{
  "destination_card": {{
    "destination": "도시/국가",
    "dday": "D-3 같은 문자열",
    "weather_one_liner": "한 줄 날씨 요약"
  }},
  "outfits": [
    {{
      "title": "코디 이름(짧게)",
      "vibe_keywords": ["키워드1","키워드2","키워드3"],
      "items": {{
        "top": ["..."],
        "bottom": ["..."],
        "outer": ["..."],
        "shoes": ["..."],
        "accessories": ["..."]
      }},
      "key_items": ["핵심 아이템 3~5개"],
      "why_recommended": "추천 이유(2~4문장, 날씨+TPO+사진발 근거 포함)",
      "packing_checklist": ["캐리어 체크리스트 8~14개(중복 없이)"]
    }}
  ],
  "tips": {{
    "layering": "레이어링 팁(1~3문장)",
    "photo_spots_style": "여행지 무드에 맞는 사진발 포인트(1~3문장)"
  }}
}}

[제약]
- 코디는 3개 생성
- 과장된 브랜드/가격 언급은 하지 말고, 품목 중심으로
- 한국어로
""".strip()

def generate_styling(openai_api_key: str, user: dict, weather: WeatherInfo, trip_date: date) -> dict:
    client = OpenAI(api_key=openai_api_key)
    prompt = build_prompt(user, weather, trip_date)

    # Responses API (openai>=1.x)
    resp = client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
        temperature=0.7,
    )

    text = (resp.output_text or "").strip()
    # 모델이 JSON만 출력하도록 유도했지만, 혹시 앞뒤 텍스트가 섞이면 JSON 부분만 파싱 시도
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # fallback: 첫 '{'부터 마지막 '}'까지 잘라 파싱 시도
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


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
  <div class="small-muted">무드: {" · ".join(outfit.get("vibe_keywords", [])[:5])}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    items = outfit.get("items", {})
    cols = st.columns(2)
    with cols[0]:
        st.subheader("착장 구성")
        for cat in ["top", "bottom", "outer", "shoes", "accessories"]:
            vals = items.get(cat, [])
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
    """
    MVP: 저작권 이슈를 피하려고 ‘이미지’ 자체를 끌어오기보다,
    검색 링크(출처 기반)로 무드보드 레퍼런스를 제공합니다.
    """
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
st.set_page_config(page_title="Tripfit", page_icon="🧳", layout="wide")
inject_css()

st.title("🧳 Tripfit")
st.caption("여행지 날씨 + 일정 + 취향을 바탕으로, 실용적이면서 사진에 잘 어울리는 코디를 추천해요.")

with st.sidebar:
    st.header("🔑 API Key")
    st.write("Streamlit Cloud에서는 Secrets에 `OPENAI_API_KEY`를 넣어주세요.")
    openai_key = st.text_input("OPENAI_API_KEY", type="password", value=st.secrets.get("OPENAI_API_KEY", ""))

st.divider()

# Inputs
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

# Action
colA, colB = st.columns([1, 2])

with colA:
    st.subheader("3) 생성")
    generate_btn = st.button("✨ 코디 추천 받기", use_container_width=True)

with colB:
    st.info("MVP 기준: **텍스트 기반 코디 + 체크리스트 + 무드보드(레퍼런스 링크)** 중심으로 구현했습니다.")

if generate_btn:
    if not destination.strip():
        st.error("목적지를 입력해주세요.")
        st.stop()
    if not openai_key:
        st.error("OPENAI_API_KEY가 필요해요. (사이드바/Secrets 설정)")
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
        st.warning(f"날씨 API 호출에 실패했어요. 코디는 생성하되, 날씨 반영이 제한될 수 있어요. ({e})")
        w = WeatherInfo(
            city=city, country=country, lat=lat, lon=lon,
            temp_min=None, temp_max=None, precipitation_prob_max=None,
            summary="날씨 데이터 없음"
        )

    # Note about forecast range
    if (trip_date - today_kr()).days > 16:
        st.warning("여행 날짜가 예보 범위(대개 16일)를 넘어갈 수 있어요. 기온/강수 정보가 비거나 부정확할 수 있습니다.")

    # OpenAI generate
    try:
        result = generate_styling(openai_key, user, w, trip_date)
    except Exception as e:
        st.error(f"AI 코디 생성 실패: {e}")
        st.stop()

    # Persist in session (for checklist state)
    st.session_state["latest_result"] = result
    st.session_state["latest_destination"] = f"{w.city}, {w.country}".strip().strip(",")

# Render results (if any)
result = st.session_state.get("latest_result")
if result:
    st.subheader("결과")
    dest_card = result.get("destination_card", {})
    # Ensure card fields
    dest_card.setdefault("destination", st.session_state.get("latest_destination", "목적지"))
    dest_card.setdefault("dday", dday_string(trip_date))
    dest_card.setdefault("weather_one_liner", f"{dest_card.get('weather_one_liner','')}".strip() or "날씨 정보")

    render_destination_card(dest_card)

    outfits = result.get("outfits", [])
    if not outfits:
        st.warning("코디 결과가 비어 있어요. 다시 시도해보세요.")
        st.stop()

    st.divider()
    st.subheader("👚 오늘의 추천 여행 룩 (카드 슬라이드)")

    # "슬라이드" 느낌: 탭으로 넘기기 (추가 라이브러리 없이 MVP)
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

    st.caption("※ 무드보드는 MVP 단계에서 저작권 이슈를 줄이기 위해 ‘레퍼런스 링크’ 방식으로 제공됩니다.")
