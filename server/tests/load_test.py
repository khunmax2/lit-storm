"""Many Runs and many people at once, on a stack of its own, at no LLM cost.

    uv run python tests/load_test.py <output dir> [--keep] [--only=N ...]

Wipes and installs its own stack (Compose project `litstorm-load` on port
8093, behind /litstorm as on the host), signs in many Users, and has each
queue Runs. Before the Worker sees them the Runs are handed the test Engine
(engines/fake.py) with a script shaped like a real Run: it loads STORM's
libraries, walks the stages, sends progress notes and takes its time, but
calls no model and no search. Meanwhile every User polls the pages the web
app polls while a Run is live.

Each scenario records the Worker's memory, the database's connections, how
long Runs waited for a slot, the order Users got their turns, and the API's
response times, and writes <output dir>/load.md and load.json.
"""

import json
import os
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = "litstorm-load"
PORT = "8093"
COMPOSE = [
    "docker", "compose", "-p", PROJECT,
    "-f", os.path.join(ROOT, "stack", "compose.yml"),
    "-f", os.path.join(ROOT, "stack", "compose.mirror.yml"),
]
os.environ["LITSTORM_PORT"] = PORT
BASE = f"http://127.0.0.1:{PORT}/litstorm"
ADMIN = ("admin@example.org", "load test admin pw")
PASSWORD = "load test user pw"
FINAL = {"succeeded", "failed", "cancelled", "interrupted"}

# name, Users, Runs each, system ceiling, per-User ceiling, embed built in,
# seconds of work per Run
SCENARIOS = [
    ("20 at once", 20, 1, 20, 1, False, 90),
    ("10 at once, built-in embedding", 10, 1, 10, 1, True, 90),
    ("60 Users, ceiling 20", 60, 1, 20, 1, False, 60),
    ("100 Users, 2 Runs each, ceiling 20, 2 per User", 100, 2, 20, 2, False, 30),
]


def sh(*args, check=True):
    print("$", " ".join(args), flush=True)
    return subprocess.run(args, check=check, capture_output=True, text=True, encoding="utf-8")


def compose(*args, check=True):
    return sh(*COMPOSE, *args, check=check)


def psql(sql):
    return compose("exec", "-T", "db", "psql", "-U", "litstorm", "-tAc", sql).stdout.strip()


def wait_healthy(timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE}/api/health", timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise RuntimeError("stack did not become healthy")


class Api:
    def __init__(self, email, password):
        self.c = httpx.Client(base_url=BASE, timeout=60)
        r = self.c.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text

    def _h(self):
        return {"X-CSRF-Token": self.c.cookies.get("litstorm_csrf")}

    def get(self, path, **kw):
        return self.c.get(path, **kw)

    def post(self, path, **kw):
        return self.c.post(path, headers=self._h(), **kw)

    def put(self, path, **kw):
        return self.c.put(path, headers=self._h(), **kw)


def script(seconds, embed):
    """A Run's shape without its calls: STORM's libraries, four stages, a
    progress note every couple of seconds."""
    steps = [{"import": "litstorm.engines.storm.engine"}]
    stages = ("research", "outline", "article", "polish")
    for stage in stages:
        steps.append({"stage": stage})
        if stage == "article" and embed:
            steps.append({"embed": True})
        for i in range(int(seconds / len(stages) / 2)):
            steps.append({"note": "search", "data": {"query": f"{stage} query {i}", "results": 5}})
            steps.append({"sleep": 2})
    return {"script": steps}


# --- measuring ----------------------------------------------------------------------------


def _mib(text):
    number, unit = float(text[:-3]), text[-3:]
    return number * {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024}[unit]


class Sampler(threading.Thread):
    """Every few seconds: each container's memory, the Runs by status, and
    the database's open connections."""

    def __init__(self):
        super().__init__(daemon=True)
        self.samples, self.stopping = [], threading.Event()

    def run(self):
        started = time.time()
        while not self.stopping.is_set():
            stats = sh("docker", "stats", "--no-stream", "--format", "{{.Name}} {{.MemUsage}} {{.CPUPerc}}").stdout
            memory, cpu = {}, {}
            for line in stats.splitlines():
                name, used, *_rest = line.split()
                if name.startswith(PROJECT + "-"):
                    service = name[len(PROJECT) + 1:].rsplit("-", 1)[0]
                    memory[service] = round(_mib(used))
                    cpu[service] = float(_rest[-1].rstrip("%"))
            counts = dict(
                line.split("|") for line in psql("select status, count(*) from runs group by status").splitlines() if line
            )
            connections = int(psql("select count(*) from pg_stat_activity where datname = 'litstorm'"))
            self.samples.append({
                "t": round(time.time() - started), "memory": memory, "cpu": cpu,
                "running": int(counts.get("running", 0)), "queued": int(counts.get("queued", 0)),
                "connections": connections,
            })

    def stop(self):
        self.stopping.set()
        self.join()


