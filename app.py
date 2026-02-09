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
# Style options + per-style variety templates (for MOCK)
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

# 스타일별 "낮(활동)" 2종 + "밤(무드)" 2종 템플릿
STYLE_VARIATIONS = {
    "미니멀": {
        "day": [
            dict(
                title="🖤 미니멀 모노 데이룩",
                items=dict(
                    top=["화이트/블랙 셔츠", "미니멀 니트(레이어드)"],
                    bottom=["테일러드 슬랙스", "스트레이트 데님(선택)"],
                    outer=["싱글 자켓", "라이트 트렌치(선택)"],
                    shoes=["화이트 스니커즈", "로퍼(선택)"],
                    accessories=["가죽 크로스백", "심플 시계"],
                ),
                key_items=["화이트 셔츠", "슬랙스", "가죽 크로스백"],
                why="불필요한 디테일 없이 실루엣과 톤으로 정리해 사진이 깔끔하게 나와요. 이동·관광에도 부담 없는 조합입니다.",
                checklist=["셔츠 여벌", "얇은 니트", "벨트", "보조배터리", "선크림", "미니 파우치"],
                covers=["오전", "오후"],
            ),
            dict(
                title="🧊 미니멀 레이어드 데이룩",
                items=dict(
                    top=["유니 톤 티셔츠", "가디건/집업(레이어)"],
                    bottom=["와이드 슬랙스", "미디 스커트(선택)"],
                    outer=["바람막이/라이트 코트"],
                    shoes=["슬립온", "스니커즈"],
                    accessories=["미니 토트", "선글라스"],
                ),
                key_items=["레이어드 가디건", "와이드 슬랙스", "선글라스"],
                why="기온 변화에 레이어드로 대응하고, 톤온톤으로 안정감 있게 연출해요.",
                checklist=["가디건", "얇은 머플러(선택)", "양말", "립밤", "물티슈"],
                covers=["오전", "오후"],
            ),
        ],
        "night": [
            dict(
                title="🌙 미니멀 디너룩",
                items=dict(
                    top=["블랙 터틀넥/니트", "셔츠(선택)"],
                    bottom=["울 슬랙스", "롱 스커트(선택)"],
                    outer=["코트/블레이저"],
                    shoes=["로퍼", "미니멀 앵클부츠(선택)"],
                    accessories=["미니백", "실버 액세서리"],
                ),
                key_items=["블랙 니트", "로퍼", "미니백"],
                why="저녁 조명에서 톤이 정리되면 훨씬 세련돼 보여요. 과한 포인트 없이 소재로 분위기만 살립니다.",
                checklist=["향/미스트", "작은 액세서리", "핸드크림"],
                covers=["저녁"],
            ),
            dict(
                title="✨ 미니멀 포멀 무드룩",
                items=dict(
                    top=["실키 블라우스/셔츠"],
                    bottom=["슬랙스", "플레어 스커트(선택)"],
                    outer=["블레이저"],
                    shoes=["로퍼", "스트랩 슈즈(선택)"],
                    accessories=["클러치/미니백", "진주/실버"],
                ),
                key_items=["블레이저", "실키 셔츠", "클러치"],
                why="식사·바/공연 같은 일정에 ‘정돈된 느낌’을 주기 좋고 사진에서도 균형이 잡혀요.",
                checklist=["블레이저", "여분 스타킹/양말", "헤어핀"],
                covers=["저녁"],
            ),
        ],
    },

    "빈티지": {
        "day": [
            dict(
                title="🍂 빈티지 레트로 투어룩",
                items=dict(
                    top=["체크 셔츠", "니트 베스트(레이어)"],
                    bottom=["하이웨스트 데님", "코듀로이 팬츠(선택)"],
                    outer=["트위드 자켓", "가죽 자켓(선택)"],
                    shoes=["메리제인/로퍼", "캔버스화(선택)"],
                    accessories=["숄더백", "스카프"],
                ),
                key_items=["체크 셔츠", "니트 베스트", "스카프"],
                why="빈티지의 ‘레이어드’가 여행 사진을 풍성하게 만들어줘요. 색감을 톤다운하면 촌스럽지 않아요.",
                checklist=["스카프", "얇은 이너", "양말", "선글라스"],
                covers=["오전", "오후"],
            ),
            dict(
                title="📼 빈티지 데님 무드룩",
                items=dict(
                    top=["그래픽 티/프린트 티", "가디건"],
                    bottom=["빈티지 워싱 데님"],
                    outer=["청자켓/헌팅 자켓"],
                    shoes=["스니커즈", "로퍼(선택)"],
                    accessories=["토트백", "볼캡"],
                ),
                key_items=["워싱 데님", "헌팅 자켓", "토트백"],
                why="편한데도 ‘무드’가 살아서 카페·거리 스냅에 강해요.",
                checklist=["볼캡", "에코백", "선크림", "보조배터리"],
                covers=["오전", "오후"],
            ),
        ],
        "night": [
            dict(
                title="🌙 빈티지 시네마 룩",
                items=dict(
                    top=["블라우스/셔츠(러플/카라)"],
                    bottom=["미디 스커트", "슬랙스(선택)"],
                    outer=["트렌치/코트"],
                    shoes=["로퍼", "메리제인"],
                    accessories=["미니백", "헤어밴드"],
                ),
                key_items=["카라 블라우스", "미디 스커트", "헤어밴드"],
                why="저녁에는 디테일이 사진에 잘 담겨요. ‘카라/스커트’ 조합이 빈티지 감성을 확실히 줍니다.",
                checklist=["헤어밴드", "립밤", "향/미스트"],
                covers=["저녁"],
            ),
            dict(
                title="✨ 빈티지 클래식 나잇룩",
                items=dict(
                    top=["니트/가디건(단정)"],
                    bottom=["플리츠 스커트", "슬랙스(선택)"],
                    outer=["울 코트"],
                    shoes=["로퍼"],
                    accessories=["클래식 숄더백", "심플 귀걸이"],
                ),
                key_items=["플리츠 스커트", "울 코트", "숄더백"],
                why="차분한 톤으로 마감하면 ‘옛 영화 느낌’이 나서 야경/레스토랑에 잘 어울려요.",
                checklist=["코트", "핸드크림", "작은 액세서리"],
                covers=["저녁"],
            ),
        ],
    },

    "스트릿": {
        "day": [
            dict(
                title="🔥 스트릿 오버핏 데이룩",
                items=dict(
                    top=["오버핏 티/후드", "그래픽 포인트"],
                    bottom=["카고 팬츠", "와이드 데님(선택)"],
                    outer=["바시티/항공점퍼"],
                    shoes=["청키 스니커즈"],
                    accessories=["볼캡", "크로스백"],
                ),
                key_items=["후드", "카고 팬츠", "청키 스니커즈"],
                why="도보/쇼핑 많은 날에 편하고, 사진에 실루엣이 크게 잡혀 스트릿 무드가 확 살아나요.",
                checklist=["볼캡", "보조배터리", "이어폰", "물티슈"],
                covers=["오전", "오후"],
            ),
            dict(
                title="🧢 스트릿 레이어 믹스룩",
                items=dict(
                    top=["롱슬리브", "반팔 레이어(선택)"],
                    bottom=["조거/와이드 팬츠"],
                    outer=["바람막이", "체크 셔츠(아우터 대용)"],
                    shoes=["스니커즈"],
                    accessories=["백팩", "선글라스"],
                ),
                key_items=["바람막이", "조거 팬츠", "백팩"],
                why="여행에서 기온이 애매할 때 레이어가 최고예요. 스트릿은 ‘레이어+실용’이 정답.",
                checklist=["바람막이", "선글라스", "양말", "물"],
                covers=["오전", "오후"],
            ),
        ],
        "night": [
            dict(
                title="🌙 스트릿 나잇 아웃룩",
                items=dict(
                    top=["블랙 티/니트", "레더 포인트(선택)"],
                    bottom=["블랙 데님", "카고(선택)"],
                    outer=["레더 자켓", "블루종(선택)"],
                    shoes=["하이탑/청키 스니커즈"],
                    accessories=["체인 액세서리", "미니 크로스백"],
                ),
                key_items=["레더 자켓", "블랙 데님", "체인 액세서리"],
                why="야경에서는 대비가 살아서 블랙 베이스가 사진발 잘 받아요. 포인트는 하나만!",
                checklist=["향/미스트", "립밤", "작은 액세서리"],
                covers=["저녁"],
            ),
            dict(
                title="✨ 스트릿 포인트 컬러룩",
                items=dict(
                    top=["블랙 베이스", "컬러 포인트 상의/비니"],
                    bottom=["와이드 팬츠"],
                    outer=["점퍼"],
                    shoes=["스니커즈"],
                    accessories=["비니/캡", "크로스백"],
                ),
                key_items=["포인트 컬러", "와이드 팬츠", "비니"],
                why="저녁 사진은 포인트 컬러가 더 선명해요. 상의/모자 한 군데만 컬러로 ‘찍어’줍니다.",
                checklist=["비니", "핸드폰 스트랩", "보조배터리"],
                covers=["저녁"],
            ),
        ],
    },

    "캐주얼": {
        "day": [
            dict(
                title="☀️ 캐주얼 데이 투어룩",
                items=dict(
                    top=["맨투맨/티셔츠", "셔츠(레이어)"],
                    bottom=["데님/면팬츠"],
                    outer=["가디건/가벼운 자켓"],
                    shoes=["스니커즈"],
                    accessories=["에코백", "볼캡"],
                ),
                key_items=["맨투맨", "스니커즈", "에코백"],
                why="어디든 무난하고 편해서 일정이 많은 날에 안전한 선택이에요.",
                checklist=["양말", "보조배터리", "선크림", "물티슈"],
                covers=["오전", "오후"],
            ),
            dict(
                title="🌿 캐주얼 레이어드 룩",
                items=dict(
                    top=["티셔츠", "니트 베스트/가디건"],
                    bottom=["와이드 데님"],
                    outer=["바람막이(선택)"],
                    shoes=["러닝 스니커즈"],
                    accessories=["백팩"],
                ),
                key_items=["가디건", "와이드 데님", "백팩"],
                why="기온 변화 대응이 쉽고, 활동성이 좋아서 ‘여행 전용’으로 잘 맞아요.",
                checklist=["가디건", "이어폰", "상비약"],
                covers=["오전", "오후"],
            ),
        ],
        "night": [
            dict(
                title="🌙 캐주얼 디너룩",
                items=dict(
                    top=["니트/셔츠(단정)"],
                    bottom=["슬랙스/미디 스커트"],
                    outer=["블레이저(선택)"],
                    shoes=["로퍼/단정 스니커즈"],
                    accessories=["미니백"],
                ),
                key_items=["단정 니트", "슬랙스", "미니백"],
                why="너무 꾸민 느낌 없이도 저녁 장소에서 깔끔하게 보이는 조합입니다.",
                checklist=["향/미스트", "립밤"],
                covers=["저녁"],
            ),
            dict(
                title="✨ 캐주얼 원마일 무드룩",
                items=dict(
                    top=["집업/가디건"],
                    bottom=["조거 팬츠(깔끔 핏)"],
                    outer=["코트(선택)"],
                    shoes=["슬립온"],
                    accessories=["토트백"],
                ),
                key_items=["집업", "슬립온", "토트백"],
                why="숙소 근처/야식/가벼운 산책에 편하고 사진도 ‘꾸안꾸’로 잘 나와요.",
                checklist=["핸드크림", "얇은 아우터"],
                covers=["저녁"],
            ),
        ],
    },

    "클래식": {
        "day": [
            dict(
                title="🧥 클래식 시티 워크룩",
                items=dict(
                    top=["셔츠/니트(단정)"],
                    bottom=["슬랙스", "미디 스커트(선택)"],
                    outer=["트렌치/블레이저"],
                    shoes=["로퍼"],
                    accessories=["가죽 토트", "심플 시계"],
                ),
                key_items=["트렌치", "로퍼", "가죽 토트"],
                why="도시 여행에 찰떡인 정돈된 룩이에요. 사진이 ‘격식 있게’ 정리됩니다.",
                checklist=["벨트", "양말", "헤어 브러시"],
                covers=["오전", "오후"],
            ),
            dict(
                title="🏛️ 클래식 뮤지엄 룩",
                items=dict(
                    top=["니트", "셔츠(레이어)"],
                    bottom=["슬랙스"],
                    outer=["코트(선택)/블레이저"],
                    shoes=["로퍼"],
                    accessories=["스카프(선택)", "미니백"],
                ),
                key_items=["니트", "슬랙스", "스카프"],
                why="실내(박물관/전시)에서 조명이 안정적이라 클래식 룩이 더 돋보여요.",
                checklist=["스카프", "미니 파우치", "립밤"],
                covers=["오전", "오후"],
            ),
        ],
        "night": [
            dict(
                title="🌙 클래식 디너 룩",
                items=dict(
                    top=["실키 블라우스/셔츠"],
                    bottom=["슬랙스/롱 스커트"],
                    outer=["코트"],
                    shoes=["스트랩 슈즈/로퍼"],
                    accessories=["클러치/미니백"],
                ),
                key_items=["블라우스", "클러치", "코트"],
                why="저녁엔 소재가 빛을 받아 고급스럽게 보여요. 사진도 분위기 있게 나옵니다.",
                checklist=["향/미스트", "작은 액세서리"],
                covers=["저녁"],
            ),
            dict(
                title="✨ 클래식 블랙 타이프 룩",
                items=dict(
                    top=["블랙 탑/니트"],
                    bottom=["슬랙스/롱 스커트"],
                    outer=["블레이저"],
                    shoes=["로퍼/힐(선택)"],
                    accessories=["실버 포인트"],
                ),
                key_items=["블레이저", "블랙 탑", "실버 포인트"],
                why="톤을 제한하면 누구나 실패 없이 ‘단정+세련’으로 갑니다.",
                checklist=["블레이저", "핸드크림"],
                covers=["저녁"],
            ),
        ],
    },

    "러블리": {
        "day": [
            dict(
                title="🎀 러블리 데이트 무드룩",
                items=dict(
                    top=["파스텔 니트/블라우스"],
                    bottom=["미디 스커트", "연청 데님(선택)"],
                    outer=["가디건"],
                    shoes=["메리제인/스니커즈(선택)"],
                    accessories=["미니백", "헤어핀"],
                ),
                key_items=["파스텔 니트", "미니백", "헤어핀"],
                why="색감과 디테일이 사진에 잘 담겨요. 러블리는 ‘톤+작은 포인트’가 핵심!",
                checklist=["헤어핀", "립밤", "손거울(선택)"],
                covers=["오전", "오후"],
            ),
            dict(
                title="🌸 러블리 캐주얼 스냅룩",
                items=dict(
                    top=["크롭 가디건/티"],
                    bottom=["플리츠 스커트", "숏팬츠(시즌)"],
                    outer=["라이트 자켓(선택)"],
                    shoes=["스니커즈"],
                    accessories=["에코백", "리본"],
                ),
                key_items=["가디건", "플리츠 스커트", "리본 포인트"],
                why="움직임이 있는 스커트가 여행 사진에 잘 어울려요. 캐주얼하게 귀여움만 살립니다.",
                checklist=["에코백", "선크림", "보조배터리"],
                covers=["오전", "오후"],
            ),
        ],
        "night": [
            dict(
                title="🌙 러블리 나잇 룩",
                items=dict(
                    top=["블라우스(디테일)"],
                    bottom=["롱 스커트"],
                    outer=["코트/가디건"],
                    shoes=["메리제인/로퍼"],
                    accessories=["미니백", "작은 귀걸이"],
                ),
                key_items=["블라우스", "롱 스커트", "귀걸이"],
                why="저녁 조명에서 디테일이 더 예쁘게 보여요. 실루엣은 길게, 포인트는 작게!",
                checklist=["향/미스트", "귀걸이", "핸드크림"],
                covers=["저녁"],
            ),
            dict(
                title="✨ 러블리 글로우 룩",
                items=dict(
                    top=["아이보리 니트"],
                    bottom=["슬랙스/스커트"],
                    outer=["트렌치(선택)"],
                    shoes=["로퍼"],
                    accessories=["펄 포인트"],
                ),
                key_items=["아이보리 니트", "펄 포인트", "로퍼"],
                why="아이보리 톤은 야경에서 얼굴이 환해 보이고 사진이 부드럽게 나와요.",
                checklist=["립밤", "작은 파우치"],
                covers=["저녁"],
            ),
        ],
    },

    "고프코어": {
        "day": [
            dict(
                title="🧗 고프코어 하이브리드 룩",
                items=dict(
                    top=["기능성 티/긴팔", "플리스(선택)"],
                    bottom=["나일론 팬츠", "카고 팬츠(선택)"],
                    outer=["바람막이/쉘 자켓"],
                    shoes=["트레일 스니커즈"],
                    accessories=["백팩", "캡"],
                ),
                key_items=["쉘 자켓", "트레일 스니커즈", "백팩"],
                why="날씨 변동·이동이 많은 여행에 최고예요. 기능성 소재라 실용성도 강합니다.",
                checklist=["우산/우비(선택)", "보조배터리", "물병", "상비약"],
                covers=["오전", "오후"],
            ),
            dict(
                title="🌿 고프코어 시티 아웃도어룩",
                items=dict(
                    top=["맨투맨/긴팔"],
                    bottom=["조거/나일론 팬츠"],
                    outer=["패딩 베스트(시즌)/바람막이"],
                    shoes=["러닝/트레일 슈즈"],
                    accessories=["웨이스트백", "선글라스"],
                ),
                key_items=["바람막이", "웨이스트백", "러닝 슈즈"],
                why="도시에서도 아웃도어 감성은 살리되 과하지 않게 ‘시티형’으로 맞춘 버전이에요.",
                checklist=["선글라스", "물티슈", "휴대용 손세정제"],
                covers=["오전", "오후"],
            ),
        ],
        "night": [
            dict(
                title="🌙 고프코어 나잇 라이트룩",
                items=dict(
                    top=["기능성 니트/후디"],
                    bottom=["카고/조거"],
                    outer=["가벼운 다운/쉘(선택)"],
                    shoes=["스니커즈"],
                    accessories=["크로스백"],
                ),
                key_items=["후디", "크로스백", "카고"],
                why="저녁엔 체온 유지가 중요해서 보온/방풍을 챙겼어요. 편하게 야경 보러 가기 좋아요.",
                checklist=["얇은 아우터", "핫팩(시즌)"],
                covers=["저녁"],
            ),
            dict(
                title="✨ 고프코어 톤온톤 룩",
                items=dict(
                    top=["다크 톤 상의"],
                    bottom=["다크 톤 팬츠"],
                    outer=["쉘 자켓"],
                    shoes=["스니커즈"],
                    accessories=["캡/비니(선택)"],
                ),
                key_items=["쉘 자켓", "다크 톤", "비니"],
                why="톤온톤으로 정리하면 기능성 아이템도 ‘패션’으로 보이기 쉬워요.",
                checklist=["비니", "이어폰"],
                covers=["저녁"],
            ),
        ],
    },

    "시티보이/시티걸": {
        "day": [
            dict(
                title="🏙️ 시티보이/걸 데이룩",
                items=dict(
                    top=["셔츠", "니트(레이어)"],
                    bottom=["와이드 슬랙스/데님"],
                    outer=["코트/자켓(선택)"],
                    shoes=["로퍼/스니커즈"],
                    accessories=["토트백", "안경(선택)"],
                ),
                key_items=["셔츠", "토트백", "와이드 슬랙스"],
                why="도시 배경에서 ‘정돈된 캐주얼’이 제일 예뻐요. 실루엣은 여유 있게, 컬러는 차분하게!",
                checklist=["셔츠 여벌", "립밤", "보조배터리"],
                covers=["오전", "오후"],
            ),
            dict(
                title="☕ 시티 카페 스냅룩",
                items=dict(
                    top=["후디/맨투맨(깔끔)", "셔츠 레이어(선택)"],
                    bottom=["슬랙스", "데님(선택)"],
                    outer=["블레이저(선택)"],
                    shoes=["스니커즈"],
                    accessories=["크로스백", "선글라스"],
                ),
                key_items=["깔끔 후디", "슬랙스", "선글라스"],
                why="카페·서점 같은 실내에서 ‘꾸안꾸’ 사진이 잘 나오는 조합이에요.",
                checklist=["선글라스", "에코백"],
                covers=["오전", "오후"],
            ),
        ],
        "night": [
            dict(
                title="🌙 시티 나잇 무드룩",
                items=dict(
                    top=["니트/셔츠(단정)"],
                    bottom=["슬랙스/롱 스커트"],
                    outer=["코트"],
                    shoes=["로퍼"],
                    accessories=["미니백", "심플 액세서리"],
                ),
                key_items=["코트", "로퍼", "미니백"],
                why="야경/바/디너에 잘 어울리는 도시적인 무드예요. 소재를 단정하게 맞추면 사진이 고급스럽게 나옵니다.",
                checklist=["향/미스트", "핸드크림"],
                covers=["저녁"],
            ),
            dict(
                title="✨ 시티 모노 포인트룩",
                items=dict(
                    top=["모노 톤 상의"],
                    bottom=["모노 톤 하의"],
                    outer=["자켓"],
                    shoes=["로퍼/단정 스니커즈"],
                    accessories=["메탈 포인트"],
                ),
                key_items=["모노 톤", "자켓", "메탈 포인트"],
                why="도시 조명에서는 대비가 중요해서 모노 톤+작은 포인트가 실패 확률이 낮아요.",
                checklist=["작은 액세서리", "립밤"],
                covers=["저녁"],
            ),
        ],
    },
}


