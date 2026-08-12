#!/usr/bin/env python3
"""Build utm_data.json for the UTM Content Analysis dashboard page.

Matches the format of scripts/utm_analysis.py — the internal marketer/creative
CVR breakdown Andrew uses. Structure per tort:
  - TOTAL payable/signed/CVR
  - By marketer (Jordan/Charlie/Morane/Untagged)
  - By concept number (SMA 27, HM 12, etc.)
  - By criteria token dimensions (hook, visual, audience, version, suffix, format, concept)
  - By individual creative (>=5 payable, <5 bucketed)

Output: utm_data.json in the same directory as this script.
"""
import json, sys, os, re, datetime, collections

sys.path.insert(0, "/Users/andyoc/Library/Python/3.9/lib/python/site-packages")

from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_KEY = "/Users/andyoc/.hermes/gcp-service-account.json"
SRC_SHEET = "1rnqYRHwbDrgoWjztft__fRt-XGEtsfnDD2MtDt9Wcrw"
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "utm_data.json")

EXCL = {"Rejected - Failed Prequalification", "Rejected - Wrong Number | Spam | Other", "Rejected - Existing Contact"}
SKIP_TOKENS = {'mo','jor','cha','char','ah','ma','ahm','ahmed','15','1/5','1_5','1-5','2-5','1',
               'mo-v2','mo-v1-text','mo-v2-text','jor-v2'}

TORTS = [
    {"id": "sma", "name": "Social Media Addiction", "prefix": "SMA", "tab": "Social Media Addiction"},
    {"id": "hm", "name": "Hernia Mesh", "prefix": "HM", "tab": "Hernia Mesh"},
    {"id": "end", "name": "Endoscopy", "prefix": "END", "tab": "Endoscopy"},
    {"id": "pp", "name": "PowerPort", "prefix": "PP", "tab": "PowerPort"},
    {"id": "pqt", "name": "Paraquat", "prefix": "PQT", "tab": "Paraquat"},
    {"id": "sil", "name": "Silicosis", "prefix": "SIL", "tab": "Silicosis"},
    {"id": "jdc", "name": "JDC IL", "prefix": "JDC", "tab": "Juvenile Detention Center - IL"},
    {"id": "talc", "name": "Talcum", "prefix": "TALC", "tab": "Talcum Powder"},
    {"id": "bm", "name": "Breast Mesh", "prefix": "BM", "tab": "Breast Mesh"},
    {"id": "tvm", "name": "Transvaginal Mesh", "prefix": "TVM", "tab": "Transvaginal Mesh"},
    {"id": "chlor", "name": "Chlorpyrifos", "prefix": "CHLOR", "tab": "Chlorpyrifos"},
]

# Canonical targets from meta-ads-media-buying/references/target-cpls.md (Jul 8 2026)
TARGETS = {
    "sma": 8.2, "hm": 6.7, "end": 10.0, "pp": 9.5, "pqt": 6.4,
    "sil": None, "jdc": 24.8, "talc": 12.5, "bm": None, "tvm": None, "chlor": None
}


def is_num(s):
    s = s.strip()
    return s.isdigit() and len(s) >= 10


def resolve_label(row, idx):
    """Priority: adSetId (non-numeric) → UTM_Content → keyword → UTM_Campaign → UTM_Medium → campaignId → (blank)"""
    adset = (row[idx["adsetid"]] if idx.get("adsetid") is not None and idx["adsetid"] < len(row) else "").strip()
    if adset and not is_num(adset):
        return adset
    for k in ("utm_content", "keyword", "utm_campaign", "utm_medium"):
        v = (row[idx[k]] if idx.get(k) is not None and idx[k] < len(row) else "").strip()
        if v and not is_num(v):
            return v
    camp = (row[idx["campaignid"]] if idx.get("campaignid") is not None and idx["campaignid"] < len(row) else "").strip()
    if camp and not is_num(camp):
        return camp
    return adset if adset else (camp if camp else "(blank)")


def marketer(row, idx):
    """Detect marketer from all tag-bearing cells."""
    t = " ".join(
        (row[idx[k]] if idx.get(k) is not None and idx[k] < len(row) else "")
        for k in ("campaignid", "adsetid", "keyword", "utm_content", "utm_campaign", "utm_medium")
    ).lower()
    if re.search(r'\[jor\]|\(jor\)|jordan', t):
        return "Jordan"
    if re.search(r'\[cha\]|\(cha\)|charlie|cha 15|bro cha', t):
        return "Charlie"
    if re.search(r'\(mo\)|\[mo\]|morane|sh-mo', t):
        return "Morane"
    return "Untagged"


