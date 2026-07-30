import streamlit as st
from openai import OpenAI

# --------------------------------------------------
# 1. 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="AI 정보 선생님",
    page_icon="🤖",
    layout="centered",
)

st.title("🤖 AI 정보 선생님")
st.caption("정보 수업에서 궁금한 내용을 편하게 질문해 보세요.")


# --------------------------------------------------
# 2. Upstage API 연결
# --------------------------------------------------
client = OpenAI(
    api_key=st.secrets["SOLAR_API_KEY"],
    base_url="https://api.upstage.ai/v1",
)


# --------------------------------------------------
# 3. AI 선생님의 성격 설정
# --------------------------------------------------
SYSTEM_PROMPT = """
너는 중고등학생에게 정보 과목을 가르치는 친절한 정보 선생님이야.

다음 규칙을 반드시 지켜.
1. 어려운 말은 학생이 이해하기 쉬운 말로 바꿔 설명해.
2. 반드시 자연스러운 한국어로만 답해.
3. 학생의 질문에 바로 답하기 전에 짧게 반응해.
4. 좋은 질문이면 칭찬하고, 어려움을 말하면 공감해.
5. 이모지는 한 답변에 1~3개 정도만 자연스럽게 사용해.
6. 설명이 길어지면 제목이나 번호를 사용해 보기 쉽게 정리해.
7. 잘못 알고 있는 내용은 무안하지 않게 부드럽게 고쳐 줘.
8. 마지막에는 이해를 확인하는 짧은 질문이나 도움말을 덧붙여.
9. 답을 모를 때는 아는 척하지 말고 정확히 모른다고 말해.
"""


# --------------------------------------------------
# 4. 대화 기록과 반응 기록 초기화
# --------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "assistant",
            "content": (
                "안녕하세요! 저는 **AI 정보 선생님**이에요. 🤖\n\n"
                "컴퓨터, 인공지능, 인터넷, 개인정보 보호 등 "
                "정보 과목에서 궁금한 내용을 물어보세요!"
            ),
        },
    ]

if "reactions" not in st.session_state:
    st.session_state.reactions = {}


# --------------------------------------------------
# 5. 답변 반응 버튼 함수
# --------------------------------------------------
def show_reaction_buttons(message_index):
    """각 AI 답변 아래에 반응 버튼을 표시한다."""

    reaction_key = str(message_index)
    selected_reaction = st.session_state.reactions.get(reaction_key)

    # 이미 반응을 선택했다면 선택 결과만 표시
    if selected_reaction:
        reaction_text = {
            "good": "👍 도움이 됐어요",
            "normal": "🙂 보통이에요",
            "bad": "🤔 조금 아쉬워요",
        }

        st.caption(f"내 반응: {reaction_text[selected_reaction]}")
        return

    st.caption("이 답변은 어땠나요?")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "👍 도움됐어요",
            key=f"good_{message_index}",
            use_container_width=True,
        ):
            st.session_state.reactions[reaction_key] = "good"
            st.toast("좋은 반응을 남겨 주셔서 감사해요!", icon="😊")
            st.rerun()

    with col2:
        if st.button(
            "🙂 보통이에요",
            key=f"normal_{message_index}",
            use_container_width=True,
        ):
            st.session_state.reactions[reaction_key] = "normal"
            st.toast("반응을 남겨 주셔서 감사해요!", icon="🙂")
            st.rerun()

    with col3:
        if st.button(
            "🤔 아쉬워요",
            key=f"bad_{message_index}",
            use_container_width=True,
        ):
            st.session_state.reactions[reaction_key] = "bad"
            st.toast("다음에는 더 쉽게 설명해 볼게요!", icon="✏️")
            st.rerun()


# --------------------------------------------------
# 6. 왼쪽 메뉴
# --------------------------------------------------
with st.sidebar:
    st.header("💬 대화 설정")

    st.write(
        "AI 정보 선생님은 정보 과목의 개념을 "
        "학생의 눈높이에 맞게 설명합니다."
    )

    if st.button(
        "🗑️ 새 대화 시작",
        use_container_width=True,
    ):
        st.session_state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "assistant",
                "content": (
                    "새로운 대화를 시작했어요! 😊\n\n"
                    "이번에는 무엇이 궁금한가요?"
                ),
            },
        ]

        st.session_state.reactions = {}
        st.rerun()

    st.divider()
    st.caption("AI의 답변에는 틀린 내용이 포함될 수 있어요.")


# --------------------------------------------------
# 7. 지금까지의 대화 출력
# --------------------------------------------------
for index, msg in enumerate(st.session_state.messages):
    if msg["role"] == "system":
        continue

    # 사용자와 AI의 아바타를 다르게 표시
    avatar = "🧑‍🎓" if msg["role"] == "user" else "🤖"

    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

        # AI의 답변에만 반응 버튼 표시
        if msg["role"] == "assistant":
            show_reaction_buttons(index)


# --------------------------------------------------
# 8. 채팅 입력창
# --------------------------------------------------
user_input = st.chat_input("궁금한 것을 물어보세요!")


# --------------------------------------------------
# 9. 질문을 입력했을 때
# --------------------------------------------------
if user_input:
    # 사용자 질문 저장
    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    # 사용자 질문 화면 출력
    with st.chat_message("user", avatar="🧑‍🎓"):
        st.markdown(user_input)

    # AI 답변 생성
    with st.chat_message("assistant", avatar="🤖"):
        try:
            # AI가 답변을 준비하고 있다는 반응 표시
            with st.spinner("질문을 살펴보고 있어요..."):
                stream = client.chat.completions.create(
                    model="solar-open2",
                    messages=st.session_state.messages,
                    reasoning_effort="none",
                    stream=True,
                )

            # 답변을 실시간으로 출력
            answer = st.write_stream(
                chunk.choices[0].delta.content or ""
                for chunk in stream
                if chunk.choices
            )

            # AI 답변을 대화 기록에 저장
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

            # 새로 생성된 답변 아래에도 반응 버튼 표시
            new_message_index = len(st.session_state.messages) - 1
            show_reaction_buttons(new_message_index)

        except Exception as error:
            st.error(
                "앗, 지금은 답변을 가져오지 못했어요. "
                "잠시 후 질문을 다시 보내 주세요."
            )

            # 개발 중에만 오류 원인을 확인하고 싶을 때 사용
            # st.exception(error)
