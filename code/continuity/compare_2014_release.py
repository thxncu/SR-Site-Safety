#!/usr/bin/env python3
"""Compare the SR-Site screening records in the 2014 release of the SKB FEP database
(distributed with SKB TR-14-07) with the SR-Site archive extraction in data/,
and summarize how SR-PSU re-screened the fixed 200 coverage-related exclusions
(Supplementary Section S8). No retrieval-dependent subset is used.

Requires the official archive (see source_manifest.csv) and fmp2sqlite from fmptools
(https://github.com/evanmiller/fmptools, tested at commit 273871964843), because the 2014
release uses the FileMaker 12 runtime format.
Usage: python code/continuity/compare_2014_release.py <archive.zip> <path/to/fmp2sqlite>
"""
import hashlib, re, sqlite3, subprocess, sys, tempfile, unicodedata, zipfile
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]; DATA = ROOT / "data"
TABLES = {"NEA mapping_SRSite": "NEA mapping_SRSite", "HandlingNEAFEPs_SRSite": "HandlingNEAFEPs_SRSite",
          "NEA mapping_SR-PSU": "Tabell"}
COVERED = {"Heading only, covered by other NEA project FEPs", "Too general, covered by other NEA project FEPs"}

def n(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return ""
    s = unicodedata.normalize("NFKC", str(v)).replace("\x00", " ").replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    return re.sub(r"\s+", " ", s).strip()

def load(archive, fmp2sqlite):
    out = {}
    with tempfile.TemporaryDirectory(dir=ROOT.parent) as tmp, zipfile.ZipFile(archive) as z:
        for name, table in TABLES.items():
            src = Path(tmp) / f"{name}.fmpur"; src.write_bytes(z.read(f"SKB FEP database/{name}.fmpur"))
            db = Path(tmp) / f"{name}.sqlite"
            subprocess.run([fmp2sqlite, str(src), str(db)], check=True, capture_output=True)
            out[name] = pd.read_sql(f'select * from "{table}"', sqlite3.connect(db))
    return out

def main(archive, fmp2sqlite):
    manifest = pd.read_csv(ROOT / "source_manifest.csv")
    expected = manifest.loc[manifest.file_name.eq("1477291 - SKB TR-14-07 FEP database.zip"), "sha256"].iat[0]
    if hashlib.sha256(Path(archive).read_bytes()).hexdigest() != expected:
        raise ValueError("The 2014 archive checksum does not match source_manifest.csv")
    t = load(archive, fmp2sqlite)
    pop = pd.read_csv(DATA / "pfep_relevance_population_1671.csv", dtype=str)
    nr = pd.read_csv(DATA / "not_relevant_370_normalized.csv", dtype=str)
    cov = pd.read_csv(DATA / "coverage_evidence_200.csv", dtype=str)
    net = pd.read_csv(DATA / "pfep_srsite_network_edges.csv", dtype=str)
    m = t["NEA mapping_SRSite"].assign(id=lambda d: d.NEA_Project_FEP_ID.map(n))
    for d in (pop, nr, cov, net): d["id"] = d["pfep_id"].map(n)
    j = pop.merge(m, on="id", how="left"); jn = nr.merge(m, on="id", how="left")
    C = set(cov.id)
    if len(C) != 200:
        raise ValueError("The fixed coverage cohort must contain 200 distinct PFEPs")
    diff = lambda a, b, d: int((d[a].map(n) != d[b].map(n)).sum())
    h = t["HandlingNEAFEPs_SRSite"]; e14 = set(zip(h.NEA_Project_FEP_ID.map(n), h.SRSite_FEP_ID.map(n)))
    e10 = set(zip(net.id, net.sr_id.map(n)))
    rev = j[j.revision_date.map(n) != j.Revision_date.map(n)]
    ps = t["NEA mapping_SR-PSU"].assign(id=lambda d: d.NEA_Project_FEP_ID.map(n))
    s200 = ps[ps.id.isin(C)]
    rows = [
        ("Records matched by identifier", f"{int(j.Relevance.notna().sum())} of {len(pop)}"),
        ("Relevance status (all records): differences", diff("relevance", "Relevance", j)),
        ("Database version field: differences", diff("database_version", "Database_version", j)),
        ("Screening motivation (370 not-relevant records): differences", diff("relevance_motivation_raw", "Relevance_motivation", jn)),
        ("Deliberation note (370): differences", diff("comments_needs_discussion_raw", "Comments_Needs_discussion", jn)),
        ("Assessment-basis comment (370): differences", diff("assessment_basis_comment_raw", "Assessment_basis_comment", jn)),
        ("Mapping field (370): differences", diff("legacy_mapping_raw", "Mapping", jn)),
        ("Revision date (all records): differences", "; ".join(f"{r.id} ({r.relevance}): {n(r.revision_date)} to {n(r.Revision_date)}" for r in rev.itertuples()) or 0),
        ("Handling associations (unique PFEP to SR-Site FEP pairs), SR-Site archive / 2014 release", f"{len(e10)} / {len(e14)}"),
        ("Handling associations added / removed", f"{len(e14 - e10)} / {len(e10 - e14)}"),
        ("Handling associations on the 200 covered-elsewhere records, 2014", sum(p in C for p, _ in e14)),
        ("SR-PSU re-screening: the 200 judged not relevant", int(s200.Relevance.map(n).eq("Not relevant").sum())),
        ("SR-PSU re-screening: the 200 with the same covered-elsewhere wording", int(s200.Relevance_motivation.map(n).isin(COVERED).sum())),
    ]
    out = pd.DataFrame(rows, columns=["check", "result"]); out.to_csv(DATA / "database_release_comparison_2014.csv", index=False)
    print(out.to_string(index=False))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
