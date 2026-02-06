import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from typing import Any

from llm_cards import fill_cards

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:  # pragma: no cover
    pymysql = None
    DictCursor = None


CANONICAL_VERSION = "v1"


STACK_RULES: dict[str, list[str]] = {
    "spring_boot": [
        "spring boot",
        "springboot",
        "\uc2a4\ud504\ub9c1\ubd80\ud2b8",
        "\uc2a4\ud504\ub9c1 \ubd80\ud2b8",
    ],
    "postgresql": [
        "postgres",
        "postgresql",
        "postgre",
        "psql",
        "\ud3ec\uc2a4\ud2b8\uadf8\ub808\uc2a4",
    ],
    "redis": ["redis", "\ub808\ub514\uc2a4"],
    "github_actions": [
        "github action",
        "github actions",
        "gh actions",
        "\uae43\ud5c8\ube0c \uc561\uc158",
        "\uae43\ud5c8\ube0c \uc561\uc158\uc988",
    ],
}

TOPIC_RULES: dict[str, list[str]] = {
    "n_plus_one_optimization": [
        "n+1",
        "n + 1",
        "nplus1",
        "\uc5d4\ud50c\ub7ec\uc2a4\uc6d0",
    ],
    "index_tuning": [
        "\uc778\ub371\uc2a4 \ud29c\ub2dd",
        "index tuning",
        "index optimize",
        "query tuning",
        "\ucffc\ub9ac \ud29c\ub2dd",
    ],
    "cache_strategy": [
        "\uce90\uc2dc \ub3c4\uc785",
        "cache",
        "caching",
        "\uce90\uc2f1",
    ],
    "throughput_optimization": [
        "tps",
        "throughput",
        "latency",
        "\uc131\ub2a5 \uac1c\uc120",
    ],
    "ci_cd_pipeline": [
        "ci/cd",
        "ci cd",
        "ci pipeline",
        "cd pipeline",
        "\ubc30\ud3ec \uc790\ub3d9\ud654",
        "\ud30c\uc774\ud504\ub77c\uc778 \uad6c\ucd95",
    ],
    "concurrency_control": [
        "\ub3d9\uc2dc\uc131 \uc81c\uc5b4",
        "\ub77d",
        "\ub099\uad00\uc801 \ub77d",
        "\ube44\uad00\uc801 \ub77d",
        "optimistic lock",
        "pessimistic lock",
    ],
    "inventory_deduction_logic": [
        "\uc7ac\uace0 \ucc28\uac10",
        "\uc7ac\uace0 \uac10\uc18c",
        "inventory deduction",
        "stock deduction",
    ],
}

CATEGORY_BY_TAG: dict[str, set[str]] = {
    "backend": {"spring_boot", "concurrency_control", "inventory_deduction_logic"},
    "database": {"postgresql", "index_tuning", "n_plus_one_optimization"},
    "performance": {"throughput_optimization", "cache_strategy", "index_tuning"},
    "devops": {"github_actions", "ci_cd_pipeline"},
    "architecture": {"concurrency_control", "cache_strategy"},
}


@dataclass
class Mentor:
    mentor_id: int
    name: str
    company: str
    price: int
    mentoring_count: int
    stacks: set[str]
    topics: set[str]
    quality: float


def normalize_text(text: str) -> str:
    value = text.lower().strip()
    value = re.sub(r"[^\w\s\+\-/]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def split_tokens(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[,/|;\n]+", raw)
    return [p.strip() for p in parts if p.strip()]


def match_canonical(text: str, rules: dict[str, list[str]]) -> list[dict[str, str]]:
    normalized = normalize_text(text)
    hits: list[dict[str, str]] = []
    for canonical, aliases in rules.items():
        for alias in aliases:
            alias_norm = normalize_text(alias)
            if alias_norm and alias_norm in normalized:
                hits.append({"canonical": canonical, "alias": alias, "evidence": text})
                break
    return hits