def child_memory():
    """Resident memory of each Run's process in the Worker, in MiB."""
    probe = (
        "import os\n"
        "for p in os.listdir('/proc'):\n"
        "    if p.isdigit():\n"
        "        try:\n"
        "            cmd = open(f'/proc/{p}/cmdline').read()\n"
        "            if 'litstorm.runner.child' in cmd:\n"
        "                rss = [l for l in open(f'/proc/{p}/status') if l.startswith('VmRSS')][0].split()[1]\n"
        "                print(int(rss) // 1024)\n"
        "        except OSError:\n"
        "            pass\n"
    )
    out = compose("exec", "-T", "worker", "python", "-c", probe).stdout
    return [int(x) for x in out.split()]


class Viewers:
    """Each User with a live Run polls what the Run page polls: the Run's
    events every 2.5 s, its Session every 4 s, the sidebar every 15 s."""

    def __init__(self, users, sessions):
        self.users, self.sessions = users, sessions
        self.latencies, self.errors, self.lock = [], [], threading.Lock()
        self.stopping = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=len(users))

    def _time(self, api, path):
        started = time.perf_counter()
        try:
            r = api.get(path)
            status = r.status_code
        except httpx.HTTPError as error:
            status = type(error).__name__
        took = (time.perf_counter() - started) * 1000
        with self.lock:
            self.latencies.append(took)
            if status != 200:
                self.errors.append(f"{path.split('?')[0]} {status}")
        return r if status == 200 else None

    def start(self, runs_by_user):
        for api, sessions in zip(self.users, self.sessions):
            self.pool.submit(self._watch_runs, api, sessions, runs_by_user[id(api)])

    def _watch_runs(self, api, sessions, run_ids):
        try:
            after = {r: 0 for r in run_ids}
            last_session = last_recent = 0.0
            while not self.stopping.is_set() and after:
                now = time.time()
                if now - last_recent >= 15:
                    self._time(api, "/api/sessions/recent?limit=12")
                    last_recent = now
                if now - last_session >= 4:
                    for s in sessions:
                        self._time(api, f"/api/sessions/{s}")
                    last_session = now
                for run_id in list(after):
                    r = self._time(api, f"/api/runs/{run_id}?after={after[run_id]}")
                    if r is not None:
                        body = r.json()
                        if body.get("events"):
                            after[run_id] = body["events"][-1]["id"]
                        if body["status"] in FINAL:
                            del after[run_id]
                self.stopping.wait(2.5)
        except Exception as error:  # noqa: BLE001 - one viewer's fault is a finding, not a crash
            with self.lock:
                self.errors.append(f"viewer: {type(error).__name__}: {error}")

    def stop(self):
        self.stopping.set()
        self.pool.shutdown(wait=True)


def pct(values, p):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * p / 100))], 1)


# --- the run ---------------------------------------------------------------------------------


def install():
    compose("down", "-v")
    sh("sh", os.path.join(ROOT, "stack", "init-secrets.sh"))
    compose("up", "-d", "--build")
    wait_healthy()
    code = open(os.path.join(ROOT, "stack", "secrets", "bootstrap_code"), encoding="utf-8").read().strip()
    r = httpx.post(f"{BASE}/api/setup", json={"code": code, "email": ADMIN[0], "name": "Admin", "password": ADMIN[1]})
    assert r.status_code in (200, 201), r.text
    admin = Api(*ADMIN)
    # A key the fake Engine never uses: a Run needs a model to be queued.
    admin.put("/api/admin/llm-credentials/openrouter", json={"api_key": "load-test-not-a-key"})
    r = admin.post(
        "/api/admin/llm-models",
        json={"label": "Load test", "provider": "openrouter", "model": "google/gemini-3.5-flash-lite",
              "max_tokens": {"conversation": 1500, "writing": 4000}, "is_default": True},
    )
    assert r.status_code in (200, 201), r.text
    return admin


