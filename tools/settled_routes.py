#!/usr/bin/env python3
"""Print the routes to fetch once epoch 421 has settled (input for tools/fetch.py).

Usage: python3 tools/fetch.py snapshots/settled $(python3 tools/settled_routes.py)
"""
import json, os

P = "/productscience/inference/inference"
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = json.load(open(os.path.join(here, "coefficients_snapshot.json")))
start = json.load(open(os.path.join(here, "poc_snapshot.json")))["epochs"]["421"]["poc_stage_start_block_height"]
routes = [f"{P}/epoch_group_data/421", f"{P}/confirmation_poc_events/421", f"{P}/excluded_participants/421",
          f"{P}/epoch_group_data/422", f"{P}/params"]
routes += [f"{P}/epoch_group_data/421?model_id=" + m.replace("/", "%2F") for m in C["epoch_group_data_421"]["sub_group_models"]]
for v in C["epoch_group_data_421"]["validation_weights"]:
    routes += [f"{P}/epoch_performance_summary/421/{v['member_address']}", f"{P}/poc_delegation/{v['member_address']}"]
print("\n".join(routes))
