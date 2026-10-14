"""Policy library: section-level chunks with stable citations ("POL-IT-001 §5.1") and BM25 search.

Runs fully locally (no embeddings service), so policy text never leaves the deployment.
Arabic queries are mapped to English search terms with a small glossary; in LLM mode the model
also answers in Arabic from the same cited English sections.
"""
import math
import re
from collections import Counter

from . import config

SEC_RE = re.compile(r"^##\s+(\d+)\.\s+(.*)$")
SUB_RE = re.compile(r"^(\d+\.\d+)\s+(.*)$")
TOKEN_RE = re.compile(r"[a-z0-9]+")

STOP = set("""a an the of to and or for in on at by with is are be was were it its this that you your
i me my we our us can do does did will would should could may might what when where who how which if
from as not no yes there their they them about into than then so up out any all have has had get""".split())

SYNONYMS = {
    "laptop": ["equipment", "device", "kit"], "computer": ["laptop", "equipment"], "phone": ["equipment", "mobile"],
    "login": ["access", "account"], "log": ["access"], "password": ["access", "security"], "email": ["access"],
    "visa": ["permit", "sponsorship"], "medical": ["fitness", "test"], "permit": ["visa", "work"],
    "flat": ["accommodation", "housing"], "apartment": ["accommodation", "housing"], "room": ["accommodation"],
    "house": ["housing", "accommodation"], "housing": ["accommodation", "allowance"], "rent": ["housing", "allowance"],
    "money": ["allowance", "payment"], "paid": ["payment", "allowance"], "pay": ["payment", "covered"],
    "relocation": ["relocate", "move"], "move": ["transfer", "relocation"], "transfer": ["move"],
    "flight": ["ticket", "travel"], "ticket": ["flight", "travel"], "luggage": ["baggage"], "bags": ["baggage"],
    "training": ["induction", "course"], "course": ["training"], "badge": ["staff", "id", "pass"],
    "card": ["id", "pass"], "buddy": ["onboarding", "contact"], "manager": ["line"],
    "privacy": ["data", "consent"], "feedback": ["pulse", "consent"], "survey": ["pulse"],
    "probation": ["objectives", "review"], "escalate": ["escalation"], "complaint": ["escalation", "hrbp"],
    "id": ["emirates", "staff"],
    "family": ["dependant", "sponsored"], "spouse": ["dependant"], "wife": ["dependant"], "husband": ["dependant"],
    "children": ["dependant", "schooling"], "kids": ["dependant", "schooling"], "school": ["schooling"],
}

# Arabic -> English search terms (glossary for offline mode)
AR_GLOSSARY = {
    "بدل": "allowance", "السكن": "housing accommodation", "سكن": "housing accommodation", "تأشيرة": "visa",
    "التأشيرة": "visa", "فحص": "medical test", "الطبي": "medical", "طبي": "medical", "الهوية": "emirates id",
    "حاسوب": "laptop equipment", "الحاسوب": "laptop equipment", "لابتوب": "laptop", "جهاز": "device equipment",
    "تدريب": "training", "التدريب": "training", "التعريف": "induction", "انتقال": "transfer move relocation",
    "الانتقال": "transfer move relocation", "راتب": "salary", "الراتب": "salary", "تذكرة": "ticket flight",
    "مدير": "manager", "مديري": "manager", "التجربة": "probation", "بيانات": "data privacy", "بياناتي": "data privacy",
    "صلاحيات": "access", "دخول": "access login", "بطاقة": "id card pass", "رفيق": "buddy", "زميل": "buddy",
    "مرافق": "buddy", "تصريح": "permit", "عمل": "work", "مواصلات": "transport", "النقل": "transport",
    "متى": "when", "كم": "amount", "موعد": "date",
}


def tokenize(text):
    toks = []
    for t in TOKEN_RE.findall(text.lower()):
        if t in STOP:
            continue
        if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        toks.append(t)
    return toks


def arabic_to_query(text):
    terms = []
    for word in re.findall(r"[؀-ۿ]+", text):
        for key, val in AR_GLOSSARY.items():
            if key in word:
                terms.append(val)
    return " ".join(terms)


def has_arabic(text):
    return bool(re.search(r"[؀-ۿ]", text))


class PolicyLibrary:
    def __init__(self):
        self.sections = []      # dict(cite, policy_id, title, heading, text)
        self.policies = {}      # policy_id -> {title, version, owner}
        for path in sorted((config.DATA_DIR / "policies").glob("*.md")):
            self._load(path)
        self._index()

    def _load(self, path):
        raw = path.read_text(encoding="utf-8")
        meta, body = {}, raw
        if raw.startswith("---"):
            _, fm, body = raw.split("---", 2)
            for line in fm.strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
        pid = meta.get("policy_id", path.stem.split("_")[0])
        self.policies[pid] = {"policy_id": pid, "title": meta.get("title", pid), "version": meta.get("version", ""),
                              "owner": meta.get("owner", ""), "file": path.name}
        heading, sec_no, table = "", "", []
        for line in body.splitlines():
            line = line.rstrip()
            m = SEC_RE.match(line)
            if m:
                self._flush_table(pid, heading, sec_no, table)
                table = []
                sec_no, heading = m.group(1), m.group(2)
                continue
            m = SUB_RE.match(line)
            if m and sec_no:
                self.sections.append(dict(cite=f"{pid} §{m.group(1)}", policy_id=pid,
                                          title=self.policies[pid]["title"], heading=heading, text=m.group(2)))
            elif line.startswith("|") and sec_no:
                table.append(line)
        self._flush_table(pid, heading, sec_no, table)

    def _flush_table(self, pid, heading, sec_no, table):
        rows = [r for r in table if not re.match(r"^\|\s*-", r)]
        if len(rows) > 1:
            text = "; ".join(" ".join(c.strip() for c in r.strip("|").split("|")) for r in rows[1:])
            self.sections.append(dict(cite=f"{pid} §{sec_no}", policy_id=pid,
                                      title=self.policies[pid]["title"], heading=heading, text=text))

    def _index(self):
        self.docs = [tokenize(f"{s['title']} {s['heading']} {s['heading']} {s['text']}") for s in self.sections]
        self.avgdl = sum(len(d) for d in self.docs) / max(1, len(self.docs))
        df = Counter()
        for d in self.docs:
            df.update(set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.tf = [Counter(d) for d in self.docs]
        self.by_cite = {s["cite"]: s for s in self.sections}

    def get(self, cite):
        return self.by_cite.get(cite)

    def search(self, query, k=4, boost=None):
        if has_arabic(query):
            query = query + " " + arabic_to_query(query)
        q = tokenize(query)
        expanded = list(q)
        for t in q:
            expanded += SYNONYMS.get(t, [])
        scores = []
        k1, b = 1.4, 0.75
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i])
            s = 0.0
            for t in expanded:
                if t in tf:
                    w = 1.0 if t in q else 0.5
                    s += w * self.idf.get(t, 0) * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * dl / self.avgdl))
            if boost and self.sections[i]["cite"] in boost:
                s *= 1.35
            if s > 0:
                scores.append((s, i))
        scores.sort(reverse=True)
        out = []
        for s, i in scores[:k]:
            sec = dict(self.sections[i])
            sec["score"] = round(s, 2)
            out.append(sec)
        return out


library = PolicyLibrary()
