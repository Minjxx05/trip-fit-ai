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
# Theme (style -> UI tone)
# =============================
STYLE_OPTIONS = [
    "미니멀", "빈티지", "스트릿", "캐주얼",
    "클래식", "러블리", "고프코어", "시티보이/시티걸"
]

STYLE_THEME = {
    "미니멀": {"g1": "#2b2b2b", "g2": "#7a7a7a", "accent": "#cfcfcf", "card": "rgba(255,255,255,0.04)"},
    "빈티지": {"g1": "#b16a3c", "g2": "#6b3f2a", "accent": "#f3d1b3", "card": "rgba(255,255,255,0.05)"},
    "스트릿": {"g1": "#ff3d7f", "g2": "#7c3aed", "accent": "#ffd1e2", "card": "rgba(255,255,255,0.05)"},
    "캐주얼": {"g1": "#22c55e", "g2": "#06b6d4", "accent": "#d7ffe6", "card": "rgba(255,255,255,0.05)"},
    "클래식": {"g1": "#1f2937", "g2": "#b45309", "accent": "#fde68a", "card": "rgba(255,255,255,0.04)"},
    "러블리": {"g1": "#ff6cab", "g2": "#7366ff", "accent": "#ffe0ef", "card": "rgba(255,255,255,0.06)"},
    "고프코어": {"g1": "#16a34a", "g2": "#0f172a", "accent": "#b7f7c9", "card": "rgba(255,255,255,0.04)"},
    "시티보이/시티걸": {"g1": "#0ea5e9", "g2": "#111827", "accent": "#cdeeff", "card": "rgba(255,255,255,0.04)"},
}

def inject_css(theme: dict):
    # 버튼/카드/뱃지/칩/포커스 링 등 톤을 통일
    st.markdown(
        f"""
<style>
:root {{
  --g1: {theme["g1"]};
  --g2: {theme["g2"]};
  --accent: {theme["accent"]};
  --cardbg: {theme["card"]};
}}

/* 메인 CTA 버튼 */
div.stButton > button {{
  background: linear-gradient(135deg, var(--g1) 0%, var(--g2) 100%) !important;
  color: white !important;
  border-radius: 14px !important;
  height: 3.2em !important;
  font-size: 1.05rem !important;
  font-weight: 800 !important;
  border: none !important;
  transition: transform .15s ease, box-shadow .15s ease !important;
}}
div.stButton > button:hover {{
  transform: translateY(-2px);
  box-shadow: 0 10px 22px rgba(0,0,0,0.25);
}}
div.stButton > button:active {{
  transform: scale(0.98);
}}

/* 카드 UI */
.trip-card {{
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 18px;
  padding: 14px 14px;
  background: var(--cardbg);
}}
.card-title {{
  font-size: 18px;
  font-weight: 800;
  margin-bottom: 4px;
}}
.badge {{
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.10);
  margin-right: 6px;
  font-size: 12px;
  border: 1px solid rgba(255,255,255,0.12);
}}
.item-chip {{
  display: inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.14);
  margin: 4px 6px 0 0;
  font-size: 12px;
}}
/* 포커스 링: 테마 악센트 */
div[data-baseweb="select"] *:focus {{
  box-shadow: 0 0 0 2px var(--accent) !important;
}}
</style>
        """,
        unsafe_allow_html=True,
    )


# =============================
# Weather (Open-Meteo free)
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
        timeout=12,
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
        timeout=12,
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
# Calendar itinerary
# =============================
SLOTS = ["오전", "오후", "저녁"]

def build_calendar_rows(start_date: date, days: int, plans: list[dict]) -> list[dict]:
    rows = []
    for i in range(days):
        d = start_date + relativedelta(days=i)
        for slot in SLOTS:
            plan_text = ""
            for p in plans:
                if p["date"] == d.isoformat() and p["slot"] == slot:
                    plan_text = (p["plan"] or "").strip()
                    break
            rows.append({"날짜": d.isoformat(), "시간대": slot, "일정": plan_text if plan_text else "—"})
    return rows


