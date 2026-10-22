"""Runtime state storage: everything the app creates while people use it.

  requests        service requests raised through the companion
  cases           human handoffs and early warnings (named owner, HRBP, shared items, notes)
  consent_events  every consent change (append-only); current consent = latest event
  audit_log       append-only access and action log
  notifications   updates shown to the employee
  conversations   companion chat history, grouped into threads (employee can delete)
  threads         the employee's conversations: title and start time (max 10 kept, 90-day retention)
  priority        priority overrides on pack requests
  flags           one-off markers (e.g. early warnings seeded)

The synthetic data pack itself is read-only and is never written here.

Backends: PgStore (PostgreSQL, used when DATABASE_URL is set, e.g. Render Postgres or Azure
Database for PostgreSQL in a pilot) and JsonStore (single file, for local runs and tests).
Both expose the same methods; nothing else in the app touches storage directly.
"""
import contextlib
import datetime as dt
import json
import threading
import uuid

from . import config

_lock = threading.RLock()


class BaseStore:
    kind = "base"

    @staticmethod
    def now_iso():
        t = dt.datetime.combine(config.AS_OF, dt.datetime.now().time()).replace(microsecond=0)
        return t.isoformat() + "+04:00"

    @staticmethod
    def new_id(prefix):
        return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"

    def audit(self, actor, action, employee_id, detail):
        self._audit({"at": self.now_iso(), "actor": actor, "action": action, "employee_id": employee_id, "detail": detail})

    # Completions recorded by a named owner when they resolve a case (WFL-CS-04). Stored as flags so both
    # stores need no new table: "done|EMP|STEP|date" and "reqdone|SR-ID|date". Cached briefly; reset clears them.
    _comp = None

    def add_completion(self, employee_id, step_code, date, request_id=None):
        self.flag_set(f"done|{employee_id}|{step_code}|{date}")
        if request_id:
            self.flag_set(f"reqdone|{request_id}|{date}")
        self._comp = None

    def completions(self):
        import time
        if self._comp and time.time() - self._comp[0] < 3:
            return self._comp[1]
        steps, reqs = {}, {}
        for k in self._flag_keys():
            parts = k.split("|")
            if parts[0] == "done" and len(parts) == 4:
                steps[(parts[1], parts[2])] = parts[3]
            elif parts[0] == "reqdone" and len(parts) == 3:
                reqs[parts[1]] = parts[2]
        self._comp = (time.time(), {"steps": steps, "requests": reqs})
        return self._comp[1]

    def notify(self, employee_id, text, text_ar=None, kind="info", ref=None):
        self._notify({"id": self.new_id("NTF"), "at": self.now_iso(), "employee_id": employee_id, "text": text,
                      "text_ar": text_ar or text, "kind": kind, "ref": ref})


