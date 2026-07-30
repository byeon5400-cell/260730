import io

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="전국 고령화 지도",
    page_icon="🗺️",
    layout="wide",
)

POPULATION_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/"
    "main/data/population_yearly.csv.gz"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/"
    "main/data/boundaries/sigungu_kr.geojson"
)


# ---------------------------------------------------------
# 2. 인구 데이터 불러오기
# ---------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_population_data():
    """
    전국 읍·면·동 인구 데이터를 내려받아
    가장 최신 연도의 시군구별 고령화율을 계산합니다.
    """

    response = requests.get(POPULATION_URL, timeout=120)
    response.raise_for_status()

    population_bytes = response.content

    # 먼저 열 이름만 읽어서 필요한 열을 확인합니다.
    header = pd.read_csv(
        io.BytesIO(population_bytes),
        compression="gzip",
        nrows=0,
    )

    columns = header.columns.tolist()

    # '계_'로 시작하는 열은 남녀를 합친 연령별 인구입니다.
    total_age_columns = [
        column for column in columns
        if str(column).startswith("계_")
    ]

    # 65세 이상 인구 열을 찾습니다.
    elderly_columns = []

    for column in total_age_columns:
        age_text = str(column).replace("계_", "").replace("세", "").strip()

        # '100세 이상'과 같은 열을 처리합니다.
        if "이상" in age_text:
            age_number_text = age_text.replace("이상", "").strip()
        else:
            age_number_text = age_text

        try:
            age = int(age_number_text)
        except ValueError:
            continue

        if age >= 65:
            elderly_columns.append(column)

    required_columns = [
        "연도",
        "시도",
        "시군구",
        "코드",
        *total_age_columns,
    ]

    # 혹시 데이터에 없는 열이 있다면 제외합니다.
    required_columns = [
        column for column in required_columns
        if column in columns
    ]

    # 첫 번째로 연도 열만 읽어서 가장 최신 연도를 찾습니다.
    year_data = pd.read_csv(
        io.BytesIO(population_bytes),
        compression="gzip",
        usecols=["연도"],
    )

    year_data["연도"] = pd.to_numeric(
        year_data["연도"],
        errors="coerce",
    )

    latest_year = int(year_data["연도"].max())

    # 최신 연도 데이터만 모읍니다.
    latest_chunks = []

    # chunk 단위로 읽으면 메모리 사용량을 줄일 수 있습니다.
    for chunk in pd.read_csv(
        io.BytesIO(population_bytes),
        compression="gzip",
        usecols=required_columns,
        dtype={"코드": "string"},
        chunksize=10_000,
        low_memory=False,
    ):
        chunk["연도"] = pd.to_numeric(
            chunk["연도"],
            errors="coerce",
        )

        latest_chunk = chunk.loc[
            chunk["연도"] == latest_year
        ].copy()

        if not latest_chunk.empty:
            latest_chunks.append(latest_chunk)

    if not latest_chunks:
        raise ValueError("최신 연도의 인구 데이터를 찾지 못했습니다.")

    latest_data = pd.concat(
        latest_chunks,
        ignore_index=True,
    )

    # 코드는 계산할 숫자가 아니라 지역을 구분하는 이름표입니다.
    # 숫자로 읽혔을 가능성에 대비하여 문자열로 변환하고
    # 앞을 0으로 채워 열 자리로 맞춥니다.
    latest_data["코드"] = (
        latest_data["코드"]
        .astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.zfill(10)
    )

    # 행정동 코드 앞 5자리가 시군구 코드입니다.
    latest_data["시군구코드"] = latest_data["코드"].str[:5]

    # 인구 열에 쉼표나 특수 문자가 있어도 계산할 수 있도록
    # 숫자형으로 변환합니다.
    for column in total_age_columns:
        if column not in latest_data.columns:
            continue

        latest_data[column] = pd.to_numeric(
            latest_data[column]
            .astype("string")
            .str.replace(",", "", regex=False)
            .str.strip(),
            errors="coerce",
        ).fillna(0)

    available_total_columns = [
        column for column in total_age_columns
        if column in latest_data.columns
    ]

    available_elderly_columns = [
        column for column in elderly_columns
        if column in latest_data.columns
    ]

    if not available_total_columns:
        raise ValueError("'계_'로 시작하는 연령별 인구 열을 찾지 못했습니다.")

    if not available_elderly_columns:
        raise ValueError("65세 이상 인구 열을 찾지 못했습니다.")

    # 각 읍·면·동의 전체 인구와 65세 이상 인구를 계산합니다.
    latest_data["전체인구"] = latest_data[
        available_total_columns
    ].sum(axis=1)

    latest_data["65세이상인구"] = latest_data[
        available_elderly_columns
    ].sum(axis=1)

    # 읍·면·동 데이터를 시군구 단위로 합칩니다.
    sigungu_data = (
        latest_data
        .groupby(
            ["시군구코드", "시도", "시군구"],
            as_index=False,
            dropna=False,
        )[["전체인구", "65세이상인구"]]
        .sum()
    )

    # 전체 인구가 0인 지역은 나눗셈에서 제외합니다.
    sigungu_data["고령화율"] = np.where(
        sigungu_data["전체인구"] > 0,
        (
            sigungu_data["65세이상인구"]
            / sigungu_data["전체인구"]
            * 100
        ),
        np.nan,
    )

    return sigungu_data, latest_year


