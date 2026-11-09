"""Request + download the CORINE CLC2018 100 m raster (GeoTIFF, EPSG:3035)
from the CLMS prepackaged download API, then extract the .tif into
data/landcover/.
"""
import os
import io
import json
import time
import zipfile
import _env
import jwt
import requests

KEY = os.path.join(_env.PROJECT, "clms_apikey.json")
API = "https://land.copernicus.eu/api"
DATASET_ID = "0407d497d3c44bcd93ce8fd5bf78596a"
FILE_ID = "3d9e2413-46ca-4f6e-abf8-b6eb429a4e48"  # prepackaged 100 m raster, 125 MB
ZIP_OUT = os.path.join(_env.LANDCOVER, "clc2018_raster.zip")


def get_token():
    k = json.load(open(KEY))
    claim = {"iss": k["client_id"], "sub": k["user_id"], "aud": k["token_uri"],
             "iat": int(time.time()), "exp": int(time.time()) + 3600}
    grant = jwt.encode(claim, k["private_key"], algorithm="RS256")
    r = requests.post(k["token_uri"], data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": grant}, headers={"Accept": "application/json"})
    r.raise_for_status()
    return r.json()["access_token"]


def submit(h):
    body = {"Datasets": [{
        "DatasetID": DATASET_ID,
        "FileID": FILE_ID,
    }]}
    r = requests.post(f"{API}/@datarequest_post", headers=h, json=body)
    print("submit status", r.status_code, r.text[:500])
    r.raise_for_status()
    j = r.json()
    # response shape: {"TaskIds":[{"TaskID":..,"DatasetId":..}]}
    tasks = j.get("TaskIds") or j.get("TaskId") or []
    if isinstance(tasks, dict):
        tasks = [tasks]
    tid = tasks[0]["TaskID"]
    print("TaskID:", tid)
    return tid


def poll(h, tid, every=30, timeout=5400):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = requests.get(f"{API}/@datarequest_status_get", headers=h,
                         params={"TaskID": tid})
        r.raise_for_status()
        st = r.json()
        status = st.get("Status")
        print(f"  [{int(time.time()-t0)}s] status={status}")
        if status in ("Finished_ok", "Finished"):
            return st.get("DownloadURL")
        if status in ("Cancelled", "Rejected", "Error", "Finished_error"):
            raise SystemExit(f"Request failed: {json.dumps(st)[:800]}")
        time.sleep(every)
    raise SystemExit("Timed out waiting for CLMS packaging")


def main():
    tok = get_token()
    h = {"Accept": "application/json", "Authorization": f"Bearer {tok}",
         "Content-Type": "application/json"}
    print("AUTH OK")
    tid = submit(h)
    url = poll(h, tid)
    print("DownloadURL:", url)

    # the FME results host (Azure App Gateway WAF) rejects non-browser UAs
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
    r = requests.get(url, stream=True, headers={"User-Agent": ua})
    r.raise_for_status()
    total = int(r.headers.get("Content-Length", 0))
    got = 0
    with open(ZIP_OUT, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk); got += len(chunk)
            if total and got % (50 << 20) < (1 << 20):
                print(f"  downloaded {got/1e6:.0f} / {total/1e6:.0f} MB")
    print(f"Saved {ZIP_OUT} ({got/1e6:.0f} MB)")

    print("Extracting GeoTIFFs ...")
    with zipfile.ZipFile(ZIP_OUT) as z:
        tifs = [n for n in z.namelist() if n.lower().endswith(".tif")]
        for n in tifs:
            data = z.read(n)
            out = os.path.join(_env.LANDCOVER, os.path.basename(n))
            with open(out, "wb") as f:
                f.write(data)
            print("  ->", out, f"({len(data)/1e6:.0f} MB)")
    print("DONE")


if __name__ == "__main__":
    main()