def pick_variations(style: str):
    """Returns (day_variations, night_variations) lists. Falls back to 캐주얼 if missing."""
    base = STYLE_VARIATIONS.get(style) or STYLE_VARIATIONS["캐주얼"]
    return base["day"], base["night"]


# =============================
# Theme CSS
# =============================
def inject_css(theme: dict):
    st.markdown(
        f"""
<style>
:root {{
  --g1: {theme["g1"]};
  --g2: {theme["g2"]};
  --accent: {theme["accent"]};
  --cardbg: {theme["card"]};
}}

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
# Calendar itinerary (per-day style)
# =============================
SLOTS = ["오전", "오후", "저녁"]

def build_calendar_rows(start_date: date, days: int, plans: list[dict], day_styles: dict) -> list[dict]:
    rows = []
    for i in range(days):
        d = start_date + relativedelta(days=i)
        dkey = d.isoformat()
        style = day_styles.get(dkey, "러블리")
        for slot in SLOTS:
            plan_text = ""
            for p in plans:
                if p["date"] == dkey and p["slot"] == slot:
                    plan_text = (p["plan"] or "").strip()
                    break
            rows.append({"날짜": dkey, "시간대": slot, "일정": plan_text if plan_text else "—", "스타일": style})
    return rows


# =============================
# AI Prompt / MOCK / Fallback
# =============================
def build_prompt(user: dict, weather: WeatherInfo, start_date: date, days: int, calendar_rows: list[dict], day_styles: dict) -> str:
    calendar_json = json.dumps(calendar_rows, ensure_ascii=False)
    styles_json = json.dumps(day_styles, ensure_ascii=False)

    return f"""
너는 여행 전문 패션 코디네이터다.
여행지 날씨와 사용자의 스타일 취향, 그리고 '캘린더 형식 일정'에 맞춰
실용적이면서 사진에 잘 어울리는 코디를 추천해야 한다.

[사용자]
- 성별: {user["gender"]}
- 나이대: {user["age_group"]}
- 계절: {user["season"]}

[여행]
- 목적지: {weather.city}, {weather.country}
- 시작일: {start_date.isoformat()} ({dday_string(start_date)})
- 기간: {days}일
- 날씨 요약(시작일 기준): {weather.summary}

[날짜별 스타일(JSON)]
{styles_json}

[일정 캘린더(JSON)]
{calendar_json}

[출력 규칙: 반드시 JSON만]
- 날짜별로 코디를 묶어서 제공
- 각 날짜는 그날 스타일을 반드시 반영 (styles_json 기준)
- 각 날짜마다 day_outfits는 '최소 2개'(활동/저녁처럼 서로 다른 무드)
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
      "day_style": "그날 스타일",
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

def _plan_summary(rows_for_date: list[dict]) -> str:
    plans = [f'{x["시간대"]}:{x["일정"]}' for x in rows_for_date if x["일정"] != "—"]
    summary = " / ".join(plans) if plans else "가벼운 자유 일정"
    return summary[:80] + ("…" if len(summary) > 80 else "")

def mock_generate_calendar(user: dict, weather: WeatherInfo, start_date: date, days: int, calendar_rows: list[dict], day_styles: dict) -> dict:
    dest = f"{weather.city}, {weather.country}".strip().strip(",")
    dest_card = {"destination": dest, "dday": dday_string(start_date), "weather_one_liner": weather.summary}

    by_date = {}
    for r in calendar_rows:
        by_date.setdefault(r["날짜"], []).append(r)

    calendar_outfits = []
    for d, rows in by_date.items():
        style = day_styles.get(d, "러블리")
        day_vars, night_vars = pick_variations(style)

        # 일정에 '저녁' 텍스트가 조금이라도 있으면 night 룩 우선, 아니면 day 룩 2개
        has_evening_plan = any((x["시간대"] == "저녁" and x["일정"] != "—") for x in rows)

        chosen = []
        # 활동용 2개 중 1개 + 저녁용 2개 중 1개 (항상 2개 제공)
        chosen.append(day_vars[0])
        chosen.append(night_vars[0] if has_evening_plan else day_vars[1])

        day_outfits = []
        for v in chosen:
            day_outfits.append({
                "title": v["title"],
                "covers_slots": v["covers"],
                "items": v["items"],
                "key_items": v["key_items"],
                "why_recommended": f"{weather.summary} 기준으로 구성했어요. " + v["why"],
                "packing_checklist": v["checklist"],
            })

        calendar_outfits.append({
            "date": d,
            "day_style": style,
            "day_summary": _plan_summary(rows),
            "day_outfits": day_outfits,
        })

    return {"destination_card": dest_card, "calendar_outfits": calendar_outfits}

def generate_with_ai_or_fallback(openai_key: str, user: dict, weather: WeatherInfo, start_date: date, days: int,
                                calendar_rows: list[dict], day_styles: dict) -> tuple[dict, bool]:
    if not openai_key:
        return mock_generate_calendar(user, weather, start_date, days, calendar_rows, day_styles), True

    try:
        client = OpenAI(api_key=openai_key)
        prompt = build_prompt(user, weather, start_date, days, calendar_rows, day_styles)
        resp = client.responses.create(model="gpt-4o-mini", input=prompt, temperature=0.7)
        text = (resp.output_text or "").strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            s = text.find("{")
            e = text.rfind("}")
            if s != -1 and e != -1 and e > s:
                data = json.loads(text[s:e+1])
            else:
                raise

        # ✅ 보강: AI가 1개만 주면(혹시) 최소 2개로 채우기
        for day in data.get("calendar_outfits", []):
            outfits = day.get("day_outfits") or []
            if len(outfits) < 2:
                d = day.get("date")
                style = day.get("day_style") or day_styles.get(d, "러블리")
                day_vars, night_vars = pick_variations(style)
                # 부족분 채우기
                while len(outfits) < 2:
                    outfits.append({
                        "title": night_vars[1]["title"],
                        "covers_slots": night_vars[1]["covers"],
                        "items": night_vars[1]["items"],
                        "key_items": night_vars[1]["key_items"],
                        "why_recommended": f"{weather.summary} 기준으로 구성했어요. " + night_vars[1]["why"],
                        "packing_checklist": night_vars[1]["checklist"],
                    })
                day["day_outfits"] = outfits

        return data, False

    except Exception:
        return mock_generate_calendar(user, weather, start_date, days, calendar_rows, day_styles), True


# =============================
# Links (Google/Pinterest + Shopping links)
# =============================
def inspiration_links(destination: str, style_pref: str):
    st.subheader("🔎 참고 링크")
    q = f"{destination} {style_pref} ootd"
    st.link_button("🖼️ Google 이미지", f"https://www.google.com/search?tbm=isch&q={requests.utils.quote(q)}")
    st.link_button("📌 Pinterest", f"https://www.pinterest.com/search/pins/?q={requests.utils.quote(q)}")

def shopping_links_row(item_keyword: str):
    c1, c2 = st.columns(2)
    with c1:
        st.link_button("🛍️ 무신사", f"https://www.musinsa.com/search/musinsa/integration?q={requests.utils.quote(item_keyword)}")
    with c2:
        st.link_button("🛒 에이블리", f"https://m.a-bly.com/search?query={requests.utils.quote(item_keyword)}")


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

    st.write("🛒 비슷한 상품 찾기")
    for kw in outfit.get("key_items", [])[:3]:
        st.markdown(f"**{kw}**")
        shopping_links_row(kw)


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

# UI 톤: 자동(첫날 스타일) or 고정
ui_theme_mode = st.selectbox("🎨 UI 톤", ["자동(첫날 스타일)", "고정 선택"])
if ui_theme_mode == "고정 선택":
    ui_theme_style = st.selectbox("✨ UI 톤 스타일", STYLE_OPTIONS, index=STYLE_OPTIONS.index("러블리"))
else:
    ui_theme_style = None

user = {
    "gender": gender,
    "age_group": age_group,
    "season": season_from_month(start_date.month),
}

st.subheader("🗓️ 일정 (날짜별 스타일 + 코디 다양화)")
plans = []
day_styles = {}

day_tabs = st.tabs([(start_date + relativedelta(days=i)).strftime("📅 %m/%d") for i in range(days)])

for i, tab in enumerate(day_tabs):
    d = start_date + relativedelta(days=i)
    dkey = d.isoformat()

    with tab:
        # 날짜별 스타일 선택
        day_style = st.selectbox(
            "👗 오늘의 스타일",
            STYLE_OPTIONS,
            key=f"day_style_{dkey}",
            index=STYLE_OPTIONS.index("러블리"),
        )
        day_styles[dkey] = day_style

        cols = st.columns(3)
        for j, slot in enumerate(["오전", "오후", "저녁"]):
            with cols[j]:
                txt = st.text_area(
                    f"🧩 {slot}",
                    key=f"plan_{dkey}_{slot}",
                    height=90,
                    placeholder="예: 박물관 / 카페 / 쇼핑"
                )
                plans.append({"date": dkey, "slot": slot, "plan": txt})

# 테마 적용(대표 스타일)
first_day_key = start_date.isoformat()
auto_theme_style = day_styles.get(first_day_key, "러블리")
applied_theme_style = ui_theme_style if (ui_theme_mode == "고정 선택" and ui_theme_style) else auto_theme_style
inject_css(STYLE_THEME.get(applied_theme_style, STYLE_THEME["러블리"]))

calendar_rows = build_calendar_rows(start_date, days, plans, day_styles)

st.divider()
btn = st.button("🪄 코디 만들기", use_container_width=True)

if btn:
    if not destination_input.strip():
        st.error("📍 목적지를 입력해줘!")
        st.stop()

    with st.spinner("✨ 코디 준비 중..."):
        # 1) geocode
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

        # 2) weather
        try:
            wx = fetch_weather_one_liner(lat, lon, start_date)
        except Exception:
            wx = "날씨 정보 없음"

        weather = WeatherInfo(city=city, country=country, lat=lat, lon=lon, summary=wx)

        # 3) AI / fallback
        if use_ai:
            result, used_fallback = generate_with_ai_or_fallback(openai_key, user, weather, start_date, days, calendar_rows, day_styles)
        else:
            result, used_fallback = mock_generate_calendar(user, weather, start_date, days, calendar_rows, day_styles), True

    # Render
    dest_card = result.get("destination_card", {})
    dest_card.setdefault("destination", f"{city}, {country}".strip().strip(","))
    dest_card.setdefault("dday", dday_string(start_date))
    dest_card.setdefault("weather_one_liner", wx)
    render_destination_card(dest_card)

    if used_fallback:
        st.info("🙂 샘플 코디로 보여줄게요!")

    st.subheader("🗂️ 일정표")
    st.dataframe(calendar_rows, use_container_width=True, hide_index=True)

    st.subheader("👗 날짜별 코디 (각 날짜 최소 2개)")
    cal = result.get("calendar_outfits", [])
    if not cal:
        st.info("다시 시도해줘!")
        st.stop()

    tabs = st.tabs([f"📅 {x['date']}" for x in cal])
    for t, day in zip(tabs, cal):
        with t:
            day_style = day.get("day_style") or day_styles.get(day["date"], "러블리")
            st.caption(f"👗 오늘 스타일: {day_style}")
            if day.get("day_summary"):
                st.caption(day["day_summary"])

            outfits = day.get("day_outfits", []) or []
            # 혹시 빈 경우 안전장치
            if len(outfits) == 0:
                st.info("코디가 비어 있어요. 다시 시도해줘!")
                continue

            for k, outfit in enumerate(outfits):
                st.divider()
                render_outfit(outfit, key_prefix=f"{day['date']}_{k}")

            st.divider()
            inspiration_links(dest_card.get("destination", destination_input), day_style)

