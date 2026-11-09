import os, json, time, _env, jwt, requests
KEY = os.path.join(_env.PROJECT, "clms_apikey.json")
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

h = {"Accept": "application/json", "Authorization": f"Bearer {get_token()}"}
d = requests.get(DS, params={"fullobjects": 1}, headers=h).json()
for key in ("downloadable_files", "downloadable_full_dataset", "downloadable_dataset"):
    print("="*30, key, "="*30)
    print(json.dumps(d.get(key), ensure_ascii=False, indent=1)[:4000])
