import os, json, time, _env, jwt, requests
KEY = os.path.join(_env.PROJECT, "clms_apikey.json")
def token():
    k = json.load(open(KEY))
    claim = {"iss": k["client_id"], "sub": k["user_id"], "aud": k["token_uri"],
             "iat": int(time.time()), "exp": int(time.time()) + 3600}
    g = jwt.encode(claim, k["private_key"], algorithm="RS256")
    r = requests.post(k["token_uri"], data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                      "assertion": g}, headers={"Accept": "application/json"}); r.raise_for_status()
    return r.json()["access_token"]
h = {"Accept": "application/json", "Authorization": f"Bearer {token()}"}
DS = "https://land.copernicus.eu/api/en/products/high-resolution-layer-forests-and-tree-cover/tree-cover-density-2018-present-raster-100-m-europe-yearly"
d = requests.get(DS, params={"fullobjects": 1}, headers=h).json()
print("UID:", d.get("UID"))
items = d.get("downloadable_files", {}).get("items", [])
print(f"{len(items)} downloadable files:")
for e in items:
    print(json.dumps({k: e.get(k) for k in ("@id","file","format","resolution","size","year","area")}, ensure_ascii=False))
