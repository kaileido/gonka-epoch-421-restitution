# Restitution for epoch 421: PoC commits rejected by the cross-model porosity check

Status: draft. Epoch 421 settled at block 6,506,756. The requested amounts come from `python3 recalc.py --settled snapshots/settled --joint` against chain snapshots taken at blocks 6,507,164 – 6,507,167 (epoch 422). Its self-check reproduces the settled `rewarded_coins` of all 29 epoch-421 members within 1 ngonka.

This is an independent governance proposal. It is not submitted through the GRC process.

| | |
|---|---|
| Incident epoch | 421 (PoC stage starting at block 6,490,966) |
| Cause | PoC nonce stride shared across models, combined with a porosity check applied per model; fix proposed in [gonka-ai/gonka#1978](https://github.com/gonka-ai/gonka/pull/1978) |
| Address voted out | `gonka1gvrrhjmy4w4mayvs2s5l23edj8ertcmtd2v4zr` (DeepSeek-V4-Flash-0731 and GLM-5.3-Flash subgroups) |
| Recipients | 5: that address and the four addresses whose delegations to it were voided by the incident |
| Requested total | 32,723.422557135 GNK (32,723,422,557,135 ngonka) |
| Computed by | `python3 recalc.py --settled snapshots/settled --joint`, output in `outputs/recalc-settled-joint.out` |
| Snapshots | blocks 6,493,182 – 6,493,251, 2026-10-10 22:38 UTC (epoch 421 open); settled: `snapshots/settled/`, blocks 6,507,164 – 6,507,167, 2026-10-11 19:17 UTC |

## Requested amounts

| Recipient | Amount (ngonka) | Amount (GNK) |
|---|---:|---:|
| `gonka1gvrrhjmy4w4mayvs2s5l23edj8ertcmtd2v4zr` | 25,543,824,728,805 | 25,543.824728805 |
| `gonka1scskt6wpnjnumsah6kjphmdu87vjgvcxmn4rxv` | 5,765,476,743,246 | 5,765.476743246 |
| `gonka1w63xj0j6wxn5w4yuquuckqwmmdyf930pwdy5wh` | 1,360,462,307,311 | 1,360.462307311 |
| `gonka1346p2h8dn4kp98c5e93k5q64g0h7vxjxnd55fh` | 43,095,726,979 | 43.095726979 |
| `gonka1w29nvdy6caqtrw30whz9h6ghl0xszwh3egndah` | 10,563,050,794 | 10.563050794 |
| Total | 32,723,422,557,135 | 32,723.422557135 |

Each amount is the reward the address would have received in epoch 421 without the incident minus the reward the chain actually paid it. The derivation per address is in [Derivation per recipient](#derivation-per-recipient).

## Summary

In epoch 421 the address `gonka1gvrrhjmy4w4mayvs2s5l23edj8ertcmtd2v4zr` stored PoC commits for three models: `MiniMaxAI/MiniMax-M2.7`, `deepseek-ai/DeepSeek-V4-Flash-0731` and `zai-org/GLM-5.3-Flash`. The DeepSeek and GLM commits were voted invalid by all 24 validators that voted on them, and the address is absent from both of those subgroups for epoch 421. Its MiniMax commit was accepted by 23 of 23 and it is a member of the MiniMax subgroup. In epoch 420 the same address was a member of all three subgroups with one node each for DeepSeek and GLM.

The rejection is explained by a defect in how nonces were numbered, which [gonka-ai/gonka#1978](https://github.com/gonka-ai/gonka/pull/1978) fixes (see [Cause](#cause)).

Being left out of two subgroups cost the address far more than the two models' own weight, and it also cost the addresses that delegate those models to it:

- The address lost its own DeepSeek and GLM weight (6,218 weight).
- For each eligible model where an address is neither a member nor a valid delegator, the chain deducts 0.15 of its whole reward weight. Two models add up to 0.30 for this address, and the deduction also hits its MiniMax weight.
- A delegation transfers 5% of the delegator's weight to the target only when the target is a member of that model's subgroup. With the target out of both subgroups, every DeepSeek and GLM delegation to it became invalid. The chain then treats each such delegator as a non-participant for that model: it does not transfer the 5% and instead takes the 0.15 no-participation penalty itself.
- The address's confirmation PoC ratio for epoch 421 settled at 0.72235. The counterfactual attributes that shortfall to the same incident and uses ratio 1 for this address.

## Cause

Validators check porosity, the highest nonce in a commit divided by the number of nonces in it, separately for each model commit, and vote the commit invalid above a fixed threshold (`decentralized-api/poc/validator.go`, `isPorosityTooHigh`). Porosity is computed off-chain by each validator, so the chain records only the result: the votes with `validated_weight = -1`.

The API node gave each ML node a nonce stride equal to the host's total number of node slots across all models, not across the nodes of that model. A model served by a single node therefore received a nonce sequence with gaps roughly as wide as the host's total slot count, and its per-model porosity rose with every node the host added for other models. [gonka-ai/gonka#1978](https://github.com/gonka-ai/gonka/pull/1978) ("fix(poc): prevent cross-model nonce gaps from failing porosity") assigns node numbers and node counts per model, so a single-node model gets `node_id=0, node_count=1`.

The chain data is consistent with that mechanism:

- In epoch 421 the address's DeepSeek and GLM commits each came from a single node (`CA-LA-1` with 4,000 nonces and `vs-glm-4b200-6` with 8,768 nonces, per `all_mlnode_weight_distributions/6490966`).
- The same two nodes were members of the DeepSeek and GLM subgroups in epoch 420 (raw PoC weight 3,506 and 7,433), so the same setup passed one epoch earlier.
- Between the two epochs the address's MiniMax subgroup row grew from 14 to 41 ML nodes, which raises the host's total slot count and with it the stride given to the single DeepSeek and GLM nodes.
- Every validator runs the same check, so the commits were rejected unanimously (0 valid, 24 invalid on each), while the multi-node MiniMax commit passed unanimously.

Check the status of PR 1978 before voting. Until it is deployed, the same configuration fails again in every epoch.

## Basis of the joint counterfactual

The amounts come from one counterfactual settlement of the whole epoch, computed once and compared address by address with what the chain settled.

1. `gonka1gvrrhjmy4w4mayvs2s5l23edj8ertcmtd2v4zr` is a member of the DeepSeek and GLM subgroups with the weight its own epoch-421 commits would have received (3,522 and 7,721 raw PoC weight, see [Counterfactual weight](#counterfactual-weight)). Its confirmation ratio is 1 for its whole weight, because its confirmation-PoC shortfall is attributed to the incident.
2. Every DeepSeek and GLM delegation edge to that address becomes valid. The 0.15 no-participation penalty each delegator took for that model is lifted, and the delegator transfers 5% of its post-penalty reward weight to the address, exactly as the chain does (`trunc(0.05 × weight)`, transfers applied in the chain's order).
3. Each delegator keeps its own settled confirmation ratio. Its confirmation PoC result is not attributed to the incident.
4. Everyone else is unchanged. Members the chain settled at zero for downtime stay at zero.
5. The epoch denominator T is recomputed once for this joint scenario: 862,402 → 868,620 (the address's added 6,218 weight; delegations do not change T).

### Delegators

In the delegation snapshot the chain settled with, six addresses delegate DeepSeek and/or GLM to the address, nine edges in all. In the actual settlement all nine resolved to no participation; in the joint counterfactual all nine are valid.

| Delegator | Models delegated to the address | Weight | Confirmed / raw | Penalty actual → counterfactual | Reward weight actual → counterfactual | Settled at zero |
|---|---|---:|---:|---|---:|---|
| `gonka1scskt6wpnjnumsah6kjphmdu87vjgvcxmn4rxv` | DeepSeek, GLM | 133,006 | 97,089 / 133,006 | 0.30 → 0 | 67,963 → 87,381 | no |
| `gonka1w63xj0j6wxn5w4yuquuckqwmmdyf930pwdy5wh` | DeepSeek, GLM | 37,344 | 22,908 / 37,344 | 0.30 → 0 | 16,036 → 20,618 | no |
| `gonka1346p2h8dn4kp98c5e93k5q64g0h7vxjxnd55fh` | DeepSeek | 1,633 | 1,633 / 1,633 | 0.15 → 0 | 1,320 → 1,471 | no |
| `gonka1w29nvdy6caqtrw30whz9h6ghl0xszwh3egndah` | DeepSeek | 397 | 397 / 397 | 0.15 → 0 | 322 → 359 | no |
| `gonka1rqm2u7lxzn7r68y0drcyhag6xnckpsnfmgd53t` | GLM | 7,090 | 7,090 / 7,090 | 0.30 → 0.15 | 0 → 0 | yes, downtime |
| `gonka1s9tqdht34yrdvcstyytmqzaqqup2ms7jjy9589` | DeepSeek, GLM | 4,064 | 4,064 / 4,064 | 0.30 → 0 | 0 → 0 | yes, downtime |

A delegator's reward weight rises by the lifted penalty and falls by the 5% it now transfers; the net is positive for all four that were paid. `gonka1rqm2u7…` keeps a 0.15 penalty in the counterfactual because its DeepSeek delegation points to an address that is not a member of that subgroup, which has nothing to do with this incident.

### Downtime treatment of the two zero-settled delegators

`gonka1rqm2u7…` and `gonka1s9tqdht…` were settled at zero by the chain's downtime check, not because of the invalid delegation, so they stay at zero and are not recipients. The chain applies the downtime check before the delegation penalties and transfers (`bitcoin_rewards.go`: `CheckAndPunishForDowntimeForParticipants`, then `applyDelegationRewardPenalties`, then `applyDelegationRewardTransfers`), and the check reads only inference and missed-request counts. In epoch 421 the downtime p0 resolves to 0.10, and with that p0 the chain's missed-request test fails for exactly the eight members settled at zero and passes for the other 21. `gonka1rqm2u7…` missed 304 of 785 requests and `gonka1s9tqdht…` missed 113 of 659. `excluded_participants/421` is empty. A zeroed delegator has no reward weight left to penalise or transfer, so their invalid delegations changed nothing for them and the counterfactual transfers from them are zero.

### The address voted out

| | Actual (settled) | Joint counterfactual |
|---|---|---|
| Weight | 133,572 | 139,790 (+953 DeepSeek, +5,265 GLM) |
| Confirmation weight / raw | 96,486 / 133,572 (ratio 0.72235) | 139,790 / 139,790 (ratio 1) |
| Penalty fraction | 0.30 | 0 |
| Inbound transfers | 0 | 12,098 (6 edges from the 4 delegators not settled at zero) |
| Reward weight | 67,541 | 151,888 |
| T | 862,402 | 868,620 |
| Reward | 20,721.371863954 GNK (chain `rewarded_coins`) | 46,265.196592759 GNK |

Valued at F / T = 304,600,736 ngonka per reward-weight unit (counterfactual T), the address's components are: effective weight restored +43,304 (its DeepSeek/GLM weight and the confirmation ratio back to 1, ≈13,190.430 GNK), the 0.30 no-participation penalty lifted +28,945 (≈8,816.668 GNK) and inbound delegation transfers +12,098 (≈3,685.060 GNK), less ≈148.333 GNK because the larger T lowers the value of every weight unit.

### Third-party dilution

The larger T dilutes every other paid member slightly. These addresses would have received less in the joint counterfactual than the chain paid them. They are not recipients and nothing is clawed back from them.

| Address | Counterfactual − settled (ngonka) | GNK |
|---|---:|---:|
| `gonka168rtjfkszuhcggg4dfyse4yh7xn9zwfglnkns2` | −198,953,768,944 | −198.953768944 |
| `gonka1nurzpppvn0lxg20v2c3gf8zfltpdpz599rggst` | −196,676,309,419 | −196.676309419 |
| `gonka147qfckm9hpdzd9dgfvfj2r5rsv0eeunj4gpvz8` | −187,720,205,326 | −187.720205326 |
| `gonka16dgkvx7mh609ntkzknckwaskgq9lcdp86j0skk` | −114,017,742,514 | −114.017742514 |
| `gonka1kvmerzu64094dt9t62ea0cp75larh39ulzldum` | −92,705,999,499 | −92.705999499 |
| `gonka1ajmhqgvkf76hss5xe35kcnntqqhs7r8jz8s939` | −50,334,710,569 | −50.334710569 |
| `gonka1xvlfshxznnuftsv2lke98rv9eqkjr0v6z8c3uk` | −31,313,421,323 | −31.313421323 |
| `gonka1a5dgp5cul6tn0jrdzs6usrm3jtg7w63nqaygd8` | −29,648,701,631 | −29.648701631 |
| `gonka1kx9mca3xm8u8ypzfuhmxey66u0ufxhs7nm6wc5` | −27,497,889,881 | −27.497889881 |
| `gonka1ym3np7guxart483yfdxnlztuazx22cjt0e4a2p` | −11,011,747,406 | −11.011747406 |
| `gonka1qwfrtz9c7kcrfkrrlne2pkcye74mj6ce33xdkl` | −6,193,284,340 | −6.193284340 |
| `gonka1dkl4mah5erqggvhqkpc8j3qs5tyuetgdy552cp` | −6,050,531,333 | −6.050531333 |
| `gonka1tlvg4kjx7ljd5thgd5fkgh39q6lu8cmxupktgg` | −4,627,393,654 | −4.627393654 |
| `gonka1y2a9p56kv044327uycmqdexl7zs82fs5ryv5le` | −4,469,267,246 | −4.469267246 |
| `gonka1p2lhgng7tcqju7emk989s5fpdr7k2c3ek6h26m` | −3,483,173,391 | −3.483173391 |
| `gonka1gyk0aahvr3qeju4zx0nplfreej6cy4jjk8svc5` | −1,803,080,299 | −1.803080299 |
| Total | −966,507,226,775 | −966.507226775 |

The eight members settled at zero are unchanged at zero.

## Chain evidence

All chain data was read from the public REST endpoints (`node1/node2/node3.gonka.ai`) with read-only GET requests. Every raw response is in `snapshots/` together with the node it came from, its HTTP status, the block height the node answered at (`x-cosmos-block-height`), the latest block time and the fetch time.

| File | Contents |
|---|---|
| `poc_snapshot.json` | The address's store commits, per-node weight distributions, every validator's vote and per-model subgroup rows for epochs 420 and 421. Also its participant and hardware-node records, confirmation-PoC state, and routes that returned Not Implemented. Built from `snapshots/raw/` only |
| `coefficients_snapshot.json` | Epoch-421 per-model coefficients (`dynamic_coefficients/421`, `confirmation_weight_scales`, `weight_scale_factor`). Also `bitcoin_reward_params`, `delegation_params`, `poc_params`, the full `epoch_group_data/421` (main and per model), `poc_delegation` for all 29 members, and the chain's own `estimate_bitcoin_reward` for all 29 members. Built from `snapshots/raw/` only |
| `snapshots/raw/` | 97 raw responses taken while epoch 421 was open |
| `snapshots/settled/` | 66 raw responses taken after epoch 421 settled: `epoch_group_data/421` (main and per model), `epoch_performance_summary/421/{address}` and `poc_delegation/{address}` for every member, `confirmation_poc_events/421`, `excluded_participants/421`, `epoch_group_data/422`, `params` |
| `outputs/` | `recalc-settled-joint.out` and `recalc-settled-joint.json`, the output of the command that produces the requested amounts |
| `recalc.py` | Offline recalculation (no network) |
| `tools/fetch.py`, `tools/build_snapshots.py`, `tools/settled_routes.py` | Fetch raw responses; build the two snapshot files from `snapshots/raw/`; list the routes to fetch after settlement |

What the chain recorded for the address in epoch 421 (stage 6,490,966), from `poc_snapshot.json`:

| Model | Commit count | Node (weight distribution) | Votes | In epoch-421 subgroup | Epoch-420 subgroup |
|---|---|---|---|---|---|
| MiniMax-M2.7 | 479,168 | 38 nodes | 23 valid / 0 invalid | yes, raw weight 441,709 | yes, 14 nodes, raw weight 138,401 |
| DeepSeek-V4-Flash-0731 | 4,000 | `CA-LA-1`: 4,000 | 0 valid / 24 invalid | no | yes, `CA-LA-1`, raw weight 3,506 |
| GLM-5.3-Flash | 8,768 | `vs-glm-4b200-6`: 8,768 | 0 valid / 24 invalid | no | yes, `vs-glm-4b200-6`, raw weight 7,433 |

The epoch-420 commits and votes are already pruned on the public nodes (empty responses for stage 6,475,575). Only the 420 subgroup rows remain. This is why the 421 data was snapshotted while the epoch was still open.

Routes that returned Not Implemented (HTTP 501) on the public gateway are listed in `poc_snapshot.json`. They are the single-row `poc_v2_store_commit/...` and `mlnode_weight_distribution/...`. The `all_poc_v2_store_commits/{height}` and `all_mlnode_weight_distributions/{height}` routes return the same records and were used instead.

## Calculation

### Method

`recalc.py` re-implements the chain's reward settlement (`CalculateParticipantBitcoinRewardsWithTransfers` in `inference-chain/x/inference/keeper/bitcoin_rewards.go`, `types/weight.go`, `module/delegation_weight_adjustment.go`, `module/delegation_weight_calculator.go`):

```
F       = trunc(initial_epoch_reward * exp(decay_rate)^(epoch - genesis_epoch))      = 264,582.291322574 GNK
weight  = sum over models of trunc(coefficient_m * raw_poc_weight_m)
eff     = weight * confirmation_weight / raw_confirmation_weight, then the 30% power cap
zero    = members failing the downtime check (or not ACTIVE) are set to 0 here
penalty = trunc(0.15 * eff) for each eligible model where the address is neither member nor valid delegator
transfer= trunc(0.05 * post-penalty weight) per valid delegation edge, only to a target that is a member of that model's subgroup
reward  = trunc(reward_weight * F / T),  T = sum of all members' full weights (never renormalised)
```

### Derivation per recipient

Actual is the reward the chain settled (`rewarded_coins` in `snapshots/settled/`); counterfactual is the reward in one joint recalculation of the whole epoch without the incident.

| Recipient | Settled reward (chain `rewarded_coins`, ngonka) | Counterfactual reward (ngonka) | Loss (ngonka) | Loss (GNK) |
|---|---:|---:|---:|---:|
| `gonka1gvrrhjmy4w4mayvs2s5l23edj8ertcmtd2v4zr` | 20,721,371,863,954 | 46,265,196,592,759 | 25,543,824,728,805 | 25,543.824728805 |
| `gonka1scskt6wpnjnumsah6kjphmdu87vjgvcxmn4rxv` | 20,850,840,171,006 | 26,616,316,914,252 | 5,765,476,743,246 | 5,765.476743246 |
| `gonka1w63xj0j6wxn5w4yuquuckqwmmdyf930pwdy5wh` | 4,919,795,667,970 | 6,280,257,975,281 | 1,360,462,307,311 | 1,360.462307311 |
| `gonka1346p2h8dn4kp98c5e93k5q64g0h7vxjxnd55fh` | 404,971,955,707 | 448,067,682,686 | 43,095,726,979 | 43.095726979 |
| `gonka1w29nvdy6caqtrw30whz9h6ghl0xszwh3egndah` | 98,788,613,437 | 109,351,664,231 | 10,563,050,794 | 10.563050794 |
| Total | | | 32,723,422,557,135 | 32,723.422557135 |

### Delegator mechanism in the chain code

The chain resolves each address's mode per model in `ResolveGroupParticipation` (`module/delegation_weight_calculator.go`): a delegation counts only if its target is a member of the model's subgroup and participates; otherwise the delegator is NONE. NONE adds the no-participation penalty (`AccumulateDelegationPenalties`, `module/delegation_weight_adjustment.go`), and only DELEGATE edges produce transfers (`BuildDelegationRewardTransfers`). Both are built once at epoch formation (`runWeightPipeline`, `module/module.go`) and applied at settlement (`applyDelegationRewardPenalties`, `applyDelegationRewardTransfers`, `keeper/bitcoin_rewards.go`).

### Self-check

Before computing anything else, the script reproduces the chain's settled `rewarded_coins` for every epoch-421 member: 29 of 29 match within 1 ngonka (28 exactly). It uses the delegation records in `coefficients_snapshot.json`, snapshotted while epoch 421 was open, which are the records the chain formed the epoch with. The `poc_delegation` responses in `snapshots/settled/` were fetched after settlement and no longer point the two zero-settled delegators' DeepSeek and GLM edges at the address, so they are kept for reference but not used.

### Counterfactual weight

The address is put back into the DeepSeek and GLM subgroups with the weight its own epoch-421 commits would have received. For each node the chain computes `poc_weight = trunc(count * f)`, where `f` is the stage's time normalisation factor (`chainvalidation.go`, `calculateParticipantWeight`). Across all 166 node rows of epoch 421, `f` is bracketed in [0.8806977, 0.8806991]. That pins DeepSeek at 3,522 and GLM at 7,721 with no ambiguity: `trunc(0.2706 × 3,522) = 953` and `trunc(0.682 × 7,721) = 5,265` weight.

### Earlier figures

Earlier single-recipient figures covered only `gonka1gvrrhjmy4w4mayvs2s5l23edj8ertcmtd2v4zr` and are replaced by the joint amounts above. Each can be reproduced from this tree:

| Figure | Command | Loss for the address (GNK) |
|---|---|---:|
| Provisional, epoch 421 still open, against the chain's `estimate_bitcoin_reward` | `python3 recalc.py` | 19,328.698293532 |
| Settled, the address's own settled confirmation ratio (0.72235) also applied to its counterfactual weight | `python3 recalc.py --settled snapshots/settled` | 13,721.356361622 |
| Settled, ratio 1; equal to this address's row in the joint result | `python3 recalc.py --settled snapshots/settled --cf-cw-ratio 1` | 25,543.824728805 |

Most of the loss is the penalty, the confirmation ratio and the delegation transfers, not the two models' own weight, so a different estimate of the commits' weight (for example `--ref-epoch 420`, which takes it from the epoch-420 subgroup rows) moves the total little.

## Requested spend

The requested total is 32,723,422,557,135 ngonka (32,723.422557135 GNK), paid to five recipients in the amounts of the [Requested amounts](#requested-amounts) table. It is a vesting transfer from the governance module account, the same form as the passed restitution proposal 110 (`snapshots/raw/cosmos_gov_v1_proposals_110.json`). The payment vests over 180 epochs, the same `reward_vesting_period` that applies to epoch rewards. The submit-ready proposal is [`proposal/proposal.json`](proposal/proposal.json) (deposit 500,000 GNK, the current `min_deposit`), and [`proposal/payout_audit.json`](proposal/payout_audit.json) lists the same payouts with their source.

```json
{
  "@type": "/inference.streamvesting.MsgBatchTransferWithVesting",
  "sender": "gonka10d07y265gmmuvt4z0w9aw880jnsr700j2h5m33",
  "outputs": [
    {"recipient": "gonka1gvrrhjmy4w4mayvs2s5l23edj8ertcmtd2v4zr", "amount": [{"denom": "ngonka", "amount": "25543824728805"}]},
    {"recipient": "gonka1scskt6wpnjnumsah6kjphmdu87vjgvcxmn4rxv", "amount": [{"denom": "ngonka", "amount": "5765476743246"}]},
    {"recipient": "gonka1w63xj0j6wxn5w4yuquuckqwmmdyf930pwdy5wh", "amount": [{"denom": "ngonka", "amount": "1360462307311"}]},
    {"recipient": "gonka1346p2h8dn4kp98c5e93k5q64g0h7vxjxnd55fh", "amount": [{"denom": "ngonka", "amount": "43095726979"}]},
    {"recipient": "gonka1w29nvdy6caqtrw30whz9h6ghl0xszwh3egndah", "amount": [{"denom": "ngonka", "amount": "10563050794"}]}
  ],
  "vesting_epochs": "180"
}
```

The governance module account held about 6.07 M GNK at block 6,493,251 (`snapshots/raw/cosmos_bank_v1beta1_balances_gonka10d07y265gmmuvt4z0w9aw880jnsr700j2h5m33.json`). That account is also where the chain sends reward share that settlement does not distribute, including the penalties withheld from these addresses in epoch 421.

## How to verify

All commands run from the root of this repository with Python 3 and no other dependencies. Nothing below needs network access except re-querying the chain.

1. The commits were stored and rejected. In `poc_snapshot.json` → `epochs.421`: three store commits (4,000 and 8,768 for the two models), a weight distribution naming one node each, and 24 votes with `validated_weight = -1` on each of the two models. `epoch_group_data_per_model` shows the address absent from the DeepSeek and GLM subgroups in 421 and present in all three in 420. Each entry under `sources` gives the route and the block height; re-query a node that still holds that height (`x-cosmos-block-height` header).
2. The snapshot files match the raw responses. `python3 tools/build_snapshots.py .` rebuilds `poc_snapshot.json` and `coefficients_snapshot.json` from `snapshots/raw/` offline; `git diff` should then show no change.
3. The amounts. Run `python3 recalc.py --settled snapshots/settled --joint`. Check that the self-check reports 29 of 29 within 1 ngonka against the settled `rewarded_coins`, then read the per-address table, the delegator lines and the recipient lines it prints. The output should be identical to `outputs/recalc-settled-joint.out`; `--json` gives the same result in machine-readable form (`outputs/recalc-settled-joint.json`).
4. The downtime zeros. `epoch_performance_summary/421/{address}` in `snapshots/settled/` gives each member's `inference_count`, `missed_requests` and `rewarded_coins`; the chain's missed-request test at p0 = 0.10 (`calculations/stats_table.go`) fails for exactly the eight members settled at zero.
5. The cause and its fix. Read [gonka-ai/gonka#1978](https://github.com/gonka-ai/gonka/pull/1978) and check its status before voting. Any validator that ran the API in epoch 421 can also check its own logs for the porosity rejection of these two commits at stage 6,490,966.

## What is not modelled

- Re-solving the dynamic coefficients. DeepSeek (0.2706) and GLM (0.682) are already at their `coeff_max`. Adding this address's weight would not raise them; a re-solve could only lower them slightly.
- Lost inference fees on the two models during epoch 421.
- Voting-power effects of the missing subgroup membership (validation of other participants, guardian tiebreaks).
- Group-level caps (`cap_factor`, `v_min`). They do not bind in epoch 421.
- The confirmation PoC of the delegators. Their own settled ratios are kept; the shortfall of the address voted out is the only one attributed to the incident.
- Later epochs. Epoch 422 and onward are outside this proposal.