def make_users(admin, count):
    def one(i):
        email = f"user{i:03d}@example.org"
        link = admin.post("/api/admin/users", json={"email": email, "name": f"User {i}"}).json()["link"]
        r = httpx.post(f"{BASE}/api/auth/password", json={"token": link.split("#", 1)[1], "password": PASSWORD})
        assert r.status_code == 200, r.text
        return Api(email, PASSWORD)

    with ThreadPoolExecutor(max_workers=10) as pool:
        return list(pool.map(one, range(count)))


def set_limits(admin, **changes):
    current = admin.get("/api/admin/limits").json()
    r = admin.put("/api/admin/limits", json={**current, **changes})
    assert r.status_code == 200, r.text


def scenario(admin, users, name, n_users, runs_each, total, per_user, embed, seconds):
    print(f"\n=== {name}", flush=True)
    set_limits(admin, max_concurrent_total=total, max_concurrent_per_user=per_user,
               max_queued_per_user=max(5, runs_each), monthly_run_quota=1000)
    compose("stop", "worker")
    group = users[:n_users]

    def queue(api):
        project = api.post("/api/projects", json={"name": f"{name[:30]}"}).json()
        sessions, run_ids = [], []
        for k in range(runs_each):
            r = api.post(f"/api/projects/{project['id']}/sessions",
                         json={"topic": f"Load test {name} {k}", "language": "en"})
            assert r.status_code == 201, r.text
            body = r.json()
            sessions.append(body["id"])
            run_ids.append(body["runs"][0]["id"])
        return sessions, run_ids

    submitted = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(group)) as pool:
        queued = list(pool.map(queue, group))
    submit_seconds = round(time.perf_counter() - submitted, 1)
    all_runs = [r for _, runs in queued for r in runs]
    ids = ",".join(f"'{r}'" for r in all_runs)
    params = json.dumps(script(seconds, embed)).replace("'", "''")
    psql(f"update runs set engine = 'fake', config = jsonb_set(config, '{{params}}', '{params}'::jsonb) where id in ({ids})")

    viewers = Viewers(group, [s for s, _ in queued])
    viewers.start({id(api): runs for api, (_, runs) in zip(group, queued)})
    sampler = Sampler()
    sampler.start()
    started = time.time()
    compose("start", "worker")

    # The Run processes at the moment they held the most memory together.
    children = []
    while True:
        done = int(psql(f"select count(*) from runs where id in ({ids}) and status in ('succeeded','failed','cancelled','interrupted')"))
        now = child_memory()
        if sum(now) > sum(children):
            children = now
        if done == len(all_runs):
            break
        if time.time() - started > 30 * 60:
            raise TimeoutError(f"{name}: {done}/{len(all_runs)} finished after 30 minutes")
        time.sleep(3)
    wall = round(time.time() - started)
    viewers.stop()
    sampler.stop()

    rows = psql(
        "select status, coalesce(reason,''), extract(epoch from started_at - queued_at), "
        "extract(epoch from finished_at - started_at), owner_id "
        f"from runs where id in ({ids}) order by started_at"
    ).splitlines()
    statuses, waits, durations, owners = {}, [], [], []
    for row in rows:
        status, reason, wait, took, owner = row.split("|")
        key = f"{status}/{reason}" if reason else status
        statuses[key] = statuses.get(key, 0) + 1
        waits.append(float(wait))
        durations.append(float(took))
        owners.append(owner)
    # Turns between Users: with 2 Runs each, no User's second Run should
    # start before every User with a waiting Run has had their first.
    first_seen, second_before_all_first = set(), 0
    for owner in owners:
        if owner in first_seen:
            if len(first_seen) < len(group):
                second_before_all_first += 1
        first_seen.add(owner)

    worker_peak = max((s["memory"].get("worker", 0) for s in sampler.samples), default=0)
    idle = sampler.samples[0]["memory"].get("worker", 0) if sampler.samples else 0
    return {
        "name": name, "users": n_users, "runs": len(all_runs), "ceiling": total, "per_user": per_user,
        "builtin_embedding": embed, "work_seconds": seconds,
        "submit_seconds": submit_seconds, "wall_seconds": wall, "statuses": statuses,
        "peak_running": max((s["running"] for s in sampler.samples), default=0),
        "wait_p50": pct(waits, 50), "wait_p95": pct(waits, 95), "wait_max": round(max(waits), 1),
        "run_seconds_p50": pct(durations, 50), "run_seconds_max": round(max(durations), 1),
        "second_run_before_everyones_first": second_before_all_first if runs_each > 1 else None,
        "worker_memory_idle_mib": idle, "worker_memory_peak_mib": worker_peak,
        "child_memory_mib_at_peak": children,
        "api_memory_peak_mib": max((s["memory"].get("api", 0) for s in sampler.samples), default=0),
        "db_memory_peak_mib": max((s["memory"].get("db", 0) for s in sampler.samples), default=0),
        "worker_cpu_peak_pct": max((s["cpu"].get("worker", 0) for s in sampler.samples), default=0),
        "db_connections_peak": max((s["connections"] for s in sampler.samples), default=0),
        "api_requests": len(viewers.latencies), "api_ms_p50": pct(viewers.latencies, 50),
        "api_ms_p95": pct(viewers.latencies, 95), "api_ms_max": pct(viewers.latencies, 100),
        "api_errors": sorted(set(viewers.errors))[:20], "api_error_count": len(viewers.errors),
        "samples": sampler.samples,
    }


