"""
Generate and push wrong_answer_tip for all listening and reading questions.
Run from the repo root: python -m scripts.push_question_tips [--overwrite] [--module listening|reading]

Reads DATABASE_URL and ANTHROPIC_API_KEY from .env.
"""
import argparse
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

# Must be set before importing any app code
os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL", ""))
os.environ.setdefault("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))

import psycopg2
from psycopg2.extras import RealDictCursor
import anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM = (
    "You are an IELTS coach. Write a single specific, actionable tip (1-2 sentences) "
    "that helps a student get this exact question right next time. "
    "Focus on the listening/reading strategy — what to listen/look for, "
    "common traps for this question type, or how the correct answer is signalled. "
    "Do NOT reveal or restate the answer. Return only the tip text, no preamble."
)

_LISTENING_TYPE_HINTS = {
    "fill_in_the_blank": "Listen for stressed words, spelling cues, and number/name signposting.",
    "multiple_choices":  "Listen for paraphrases of the options, not the exact words.",
    "multiple_select":   "Speakers sometimes mention a point then contradict it — wait for the final stance.",
    "dropdown":          "Match by meaning, not by word — the recording uses synonyms of the options.",
}

_READING_TYPE_HINTS = {
    "tfng":               "Check whether the passage directly supports or contradicts the statement, or simply doesn't mention it.",
    "mcq":                "Locate the relevant paragraph first, then eliminate wrong options using the passage — not general knowledge.",
    "fill":               "Copy the exact word(s) from the passage; paraphrases are wrong.",
    "matching_headings":  "Read the paragraph's main idea first, ignore minor details, then match to the heading.",
    "matching_info":      "Scan for the specific fact or name in each paragraph; it may appear once.",
    "short_answer":       "Use only words from the passage; do not exceed the word limit.",
    "multiple_select":    "All correct options must be stated in the passage, not just implied.",
}


def call_haiku(prompt: str) -> str:
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def tip_for_listening(question_type, stem, answer_key) -> str:
    hint = _LISTENING_TYPE_HINTS.get(question_type, "")
    prompt = (
        f"Question type: {question_type}\n"
        f"Question: {(stem or '(fill in the blank)')[:200]}\n"
        f"Correct answer: {str(answer_key)[:80]}\n"
        f"Strategy hint: {hint}\n\nWrite the tip."
    )
    return call_haiku(prompt)


def tip_for_reading(question_type, question_text, answer_key, instruction="") -> str:
    hint = _READING_TYPE_HINTS.get(question_type, "")
    prompt = (
        f"Question type: {question_type}\n"
        f"Instruction: {(instruction or '')[:150]}\n"
        f"Question: {(question_text or '')[:200]}\n"
        f"Correct answer: {str(answer_key)[:80]}\n"
        f"Strategy hint: {hint}\n\nWrite the tip."
    )
    return call_haiku(prompt)


def process_listening(conn, overwrite: bool):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if overwrite:
            cur.execute("SELECT id, question_type, stem, answer_key FROM listening_questions")
        else:
            cur.execute(
                "SELECT id, question_type, stem, answer_key FROM listening_questions "
                "WHERE wrong_answer_tip IS NULL OR wrong_answer_tip = ''"
            )
        rows = cur.fetchall()

    print(f"[listening] {len(rows)} questions to process")
    updated = 0
    for i, row in enumerate(rows, 1):
        try:
            tip = tip_for_listening(row["question_type"], row["stem"], row["answer_key"])
            if tip:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE listening_questions SET wrong_answer_tip = %s WHERE id = %s",
                        (tip, row["id"]),
                    )
                conn.commit()
                updated += 1
                print(f"  [{i}/{len(rows)}] Q{row['id']} OK")
            else:
                print(f"  [{i}/{len(rows)}] Q{row['id']} EMPTY TIP — skipped")
        except Exception as e:
            print(f"  [{i}/{len(rows)}] Q{row['id']} ERROR: {e}")
            conn.rollback()
        time.sleep(0.3)  # ~3 req/s to stay within rate limits

    print(f"[listening] done — {updated}/{len(rows)} updated")


def process_reading(conn, overwrite: bool):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if overwrite:
            cur.execute("""
                SELECT rq.id, rq.question_text, rq.answer_key, rg.question_type, rg.instruction
                FROM reading_questions rq
                JOIN reading_question_groups rg ON rq.group_id = rg.id
            """)
        else:
            cur.execute("""
                SELECT rq.id, rq.question_text, rq.answer_key, rg.question_type, rg.instruction
                FROM reading_questions rq
                JOIN reading_question_groups rg ON rq.group_id = rg.id
                WHERE rq.wrong_answer_tip IS NULL OR rq.wrong_answer_tip = ''
            """)
        rows = cur.fetchall()

    print(f"[reading] {len(rows)} questions to process")
    updated = 0
    for i, row in enumerate(rows, 1):
        try:
            tip = tip_for_reading(
                row["question_type"], row["question_text"],
                row["answer_key"], row["instruction"],
            )
            if tip:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE reading_questions SET wrong_answer_tip = %s WHERE id = %s",
                        (tip, row["id"]),
                    )
                conn.commit()
                updated += 1
                print(f"  [{i}/{len(rows)}] Q{row['id']} OK")
            else:
                print(f"  [{i}/{len(rows)}] Q{row['id']} EMPTY TIP — skipped")
        except Exception as e:
            print(f"  [{i}/{len(rows)}] Q{row['id']} ERROR: {e}")
            conn.rollback()
        time.sleep(0.3)

    print(f"[reading] done — {updated}/{len(rows)} updated")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true",
                        help="Regenerate tips even if one already exists")
    parser.add_argument("--module", choices=["listening", "reading", "both"], default="both")
    args = parser.parse_args()

    # psycopg2 needs postgresql:// not postgresql+asyncpg://
    db_url = DATABASE_URL.replace("+asyncpg", "").replace("postgresql+psycopg2", "postgresql")

    print(f"Connecting to DB…")
    conn = psycopg2.connect(db_url)
    print(f"Connected. overwrite={args.overwrite}, module={args.module}")

    try:
        if args.module in ("listening", "both"):
            process_listening(conn, args.overwrite)
        if args.module in ("reading", "both"):
            process_reading(conn, args.overwrite)
    finally:
        conn.close()

    print("All done.")


if __name__ == "__main__":
    main()