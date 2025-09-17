import os, time, json, asyncio, contextlib, hashlib, random
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
from copy import deepcopy
from threading import Lock
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import httpx

load_dotenv()
API_KEY = os.getenv("LOCAL_API_KEY", "local-dev-key-123")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

app = FastAPI(title="Twin Boss Agent API")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("TB_DATA_DIR", BASE_DIR / "runtime"))
STATE_FILE = Path(os.getenv("TB_STATE_FILE", DATA_DIR / "state.json"))
TRAEFIK_DYNAMIC_PATH = Path(os.getenv("TRAEFIK_DYNAMIC_FILE", BASE_DIR / "config/traefik/dynamic/domains.yml"))
SERVICE_DEFAULT_PORTS = {
    "twinboss_api": 9000,
    "fastmcp": 8080,
    "mcpjungle": 4000,
    "docker_mcp": 8090,
}

_state_lock = Lock()


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _default_state() -> Dict[str, Any]:
    now = _now_iso()
    return {
        "meta": {"created_at": now, "updated_at": now, "revision": 0},
        "domains": [],
        "storage": {"date_app": {"status": "uninitialized", "updated_at": now}},
        "agents": {},
    }


def _write_state_unlocked(state: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_FILE.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
    tmp_path.replace(STATE_FILE)


def _read_state_unlocked() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return _default_state()
    try:
        with STATE_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        state = _default_state()
        _write_state_unlocked(state)
        return state


def _ensure_state_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        _write_state_unlocked(_default_state())
    else:
        try:
            _read_state_unlocked()
        except Exception:
            _write_state_unlocked(_default_state())


def read_state() -> Dict[str, Any]:
    with _state_lock:
        return deepcopy(_read_state_unlocked())


def update_state(mutator) -> (Dict[str, Any], Any):
    with _state_lock:
        state = _read_state_unlocked()
        result = mutator(state)
        ts = _now_iso()
        meta = state.setdefault("meta", {})
        meta.setdefault("created_at", ts)
        meta["updated_at"] = ts
        meta["revision"] = meta.get("revision", 0) + 1
        meta["domain_count"] = len(state.get("domains", []))
        meta["agent_count"] = len(state.get("agents", {}))
        storage = state.get("storage", {}).get("date_app", {})
        meta["date_storage_status"] = storage.get("status", "uninitialized")
        _write_state_unlocked(state)
        return deepcopy(state), deepcopy(result)


def _normalize_domain(domain: str) -> str:
    if not domain:
        raise ValueError("domain required")
    candidate = domain.strip()
    if "//" not in candidate:
        candidate = f"http://{candidate}"
    parsed = urlparse(candidate)
    host = parsed.hostname
    if not host:
        raise ValueError(f"invalid domain '{domain}'")
    return host.lower()


def _normalize_domains(domains: List[str]) -> List[str]:
    cleaned = []
    for item in domains or []:
        try:
            normalized = _normalize_domain(item)
        except ValueError:
            continue
        cleaned.append(normalized)
    unique = list(dict.fromkeys(sorted(cleaned)))
    return unique


def _slugify(name: str) -> str:
    slug = "".join(char if char.isalnum() else "-" for char in name.lower())
    parts = [segment for segment in slug.split("-") if segment]
    return "-".join(parts) or f"agent-{int(time.time())}"


def _write_domain_dynamic_config(domains: List[Dict[str, Any]]) -> None:
    TRAEFIK_DYNAMIC_PATH.parent.mkdir(parents=True, exist_ok=True)
    middleware_needed = any(d.get("redirect_to_https") for d in domains or [])
    lines: List[str] = ["http:"]
    if middleware_needed:
        lines.extend([
            "  middlewares:",
            "    redirect-to-https:",
            "      redirectScheme:",
            "        scheme: https",
            "        permanent: true",
        ])
    lines.append("  routers:")
    routers_written = False
    service_urls: Dict[str, set] = {}
    for entry in domains or []:
        domain = entry.get("domain")
        if not domain:
            continue
        routers_written = True
        router_name = entry.get("router_name") or domain.replace(".", "-")
        service_name = entry.get("service_name") or entry.get("target_service") or f"svc-{entry.get('id', router_name)}"
        entrypoint = entry.get("entrypoint") or ("websecure" if entry.get("auto_ssl") else "web")
        lines.append(f"    {router_name}:")
        lines.append(f"      rule: Host(`{domain}`)")
        lines.append("      entryPoints:")
        lines.append(f"        - {entrypoint}")
        lines.append(f"      service: {service_name}")
        if entry.get("redirect_to_https") and entrypoint != "websecure":
            lines.append("      middlewares:")
            lines.append("        - redirect-to-https")
        target_url = entry.get("target_url")
        if target_url:
            url = target_url.rstrip("/")
        else:
            scheme = entry.get("target_scheme", "http")
            service_host = entry.get("target_service", "twinboss_api")
            port = entry.get("target_port") or SERVICE_DEFAULT_PORTS.get(service_host, 80)
            url = f"{scheme}://{service_host}:{port}"
        service_urls.setdefault(service_name, set()).add(url)
    if not routers_written:
        lines.append("    placeholder:")
        lines.append("      rule: HostRegexp(`{any:.+}`)")
        lines.append("      service: noop")
    lines.append("  services:")
    if service_urls:
        for service_name, urls in sorted(service_urls.items()):
            lines.append(f"    {service_name}:")
            lines.append("      loadBalancer:")
            lines.append("        servers:")
            for url in sorted(urls):
                lines.append(f"          - url: \"{url}\"")
    else:
        lines.extend([
            "    noop:",
            "      loadBalancer:",
            "        servers:",
            "          - url: \"http://127.0.0.1:9000\"",
        ])
    TRAEFIK_DYNAMIC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _collect_domains_from_env() -> List[str]:
    domains = set()
    env_value = os.getenv("DOMAINS", "")
    for raw in env_value.split(","):
        host = raw.strip()
        if host:
            domains.add(host)
    for key, value in os.environ.items():
        if key.startswith("DOMAIN_") and key != "DOMAINS":
            candidate = value.strip()
            if candidate:
                domains.add(candidate)
    normalized = []
    for item in domains:
        try:
            normalized.append(_normalize_domain(item))
        except ValueError:
            continue
    return sorted(dict.fromkeys(normalized))


def seed_domains_from_env() -> None:
    domains = _collect_domains_from_env()
    if not domains:
        return
    snapshot = read_state()
    existing = {entry.get("domain") for entry in snapshot.get("domains", []) if entry.get("domain")}
    missing = [d for d in domains if d not in existing]
    if not missing:
        return
    ts = _now_iso()

    def mut(state: Dict[str, Any]):
        domain_list = state.setdefault("domains", [])
        for domain in missing:
            entry = {
                "domain": domain,
                "id": hashlib.blake2s(domain.encode("utf-8"), digest_size=6).hexdigest(),
                "created_at": ts,
                "updated_at": ts,
                "history": [{"action": "seeded-env", "at": ts, "target": "twinboss_api"}],
                "target_service": "twinboss_api",
                "service_name": "twinboss_api",
                "router_name": domain.replace(".", "-"),
                "target_port": SERVICE_DEFAULT_PORTS.get("twinboss_api", 9000),
                "target_scheme": "http",
                "target_url": None,
                "entrypoint": "web",
                "auto_ssl": True,
                "redirect_to_https": True,
            }
            domain_list.append(entry)
        domain_list.sort(key=lambda item: item["domain"])
        return {"added": missing}

    state, _ = update_state(mut)
    _write_domain_dynamic_config(state.get("domains", []))


_ensure_state_file()
seed_domains_from_env()
_write_domain_dynamic_config(read_state().get("domains", []))


def auth(x_api_key: Optional[str]):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, "unauthorized")


