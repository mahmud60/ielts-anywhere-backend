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
import random
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

# Maximum speaking sessions this single worker will run concurrently. The worker
# reports load = active_sessions / cap to LiveKit; once it crosses the threshold
# LiveKit stops routing new rooms here, so extra users wait instead of pushing a
# memory-constrained VM into OOM (which would kill live tests). Raise this via
# env once the VM is sized up or additional worker replicas are added.
MAX_CONCURRENT_SESSIONS = int(os.environ.get("AGENT_MAX_SESSIONS", "4"))

PERSONAS = [
    {"name": "Sarah",   "voice": "nova",    "gender": "female"},
    {"name": "Claire",  "voice": "shimmer",  "gender": "female"},
    {"name": "James",   "voice": "echo",    "gender": "male"},
    {"name": "Michael", "voice": "onyx",    "gender": "male"},
]

IELTS_EXAMINER_PROMPT = """Your name is {name}. You are a certified IELTS speaking examiner conducting an official IELTS Speaking test. \
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
    def __init__(self, name: str) -> None:
        super().__init__(instructions=IELTS_EXAMINER_PROMPT.format(name=name))
        self._name = name

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=f"Greet the candidate warmly, introduce yourself as {self._name}, and ask for their full name to begin Part 1."
        )


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
    persona = random.choice(PERSONAS)
    logger.info("Agent joined room: %s (examiner: %s)", ctx.room.name, persona["name"])

    session = AgentSession(
        stt=deepgram.STT(
            model="nova-2",
            api_key=os.environ["DEEPGRAM_API_KEY"],
        ),
        llm=lk_openai.LLM(
            model="gpt-4o-mini",
            api_key=os.environ["OPENAI_API_KEY"],
        ),
        tts=lk_openai.TTS(
            model="tts-1",
            voice=persona["voice"],
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
        agent=IELTSExaminer(name=persona["name"]),
        room_input_options=RoomInputOptions(),
    )
    logger.info("AgentSession started for room: %s", ctx.room.name)


def _compute_load(*args) -> float:
    """Report worker load as a fraction of the concurrency cap.

    livekit-agents invokes this with the worker/server instance (newer API) or
    with no arguments (older API), so accept *args. If the active-job list isn't
    exposed under the expected name on the installed version, fall back to 0.0
    (no cap) rather than raising and taking the worker down.
    """
    worker = args[0] if args else None
    jobs = getattr(worker, "active_jobs", None)
    if jobs is None:
        return 0.0
    return min(len(jobs) / MAX_CONCURRENT_SESSIONS, 1.0)


def _build_worker_options() -> WorkerOptions:
    """Construct WorkerOptions, passing concurrency/memory tuning only if the
    installed livekit-agents version accepts each kwarg. The worker API has
    shifted across 1.x, so we introspect the signature instead of risking a
    startup crash on an unknown argument.
    """
    import inspect

    opts = {"entrypoint_fnc": entrypoint}
    supported = set(inspect.signature(WorkerOptions).parameters)
    for key, value in (
        ("load_fnc", _compute_load),       # count-based load => graceful shed
        ("load_threshold", 0.75),          # stop accepting near the cap
        ("num_idle_processes", 1),         # keep idle memory low on a small VM
    ):
        if key in supported:
            opts[key] = value
    return WorkerOptions(**opts)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli.run_app(_build_worker_options())
