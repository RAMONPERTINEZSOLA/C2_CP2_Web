# scripts/gen_low_stock_email.py
import csv, os, argparse, html

def to_int(x, fb=None):
    try:
        return int(str(x).strip())
    except Exception:
        return fb

def read_csv_rows(path):
    """
    Llegeix docs/stock.csv acceptant:
      - capçalera amb noms (drawerCode, stockQty, productName, productCode, description, minStock)
      - o sense capçalera amb les 6 columnes en aquest ordre
    Retorna llista de dicts.
    """
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        sample = f.read(4096); f.seek(0)
        sniffer_has_header = False
        try:
            sniffer_has_header = csv.Sniffer().has_header(sample)
        except Exception:
            pass

        reader = csv.reader(f)
        header = None
        if sniffer_has_header:
            header = next(reader, None)
            if header:
                header = [h.strip() for h in header]

        for r in reader:
            if not r: 
                continue
            r = [c.strip() for c in r]
            # per capçalera
            if header and len(header) >= 2:
                cols = {header[i].lower(): (r[i] if i < len(r) else "") for i in range(len(header))}
                drawer = cols.get("drawercode", cols.get("drawer_code", cols.get("drawer", "")))
                qty    = cols.get("stockqty", cols.get("stock_qty", cols.get("qty", "")))
                pname  = cols.get("productname", cols.get("product_name", ""))
                pcode  = cols.get("productcode", cols.get("product_code", ""))
                desc   = cols.get("description", cols.get("desc", ""))
                minst  = cols.get("minstock", cols.get("min_stock", cols.get("min", "")))
            else:
                # sense capçalera: 6 columnes en ordre
                r = (r + [""]*6)[:6]
                drawer, qty, pname, pcode, desc, minst = r

            rows.append({
                "drawerCode": drawer,
                "stockQty": to_int(qty, fb=None),
                "productName": pname,
                "productCode": pcode,
                "description": desc,
                "minStockRaw": minst,   # text original (per si cal parsejar)
            })
    return rows

def raw_github_url(repo: str, branch: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"

def find_product_image(drawer_code: str):
    """
    Busca imatge per drawerCode dins docs/**/img o docs/**/images
    """
    import glob
    if not drawer_code:
        return None
    pats = [
        f"docs/**/img/**/*{drawer_code}*.jpg",
        f"docs/**/img/**/*{drawer_code}*.jpeg",
        f"docs/**/img/**/*{drawer_code}*.png",
        f"docs/**/img/**/*{drawer_code}*.webp",
        f"docs/**/images/**/*{drawer_code}*.jpg",
        f"docs/**/images/**/*{drawer_code}*.jpeg",
        f"docs/**/images/**/*{drawer_code}*.png",
        f"docs/**/images/**/*{drawer_code}*.webp",
    ]
    for pat in pats:
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0].replace("\\", "/")
    return None

def build_html(low_rows, logo_url, repo):
    def esc(x): return html.escape(str(x)) if x is not None else ""
    cards = []
    for it in low_rows:
        card = f"""
        <div style="display:flex;gap:16px;align-items:flex-start;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin:12px 0;background:#ffffff;">
          {f'<img src="{it.get("image_url")}" alt="product" style="width:88px;height:88px;object-fit:cover;border-radius:10px;border:1px solid #e5e7eb" />' if it.get("image_url") else ''}
          <div>
            <div style="font-weight:600;font-size:16px;color:#111827">{esc(it["drawerCode"])} <span style="font-weight:400;color:#6b7280">— qty: {it["stockQty"]} (min: {it["minStock"]})</span></div>
            {f'<div style="margin-top:4px;color:#111827"><b>name:</b> {esc(it["productName"])}</div>' if it["productName"] else ''}
            {f'<div style="color:#111827"><b>code:</b> {esc(it["productCode"])}</div>' if it["productCode"] else ''}
            {f'<div style="color:#374151">{esc(it["description"])}</div>' if it["description"] else ''}
          </div>
        </div>
        """
        cards.append(card)

    main_block = (
        '<p style="margin:0">✅ No items below minimum stock.</p>'
        if not cards else
        f'<p style="margin:0 0 8px 0">⚠️ <b>{len(low_rows)} item(s) below minimum stock</b>:</p>' + "".join(cards)
    )

    html_doc = f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f8fafc">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
      <tr>
        <td align="center" style="padding:24px">
          <table role="presentation" cellpadding="0" cellspacing="0" width="680" style="max-width:680px;background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;overflow:hidden">
            <tr>
              <td style="background:#0ea5e9;padding:18px 22px;color:#fff">
                <div style="display:flex;align-items:center;gap:12px">
                  {f'<img src="{logo_url}" alt="Parcsafe" style="height:28px;border:0;display:block" />' if logo_url else ''}
                  <div style="font-size:18px;font-weight:700;letter-spacing:0.3px">LOW STOCK ALERT</div>
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:22px 22px 8px 22px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#0f172a;line-height:1.45">
                {main_block}
              </td>
            </tr>
            <tr>
              <td style="padding:0 22px 22px 22px;font-size:12px;color:#64748b">
                <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0" />
                <div>Generated automatically by <code>{html.escape(repo or "")}</code>.</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return html_doc

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", required=True)
    ap.add_argument("--logo-path", default=os.environ.get("LOGO_PATH", "docs/assets/parcsafe-logo.png"))
    ap.add_argument("--default-min", type=int, default=int(os.environ.get("DEFAULT_MIN_STOCK", "10")))
    ap.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", "main"))
    args = ap.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "")  # owner/repo

    # Llegeix CSV
    rows = read_csv_rows(args.current)

    # Calcula minStock efectiu i filtra per stockQty < minStock
    low_rows = []
    for r in rows:
        qty = r["stockQty"]
        min_raw = r["minStockRaw"]
        min_effective = to_int(min_raw, fb=args.default_min)
        # condició estricta: minStock > stockQty  <=> stockQty < minStock
        if qty is not None and min_effective is not None and qty < min_effective:
            low_rows.append({
                "drawerCode": r["drawerCode"],
                "stockQty": qty,
                "minStock": min_effective,
                "productName": r["productName"],
                "productCode": r["productCode"],
                "description": r["description"],
            })

    # Enriquir amb imatge si existeix
    logo_url = None
    if args.logo_path and os.path.isfile(args.logo_path) and repo:
        logo_url = raw_github_url(repo, args.branch, args.logo_path.replace("\\", "/"))

    for it in low_rows:
        img_rel = find_product_image(it["drawerCode"])
        it["image_url"] = raw_github_url(repo, args.branch, img_rel) if (img_rel and repo) else None

    # Escriu HTML i recompte
    html_doc = build_html(low_rows, logo_url, repo)
    with open("email_body.html", "w", encoding="utf-8") as f:
        f.write(html_doc)

    with open("count.txt", "w", encoding="utf-8") as f:
        f.write(str(len(low_rows)))
