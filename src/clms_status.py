import os, json, time, _env, jwt, requests
KEY = os.path.join(_env.PROJECT, "clms_apikey.json")
API = "https://land.copernicus.eu/api"
TID = "85527043190"

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
for name, url, params in [
    ("status_get no-params", f"{API}/@datarequest_status_get", None),
    ("status_get TaskID",    f"{API}/@datarequest_status_get", {"TaskID": TID}),
    ("datarequest_search",   f"{API}/@datarequest_search", None),
]:
    try:
        r = requests.get(url, headers=h, params=params)
        print(f"\n## {name} -> {r.status_code}")
        print(r.text[:1500])
    except Exception as e:
        print(f"\n## {name} -> EXC {e}")
