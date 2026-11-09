"""List and optionally cancel CLMS data-request tasks (to clear stale/duplicate
subset jobs from the cart).
Usage:
    python clms_tasks.py list
    python clms_tasks.py cancel <TaskID> [<TaskID> ...]
"""
import os, sys, json, time
import _env, jwt, requests
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


def main():
    h = {"Accept": "application/json", "Authorization": f"Bearer {token()}", "Content-Type": "application/json"}
    if sys.argv[1] == "list":
        j = requests.get(f"{API}/@datarequest_search", headers=h).json()
        for tid, t in j.items():
            ds = t.get("Datasets")
            title = ds.get("DatasetTitle") if isinstance(ds, dict) else (ds[0].get("DatasetTitle") if ds else "?")
            bbox = ds.get("BoundingBox") if isinstance(ds, dict) else None
            print(f"{tid}  {t.get('Status'):14}  {str(title)[:45]:45}  bbox={bbox}")
    elif sys.argv[1] == "cancel":
        ids = sys.argv[2:]
        for ep in ("@datarequest_delete_post", "@datarequest_delete"):
            r = requests.post(f"{API}/{ep}", headers=h, json={"TaskIds": ids})
            print(ep, r.status_code, r.text[:200])
            if r.status_code < 300:
                break


if __name__ == "__main__":
    main()
