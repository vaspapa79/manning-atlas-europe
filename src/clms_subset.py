"""Download a bounding-box subset of a CLMS dataset (FME spatial subset).
Usage: python clms_subset.py <DATASET_UID> <DLINFO_ID> <xmin> <ymin> <xmax> <ymax> <out_basename>
Bounding box in EPSG:3035. Saves + extracts the clipped GeoTIFF into data/landcover/.
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


def main(ds, dli, bbox, base):
    h = {"Accept": "application/json", "Authorization": f"Bearer {token()}", "Content-Type": "application/json"}
    body = {"Datasets": [{
        "DatasetID": ds, "DatasetDownloadInformationID": dli,
        "OutputFormat": "Geotiff", "OutputGCS": "EPSG:3035",
        "BoundingBox": bbox}]}
    r = requests.post(f"{API}/@datarequest_post", headers=h, json=body)
    print("submit", r.status_code, r.text[:400], flush=True); r.raise_for_status()
    tid = r.json()["TaskIds"][0]["TaskID"]
    url = None; t0 = time.time()
    while time.time() - t0 < 7200:
        st = requests.get(f"{API}/@datarequest_status_get", headers=h, params={"TaskID": tid}).json()
        s = st.get("Status"); print(f"  [{int(time.time()-t0)}s] {s}", flush=True)
        if s in ("Finished_ok", "Finished"):
            url = st["DownloadURL"]; break
        if s in ("Cancelled", "Rejected", "Error", "Finished_error"):
            raise SystemExit(json.dumps(st)[:600])
        time.sleep(30)
    zp = os.path.join(_env.LANDCOVER, base + ".zip")
    with requests.get(url, stream=True, headers={"User-Agent": UA}) as rr:
        rr.raise_for_status()
        with open(zp, "wb") as f:
            for c in rr.iter_content(1 << 20):
                f.write(c)
    print("downloaded", round(os.path.getsize(zp)/1e6, 1), "MB")
    def extract(zf, depth=0):
        for n in zf.namelist():
            low = n.lower()
            if low.endswith(".tif"):
                data = zf.read(n)
                out = os.path.join(_env.LANDCOVER, base + "_" + os.path.basename(n))
                open(out, "wb").write(data); print("  ->", os.path.basename(out), round(len(data)/1e6, 1), "MB")
            elif low.endswith(".zip") and depth == 0:
                extract(zipfile.ZipFile(io.BytesIO(zf.read(n))), depth + 1)
    with zipfile.ZipFile(zp) as z:
        extract(z)
    print("DONE", base)


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], [float(a[3]), float(a[4]), float(a[5]), float(a[6])], a[7])
