#!/usr/bin/env python3
"""Build poc_snapshot.json and coefficients_snapshot.json from snapshots/raw/.
Offline: reads only files already fetched by tools/fetch.py.

Usage: build_snapshots.py REPO_DIR
"""
import glob, json, os, re, sys
from fractions import Fraction

ADDR = "gonka1gvrrhjmy4w4mayvs2s5l23edj8ertcmtd2v4zr"
EPOCH = 421
P = "/productscience/inference/inference"


def fname(route):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", route.strip("/"))[:200] + ".json"


def load(raw, route):
    path = os.path.join(raw, fname(route))
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def meta(rec, raw):
    return {"route": rec["route"], "file": os.path.join("snapshots/raw", fname(rec["route"])),
            "http_status": rec["http_status"], "query_height": rec["query_height"],
            "block_time_at_query": rec["latest_block_before_query"]["time"],
            "fetched_at_utc": rec["fetched_at_utc"], "node": rec["node"]}


def q(m):
    return m.replace("/", "%2F")


def main(repo):
    raw = os.path.join(repo, "snapshots", "raw")
    L = lambda r: load(raw, r)
    eg = {e: L(f"{P}/epoch_group_data/{e}") for e in (EPOCH - 1, EPOCH)}
    start = {e: eg[e]["body"]["epoch_group_data"]["poc_start_block_height"] for e in eg}
    models = eg[EPOCH]["body"]["epoch_group_data"]["sub_group_models"]
    sources = []

    def use(rec):
        if rec is not None:
            sources.append(meta(rec, raw))
        return rec

    # ---------- poc_snapshot ----------
    per_epoch = {}
    for e in (EPOCH - 1, EPOCH):
        commits = use(L(f"{P}/all_poc_v2_store_commits/{start[e]}"))
        dists = use(L(f"{P}/all_mlnode_weight_distributions/{start[e]}"))
        vals = use(L(f"{P}/poc_v2_validations_for_stage/{start[e]}"))
        mine_c = [c for c in commits["body"]["commits"] if c["participant_address"] == ADDR]
        mine_d = [d for d in dists["body"]["distributions"] if d["participant_address"] == ADDR]
        votes = {}
        for v in vals["body"]["poc_validation"]:
            if v["participant"] != ADDR:
                continue
            ws = [int(x["validated_weight"]) for x in v["poc_validation"]]
            votes[v["model_id"]] = {"validators": len(ws), "valid_votes(validated_weight>0)": sum(w > 0 for w in ws),
                                    "invalid_votes(validated_weight<=0)": sum(w <= 0 for w in ws),
                                    "validated_weight_values": sorted(set(ws)),
                                    "by_validator": {x["validator_participant_address"]: int(x["validated_weight"]) for x in v["poc_validation"]}}
        groups = {}
        for m in models + [x for x in eg[e]["body"]["epoch_group_data"]["sub_group_models"] if x not in models]:
            g = use(L(f"{P}/epoch_group_data/{e}?model_id={q(m)}"))
            if g is None:
                continue
            gd = g["body"]["epoch_group_data"]
            row = [v for v in gd["validation_weights"] if v["member_address"] == ADDR]
            groups[m] = {"members": len(gd["validation_weights"]), "participant_is_member": bool(row),
                         "participant_row": row[0] if row else None,
                         "raw_poc_weight_sum": sum(int(n["poc_weight"]) for n in row[0]["ml_nodes"]) if row else 0}
        per_epoch[str(e)] = {
            "poc_stage_start_block_height": int(start[e]),
            "store_commits": mine_c or ("none returned (pruned or no commit)" if not commits["body"]["commits"] else []),
            "store_commits_total_rows_in_stage": len(commits["body"]["commits"]),
            "mlnode_weight_distributions": mine_d or ("none returned" if not dists["body"]["distributions"] else []),
            "validations": votes or ("none returned (pruned)" if not vals["body"]["poc_validation"] else {}),
            "epoch_group_data_per_model": groups,
        }

    # time normalisation factor of the 421 stage, bracketed from every node row:
    # poc_weight = trunc(count * f)  (chainvalidation.go calculateParticipantWeight)
    d421 = L(f"{P}/all_mlnode_weight_distributions/{start[EPOCH]}")["body"]["distributions"]
    lo, hi, n = Fraction(0), Fraction(10), 0
    for m in models:
        gd = L(f"{P}/epoch_group_data/{EPOCH}?model_id={q(m)}")["body"]["epoch_group_data"]
        for v in gd["validation_weights"]:
            dist = {w["node_id"]: int(w["weight"]) for x in d421 if x["participant_address"] == v["member_address"]
                    and x["model_id"] == m for w in x["weights"]}
            for nd in v["ml_nodes"]:
                c, p = dist.get(nd["node_id"]), int(nd["poc_weight"])
                if c:
                    n += 1
                    lo, hi = max(lo, Fraction(p, c)), min(hi, Fraction(p + 1, c))
    implied = {}
    for c in per_epoch[str(EPOCH)]["store_commits"]:
        a, b = (c["count"] * lo).__floor__(), ((c["count"] * hi) - Fraction(1, 10**12)).__floor__()
        implied[c["model_id"]] = {"commit_count": c["count"], "implied_raw_poc_weight": a if a == b else [a, b]}

    part = use(L(f"{P}/participant/{ADDR}"))
    hw = use(L(f"{P}/hardware_nodes/{ADDR}"))
    cpoc = use(L(f"{P}/confirmation_poc_events/{EPOCH}"))
    act = use(L(f"{P}/active_confirmation_poc_event"))
    snap = use(L(f"{P}/poc_validation_snapshot/{start[EPOCH]}"))
    excl = use(L(f"{P}/excluded_participants/{EPOCH}"))
    not_impl = []
    for r in glob.glob(os.path.join(raw, "*.json")):
        rec = json.load(open(r))
        if rec["http_status"] == 501:
            not_impl.append(rec["route"])

    poc = {
        "description": f"What the chain recorded about the PoC of {ADDR} in epochs {EPOCH-1} and {EPOCH}. "
                       "All values are copied from the raw REST responses listed in 'sources'.",
        "participant": ADDR, "epoch": EPOCH,
        "heights": {"min": min(s["query_height"] for s in sources), "max": max(s["query_height"] for s in sources)},
        "epochs": per_epoch,
        "time_normalization_factor_421": {
            "method": "poc_weight = trunc(commit_count * f) for every (participant, model, node) row of epoch 421; "
                      "f is bracketed by all rows (inference-chain/x/inference/module/chainvalidation.go, calculateParticipantWeight)",
            "rows_used": n, "f_lower": str(float(lo)), "f_upper": str(float(hi)),
            "implied_raw_poc_weight_for_participant_commits": implied},
        "participant_record": part["body"]["participant"],
        "hardware_nodes": hw["body"],
        "confirmation_poc_events_421": cpoc["body"], "active_confirmation_poc_event": act["body"],
        "poc_validation_snapshot_421": snap["body"], "excluded_participants_421": excl["body"],
        "routes_not_implemented_on_public_gateway": sorted(not_impl) + [
            f"{P}/poc_v2_store_commit/{{height}}/{{participant}}/{{model_id}} (single-row; the all_ variant above is used instead)",
            f"{P}/mlnode_weight_distribution/{{height}}/{{participant}}/{{model_id}} (single-row; the all_ variant above is used instead)"],
        "sources": sources,
    }
    poc["routes_not_implemented_on_public_gateway"] = sorted(set(poc["routes_not_implemented_on_public_gateway"]))
    write(repo, "poc_snapshot.json", poc)

    # ---------- coefficients_snapshot ----------
    sources = []
    params = use(L(f"{P}/params"))["body"]["params"]
    dc = {e: use(L(f"{P}/dynamic_coefficients/{e}")) for e in (EPOCH - 1, EPOCH)}
    g421 = use(eg[EPOCH])["body"]["epoch_group_data"]
    members = [v["member_address"] for v in g421["validation_weights"]]
    subs = {m: use(L(f"{P}/epoch_group_data/{EPOCH}?model_id={q(m)}"))["body"]["epoch_group_data"] for m in models}
    deleg, est = {}, {}
    for a in members:
        r = use(L(f"{P}/poc_delegation/{a}"))
        deleg[a] = r["body"] if r else None
        r = use(L(f"{P}/estimate_bitcoin_reward/{a}"))
        est[a] = r["body"] if r else None
    coef = {
        "description": f"Inputs needed to recompute every epoch-{EPOCH} reward offline (see recalc.py).",
        "epoch": EPOCH,
        "heights": {"min": min(s["query_height"] for s in sources), "max": max(s["query_height"] for s in sources)},
        "confirmation_weight_scales": g421["confirmation_weight_scales"],
        "dynamic_coefficient_params": g421.get("dynamic_coefficient_params"),
        "dynamic_coefficients": {str(e): dc[e]["body"] if dc[e] else None for e in dc},
        "weight_scale_factor": {s["model_id"]: s.get("weight_scale_factor") for s in g421["confirmation_weight_scales"]},
        "bitcoin_reward_params": params["bitcoin_reward_params"],
        "delegation_params": params["delegation_params"],
        "poc_params": params["poc_params"],
        "epoch_params": params["epoch_params"],
        "validation_params": params["validation_params"],
        "epoch_group_data_421": {k: v for k, v in g421.items() if k not in ("member_seed_signatures",)},
        "epoch_group_data_421_per_model": {m: {k: v for k, v in s.items() if k != "member_seed_signatures"} for m, s in subs.items()},
        "poc_delegation": deleg,
        "estimate_bitcoin_reward": est,
        "sources": sources,
    }
    write(repo, "coefficients_snapshot.json", coef)


def write(repo, name, obj):
    with open(os.path.join(repo, name), "w") as f:
        json.dump(obj, f, indent=1, sort_keys=False)
    print("wrote", name, os.path.getsize(os.path.join(repo, name)))


if __name__ == "__main__":
    main(sys.argv[1])
