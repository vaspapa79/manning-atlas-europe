import os, json, time, _env, jwt, requests
KEY = os.path.join(_env.PROJECT, "clms_apikey.json")
API = "https://land.copernicus.eu/api"
DS = "https://land.copernicus.eu/api/en/products/corine-land-cover/clc2018"

def get_token():
    k = json.load(open(KEY))
    claim = {"iss": k["client_id"], "sub": k["user_id"], "aud": k["token_uri"],
             "iat": int(time.time()), "exp": int(time.time()) + 3600}
    grant = jwt.encode(claim, k["private_key"], algorithm="RS256")
    r = requests.post(k["token_uri"], data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": grant}, headers={"Accept": "application/json"})
    r.raise_for_status(); return r.json()["access_token"]

tok = get_token()
h = {"Accept": "application/json", "Authorization": f"Bearer {tok}"}
d = requests.get(DS, params={"fullobjects": 1}, headers=h).json()
print("TOP-LEVEL KEYS:")
print([k for k in d.keys()])
dli = d.get("dataset_download_information", {})
items = dli.get("items", []) if isinstance(dli, dict) else dli
print("\nFULL download-information items:")
for e in items:
    print(json.dumps(e, ensure_ascii=False, indent=1)[:2000])
# look for prepackaged collection references / any URL fields
import re
blob = json.dumps(d)
urls = sorted(set(re.findall(r'https?://[^"\\]+', blob)))
print("\nURL-like strings in dataset JSON:")
for u in urls:
    print(" ", u)
