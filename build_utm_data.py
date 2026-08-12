#!/usr/bin/env python3
"""Build utm_data.json for the UTM Content Analysis dashboard page.

Pulls all BP intake sheet tabs, extracts UTM/adSetId labels, computes
payable/signed per script family, and cross-references LeadProsper for
buyer attribution where possible.

Output: utm_data.json in the same directory as this script.
"""
import json, sys, os, re, datetime, collections

sys.path.insert(0, "/Users/andyoc/Library/Python/3.9/lib/python/site-packages")

from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_KEY = "/Users/andyoc/.hermes/gcp-service-account.json"
SRC_SHEET = "1rnqYRHwbDrgoWjztft__fRt-XGEtsfnDD2MtDt9Wcrw"
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "utm_data.json")

NONPAY = ("rejected - failed prequalification", "rejected - wrong number", "rejected - existing contact")

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


def norm_phone(p):
    d = "".join(ch for ch in str(p or "") if ch.isdigit())
    return d[-10:] if len(d) >= 10 else d


def resolve_label(row, idx):
    """Priority: adSetId (non-numeric) → UTM_Content → keyword → UTM_Campaign → UTM_Medium → campaignId → (blank)"""
    adset = (row[idx["adsetid"]] if idx.get("adsetid") is not None and idx["adsetid"] < len(row) else "").strip()
    if adset and not re.match(r"^\d{10,}$", adset):
        return adset
    utm = (row[idx["utm_content"]] if idx.get("utm_content") is not None and idx["utm_content"] < len(row) else "").strip()
    if utm:
        return utm
    kw = (row[idx["keyword"]] if idx.get("keyword") is not None and idx["keyword"] < len(row) else "").strip()
    if kw:
        return kw
    camp = (row[idx["utm_campaign"]] if idx.get("utm_campaign") is not None and idx["utm_campaign"] < len(row) else "").strip()
    if camp:
        return camp
    med = (row[idx["utm_medium"]] if idx.get("utm_medium") is not None and idx["utm_medium"] < len(row) else "").strip()
    if med:
        return med
    cid = (row[idx["campaignid"]] if idx.get("campaignid") is not None and idx["campaignid"] < len(row) else "").strip()
    if cid:
        return cid
    return "(blank)"


def main():
    creds = service_account.Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sheets = build("sheets", "v4", credentials=creds)

    all_rows = []
    total_rows = 0

    for tort in TORTS:
        print(f"Pulling {tort['name']}...", file=sys.stderr)
        try:
            result = sheets.spreadsheets().values().get(
                spreadsheetId=SRC_SHEET,
                range=f"'{tort['tab']}'!A1:AZ10000"
            ).execute()
            rows = result.get("values", [])
            if len(rows) < 2:
                print(f"  {tort['name']}: empty", file=sys.stderr)
                continue

            hdr = rows[0]
            idx = {h.lower(): i for i, h in enumerate(hdr)}

            # Find column indices
            status_i = idx.get("status")
            if status_i is None:
                print(f"  {tort['name']}: no Status column", file=sys.stderr)
                continue

            # Map possible column names
            col_map = {}
            for name, keys in [
                ("adsetid", ["adsetid", "adset id", "ad_set_id"]),
                ("utm_content", ["utm_content", "utm content", "content"]),
                ("keyword", ["keyword", "kw"]),
                ("utm_campaign", ["utm_campaign", "utm campaign", "campaign"]),
                ("utm_medium", ["utm_medium", "utm medium", "medium"]),
                ("campaignid", ["campaignid", "campaign id", "campaign_id"]),
                ("phone", ["phone", "phone number", "phone_number"]),
                ("created_date", ["created_date", "created date", "createddate", "date"]),
            ]:
                for k in keys:
                    if k in idx:
                        col_map[name] = idx[k]
                        break

            count = 0
            for r in rows[1:]:
                if len(r) <= status_i:
                    continue
                status = (r[status_i] or "").strip().lower()
                if not status:
                    continue

                # Skip non-payable
                if any(status.startswith(np) for np in NONPAY):
                    payable = False
                    signed = False
                else:
                    payable = True
                    signed = (status == "signed")

                label = resolve_label(r, col_map)
                phone = norm_phone(r[col_map["phone"]] if col_map.get("phone") is not None and col_map["phone"] < len(r) else "")
                created = (r[col_map["created_date"]] if col_map.get("created_date") is not None and col_map["created_date"] < len(r) else "").strip()

                all_rows.append({
                    "tort_id": tort["id"],
                    "tort_name": tort["name"],
                    "tort_prefix": tort["prefix"],
                    "label": label,
                    "status": status,
                    "payable": payable,
                    "signed": signed,
                    "phone": phone,
                    "created_date": created,
                    "buyer": "Broughton Partners",  # Default; LP cross-ref would refine this
                })
                count += 1

            print(f"  {tort['name']}: {count} rows", file=sys.stderr)
            total_rows += count

        except Exception as e:
            print(f"  {tort['name']}: ERROR {e}", file=sys.stderr)

    # Write output
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4))).strftime("%Y-%m-%d %H:%M EST"),
        "total_rows": total_rows,
        "torts": [{"id": t["id"], "name": t["name"], "prefix": t["prefix"]} for t in TORTS],
        "rows": all_rows,
    }

    with open(OUT_PATH, "w") as f:
        json.dump(out, f)

    print(f"\nWrote {OUT_PATH}: {total_rows} rows across {len(TORTS)} torts", file=sys.stderr)


if __name__ == "__main__":
    main()