def extract_tokens(label, prefix):
    """Extract concept number, version, and criteria tokens from a label."""
    toks = [t.strip().lower().replace('\u2019', "'") for t in re.findall(r'[\[\(]([^\]\)]+)[\]\)]', label)]
    m = re.match(rf'{prefix}\s*\(?(\d+[\-A-Za-z0-9]*)', label)
    num = m.group(1) if m else None
    vm = re.search(r'\b(v\d|ver\.?\s*\d)\b', label.lower())
    ver = vm.group(1).replace('ver.', 'v').replace(' ', '') if vm else None
    return num, ver, toks


def dim(tok):
    """Classify a token into a dimension."""
    if tok in SKIP_TOKENS:
        return None
    if re.fullmatch(r'h\d', tok):
        return ('hook', tok)
    if tok in ('f', 'n', 'm'):
        return ('audience', tok.upper())
    if re.fullmatch(r'v\d', tok):
        return ('version', tok)
    if tok.startswith('u-') or tok.startswith('ugc') or tok == 'uh':
        return ('visual', tok.replace('uh', 'u-h'))
    if tok in ('sb', 'sj', 'sh', 'ss', 'ad'):
        return ('suffix', tok.upper())
    if tok in ('pov', 'face'):
        return ('format', tok)
    return ('concept', tok)


