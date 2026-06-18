"""
IELTS Speaking Agent — LiveKit voice pipeline (livekit-agents 1.x)
==================================================================
Run alongside FastAPI as a separate process:

  Development:   python speaking_agent.py dev
  Production:    python speaking_agent.py start

Requires env vars (loaded from .env):
  LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
  DEEPGRAM_API_KEY
  GOOGLE_API_KEY        (Google AI Studio / Gemini)
  OPENAI_API_KEY        (for TTS)
"""

import asyncio
import json
import logging
import os
import time

from dotenv import load_dotenv

load_dotenv()

from livekit.agents import (
    Agent,
    AgentSession,
    ChatMessage,
    ConversationItemAddedEvent,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
)
from livekit.plugins import deepgram
from livekit.plugins import openai as lk_openai
from livekit.plugins import google as lk_google

logger = logging.getLogger("ielts-speaking-agent")

IELTS_EXAMINER_PROMPT = """You are a certified IELTS speaking examiner conducting an official IELTS Speaking test. \
The test has three parts:

Part 1 (first 5 minutes): Introduction and interview. Ask about familiar topics such as home, family, work, \
studies, and hobbies. Keep questions short and natural.

Part 2 (next 4 minutes): Long turn. Give the candidate a topic and ask them to talk for 1-2 minutes, then \
ask 1-2 brief follow-up questions.

Part 3 (final 6 minutes): Two-way discussion. Ask more abstract questions linked to the Part 2 topic. \
Explore the candidate's opinions and ideas.

Guidelines:
- Begin by greeting the candidate warmly and asking for their full name.
- Ask only one question at a time.
- Be encouraging but neutral — do not comment on the quality of answers.
- Do not score or evaluate aloud during the conversation.
- If the candidate seems confused, rephrase the question once, gently.
- Stay strictly within the IELTS exam format and timing.
"""


class IELTSExaminer(Agent):
    def __init__(self):
        super().__init__(instructions=IELTS_EXAMINER_PROMPT)


async def _publish_transcript(ctx: JobContext, role: str, text: str) -> None:
    """Send a transcript entry to the browser via LiveKit data channel."""
    try:
        payload = json.dumps({
            "role": role,
            "text": text,
            "timestamp": int(time.time() * 1000),
        }).encode("utf-8")
        await ctx.room.local_participant.publish_data(payload, reliable=True)
    except Exception as exc:
        logger.warning("Transcript publish failed: %s", exc)


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    logger.info("Agent joined room: %s", ctx.room.name)

    session = AgentSession(
        stt=deepgram.STT(
            model="nova-2",
            api_key=os.environ["DEEPGRAM_API_KEY"],
        ),
        llm=lk_google.LLM(
            model="gemini-2.0-flash",
            api_key=os.environ["GOOGLE_API_KEY"],
        ),
        tts=lk_openai.TTS(
            model="tts-1",
            voice="nova",
            api_key=os.environ["OPENAI_API_KEY"],
        ),
    )

    @session.on("conversation_item_added")
    def on_item_added(event: ConversationItemAddedEvent) -> None:
        item = event.item
        if not isinstance(item, ChatMessage):
            return
        text = item.text_content
        if not text or not text.strip():
            return
        role = "user" if str(item.role) == "user" else "agent"
        asyncio.ensure_future(_publish_transcript(ctx, role, text.strip()))

    await session.start(
        room=ctx.room,
        agent=IELTSExaminer(),
        room_input_options=RoomInputOptions(),
    )
    logger.info("AgentSession started for room: %s", ctx.room.name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
