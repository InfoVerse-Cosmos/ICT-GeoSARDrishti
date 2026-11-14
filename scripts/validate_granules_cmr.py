"""Cross-check every granule shown by the app against NASA live catalogue (CMR). Run from repo root: python scripts/validate_granules_cmr.py"""
import json
import re
import urllib.parse
import urllib.request

COLL = {"C2854338529-ASF": "PROVISIONAL (NISAR_L2_GCOV_PROVISIONAL_V1)", "C3622241360-ASF": "VALIDATED (NISAR_L2_GCOV_V1)"}
BOUNDS = {"aoi_assam_majuli": [93.90, 26.75, 94.30, 27.05], "aoi_nagpur_kanhan": [78.95, 21.15, 79.35, 21.45]}
root = "services/api/data_store/"
ok_all = True
for aoi, b in BOUNDS.items():
    m = json.load(open(root + aoi + "/manifest.json", encoding="utf-8"))
    print(f"\n== {aoi}  (manifest: track/frame {m['track_frame']}, plan {m['fallback_plan']}, synthetic={m.get('synthetic_test_data', False)})")
    for t in m["timeline"]:
        gid = t["granule_id"]
        url = ("https://cmr.earthdata.nasa.gov/search/granules.json?provider=ASF&readable_granule_name="
               + urllib.parse.quote(gid) + "&page_size=5")
        e = json.load(urllib.request.urlopen(url, timeout=40))["feed"]["entry"]
        e = [x for x in e if x["title"] == gid or x.get("producer_granule_id") == gid]
        if not e:
            print(f"  {t['date']}  NOT FOUND in CMR: {gid}")
            ok_all = False
            continue
        x = e[0]
        coll = COLL.get(x["collection_concept_id"], x["collection_concept_id"])
        p = x["polygons"][0][0].split()
        la, lo = [float(v) for v in p[0::2]], [float(v) for v in p[1::2]]
        covers = min(la) <= b[1] and max(la) >= b[3] and min(lo) <= b[0] and max(lo) >= b[2]
        name_date = re.search(r"_(\d{8})T", gid).group(1)
        cmr_date = x["time_start"][:10].replace("-", "")
        mat_ok = coll.startswith(t["maturity"])
        checks = {"in CMR": True, "date matches": name_date == cmr_date == t["date"].replace("-", ""),
                  "maturity matches collection": mat_ok, "footprint covers AOI": covers,
                  "dual-pol DHDH": "_DHDH_" in gid}
        bad = [k for k, v in checks.items() if not v]
        ok_all &= not bad
        print(f"  {t['date']} manifest={t['maturity']:<11} CMR collection={coll} | start {x['time_start']} | {round(float(x['granule_size'])/1000,1)} GB | "
              f"footprint lat {min(la):.2f}..{max(la):.2f} lon {min(lo):.2f}..{max(lo):.2f} | {'ALL CHECKS PASS' if not bad else 'FAILED: ' + ', '.join(bad)}")
print("\nOVERALL:", "ALL GRANULE FACTS MATCH NASA CMR" if ok_all else "MISMATCH FOUND")