# =============================
# AI Prompt / Mock / Fallback
# =============================
def build_prompt(user: dict, weather: WeatherInfo, start_date: date, days: int, calendar_rows: list[dict]) -> str:
    calendar_json = json.dumps(calendar_rows, ensure_ascii=False)

    return f"""
너는 여행 전문 패션 코디네이터다.
여행지 날씨와 사용자의 스타일 취향, 그리고 '캘린더 형식 일정'에 맞춰
실용적이면서 사진에 잘 어울리는 코디를 추천해야 한다.

[사용자]
- 성별: {user["gender"]}
- 나이대: {user["age_group"]}
- 스타일 성향: {user["style_pref"]}
- 계절: {user["season"]}

[여행]
- 목적지: {weather.city}, {weather.country}
- 시작일: {start_date.isoformat()} ({dday_string(start_date)})
- 기간: {days}일
- 날씨 요약(시작일 기준): {weather.summary}

[일정 캘린더(JSON)]
{calendar_json}

[출력 규칙: 반드시 JSON만]
- 날짜별로 코디를 묶어서 제공
- 각 날짜마다 day_outfits는 최소 1개, 최대 2개(오전/오후/저녁 일정 커버)
- 코디에는 반드시: 핵심 아이템, 추천 이유(날씨+일정 근거), 캐리어 체크리스트 포함
- 브랜드/가격 언급 금지(품목 중심)
- 한국어

{{
  "destination_card": {{
    "destination": "도시/국가",
    "dday": "D-3",
    "weather_one_liner": "한 줄 날씨"
  }},
  "calendar_outfits": [
    {{
      "date": "YYYY-MM-DD",
      "day_summary": "그날 일정 핵심 요약(1줄)",
      "day_outfits": [
        {{
          "title": "코디 이름",
          "covers_slots": ["오전","오후"],
          "items": {{
            "top": ["..."],
            "bottom": ["..."],
            "outer": ["..."],
            "shoes": ["..."],
            "accessories": ["..."]
          }},
          "key_items": ["핵심 3~5개"],
          "why_recommended": "추천 이유(2~4문장)",
          "packing_checklist": ["체크리스트 8~14개"]
        }}
      ]
    }}
  ]
}}
""".strip()

def mock_generate_calendar(user: dict, weather: WeatherInfo, start_date: date, days: int, calendar_rows: list[dict]) -> dict:
    dest = f"{weather.city}, {weather.country}".strip().strip(",")
    dest_card = {
        "destination": dest,
        "dday": dday_string(start_date),
        "weather_one_liner": weather.summary,
    }

    by_date = {}
    for r in calendar_rows:
        by_date.setdefault(r["날짜"], []).append(r)

    calendar_outfits = []
    for d, rows in by_date.items():
        plans = [f'{x["시간대"]}:{x["일정"]}' for x in rows if x["일정"] != "—"]
        summary = " / ".join(plans) if plans else "가벼운 자유 일정"

        calendar_outfits.append({
            "date": d,
            "day_summary": summary[:80] + ("…" if len(summary) > 80 else ""),
            "day_outfits": [
                {
                    "title": f"👟 {user['style_pref']} 데이룩",
                    "covers_slots": ["오전", "오후"],
                    "items": {
                        "top": ["베이직 상의", f"{user['style_pref']} 포인트 톱"],
                        "bottom": ["편한 팬츠/스커트"],
                        "outer": ["가벼운 자켓/가디건"],
                        "shoes": ["스니커즈(도보 최적)"],
                        "accessories": ["크로스백", "선글라스/모자"],
                    },
                    "key_items": ["편한 신발", "레이어드 아우터", "크로스백"],
                    "why_recommended": f"{weather.summary} 기준으로 이동/투어에 무리 없게 구성했어요. 사진에는 실루엣이 깔끔하게 나오도록 톤을 정리했습니다.",
                    "packing_checklist": ["상/하의 여벌", "양말", "보조배터리", "선크림", "물티슈", "우산(선택)", "상비약", "에코백"],
                },
                {
                    "title": "🌙 저녁 무드룩",
                    "covers_slots": ["저녁"],
                    "items": {
                        "top": ["니트/셔츠(단정)"],
                        "bottom": ["슬랙스/미디 스커트"],
                        "outer": ["블레이저/코트(선택)"],
                        "shoes": ["로퍼/단정 스니커즈"],
                        "accessories": ["미니백", "작은 액세서리"],
                    },
                    "key_items": ["단정한 상의", "미니백", "로퍼"],
                    "why_recommended": "저녁 조명/실내 동선에 맞춰 단정한 소재와 라인을 우선했어요. 과하지 않게 포인트만 주면 사진이 안정적으로 나옵니다.",
                    "packing_checklist": ["단정 상의", "향/미스트", "립밤", "작은 액세서리", "여분 스타킹/양말"],
                }
            ],
        })

    return {"destination_card": dest_card, "calendar_outfits": calendar_outfits}

