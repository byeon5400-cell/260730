import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="박스오피스 대시보드",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 날짜별 박스오피스 대시보드")

# 비밀 금고에서 인증키 가져오기
KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 한국 시간 기준 오늘과 어제 날짜
today = datetime.now(ZoneInfo("Asia/Seoul")).date()
yesterday = today - timedelta(days=1)

# -------------------------------------------------
# 1. 날짜 선택 메뉴
# -------------------------------------------------
st.sidebar.header("🔍 조회 조건")

selected_date = st.sidebar.date_input(
    "박스오피스 날짜를 선택하세요.",
    value=yesterday,
    max_value=yesterday,
    help="당일 자료는 아직 집계되지 않으므로 어제 날짜까지만 선택할 수 있습니다."
)

target_dt = selected_date.strftime("%Y%m%d")

st.caption(
    f"조회 기준일: {selected_date.strftime('%Y년 %m월 %d일')}"
)

# -------------------------------------------------
# KOBIS API 요청
# -------------------------------------------------
url = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

try:
    res = requests.get(
        url,
        params={
            "key": KOBIS_KEY,
            "targetDt": target_dt
        },
        timeout=10
    )

    res.raise_for_status()

except requests.exceptions.Timeout:
    st.error("요청 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.")
    st.stop()

except requests.exceptions.RequestException as error:
    st.error(f"박스오피스 자료를 불러오지 못했습니다: {error}")
    st.stop()

data = res.json()

# KOBIS는 인증키가 잘못되어도 상태코드 200을 반환할 수 있음
if "faultInfo" in data:
    fault_message = data["faultInfo"].get(
        "message",
        "인증키가 올바르지 않습니다."
    )

    st.error(
        f"{fault_message} Secrets의 KOBIS_KEY를 확인해 주세요."
    )
    st.stop()

box_list = (
    data.get("boxOfficeResult", {})
    .get("dailyBoxOfficeList", [])
)

if not box_list:
    st.warning("선택한 날짜의 박스오피스 자료가 없습니다.")
    st.stop()

df = pd.DataFrame(box_list)

# -------------------------------------------------
# 숫자 자료 변환
# -------------------------------------------------
number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for col in number_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).fillna(0).astype(int)

df = df.sort_values("rank").reset_index(drop=True)

# -------------------------------------------------
# 2. TOP 1, 2, 3 영화 표시
# -------------------------------------------------
st.subheader("🏆 박스오피스 TOP 3")

top3 = df.head(3)

rank_icons = {
    1: "🥇",
    2: "🥈",
    3: "🥉"
}

top_columns = st.columns(3)

for index, (_, movie) in enumerate(top3.iterrows()):
    rank = int(movie["rank"])
    rank_change = int(movie.get("rankInten", 0))

    if rank_change > 0:
        rank_text = f"▲ {rank_change}"
    elif rank_change < 0:
        rank_text = f"▼ {abs(rank_change)}"
    else:
        rank_text = "-"

    with top_columns[index]:
        st.markdown(
            f"""
            ### {rank_icons.get(rank, '🎬')} {rank}위
            **{movie['movieNm']}**
            """
        )

        st.metric(
            label="당일 관객수",
            value=f"{movie['audiCnt']:,}명",
            delta=f"순위 변동 {rank_text}",
            delta_color="off"
        )

        st.caption(
            f"누적 관객 {movie['audiAcc']:,}명 · "
            f"스크린 {movie['scrnCnt']:,}개"
        )

st.divider()

# -------------------------------------------------
# 전체 순위표
# -------------------------------------------------
table = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
        "showCnt"
    ]
].copy()

table.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
    "상영횟수"
]

table = table.sort_values("순위").reset_index(drop=True)

# 숫자 열 천 단위 구분
table_style = {
    "순위": "{:d}",
    "관객수": "{:,}",
    "누적관객": "{:,}",
    "스크린수": "{:,}",
    "상영횟수": "{:,}"
}

st.subheader("📋 박스오피스 TOP 10")

st.dataframe(
    table.style.format(table_style),
    width="stretch",
    hide_index=True
)

# -------------------------------------------------
# 관객수 상위 5편 차트
# -------------------------------------------------
st.subheader("📈 관객수 상위 5편")

top5 = (
    table.sort_values("관객수", ascending=False)
    .head(5)
    .set_index("영화명")
)

st.bar_chart(
    top5["관객수"],
    horizontal=True
)
