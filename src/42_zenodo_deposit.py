"""Step 42: deposit the archive on Zenodo and obtain the DOI.

Two stages, because publishing on Zenodo cannot be undone: a published record
can be edited but never deleted, and its DOI is permanent.

  python 42_zenodo_deposit.py            create the draft, upload, print the
                                         reserved DOI; nothing is public yet
  python 42_zenodo_deposit.py --publish   publish the draft, which registers
                                         the DOI  (irreversible)

  --access open         files open from the start
  --access restricted   files access-controlled, for a reviewer link (default,
                        which is what the manuscript's data availability
                        statement promises during review)
  --sandbox             rehearse against sandbox.zenodo.org

The token is read from zenodo_token.json at the project root, which you create
yourself and which is never committed:

    {"token": "..."}

Make one at https://zenodo.org/account/settings/applications/tokens/new with
the scopes deposit:write and deposit:actions.
"""
import os
import re
import sys
import json
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _env

ROOT = _env.PROJECT
BUNDLE = os.path.join(ROOT, "manning_atlas_release.zip")
TOKEN_FILE = os.path.join(ROOT, "zenodo_token.json")
STATE = os.path.join(ROOT, "outputs", "zenodo_deposition.json")

REPO = "https://github.com/vaspapa79/manning-atlas-europe"
AFFIL = ("Information Technologies Institute, Centre for Research and "
         "Technology Hellas (CERTH-ITI), Thessaloniki, Greece")
AUTHORS = ["Papaioannou, Vassilios", "Valsamis, Dimitrios",
           "Anagnostopoulos, Christos", "Moumtzidou, Anastasia",
           "Gialampoukidis, Ilias", "Vrochidis, Stefanos",
           "Kompatsiaris, Ioannis"]

TITLE = ("An uncertainty-aware Manning's roughness atlas for Europe, with a "
         "Greek application: gridded products, look-up tables and processing "
         "code")

DESCRIPTION = """<p>Data and code archive for the paper <em>Uncertainty-aware
Manning's roughness for the river basins of Greece, from a harmonized European
atlas</em> (Journal of Hydrology: Regional Studies).</p>

<p>The atlas assigns Manning's roughness coefficient to the 44 classes of
CORINE Land Cover 2018 with an explicit lower, best and upper value, on the
100 m EPSG:3035 grid, for 39 European states. The envelope is benchmarked
against two independent Sentinel-derived classifiers (ESA WorldCover 10 m and
CLC+ Backbone 10 m), the four methodological choices behind such a layer are
ranked on a single metric, and the bounds are propagated through the SFINCS
2-D flood model in 721 simulations, deterministically and by Monte-Carlo, over
Greek river corridors and five floodplain landscapes.</p>

<p><strong>Contents.</strong> The pan-European lower, best and upper GeoTIFFs
at 100 m; the per-country products and their provenance manifests; the ESA
WorldCover benchmark rasters; the consolidated national statistics and every
derived analysis table; the SFINCS configurations for the deterministic and
Monte-Carlo experiments; and the complete processing code with the three
look-up tables.</p>

<p><strong>Not included.</strong> The third-party inputs, which are openly
available from their providers and are not ours to redistribute, and the
Deltares SFINCS solver, which is distributed under its own freeware licence.
The code is also maintained at <a href="%s">%s</a>.</p>

<p><strong>Funding.</strong> Co-financed by the European Union and Greek
national funds through the Programme &#8216;COMPETITIVENESS&#8217;, under the
Action &#8216;RESEARCH &#8211; INNOVATE&#8217;, through the HydroDS project
&#8216;Hydrometeorological Data Space for innovative environmental design and
decision support&#8217; (project code: EKPAR02-0071041).</p>""" % (REPO, REPO)

KEYWORDS = ["Manning roughness", "flood inundation", "CORINE Land Cover",
            "uncertainty quantification", "SFINCS", "Greece", "Europe",
            "land cover", "hydraulic modelling"]

REFERENCED = [
    "10.2909/960998c1-1870-4e82-8051-6485205ebbac",
    "10.2909/264d4e20-de6d-4f88-b1be-b592303452af",
    "10.2909/cd534ebf-f553-42f0-9ac1-62c1dc36d32c",
    "10.5281/zenodo.7254221",
]


def token():
    if not os.path.exists(TOKEN_FILE):
        print("No token file. Create one at")
        print("   https://zenodo.org/account/settings/applications/tokens/new")
        print("with the scopes deposit:write and deposit:actions, then save it as")
        print("   %s" % TOKEN_FILE)
        print('containing   {"token": "..."}')
        return None
    t = json.load(open(TOKEN_FILE, encoding="utf-8")).get("token", "").strip()
    return t or None


