import json
from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta

import requests
import streamlit as st
from openai import OpenAI


# =============================
# Helpers
# =============================
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
    if m in (12, 1, 2): return "겨울"
    if m in (3, 4, 5): return "봄"
    if m in (6, 7, 8): return "여름"
    return "가을"

def safe_get_secret(name: str) -> str:
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


# =============================
# Weather (Open-Meteo)
# =============================
@dataclass
class WeatherInfo:
    city: str
    country: str
    lat: float
    lon: float
    summary: str

def geocode_city(city: str) -> dict | None:
    r = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "ko"},
        timeout=10,
    )
    r.raise_for_status()
    results = r.json().get("results") or []
    return results[0] if results else None

def fetch_weather_one_liner(lat: float, lon: float, target: date) -> str:
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_min,temperature_2m_max,precipitation_probability_max",
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
            "timezone": "Asia/Seoul",
        },
        timeout=10,
    )
    r.raise_for_status()
    d = r.json().get("daily") or {}
    tmin = (d.get("temperature_2m_min") or [None])[0]
    tmax = (d.get("temperature_2m_max") or [None])[0]
    pmax = (d.get("precipitation_probability_max") or [None])[0]

    if tmin is None or tmax is None:
        return "날씨 정보 없음"
    parts = [f"🌡️ {tmin:.0f}°~{tmax:.0f}°"]
    if pmax is not None:
        parts.append(f"🌧️ {pmax:.0f}%")
    return " · ".join(parts)


# =============================
# Calendar
# =============================
SLOTS = ["오전", "오후", "저녁"]

def build_calendar_rows(start_date: date, days: int, plans: list[dict]) -> list[dict]:
    rows = []
    for i in range(days):
        d = start_date + relativedelta(days=i)
        for slot in SLOTS:
            plan_text = next(
                (p["plan"] for p in plans if p["date"] == d.isoformat() and p["slot"] == slot),
                ""
            )
            rows.append({
                "날짜": d.isoformat(),
                "시간대": slot,
                "일정": plan_text.strip() if plan_text else "—"
            })
    return rows


# =============================
# Prompt / Mock / AI
# =============================
STYLE_OPTIONS = [
    "미니멀", "빈티지", "스트릿", "캐주얼",
    "클래식", "러블리", "고프코어", "시티보이/시티걸"
]

def build_prompt(user, weather, start_date, days, calendar_rows):
    return f"""
너는 여행 전문 패션 코디네이터다.
캘린더 일정에 맞춰 실용적이면서 사진에 잘 어울리는 코디를 날짜별로 추천하라.

[사용자]
- 성별: {user['gender']}
- 나이대: {user['age_group']}
- 스타일: {user['style_pref']}
- 계절: {user['season']}

[여행]
- 목적지: {weather.city}
- 기간: {days}일
- 날씨: {weather.summary}

[일정(JSON)]
{json.dumps(calendar_rows, ensure_ascii=False)}

[출력: JSON만]
""".strip()

def mock_generate_calendar(user, weather, start_date, days, calendar_rows):
    dest = f"{weather.city}, {weather.country}".strip().strip(",")
    by_date = {}
    for r in calendar_rows:
        by_date.setdefault(r["날짜"], []).append(r)

    calendar_outfits = []
    for d, rows in by_date.items():
        calendar_outfits.append({
            "date": d,
            "day_summary": f"{user['style_pref']} 무드의 데일리 코디",
            "day_outfits": [
                {
                    "title": f"👟 {user['style_pref']} 데이룩",
                    "covers_slots": ["오전", "오후"],
                    "items": {
                        "top": [f"{user['style_pref']} 상의"],
                        "bottom": ["편한 팬츠/스커트"],
                        "outer": ["가벼운 아우터"],
                        "shoes": ["스니커즈"],
                        "accessories": ["크로스백"],
                    },
                    "key_items": ["스니커즈", "아우터"],
                    "why_recommended": "일정 전반을 커버할 수 있는 안정적인 데일리 코디입니다.",
                    "packing_checklist": ["양말", "보조배터리", "선크림"],
                }
            ],
        })

    return {
        "destination_card": {
            "destination": dest,
            "dday": dday_string(start_date),
            "weather_one_liner": weather.summary,
        },
        "calendar_outfits": calendar_outfits,
    }

def generate_with_ai_or_fallback(openai_key, user, weather, start_date, days, calendar_rows):
    if not openai_key:
        return mock_generate_calendar(user, weather, start_date, days, calendar_rows), True
    try:
        client = OpenAI(api_key=openai_key)
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=build_prompt(user, weather, start_date, days, calendar_rows),
        )
        return json.loads(resp.output_text), False
    except Exception:
        return mock_generate_calendar(user, weather, start_date, days, calendar_rows), True


# =============================
# UI
# =============================
def inject_css():
    st.markdown("""
<style>
div.stButton > button {
    background: linear-gradient(135deg, #ff6cab 0%, #7366ff 100%);
    color: white;
    border-radius: 14px;
    height: 3.2em;
    font-size: 1.05rem;
    font-weight: 700;
    border: none;
}
div.stButton > button:hover {
    box-shadow: 0 8px 20px rgba(115,102,255,0.35);
    transform: translateY(-2px);
}
</style>
""", unsafe_allow_html=True)

st.set_page_config("Tripfit", "🧳", layout="wide")
inject_css()

st.title("🧳 Tripfit ✨")

with st.sidebar:
    st.toggle("🤖 AI 코디", value=True)
    openai_key = st.text_input("🔑 OpenAI API Key", type="password", value=safe_get_secret("OPENAI_API_KEY"))

c1, c2 = st.columns(2)

with c1:
    destination = st.text_input("📍 목적지", "파리")
    start_date = st.date_input("🗓️ 시작일", today_kr() + relativedelta(days=7))
    days = st.slider("⏳ 여행 기간", 1, 7, 3)

with c2:
    gender = st.selectbox("🙋 성별", ["여성", "남성", "기타/선호없음"])
    age_group = st.selectbox("🎂 나이대", ["10대", "20대", "30대", "40대", "50대+"])
    style_pref = st.selectbox("👗 스타일", STYLE_OPTIONS)

user = {
    "gender": gender,
    "age_group": age_group,
    "style_pref": style_pref,
    "season": season_from_month(start_date.month),
}

st.subheader("🗓️ 일정")
plans = []
tabs = st.tabs([(start_date + relativedelta(days=i)).strftime("📅 %m/%d") for i in range(days)])
for i, tab in enumerate(tabs):
    d = start_date + relativedelta(days=i)
    with tab:
        for slot in SLOTS:
            txt = st.text_area(f"{slot}", key=f"{d}_{slot}")
            plans.append({"date": d.isoformat(), "slot": slot, "plan": txt})

calendar_rows = build_calendar_rows(start_date, days, plans)

if st.button("🪄 코디 만들기", use_container_width=True):
    with st.spinner("✨ 코디 준비 중..."):
        geo = geocode_city(destination)
        weather = WeatherInfo(
            city=geo["name"],
            country=geo.get("country", ""),
            lat=geo["latitude"],
            lon=geo["longitude"],
            summary=fetch_weather_one_liner(geo["latitude"], geo["longitude"], start_date),
        )
        result, used_fallback = generate_with_ai_or_fallback(
            openai_key, user, weather, start_date, days, calendar_rows
        )

    st.subheader("👗 결과")
    for day in result["calendar_outfits"]:
        st.markdown(f"### 📅 {day['date']}")
        for outfit in day["day_outfits"]:
            st.markdown(f"**{outfit['title']}**")
            st.write(outfit["why_recommended"])
