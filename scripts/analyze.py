"""Aggregate real Claude Code usage from ~/.claude/projects into docs/stats.json.
Counts only; no prompt or response text is read into the output."""
import json, glob, os, collections, sys, re
from datetime import datetime

ROOT = os.path.expanduser("~/.claude/projects")
OUT = sys.argv[1] if len(sys.argv) > 1 else "docs/stats.json"

# projects left out of every count and name in the output; one name per line in a local, untracked file
_ex = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exclude.txt")
EXCLUDE = set(open(_ex).read().split()) if os.path.exists(_ex) else set()

def proj(d):
    d = re.sub(r"^-(Users|home)-[^-]+-", "", d)
    if "Library-Application-Support-Claude" in d: return "Claude desktop scratch"
    for p in ("Documents-projects-colabrex-", "Documents-projects-wmc-", "Documents-projects-", "Downloads-"):
        if d.startswith(p): return d[len(p):] or "colabrex (root)"
    return d

sessions = {}
days = collections.defaultdict(lambda: collections.Counter())
tools = collections.Counter(); models = collections.Counter()
tok = collections.Counter(); modes = collections.Counter(); entry = collections.Counter()
subagents = []; agent_calls = collections.Counter(); prs = set()
hours = collections.Counter()
meta = collections.defaultdict(lambda: dict(branches=collections.Counter(), titles={}, days=set(), entry=collections.Counter(), tools=collections.Counter(), models=collections.Counter()))
versions = collections.Counter()

def ts(d):
    return datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).astimezone()

for f in glob.glob(ROOT + "/**/*.jsonl", recursive=True):
    rel = os.path.relpath(f, ROOT).split(os.sep)
    p = proj(rel[0])
    if p in EXCLUDE: continue
    is_sub = "subagents" in rel
    sid = rel[1].replace(".jsonl", "") if not is_sub else rel[1]
    s = sessions.setdefault(sid, dict(project=p, start=None, end=None, prompts=0, turns=0, subagent_turns=0, tools=0, out_tokens=0))
    for l in open(f):
        try: d = json.loads(l)
        except: continue
        if d.get("type") == "ai-title" and d.get("aiTitle"): meta[p]["titles"][d["aiTitle"]] = 1
        if "timestamp" not in d: continue
        t = ts(d); day = t.strftime("%Y-%m-%d")
        if not is_sub:
            s["start"] = min(filter(None, [s["start"], t.isoformat()])); s["end"] = max(filter(None, [s["end"], t.isoformat()]))
        ty = d.get("type"); mp = meta[p]
        if not is_sub:
            mp["days"].add(day)
            if d.get("gitBranch") and d["gitBranch"] != "HEAD": mp["branches"][d["gitBranch"]] += 1
            if d.get("version"): versions[d["version"]] += 1
            if d.get("entrypoint"): mp["entry"][d["entrypoint"]] += 1
        if ty == "user" and not is_sub and d.get("origin", {}).get("kind") == "human" and d.get("promptId"):
            s["prompts"] += 1; days[day]["prompts"] += 1; hours[t.hour] += 1
            modes[d.get("permissionMode", "default")] += 1
            entry[d.get("entrypoint", "unknown")] += 1
        elif ty == "assistant":
            m = d["message"]; u = m.get("usage", {})
            key = "subagent_turns" if is_sub else "turns"; s[key] += 1; days[day][key] += 1
            if m.get("model") and not m["model"].startswith("<"):
                models[m["model"]] += 1; mp["models"][m["model"]] += 1
                tok[m["model"] + "|out"] += u.get("output_tokens", 0)
            s["out_tokens"] += u.get("output_tokens", 0)
            for b in m.get("content", []) if isinstance(m.get("content"), list) else []:
                if b.get("type") == "tool_use":
                    tools[b["name"]] += 1; mp["tools"][b["name"]] += 1; s["tools"] += 1; days[day]["tools"] += 1
                    if b["name"] == "Agent":
                        agent_calls[b["input"].get("subagent_type") or "general-purpose"] += 1
        elif ty == "pr-link": prs.add(d.get("prUrl") or d.get("url") or json.dumps(d)[:80])
    if is_sub and f.endswith(".jsonl"):
        mf = f.replace(".jsonl", ".meta.json")
        if os.path.exists(mf):
            mt = json.load(open(mf)); subagents.append(dict(type=mt.get("agentType"), project=p, task=mt.get("description"), mode=mt.get("requestShape", "background/unknown")))

real = {k: v for k, v in sessions.items() if v["start"] and v["prompts"] > 0}
per_proj = collections.defaultdict(lambda: collections.Counter())
for v in real.values():
    c = per_proj[v["project"]]; c["sessions"] += 1; c["prompts"] += v["prompts"]; c["turns"] += v["turns"]; c["tools"] += v["tools"]
ordered = sorted(days)
out = dict(
    generated=datetime.now().astimezone().isoformat(timespec="seconds"),
    first_day=ordered[0], last_day=ordered[-1], active_days=len(ordered),
    sessions=len(real), prompts=sum(v["prompts"] for v in real.values()),
    assistant_turns=sum(v["turns"] for v in real.values()), subagent_turns=sum(v["subagent_turns"] for v in sessions.values()),
    tool_calls=sum(tools.values()), pr_links=len(prs), subagent_runs=len(subagents),
    daily=[dict(day=d, **days[d]) for d in ordered],
    tools=tools.most_common(15), models=models.most_common(), output_tokens_by_model={k[:-4]: v for k, v in tok.items()},
    permission_modes=modes.most_common(), entrypoints=entry.most_common(),
    hours=[hours[h] for h in range(24)],
    projects=sorted(([k, dict(v, first=min(meta[k]["days"]), last=max(meta[k]["days"]), active_days=len(meta[k]["days"]),
        branches=[b for b, _ in meta[k]["branches"].most_common(8)], titles=list(meta[k]["titles"])[:40],
        entrypoints=[e for e, _ in meta[k]["entry"].most_common()], top_tools=meta[k]["tools"].most_common(5),
        models=[m for m, _ in meta[k]["models"].most_common()])] for k, v in per_proj.items()), key=lambda x: -x[1]["prompts"]),
    versions=len(versions), platform="macOS (Darwin), Claude Code in VS Code and Claude desktop",
    subagents=subagents, agent_tool_calls=agent_calls.most_common(),
)
json.dump(out, open(OUT, "w"), indent=1)
print({k: v for k, v in out.items() if not isinstance(v, (list, dict))})
