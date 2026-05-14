import os
import traceback
import uuid
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.doc_analyzer_agent import DocAnalyzerAgent
from utils.memory import ChatMemory

load_dotenv()

chat_memory = ChatMemory()
doc_analyzer_agent = DocAnalyzerAgent()

app = FastAPI()

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Memory storage configuration
USE_S3 = os.getenv("USE_S3", "false").lower() == "true"
S3_BUCKET = os.getenv("S3_BUCKET", "")
MEMORY_DIR = os.getenv("MEMORY_DIR", "../memory")

# LLM configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: list[dict[str, Any]]
    session_id: str


class Message(BaseModel):
    role: str
    content: str
    timestamp: str


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "message": "Assessment App API",
        "memory_enabled": True,
        "use_s3": USE_S3,
        "llm_provider": LLM_PROVIDER,
        "llm_model": LLM_MODEL,
    }


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "use_s3": USE_S3,
        "llm_provider": LLM_PROVIDER,
        "llm_model": LLM_MODEL,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process a chat message and return a response.

    Args:
        request: The chat request containing the message and session ID

    Returns:
        A chat response containing the response and session ID
    """

    try:
        session_id = request.session_id or str(uuid.uuid4())

        success_criteria = (
            "The assistant should be able give a valid answer to the user's question."
        )

        conversation = chat_memory.load_conversation(session_id)

        await doc_analyzer_agent.initialize()
        assistant_response = await doc_analyzer_agent.process_message(
            request.message, success_criteria, conversation, session_id
        )

        conversation.append(
            {
                "role": "user",
                "content": request.message,
                "timestamp": datetime.now().isoformat(),
            }
        )

        conversation.append(
            {
                "role": "assistant",
                "content": assistant_response[1]["content"],
                "timestamp": datetime.now().isoformat(),
            }
        )

        chat_memory.save_conversation(session_id, conversation)

        return ChatResponse(response=assistant_response, session_id=session_id)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat endpoint: \n{e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversation/{session_id}")
async def get_conversation(session_id: str) -> dict[str, Any]:
    """
    Retrieve conversation history
    """

    try:
        conversation = chat_memory.load_conversation(session_id)
        return {"session_id": session_id, "messages": conversation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