def call(api, method, path, tok, body=None, raw=None, ctype=None):
    url = path if path.startswith("http") else api + path
    sep = "&" if "?" in url else "?"
    url = url + sep + "access_token=" + tok
    data = raw if raw is not None else (
        json.dumps(body).encode("utf-8") if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", ctype or "application/json")
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            txt = r.read().decode("utf-8", "replace")
            return json.loads(txt) if txt.strip() else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        raise SystemExit("Zenodo %s %s -> HTTP %s%s%s"
                         % (method, path, e.code, chr(10), detail))


def metadata(access):
    md = {
        "upload_type": "dataset",
        "title": TITLE,
        "description": DESCRIPTION,
        "creators": [{"name": a, "affiliation": AFFIL} for a in AUTHORS],
        "keywords": KEYWORDS,
        "version": "1.0",
        "language": "eng",
        "access_right": access,
        "license": "cc-by-4.0",
        "related_identifiers":
            [{"relation": "isSupplementedBy", "identifier": REPO,
              "resource_type": "software"}] +
            [{"relation": "references", "identifier": d} for d in REFERENCED],
    }
    if access == "restricted":
        md["access_conditions"] = (
            "Access is restricted during peer review. A secret link is "
            "provided to the editor and reviewers, and the record will be "
            "opened on acceptance.")
    return md


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return {}


def save_state(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(d, open(STATE, "w", encoding="utf-8"), indent=2)


def main():
    argv = sys.argv[1:]
    publish = "--publish" in argv
    sandbox = "--sandbox" in argv
    access = "restricted"
    if "--access" in argv:
        access = argv[argv.index("--access") + 1]
    if access not in ("open", "restricted"):
        raise SystemExit("--access takes open or restricted")

    api = ("https://sandbox.zenodo.org/api" if sandbox
           else "https://zenodo.org/api")
    tok = token()
    if not tok:
        return 1
    if not os.path.exists(BUNDLE):
        raise SystemExit("bundle missing; run make_release.py first")

    st = load_state()
    key = "sandbox" if sandbox else "zenodo"
    dep = st.get(key)

    if dep is None:
        d = call(api, "POST", "/deposit/depositions", tok, body={})
        dep = {"id": d["id"], "bucket": d["links"]["bucket"],
               "links": {k: v for k, v in d["links"].items()},
               "uploaded": False, "published": False}
        st[key] = dep
        save_state(st)
        print("draft deposition %s created" % dep["id"])
    else:
        print("reusing draft deposition %s" % dep["id"])

    if not dep.get("uploaded"):
        name = os.path.basename(BUNDLE)
        size = os.path.getsize(BUNDLE)
        print("uploading %s (%.0f MB), this takes a while" % (name, size / 1e6))
        t0 = time.time()
        with open(BUNDLE, "rb") as f:
            call(api, "PUT", dep["bucket"] + "/" + name, tok, raw=f.read(),
                 ctype="application/octet-stream")
        dep["uploaded"] = True
        save_state(st)
        print("   uploaded in %.0f s" % (time.time() - t0))

    d = call(api, "PUT", "/deposit/depositions/%s" % dep["id"], tok,
             body={"metadata": metadata(access)})
    doi = (d.get("metadata", {}).get("prereserve_doi", {}) or {}).get("doi") \
        or d.get("doi") or d.get("metadata", {}).get("doi", "")
    dep["doi"] = doi
    dep["access"] = access
    save_state(st)

    print()
    print("title     %s" % TITLE[:66])
    print("authors   %d, access %s, licence CC BY 4.0" % (len(AUTHORS), access))
    print("edit at   https://%szenodo.org/deposit/%s"
          % ("sandbox." if sandbox else "", dep["id"]))
    print()
    if not publish:
        print("RESERVED DOI   %s" % (doi or "(not reported by the API)"))
        print()
        print("Nothing is public yet. The DOI above is reserved for this record")
        print("and becomes resolvable the moment it is published:")
        print("   python 42_zenodo_deposit.py --publish --access %s" % access)
        return 0

    print("publishing: this registers the DOI and cannot be undone")
    d = call(api, "POST", "/deposit/depositions/%s/actions/publish" % dep["id"],
             tok)
    dep["published"] = True
    dep["doi"] = d.get("doi", doi)
    save_state(st)
    print()
    print("PUBLISHED")
    print("   DOI      %s" % dep["doi"])
    print("   record   %s" % d.get("links", {}).get("record_html", ""))
    if access == "restricted":
        print()
        print("Create the reviewer link on the record page, under Share.")
    print()
    print("Now put %s in place of 10.5281/zenodo.XXXXXXX in" % dep["doi"])
    print("   manuscript_JHRS.docx   Data availability, and the [dataset] entry")
    print("   the repository         README.md and CITATION.cff")
    return 0


if __name__ == "__main__":
    sys.exit(main())
