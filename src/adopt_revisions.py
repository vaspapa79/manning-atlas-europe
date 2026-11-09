"""Adopt the manual revisions from manuscript_revised_clean.docx into the
markdown source: sequential numbering of equations/figures/tables, updated
cross-references, three rewritten paragraphs, and a reference cleanup.
Backs up the original md, then verifies counts.
"""
import os, re, shutil
import _env

MD = os.path.join(_env.PROJECT, "manuscript.md")
shutil.copy(MD, os.path.join(_env.PROJECT, "manuscript_pre_revision.md"))
t = open(MD, encoding="utf-8").read()

# 1) equation display tags -> sequential 1..N in document order
_c = [0]
def _tag(m):
    _c[0] += 1
    return f"\\tag{{{_c[0]}}}"
t = re.sub(r"\\tag\{[^}]*\}", _tag, t)

# 2) generic two-pass renumber for cross-references
def renum(text, pat, mapping):
    keys = sorted(mapping, key=len, reverse=True)
    for i, k in enumerate(keys):
        text = re.sub(rf"{pat}(\s+){re.escape(k)}\b", f"{pat}\\1\x00{i}\x00", text)
    for i, k in enumerate(keys):
        text = text.replace(f"\x00{i}\x00", mapping[k])
    return text

t = renum(t, "Figure", {"0": "1", "1": "2", "2": "3", "3": "4", "4": "5",
                         "C": "6", "A": "7", "E": "8", "D": "9"})
t = renum(t, "Table", {"4": "5", "5": "4"})
t = renum(t, r"Eq\.", {"3b": "7", "3": "6", "4": "4", "5": "2"})

# 3) rewritten paragraphs (verbatim from manuscript_revised_clean.docx)
NEW = {
 "Manning's roughness coefficient (*n*) is one of the most influential":
 "Manning's roughness coefficient (*n*) is among the most influential and uncertain parameters in hydraulic modelling, yet no harmonized, openly available, continental-scale map of *n* exists for Europe. We present a reproducible, uncertainty-aware atlas of floodplain Manning's *n* for 39 European countries (5.84 × 10⁶ km²), mapping the 44 Level-3 classes of CORINE Land Cover 2018 (100 m) to literature-based roughness values. For every land pixel we supply a best estimate with lower and upper bounds, propagating the mapping uncertainty into three companion maps. The area-weighted continental mean *n* is 0.062 (0.064 excluding partially-mapped Türkiye), but national means span more than twofold — from 0.036 (Iceland, Malta) to 0.092 (Finland) — along a physiographic gradient: forested, boreal and mountainous countries are roughest, maritime-agricultural lowlands smoothest. The mapping uncertainty alone is large: the continental low–high envelope spans 0.041–0.093, a factor of 2.3. Propagated through the SFINCS 2-D flood model on a test reach, it shifts peak depth by ~3% and inundated extent by ~5% (rougher surfaces give deeper but less widespread water), with a Critical Success Index of 0.86 between scenarios — leaving roughly one-seventh of the flood footprint indeterminate. Benchmarking the 100 m product against an independent 10 m ESA WorldCover 2021 map for two contrasting countries (temperate-lowland Luxembourg, mountainous Montenegro) shows that coarsening to 100 m conserves the mean but cuts variance by ~15%, whereas changing the land-cover product shifts the mean by ~13% — so dataset choice outweighs resolution. A cell-by-cell consistency check confirms the CORINE- and Sentinel-derived fields agree well (Lin's concordance 0.66–0.78) with a small, well-characterised offset. The atlas is released as analysis-ready GeoTIFFs in the ETRS89-LAEA (EPSG:3035) grid with full processing code, as a transparent default roughness layer for 2-D flood inundation modelling across Europe.",

 "By releasing lower, best and upper roughness fields rather than a single map":
 "By releasing lower, best and upper roughness fields rather than a single map, the atlas makes the epistemic uncertainty of the land-cover-to-roughness transfer explicit and propagable. Because roughness is a leading control on simulated flood depth and extent (Pappenberger et al., 2005; Papaioannou et al., 2018), ready-made bounding scenarios let modellers envelope inundation uncertainty without building their own roughness-uncertainty model. The magnitude is not a minor correction: the continental area-weighted *n* ranges from 0.041 to 0.093 (a factor of 2.3), and the envelope is widest in the forest-dominated countries (e.g. Finland 0.061–0.128) where roughness most influences flood hydraulics. In SFINCS this envelope alone shifts peak depth by ~3% and inundation extent by ~5%, leaving ~14% of the flood footprint indeterminate (CSI 0.86; §4.6). Decomposing it by class (Figure 9) shows the width is dominated by the forest classes — which combine a wide per-class spread (0.08–0.16) with extensive area — followed by non-irrigated arable land, which contributes through area alone. The relative-uncertainty field U(x) (Eq. 4) maps where roughness is least constrained — the forested north and mountainous interiors — and the per-class triangular distribution (Eq. 2) provides a ready Monte-Carlo specification for formal propagation.",

 "The two-country benchmark allows the dataset effect and the resolution effect to be separated":
 "The benchmark separates the two effects with a clear practical message. Changing resolution (10 m → 100 m) for a single product left the mean unchanged but reduced its variance by ~15%, whereas changing the product (CORINE vs ESA WorldCover) at comparable resolution shifted the mean by ~13% (Luxembourg 0.065 vs 0.073; Montenegro 0.076 vs 0.086). For the first moment of roughness, then, the thematic choice of land-cover product is the more consequential decision, because the two schemes distribute area differently among classes — above all in how they delimit tree cover and shrubland, which carry the highest roughness — whereas resolution mainly controls sub-grid variability. The practical implication is that a higher-resolution version of the same product chiefly buys variance, while the systematic level of roughness is fixed by the classification scheme and the look-up table — the two elements this atlas makes explicit and adjustable. The absolute values are therefore conditional on CORINE's scheme: the CORINE atlas is the right choice for pan-European consistency and thematic detail (44 classes), and the ESA benchmark indicates the direction and rough magnitude of the sensitivity to that choice. We stress that this “dataset > resolution” finding rests on two contrasting regimes (temperate-lowland Luxembourg, mountainous-Mediterranean Montenegro); the released code makes extending it to further settings straightforward.",
}
for prefix, newtext in NEW.items():
    pat = re.escape(prefix) + r".*?(?=\n\n)"
    t2, k = re.subn(pat, lambda m: newtext, t, count=1, flags=re.DOTALL)
    if k != 1:
        raise SystemExit(f"paragraph not matched: {prefix[:40]!r}")
    t = t2

# 4) reference cleanup
t = t.replace(" [ESA WorldCover accuracy reference.]", "")

open(MD, "w", encoding="utf-8").write(t)
print("tags now:", re.findall(r"\\tag\{([^}]*)\}", t))
import collections
for kind in ["Figure", "Table", r"Eq\."]:
    print(kind, dict(collections.Counter(re.findall(kind + r"\s*([0-9]+|[A-E])\b", t))))
print("adopted -> manuscript.md (backup: manuscript_pre_revision.md)")
