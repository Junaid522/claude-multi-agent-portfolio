"""Merge several analyze.py outputs into one stats file: python3 -I scripts/merge.py out.json a.json b.json ..."""
import json, sys, collections
from datetime import datetime

# same project seen under different folder names
ALIAS = {"Ibex-Dashboard-2-Ibex-Dashboard-2": "Ibex-Dashboard-2", "MJProjects-MJFINAL": "MJFINAL"}
out_path, *ins = sys.argv[1:]
D = [json.load(open(p)) for p in ins]

def total(k): return sum(d[k] for d in D)
def counter(k):
    c = collections.Counter()
    for d in D:
        for name, n in d[k]: c[name] += n
    return c

daily = collections.defaultdict(collections.Counter)
for d in D:
    for r in d["daily"]:
        for k, v in r.items():
            if k != "day": daily[r["day"]][k] += v
days = sorted(daily)

proj = {}
for d in D:
    for name, p in d["projects"]:
        name = ALIAS.get(name, name)
        m = proj.setdefault(name, dict(sessions=0, prompts=0, turns=0, tools=0, first=p["first"], last=p["last"],
            branches=[], titles=[], entrypoints=[], models=[], tt=collections.Counter()))
        for k in ("sessions", "prompts", "turns", "tools"): m[k] += p[k]
        m["first"] = min(m["first"], p["first"]); m["last"] = max(m["last"], p["last"])
        for k in ("branches", "titles", "entrypoints", "models"):
            m[k] += [x for x in p[k] if x not in m[k]]
        for t, n in p["top_tools"]: m["tt"][t] += n
projects = []
for name, m in proj.items():
    span = (datetime.fromisoformat(m["last"]) - datetime.fromisoformat(m["first"])).days + 1
    m["active_days"] = min(span, sum(p["active_days"] for d in D for n, p in d["projects"] if ALIAS.get(n, n) == name))
    m["top_tools"] = m.pop("tt").most_common(5)
    projects.append([name, m])
projects.sort(key=lambda x: -x[1]["prompts"])

tok = collections.Counter()
for d in D:
    for k, v in d["output_tokens_by_model"].items(): tok[k] += v
out = dict(generated=datetime.now().astimezone().isoformat(timespec="seconds"),
    first_day=days[0], last_day=days[-1], active_days=len(days),
    **{k: total(k) for k in ("sessions", "prompts", "assistant_turns", "subagent_turns", "tool_calls", "pr_links", "subagent_runs")},
    daily=[dict(day=x, **daily[x]) for x in days], tools=counter("tools").most_common(15),
    models=counter("models").most_common(), output_tokens_by_model=dict(tok),
    permission_modes=counter("permission_modes").most_common(), entrypoints=counter("entrypoints").most_common(),
    hours=[sum(d["hours"][h] for d in D) for h in range(24)], projects=projects,
    versions=max(d["versions"] for d in D), platform=D[0]["platform"],
    subagents=[s for d in D for s in d["subagents"]], agent_tool_calls=counter("agent_tool_calls").most_common())
json.dump(out, open(out_path, "w"), indent=1)
print({k: v for k, v in out.items() if not isinstance(v, (list, dict))})
