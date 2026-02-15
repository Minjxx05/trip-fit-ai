# -*- coding: utf-8 -*-

import os
from datetime import date
import streamlit as st
from dotenv import load_dotenv

from services.weather_service import get_daily_weather, summarize_weather
from services.gemini_service import GeminiConfig, generate_outfit_json, generate_outfit_image
from services.moodboard_service import moodboard_image_urls

load_dotenv()

st.set_page_config(
    page_title="Tripfit",
    page_icon="🧳",
    layout="wide"
)

# =========================
# 세션 상태 초기화
# =========================
if "packing_list" not in st.session_state:
    st.session_state.packing_list = []

if "last_outfits" not in st.session_state:
    st.session_state.last_outfits = None

if "weather" not in st.session_state:
    st.session_state.weather = None

# =========================
# 사이드바
# =========================
st.sidebar.title("Tripfit Settings")

destination = st.sidebar.text_input("Destination (City)", value="Paris")

col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input("Start Date", value=date.today())
end_date = col2.date_input("End Date", value=date.today())

gender = st.sidebar.selectbox("Gender", ["Female", "Male", "Other"])
style = st.sidebar.selectbox("Style", ["Minimal", "Vintage", "Street", "Casual", "Formal", "Lovely"])
season = st.sidebar.selectbox("Season", ["Spring", "Summer", "Fall", "Winter", "Auto"])
tpo = st.sidebar.multiselect(
    "Main Activities",
    ["Museum", "City Walk", "Restaurant", "Nature", "Shopping", "Club", "Business"],
    default=["Museum", "City Walk"]
)

with st.sidebar.expander("Model Settings", expanded=False):
    text_model = st.text_input(
        "Text Model",
        value=os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
    )
    image_model = st.text_input(
        "Image Model",
        value=os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    )
    generate_images = st.checkbox("Generate Outfit Images", value=True)

cfg = GeminiConfig(
    text_model=text_model,
    image_model=image_model
)

# =========================
# 상단 정보 영역
# =========================
st.title("Tripfit - Travel Outfit AI")

days_to_trip = (start_date - date.today()).days
st.caption("D-Day: {0:+d} days | Destination: {1}".format(days_to_trip, destination))

colA, colB, colC = st.columns([1.2, 1.2, 1.6])

# 날씨
with colA:
    st.subheader("Weather")

    if st.button("Load Weather"):
        st.session_state.weather = get_daily_weather(
            destination,
            str(start_date),
            str(end_date)
        )

    if st.session_state.weather:
        weather_data = st.session_state.weather
        if not weather_data.get("ok"):
            st.error(weather_data.get("error"))
        else:
            st.success(summarize_weather(weather_data))
            with st.expander("Details"):
                st.dataframe(weather_data["daily"])

# 선택 요약
with colB:
    st.subheader("Selections")
    st.write("Gender:", gender)
    st.write("Style:", style)
    st.write("Season:", season)

# 안내
with colC:
    st.subheader("Generate 3 Outfit Recommendations")
    st.write("Click the button below to generate outfits based on your trip information.")

st.divider()

# =========================
# 프롬프트 파일 읽기
# =========================
prompt_path = os.path.join("prompts", "outfit_prompt.txt")
with open(prompt_path, "r", encoding="utf-8") as f:
    prompt_template = f.read()

weather_summary = (
    summarize_weather(st.session_state.weather)
    if st.session_state.weather
    else "Weather not loaded"
)

user_payload = {
    "destination": destination,
    "date_range": "{0} ~ {1}".format(start_date, end_date),
    "gender": gender,
    "style": style,
    "season": season,
    "tpo": tpo,
    "weather_summary": weather_summary
}

# =========================
# 코디 생성 버튼
# =========================
colX, colY = st.columns(2)

with colX:
    if st.button("Generate 3 Outfits", type="primary"):
        with st.spinner("Generating outfits..."):
            result = generate_outfit_json(
                prompt_template,
                user_payload,
                cfg
            )

        if not result["ok"]:
            st.error(result["error"])
        else:
            st.session_state.last_outfits = result["data"]
            st.success("Outfits generated successfully!")

with colY:
    if st.button("Clear Packing List"):
        st.session_state.packing_list = []
        st.success("Packing list cleared.")

# =========================
# 결과 출력
# =========================
data = st.session_state.last_outfits

if data:
    st.subheader("Recommended Outfits")

    outfits = data.get("outfits", [])

    for idx, outfit in enumerate(outfits, start=1):

        with st.container(border=True):

            left, right = st.columns([1.2, 0.8])

            with left:
                st.markdown("### {0}. {1}".format(
                    idx,
                    outfit.get("title", "Untitled")
                ))

                st.write("TPO:", outfit.get("tpo", "-"))

                items = outfit.get("items", {})

                st.write("Top:", ", ".join(items.get("top", [])))
                st.write("Bottom:", ", ".join(items.get("bottom", [])))
                st.write("Outer:", ", ".join(items.get("outer", [])))
                st.write("Shoes:", ", ".join(items.get("shoes", [])))
                st.write("Accessories:", ", ".join(items.get("accessories", [])))

                st.markdown("Reason")
                for reason in outfit.get("reasons", []):
                    st.write("-", reason)

                additions = outfit.get("packing_list_additions", [])

                if st.button("Add to Packing List", key="pack_{0}".format(idx)):
                    for item in additions:
                        if item not in st.session_state.packing_list:
                            st.session_state.packing_list.append(item)
                    st.success("Added to packing list.")

            with right:
                if generate_images:
                    img_prompt = (
                        "Create a realistic fashion lookbook photo for a trip to {0}. "
                        "Style: {1}. Season: {2}. TPO: {3}. "
                        "Outfit items: {4}. "
                        "No text in image."
                    ).format(
                        destination,
                        style,
                        season,
                        outfit.get("tpo", ""),
                        str(items)
                    )

                    with st.spinner("Generating image..."):
                        img_res = generate_outfit_image(
                            img_prompt,
                            cfg
                        )

                    if img_res["ok"]:
                        st.image(img_res["image"], use_container_width=True)
                    else:
                        st.info("Image generation failed.")

# =========================
# 패킹 리스트
# =========================
st.divider()
st.subheader("Packing Checklist")

if not st.session_state.packing_list:
    st.info("No items added yet.")
else:
    for i, item in enumerate(st.session_state.packing_list):
        col1, col2 = st.columns([0.9, 0.1])
        col1.checkbox(item, key="chk_{0}".format(i))
        if col2.button("Remove", key="del_{0}".format(i)):
            st.session_state.packing_list.pop(i)
            st.rerun()

# =========================
# 무드보드
# =========================
st.divider()
st.subheader("Moodboard")

images = moodboard_image_urls(destination, season, style, n=6)
cols = st.columns(3)

for i, img_url in enumerate(images):
    cols[i % 3].image(img_url, use_container_width=True)
