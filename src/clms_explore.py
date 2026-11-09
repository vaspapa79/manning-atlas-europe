"""Authenticate to the Copernicus Land Monitoring Service (CLMS) API with the
local API key and locate the CORINE CLC2018 100 m raster dataset + its
download-information entries. Prints what we need to place a download request.
"""
import os
import json
import time
import _env
import jwt
import requests

KEY = os.path.join(_env.PROJECT, "clms_apikey.json")
API = "https://land.copernicus.eu/api"


def get_token():
    k = json.load(open(KEY))
    claim = {
        "iss": k["client_id"],
        "sub": k["user_id"],
        "aud": k["token_uri"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    grant = jwt.encode(claim, k["private_key"], algorithm="RS256")
    r = requests.post(k["token_uri"], data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": grant,
    }, headers={"Accept": "application/json"})
    r.raise_for_status()
    return r.json()["access_token"]


def main():
    tok = get_token()
    print("AUTH OK, token len", len(tok))
    h = {"Accept": "application/json", "Authorization": f"Bearer {tok}"}

    # search the catalogue for CORINE 2018 datasets
    r = requests.get(f"{API}/@search", params={
        "portal_type": "DataSet",
        "SearchableText": "CORINE Land Cover 2018",
        "metadata_fields": "UID",
        "b_size": 50,
    }, headers=h)
    r.raise_for_status()
    items = r.json().get("items", [])
    print(f"\n{len(items)} datasets matched:")
    for it in items:
        print(" -", it.get("title"), "|", it.get("@id"))

    # pick the CLC2018 status layer (100 m raster)
    cand = [it for it in items if "2018" in (it.get("title") or "")]
    target = None
    for it in cand:
        t = (it.get("title") or "").lower()
        if "corine land cover 2018" in t and ("status" in t or t.strip().endswith("2018")):
            target = it
            break
    target = target or (cand[0] if cand else (items[0] if items else None))
    if not target:
        print("No dataset found"); return
    print("\nUsing dataset:", target.get("title"), target.get("@id"))

    d = requests.get(target["@id"], params={"fullobjects": 1}, headers=h).json()
    print("UID:", d.get("UID"))
    dli = d.get("dataset_download_information", {})
    items_dl = dli.get("items", []) if isinstance(dli, dict) else dli
    print(f"\ndownload-information entries ({len(items_dl)}):")
    for e in items_dl:
        print(json.dumps({k: e.get(k) for k in
                          ("@id", "id", "name", "full_format", "full_source",
                           "resolution", "full_path", "area")},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
