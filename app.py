import json
from dataclasses import dataclass
from datetime import date
from dateutil.relativedelta import relativedelta

import requests
import streamlit as st
from openai import OpenAI


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
    if m in (12, 1, 2): return "겨울"
    if m in (3, 4, 5): return "봄"
    if m in (6, 7, 8): return "여름"
    return "가을"


# -----------------------------
# Weather (Open-Meteo, free)
# -----------------------------
@dataclass
class WeatherInfo:
    city: str
    country: str
    lat: float
    lon: float
    summary: str

def geocode_city(city: str):
    r = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "ko"},
        timeout=10,
    )
    data = r.json()
    return (data.get("results") or [None])[0]

def fetch_weather(lat, lon, target):
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_min,temperature_2m_max",
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
            "timezone": "Asia/Seoul",
        },
        timeout=10,
    )
    d = r.json().get("daily", {})
    tmin = d.get("temperature_2m_min", [None])[0]
    tmax = d.get("temperature_2m_max", [None])[0]
    return f"🌡️ {tmin}° ~ {tmax}°" if tmin else "날씨 정보 없음"


# -----------------------------
# AI Prompt
# -----------------------------
def build_prompt(user, weather, trip_date):
    return f"""
너는 여행 전문 패션 코디네이터다.
여행지, 날씨, 일정, 사용자의 스타일 취향을 고려해
실용적이면서 사진에 잘 어울리는 여행 코디 3개를 추천하라.

[입력]
- 목적지: {weather.city}
- 날짜: {trip_date} ({dday_string(trip_date)})
- 성별: {user['gender']}
- 나이대: {user['age']}
- 스타일: {user['style']}
- 계절: {user['season']}
- 일정: {user['itinerary']}
- 날씨: {weather.summary}

[출력(JSON)]
{{
  "outfits": [
    {{
      "title": "",
      "items": ["상의","하의","아우터","신발","가방"],
      "reason": "",
      "checklist": ["아이템1","아이템2"]
    }}
  ]
}}
"""


# -----------------------------
# OpenAI (with fallback)
# -----------------------------
def generate_with_ai_or_mock(openai_key, user, weather, trip_date):
    try:
        client = OpenAI(api_key=openai_key)
        res = client.responses.create(
            model="gpt-4o-mini",
            input=build_prompt(user, weather, trip_date),
        )
        return json.loads(res.output_text)

    except Exception as e:
        # 👉 핵심: 여기서 자동 fallback
        st.warning("⚠️ AI 호출 실패 → 더미 코디로 전환합니다.")
        return {
            "outfits": [
                {
                    "title": "미니멀 데이 투어 룩",
                    "items": ["화이트 셔츠", "슬랙스", "가벼운 자켓", "스니커즈", "크로스백"],
                    "reason": "도보 이동이 많은 일정에 적합하며 사진에서 깔끔한 실루엣을 연출합니다.",
                    "checklist": ["셔츠 여벌", "양말", "선글라스", "보조배터리"]
                },
                {
                    "title": "저녁 무드 룩",
                    "items": ["니트", "와이드 팬츠", "코트", "로퍼", "미니백"],
                    "reason": "저녁 레스토랑과 야경에 어울리는 차분한 스타일입니다.",
                    "checklist": ["니트", "액세서리", "향수"]
                },
                {
                    "title": "이동 최적화 룩",
                    "items": ["맨투맨", "조거 팬츠", "바람막이", "슬립온", "백팩"],
                    "reason": "공항 및 장시간 이동 시 편안함을 최우선으로 고려했습니다.",
                    "checklist": ["목베개", "이어폰", "가디건"]
                }
            ]
        }


# -----------------------------
# App UI
# -----------------------------
st.set_page_config("Tripfit", "🧳", layout="wide")
st.title("🧳 Tripfit")
st.caption("API Key는 쓰되, 결제 없어도 테스트 가능한 구조")

with st.sidebar:
    use_ai = st.checkbox("🤖 AI 코디 사용", value=True)
    openai_key = st.text_input(
        "OPENAI API KEY",
        type="password",
        value=st.secrets.get("OPENAI_API_KEY", "")
    )

destination = st.text_input("목적지", "파리")
trip_date = st.date_input("여행 날짜", today_kr() + relativedelta(days=7))
itinerary = st.text_area("일정", "박물관 투어 + 저녁 레스토랑")

user = {
    "gender": st.selectbox("성별", ["여성", "남성"]),
    "age": st.selectbox("나이대", ["20대", "30대", "40대"]),
    "style": st.selectbox("스타일", ["미니멀", "캐주얼", "스트릿"]),
    "season": season_from_month(trip_date.month),
    "itinerary": itinerary,
}

if st.button("✨ 코디 생성"):
    geo = geocode_city(destination)
    if not geo:
        st.error("도시를 찾을 수 없어요")
        st.stop()

    weather = WeatherInfo(
        city=geo["name"],
        country=geo.get("country", ""),
        lat=geo["latitude"],
        lon=geo["longitude"],
        summary=fetch_weather(geo["latitude"], geo["longitude"], trip_date),
    )

    if use_ai and openai_key:
        result = generate_with_ai_or_mock(openai_key, user, weather, trip_date)
    else:
        st.info("AI 비활성화 → 더미 코디 사용")
        result = generate_with_ai_or_mock(None, user, weather, trip_date)

    st.subheader("👗 추천 코디")
    for o in result["outfits"]:
        st.markdown(f"### {o['title']}")
        st.write("🧩 구성:", ", ".join(o["items"]))
        st.write("💡 이유:", o["reason"])
        for c in o["checklist"]:
            st.checkbox(c)