# ---------------------------------------------------------
# 3. 시군구 경계 데이터 불러오기
# ---------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_geojson():
    """
    전국 시군구 경계 GeoJSON을 내려받습니다.
    """

    response = requests.get(GEOJSON_URL, timeout=120)
    response.raise_for_status()

    geojson = response.json()

    # GeoJSON 코드도 문자열 5자리로 통일합니다.
    for feature in geojson.get("features", []):
        properties = feature.get("properties", {})
        code = properties.get("코드", "")

        properties["코드"] = (
            str(code)
            .replace(".0", "")
            .strip()
            .zfill(5)
        )

    return geojson


# ---------------------------------------------------------
# 4. 고령화율 구간 만들기
# ---------------------------------------------------------
def add_aging_group(data):
    """
    고령화율을 정해진 경계값에 따라 5단계로 나눕니다.
    """

    result = data.copy()

    group_labels = [
        "19% 미만",
        "19% 이상 23% 미만",
        "23% 이상 28% 미만",
        "28% 이상 38% 미만",
        "38% 이상",
    ]

    result["고령화 단계"] = pd.cut(
        result["고령화율"],
        bins=[
            -np.inf,
            19,
            23,
            28,
            38,
            np.inf,
        ],
        labels=group_labels,
        right=False,
        ordered=True,
    )

    return result, group_labels


