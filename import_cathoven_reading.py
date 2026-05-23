"""
Import cathoven_reading_tests.json + cathoven_reading_answers.json
into the reading DB tables.

Run from the backend root:
    python import_cathoven_reading.py
"""
import json
import os
import uuid
import psycopg2
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

DB = (
    os.getenv("DATABASE_URL", "")
    .replace("postgresql+asyncpg://", "postgresql://")
    .replace("postgresql+psycopg2://", "postgresql://")
)
if not DB:
    raise RuntimeError("DATABASE_URL not set")

with open("cathoven_reading_tests.json", encoding="utf-8") as f:
    tests = json.load(f)

with open("cathoven_reading_answers.json", encoding="utf-8") as f:
    answers = json.load(f)  # { "cathoven_q_id_str": ["ans1", ...] }


def null_title(t):
    if not t or str(t).strip() in ("None", "-"):
        return None
    return str(t).strip()


def map_question_type(q_type: str, ielts_type: str | None) -> str:
    """Map Cathoven question_type + ielts_question_type to DB enum value."""
    if q_type == "fill_in_the_blank":
        return "fill"
    if q_type == "multiple_select":
        return "multiple_select"
    if q_type == "multiple_choices":
        if ielts_type in ("identifying_information", "identifying_writers_views"):
            return "tfng"
        return "mcq"
    if q_type == "dropdown":
        if ielts_type in ("identifying_information", "identifying_writers_views"):
            return "tfng"
        if ielts_type == "matching_headings":
            return "matching_headings"
        if ielts_type == "multiple_choice":
            return "mcq"
        # matching_information, matching_features, matching_sentence_endings,
        # summary_note_table_flow_chart_completion, None → letter-based matching
        return "matching_info"
    return "matching_info"


conn = psycopg2.connect(DB)
conn.autocommit = False
cur = conn.cursor()

inserted_tests = 0
inserted_questions = 0

try:
    for raw_qid, test in tests.items():
        # ── reading_tests ─────────────────────────────────────────────────────
        test_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO reading_tests
                (id, source_qid, title, description, task, test_type,
                 test_order, is_active, is_recommended, mock_test_order)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (source_qid) DO UPDATE
                SET title = EXCLUDED.title,
                    description = EXCLUDED.description
            RETURNING id
            """,
            (
                test_id,
                test.get("qid"),
                test.get("title") or test.get("question"),
                test.get("description"),
                test.get("task"),
                "general" if "general" in (test.get("task") or "").lower() else "academic",
                test.get("order"),
                test.get("is_active", True),
                test.get("is_recommended", False),
                test.get("mock_test_order"),
            ),
        )
        actual_test_id = str(cur.fetchone()[0])
        inserted_tests += 1

        # Skip if passages already exist (idempotent re-run)
        cur.execute(
            "SELECT COUNT(*) FROM reading_passages WHERE test_id = %s",
            (actual_test_id,),
        )
        if cur.fetchone()[0] > 0:
            continue

        for section in test.get("sections", []):
            # ── reading_passages ──────────────────────────────────────────────
            passage_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO reading_passages
                    (id, test_id, passage_number, title, body)
                VALUES (%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    passage_id,
                    actual_test_id,
                    section.get("part"),
                    section.get("title", ""),
                    section.get("text", ""),
                ),
            )
            actual_passage_id = str(cur.fetchone()[0])

            for sub in section.get("subsections", []):
                qs = sub.get("questions", [])
                if not qs:
                    continue

                # Derive group question_type from first question (all uniform)
                first_q = qs[0]
                db_qtype = map_question_type(
                    first_q.get("question_type", ""),
                    first_q.get("ielts_question_type"),
                )

                # ── reading_question_groups ───────────────────────────────────
                group_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO reading_question_groups
                        (id, passage_id, order_index, question_type,
                         instruction, subsection_type, title, image)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        group_id,
                        actual_passage_id,
                        sub.get("order"),
                        db_qtype,
                        sub.get("text") or "",
                        sub.get("subsection_type"),
                        null_title(sub.get("title")),
                        sub.get("image"),
                    ),
                )
                actual_group_id = str(cur.fetchone()[0])

                for q in qs:
                    cathoven_qid = str(q["id"])
                    answer_key = answers.get(cathoven_qid)

                    cur.execute(
                        """
                        INSERT INTO reading_questions
                            (id, group_id, order_index, question_text,
                             options, answer_key,
                             group_label, ielts_question_type, max_selected_options)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            str(uuid.uuid4()),
                            actual_group_id,
                            q.get("order"),
                            q.get("text", ""),
                            json.dumps(q.get("options", [])),
                            json.dumps(answer_key) if answer_key is not None else json.dumps([]),
                            null_title(q.get("title")),
                            q.get("ielts_question_type"),
                            q.get("max_selected_options"),
                        ),
                    )
                    inserted_questions += 1

    conn.commit()
    print(f"Done. Inserted {inserted_tests} tests, {inserted_questions} questions.")

except Exception as e:
    conn.rollback()
    print(f"ERROR: {e}")
    raise
finally:
    cur.close()
    conn.close()