def generate_with_ai_or_fallback(openai_key: str, user: dict, weather: WeatherInfo, start_date: date, days: int, calendar_rows: list[dict]) -> tuple[dict, bool]:
    if not openai_key:
        return mock_generate_calendar(user, weather, start_date, days, calendar_rows), True

    try:
        client = OpenAI(api_key=openai_key)
        prompt = build_prompt(user, weather, start_date, days, calendar_rows)
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
            temperature=0.6,
        )
        text = (resp.output_text or "").strip()

        # JSON 안전 파싱
        try:
            return json.loads(text), False
        except json.JSONDecodeError:
            s = text.find("{")
            e = text.rfind("}")
            if s != -1 and e != -1 and e > s:
                return json.loads(text[s:e+1]), False
            raise

    except Exception:
        # ✅ 에러코드/상세는 화면에 절대 노출하지 않음
        return mock_generate_calendar(user, weather, start_date, days, calendar_rows), True


# =============================
# UI render
# =============================
def render_destination_card(card: dict):
    st.markdown(
        f"""
<div class="trip-card">
  <div class="card-title">🧳 {card.get("destination","")}</div>
  <div style="margin-top:8px;">
    <span class="badge">{card.get("dday","")}</span>
    <span class="badge">{card.get("weather_one_liner","")}</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

def render_outfit(outfit: dict, key_prefix: str):
    st.markdown(f"### {outfit.get('title','')}")
    slots = outfit.get("covers_slots", [])
    if slots:
        st.caption("🗓️ " + " · ".join(slots))

    items = outfit.get("items", {})
    cols = st.columns(2)
    with cols[0]:
        st.write("🧩 착장")
        for cat in ["top", "bottom", "outer", "shoes", "accessories"]:
            vals = [v for v in (items.get(cat, []) or []) if v]
            if vals:
                st.write(f"- {cat.upper()}")
                for v in vals:
                    st.markdown(f"<span class='item-chip'>{v}</span>", unsafe_allow_html=True)

    with cols[1]:
        st.write("⭐ 핵심")
        for v in outfit.get("key_items", []):
            st.markdown(f"<span class='item-chip'>{v}</span>", unsafe_allow_html=True)

    st.write("💬 이유")
    st.write(outfit.get("why_recommended", ""))

    st.write("✅ 체크리스트")
    for i, item in enumerate(outfit.get("packing_checklist", [])[:18]):
        st.checkbox(item, key=f"{key_prefix}_{i}")

def moodboard_images(destination: str, style_pref: str):
    st.subheader("🖼️ 무드보드 (레퍼런스)")
    q = f"{destination} {style_pref} outfit street"
    cols = st.columns(3)
    for i in range(6):
        url = f"https://source.unsplash.com/600x800/?{requests.utils.quote(q)}&sig={i}"
        with cols[i % 3]:
            st.image(url, use_container_width=True)
    st.caption("레퍼런스 이미지(공개 이미지 기반).")

def moodboard_links(destination: str, style_pref: str):
    q = f"{destination} {style_pref} ootd"
    st.link_button("🔎 Google 이미지", f"https://www.google.com/search?tbm=isch&q={requests.utils.quote(q)}")
    st.link_button("📌 Pinterest", f"https://www.pinterest.com/search/pins/?q={requests.utils.quote(q)}")


# =============================
# App
# =============================
st.set_page_config(page_title="Tripfit", page_icon="🧳", layout="wide")

st.title("🧳 Tripfit ✨")

with st.sidebar:
    st.subheader("⚙️ 설정")
    use_ai = st.toggle("🤖 AI 코디", value=True)
    openai_key = st.text_input("🔑 OpenAI API Key", type="password", value=safe_get_secret("OPENAI_API_KEY"))

st.divider()

c1, c2 = st.columns([1, 1])

with c1:
    destination_input = st.text_input("📍 목적지", placeholder="예: 파리, 도쿄, 서울")
    start_date = st.date_input("🗓️ 시작일", value=today_kr() + relativedelta(days=7))
    days = st.slider("⏳ 여행 기간(일)", min_value=1, max_value=10, value=3)

with c2:
    gender = st.selectbox("🙋 성별", ["여성", "남성", "기타/선호없음"])
    age_group = st.selectbox("🎂 나이대", ["10대", "20대", "30대", "40대", "50대+"])
    style_pref = st.selectbox("👗 스타일", STYLE_OPTIONS)

# ✅ 스타일 선택값으로 테마 적용 (리런 때마다 자동 반영)
inject_css(STYLE_THEME.get(style_pref, STYLE_THEME["러블리"]))

user = {
    "gender": gender,
    "age_group": age_group,
    "style_pref": style_pref,
    "season": season_from_month(start_date.month),
}

st.subheader("🗓️ 일정")
plans = []
day_tabs = st.tabs([(start_date + relativedelta(days=i)).strftime("📅 %m/%d") for i in range(days)])

for i, tab in enumerate(day_tabs):
    d = start_date + relativedelta(days=i)
    with tab:
        cols = st.columns(3)
        for j, slot in enumerate(SLOTS):
            with cols[j]:
                txt = st.text_area(
                    f"🧩 {slot}",
                    key=f"plan_{d.isoformat()}_{slot}",
                    height=90,
                    placeholder="예: 박물관 / 카페 / 쇼핑"
                )
                plans.append({"date": d.isoformat(), "slot": slot, "plan": txt})

calendar_rows = build_calendar_rows(start_date, days, plans)

st.divider()
btn = st.button("🪄 코디 만들기", use_container_width=True)

if btn:
    if not destination_input.strip():
        st.error("📍 목적지를 입력해줘!")
        st.stop()

    with st.spinner("✨ 코디 준비 중..."):
        # 1) 지오코딩
        geo = None
        try:
            geo = geocode_city(destination_input.strip())
        except Exception:
            geo = None

        if not geo:
            st.error("😢 도시를 찾지 못했어. 도시명을 더 정확히 적어줘!")
            st.stop()

        city = geo.get("name", destination_input.strip())
        country = geo.get("country", "")
        lat = float(geo["latitude"])
        lon = float(geo["longitude"])

        # 2) 날씨
        try:
            wx = fetch_weather_one_liner(lat, lon, start_date)
        except Exception:
            wx = "날씨 정보 없음"

        weather = WeatherInfo(city=city, country=country, lat=lat, lon=lon, summary=wx)

        # 3) AI / fallback
        if use_ai:
            result, used_fallback = generate_with_ai_or_fallback(openai_key, user, weather, start_date, days, calendar_rows)
        else:
            result, used_fallback = mock_generate_calendar(user, weather, start_date, days, calendar_rows), True

    # Render
    dest_card = result.get("destination_card", {})
    dest_card.setdefault("destination", f"{city}, {country}".strip().strip(","))
    dest_card.setdefault("dday", dday_string(start_date))
    dest_card.setdefault("weather_one_liner", wx)
    render_destination_card(dest_card)

    # ✅ 에러코드 노출 없이 짧게만
    if used_fallback:
        st.info("🙂 샘플 코디로 보여줄게요!")

    st.subheader("🗂️ 일정표")
    st.dataframe(calendar_rows, use_container_width=True, hide_index=True)

    st.subheader("👗 날짜별 코디")
    cal = result.get("calendar_outfits", [])
    if not cal:
        st.info("다시 시도해줘!")
        st.stop()

    tabs = st.tabs([f"📅 {x['date']}" for x in cal])
    for t, day in zip(tabs, cal):
        with t:
            if day.get("day_summary"):
                st.caption(day["day_summary"])
            for k, outfit in enumerate(day.get("day_outfits", [])):
                st.divider()
                render_outfit(outfit, key_prefix=f"{day['date']}_{k}")

    moodboard_images(dest_card.get("destination", destination_input), style_pref)
    moodboard_links(dest_card.get("destination", destination_input), style_pref)

