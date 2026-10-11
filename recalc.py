#!/usr/bin/env python3
"""Offline recalculation of the epoch-421 reward loss of
gonka1gvrrhjmy4w4mayvs2s5l23edj8ertcmtd2v4zr.

No network access. Inputs are only the snapshot files in this repository:
  coefficients_snapshot.json   params, coefficients, epoch group data, delegations,
                               the chain's own estimate_bitcoin_reward for every member
  poc_snapshot.json            the participant's PoC commits, votes and the epoch's
                               time-normalisation factor

The settlement arithmetic re-implements, step by step, the chain's
CalculateParticipantBitcoinRewardsWithTransfers (inference-chain/x/inference/keeper/
bitcoin_rewards.go, types/weight.go, module/delegation_weight_adjustment.go,
module/delegation_weight_calculator.go). The self-check reproduces the chain's
estimate_bitcoin_reward for every epoch-421 member before any counterfactual is
computed; if it does not match, the loss figure must not be used.

Usage:
  python3 recalc.py                       provisional figure (epoch 421 still open)
  python3 recalc.py --ref-epoch 420       use the 420 per-node weights instead of the 421 commits
  python3 recalc.py --missing deepseek-ai/DeepSeek-V4-Flash-0731=3522 ...
  python3 recalc.py --settled snapshots/settled
                                          final figure, from snapshots taken after epoch 421 settled
                                          (see README "Final figure")
  python3 recalc.py --settled snapshots/settled --joint
                                          requested figure: one joint counterfactual (participant at
                                          confirmation ratio 1, its delegators' edges valid, T recomputed
                                          once) and the settled loss of every recipient
  python3 recalc.py --json                machine-readable output
"""
import argparse
import json
import os
import re
import sys
from decimal import Decimal, getcontext, ROUND_DOWN

getcontext().prec = 60
ADDR = "gonka1gvrrhjmy4w4mayvs2s5l23edj8ertcmtd2v4zr"
EPOCH = 421
NGONKA = 10**9
P = "/productscience/inference/inference"
HERE = os.path.dirname(os.path.abspath(__file__))


def dec(d):
    return None if d is None else Decimal(int(d["value"])) * (Decimal(10) ** int(d["exponent"]))


def trunc(x):
    return int(Decimal(x).to_integral_value(rounding=ROUND_DOWN))


def fixed_epoch_reward(epoch, bp):
    # bitcoin_rewards.go: F = IntPart(initial_epoch_reward * exp(decay_rate)^(epoch - genesis_epoch))
    return trunc(Decimal(int(bp["initial_epoch_reward"])) * dec(bp["decay_rate"]).exp() ** (epoch - int(bp["genesis_epoch"])))


def optimal_cap(weights, maxpct=Decimal("0.30")):
    # bitcoin_rewards.go ApplyPowerCappingForWeights: no participant above 30% of the capped total
    pos = sorted(w for w in weights.values() if w > 0)
    n = len(pos)
    if n <= 1:
        return dict(weights)
    if n < 4:
        maxpct = {2: Decimal("0.5"), 3: Decimal("0.4")}[n]
    cap, s = -1, 0
    for k, p in enumerate(pos):
        if Decimal(p) > maxpct * (s + p * (n - k)):
            den = 1 - maxpct * (n - k)
            cap = p if den <= 0 else trunc(maxpct * s / den)
            break
        s += p
    if cap <= 0:
        return dict(weights)
    return {a: min(w, cap) for a, w in weights.items()}


