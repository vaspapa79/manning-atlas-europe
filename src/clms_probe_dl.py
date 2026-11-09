import os, json, time, _env, jwt, requests
KEY = os.path.join(_env.PROJECT, "clms_apikey.json")
API = "https://land.copernicus.eu/api"
DATASET_ID = "0407d497d3c44bcd93ce8fd5bf78596a"
FILE_ID = "3d9e2413-46ca-4f6e-abf8-b6eb429a4e48"

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
h = {"Accept": "application/json", "Authorization": f"Bearer {tok}",
     "Content-Type": "application/json"}
tid = requests.post(f"{API}/@datarequest_post", headers=h, json={
    "Datasets": [{"DatasetID": DATASET_ID, "FileID": FILE_ID}]}).json()["TaskIds"][0]["TaskID"]
print("TaskID", tid)
url = None
for _ in range(20):
    st = requests.get(f"{API}/@datarequest_status_get", headers=h, params={"TaskID": tid}).json()
    if st.get("Status") == "Finished_ok":
        url = st["DownloadURL"]; break
    time.sleep(15)
print("URL", url)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
variants = {
    "browser-UA only":      {"User-Agent": UA},
    "browser-UA + Bearer":  {"User-Agent": UA, "Authorization": f"Bearer {tok}"},
    "Bearer only":          {"Authorization": f"Bearer {tok}"},
}
for name, hh in variants.items():
    try:
        r = requests.get(url, headers=hh, stream=True, allow_redirects=True, timeout=60)
        print(f"\n## {name}: {r.status_code}  ctype={r.headers.get('Content-Type')} "
              f"clen={r.headers.get('Content-Length')}")
        print("   history:", [resp.status_code for resp in r.history],
              "final:", r.url[:120])
        if r.status_code != 200:
            print("   body:", r.text[:300])
        r.close()
    except Exception as e:
        print(f"\n## {name}: EXC {type(e).__name__} {e}")
