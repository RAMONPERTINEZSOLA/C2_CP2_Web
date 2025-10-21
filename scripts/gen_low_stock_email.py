# scripts/gen_low_stock_email.py
import csv, os

csv_path = os.environ.get("STOCK_PATH", "docs/stock.csv")
default_min = int(os.environ.get("DEFAULT_MIN_STOCK", "2"))

rows = []
with open(csv_path, newline='', encoding='utf-8') as f:
    sample = f.read(4096)
    f.seek(0)
    try:
        has_header = csv.Sniffer().has_header(sample)
    except Exception:
        has_header = False

    reader = csv.reader(f)
    if has_header:
        next(reader, None)

    for r in reader:
        if not r:
            continue
        # Normalitza longitud a 6 columnes:
        # 0:drawerCode, 1:stockQty, 2:productName, 3:productCode, 4:description, 5:minStock(opc)
        r = (r + [""]*6)[:6]
        drawer, qty, pname, pcode, desc, minsto = r

        def to_int(x, fb=0):
            try:
                return int(str(x).strip())
            except Exception:
                return fb

        qty_i = to_int(qty, fb=-1)              # -1 si buit/no vàlid
        min_i = to_int(minsto, fb=default_min)  # min per defecte si buit

        # Marca low-stock si qty és vàlida i <= min
        if qty_i >= 0 and qty_i <= min_i:
            rows.append((
                drawer.strip(),
                qty_i,
                min_i,
                str(pname).strip(),
                str(pcode).strip(),
                str(desc).strip(),
            ))

# Escriu cos del correu
with open("email_body.txt", "w", encoding="utf-8") as out:
    if not rows:
        out.write("✅ No low-stock items detected.\n")
    else:
        out.write("⚠️ Low stock detected on the following items:\n\n")
        for i, r in enumerate(rows, 1):
            drawer, qty_i, min_i, pname, pcode, desc = r
            out.write(f"{i}. {drawer} — qty: {qty_i} (min: {min_i})\n")
            if pname:
                out.write(f"   name: {pname}\n")
            if pcode:
                out.write(f"   code: {pcode}\n")
            if desc:
                out.write(f"   desc: {desc}\n")
            out.write("\n")

# Guarda el recompte per al pas del workflow
with open("count.txt", "w", encoding="utf-8") as f:
    f.write(str(len(rows)))
