"""Generic CLMS prepackaged-file downloader.
Usage: python clms_get.py <DATASET_UID> <FILE_ID> <out_basename>
Reuses the proven JWT -> datarequest_post(FileID) -> poll -> download(browser UA) flow.
"""
import os, sys, json, time, zipfile, io
import _env, jwt, requests

KEY = os.path.join(_env.PROJECT, "clms_apikey.json")
API = "https://land.copernicus.eu/api"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def token():
    k = json.load(open(KEY))
    claim = {"iss": k["client_id"], "sub": k["user_id"], "aud": k["token_uri"],
             "iat": int(time.time()), "exp": int(time.time()) + 3600}
    g = jwt.encode(claim, k["private_key"], algorithm="RS256")
    r = requests.post(k["token_uri"], data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                      "assertion": g}, headers={"Accept": "application/json"}); r.raise_for_status()
    return r.json()["access_token"]


def main(dataset_id, file_id, base):
    h = {"Accept": "application/json", "Authorization": f"Bearer {token()}", "Content-Type": "application/json"}
    r = requests.post(f"{API}/@datarequest_post", headers=h,
                      json={"Datasets": [{"DatasetID": dataset_id, "FileID": file_id}]})
    print("submit", r.status_code, r.text[:300]); r.raise_for_status()
    tid = r.json()["TaskIds"][0]["TaskID"]
    url = None
    t0 = time.time()
    while time.time() - t0 < 5400:
        st = requests.get(f"{API}/@datarequest_status_get", headers=h, params={"TaskID": tid}).json()
        s = st.get("Status"); print(f"  [{int(time.time()-t0)}s] {s}", flush=True)
        if s in ("Finished_ok", "Finished"):
            url = st["DownloadURL"]; break
        if s in ("Cancelled", "Rejected", "Error", "Finished_error"):
            raise SystemExit(json.dumps(st)[:500])
        time.sleep(30)
    zp = os.path.join(_env.LANDCOVER, base + ".zip")
    with requests.get(url, stream=True, headers={"User-Agent": UA}) as rr:
        rr.raise_for_status()
        with open(zp, "wb") as f:
            for c in rr.iter_content(1 << 20):
                f.write(c)
    print("downloaded", round(os.path.getsize(zp)/1e6), "MB")
    # extract any tif(s), handling one level of nested zip
    def extract(zf, depth=0):
        for n in zf.namelist():
            low = n.lower()
            if low.endswith(".tif"):
                out = os.path.join(_env.LANDCOVER, base + "_" + os.path.basename(n))
                open(out, "wb").write(zf.read(n)); print("  ->", os.path.basename(out), round(len(zf.read(n))/1e6), "MB")
            elif low.endswith(".zip") and depth == 0:
                extract(zipfile.ZipFile(io.BytesIO(zf.read(n))), depth + 1)
    with zipfile.ZipFile(zp) as z:
        extract(z)
    print("DONE")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