# ---- Preview stream via SSE ----
_preview_queue: asyncio.Queue[str] = asyncio.Queue()


async def publish(msg: str):
    await _preview_queue.put(msg)


async def sse_gen():
    while True:
        msg = await _preview_queue.get()
        yield f"data: {msg}\n\n"


@app.get("/health")
def health():
    return {"ok": True, "service": "twinboss", "time": time.time()}


@app.get("/config")
async def config(x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    state = read_state()
    domains_env = [d.strip() for d in os.getenv("DOMAINS", "").split(",") if d.strip()]
    stored_domains = [d.get("domain") for d in state.get("domains", []) if d.get("domain")]
    domains = sorted(set(domains_env + stored_domains))
    return {
        "keys_present": {"OPENAI": bool(OPENAI_API_KEY), "GEMINI": bool(GEMINI_API_KEY)},
        "domains": domains,
        "state": state.get("meta", {}),
    }


@app.get("/previews/stream")
async def previews_stream():
    return StreamingResponse(sse_gen(), media_type="text/event-stream")


# ---- LLM helpers ----
async def llm_openai(prompt: str) -> str:
    if not OPENAI_API_KEY:
        return f"[MOCK OPENAI OUTPUT] {prompt[:140]} ..."
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a senior production engineer. Output only complete, deployable answers. No samples."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]


def score_output(text: str) -> float:
    score = 0.0
    score += text.count("```") * 2
    for kw in ["docker", "deploy", "install", "powershell", "bash", "curl", "npm", "uvicorn", "systemctl", "compose"]:
        if kw in text.lower():
            score += 1.0
    if "example" in text.lower() or "sample" in text.lower():
        score -= 3.0
    score += len(text.split()) / 500.0
    return score


class TwinQuery(BaseModel):
    query: str


@app.post("/agents/twin/execute")
async def twin_execute(body: TwinQuery, x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    q = body.query.strip()
    await publish(f"twin:start:{q}")
    p1 = f"Produce a complete, production-ready solution for: {q}"
    p2 = f"Independently produce a different complete production solution for: {q}. Use distinct stack or architecture."
    r1, r2 = await asyncio.gather(llm_openai(p1), llm_openai(p2))
    await publish("twin:generated:two-candidates")
    s1, s2 = score_output(r1), score_output(r2)
    choice = r1 if s1 >= s2 else r2
    await publish(f"twin:selected:best s1={s1:.2f} s2={s2:.2f}")
    return JSONResponse({"chosen": "A" if s1 >= s2 else "B", "scoreA": s1, "scoreB": s2, "output": choice})


class DomainHostRequest(BaseModel):
    domain: str
    target_service: Optional[str] = None
    target_port: Optional[int] = None
    target_scheme: str = "http"
    target_url: Optional[str] = None
    entrypoint: str = "web"
    auto_ssl: bool = True
    redirect_to_https: bool = True
    notes: Optional[str] = None


class DateStorageRequest(BaseModel):
    storage_engine: str = "postgres"
    primary_region: str = "us-east-1"
    replicas: int = 1
    retention_days: int = 365
    backup_regions: List[str] = Field(default_factory=list)
    analytics: bool = False
    encryption: bool = True
    notes: Optional[str] = None


class AgentRegistration(BaseModel):
    name: str
    role: str = "generalist"
    rights: str = "member"
    status: str = "active"
    endpoint: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)


@app.get("/domains")
async def list_domains(x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    state = read_state()
    return {"domains": state.get("domains", []), "revision": state.get("meta", {}).get("revision")}


@app.post("/domains/host")
async def host_domain(payload: DomainHostRequest, x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    if not payload.target_service and not payload.target_url:
        raise HTTPException(400, "target_service or target_url is required")
    try:
        normalized = _normalize_domain(payload.domain)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    target_service = payload.target_service
    target_url = payload.target_url.rstrip("/") if payload.target_url else None
    if target_service:
        target_port = payload.target_port or SERVICE_DEFAULT_PORTS.get(target_service, 80)
    else:
        target_port = payload.target_port
    ts = _now_iso()

    def mut(state: Dict[str, Any]):
        domains = state.setdefault("domains", [])
        existing = next((d for d in domains if d.get("domain") == normalized), None)
        entry = existing or {
            "domain": normalized,
            "id": hashlib.blake2s(normalized.encode("utf-8"), digest_size=6).hexdigest(),
            "created_at": ts,
            "history": [],
        }
        entry.update(
            {
                "target_service": target_service,
                "target_port": target_port,
                "target_scheme": payload.target_scheme or "http",
                "target_url": target_url,
                "entrypoint": payload.entrypoint or ("websecure" if payload.auto_ssl else "web"),
                "auto_ssl": bool(payload.auto_ssl),
                "redirect_to_https": bool(payload.redirect_to_https),
                "notes": payload.notes,
                "updated_at": ts,
            }
        )
        history = entry.setdefault("history", [])
        history.append(
            {
                "action": "provisioned" if existing is None else "updated",
                "at": ts,
                "target": target_service or target_url,
            }
        )
        if existing is None:
            domains.append(entry)
        domains.sort(key=lambda item: item["domain"])
        entry["service_name"] = entry.get("target_service") or entry.get("service_name")
        entry["router_name"] = entry.get("router_name") or entry["domain"].replace(".", "-")
        return deepcopy(entry)

    state, record = update_state(mut)
    _write_domain_dynamic_config(state.get("domains", []))
    action = "provisioned" if record and record.get("history", [{}])[-1].get("action") == "provisioned" else "updated"
    await publish(f"domains:{action}:{record.get('domain')}")
    return {"domain": record, "revision": state.get("meta", {}).get("revision")}


@app.post("/storage/date/setup")
async def setup_date_storage(payload: DateStorageRequest, x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    ts = _now_iso()
    backup_regions = list(payload.backup_regions)

    def mut(state: Dict[str, Any]):
        storage = state.setdefault("storage", {})
        record = storage.get("date_app") or {"created_at": ts}
        record.update(
            {
                "storage_engine": payload.storage_engine,
                "primary_region": payload.primary_region,
                "replicas": payload.replicas,
                "retention_days": payload.retention_days,
                "backup_regions": backup_regions,
                "analytics": payload.analytics,
                "encryption": payload.encryption,
                "notes": payload.notes,
                "status": "ready",
                "updated_at": ts,
            }
        )
        storage["date_app"] = record
        return deepcopy(record)

    state, record = update_state(mut)
    await publish("storage:date:ready")
    return {"storage": record, "revision": state.get("meta", {}).get("revision")}


@app.get("/storage/date")
async def get_date_storage(x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    state = read_state()
    return state.get("storage", {}).get("date_app", {"status": "uninitialized"})


@app.post("/agents/register")
async def register_agent(payload: AgentRegistration, x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "name is required")
    normalized_domains = _normalize_domains(payload.domains)
    capabilities = sorted(set(cap.strip().lower() for cap in payload.capabilities if cap.strip()))
    ts = _now_iso()

    def mut(state: Dict[str, Any]):
        agents = state.setdefault("agents", {})
        slug = _slugify(name)
        record = agents.get(slug) or {
            "created_at": ts,
            "history": [],
        }
        record.update(
            {
                "name": name,
                "slug": slug,
                "role": payload.role,
                "rights": payload.rights,
                "status": payload.status,
                "endpoint": payload.endpoint,
                "capabilities": capabilities,
                "domains": normalized_domains,
                "updated_at": ts,
            }
        )
        history = record.setdefault("history", [])
        history.append({"action": "registered", "at": ts})
        agents[slug] = record
        return deepcopy(record)

    _, record = update_state(mut)
    await publish(f"agent:register:{record['slug']}")
    return {"agent": record}


@app.get("/agents")
async def list_agents(x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    state = read_state()
    agents = sorted(state.get("agents", {}).values(), key=lambda item: item.get("name", ""))
    return {"agents": agents, "revision": state.get("meta", {}).get("revision")}


class AgentCreate(BaseModel):
    name: str


@app.post("/agents/create")
async def agents_create(body: AgentCreate, x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    n = body.name.strip() or f"agent-{int(time.time())}"
    ts = _now_iso()

    def mut(state: Dict[str, Any]):
        agents = state.setdefault("agents", {})
        slug = _slugify(n)
        record = agents.get(slug) or {
            "created_at": ts,
            "history": [],
        }
        record.update(
            {
                "name": n,
                "slug": slug,
                "rights": "admin",
                "role": "generalist",
                "status": "ready",
                "capabilities": record.get("capabilities", []),
                "domains": record.get("domains", []),
                "updated_at": ts,
            }
        )
        history = record.setdefault("history", [])
        history.append({"action": "ensure-admin", "at": ts})
        agents[slug] = record
        return deepcopy(record)

    _, agent = update_state(mut)
    await publish(f"agent:create:{agent['slug']}")
    return {"created": agent["name"], "rights": agent["rights"], "status": agent["status"], "slug": agent["slug"]}


@app.post("/fundraising/deploy")
async def fundraising_deploy(x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    await publish("fundraising:deploy:start")
    steps = [
        "create-landing-check",
        "email-capture-form-ready",
        "schedule-social-posts",
        "press-release-draft",
    ]
    for step in steps:
        await publish(f"fundraising:{step}")
        await asyncio.sleep(0.05)
    return {"status": "deployed", "steps": steps}


@app.post("/business/integrate")
async def business_integrate(x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    await publish("business:integrate:start")
    state = read_state()
    domains = [d.get("domain") for d in state.get("domains", []) if d.get("domain")]
    if not domains:
        domains = [d for d in os.getenv("DOMAINS", "").split(",") if d]
    await publish(f"business:domains:{domains}")
    return {"integrations": ["dashboard-proxy", "api-online"], "domains": domains}


@app.post("/admin/automate")
async def admin_automate(x_api_key: Optional[str] = Header(default=None)):
    auth(x_api_key)
    await publish("admin:automate:start")
    tasks = ["rotate-keys:planned", "backup-config:ready", "health-checks:scheduled"]
    for task in tasks:
        await publish(f"admin:{task}")
    return {"status": "ok", "tasks": tasks}
