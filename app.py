import os
from datetime import date
import streamlit as st
from dotenv import load_dotenv

from services.weather_service import get_daily_weather, summarize_weather
from services.gemini_service import GeminiConfig, generate_outfit_json, generate_outfit_image
from services.moodboard_service import moodboard_image_urls

load_dotenv()

st.set_page_config(page_title="Tripfit", page_icon="🧳", layout="wide")

# ====== 세션 상태 ======
if "packing_list" not in st.session_state:
    st.session_state.packing_list = []  # list[str]
if "last_outfits" not in st.session_state:
    st.session_state.last_outfits = None  # dict
if "weather" not in st.session_state:
    st.session_state.weather = None

# ====== 사이드바 입력 ======
st.sidebar.title("🧳 Tripfit 설정")

destination = st.sidebar.text_input("목적지(도시)", value="Paris")
colA, colB = st.sidebar.columns(2)
start_date = colA.date_input("출발일", value=date.today())
end_date = colB.date_input("귀국일", value=date.today())

gender = st.sidebar.selectbox("성별", ["여성", "남성", "무관/기타"])
style = st.sidebar.selectbox("스타일 취향", ["미니멀", "빈티지", "스트릿", "캐주얼", "포멀", "러블리"])
season = st.sidebar.selectbox("계절감", ["봄", "여름", "가을", "겨울", "현지 기후에 맞게 자동"])
tpo = st.sidebar.multiselect(
    "주요 일정(TPO)",
    ["박물관/미술관", "도심 산책", "맛집 투어", "자연/하이킹", "쇼핑", "클럽/바", "비즈니스/회의"],
    default=["박물관/미술관", "도심 산책"]
)

