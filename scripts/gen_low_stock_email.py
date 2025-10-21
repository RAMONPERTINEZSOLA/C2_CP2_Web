# scripts/gen_low_stock_email.py
import csv, os, argparse

def to_int(x, fb=None):
    try:
        return int(str(x).strip())
    except Exception:
        return fb

def load_csv(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, newline='', encoding='utf-8') as f:
        sample = f.read(4096); f.seek(0)
        try:
            has_header = csv.Sniffer().has_header(sample)
        except Exception:
            has_header = False
        reader = csv.reader(f)
        if has_header:
            next(reader, None)
        for r in reader:
            if not r: continue
            r = (r + [""]*6)[:6]
            drawer, qty, pname, pcode, desc, minsto = r
            rows.append({
                "drawerCode": str(drawer).strip(),
                "stockQty": to_int(qty, fb=None),
                "productName": str(pname).strip(),
                "productCode": str(pcode).strip(),
                "description": str(desc).strip(),
                "minStock": to_int(minsto, fb=None),
            })
    return rows

def map_by_code(rows):
    return {r["drawerCode"]: r for r in rows if r["drawerCode"]}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", default=os.environ.get("STOCK_PATH", "docs/stock.csv"))
    ap.add_argument("--prev", default="prev.csv")
    ap.add_argument("--default-min", type=int, default=int(os.environ.get("DEFAULT_MIN_STOCK", "2")))
    args = ap.parse_args()

    cur_rows = load_csv(args.current)
    prev_rows = load_csv(args.prev) if os.path.isfile(args.prev) else []

    cur = map_by_code(cur_rows)
    prev = map_by_code(prev_rows)

    newly_low = []  # només files que HAN ENTRAT a low-stock en aquest commit

    for code, r in cur.items():
        qty_now = r["stockQty"]
        min_now = r["minStock"] if r["minStock"] is not None else args.default_min
        if qty_now is None:
            continue

        # Estat actual low?
        is_low_now = qty_now <= min_now

        # Estat anterior (si existia)
        pr = prev.get(code)
        if pr is None:
            # Si no existia abans, només avisa si ARA és low
            was_low_before = False
        else:
            qty_prev = pr["stockQty"]
            min_prev = pr["minStock"] if pr["minStock"] is not None else args.default_min
            was_low_before = (qty_prev is not None) and (qty_prev <= min_prev)

        if is_low_now and not was_low_before:
            newly_low.append({
                "drawerCode": code,
                "stockQty": qty_now,
                "minStock": min_now,
                "productName": r["productName"],
                "productCode": r["productCode"],
                "description": r["description"],
            })

    # Escriu cos del correu
    with open("email_body.txt", "w", encoding="utf-8") as out:
        if not newly_low:
            out.write("✅ No newly low-stock items in this commit.\n")
        else:
            out.write("⚠️ Newly low-stock items detected (this commit):\n\n")
            for i, r in enumerate(newly_low, 1):
                out.write(f"{i}. {r['drawerCode']} — qty: {r['stockQty']} (min: {r['minStock']})\n")
                if r['productName']:
                    out.write(f"   name: {r['productName']}\n")
                if r['productCode']:
                    out.write(f"   code: {r['productCode']}\n")
                if r['description']:
                    out.write(f"   desc: {r['description']}\n")
                out.write("\n")

    # Guarda recompte per al workflow
    with open("count.txt", "w", encoding="utf-8") as f:
        f.write(str(len(newly_low)))
