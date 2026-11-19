"""Connection-independent question state for the compatibility prototype.

SQLite serializes answer/timeout/cancellation races. Transport leases never count
as answers. This module deliberately cannot execute workflow actions or approve
gates: a receipt describes answers to immutable snapshots, not permission to read
and act on mutable files later. Production action guards are a separate live-
checkpoint-gated integration step.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import unicodedata
import uuid

from .errors import QuestionError
from . import projection, selection


WAITING_STATES = ("awaiting-chat-answer", "deferred")  # answerable at the prompt
RETIRED_NOTICE_SECONDS = 86400  # how long outstanding() reports a voided question
MAX_EVENTS = 400  # diagnostic history only; answers/receipts live outside it


def load(text):
    """Decode a stored occurrence; damaged state is an error, never an answer."""
    try:
        body = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise QuestionError("question state is corrupt") from exc
    if not isinstance(body, dict) or body.get("schema") != 1 or not isinstance(body.get("answers"), dict):
        raise QuestionError("question state is corrupt")
    return body


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def tree_entry(listing, path):
    """"<mode> <type> <object id>" from `git ls-tree -z <tree> -- <path>`, or
    None when the tree holds nothing at exactly that path."""
    for record in (listing or b"").split(b"\0"):
        head, _, name = record.partition(b"\t")
        if name == os.fsencode(path):
            return head.decode()
    return None


def token(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise QuestionError(f"invalid {name}")
    return value


def validate_questions(questions):
    if not isinstance(questions, list) or not 1 <= len(questions) <= 100:
        raise QuestionError("expected 1..100 questions")
    ids = set()
    for q in questions:
        if not isinstance(q, dict) or set(q) - {"id", "text", "kind", "options", "page_size",
                                               "min_selected", "max_selected", "allow_early_finish"}:
            raise QuestionError("invalid question fields")
        qid = token(q.get("id"), "question id")
        if qid in ids:
            raise QuestionError("duplicate question id")
        ids.add(qid)
        if not isinstance(q.get("text"), str) or not 1 <= len(q["text"].strip()) <= 20000:
            raise QuestionError("invalid question text")
        if q.get("kind") not in {"choice", "text", "multi"}:
            raise QuestionError("unsupported_shape: expected choice, text or multi")
        if q["kind"] != "multi" and set(q) & {"page_size", "min_selected", "max_selected", "allow_early_finish"}:
            raise QuestionError("selection fields require multi kind")
        options = q.get("options", [])
        if not isinstance(options, list) or len(options) > 500:
            raise QuestionError("invalid options")
        if (q["kind"] in {"choice", "multi"} and not options) or (q["kind"] == "text" and options):
            raise QuestionError("options do not match question kind")
        seen = set()
        for o in options:
            if not isinstance(o, dict) or set(o) != {"id", "label", "description"}:
                raise QuestionError("option requires id, label, description")
            oid = token(o["id"], "option id")
            token(o["label"], "option label")
            if oid in seen or not isinstance(o["description"], str) or len(o["description"]) > 2000:
                raise QuestionError("duplicate option id or invalid description")
            seen.add(oid)
        if q["kind"] == "multi":
            selection.validate_shape(q)


# Matching a choice typed at the chat prompt (codex_prompt_model_forwarded).
# A fuzzy acceptance is consent read from heuristic evidence, so every rule
# below errs towards refusing: the question then stays pending and the user is
# shown the labels to answer with.
MIN_PREFIX = 3                    # an abbreviated word keeps at least 3 letters
TYPO_BUDGET = ((8, 2), (4, 1))    # (shorter word length >=, edits allowed)
FILLER = frozenset({"a", "an", "the", "and", "to", "of"})  # may be left out of a label
HEDGE_WORDS = frozenset({"not", "no", "never", "without", "instead", "but", "or", "nor",
                         "except", "unless", "neither", "maybe", "later", "dont", "cant",
                         "wont"})
_QUOTES = "\"'`“”‘’"
REASON_LABELS = 20                # labels listed in a refusal reason


def _normalize(text):
    """Case, spacing, `_`/`-`, surrounding quotes and trailing .!, removed."""
    text = text.strip()
    while True:
        trimmed = text.strip(_QUOTES).strip().rstrip(".!,").strip()
        if trimmed == text:
            break
        text = trimmed
    return " ".join(text.casefold().replace("_", " ").replace("-", " ").split())


def _osa(a, b, limit):
    """Optimal string alignment distance (insert, delete, substitute, swap), or
    limit + 1 once it exceeds limit. Only cells within `limit` of the diagonal
    are computed, so the cost is linear in the word length."""
    over = limit + 1
    if abs(len(a) - len(b)) > limit:
        return over
    width = len(b) + 1
    before = None                                   # row i - 2
    prev = [j if j <= limit else over for j in range(width)]  # row 0
    for i in range(1, len(a) + 1):
        row = [over] * width
        if i <= limit:
            row[0] = i
        for j in range(max(1, i - limit), min(len(b), i + limit) + 1):
            cell = min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cell = min(cell, before[j - 2] + 1)
            row[j] = min(cell, over)
        if min(row) > limit:
            return over
        before, prev = prev, row
    return prev[-1]


def _word_match(reply, word):
    """Edits needed for one reply word to stand for one label word, or None."""
    if reply == word or (len(reply) >= MIN_PREFIX and word.startswith(reply)):
        return 0
    shorter = min(len(reply), len(word))
    budget = next((edits for size, edits in TYPO_BUDGET if shorter >= size), 0)
    # The distance is at least the length difference, so a word that cannot
    # fit the budget never reaches the quadratic _osa (a long paste would
    # otherwise stall the write transaction submit holds).
    if budget and reply[0] == word[0] and abs(len(reply) - len(word)) <= budget:
        edits = _osa(reply, word, budget)
        if edits <= budget:
            return edits
    return None


def _align(reply, label):
    """Fewest edits mapping every reply word, in order and one-to-one, onto the
    label's words, leaving out nothing but FILLER; None when there is no such
    mapping. So a reply can neither add a qualifier nor drop a word that
    decides the action ("approve and" is not "Approve and stop here", "do
    delete branch" is not "Do not delete branch").
    """
    if not reply or len(reply) > len(label):
        return None  # nothing typed, or more words than the label has
    best = {}

    def walk(i, j):
        if (i, j) not in best:
            if i == len(reply):
                result = 0 if all(w in FILLER for w in label[j:]) else None
            elif j == len(label):
                result = None
            else:
                options = []
                edits = _word_match(reply[i], label[j])
                rest = walk(i + 1, j + 1) if edits is not None else None
                if rest is not None:
                    options.append(edits + rest)
                if label[j] in FILLER and (skipped := walk(i, j + 1)) is not None:
                    options.append(skipped)
                result = min(options) if options else None
            best[(i, j)] = result
        return best[(i, j)]

    return walk(0, 0)


def _hedged(text):
    """Not plain words, or a negation or hedge: never read as a fuzzy choice.

    Any punctuation or symbol left after normalization refuses fuzzy matching
    outright. A question mark in any script ("?", "？", "⁇", "‽", …) is
    one of them, and a typo edit must never be what silently deletes it.
    """
    if any(unicodedata.category(ch)[0] in "PS" for ch in text):
        return True
    for word in text.split():
        bare = word.replace("'", "").replace("’", "")
        if bare in HEDGE_WORDS or word.endswith(("n't", "n’t")):
            return True
    return False


def _resolve(options, value):
    """The matching rule itself, without raising: (option, provenance, problem,
    candidates). option is None when the reply picks nothing; problem is then
    "ambiguous choice" (candidates = the options it matched) or
    "unknown choice".

    Tiers, each consulted only when the one before found nothing, and each
    refusing when more than one option matches:
      exact       the id or label as written (today's rule, so it always wins);
      normalized  the id or label up to case, spacing, `_`/`-`, quotes and
                  trailing .!, ;
      fuzzy       the LABEL (never the id — a prefix of an id could bypass a
                  conflicting label), word by word: every reply word abbreviates
                  (>= MIN_PREFIX letters) or slightly mistypes (same first
                  letter, within TYPO_BUDGET) one label word, in order, and
                  every label word except FILLER is covered. Never for a reply
                  holding punctuation or a symbol, a negation or a hedge.
    """
    def tier(found, provenance):
        if len(found) > 1:
            return None, None, "ambiguous choice", found
        if found:
            return found[0], provenance, None, ()
        return None

    raw = value.strip()
    hit = tier([o for o in options if raw in (o["id"], o["label"])], {"match": "exact"})
    if hit:
        return hit
    reply = _normalize(value)
    if not reply:
        # Only punctuation/quotes ("!"): it would equal an empty normalized
        # label and, in fuzzy, omit every word of a label like "A" (filler).
        return None, None, "unknown choice", ()
    hit = tier([o for o in options if reply in (_normalize(o["id"]), _normalize(o["label"]))],
               {"match": "normalized"})
    if hit:
        return hit
    if not _hedged(reply):
        scored = [(o, _align(reply.split(), _normalize(o["label"]).split())) for o in options]
        scored = [(o, edits) for o, edits in scored if edits is not None]
        if scored:
            edits = scored[0][1]
            return tier([o for o, _ in scored],
                        {"match": "fuzzy", "via": "typo" if edits else "prefix", "edits": edits})
    return None, None, "unknown choice", ()


def _choice_names(options, chosen):
    """How to name each chosen option in a reason, at most REASON_LABELS of
    them. A suggested reply is offered only when submitting it verbatim,
    under _resolve, records exactly this option: the label alone when it
    does; else the label plus `(reply "<id>")` when the literal id does; else
    a note that no typed reply can pick it, so the form must be shown again.
    """
    def picks(reply, option):
        return _resolve(options, reply)[0] is option

    names = []
    for o in chosen[:REASON_LABELS]:
        name = json.dumps(o["label"], ensure_ascii=False)
        if not picks(o["label"], o):
            if picks(o["id"], o):
                name += f" (reply {json.dumps(o['id'], ensure_ascii=False)})"
            else:
                name += " (no typed reply selects it; show the form again)"
        names.append(name)
    if len(chosen) > REASON_LABELS:
        names.append(f"… and {len(chosen) - REASON_LABELS} more")
    return names


def _choices_reason(problem, options, candidates=()):
    shown = ", ".join(_choice_names(options, options))
    lead = problem
    if candidates:
        named = _choice_names(options, list(candidates))
        lead += f" (matches {', '.join(named[:-1])} and {named[-1]})"
    return f"{lead}; question remains pending; answer with one of: {shown}"


def match_choice(options, value):
    """The option a prompt answer names: (option, provenance) or QuestionError
    whose reason lists, for every choice, a reply that selects it (_resolve
    holds the rule). The stored answer is always the option id; provenance
    says how it matched.
    """
    option, provenance, problem, candidates = _resolve(options, value)
    if option is None:
        raise QuestionError(_choices_reason(problem, options, candidates))
    return option, provenance


def validate_answer(question, value, source):
    """(stored value, provenance) for an answer, or QuestionError.

    Form input carries stable ids and must name one exactly. A prompt answer
    is matched by match_choice; whatever matched, the option id is stored.
    """
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 20000:
        raise QuestionError("missing or invalid answer")
    if question["kind"] == "text":
        return value, {}
    options = question["options"]
    if source == "mcp_form":
        option = next((o for o in options if value == o["id"]), None)
        if option is None:
            raise QuestionError(_choices_reason("unknown choice", options))
        found = (option, {"match": "exact"})
    else:
        found = match_choice(options, value)
    option, provenance = found
    return option["id"], {"label": option["label"], **provenance}


def resolved(question, record):
    """Which option a stored choice answer recorded, for the agent to echo.

    Built from the question's options and the stored id, so an answer stored
    before `label`/`match` were recorded still resolves; the only thing the
    validator accepted then was a literal id or label, hence "exact".
    """
    option = next((o for o in question["options"] if o["id"] == record["value"]), None)
    if option is None:
        return None
    found = {"question_id": question["id"], "id": option["id"], "label": option["label"],
             "match": record.get("match", "exact")}
    found.update({k: record[k] for k in ("via", "edits") if k in record})
    return found


class Store:
    def __init__(self, directory: Path, project: Path, owner=None):
        self.project = project.resolve(strict=True)
        # The serving process (owner.describe()), stamped on a question that
        # falls back to the prompt so a monitor can tell which pane waits.
        # None for every other user of the store (gate scripts, tests).
        self.owner = owner
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if directory.is_symlink():
            raise QuestionError("state directory must not be a symlink")
        self.db = directory / "questions.sqlite3"
        if self.db.is_symlink():
            raise QuestionError("state database must not be a symlink")
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, "
                         "scope TEXT NOT NULL, opening TEXT NOT NULL, body TEXT NOT NULL, "
                         "UNIQUE(scope, opening))")
            # Approved bytes, keyed by content digest. A consumer acts on these,
            # never on a later read of the mutable file.
            conn.execute("CREATE TABLE IF NOT EXISTS snapshots (sha256 TEXT PRIMARY KEY, "
                         "data BLOB NOT NULL)")
        self.db.chmod(0o600)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        except sqlite3.Error as exc:
            # Locked/damaged storage: nothing was written, nothing is answered.
            raise QuestionError("question state is busy or unreadable") from exc
        finally:
            conn.close()

    def manifest(self, artifacts, deleted=(), workflow="", checkpoint=""):
        """Capture exact local bytes, including uncommitted plans; no git digest."""
        return [entry for entry, _ in self._capture(artifacts, list(deleted), workflow, checkpoint)]

    def _capture(self, artifacts, deleted, workflow, checkpoint):
        """Everything an occurrence binds: [(manifest entry, bytes to snapshot)].

        Files the caller names, paths the caller says the change removed, and
        what the server binds by itself (projection.derived).
        """
        change = checkpoint == projection.CHANGE_CHECKPOINT
        result = (self._read_artifacts(artifacts, change) + self._read_deleted(deleted, change)
                  + projection.derived(self.project, workflow, checkpoint))
        if len({x["path"] for x, _ in result}) != len(result):
            raise QuestionError("duplicate artifact (a plan approval binds the task file itself)")
        return result

    def _relative(self, rel):
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise QuestionError("artifact must be project-relative")

    def _git(self, *args, data=None):
        """Output of a read-only git query in the project, or None."""
        try:
            done = subprocess.run(["git", "-C", str(self.project), *args], input=data,
                                  capture_output=True, timeout=20, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout if done.returncode == 0 else None

    def _base(self, rel):
        """What the branch holds at a path: its whole tree entry in HEAD,
        "<mode> <type> <object id>", or None. The mode is part of it: a path
        whose content is unchanged but whose executable bit or type moved is
        a different target.
        """
        return tree_entry(self._git("ls-tree", "-z", "HEAD", "--", rel), rel)

    def _git_blob(self, rel, data, link=False):
        """The object id git stores for these working-tree bytes at this path
        (clean filters and attribute conversion applied), or None outside git.
        Computed from the bytes that are snapshotted, not from a second read.
        """
        how = ["--no-filters"] if link else [f"--path={rel}"]
        out = self._git("hash-object", *how, "--stdin", data=data)
        return out.decode().strip() if out else None

    def _commit_of(self, name):
        out = self._git("rev-parse", "-q", "--verify", f"{name}^{{commit}}")
        return out.decode().strip() if out else None

    def target(self, checkpoint, action=None):
        """What an approval acts on besides files, or None.

        review_approved  the checked-out branch the change is committed to.
        merge_approved   the source revision (the commit `source` names now)
                         and the branch it is merged into; `action` is
                         {"source", "destination"} as the caller named them.
        """
        if checkpoint == projection.MERGE_CHECKPOINT:
            return self._merge_target(action)
        if action:
            raise QuestionError("only a merge approval names a merge source and destination")
        if checkpoint != projection.CHANGE_CHECKPOINT:
            return None
        out = self._git("symbolic-ref", "-q", "HEAD")
        return {"ref": out.decode().strip()} if out and out.strip() else None

    def _merge_target(self, action):
        if not isinstance(action, dict) or set(action) != {"source", "destination"}:
            raise QuestionError("a merge approval names what is merged and where: "
                                "merge_source and merge_into")
        source, destination = action["source"], action["destination"]
        for name in (source, destination):
            if not isinstance(name, str) or not name or name.startswith("-") or len(name) > 200:
                raise QuestionError("invalid merge source or destination")
        if destination.startswith("refs/heads/"):
            destination = destination[len("refs/heads/"):]
        commit = self._commit_of(source)
        if commit is None:
            raise QuestionError("merge source does not name a commit")
        if self._commit_of(f"refs/heads/{destination}") is None:
            raise QuestionError("merge destination is not a local branch")
        return {"kind": "merge", "source_ref": source, "source": commit,
                "destination": destination, "ref": f"refs/heads/{destination}"}

    def _live(self, entry):
        """Current bytes of a bound path, read the way they were bound."""
        path = self.project / entry["path"]
        if entry.get("mode") == "120000":
            return os.fsencode(os.readlink(path))
        return path.read_bytes()

    def _read_artifacts(self, artifacts, change=False):
        """change: the files are a change set to commit. Each entry then also
        records the git file mode, `base` (the tree entry the branch holds
        at that path; None: a new file) and `blob` (the object git stores for
        these bytes at this path, after clean filters), so the approval is of
        a change to a known target, in a known git representation, and can be
        committed from the stored bytes.
        """
        # 200: a review approval binds every file of the change set.
        if not isinstance(artifacts, list) or len(artifacts) > 200:
            raise QuestionError("invalid artifact list")
        result = []
        for rel in artifacts:
            self._relative(rel)
            entry = {"path": rel}
            try:
                if change and (self.project / rel).is_symlink():
                    entry["mode"] = "120000"  # bound as the link, never its target
                    data = os.fsencode(os.readlink(self.project / rel))
                else:
                    path = (self.project / rel).resolve(strict=True)
                    path.relative_to(self.project)
                    data = path.read_bytes()
                    if change:
                        entry["mode"] = "100755" if os.access(path, os.X_OK) else "100644"
            except (OSError, ValueError) as exc:
                raise QuestionError("artifact is missing, unreadable or outside project") from exc
            if len(data) > 2_000_000:
                raise QuestionError("prototype artifact exceeds 2 MB")
            entry["sha256"] = hashlib.sha256(data).hexdigest()
            if change:
                entry["base"] = self._base(rel)
                entry["blob"] = self._git_blob(rel, data, entry["mode"] == "120000")
            result.append((entry, data))
        return result

    def _read_deleted(self, deleted, change=False):
        """Paths a reviewed change removes (a rename is its old path here plus
        its new path in artifacts). Bound as: absent now, and WHICH committed
        content is being removed. A path that exists, or that HEAD does not
        hold, is refused - absence is never inferred from a failed read.
        """
        if not isinstance(deleted, list) or len(deleted) > 200:
            raise QuestionError("invalid deleted list")
        result = []
        for rel in deleted:
            self._relative(rel)
            if os.path.lexists(self.project / rel):
                raise QuestionError("deleted path still exists")
            try:
                done = subprocess.run(["git", "-C", str(self.project), "show", f"HEAD:{rel}"],
                                      capture_output=True, timeout=20, check=False)
            except (OSError, subprocess.SubprocessError) as exc:
                raise QuestionError("deleted path has no readable committed original") from exc
            if done.returncode != 0:
                raise QuestionError("deleted path has no readable committed original")
            if len(done.stdout) > 2_000_000:
                raise QuestionError("prototype artifact exceeds 2 MB")
            entry = {"path": rel, "absent": True,
                     "original_sha256": hashlib.sha256(done.stdout).hexdigest()}
            if change:
                entry["base"] = self._base(rel)
            result.append((entry, done.stdout))
        return result

    def open(self, workflow, checkpoint, opening, questions, artifacts, deleted=(), run="",
             action=None):
        """opening is an occurrence-opening idempotency key, NOT question wording.

        run isolates independent runs of one skill: occurrences supersede each
        other only within (project, workflow, checkpoint, run). A task workflow
        is one run by construction - the task - and takes no run.
        """
        for v, n in [(workflow, "workflow"), (checkpoint, "checkpoint"), (opening, "opening")]:
            token(v, n)
        if run != "":
            token(run, "run")
            if projection.is_task_workflow(workflow):
                raise QuestionError("a task workflow is its own run; omit run")
        deleted = list(deleted)
        validate_questions(questions)
        captured = self._capture(artifacts, deleted, workflow, checkpoint)
        manifest = [entry for entry, _ in captured]
        target = self.target(checkpoint, action)
        # Optional parts join the keys only when used, so state written before
        # they existed keeps its scope and spec digest.
        scope = digest([str(self.project), workflow, checkpoint] + ([run] if run else []))
        spec = {"questions": questions, "artifacts": artifacts}
        if deleted:
            spec["deleted"] = deleted
        if action:
            spec["action"] = action
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute("SELECT body FROM sessions WHERE scope=? AND opening=?",
                               (scope, opening)).fetchone()
            if old:
                body = load(old[0])
                if body["spec_digest"] != digest(spec):
                    raise QuestionError("opening key reused for a different question set")
                self._refresh(body)
                self._save(conn, body)
                return self.view(body)
            # A new occurrence retires ALL older occurrences of this run at this
            # workflow checkpoint, even when questions/artifact bytes are
            # identical - including an approval already claimed: what it
            # permitted is history, it is no longer authority for new work.
            for row in conn.execute("SELECT body FROM sessions WHERE scope=?", (scope,)).fetchall():
                try:
                    old_body = load(row[0])
                except QuestionError:
                    continue  # unreadable occurrence can never complete; leave it
                self._invalidate(old_body, "checkpoint_reopened")
                self._revoke(old_body, "checkpoint_reopened")
                self._save(conn, old_body)
            body = {"schema": 1, "id": uuid.uuid4().hex, "project": str(self.project),
                    "workflow": workflow, "checkpoint": checkpoint, "opening": opening, "run": run,
                    "spec_digest": digest(spec), "questions": questions, "artifacts": artifacts,
                    "deleted": deleted, "action": action, "target": target,
                    "manifest": manifest, "answers": {}, "state": "pending",
                    "attempt": None, "receipt": None, "events": [], "selections": {}}
            self._event(body, "opened")
            # The fingerprinted bytes and the stored snapshot are one read.
            conn.executemany("INSERT OR IGNORE INTO snapshots VALUES (?,?)",
                             [(hashlib.sha256(data).hexdigest(), data) for _, data in captured])
            conn.execute("INSERT INTO sessions VALUES (?,?,?,?)",
                         (body["id"], scope, opening, encoded(body)))
            return self.view(body)

    @contextmanager
    def edit(self, session_id):
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT body FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                raise QuestionError("unknown question session")
            body = load(row[0])
            if body["project"] != str(self.project):
                raise QuestionError("question session belongs to another project")
            self._refresh(body)
            try:
                yield body
            finally:
                # Preserve freshness invalidation even if answer validation fails.
                self._stamp(body)
                self._save(conn, body)
                conn.commit()

    def _stamp(self, body):
        """Keep `waiting` true to the state: who serves a question that now
        waits at the prompt, and nothing once it no longer does. Only a touch
        of this one occurrence moves the stamp; listings never do.
        """
        if body["state"] not in WAITING_STATES:
            body.pop("waiting", None)
        elif self.owner:
            body["waiting"] = self.owner

    def _save(self, conn, body):
        conn.execute("UPDATE sessions SET body=? WHERE id=?", (encoded(body), body["id"]))

    def _event(self, body, event, **fields):
        events = body["events"]
        events.append({"at": time.time(), "event": event, **fields})
        if len(events) > MAX_EVENTS:
            # Keep the opening record; drop the oldest diagnostics after it.
            extra = len(events) - MAX_EVENTS
            del events[1:1 + extra]
            body["events_dropped"] = body.get("events_dropped", 0) + extra

    def _invalidate(self, body, reason):
        if body["state"] != "invalidated":
            body["state"] = "invalidated"
            body["attempt"] = None
            body["receipt"] = None
            self._event(body, "invalidated", reason=reason)

    def _revoke(self, body, reason):
        """End a claimed approval's standing. Persisted; never undone."""
        claim = body.get("consumption")
        if claim and not claim.get("revoked"):
            claim["revoked"] = {"at": time.time(), "reason": reason}
            self._event(body, "approval_revoked", reason=reason)

    def _blob(self, sha):
        with self.connect() as conn:
            row = conn.execute("SELECT data FROM snapshots WHERE sha256=?", (sha,)).fetchone()
        if row is None or hashlib.sha256(row[0]).hexdigest() != sha:
            raise QuestionError("approved snapshot is unavailable or corrupt")
        return bytes(row[0])

    def coverage(self, body):
        """Does a claimed approval still cover what it approved? (verdict, detail)

          FRESH        every bound entry matches the files; or, for an approval
                       whose change was committed through commit.py, that
                       commit is on the bound branch (its content cannot
                       change; later edits to the files are new work)
          BOOKKEEPING  as FRESH, except files changed only within the projection
                       the claim tolerates for them (plan-bookkeeping/v2)
          NOTES        the approved plan is intact and only the workflow's
                       closing sections follow it (plan-closing-notes/v1). The
                       approval does NOT stand for further work; it is not
                       revoked either, because nothing it approved changed
          PREPARED     the commit object exists but is not on the branch yet
          STALE        anything else, including unreadable evidence and a claim
                       that lacks what its checkpoint must bind today
        """
        claim = body["consumption"]
        target = body.get("target") or {}
        lacking = projection.unmet(body["workflow"], body["checkpoint"], claim["manifest"], target)
        if lacking:
            return "STALE", lacking
        if target.get("kind") == "merge":
            return self._merge_coverage(target)
        effect = claim.get("effect")
        if effect:
            short = effect["commit"][:12]
            if self._contains(effect["ref"], effect["commit"]):
                return "FRESH", f"committed as {short} on {effect['ref']}"
            if not effect.get("applied"):
                return "PREPARED", f"commit {short} is not on {effect['ref']} yet"
            if self._commit_of(effect["ref"]) is None:
                # The branch was merged and removed (a task branch after its
                # merge): the commit stands while a local branch contains it.
                held = self._git("for-each-ref", "--count=1", "--format=%(refname)",
                                 f"--contains={effect['commit']}", "refs/heads")
                if held and held.strip():
                    return "FRESH", f"committed as {short}, now on {held.decode().strip()}"
            return "STALE", f"commit {short} is no longer on {effect['ref']}"
        tolerated = claim.get("tolerates", {})
        bookkeeping, closed = [], []
        for entry in claim["manifest"]:
            path = entry["path"]
            if entry.get("absent"):
                # The original was bound at the approval; HEAD moves once the
                # approved change is committed, so only absence is re-proven.
                if os.path.lexists(self.project / path):
                    return "STALE", f"{path} exists again"
                continue
            try:
                live = self._live(entry)
                if entry.get("projection") == projection.TASK_PROJECTION:
                    live = projection.task_requirements(live)
            except (OSError, QuestionError):
                return "STALE", f"{path} is missing or unreadable"
            if hashlib.sha256(live).hexdigest() == entry["sha256"]:
                continue
            if entry.get("projection") == projection.TASK_PROJECTION:
                return "STALE", f"{path}: task requirements changed"
            if tolerated.get(path) != projection.PLAN_PROJECTION:
                return "STALE", f"{path} differs from the approved content"
            try:
                approved = self._blob(entry["sha256"])
            except QuestionError:
                return "STALE", f"{path} changed and its approved snapshot is unavailable"
            if projection.plan_covers(approved, live):
                bookkeeping.append(path)
            elif projection.plan_closed(approved, live):
                closed.append(path)
            else:
                return "STALE", f"{path} changed beyond {projection.PLAN_PROJECTION}"
        if closed:
            return "NOTES", ",".join(closed)
        if bookkeeping:
            return "BOOKKEEPING", ",".join(bookkeeping)
        return "FRESH", f"{len(claim['manifest'])} bound"

    def _contains(self, ref, commit):
        return self._git("merge-base", "--is-ancestor", commit, ref) is not None

    def _merge_coverage(self, target):
        """A merge approval is of ONE revision into ONE branch. It stands while
        that revision is what the source still names, and after the merge
        while the destination contains it."""
        short = target["source"][:12]
        if self._contains(target["ref"], target["source"]):
            return "FRESH", f"{short} is merged into {target['destination']}"
        if self._commit_of(target["ref"]) is None:
            return "STALE", f"merge destination {target['destination']} is gone"
        if self._commit_of(target["source_ref"]) == target["source"]:
            return "FRESH", f"{target['source_ref']} is still {short}; not merged yet"
        return "STALE", f"{target['source_ref']} no longer names the approved revision {short}"

    def standing(self, session_id):
        """Verdict on a claimed approval, with any revocation persisted first."""
        with self.edit(session_id) as body:
            claim = body.get("consumption")
            if not claim:
                return "STALE", "receipt was never claimed"
            if claim.get("revoked"):
                return "STALE", f"revoked: {claim['revoked']['reason']}"
            return self.coverage(body)

    def _refresh(self, body):
        claim = body.get("consumption")
        if claim and not claim.get("revoked"):
            # Observed staleness ends the approval for good: reverting the
            # bytes afterwards must not bring it back.
            verdict, detail = self.coverage(body)
            if verdict == "STALE":
                self._revoke(body, detail)
        if body["state"] in {"invalidated", "cancelled"}:
            return
        try:
            fresh = (self.manifest(body["artifacts"], body.get("deleted", ()),
                                   body["workflow"], body["checkpoint"]) == body["manifest"]
                     and self.target(body["checkpoint"], body.get("action")) == body.get("target"))
        except QuestionError:
            fresh = False
        if not fresh:
            self._invalidate(body, "artifact_revision_changed_or_unverifiable")
            return
        if body["attempt"] and body["attempt"]["deadline"] <= time.time():
            body["attempt"] = None
            body["state"] = "awaiting-chat-answer"
            self._event(body, "deadline_expired")

    def view(self, body, **extra):
        pending = [q for q in body["questions"] if q["id"] not in body["answers"]]
        state = body["state"]
        page = None
        if pending and pending[0]["kind"] == "multi":
            page = selection.page_view(pending[0], body["id"], self._selection(body, pending[0]["id"]))
        return {"session_id": body["id"], "occurrence_id": body["id"],
                "checkpoint": body["checkpoint"], "run": body.get("run", ""), "state": state,
                "answers": body["answers"], "pending": pending, "pending_page": page,
                "manifest": body["manifest"], "receipt": body["receipt"],
                "attempt": body["attempt"], "last_event": body["events"][-1],
                "consumption": body.get("consumption"),
                "next_action": ("consume_receipt_before_dependent_action" if state == "complete" else
                                "open_new_occurrence" if state == "invalidated" else
                                "stop" if state == "cancelled" else
                                "end_turn_and_request_explicit_prompt_answer"
                                if state in {"awaiting-chat-answer", "deferred"} else
                                "resume_next_question"), **extra}

    def _selection(self, body, question_id):
        return body.setdefault("selections", {}).setdefault(question_id, {"page": 0, "selected": [], "submissions": {}})

    def status(self, session_id):
        with self.edit(session_id) as body:
            return self.view(body)

    def outstanding(self, workflow=None, run=None):
        """Occurrences of this project still needing an answer or a consumer.

        Lets a restarted agent recover its session IDs from durable state
        instead of guessing. More than one row means the caller must match the
        checkpoint (or ask the user), never pick one.
        """
        if workflow is not None:
            token(workflow, "workflow")
        found, retired = [], []
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for row in conn.execute("SELECT body FROM sessions ORDER BY rowid").fetchall():
                try:
                    body = load(row[0])
                except QuestionError:
                    continue
                if body["project"] != str(self.project) or (workflow is not None and body["workflow"] != workflow):
                    continue
                if run is not None and body.get("run", "") != run:
                    continue
                self._refresh(body)
                self._save(conn, body)
                unconsumed = body["state"] == "complete" and not body.get("consumption")
                if body["state"] in {"pending", "awaiting-chat-answer", "deferred"} or unconsumed:
                    found.append({"workflow": body["workflow"], **self.view(body)})
                elif body["state"] == "invalidated" and not body.get("consumption"):
                    # Without this a question voided by a file edit simply
                    # vanishes and the caller concludes nothing was ever open.
                    last = body["events"][-1]
                    if last.get("event") == "invalidated" and last["at"] >= time.time() - RETIRED_NOTICE_SECONDS:
                        retired.append({"workflow": body["workflow"], "session_id": body["id"],
                                        "checkpoint": body["checkpoint"], "run": body.get("run", ""),
                                        "reason": last.get("reason"),
                                        "invalidated_at": last["at"],
                                        "next_action": "ask_again_with_new_opening"})
        return {"outstanding": found, "count": len(found), "retired": retired,
                "next_action": "none_outstanding" if not found else
                               "match_checkpoint_then_status_or_resume" if len(found) > 1 else
                               found[0]["next_action"]}

    def transport_event(self, session_id, attempt_id, details):
        """Non-secret negotiation/timing evidence survives a server restart."""
        with self.edit(session_id) as body:
            self._event(body, "transport", attempt=attempt_id, **details)

    def begin(self, session_id, timeout):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0.05 <= timeout <= 900:
            raise QuestionError("timeout must be 0.05..900 seconds")
        with self.edit(session_id) as body:
            if body["state"] in {"complete", "invalidated", "cancelled"}:
                return self.view(body)
            if body["attempt"]:
                return self.view(body, outcome="busy", next_action="end_turn_waiting_for_existing_attempt")
            question = next(q for q in body["questions"] if q["id"] not in body["answers"])
            attempt = {"id": uuid.uuid4().hex, "question_id": question["id"],
                       "deadline": time.time() + timeout}
            body["attempt"] = attempt
            body["state"] = "pending"
            self._event(body, "form_started", attempt=attempt["id"])
            return self.view(body, outcome="started", question=question)

    def fail(self, session_id, attempt_id, reason):
        with self.edit(session_id) as body:
            if body["attempt"] and body["attempt"]["id"] == attempt_id:
                body["attempt"] = None
                body["state"] = "awaiting-chat-answer"
                self._event(body, reason)
            return self.view(body, transport_outcome=reason)

    def submit(self, session_id, question_id, value, source, attempt_id=None, page_id=None):
        if source not in {"mcp_form", "codex_prompt_model_forwarded"}:
            raise QuestionError("invalid source")
        with self.edit(session_id) as body:
            # Deferred is "not now", not "no": the question stays open, so an
            # explicit later answer is accepted. A late form response cannot be
            # one — deferring cleared the attempt, so it returns stale_attempt.
            if body["state"] in {"invalidated", "cancelled"}:
                return self.view(body, outcome="not_accepted")
            question = next((q for q in body["questions"] if q["id"] == question_id), None)
            if question is None:
                raise QuestionError("unknown question id")
            if question["kind"] == "multi":
                return self._submit_selection(body, question, value, source, attempt_id, page_id)
            answer, provenance = validate_answer(question, value, source)
            old = body["answers"].get(question_id)
            if old:
                if old["value"] != answer:
                    return self.view(body, outcome="conflict")
                return self.view(body, outcome="duplicate", **self._resolution(question, old))
            pending_id = next(q["id"] for q in body["questions"] if q["id"] not in body["answers"])
            if pending_id != question_id:
                raise QuestionError("answer must address the current pending question")
            if source == "mcp_form" and (not body["attempt"] or body["attempt"]["id"] != attempt_id):
                return self.view(body, outcome="stale_attempt")
            record = {"value": answer, "raw": value, "source": source, **provenance}
            body["answers"][question_id] = record
            body["attempt"] = None
            body["state"] = "pending"
            self._event(body, "answer_accepted", question_id=question_id, source=source)
            self._complete(body)
            return self.view(body, outcome="accepted", **self._resolution(question, record))

    @staticmethod
    def _resolution(question, record):
        """{"resolved": …} for a choice answer, else nothing."""
        found = resolved(question, record) if question["kind"] == "choice" else None
        return {"resolved": found} if found else {}

    def _complete(self, body):
        if len(body["answers"]) == len(body["questions"]):
            body["state"] = "complete"
            body["receipt"] = {"id": uuid.uuid4().hex, "occurrence_id": body["id"],
                               "binding": digest([body["id"], body["spec_digest"], body["manifest"]]
                                                 + ([body["target"]] if body.get("target") else [])),
                               "purpose": "answers_only_consume_before_dependent_action"}

    def _submit_selection(self, body, question, value, source, attempt_id, page_id):
        submission = selection.parse_submission(value)
        state = self._selection(body, question["id"])
        old = state["submissions"].get(page_id)
        if old:
            return self.view(body, outcome="duplicate" if old["value"] == submission else "conflict")
        pending = [q["id"] for q in body["questions"] if q["id"] not in body["answers"]]
        if not pending or pending[0] != question["id"]:
            raise QuestionError("answer must address the current pending question")
        if source == "mcp_form" and (not body["attempt"] or body["attempt"]["id"] != attempt_id):
            return self.view(body, outcome="stale_attempt")
        ordered, done = selection.advance(question, body["id"], state, page_id, submission)
        state["selected"] = ordered
        state["submissions"][page_id] = {"value": submission, "raw": value, "source": source}
        body["attempt"] = None
        body["state"] = "pending"
        self._event(body, "selection_page_accepted", question_id=question["id"], page_id=page_id, source=source)
        if done:
            body["answers"][question["id"]] = {"value": ordered, "source": "selection_pages",
                                               "pages": state["submissions"]}
            self._event(body, "answer_accepted", question_id=question["id"], source="selection_pages")
            self._complete(body)
        else:
            state["page"] += 1
        return self.view(body, outcome="accepted")

    def cancel(self, session_id, defer=False, attempt_id=None):
        with self.edit(session_id) as body:
            if attempt_id is not None and (not body["attempt"] or body["attempt"]["id"] != attempt_id):
                return self.view(body, outcome="stale_attempt")
            if body["state"] not in {"invalidated", "cancelled", "complete"}:
                body["attempt"] = None
                body["state"] = "deferred" if defer else "cancelled"
                self._event(body, body["state"])
            return self.view(body)

    def consume(self, session_id, receipt_id, consumer, tolerates=None, effect=None):
        """Claim a completion receipt for ONE dependent action, at the action boundary.

        Freshness is re-proven inside the claiming transaction: a changed or
        unreadable artifact, a retired occurrence or a foreign receipt returns
        stale_approval and claims nothing. consumer is the caller's durable
        idempotency key for the action. A repeated claim by the same consumer
        returns duplicate with the original record, so a crash between claim
        and effect is reconciled by the caller (check acknowledged, then verify
        the effect) instead of repeated blindly. After a claim, read approved
        content with snapshot(), never from the live file.

        tolerates maps a bound path to the projection under which later
        changes to it keep the claim standing (see coverage); default none.

        effect is a commit already built from the approved snapshots
        (commit.py): recorded in the same transaction that proves freshness,
        so there is no moment at which the claim exists and depends on the
        working tree staying as approved.
        """
        token(receipt_id, "receipt id")
        token(consumer, "consumer")
        tolerates = dict(tolerates or {})
        with self.edit(session_id) as body:
            receipt = body["receipt"]
            if body["state"] != "complete" or not receipt or receipt["id"] != receipt_id:
                return self.view(body, outcome="stale_approval")
            old = body.get("consumption")
            if old:
                return self.view(body, outcome="duplicate" if old["consumer"] == consumer else "conflict")
            if set(tolerates) - {entry["path"] for entry in body["manifest"] if "sha256" in entry}:
                raise QuestionError("tolerated path is not a bound file")
            body["consumption"] = {"id": uuid.uuid4().hex, "consumer": consumer,
                                   "receipt_id": receipt_id, "manifest": body["manifest"],
                                   "tolerates": tolerates,
                                   "claimed_at": time.time(), "acknowledged": False}
            if effect:
                body["consumption"]["effect"] = dict(effect)
            self._event(body, "receipt_consumed", consumer=consumer)
            return self.view(body, outcome="claimed")

    def acknowledge(self, session_id, consumption_id):
        """Record that the claimed action's effect exists. Idempotent; history only.

        Allowed after a later invalidation: a completed action stays evidence of
        what was done, while new dependent work needs a new occurrence.
        """
        with self.edit(session_id) as body:
            claim = body.get("consumption")
            if not claim or claim["id"] != consumption_id:
                return self.view(body, outcome="unknown_consumption")
            if claim["acknowledged"]:
                return self.view(body, outcome="duplicate")
            claim["acknowledged"] = True
            self._event(body, "consumption_acknowledged")
            return self.view(body, outcome="acknowledged")

    def record_effect(self, session_id, consumption_id, effect):
        """Attach or update the commit a standing claim produced."""
        with self.edit(session_id) as body:
            claim = body.get("consumption")
            if not claim or claim["id"] != consumption_id:
                return self.view(body, outcome="unknown_consumption")
            if claim.get("revoked"):
                return self.view(body, outcome="stale_approval")
            claim["effect"] = dict(effect)
            self._event(body, "effect_recorded", commit=effect["commit"],
                        applied=bool(effect.get("applied")))
            return self.view(body, outcome="recorded")

    def snapshot(self, session_id, path):
        """Return the approved bytes of one bound artifact (immutable snapshot)."""
        with self.connect() as conn:
            row = conn.execute("SELECT body FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                raise QuestionError("unknown question session")
            body = load(row[0])
            if body["project"] != str(self.project):
                raise QuestionError("question session belongs to another project")
            entry = next((m for m in body["manifest"] if m["path"] == path), None)
            if entry is None:
                raise QuestionError("artifact is not bound to this occurrence")
        # For a removed path this is the committed original; for the task file
        # it is the bound requirements text, not the whole file.
        return self._blob(entry.get("sha256") or entry["original_sha256"])
