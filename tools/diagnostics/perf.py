"""Recompute execution timing from the authoritative append-only run events."""
import argparse
import json
from pathlib import Path

def union_ms(intervals):
    total=0
    end=None
    for a,b in sorted(intervals):
        if b<a:
            raise ValueError("negative interval")
        total+=max(0,b-max(a,end if end is not None else a))
        end=max(b,end if end is not None else b)
    return total

def report(events):
    starts=[e for e in events if e.get("event")=="UI_START"]
    ends=[e for e in events if e.get("event")=="READBACK_END"]
    result={"comparable_complete_ui":len(starts)==len(ends)==1,
        "counts":{},
        "definitions":{"page_roundtrip":"top-frame navigation; API requests reported separately",
        "model_intervention":"explicit model intervention events during the UI window; absence is not a global model-call count",
        "uncovered":"time outside action timing intervals; no causal attribution"}}
    if not result["comparable_complete_ui"]:
        return result
    a,b=starts[0]["epoch_ms"],ends[0]["epoch_ms"]
    first=events.index(starts[0]);last=events.index(ends[0])
    window=events[first:last+1]
    result["counts"]={k:sum(e.get("event")==k for e in window) for k in
        ("structured_row_written","exact_picker_blocked","inner_exc")}
    nav=[e for e in window if e.get("event")=="page_navigation"]
    result["page_navigation"]={"count":len(nav) if nav else sum(e.get("action")=="goto_new_form" for e in window),
        "coverage":"top-frame navigation events" if nav else "observed goto_new_form timings only; other navigations not instrumented"}
    metrics=[e for e in events if e.get("event")=="ui_execution_metrics"]
    result["executor_metrics"]=metrics[-1] if metrics else {"model_control_interventions":0,"external_cell_commands":0,
        "basis":"single continuous entry invocation and no command dispatcher; global model calls, stdout polls and read-only diagnostics not instrumented"}
    result["global_model_calls"]=None
    result["external_diagnostic_commands"]=None
    spans=[]
    actions={}
    for e in events:
        if e.get("event")!="timing" or e.get("action")=="ui_execution":
            continue
        t0=e.get("t0_ms",0);t1=t0+e.get("dur_ms",0)
        if t0<b and t1>a:
            span=(max(a,t0),min(b,t1))
            spans.append(span)
            actions.setdefault(e["action"],[]).append(span)
    result.update(ui_seconds=(b-a)/1000,strict_pass=ends[0].get("ok") is True,
        instrumented_union_seconds=union_ms(spans)/1000,
        uncovered_seconds=((b-a)-union_ms(spans))/1000,
        actions={k:{"count":len(v),"union_seconds":union_ms(v)/1000} for k,v in actions.items()},
        target_360_seconds=(b-a)<=360000)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument("run");p.add_argument("--output-name",default="timing_report.json");a=p.parse_args()
    run=Path(a.run)
    events=[json.loads(x) for x in (run/"events.jsonl").read_text(encoding="utf-8").splitlines() if x]
    value=report(events)
    if Path(a.output_name).name!=a.output_name or not a.output_name.endswith('.json'):
        raise ValueError("JSON filename required")
    path=run/a.output_name
    if path.exists():
        raise ValueError("timing report already exists; preserve it")
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(value,ensure_ascii=False))
if __name__=="__main__":main()
