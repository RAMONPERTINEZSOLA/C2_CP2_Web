# scripts/diff_mail.py
# -*- coding: utf-8 -*-
import csv, os

def to_int(v, default=0):
    try:
        s = (v or "").strip()
        if s in ("--", ""):
            return default
        return int(s)
    except Exception:
        return default

def clean(v):
    s = (v or "").strip()
    return "" if s == "--" else s

def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.reader(f)
        rows = list(r)
    hdr = rows[0]
    idx = {k:i for i,k in enumerate(hdr)}

    stock_field = "stockQty" if "stockQty" in idx else ("qtyStock" if "qtyStock" in idx else None)
    if stock_field is None:
        raise SystemExit("CSV header missing stockQty/qtyStock")

    need = ["drawerCode","productName","productCode","description"]
    for k in need:
        if k not in idx:
            raise SystemExit(f"CSV header missing {k}")

    has_min = "minStock" in idx
    data = {}
    for line in rows[1:]:
        if not line or all(not (c or "").strip() for c in line):
            continue
        while len(line) < len(hdr):
            line.append("")
        d = {
            "drawerCode": clean(line[idx["drawerCode"]]),
            "stockQty":   to_int(line[idx[stock_field]], 0),
            "productName": clean(line[idx["productName"]]),
            "productCode": clean(line[idx["productCode"]]),
            "description": clean(line[idx["description"]]),
            "minStock":   to_int(line[idx["minStock"]], 10) if has_min else 10,
        }
        if d["drawerCode"]:
            data[d["drawerCode"]] = d
    return data

def main():
    curr = read_csv("current.csv")
    prev = read_csv("previous.csv")

    low_events, info_changes = [], []

    for dc, c in curr.items():
        p = prev.get(dc)
        if not p:
            info_changes.append({"drawerCode": dc, "changes": {
                "productName": ["", c["productName"]],
                "productCode": ["", c["productCode"]],
                "description": ["", c["description"]],
            }})
            continue

        info_diff = {}
        for k in ("productName","productCode","description"):
            if (p.get(k,"") or "") != (c.get(k,"") or ""):
                info_diff[k] = [p.get(k,"") or "", c.get(k,"") or ""]
        if info_diff:
            info_changes.append({"drawerCode": dc, "changes": info_diff})

        stock_changed = p["stockQty"] != c["stockQty"]
        crossed = (p["stockQty"] >= c["minStock"]) and (c["stockQty"] < c["minStock"])
        only_stock = (
            (p["productName"] == c["productName"]) and
            (p["productCode"] == c["productCode"]) and
            (p["description"] == c["description"])
        )
        if stock_changed and crossed and only_stock:
            low_events.append({
                "drawerCode": dc,
                "from": p["stockQty"], "to": c["stockQty"],
                "min": c["minStock"],
                "productName": c["productName"], "productCode": c["productCode"],
            })

    low_flag  = "true" if low_events   else "false"
    info_flag = "true" if info_changes else "false"

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
        out.write(f"low_stock={low_flag}\n")
        out.write(f"info_changed={info_flag}\n")

    if low_events:
        lines = ["LOW STOCK ALERTS", "================"]
        for e in low_events:
            lines.append(f"- {e['drawerCode']} — {e['productName']} ({e['productCode']}): {e['from']} → {e['to']}  [min {e['min']}]")
        with open("low_stock_email.txt","w",encoding="utf-8") as f:
            f.write("\n".join(lines))

    if info_changes:
        def esc(s):
            return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        rows = []
        for item in info_changes:
            dc = item["drawerCode"]
            for field,(old,new) in item["changes"].items():
                rows.append(f"<tr><td>{esc(dc)}</td><td>{field}</td><td>{esc(old)}</td><td>{esc(new)}</td></tr>")
        html = f"""<!doctype html><meta charset="utf-8">
<div style="font-family:Poppins,Arial,sans-serif">
  <h2>Product Info Updated</h2>
  <p>S'han registrat canvis a dades de producte:</p>
  <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
    <thead><tr><th>Drawer</th><th>Field</th><th>Old</th><th>New</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>"""
        with open("info_update_email.html","w",encoding="utf-8") as f:
            f.write(html)

if __name__ == "__main__":
    main()