def settle(parts, F, models, members, delegs, refusals, share, pen_none, pen_ref, zeroed=frozenset()):
    """parts: addr -> {weight, cw, raw_cw}. zeroed: addresses the chain settled at zero
    (downtime punishment / non-ACTIVE status), applied after capping as the chain does."""
    full = {a: max(p["weight"], 0) for a, p in parts.items()}
    T = sum(full.values())                                   # denominator, never renormalised
    eff = {}
    for a, p in parts.items():
        if p["weight"] <= 0:
            continue
        # types/weight.go EffectiveConfirmedWeight: weight * confirmation_weight / raw_confirmation_weight
        w, cw, raw = p["weight"], max(p["cw"], 0), p["raw_cw"]
        e = 0 if raw <= 0 else (w if cw >= raw else cw * w // raw)
        eff[a] = min(e, full[a])
    pw = optimal_cap(eff)
    for a in zeroed:
        if a in pw:
            pw[a] = 0
    participates = {a for a, w in full.items() if w > 0}
    # delegation_weight_calculator.go ResolveGroupParticipation
    modes = {}
    for m in models:
        mem = members.get(m, set())
        mm = {}
        for a in sorted(participates):
            if a in mem:
                mm[a] = "direct"
            elif a in refusals.get(m, set()):
                mm[a] = "refuse"
            elif a in delegs.get(m, {}):
                t = delegs[m][a]
                mm[a] = "delegate" if (t in mem and t in participates) else "none"
            else:
                mm[a] = "none"
        modes[m] = mm
    # delegation_weight_adjustment.go AccumulateDelegationPenalties
    frac = {}
    for m in models:
        for a, md in modes[m].items():
            if md == "refuse":
                frac[a] = frac.get(a, Decimal(0)) + pen_ref
            elif md == "none":
                frac[a] = frac.get(a, Decimal(0)) + pen_none
    # bitcoin_rewards.go applyDelegationRewardPenalties
    base = dict(pw)
    for a, f in frac.items():
        if a in pw:
            pw[a] -= min(trunc(min(f, Decimal(1)) * base[a]), pw[a])
    # delegation_weight_adjustment.go BuildDelegationRewardTransfers + bitcoin_rewards.go applyDelegationRewardTransfers
    transfers = sorted((a, delegs[m][a], m) for m in models for a in modes[m] if modes[m][a] == "delegate")
    base = dict(pw)
    inbound = {}
    for frm, to, m in transfers:
        if frm not in pw:
            continue
        amt = min(trunc(share * base[frm]), pw[frm])
        if amt == 0:
            continue
        pw[frm] -= amt
        if pw.get(to, 0) > 0:
            pw[to] += amt
            inbound.setdefault(to, []).append((frm, m, amt))
    out = {}
    for a in full:
        w = pw.get(a, 0)
        out[a] = dict(reward=(w * F // T) if w > 0 else 0, reward_weight=w, penalty=frac.get(a, Decimal(0)),
                      inbound=inbound.get(a, []), modes={m: modes[m].get(a) for m in models}, T=T,
                      effective=eff.get(a, 0))
    return out


def gnk(n):
    return f"{Decimal(n) / NGONKA:,.9f}"


def joint_report(say, parts, cf_parts, actual, cf, chain, delegs, models, zeroed):
    """--joint: the counterfactual `cf` is already one joint scenario for the whole epoch (the participant
    back in both subgroups, so every delegation edge to it resolves to DELEGATE; one T). This reports the
    settled loss of every address against the chain's rewarded_coins."""
    out_of = [m for m in models if actual[ADDR]["modes"][m] != "direct"]
    edges = sorted((frm, m) for m in out_of for frm, to in delegs.get(m, {}).items() if to == ADDR)
    live = [(f, m) for f, m in edges if f not in zeroed]
    say("")
    say(f"JOINT COUNTERFACTUAL: one scenario for the epoch, T {actual[ADDR]['T']} -> {cf[ADDR]['T']} (recomputed once)")
    say(f"  delegation edges to {ADDR} in the models it was voted out of: {len(edges)} from "
        f"{len({f for f, _ in edges})} addresses ({len(live)} from {len({f for f, _ in live})} not settled at zero)")
    for frm, m in edges:
        say(f"    {frm} {m}: actual {actual[frm]['modes'][m]} -> counterfactual {cf[frm]['modes'][m]}"
            + ("  (settled at zero by the chain: downtime/status)" if frm in zeroed else ""))
    say("  delegators to the participant (own settled confirmation ratio kept):")
    for frm in sorted({f for f, _ in edges}):
        p, A_, C_ = parts[frm], actual[frm], cf[frm]
        say(f"    {frm}: weight {p['weight']} cw/raw {p['cw']}/{p['raw_cw']} effective {A_['effective']}; "
            f"penalty {A_['penalty']} -> {C_['penalty']}; reward weight {A_['reward_weight']} -> {C_['reward_weight']}"
            + ("; zeroed before penalties and transfers" if frm in zeroed else ""))
    say("")
    say("  PER-ADDRESS (ngonka; actual = chain rewarded_coins, model = recalculated actual)")
    say(f"  {'address':<45} {'actual':>16} {'model':>16} {'counterfactual':>16} {'cf - actual':>16}")
    rows, gain, lose = [], {}, {}
    for x in sorted(parts):
        act = chain.get(x, actual[x]["reward"])
        d = cf[x]["reward"] - act
        rows.append(dict(address=x, actual=act, model=actual[x]["reward"], counterfactual=cf[x]["reward"], delta=d))
        say(f"  {x:<45} {act:>16} {actual[x]['reward']:>16} {cf[x]['reward']:>16} {d:>+16}")
        if d > 0:
            gain[x] = d
        elif d < 0:
            lose[x] = d
    total = sum(gain.values())
    say("")
    say("  RECIPIENTS: settled loss = counterfactual - actual")
    for x in sorted(gain, key=lambda k: -gain[k]):
        say(f"    {x}  {cf[x]['reward']} - {chain.get(x, actual[x]['reward'])} = {gain[x]} ngonka = {gnk(gain[x])} GNK")
    say(f"    TOTAL {total} ngonka = {gnk(total)} GNK across {len(gain)} recipients")
    say("  LOWER IN THE COUNTERFACTUAL (not recipients, nothing clawed back):")
    for x in sorted(lose, key=lambda k: lose[k]):
        say(f"    {x}  {lose[x]} ngonka = {gnk(lose[x])} GNK")
    say(f"    total {sum(lose.values())} ngonka = {gnk(sum(lose.values()))} GNK across {len(lose)} addresses")
    return dict(T_actual=actual[ADDR]["T"], T_counterfactual=cf[ADDR]["T"], edges=edges, rows=rows,
                delegators={f: dict(penalty_actual=str(actual[f]["penalty"]), penalty_counterfactual=str(cf[f]["penalty"]),
                                    reward_weight_actual=actual[f]["reward_weight"],
                                    reward_weight_counterfactual=cf[f]["reward_weight"], zeroed=f in zeroed)
                            for f in sorted({f for f, _ in edges})},
                recipients=gain, total_ngonka=total, total_gnk=str(Decimal(total) / NGONKA), lower=lose)


def fname(route):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", route.strip("/"))[:200] + ".json"


def load_settled(d, members):
    """Raw files fetched with tools/fetch.py after epoch 421 settled (see README)."""
    def L(route, required=True):
        p = os.path.join(d, fname(route))
        if not os.path.exists(p):
            if required:
                sys.exit(f"--settled: missing {p} (fetch route {route})")
            return None
        with open(p) as f:
            return json.load(f)
    g = L(f"{P}/epoch_group_data/{EPOCH}")
    rewarded, heights = {}, [g["query_height"]]
    for a in members:
        r = L(f"{P}/epoch_performance_summary/{EPOCH}/{a}", required=False)
        if r and r["http_status"] == 200:
            rewarded[a] = int(r["body"]["epochPerformanceSummary"]["rewarded_coins"])
            heights.append(r["query_height"])
    cpoc = L(f"{P}/confirmation_poc_events/{EPOCH}", required=False)
    return dict(group=g["body"]["epoch_group_data"], rewarded=rewarded,
                cpoc_events=(cpoc or {}).get("body"), heights=(min(heights), max(heights)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=HERE, help="directory holding the snapshot files")
    ap.add_argument("--ref-epoch", type=int, choices=[EPOCH - 1],
                    help="take the missing per-model raw weight from the 420 subgroup instead of the 421 commits")
    ap.add_argument("--missing", action="append", default=[], help="override MODEL=RAW_POC_WEIGHT")
    ap.add_argument("--settled", help="directory with raw snapshots taken after epoch 421 settled")
    ap.add_argument("--cf-cw-ratio", type=Decimal,
                    help="settled mode: confirmed/raw ratio for the counterfactual weight "
                         "(default: the participant's own settled ratio)")
    ap.add_argument("--joint", action="store_true",
                    help="settled mode: one joint counterfactual for the epoch (participant at confirmation "
                         "ratio 1 unless --cf-cw-ratio is given, every delegation edge to it valid) and a "
                         "settled loss per address")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.joint and not a.settled:
        ap.error("--joint needs --settled")
    if a.joint and a.cf_cw_ratio is None:
        a.cf_cw_ratio = Decimal(1)

    with open(os.path.join(a.dir, "coefficients_snapshot.json")) as f:
        C = json.load(f)
    with open(os.path.join(a.dir, "poc_snapshot.json")) as f:
        PS = json.load(f)
    log = []
    say = log.append

    bp, dp = C["bitcoin_reward_params"], C["delegation_params"]
    share, pen_none, pen_ref = dec(dp["delegation_share"]), dec(dp["no_participation_penalty"]), dec(dp["refusal_penalty"])
    pstart = {m["model_id"]: int(m.get("penalty_start_epoch") or 0) for m in C["poc_params"]["models"]}
    g = C["epoch_group_data_421"]
    settled = None
    if a.settled:
        settled = load_settled(a.settled, [v["member_address"] for v in g["validation_weights"]])
        g = settled["group"]          # post-confirmation-PoC confirmation weights
    models = list(g["sub_group_models"])
    eligible = [m for m in models if EPOCH >= pstart.get(m, 0)]
    coeff = {s["model_id"]: dec(s["effective_coefficient"] or s["weight_scale_factor"])
             for s in C["confirmation_weight_scales"] if not s.get("exclude_from_confirmation")}
    subs = C["epoch_group_data_421_per_model"]
    members = {m: {v["member_address"] for v in subs[m]["validation_weights"]} for m in models}
    raw_by = {}
    for m in models:
        for v in subs[m]["validation_weights"]:
            raw_by.setdefault(v["member_address"], {})[m] = sum(int(n["poc_weight"]) for n in v["ml_nodes"])

    def raw_cw(addr, rb):
        return sum(trunc(coeff[m] * r) for m, r in rb.get(addr, {}).items() if m in coeff)

    parts = {v["member_address"]: dict(weight=int(v["weight"]), cw=int(v["confirmation_weight"]),
                                       raw_cw=raw_cw(v["member_address"], raw_by)) for v in g["validation_weights"]}
    delegs, refusals = {}, {}
    for addr, d in C["poc_delegation"].items():
        for x in (d or {}).get("delegations", []):
            delegs.setdefault(x["model_id"], {})[x["delegator"]] = x["delegate_to"]
        for x in (d or {}).get("refusals", []):
            refusals.setdefault(x.get("model_id"), set()).add(x.get("participant") or addr)
    F = fixed_epoch_reward(EPOCH, bp)

    say(f"INPUTS (coefficients_snapshot.json heights {C['heights']}, poc_snapshot.json heights {PS['heights']})")
    say(f"  F = trunc({bp['initial_epoch_reward']} * exp({dec(bp['decay_rate'])})^({EPOCH}-{bp['genesis_epoch']})) = {F} ngonka = {F/NGONKA:,.6f} GNK")
    say(f"  coefficients: " + ", ".join(f"{m}={c}" for m, c in coeff.items()))
    say(f"  eligible models (penalty_start_epoch <= {EPOCH}): {eligible}")
    say(f"  delegation_share={share} no_participation_penalty={pen_none} refusal_penalty={pen_ref}")
    say(f"  members: {len(parts)}, T = sum of member weights = {sum(max(p['weight'],0) for p in parts.values())}")
    say(f"  delegation records: {sum(len(v) for v in delegs.values())}, refusals: {sum(len(v) for v in refusals.values())}")

    # ---------------- self-check ----------------
    zeroed = set()
    if settled:
        chain = settled["rewarded"]
        src = f"epoch_performance_summary.rewarded_coins (settled, heights {settled['heights']})"
        pre = settle(parts, F, eligible, members, delegs, refusals, share, pen_none, pen_ref)
        zeroed = {x for x, r in chain.items() if r == 0 and pre[x]["reward"] > 0}
    else:
        chain = {}
        for x, r in C["estimate_bitcoin_reward"].items():
            if r and int(r["settle_amount"]["epoch_index"]) == EPOCH:
                chain[x] = int(r["settle_amount"]["reward_coins"])
        src = "estimate_bitcoin_reward (live estimate while epoch 421 is open)"
    actual = settle(parts, F, eligible, members, delegs, refusals, share, pen_none, pen_ref, zeroed)
    exact = sum(1 for x in chain if actual[x]["reward"] == chain[x])
    within1 = sum(1 for x in chain if abs(actual[x]["reward"] - chain[x]) <= 1)
    mism = {x: (actual[x]["reward"], chain[x]) for x in chain if abs(actual[x]["reward"] - chain[x]) > 1}
    say("")
    say(f"SELF-CHECK against {src}")
    say(f"  {len(chain)} members compared: {exact} exact, {within1} within 1 ngonka")
    if zeroed:
        say(f"  settled at zero by the chain (downtime/status), applied after capping: {sorted(zeroed)}")
    for x, (mo, ch) in mism.items():
        say(f"  MISMATCH {x}: model {mo} chain {ch} ({(mo-ch)/max(ch,1)*100:+.3f}%)")

    # ---------------- counterfactual ----------------
    missing, basis = {}, ""
    if a.missing:
        for s in a.missing:
            m, r = s.rsplit("=", 1)
            missing[m] = int(r)
        basis = "--missing override"
    elif a.ref_epoch:
        for m, row in PS["epochs"][str(a.ref_epoch)]["epoch_group_data_per_model"].items():
            if m in models and ADDR not in members[m] and row["participant_is_member"]:
                missing[m] = row["raw_poc_weight_sum"]
        basis = f"per-node poc_weight of the participant in the epoch-{a.ref_epoch} subgroup"
    else:
        tnf = PS["time_normalization_factor_421"]
        for m, row in tnf["implied_raw_poc_weight_for_participant_commits"].items():
            if m in models and ADDR not in members[m]:
                v = row["implied_raw_poc_weight"]
                if isinstance(v, list):
                    sys.exit(f"time-normalisation bracket does not pin {m}: {v}; use --missing")
                missing[m] = v
        basis = (f"epoch-421 store commit count x time-normalisation factor f in "
                 f"[{tnf['f_lower']}, {tnf['f_upper']}] (bracketed from {tnf['rows_used']} node rows)")
    cf_parts = json.loads(json.dumps(parts))
    cf_members = {m: set(s) for m, s in members.items()}
    cf_raw = json.loads(json.dumps(raw_by))
    added = 0
    say("")
    say(f"COUNTERFACTUAL: {ADDR} is a member of the subgroups it was voted out of")
    say(f"  basis for the missing raw PoC weight: {basis}")
    for m, r in missing.items():
        cf_members.setdefault(m, set()).add(ADDR)
        cf_raw.setdefault(ADDR, {})[m] = r
        w = trunc(coeff[m] * r)
        added += w
        say(f"  {m}: raw {r} -> trunc({coeff[m]} * {r}) = {w} weight")
    me = parts[ADDR]
    p = cf_parts[ADDR]
    p["weight"] += added
    p["raw_cw"] = raw_cw(ADDR, cf_raw)
    if settled:
        ratio = a.cf_cw_ratio if a.cf_cw_ratio is not None else (
            Decimal(me["cw"]) / Decimal(me["raw_cw"]) if me["raw_cw"] else Decimal(1))
        p["cw"] = min(trunc(ratio * p["raw_cw"]), p["raw_cw"]) if ratio < 1 else p["weight"]
        say(f"  confirmation ratio applied to the counterfactual weight: {ratio} "
            f"({'override' if a.cf_cw_ratio is not None else 'participant settled cw/raw_cw'})")
    else:
        # at epoch formation the chain sets confirmation_weight = weight for every member
        p["cw"] = p["weight"] if me["cw"] >= me["raw_cw"] else me["cw"]
    cf = settle(cf_parts, F, eligible, cf_members, delegs, refusals, share, pen_none, pen_ref, zeroed)

    A_, Cf = actual[ADDR], cf[ADDR]
    chain_me = chain.get(ADDR)
    actual_reward = chain_me if chain_me is not None else A_["reward"]
    loss = Cf["reward"] - actual_reward
    say("")
    say("ACTUAL (as recorded)")
    say(f"  weight {me['weight']}  confirmation_weight {me['cw']}  raw_confirmation_weight {me['raw_cw']}")
    say(f"  effective = {A_['effective']}; subgroup modes {A_['modes']}")
    say(f"  penalty fraction {A_['penalty']} -> reward weight after penalties and transfers {A_['reward_weight']}")
    say(f"  inbound transfers {sum(x[2] for x in A_['inbound'])} from {len(A_['inbound'])} delegations")
    say(f"  reward = trunc({A_['reward_weight']} * {F} / {A_['T']}) = {A_['reward']} ngonka (chain: {chain_me})")
    say("COUNTERFACTUAL")
    say(f"  weight {p['weight']}  confirmation_weight {p['cw']}  raw_confirmation_weight {p['raw_cw']}")
    say(f"  effective = {Cf['effective']}; subgroup modes {Cf['modes']}")
    say(f"  penalty fraction {Cf['penalty']} -> reward weight {Cf['reward_weight']}")
    say(f"  inbound transfers {sum(x[2] for x in Cf['inbound'])} from {len(Cf['inbound'])} delegations: "
        + ", ".join(f"{f_[:14]}..{m.split('/')[-1]}={amt}" for f_, m, amt in Cf["inbound"]))
    say(f"  reward = trunc({Cf['reward_weight']} * {F} / {Cf['T']}) = {Cf['reward']} ngonka")
    say("")
    say(f"LOSS = counterfactual - actual = {Cf['reward']} - {actual_reward} = {loss} ngonka = {loss/NGONKA:,.9f} GNK")
    # where the counterfactual reward weight comes from, in reward-weight units
    pen_w = A_["effective"] - trunc(min(A_["penalty"], Decimal(1)) * A_["effective"])
    say(f"  decomposition of reward weight {A_['reward_weight']} -> {Cf['reward_weight']}: "
        f"own DeepSeek/GLM weight +{Cf['effective'] - A_['effective']}, "
        f"no-participation penalty lifted +{A_['effective'] - pen_w}, "
        f"inbound delegation transfers +{sum(x[2] for x in Cf['inbound']) - sum(x[2] for x in A_['inbound'])}; "
        f"denominator T {A_['T']} -> {Cf['T']}")
    others = {}
    say("")
    say("OTHER MEMBERS: reward change in the counterfactual (ngonka; delegators to this address lose their own penalty too)")
    for x in parts:
        if x != ADDR and cf[x]["reward"] != actual[x]["reward"]:
            others[x] = cf[x]["reward"] - actual[x]["reward"]
            say(f"  {x}: {others[x]:+d}")
    joint = None
    if a.joint:
        joint = joint_report(say, parts, cf_parts, actual, cf, chain, delegs, eligible, zeroed)
    if not chain or not all(abs(actual[x]["reward"] - chain[x]) <= 1 for x in chain):
        say("\nWARNING: self-check failed; do not use the loss figure.")
    res = dict(address=ADDR, epoch=EPOCH, mode="settled" if settled else "provisional", reward_source=src,
               F=F, self_check=dict(compared=len(chain), exact=exact, within_1=within1, mismatches=mism),
               missing_raw=missing, added_weight=added, basis=basis,
               actual=dict(weight=me["weight"], cw=me["cw"], reward_weight=A_["reward_weight"],
                           penalty=str(A_["penalty"]), model_reward=A_["reward"], chain_reward=chain_me, T=A_["T"]),
               counterfactual=dict(weight=p["weight"], cw=p["cw"], reward_weight=Cf["reward_weight"],
                                   penalty=str(Cf["penalty"]), inbound=Cf["inbound"], reward=Cf["reward"], T=Cf["T"]),
               loss_ngonka=loss, loss_gnk=str(Decimal(loss) / NGONKA), others_delta_ngonka=others)
    if joint is not None:
        res["joint"] = joint
    if a.json:
        print(json.dumps(res, indent=1, default=str))
    else:
        print("\n".join(log))


if __name__ == "__main__":
    main()
