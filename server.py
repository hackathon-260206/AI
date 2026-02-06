import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from portfolio_text_analyzer import analyze_with_gemini, mask_pii
from recommand_tutor import (
    build_db_connection,
    build_mentor_models,
    extract_user_tags,
    fetch_mentors_from_mysql,
    recommend_top_n,
    resolve_keyword_table,
    simplify_top_n,
)


def _load_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, value = raw.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
    except Exception:
        return


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


LOG_PATH = os.getenv("REQUEST_LOG", "request.log")
LOG_STDOUT = os.getenv("REQUEST_LOG_STDOUT", "1") not in ("0", "false", "False")


class Handler(BaseHTTPRequestHandler):
    @staticmethod
    def _record_request(path: str, client_ip: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        line = f"{ts}\t{client_ip}\t{path}\n"
        if LOG_STDOUT:
            print(line.rstrip())
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def do_GET(self) -> None:
        self._record_request(self.path, self.client_address[0])
        if self.path == "/health":
            _send_json(self, 200, {"ok": True})
        else:
            _send_json(self, 404, {"error": "not_found"})

    def do_POST(self) -> None:
        self._record_request(self.path, self.client_address[0])
        if self.path not in ("/analyze", "/recommend"):
            _send_json(self, 404, {"error": "not_found"})
            return

        if self.path == "/recommend":
            data = _read_json(self)
            keywords = data.get("keywords")

            if not isinstance(keywords, list) or len(keywords) != 5:
                _send_json(self, 400, {"error": "keywords_must_be_array_of_5"})
                return
            if not all(isinstance(x, str) for x in keywords):
                _send_json(self, 400, {"error": "keywords_items_must_be_strings"})
                return

            user_normalized = extract_user_tags([k.strip() for k in keywords])
            db_name = os.getenv("MYSQL_DB", "")
            if not db_name:
                _send_json(
                    self,
                    200,
                    {
                        "normalized_user": user_normalized,
                        "top5": [],
                        "fallback": "MYSQL_DB not set. Returned normalized user tags only.",
                    },
                )
                return

            class _Args:
                db_host = os.getenv("MYSQL_HOST", "127.0.0.1")
                db_port = int(os.getenv("MYSQL_PORT", "3306"))
                db_user = os.getenv("MYSQL_USER", "root")
                db_password = os.getenv("MYSQL_PASSWORD", "")
                db_name = db_name
                keyword_table = os.getenv("MYSQL_KEYWORD_TABLE", "keyword")

            try:
                conn = build_db_connection(_Args)
                try:
                    actual_keyword_table = resolve_keyword_table(conn, _Args.keyword_table)
                    rows = fetch_mentors_from_mysql(conn, actual_keyword_table)
                    mentors = build_mentor_models(rows)
                    ranked_full = recommend_top_n(
                        user_topics=set(user_normalized["topics"]),
                        user_stacks=set(user_normalized["stacks"]),
                        mentors=mentors,
                        n=5,
                    )
                    payload = {
                        "normalized_user": user_normalized,
                        "top5": simplify_top_n(ranked_full),
                        "fallback": None,
                    }
                finally:
                    conn.close()
            except Exception as exc:
                _send_json(self, 500, {"error": f"recommend_failed: {exc}"})
                return

            _send_json(self, 200, payload)
            return

        data = _read_json(self)
        text = (data.get("text") or "").strip()

        if not text:
            _send_json(self, 400, {"error": "text_required"})
            return

        try:
            safe_text = mask_pii(text)
            result = analyze_with_gemini(
                portfolio_text=safe_text,
                target_role="Backend",
                model="gemini-3-flash-preview",
            )
        except SystemExit as exc:
            _send_json(self, 500, {"error": str(exc)})
            return
        except Exception as exc:
            _send_json(self, 500, {"error": f"analysis_failed: {exc}"})
            return

        _send_json(self, 200, {"keywords": result.keywords})

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    _load_env()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Server listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