# ----------------------------------------------------------------------------------------------
class JsonStore(BaseStore):
    kind = "json"

    def __init__(self):
        self.path = config.RUNTIME_DIR / "state.json"
        self.data = None
        self._load()

    def _empty(self):
        return {"requests": [], "cases": [], "consent_events": [], "audit": [], "notifications": [],
                "conversations": [], "threads": [], "priority": {}, "flags": {}}

    def _load(self):
        with _lock:
            self.data = self._empty()
            if self.path.exists():
                try:
                    saved = json.loads(self.path.read_text(encoding="utf-8"))
                    if "consent_events" in saved:
                        self.data.update(saved)
                except (json.JSONDecodeError, OSError):
                    pass
            self._save()

    def _save(self):
        config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def _append(self, key, row):
        with _lock:
            self.data[key].append(row)
            self._save()

    def reset(self):
        self._comp = None
        with _lock:
            self.data = self._empty()
            self._save()

    def health(self):
        return {"storage": "json", "ok": True}

    @contextlib.contextmanager
    def seed_lock(self):
        with _lock:
            yield

    # audit / notifications
    def _audit(self, row): self._append("audit", row)
    def _notify(self, row): self._append("notifications", row)

    def audit_for(self, employee_id, limit=20):
        return [a for a in self.data["audit"] if a["employee_id"] == employee_id][-limit:][::-1]

    def notifications(self, employee_id, limit=30):
        return [n for n in self.data["notifications"] if n["employee_id"] == employee_id][-limit:][::-1]

    # requests
    def add_request(self, req): self._append("requests", req)

    def requests_for(self, employee_id):
        return [dict(r) for r in self.data["requests"] if r["employee_id"] == employee_id]

    def set_priority(self, request_id, priority):
        with _lock:
            self.data["priority"][request_id] = priority
            for r in self.data["requests"]:
                if r["request_id"] == request_id:
                    r["priority"] = priority
            self._save()

    def priority_for(self, request_id):
        return self.data["priority"].get(request_id)

    # cases
    def add_case(self, case): self._append("cases", case)

    def cases(self, employee_id=None, hrbp_id=None, owner_name=None):
        out = self.data["cases"]
        if employee_id:
            out = [c for c in out if c["employee_id"] == employee_id]
        if hrbp_id:
            out = [c for c in out if c["hrbp"]["id"] == hrbp_id]
        if owner_name:
            out = [c for c in out if c["owner"]["name"] == owner_name]
        return [json.loads(json.dumps(c)) for c in out]

    def get_case(self, case_id):
        return next((json.loads(json.dumps(c)) for c in self.data["cases"] if c["case_id"] == case_id), None)

    def save_case(self, case):
        with _lock:
            for i, c in enumerate(self.data["cases"]):
                if c["case_id"] == case["case_id"]:
                    self.data["cases"][i] = case
            self._save()

    # consent
    def consent_set(self, employee_id, status, by):
        self._append("consent_events", {"at": self.now_iso(), "employee_id": employee_id, "status": status, "by": by})

    def consent_get(self, employee_id):
        ev = [c for c in self.data["consent_events"] if c["employee_id"] == employee_id]
        return ev[-1]["status"] if ev else None

    def consent_log(self, employee_id):
        return [c for c in self.data["consent_events"] if c["employee_id"] == employee_id]

    # conversations
    def conv_append(self, employee_id, role, text, thread_id=None, meta=None):
        self._append("conversations", {"at": self.now_iso(), "employee_id": employee_id, "role": role, "text": text,
                                       "thread_id": thread_id, "meta": meta})

    def conv_recent(self, employee_id, n=6, thread_id=None):
        return [c for c in self.data["conversations"] if c["employee_id"] == employee_id
                and (thread_id is None or c.get("thread_id") == thread_id)][-n:]

    def conv_count(self, employee_id):
        return sum(1 for c in self.data["conversations"] if c["employee_id"] == employee_id)

    def conv_delete(self, employee_id):
        with _lock:
            self.data["conversations"] = [c for c in self.data["conversations"] if c["employee_id"] != employee_id]
            self.data["threads"] = [t for t in self.data.get("threads", []) if t["employee_id"] != employee_id]
            self._save()

    # threads
    def thread_create(self, employee_id, title):
        t = {"id": self.new_id("THR"), "employee_id": employee_id, "title": title[:80], "created_at": self.now_iso()}
        self._append("threads", t)
        self._prune_threads(employee_id)
        return t["id"]

    def threads(self, employee_id):
        self._adopt_legacy(employee_id)
        conv = self.data["conversations"]
        out = []
        for t in self.data.get("threads", []):
            if t["employee_id"] != employee_id:
                continue
            idx = [i for i, c in enumerate(conv) if c.get("thread_id") == t["id"]]
            out.append({**t, "messages": len(idx), "last_at": conv[idx[-1]]["at"] if idx else t["created_at"],
                        "_order": idx[-1] if idx else -1})
        out.sort(key=lambda x: x["_order"], reverse=True)
        for o in out:
            o.pop("_order")
        return out

    def thread_get(self, employee_id, thread_id):
        return next((t for t in self.data.get("threads", []) if t["id"] == thread_id and t["employee_id"] == employee_id), None)

    def thread_messages(self, employee_id, thread_id):
        return [c for c in self.data["conversations"] if c["employee_id"] == employee_id and c.get("thread_id") == thread_id]

    def thread_delete(self, employee_id, thread_id):
        with _lock:
            self.data["threads"] = [t for t in self.data.get("threads", []) if not (t["id"] == thread_id and t["employee_id"] == employee_id)]
            self.data["conversations"] = [c for c in self.data["conversations"]
                                          if not (c["employee_id"] == employee_id and c.get("thread_id") == thread_id)]
            self._save()

    def _adopt_legacy(self, employee_id):
        """Messages saved before threads existed become one 'Earlier conversation'."""
        legacy = [c for c in self.data["conversations"] if c["employee_id"] == employee_id and not c.get("thread_id")]
        if legacy:
            tid = self.thread_create(employee_id, "Earlier conversation")
            with _lock:
                for c in legacy:
                    c["thread_id"] = tid
                self._save()

    def _prune_threads(self, employee_id):
        keep = {t["id"] for t in self.threads_raw_order(employee_id)[:THREAD_LIMIT]}
        cutoff = (config.AS_OF - dt.timedelta(days=RETENTION_DAYS)).isoformat()
        for t in list(self.data.get("threads", [])):
            if t["employee_id"] == employee_id and (t["id"] not in keep or t["created_at"][:10] < cutoff):
                self.thread_delete(employee_id, t["id"])

    def threads_raw_order(self, employee_id):
        conv = self.data["conversations"]
        ts = [t for t in self.data.get("threads", []) if t["employee_id"] == employee_id]
        last = {t["id"]: max([i for i, c in enumerate(conv) if c.get("thread_id") == t["id"]], default=10**9) for t in ts}
        return sorted(ts, key=lambda t: last[t["id"]], reverse=True)

    # flags
    def flag_get(self, key):
        return bool(self.data["flags"].get(key))

    def _flag_keys(self):
        return [k for k in self.data["flags"] if "|" in k]

    def flag_set(self, key):
        with _lock:
            self.data["flags"][key] = True
            self._save()