def analyze_tort(tort, rows, windows, youtube_only=False):
    """Run the full utm_analysis.py-style breakdown on one tort's rows."""
    idx = {h.lower(): i for i, h in enumerate(rows[0])}
    
    # Find column indices
    col_map = {}
    for name, keys in [
        ("created_date", ["created_date", "created date", "createddate", "date"]),
        ("status", ["status"]),
        ("adsetid", ["adsetid", "adset id", "ad_set_id"]),
        ("utm_content", ["utm_content", "utm content", "content"]),
        ("keyword", ["keyword", "kw"]),
        ("utm_campaign", ["utm_campaign", "utm campaign", "campaign"]),
        ("utm_medium", ["utm_medium", "utm medium", "medium"]),
        ("campaignid", ["campaignid", "campaign id", "campaign_id"]),
        ("placement", ["placement"]),
        ("intake_source", ["intake_source", "intake source"]),
    ]:
        for k in keys:
            if k in idx:
                col_map[name] = idx[k]
                break
    
    if "status" not in col_map or "created_date" not in col_map:
        return None
    
    # YouTube filter function
    def is_youtube(r):
        if not youtube_only:
            return True
        # Check placement column first
        if "placement" in col_map and col_map["placement"] < len(r):
            p = (r[col_map["placement"]] or "").strip().lower()
            if p == "youtube":
                return True
        # Check Intake_Source suffix
        if "intake_source" in col_map and col_map["intake_source"] < len(r):
            s = (r[col_map["intake_source"]] or "").strip()
            if s.endswith("-Y"):
                return True
        return False
    
    # Initialize window aggregations
    def new_window():
        return {
            "total": [0, 0],  # [payable, signed]
            "marketers": collections.defaultdict(lambda: [0, 0]),
            "concepts": collections.defaultdict(lambda: [0, 0]),
            "dimensions": collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0])),
            "creatives": collections.defaultdict(lambda: [0, 0]),  # (marketer, label) -> [payable, signed]
        }
    
    W = {wl: new_window() for wl, _, _ in windows}
    
    for r in rows[1:]:
        if len(r) <= col_map["status"]:
            continue
        
        # YouTube filter
        if not is_youtube(r):
            continue
        
        # Parse date
        ds = (r[col_map["created_date"]] if col_map["created_date"] < len(r) else "").strip()
        try:
            d = datetime.datetime.strptime(ds[:10], "%Y-%m-%d") if ds else None
        except ValueError:
            d = None
        
        status = (r[col_map["status"]] or "").strip()
        if status in EXCL:
            continue
        
        sg = 1 if status == "Signed" else 0
        lab = resolve_label(r, col_map)
        mk = marketer(r, col_map)
        num, ver, toks = extract_tokens(lab, tort["prefix"]) if lab != "(blank)" else (None, None, [])
        dims = set(dv for dv in (dim(t) for t in toks) if dv)
        if ver:
            dims.add(('version', ver))
        
        for wl, since, until in windows:
            if until is not None and (d is None or not (since <= d <= until)):
                continue
            w = W[wl]
            w["total"][0] += 1
            w["total"][1] += sg
            w["marketers"][mk][0] += 1
            w["marketers"][mk][1] += sg
            w["creatives"][(mk, lab)][0] += 1
            w["creatives"][(mk, lab)][1] += sg
            if num:
                w["concepts"][num][0] += 1
                w["concepts"][num][1] += sg
            for dn, dv in dims:
                w["dimensions"][dn][dv][0] += 1
                w["dimensions"][dn][dv][1] += sg
    
    # Format output
    result = {
        "tort_id": tort["id"],
        "tort_name": tort["name"],
        "prefix": tort["prefix"],
        "target_cvr": TARGETS.get(tort["id"]),
        "windows": {}
    }
    
    for wl, since, until in windows:
        w = W[wl]
        rng = f"{since.date()}→{until.date()}" if until else "all dates"
        
        # Marketers
        marketers = []
        for mk, (p, s) in sorted(w["marketers"].items(), key=lambda kv: -kv[1][0]):
            marketers.append({"name": mk, "payable": p, "signed": s, "cvr": round(100*s/p, 1) if p else None})
        
        # Concepts (>=5 payable)
        concepts = []
        for num, (p, s) in sorted(w["concepts"].items(), key=lambda kv: -kv[1][0]):
            if p >= 5:
                concepts.append({"concept": f"{tort['prefix']} {num}", "payable": p, "signed": s, "cvr": round(100*s/p, 1) if p else None})
        
        # Dimensions
        dimensions = {}
        for dn in ('hook', 'concept', 'audience', 'visual', 'version', 'suffix', 'format'):
            rows_dim = [(k, v) for k, v in w["dimensions"].get(dn, {}).items() if v[0] >= 8]
            if rows_dim:
                dimensions[dn] = [
                    {"value": k, "payable": v[0], "signed": v[1], "cvr": round(100*v[1]/v[0], 1) if v[0] else None}
                    for k, v in sorted(rows_dim, key=lambda kv: -(kv[1][1]/kv[1][0]))
                ]
        
        # Creatives (>=5 payable, <5 bucketed)
        creatives = []
        bucket_p, bucket_s = 0, 0
        for (mk, lab), (p, s) in sorted(w["creatives"].items(), key=lambda kv: -kv[1][0]):
            if p < 5:
                bucket_p += p
                bucket_s += s
                continue
            creatives.append({"marketer": mk, "label": lab, "payable": p, "signed": s, "cvr": round(100*s/p, 1) if p else None})
        if bucket_p:
            creatives.append({"marketer": "—", "label": f"(<5-lead bucket)", "payable": bucket_p, "signed": bucket_s, "cvr": round(100*bucket_s/bucket_p, 1) if bucket_p else None})
        
        result["windows"][wl] = {
            "range": rng,
            "total": {"payable": w["total"][0], "signed": w["total"][1], "cvr": round(100*w["total"][1]/w["total"][0], 1) if w["total"][0] else None},
            "marketers": marketers,
            "concepts": concepts,
            "dimensions": dimensions,
            "creatives": creatives,
        }
    
    return result


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--youtube-only", action="store_true", help="Filter to YouTube leads only (placement=Youtube or Intake_Source=-Y)")
    args = ap.parse_args()
    
    creds = service_account.Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    sheets = build("sheets", "v4", credentials=creds)
    
    # Windows: 7d, 14d, 30d, Lifetime
    asof = datetime.datetime.now()
    windows = [
        ("7d", asof - datetime.timedelta(days=6), asof),
        ("14d", asof - datetime.timedelta(days=13), asof),
        ("30d", asof - datetime.timedelta(days=29), asof),
        ("Lifetime", None, None),
    ]
    
    torts_out = []
    
    for tort in TORTS:
        print(f"Analyzing {tort['name']}...", file=sys.stderr)
        try:
            result = sheets.spreadsheets().values().get(
                spreadsheetId=SRC_SHEET,
                range=f"'{tort['tab']}'!A1:AZ40000"
            ).execute()
            rows = result.get("values", [])
            if len(rows) < 2:
                print(f"  {tort['name']}: empty", file=sys.stderr)
                continue
            
            analysis = analyze_tort(tort, rows, windows, youtube_only=args.youtube_only)
            if analysis:
                torts_out.append(analysis)
                total_7d = analysis["windows"]["7d"]["total"]
                print(f"  {tort['name']}: 7d payable={total_7d['payable']} signed={total_7d['signed']} cvr={total_7d['cvr']}%", file=sys.stderr)
            
        except Exception as e:
            print(f"  {tort['name']}: ERROR {e}", file=sys.stderr)
    
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4))).strftime("%Y-%m-%d %H:%M EST"),
        "youtube_only": args.youtube_only,
        "torts": torts_out,
    }
    
    with open(OUT_PATH, "w") as f:
        json.dump(out, f)
    
    print(f"\nWrote {OUT_PATH}: {len(torts_out)} torts, youtube_only={args.youtube_only}", file=sys.stderr)


if __name__ == "__main__":
    main()
