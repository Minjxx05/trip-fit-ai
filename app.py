# -*- coding: utf-8 -*-

import os
import json
from datetime import date
from dataclasses import dataclass
from typing import Any, Optional, Tuple, List
from urllib.parse import quote

import streamlit as st
import requests
from google import genai

# =========================
# Gemini Config
# =========================
@dataclass
class GeminiConfig:
    api_key: str
    text_model: str
    image_model: str

def gemini_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)

# =========================
# Weather (Open-Meteo)
# =========================
def geocode_city(city: str) -> Optional[Tuple[float, float]]:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": city, "count": 1}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data.get("results"):
        return None
    item = data["results"][0]
    return float(item["latitude"]), float(item["longitude"])

def get_daily_weather(city: str, start_date: str, end_date: str) -> dict:
    coords = geocode_city(city)
    if not coords:
        return {"ok": False, "error": f"City not found: {city}"}

    lat, lon = coords

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto",
        "start_date": start_date,
        "end_date": end_date,
    }

    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    j = r.json()

    daily = j.get("daily", {})
    rows = []
    for i, d in enumerate(daily.get("time", [])):
        rows.append({
            "date": d,
            "tmin": daily.get("temperature_2m_min", [None])[i],
            "tmax": daily.get("temperature_2m_max", [None])[i],
            "precip": daily.get("precipitation_probability_max", [None])[i],
        })

    return {"ok": True, "daily": rows}

def summarize_weather(weather: Optional[dict]) -> str:
    if not weather or not weather.get("ok"):
        return "Weather not loaded"

    rows = weather.get("daily", [])
    if not rows:
        return "No weather data"

    tmins = [r["tmin"] for r in rows if r["tmin"]]
    tmaxs = [r["tmax"] for r in rows if r["tmax"]]

    if not tmins or not tmaxs:
        return "Weather summary unavailable"

    return f"Avg Min {sum(tmins)/len(tmins):.1f}C / Avg Max {sum(tmaxs)/len(tmaxs):.1f}C"

# =========================
# Gemini Calls
# =========================
def generate_outfits(cfg: GeminiConfig, prompt: str, payload: dict) -> dict:
    client = gemini_client(cfg.api_key)

    full_prompt = prompt + "\n\nUser Input:\n" + json.dumps(payload, ensure_ascii=False)

    resp = client.models.generate_content(
        model=cfg.text_model,
        contents=[full_prompt],
    )

    text = (resp.text or "").strip()

    try:
        first = text.find("{")
        last = text.rfind("}")
        parsed = json.loads(text[first:last+1])
        return {"ok": True, "data": parsed}
    except Exception as e:
        return {"ok": False, "error": str(e), "raw": text}

def generate_image(cfg: GeminiConfig, image_prompt: str):
    client = gemini_client(cfg.api_key)

    resp = client.models.generate_content(
        model=cfg.image_model,
        contents=[image_prompt],
    )

    parts = getattr(resp, "parts", []) or []

    for part in parts:
        if getattr(part, "inline_data", None):
            try:
                return {"ok": True, "image": part.as_image()}
            except:
                pass

    return {"ok": False}

# =========================
# Moodboard
# =========================
def moodboard(city: str, season: str, style: str):
    q = quote(f"{city} {season} street style {style}")
    return [f"https://source.unsplash.com/featured/800x600?{q}&sig={i}" for i in range(6)]

# =========================
# UI
# =========================
st.set_page_config(page_title="Tripfit", page_icon="🧳", layout="wide")

if "packing_list" not in st.session_state:
    st.session_state.packing_list = []
if "outfits" not in st.session_state:
    st.session_state.outfits = None
if "weather" not in st.session_state:
    st.session_state.weather = None

st.sidebar.title("Tripfit Settings")

# 🔐 API KEY 입력
api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

text_model = st.sidebar.text_input("Text Model", value="gemini-2.5-flash")
image_model = st.sidebar.text_input("Image Model", value="gemini-2.5-flash-image")

destination = st.sidebar.text_input("Destination", value="Paris")

c1, c2 = st.sidebar.columns(2)
start_dt = c1.date_input("Start", value=date.today())
end_dt = c2.date_input("End", value=date.today())

gender = st.sidebar.selectbox("Gender", ["Female", "Male", "Other"])
style = st.sidebar.selectbox("Style", ["Minimal", "Vintage", "Street", "Casual"])
season = st.sidebar.selectbox("Season", ["Spring", "Summer", "Fall", "Winter"])

cfg = GeminiConfig(api_key, text_model, image_model)

st.title("Tripfit AI")

# Weather
if st.button("Load Weather"):
    st.session_state.weather = get_daily_weather(destination, str(start_dt), str(end_dt))

st.write(summarize_weather(st.session_state.weather))

# Generate
if st.button("Generate Outfits", disabled=not api_key):
    payload = {
        "destination": destination,
        "date_range": f"{start_dt} ~ {end_dt}",
        "gender": gender,
        "style": style,
        "season": season,
        "weather": summarize_weather(st.session_state.weather)
    }

    prompt = "Generate 3 travel outfits in JSON format only."

    result = generate_outfits(cfg, prompt, payload)

    if result["ok"]:
        st.session_state.outfits = result["data"]
    else:
        st.error(result.get("error"))
        st.code(result.get("raw", ""))

# Show outfits
data = st.session_state.outfits
if data:
    for i, outfit in enumerate(data.get("outfits", []), start=1):
        st.subheader(f"{i}. {outfit.get('title','Untitled')}")

        items = outfit.get("items", {})
        st.write(items)

        if st.button("Add to Packing", key=f"pack{i}"):
            for item in outfit.get("packing_list_additions", []):
                if item not in st.session_state.packing_list:
                    st.session_state.packing_list.append(item)

        if api_key:
            img_prompt = f"Fashion photo of outfit for trip to {destination}. Items: {items}"
            img = generate_image(cfg, img_prompt)
            if img["ok"]:
                st.image(img["image"], use_container_width=True)

# Packing List
st.subheader("Packing List")
for i, item in enumerate(st.session_state.packing_list):
    st.checkbox(item, key=f"chk{i}")

# Moodboard
st.subheader("Moodboard")
for img in moodboard(destination, season, style):
    st.image(img)

