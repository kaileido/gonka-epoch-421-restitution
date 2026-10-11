#!/usr/bin/env python3
"""Read-only fetcher: HTTP GET against public Gonka chain REST, stores every
response as snapshots/raw/<route>.json together with the node, the HTTP status,
the block height the node answered at and the UTC fetch time.

Usage: fetch.py OUTDIR ROUTE [ROUTE ...]   (routes relative to the chain-api root)
"""
import datetime, json, os, re, sys, time, urllib.error, urllib.request

NODES = ["http://node1.gonka.ai:8000/chain-api", "http://node2.gonka.ai:8000/chain-api",
         "https://node3.gonka.ai/chain-api"]
LATEST = "/cosmos/base/tendermint/v1beta1/blocks/latest"


def raw_get(node, route):
    req = urllib.request.Request(node + route, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read()


def latest(node):
    st, _, b = raw_get(node, LATEST)
    h = json.loads(b)["block"]["header"]
    return {"height": int(h["height"]), "time": h["time"]}


def fname(route):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", route.strip("/"))[:200] + ".json"


def fetch(outdir, route):
    last = None
    for attempt in range(4):
        for node in NODES:
            try:
                before = latest(node)
                t = datetime.datetime.now(datetime.timezone.utc).isoformat()
                st, hdr, body = raw_get(node, route)
                hh = {k.lower(): v for k, v in hdr.items()}
                try:
                    parsed = json.loads(body)
                except Exception:
                    parsed = body.decode("utf-8", "replace")
                rec = {"route": route, "node": node, "http_status": st,
                       "query_height": int(hh["grpc-metadata-x-cosmos-block-height"]) if "grpc-metadata-x-cosmos-block-height" in hh else None,
                       "latest_block_before_query": before, "fetched_at_utc": t, "body": parsed}
                if st >= 500 and st != 501:
                    last = rec
                    continue
                os.makedirs(outdir, exist_ok=True)
                with open(os.path.join(outdir, fname(route)), "w") as f:
                    json.dump(rec, f, indent=1)
                return rec
            except Exception as e:
                last = str(e)
        time.sleep(2 * (attempt + 1))
    print("FAILED", route, last, file=sys.stderr)
    return None


if __name__ == "__main__":
    out = sys.argv[1]
    for r in sys.argv[2:]:
        rec = fetch(out, r)
        if rec:
            print(rec["http_status"], rec["query_height"], rec["latest_block_before_query"]["height"], r, flush=True)