def extract_user_tags(sentences: list[str]) -> dict[str, Any]:
    stacks: set[str] = set()
    topics: set[str] = set()
    normalized_items: list[dict[str, Any]] = []
    unknown_items: list[dict[str, str]] = []

    for sentence in sentences:
        stack_hits = match_canonical(sentence, STACK_RULES)
        topic_hits = match_canonical(sentence, TOPIC_RULES)

        if not stack_hits and not topic_hits:
            unknown_items.append({"raw": sentence, "reason": "no_rule_match"})

        for hit in stack_hits:
            stacks.add(hit["canonical"])
            normalized_items.append(
                {
                    "type": "stack",
                    "canonical": hit["canonical"],
                    "synonyms": STACK_RULES[hit["canonical"]],
                    "confidence": 0.95,
                    "evidence": hit["evidence"],
                    "source": "rule",
                }
            )

        for hit in topic_hits:
            topics.add(hit["canonical"])
            normalized_items.append(
                {
                    "type": "topic",
                    "canonical": hit["canonical"],
                    "synonyms": TOPIC_RULES[hit["canonical"]],
                    "confidence": 0.95,
                    "evidence": hit["evidence"],
                    "source": "rule",
                }
            )

    categories: set[str] = set()
    all_tags = stacks | topics
    for category, mapped in CATEGORY_BY_TAG.items():
        if all_tags & mapped:
            categories.add(category)
            normalized_items.append(
                {
                    "type": "category",
                    "canonical": category,
                    "synonyms": [category],
                    "confidence": 0.9,
                    "evidence": "derived_from_matched_tags",
                    "source": "rule",
                }
            )

    return {
        "version": CANONICAL_VERSION,
        "stacks": sorted(stacks),
        "topics": sorted(topics),
        "categories": sorted(categories),
        "normalized_items": normalized_items,
        "unknown_items": unknown_items,
    }


def clamp_0_1(value: float) -> float:
    return max(0.0, min(1.0, value))


def compute_quality(mentoring_count: int, cohort_max: int) -> float:
    if cohort_max <= 0:
        return 0.5
    return clamp_0_1(math.log1p(max(0, mentoring_count)) / math.log1p(cohort_max))