# ---------------------------------------------------------
# 5. 지도 만들기
# ---------------------------------------------------------
def make_map(data, geojson, group_labels):
    """
    시군구별 고령화율을 5단계 색상으로 표현한
    단계구분도를 만듭니다.
    """

    # 낮은 비율은 옅게, 높은 비율은 진하게 표시합니다.
    color_map = {
    "19% 미만": "#ffffd9",
    "19% 이상 23% 미만": "#c7e9b4",
    "23% 이상 28% 미만": "#7fcdbb",
    "28% 이상 38% 미만": "#41b6c4",
    "38% 이상": "#225ea8",
}
    map_data = data.dropna(
        subset=["고령화율", "고령화 단계"]
    ).copy()

    map_data["고령화 단계"] = map_data[
        "고령화 단계"
    ].astype(str)

    # 마우스를 올렸을 때 표시할 고령화율입니다.
    map_data["고령화율 표시"] = (
        map_data["고령화율"]
        .round(1)
        .map(lambda value: f"{value:.1f}%")
    )

    figure = px.choropleth(
        map_data,
        geojson=geojson,
        locations="시군구코드",
        featureidkey="properties.코드",
        color="고령화 단계",
        category_orders={
            "고령화 단계": group_labels,
        },
        color_discrete_map=color_map,
        hover_name="시군구",
        hover_data={
            "시도": True,
            "고령화율 표시": True,
            "시군구코드": False,
            "고령화 단계": False,
        },
        labels={
            "고령화 단계": "고령화율 구간",
            "고령화율 표시": "고령화율",
        },
    )

    # 대한민국 전체 경계가 화면에 맞게 표시되도록 설정합니다.
    figure.update_geos(
        fitbounds="locations",
        visible=False,
        projection_type="mercator",
        bgcolor="rgba(0,0,0,0)",
    )

    # 시군구 경계선을 표시합니다.
    figure.update_traces(
        marker_line_color = "#B8B8B8"
        marker_line_width = 0.7,
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "시도: %{customdata[0]}<br>"
            "고령화율: %{customdata[1]}"
            "<extra></extra>"
        ),
    )

    figure.update_layout(
        height=780,
        margin=dict(
            l=0,
            r=0,
            t=10,
            b=0,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            title="고령화율 구간",
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#cccccc",
            borderwidth=1,
        ),
    )

    return figure


# ---------------------------------------------------------
# 6. 순위표 만들기
# ---------------------------------------------------------
def make_ranking_table(data, ascending=False):
    """
    고령화율 상위 또는 하위 10개 지역의 표를 만듭니다.
    """

    ranking = (
        data
        .dropna(subset=["고령화율"])
        .sort_values(
            "고령화율",
            ascending=ascending,
        )
        .head(10)
        .reset_index(drop=True)
    )

    ranking.insert(
        0,
        "순위",
        range(1, len(ranking) + 1),
    )

    ranking["고령화율"] = ranking["고령화율"].map(
        lambda value: f"{value:.1f}%"
    )

    return ranking[
        [
            "순위",
            "시도",
            "시군구",
            "고령화율",
        ]
    ]


# ---------------------------------------------------------
# 7. 화면 구성
# ---------------------------------------------------------
st.title("전국 시군구 고령화 지도")
st.caption(
    "시군구별 전체 인구 중 65세 이상 인구가 차지하는 비율을 나타냅니다."
)

try:
    with st.spinner("인구 데이터와 지도 경계를 불러오는 중입니다."):
        aging_data, latest_year = load_population_data()
        sigungu_geojson = load_geojson()

    aging_data, aging_group_labels = add_aging_group(
        aging_data
    )

    st.subheader(f"{latest_year}년 시군구별 65세 이상 인구 비율")

    st.caption(
        "고령화율 = 시군구의 65세 이상 인구 ÷ 시군구 전체 인구 × 100"
    )

    map_figure = make_map(
        aging_data,
        sigungu_geojson,
        aging_group_labels,
    )

    st.plotly_chart(
        map_figure,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "scrollZoom": False,
        },
    )

    st.divider()

    high_ranking = make_ranking_table(
        aging_data,
        ascending=False,
    )

    low_ranking = make_ranking_table(
        aging_data,
        ascending=True,
    )

    left_column, right_column = st.columns(2)

    with left_column:
        st.subheader("고령화율이 높은 시군구 10곳")
        st.dataframe(
            high_ranking,
            hide_index=True,
            use_container_width=True,
        )

    with right_column:
        st.subheader("고령화율이 낮은 시군구 10곳")
        st.dataframe(
            low_ranking,
            hide_index=True,
            use_container_width=True,
        )

    st.caption(
        "자료: 전국 읍·면·동 연령별 인구 데이터 및 전국 시군구 경계 GeoJSON"
    )

except requests.RequestException as error:
    st.error(
        "데이터를 내려받지 못했습니다. "
        "인터넷 연결이나 데이터 주소를 확인해 주세요."
    )
    st.exception(error)

except Exception as error:
    st.error(
        "데이터를 처리하는 중 오류가 발생했습니다."
    )
    st.exception(error)
