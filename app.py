# -*- coding: utf-8 -*-

import os
import json
from datetime import date
from dataclasses import dataclass
from typing import Any, Optional, Tuple, List
from urllib.parse import quote

import streamlit as st
from dotenv import load_dotenv
import requests

# Gemini SDK
from google import genai

load_dotenv()

# =========================
# Config
# =========================
@dataclass
class GeminiConfig:
    text_model: str
    image_model: str

def get_cfg() -> GeminiConfig:
    return GeminiConfig(
        text_model=os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash"),
        image_model=os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
    )

def gemini_client() -> genai.Client:
    # GEMINI_API_KEY env 를 사용
    return genai.Client()

# =========================
# Weather (Open-Meteo, no key)
# =========================
def geocode_city(city: str) -> Optional[Tuple[float, float]]:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": city, "count": 1, "language": "en", "format": "json"}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data.get("results"):
        return None
    item = data["results"][0]
    return float(item["latitude"]), float(item["longitude"])

def get_daily_weather(city: str, start_date: str, end_date: str) -> dict:
    coords = geocode_city(city)
    if not coords:
        return {"ok": False, "error": f"Could not find city: {city}"}
    lat, lon = coords

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max",
        "timezone": "auto",
        "start_date": start_date,
        "end_date": end_date,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    j = r.json()

    daily = j.get("daily", {})
    dates = daily.get("time", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    pop = daily.get("precipitation_probability_max", [])
    wind = daily.get("windspeed_10m_max", [])

    rows = []
    for i, d in enumerate(dates):
        rows.append({
            "date": d,
            "tmin": tmin[i] if i < len(tmin) else None,
            "tmax": tmax[i] if i < len(tmax) else None,
            "precip_prob": pop[i] if i < len(pop) else None,
            "wind_max": wind[i] if i < len(wind) else None,
        })
    return {"ok": True, "city": city, "lat": lat, "lon": lon, "daily": rows}

def summarize_weather(weather: Optional[dict]) -> str:
    if not weather:
        return "Weather not loaded"
    if not weather.get("ok"):
        return weather.get("error", "Weather error")
    rows = weather.get("daily", [])
    if not rows:
        return "No weather data"
    tmins = [r["tmin"] for r in rows if r.get("tmin") is not None]
    tmaxs = [r["tmax"] for r in rows if r.get("tmax") is not None]
    pops = [r["precip_prob"] for r in rows if r.get("precip_prob") is not None]

    parts = []
    if tmins and tmaxs:
        parts.append(f"Avg min {sum(tmins)/len(tmins):.1f}C / Avg max {sum(tmaxs)/len(tmaxs):.1f}C")
    if pops:
        parts.append(f"Max precip {max(pops)}%")
    return " | ".join(parts) if parts else "Weather summary unavailable"

# =========================
# Moodboard (Unsplash source)
# =========================
def moodboard_image_urls(city: str, season: str, style: str, n: int = 6) -> List[str]:
    q = quote(f"{city} {season} street style {style}")
    return [f"https://source.unsplash.com/featured/800x600?{q}&sig={i}" for i in range(n)]

# =========================
# Prompt
# =========================
DEFAULT_OUTFIT_PROMPT = """너는 여행 코디 전문 스타일리스트야.
사용자 정보와 여행 정보를 바탕으로 여행지 TPO와 날씨에 맞는 코디 3가지를 추천해줘.

반드시 JSON만 출력해. (마크다운 금지)
스키마:
{
  "destination": string,
  "date_range": string,
  "weather_summary": string,
  "outfits": [
    {
      "title": string,
      "tpo": string,
      "items": {
        "top": [string],
        "bottom": [string],
        "outer": [string],
        "shoes": [string],
        "accessories": [string]
      },
      "reasons": [string],
      "packing_list_additions": [string]
    }
  ]
}

규칙:
- 코디는 3개
- reasons는 각 코디당 2~4개
- packing_list_additions는 '캐리어 패킹'에 바로 쓸 수 있게 구체 품목명으로 작성
- 과도한 브랜드/가격 언급 금지
"""

def load_prompt() -> str:
    # prompts/outfit_prompt.txt 가 있으면 읽고, 없으면 기본 프롬프트 사용
    path = os.path.join("prompts", "outfit_prompt.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return DEFAULT_OUTFIT_PROMPT

# =========================
# Gemini calls
# =========================
def generate_outfit_json(prompt_template: str, user_payload: dict[str, Any], cfg: GeminiConfig) -> dict:
    client = gemini_client()

    full_prompt = prompt_template.strip() + "\n\n[사용자 입력]\n" + json.dumps(user_payload, ensure_ascii=False)

    resp = client.models.generate_content(
        model=cfg.text_model,
        contents=[full_prompt],
    )

    text = (resp.text or "").strip()
    try:
        first = text.find("{")
        last = text.rfind("}")
        parsed = json.loads(text[first:last+1])
        return {"ok": True, "data": parsed, "raw": text}
    except Exception as e:
        return {"ok": False, "error": f"JSON parse failed: {e}", "raw": text}

def generate_outfit_image(image_prompt: str, cfg: GeminiConfig) -> dict:
    client = gemini_client()

    resp = client.models.generate_content(
        model=cfg.image_model,
        contents=[image_prompt],
    )

    images = []
    texts = []
    parts = getattr(resp, "parts", None) or []
    for part in parts:
        if getattr(part, "text", None):
            texts.append(part.text)
        elif getattr(part, "inline_data", None) is not None:
            try:
                images.append(part.as_image())
            except Exception:
                pass

    if not images:
        return {"ok": False, "error": "No image returned", "texts": texts}
    return {"ok": True, "image": images[0], "texts": texts}

# =========================
# UI
# =========================
st.set_page_config(page_title="Tripfit", page_icon="🧳", layout="wide")

# Session state
if "packing_list" not in st.session_state:
    st.session_state.packing_list = []
if "last_outfits" not in st.session_state:
    st.session_state.last_outfits = None
if "weather" not in st.session_state:
    st.session_state.weather = None

st.sidebar.title("Tripfit Settings")

destination = st.sidebar.text_input("Destination (City)", value="Paris")

c1, c2 = st.sidebar.columns(2)
start_dt = c1.date_input("Start Date", value=date.today())
end_dt = c2.date_input("End Date", value=date.today())

gender = st.sidebar.selectbox("Gender", ["Female", "Male", "Other"])
style = st.sidebar.selectbox("Style", ["Minimal", "Vintage", "Street", "Casual", "Formal", "Lovely"])
season = st.sidebar.selectbox("Season", ["Spring", "Summer", "Fall", "Winter", "Auto"])
tpo = st.sidebar.multiselect(
    "Main Activities",
    ["Museum", "City Walk", "Restaurant", "Nature", "Shopping", "Club", "Business"],
    default=["Museum", "City Walk"]
)

with st.sidebar.expander("Model Settings", expanded=False):
    cfg = get_cfg()
    text_model = st.text_input("Text Model", value=cfg.text_model)
    image_model = st.text_input("Image Model", value=cfg.image_model)
    generate_images = st.checkbox("Generate Outfit Images", value=True)

cfg = GeminiConfig(text_model=text_model, image_model=image_model)

st.title("Tripfit - Travel Outfit AI")

days_to_trip = (start_dt - date.today()).days
st.caption(f"D-Day: {days_to_trip:+d} days | Destination: {destination}")

topA, topB, topC = st.columns([1.2, 1.2, 1.6])

with topA:
    st.subheader("Weather")
    if st.button("Load Weather", use_container_width=True):
        st.session_state.weather = get_daily_weather(destination, str(start_dt), str(end_dt))

    if st.session_state.weather:
        w = st.session_state.weather
        if not w.get("ok"):
            st.error(w.get("error"))
        else:
            st.success(summarize_weather(w))
            with st.expander("Daily details", expanded=False):
                st.dataframe(w["daily"], use_container_width=True)

with topB:
    st.subheader("Selections")
    st.write("Gender:", gender)
    st.write("Style:", style)
    st.write("Season:", season)

with topC:
    st.subheader("Generate 3 outfit recommendations")
    st.write("Click the button to generate outfits based on trip info and weather summary.")

st.divider()

prompt_template = load_prompt()
weather_summary = summarize_weather(st.session_state.weather)

user_payload = {
    "destination": destination,
    "date_range": f"{start_dt} ~ {end_dt}",
    "gender": gender,
    "style": style,
    "season": season,
    "tpo": tpo,
    "weather_summary": weather_summary,
}

btn1, btn2 = st.columns(2)

with btn1:
    if st.button("Generate 3 Outfits", type="primary", use_container_width=True):
        # API 키 체크
        if not os.getenv("GEMINI_API_KEY"):
            st.error("GEMINI_API_KEY is not set. Put it in your .env file.")
        else:
            with st.spinner("Generating outfits..."):
                result = generate_outfit_json(prompt_template, user_payload, cfg)

            if not result["ok"]:
                st.error(result["error"])
                st.code(result.get("raw", ""), language="text")
            else:
                st.session_state.last_outfits = result["data"]
                st.success("Outfits generated!")

with btn2:
    if st.button("Clear Packing List", use_container_width=True):
        st.session_state.packing_list = []
        st.toast("Cleared packing list")

data = st.session_state.last_outfits
if data:
    st.subheader("Recommended Outfits")
    outfits = data.get("outfits", [])

    for idx, outfit in enumerate(outfits, start=1):
        with st.container(border=True):
            left, right = st.columns([1.2, 0.8])

            items = outfit.get("items", {})
            additions = outfit.get("packing_list_additions", [])

            with left:
                st.markdown(f"### {idx}. {outfit.get('title', 'Untitled')}")
                st.write("TPO:", outfit.get("tpo", "-"))

                st.write("Top:", ", ".join(items.get("top", [])) or "-")
                st.write("Bottom:", ", ".join(items.get("bottom", [])) or "-")
                st.write("Outer:", ", ".join(items.get("outer", [])) or "-")
                st.write("Shoes:", ", ".join(items.get("shoes", [])) or "-")
                st.write("Accessories:", ", ".join(items.get("accessories", [])) or "-")

                st.markdown("**Reasons**")
                for r in outfit.get("reasons", []):
                    st.write("- " + str(r))

                if st.button("Add to Packing List", key=f"pack_{idx}"):
                    for item in additions:
                        if item not in st.session_state.packing_list:
                            st.session_state.packing_list.append(item)
                    st.toast("Added")

                with st.expander("Share text", expanded=False):
                    share_text = f"[Tripfit] {destination} Outfit #{idx} - {outfit.get('title','')}\n" + \
                                 "\n".join([f"- {x}" for x in additions])
                    st.code(share_text, language="text")

            with right:
                st.markdown("#### Outfit Image")
                if generate_images and os.getenv("GEMINI_API_KEY"):
                    img_prompt = (
                        f"Create a high-quality realistic fashion lookbook photo for a trip to {destination}. "
                        f"Style: {style}. Season: {season}. TPO: {outfit.get('tpo','')}. "
                        f"Outfit items: top({', '.join(items.get('top', []))}), "
                        f"bottom({', '.join(items.get('bottom', []))}), "
                        f"outer({', '.join(items.get('outer', []))}), "
                        f"shoes({', '.join(items.get('shoes', []))}), "
                        f"accessories({', '.join(items.get('accessories', []))}). "
                        f"No text in image. Clean background, realistic lighting."
                    )
                    with st.spinner("Generating image..."):
                        img_res = generate_outfit_image(img_prompt, cfg)
                    if img_res.get("ok"):
                        st.image(img_res["image"], use_container_width=True)
                    else:
                        st.info("Image generation failed. Check model name / quota / key.")
                        if img_res.get("texts"):
                            st.caption(" ".join(img_res["texts"]))
                else:
                    st.caption("Image generation is off or GEMINI_API_KEY is missing.")

st.divider()
st.subheader("Packing Checklist")

if not st.session_state.packing_list:
    st.info("No items yet. Use 'Add to Packing List' above.")
else:
    for i, item in enumerate(st.session_state.packing_list):
        a, b = st.columns([0.9, 0.1])
        a.checkbox(item, key=f"chk_{i}")
        if b.button("Remove", key=f"del_{i}"):
            st.session_state.packing_list.pop(i)
            st.rerun()

st.divider()
st.subheader("Moodboard")

urls = moodboard_image_urls(destination, season, style, n=6)
cols = st.columns(3)
for i, u in enumerate(urls):
    cols[i % 3].image(u, use_container_width=True)