with st.sidebar.expander("⚙️ 모델 설정", expanded=False):
    text_model = st.text_input("텍스트 모델", value=os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash"))
    image_model = st.text_input("이미지 모델(Nano Banana)", value=os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"))
    gen_images = st.checkbox("코디 이미지도 생성하기(느려질 수 있음)", value=True)

cfg = GeminiConfig(text_model=text_model, image_model=image_model)

# ====== 상단: 디데이 + 날씨 위젯 ======
st.title("Tripfit ✈️ 오늘의 여행 룩 & 캐리어 패킹")
days_to_trip = (start_date - date.today()).days
st.caption(f"여행 D-Day: {days_to_trip:+d}일 · 목적지: {destination}")

top1, top2, top3 = st.columns([1.2, 1.2, 1.6])

with top1:
    st.subheader("🌦️ 날씨")
    if st.button("날씨 불러오기", use_container_width=True):
        st.session_state.weather = get_daily_weather(destination, str(start_date), str(end_date))

    if st.session_state.weather:
        w = st.session_state.weather
        if not w.get("ok"):
            st.error(w["error"])
        else:
            st.success(summarize_weather(w))
            with st.expander("일자별 상세", expanded=False):
                st.dataframe(w["daily"], use_container_width=True)

with top2:
    st.subheader("⚡ 퀵 선택")
    st.write(f"- 성별: **{gender}**")
    st.write(f"- 스타일: **{style}**")
    st.write(f"- 계절: **{season}**")

with top3:
    st.subheader("🧩 오늘의 추천 여행 룩")
    st.write("아래에서 **코디 생성**을 누르면 카드 형태로 3가지 룩을 보여줘요. "
             "각 룩에는 추천 이유와 ‘캐리어에 담기’가 포함됩니다. "
             "PRD의 결과 화면 요구사항을 그대로 반영했습니다.")  # :contentReference[oaicite:10]{index=10}

st.divider()

# ====== 코디 생성 ======
prompt_path = os.path.join("prompts", "outfit_prompt.txt")
with open(prompt_path, "r", encoding="utf-8") as f:
    prompt_template = f.read()

weather_summary = summarize_weather(st.session_state.weather) if st.session_state.weather else "아직 날씨를 불러오지 않음"
user_payload = {
    "destination": destination,
    "date_range": f"{start_date} ~ {end_date}",
    "gender": gender,
    "style": style,
    "season": season,
  :contentReference[oaicite:11]{index=11}mmary": weather_summary,
}

gen_col1, gen_col2 = st.columns([1, 1])
with gen_col1:
    if st.button("✨ 코디 3개 생성", type="primary", use_container_width=True):
        with st.spinner("Gemini로 코디 생성 중..."):
            result = generate_outfit_json(prompt_template, user_payload, cfg)
        if not result["ok"]:
            st.error(result["error"])
            st.code(result.get("raw", ""), language="text")
        else:
            st.session_state.last_outfits = result["data"]
            st.success("코디 생성 완료!")

with gen_col2:
    if st.button("🧹 체크리스트 초기화", use_container_width=True):
        st.session_state.packing_list = []
        st.toast("캐리어 체크리스트를 비웠어요.")

# ====== 결과/출력 화면 ======
data = st.session_state.last_outfits
if data:
    st.subheader("📌 추천 코디 (3가지)")
    outfits = data.get("outfits", [])

    for idx, o in enumerate(outfits, start=1):
        with st.container(border=True):
            c1, c2 = st.columns([1.15, 0.85])

            with c1:
                st.markdown(f"### {idx}. {o.get('title','(제목 없음)')}")
                st.write(f"**TPO:** {o.get('tpo','-')}")
                items = o.get("items", {})
                st.markdown("**아이템 리스트**")
                st.write("- 상의:", ", ".join(items.get("top", [])) or "-")
                st.write("- 하의:", ", ".join(items.get("bottom", [])) or "-")
                st.write("- 아우터:", ", ".join(items.get("outer", [])) or "-")
                st.write("- 신발:", ", ".join(items.get("shoes", [])) or "-")
                st.write("- 액세서리:", ", ".join(items.get("accessories", [])) or "-")

                st.markdown("**추천 이유**")
                for r in (o.get("reasons") or []):
                    st.write("•", r)

                add_list = o.get("packing_list_additions") or []
                if st.button(f"🧳 캐리어에 담기 (#{idx})", key=f"pack_{idx}"):
                    # 중복 제거
                    for item in add_list:
                        if item not in st.session_state.packing_list:
                            st.session_state.packing_list.append(item)
                    st.toast("체크리스트에 담았어요!")

                with st.expander("🔗 SNS 공유용 텍스트(복사)", expanded=False):
                    share_text = f"[Tripfit] {destination} 여행 코디 #{idx} - {o.get('title','')}\n" + \
                                 "\n".join([f"- {x}" for x in add_list])
                    st.code(share_text, language="text")

            with c2:
                st.markdown("#### 🖼️ 코디 이미지")
                if gen_images:
                    # 이미지 프롬프트는 “룩 전체를 한 장의 룩북 사진”처럼 생성
                    img_prompt = (
                        f"Create a high-quality fashion lookbook photo of an outfit for a trip to {destination}. "
                        f"Style: {style}. Season: {season}. TPO: {o.get('tpo','')}. "
                        f"Outfit items: top({', '.join(items.get('top', []))}), "
                        f"bottom({', '.join(items.get('bottom', []))}), "
                        f"outer({', '.join(items.get('outer', []))}), "
                        f"shoes({', '.join(items.get('shoes', []))}), "
                        f"accessories({', '.join(items.get('accessories', []))}). "
                        "No text in the image. Clean background, realistic lighting."
                    )
                    with st.spinner("Nano Banana로 이미지 생성 중..."):
                        img_res = generate_outfit_image(img_prompt, cfg)
                    if img_res["ok"]:
                        st.image(img_res["image"], use_container_width=True)
                    else:
                        st.info("이미지를 만들지 못했어요. (API 키/모델/한도 확인)")
                        if img_res.get("texts"):
                            st.caption("모델 메시지: " + " ".join(img_res["texts"]))
                else:
                    st.caption("이미지 생성 옵션이 꺼져 있어요.")

# ====== 캐리어 체크리스트 ======
st.divider()
st.subheader("✅ 가상 캐리어 패킹 체크리스트")
if not st.session_state.packing_list:
    st.info("아직 담긴 아이템이 없어요. 위에서 ‘캐리어에 담기’를 눌러보세요.")
else:
    for i, item in enumerate(st.session_state.packing_list):
        cols = st.columns([0.9, 0.1])
        cols[0].checkbox(item, key=f"chk_{i}")
        if cols[1].button("🗑️", key=f"del_{i}"):
            st.session_state.packing_list.pop(i)
            st.rerun()

# ====== 무드보드 ======
st.divider()
st.subheader("🧷 여행지 무드보드")
st.caption("PRD의 ‘여행지 무드 보드’(도시/계절감 기반 시각 영감)를 간단 버전으로 구현했습니다. "
           "프로덕션에서는 Pinterest/Instagram 등 정식 API 기반으로 대체 권장.")  # :contentReference[oaicite:12]{index=12}

urls = moodboard_image_urls(destination, season, style, n=6)
mcols = st.columns(3)
for i, u in enumerate(urls):
    mcols[i % 3].image(u, use_container_width=True)