# ----------------------------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
  request_id   TEXT PRIMARY KEY,
  employee_id  TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  doc          JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS requests_employee ON requests (employee_id);

CREATE TABLE IF NOT EXISTS request_priority (
  request_id   TEXT PRIMARY KEY,
  priority     TEXT NOT NULL,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cases (
  case_id      TEXT PRIMARY KEY,
  employee_id  TEXT NOT NULL,
  hrbp_id      TEXT NOT NULL,
  owner_name   TEXT NOT NULL,
  case_type    TEXT NOT NULL,
  status       TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  doc          JSONB NOT NULL,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cases_employee ON cases (employee_id);
CREATE INDEX IF NOT EXISTS cases_hrbp ON cases (hrbp_id);
CREATE INDEX IF NOT EXISTS cases_owner ON cases (owner_name);

CREATE TABLE IF NOT EXISTS consent_events (
  id           BIGSERIAL PRIMARY KEY,
  employee_id  TEXT NOT NULL,
  status       TEXT NOT NULL CHECK (status IN ('ACTIVE', 'WITHDRAWN')),
  changed_by   TEXT NOT NULL,
  at           TEXT NOT NULL,
  recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS consent_employee ON consent_events (employee_id, id);

CREATE TABLE IF NOT EXISTS audit_log (
  id           BIGSERIAL PRIMARY KEY,
  at           TEXT NOT NULL,
  actor        TEXT NOT NULL,
  action       TEXT NOT NULL,
  employee_id  TEXT NOT NULL,
  detail       TEXT NOT NULL,
  recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_employee ON audit_log (employee_id, id);

CREATE TABLE IF NOT EXISTS notifications (
  id           TEXT PRIMARY KEY,
  seq          BIGSERIAL,
  employee_id  TEXT NOT NULL,
  at           TEXT NOT NULL,
  doc          JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS notifications_employee ON notifications (employee_id, seq);

CREATE TABLE IF NOT EXISTS conversations (
  id           BIGSERIAL PRIMARY KEY,
  employee_id  TEXT NOT NULL,
  role         TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  text         TEXT NOT NULL,
  at           TEXT NOT NULL,
  recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS conversations_employee ON conversations (employee_id, id);
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS thread_id TEXT;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS meta JSONB;
CREATE INDEX IF NOT EXISTS conversations_thread ON conversations (thread_id, id);

CREATE TABLE IF NOT EXISTS threads (
  id           TEXT PRIMARY KEY,
  employee_id  TEXT NOT NULL,
  title        TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  seq          BIGSERIAL
);
CREATE INDEX IF NOT EXISTS threads_employee ON threads (employee_id);

CREATE TABLE IF NOT EXISTS flags (
  key          TEXT PRIMARY KEY,
  set_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

TABLES = ["requests", "request_priority", "cases", "consent_events", "audit_log", "notifications", "conversations", "threads", "flags"]
SEED_LOCK_ID = 7_331_842
THREAD_LIMIT = 10        # conversations kept per employee (oldest removed first)
RETENTION_DAYS = 90      # conversations older than this are removed (POL-PRV-001 §8.1)  # pg advisory lock: only one instance seeds early warnings


class PgStore(BaseStore):
    kind = "postgres"

    def __init__(self, url):
        from psycopg.types.json import Jsonb
        from psycopg_pool import ConnectionPool
        self.Jsonb = Jsonb
        self.pool = ConnectionPool(url, min_size=1, max_size=int(config.DB_POOL_SIZE), open=True,
                                   kwargs={"autocommit": True}, timeout=15)
        with self.pool.connection() as c:
            c.execute(SCHEMA)

    def _x(self, sql, args=()):
        with self.pool.connection() as c:
            return c.execute(sql, args)

    def _all(self, sql, args=()):
        with self.pool.connection() as c:
            return c.execute(sql, args).fetchall()

    def _one(self, sql, args=()):
        with self.pool.connection() as c:
            return c.execute(sql, args).fetchone()

    def reset(self):
        self._comp = None
        self._x("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY")

    def health(self):
        try:
            self._one("SELECT 1")
            return {"storage": "postgres", "ok": True}
        except Exception as exc:  # noqa: BLE001
            return {"storage": "postgres", "ok": False, "error": type(exc).__name__}

    @contextlib.contextmanager
    def seed_lock(self):
        with self.pool.connection() as c:
            c.execute("SELECT pg_advisory_lock(%s)", (SEED_LOCK_ID,))
            try:
                yield
            finally:
                c.execute("SELECT pg_advisory_unlock(%s)", (SEED_LOCK_ID,))

    # audit / notifications
    def _audit(self, r):
        self._x("INSERT INTO audit_log (at, actor, action, employee_id, detail) VALUES (%s,%s,%s,%s,%s)",
                (r["at"], r["actor"], r["action"], r["employee_id"], r["detail"]))

    def _notify(self, r):
        self._x("INSERT INTO notifications (id, employee_id, at, doc) VALUES (%s,%s,%s,%s)",
                (r["id"], r["employee_id"], r["at"], self.Jsonb(r)))

    def audit_for(self, employee_id, limit=20):
        rows = self._all("SELECT at, actor, action, employee_id, detail FROM audit_log WHERE employee_id=%s "
                         "ORDER BY id DESC LIMIT %s", (employee_id, limit))
        return [dict(zip(("at", "actor", "action", "employee_id", "detail"), r)) for r in rows]

    def notifications(self, employee_id, limit=30):
        return [r[0] for r in self._all("SELECT doc FROM notifications WHERE employee_id=%s ORDER BY seq DESC LIMIT %s",
                                        (employee_id, limit))]

    # requests
    def add_request(self, req):
        self._x("INSERT INTO requests (request_id, employee_id, created_at, doc) VALUES (%s,%s,%s,%s)",
                (req["request_id"], req["employee_id"], req["created_at"], self.Jsonb(req)))

    def requests_for(self, employee_id):
        rows = self._all("SELECT doc FROM requests WHERE employee_id=%s ORDER BY created_at", (employee_id,))
        out = []
        for (doc,) in rows:
            p = self.priority_for(doc["request_id"])
            out.append({**doc, "priority": p or doc.get("priority")})
        return out

    def set_priority(self, request_id, priority):
        self._x("INSERT INTO request_priority (request_id, priority) VALUES (%s,%s) "
                "ON CONFLICT (request_id) DO UPDATE SET priority=EXCLUDED.priority, updated_at=now()", (request_id, priority))

    def priority_for(self, request_id):
        r = self._one("SELECT priority FROM request_priority WHERE request_id=%s", (request_id,))
        return r[0] if r else None

    # cases
    def add_case(self, case):
        self._x("INSERT INTO cases (case_id, employee_id, hrbp_id, owner_name, case_type, status, created_at, doc) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (case["case_id"], case["employee_id"], case["hrbp"]["id"], case["owner"]["name"], case["type"],
                 case["status"], case["created_at"], self.Jsonb(case)))

    def cases(self, employee_id=None, hrbp_id=None, owner_name=None):
        where, args = [], []
        for col, val in (("employee_id", employee_id), ("hrbp_id", hrbp_id), ("owner_name", owner_name)):
            if val:
                where.append(f"{col}=%s")
                args.append(val)
        sql = "SELECT doc FROM cases" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY created_at, case_id"
        return [r[0] for r in self._all(sql, args)]

    def get_case(self, case_id):
        r = self._one("SELECT doc FROM cases WHERE case_id=%s", (case_id,))
        return r[0] if r else None

    def save_case(self, case):
        self._x("UPDATE cases SET status=%s, case_type=%s, doc=%s, updated_at=now() WHERE case_id=%s",
                (case["status"], case["type"], self.Jsonb(case), case["case_id"]))

    # consent
    def consent_set(self, employee_id, status, by):
        self._x("INSERT INTO consent_events (employee_id, status, changed_by, at) VALUES (%s,%s,%s,%s)",
                (employee_id, status, by, self.now_iso()))

    def consent_get(self, employee_id):
        r = self._one("SELECT status FROM consent_events WHERE employee_id=%s ORDER BY id DESC LIMIT 1", (employee_id,))
        return r[0] if r else None

    def consent_log(self, employee_id):
        rows = self._all("SELECT at, employee_id, status, changed_by FROM consent_events WHERE employee_id=%s ORDER BY id",
                         (employee_id,))
        return [dict(zip(("at", "employee_id", "status", "by"), r)) for r in rows]

    # conversations
    def conv_append(self, employee_id, role, text, thread_id=None, meta=None):
        self._x("INSERT INTO conversations (employee_id, role, text, at, thread_id, meta) VALUES (%s,%s,%s,%s,%s,%s)",
                (employee_id, role, text, self.now_iso(), thread_id, self.Jsonb(meta) if meta is not None else None))

    def conv_recent(self, employee_id, n=6, thread_id=None):
        if thread_id is None:
            rows = self._all("SELECT at, role, text FROM conversations WHERE employee_id=%s ORDER BY id DESC LIMIT %s",
                             (employee_id, n))
        else:
            rows = self._all("SELECT at, role, text FROM conversations WHERE employee_id=%s AND thread_id=%s ORDER BY id DESC LIMIT %s",
                             (employee_id, thread_id, n))
        return [dict(zip(("at", "role", "text"), r)) for r in reversed(rows)]

    def conv_count(self, employee_id):
        return self._one("SELECT count(*) FROM conversations WHERE employee_id=%s", (employee_id,))[0]

    def conv_delete(self, employee_id):
        self._x("DELETE FROM conversations WHERE employee_id=%s", (employee_id,))
        self._x("DELETE FROM threads WHERE employee_id=%s", (employee_id,))

    # threads
    def thread_create(self, employee_id, title):
        tid = self.new_id("THR")
        self._x("INSERT INTO threads (id, employee_id, title, created_at) VALUES (%s,%s,%s,%s)",
                (tid, employee_id, title[:80], self.now_iso()))
        self._prune_threads(employee_id)
        return tid

    def threads(self, employee_id):
        self._adopt_legacy(employee_id)
        rows = self._all("""SELECT t.id, t.title, t.created_at, count(c.id), max(c.at), coalesce(max(c.id), 0) AS last_id, t.seq
                            FROM threads t LEFT JOIN conversations c ON c.thread_id = t.id
                            WHERE t.employee_id=%s GROUP BY t.id ORDER BY last_id DESC, t.seq DESC""", (employee_id,))
        return [{"id": r[0], "employee_id": employee_id, "title": r[1], "created_at": r[2], "messages": r[3],
                 "last_at": r[4] or r[2]} for r in rows]

    def thread_get(self, employee_id, thread_id):
        r = self._one("SELECT id, title, created_at FROM threads WHERE id=%s AND employee_id=%s", (thread_id, employee_id))
        return {"id": r[0], "employee_id": employee_id, "title": r[1], "created_at": r[2]} if r else None

    def thread_messages(self, employee_id, thread_id):
        rows = self._all("SELECT at, role, text, meta FROM conversations WHERE employee_id=%s AND thread_id=%s ORDER BY id",
                         (employee_id, thread_id))
        return [{"at": r[0], "role": r[1], "text": r[2], "meta": r[3], "thread_id": thread_id} for r in rows]

    def thread_delete(self, employee_id, thread_id):
        self._x("DELETE FROM conversations WHERE employee_id=%s AND thread_id=%s", (employee_id, thread_id))
        self._x("DELETE FROM threads WHERE employee_id=%s AND id=%s", (employee_id, thread_id))

    def _adopt_legacy(self, employee_id):
        if self._one("SELECT 1 FROM conversations WHERE employee_id=%s AND thread_id IS NULL LIMIT 1", (employee_id,)):
            tid = self.new_id("THR")
            self._x("INSERT INTO threads (id, employee_id, title, created_at) VALUES (%s,%s,%s,%s)",
                    (tid, employee_id, "Earlier conversation", self.now_iso()))
            self._x("UPDATE conversations SET thread_id=%s WHERE employee_id=%s AND thread_id IS NULL", (tid, employee_id))

    def _prune_threads(self, employee_id):
        cutoff = (config.AS_OF - dt.timedelta(days=RETENTION_DAYS)).isoformat()
        rows = self._all("""SELECT t.id, t.created_at FROM threads t LEFT JOIN conversations c ON c.thread_id = t.id
                            WHERE t.employee_id=%s GROUP BY t.id ORDER BY coalesce(max(c.id), 9e18) DESC, t.seq DESC""", (employee_id,))
        for k, (tid, created) in enumerate(rows):
            if k >= THREAD_LIMIT or created[:10] < cutoff:
                self.thread_delete(employee_id, tid)

    # flags
    def flag_get(self, key):
        return self._one("SELECT 1 FROM flags WHERE key=%s", (key,)) is not None

    def _flag_keys(self):
        return [r[0] for r in self._all("SELECT key FROM flags WHERE key LIKE %s", ("%|%",))]

    def flag_set(self, key):
        self._x("INSERT INTO flags (key) VALUES (%s) ON CONFLICT DO NOTHING", (key,))


def make_store():
    if config.DATABASE_URL:
        return PgStore(config.DATABASE_URL)
    return JsonStore()
