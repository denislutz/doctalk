from doctalk_shared.models import ChatMessage, RetrievedChunk
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# LCEL CHAIN OVERVIEW
# ───────────────────
# LangChain Expression Language (LCEL) uses the pipe operator | to compose Runnables:
#
#   chain = prompt | llm | output_parser
#
# Each component implements the Runnable interface:
#   .invoke(input)          → synchronous, returns final output
#   .ainvoke(input)         → async version (use this in FastAPI)
#   .astream(input)         → async generator, yields tokens as they arrive
#
# DATA FLOW through the chain for a single query:
#
#   query.py                    chain.py                        Ollama / Claude
#   ────────                    ────────                        ───────────────
#   search results (chunks)
#     → _chunks_to_prompt_context()
#     → {"formatted_chunks": "...", "question": "..."}
#                               → ChatPromptTemplate
#                                   fills {formatted_chunks} and {question}
#                                   into system + human message slots
#                               → ChatOllama / ChatAnthropic
#                                   sends filled prompt to LLM
#                                   returns AIMessage
#                               → StrOutputParser
#                                   extracts .content string from AIMessage
#   answer string ←─────────────────────────────────────────────────────────
#

SYSTEM_PROMPT = """
You are a helpful assistant that answers questions based on the provided context.
Always cite your sources using the format [Source: filename, page number].
Synthesize your answer from all relevant context chunks provided.
If you cannot find an answer in the context, say "I couldn't find this information in the provided documents."
""".strip()


async def generate_answer(
    question: str,
    chunks: list[RetrievedChunk],
    llm: BaseChatModel,
    history: list[ChatMessage] | None = None,
) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "Context:\n{formatted_chunks}\n\nQuestion: {question}"),
        ]
    )
    chain = prompt | llm | StrOutputParser()

    chunk_lines = []
    for chunk in chunks:
        chunk_lines.append(f"Source: {chunk.source_name}, page: {chunk.page}\n{chunk.content}")
    formatted_chunks = "\n\n".join(chunk_lines)
    chat_history = [
        HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
        for m in (history or [])
    ]

    return str(
        await chain.ainvoke(
            {
                "formatted_chunks": formatted_chunks,
                "question": question,
                "chat_history": chat_history,
            }
        )
    )
