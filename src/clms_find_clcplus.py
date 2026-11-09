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
DS = "https://land.copernicus.eu/api/en/products/clc-backbone/clc-backbone-2018"
d = requests.get(DS, params={"fullobjects": 1}, headers=h).json()
print("title:", d.get("title"))
print("UID:", d.get("UID"))
dli = d.get("dataset_download_information", {})
items = dli.get("items", []) if isinstance(dli, dict) else dli
print("dataset_download_information items:")
for e in items:
    print(json.dumps({k: e.get(k) for k in ("@id","id","name","full_format","full_source","collection","resolution")}, ensure_ascii=False))
# also list downloadable_files briefly
df = d.get("downloadable_files", {}).get("items", [])
print(f"\ndownloadable_files: {len(df)} (first 3)")
for e in df[:3]:
    print(json.dumps({k: e.get(k) for k in ("@id","file","format","resolution","size")}, ensure_ascii=False))