def report(out, results):
    lines = ["# Load test", "", f"Stack `{PROJECT}`, fake Engine loading STORM's libraries; "
             f"{time.strftime('%Y-%m-%d %H:%M')}.", ""]
    for r in results:
        per_run = r["child_memory_mib_at_peak"]
        lines += [
            f"## {r['name']}", "",
            f"- Runs: {r['runs']} from {r['users']} Users; ceiling {r['ceiling']} system, {r['per_user']} per User; "
            f"{r['work_seconds']} s of work each; built-in embedding: {'yes' if r['builtin_embedding'] else 'no'}",
            f"- Ended: {r['statuses']}; all done in {r['wall_seconds']} s; peak running {r['peak_running']}",
            f"- Wait for a slot: p50 {r['wait_p50']} s, p95 {r['wait_p95']} s, max {r['wait_max']} s",
            f"- Run length: p50 {r['run_seconds_p50']} s, max {r['run_seconds_max']} s",
            f"- Worker memory: idle {r['worker_memory_idle_mib']} MiB, peak {r['worker_memory_peak_mib']} MiB; "
            f"each Run's process at the peak: {min(per_run, default=0)}–{max(per_run, default=0)} MiB "
            f"(mean {round(statistics.mean(per_run)) if per_run else 0}, {len(per_run)} processes)",
            f"- Worker CPU peak: {r['worker_cpu_peak_pct']} % (of 1 core = 100 %)",
            f"- API memory peak {r['api_memory_peak_mib']} MiB; database peak {r['db_memory_peak_mib']} MiB, "
            f"{r['db_connections_peak']} connections",
            f"- API: {r['api_requests']} requests while Runs were live, p50 {r['api_ms_p50']} ms, "
            f"p95 {r['api_ms_p95']} ms, max {r['api_ms_max']} ms; {r['api_error_count']} errors "
            f"{r['api_errors'] or ''}",
            f"- Queueing {r['runs']} Runs took {r['submit_seconds']} s from {r['users']} Users at once",
        ]
        if r["second_run_before_everyones_first"] is not None:
            lines.append(f"- Second Runs started before every User had their first: "
                         f"{r['second_run_before_everyones_first']}")
        lines.append("")
    with open(os.path.join(out, "load.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(os.path.join(out, "load.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)


def main(out, keep, only=()):
    os.makedirs(out, exist_ok=True)
    admin = install()
    users = make_users(admin, max(s[1] for s in only or SCENARIOS))
    results = []
    try:
        for s in only or SCENARIOS:
            results.append(scenario(admin, users, *s))
            report(out, results)
    finally:
        if not keep:
            compose("down", "-v")
    print(open(os.path.join(out, "load.md"), encoding="utf-8").read())


if __name__ == "__main__":
    # --only=4: just the fourth scenario (1-based), for checking one fix.
    picked = [SCENARIOS[int(a.split("=", 1)[1]) - 1] for a in sys.argv if a.startswith("--only=")]
    main(sys.argv[1], "--keep" in sys.argv, picked)