def recommend_top_n(
    user_topics: set[str],
    user_stacks: set[str],
    mentors: list[Mentor],
    n: int = 5,
    w_topic: float = 0.5,
    w_stack: float = 0.3,
    w_quality: float = 0.2,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    topic_den = max(1, len(user_topics))
    stack_den = max(1, len(user_stacks))

    for mentor in mentors:
        overlap_topics = sorted(user_topics & mentor.topics)
        overlap_stacks = sorted(user_stacks & mentor.stacks)
        topic_match = len(overlap_topics) / topic_den
        stack_match = len(overlap_stacks) / stack_den
        quality = clamp_0_1(mentor.quality)
        total = (w_topic * topic_match) + (w_stack * stack_match) + (w_quality * quality)

        results.append(
            {
                "mentor_id": mentor.mentor_id,
                "mentor_name": mentor.name,
                "company": mentor.company,
                "price": mentor.price,
                "mentoring_count": mentor.mentoring_count,
                "total_score": round(total, 6),
                "topicMatch": round(topic_match, 6),
                "stackMatch": round(stack_match, 6),
                "quality": round(quality, 6),
                "overlap_topics": overlap_topics,
                "overlap_stacks": overlap_stacks,
            }
        )

    results.sort(key=lambda x: (-x["total_score"], -x["quality"], x["mentor_id"]))
    return results[:n]


def build_top5_card_prompt(payload: dict[str, Any]) -> str:
    return (
        "[System]\n"
        "You generate mentor recommendation card JSON only.\n"
        "Output schema:\n"
        "{\n"
        '  "mentor_id": "",\n'
        '  "one_line_reason": "",\n'
        '  "overlap_tags": [],\n'
        '  "caution_points": []\n'
        "}\n"
        "Rules:\n"
        "1) one_line_reason around 25 Korean chars.\n"
        "2) overlap_tags must be real intersections.\n"
        "3) caution_points only when missing skills are meaningful.\n"
        "4) No markdown, JSON only.\n\n"
        "[User]\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def load_keyword_sentences(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or len(data) != 5:
        raise ValueError("Input JSON must be an array of exactly 5 sentences.")
    if not all(isinstance(x, str) for x in data):
        raise ValueError("All items in input JSON must be strings.")
    return data


def resolve_keyword_table(conn: Any, preferred: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", preferred):
        raise ValueError("Invalid keyword table name format.")
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES LIKE %s", (preferred,))
        if cur.fetchone():
            return preferred
        fallback = "keywords" if preferred == "keyword" else "keyword"
        cur.execute("SHOW TABLES LIKE %s", (fallback,))
        if cur.fetchone():
            return fallback
    raise ValueError("Neither `keyword` nor `keywords` table was found.")


def build_db_connection(args: argparse.Namespace) -> Any:
    if pymysql is None:
        raise RuntimeError("pymysql is required. Install with: pip install pymysql")
    return pymysql.connect(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        database=args.db_name,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
    )


def fetch_mentors_from_mysql(conn: Any, keyword_table: str) -> list[dict[str, Any]]:
    sql = f"""
    SELECT
      u.id AS mentor_id,
      u.name AS mentor_name,
      COALESCE(mp.company, '') AS company,
      COALESCE(mp.price, 0) AS price,
      COALESCE(mp.mentoring_count, 0) AS mentoring_count,
      COALESCE(mp.tech_stack, '') AS tech_stack,
      COALESCE(GROUP_CONCAT(k.name SEPARATOR ','), '') AS keyword_names
    FROM users u
    INNER JOIN mentor_profiles mp
      ON mp.user_id = u.id
    LEFT JOIN keyword_mapping km
      ON km.user_id = u.id
    LEFT JOIN `{keyword_table}` k
      ON k.id = km.keyword_id
    WHERE u.role = 'MENTOR'
    GROUP BY u.id, u.name, mp.company, mp.price, mp.mentoring_count, mp.tech_stack
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def canonicalize_mentor_tags(tech_stack: str, keyword_names: str) -> tuple[set[str], set[str]]:
    stacks: set[str] = set()
    topics: set[str] = set()
    fragments = split_tokens(tech_stack) + split_tokens(keyword_names)
    for token in fragments:
        for hit in match_canonical(token, STACK_RULES):
            stacks.add(hit["canonical"])
        for hit in match_canonical(token, TOPIC_RULES):
            topics.add(hit["canonical"])
    return stacks, topics


def build_mentor_models(rows: list[dict[str, Any]]) -> list[Mentor]:
    if not rows:
        return []
    cohort_max = max(int(r.get("mentoring_count") or 0) for r in rows)
    mentors: list[Mentor] = []
    for row in rows:
        stacks, topics = canonicalize_mentor_tags(row.get("tech_stack", ""), row.get("keyword_names", ""))
        mentors.append(
            Mentor(
                mentor_id=int(row["mentor_id"]),
                name=str(row.get("mentor_name") or ""),
                company=str(row.get("company") or ""),
                price=int(row.get("price") or 0),
                mentoring_count=int(row.get("mentoring_count") or 0),
                stacks=stacks,
                topics=topics,
                quality=compute_quality(int(row.get("mentoring_count") or 0), cohort_max),
            )
        )
    return mentors


def main() -> None:
    parser = argparse.ArgumentParser(description="Rule + score tutor recommendation (MySQL)")
    parser.add_argument("--keywords", default="result.json", help="Path to 5-sentence keyword JSON")
    parser.add_argument("--top-n", type=int, default=5, help="Top N mentors")
    parser.add_argument("--out", default="", help="Output JSON path (stdout if empty)")
    parser.add_argument("--fill-cards", action="store_true", help="Call LLM and fill top5 cards")
    parser.add_argument("--cards-out", default="cards.json", help="Output path for filled cards JSON")
    parser.add_argument("--merged-out", default="out.json", help="Output path for merged result JSON")
    parser.add_argument("--llm-provider", default="gemini_http", help="LLM provider name")
    parser.add_argument("--llm-model", default="gemini-2.0-flash", help="LLM model name")
    parser.add_argument("--llm-timeout", type=int, default=10, help="LLM call timeout seconds")
    parser.add_argument(
        "--llm-max-concurrency",
        type=int,
        default=3,
        help="Maximum concurrent LLM calls",
    )
    parser.add_argument("--llm-cache-dir", default="./cache/cards", help="Card cache directory")
    parser.add_argument("--llm-retry", type=int, default=1, help="Retries on LLM parse/validation failure")

    parser.add_argument("--db-host", default=os.getenv("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--db-user", default=os.getenv("MYSQL_USER", "root"))
    parser.add_argument("--db-password", default=os.getenv("MYSQL_PASSWORD", ""))
    parser.add_argument("--db-name", default=os.getenv("MYSQL_DB", ""))
    parser.add_argument("--keyword-table", default=os.getenv("MYSQL_KEYWORD_TABLE", "keyword"))
    args = parser.parse_args()

    sentences = load_keyword_sentences(args.keywords)
    user_normalized = extract_user_tags(sentences)

    result: dict[str, Any] = {
        "normalized_user": user_normalized,
        "top_n": [],
        "top5_card_prompts": [],
        "cards": [],
        "fallback": None,
    }

    if not args.db_name:
        result["fallback"] = "MYSQL_DB not set. Returned normalized user tags only."
    else:
        conn = build_db_connection(args)
        try:
            actual_keyword_table = resolve_keyword_table(conn, args.keyword_table)
            rows = fetch_mentors_from_mysql(conn, actual_keyword_table)
            mentors = build_mentor_models(rows)
            ranked = recommend_top_n(
                user_topics=set(user_normalized["topics"]),
                user_stacks=set(user_normalized["stacks"]),
                mentors=mentors,
                n=args.top_n,
            )
            result["top_n"] = ranked

            mentor_by_id = {m.mentor_id: m for m in mentors}
            validator_payloads: list[dict[str, Any]] = []
            for item in ranked[:5]:
                mentor = mentor_by_id[item["mentor_id"]]
                payload = {
                    "mentor_id": item["mentor_id"],
                    "U_topics": sorted(user_normalized["topics"]),
                    "U_stacks": sorted(user_normalized["stacks"]),
                    "M_topics": sorted(mentor.topics),
                    "M_stacks": sorted(mentor.stacks),
                    "overlap": {
                        "topics": item["overlap_topics"],
                        "stacks": item["overlap_stacks"],
                    },
                    "score_breakdown": {
                        "topicMatch": item["topicMatch"],
                        "stackMatch": item["stackMatch"],
                        "quality": item["quality"],
                        "total": item["total_score"],
                    },
                }
                result["top5_card_prompts"].append(
                    {
                        "mentor_id": item["mentor_id"],
                        "prompt_for_llm": build_top5_card_prompt(payload),
                    }
                )
                validator_payloads.append(payload)

            if args.fill_cards:
                try:
                    cards = fill_cards(
                        top5_card_prompts=result["top5_card_prompts"],
                        validator_payloads=validator_payloads,
                        provider=args.llm_provider,
                        model=args.llm_model,
                        timeout=args.llm_timeout,
                        max_concurrency=args.llm_max_concurrency,
                        cache_dir=args.llm_cache_dir,
                        retry=args.llm_retry,
                    )
                except Exception as exc:
                    print(f"[fill-cards] error: {exc}", file=sys.stderr)
                    raise SystemExit(2)

                result["cards"] = cards
        finally:
            conn.close()

    payload_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.fill_cards:
        with open(args.cards_out, "w", encoding="utf-8") as f:
            f.write(json.dumps(result["cards"], ensure_ascii=False, indent=2))
        with open(args.merged_out, "w", encoding="utf-8") as f:
            f.write(payload_text)
        print(payload_text)
    elif args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload_text)
    else:
        print(payload_text)


if __name__ == "__main__":
    main()
