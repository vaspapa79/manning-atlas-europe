import os, json, time, _env, jwt, requests
KEY = os.path.join(_env.PROJECT, "clms_apikey.json")
API = "https://land.copernicus.eu/api"

def token():
    k = json.load(open(KEY))
    claim = {"iss": k["client_id"], "sub": k["user_id"], "aud": k["token_uri"],
             "iat": int(time.time()), "exp": int(time.time()) + 3600}
    g = jwt.encode(claim, k["private_key"], algorithm="RS256")
    r = requests.post(k["token_uri"], data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                      "assertion": g}, headers={"Accept": "application/json"}); r.raise_for_status()
    return r.json()["access_token"]

h = {"Accept": "application/json", "Authorization": f"Bearer {token()}"}
for q in ["Tree Cover Density 2018", "CLCplus Backbone 2018"]:
    r = requests.get(f"{API}/@search", params={"portal_type": "DataSet", "SearchableText": q,
                     "metadata_fields": "UID", "b_size": 8}, headers=h).json()
    print("\n=====", q, "=====")
    for it in r.get("items", []):
        print(" -", it.get("title"), "|", it.get("@id"))
