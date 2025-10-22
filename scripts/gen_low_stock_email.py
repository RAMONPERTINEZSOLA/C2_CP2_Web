# scripts/gen_low_stock_email.py
import csv, os, argparse, glob, html, re

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
            if not r:
                continue
            r = (r + [""]*6)[:6]
            drawer, qty, pname, pcode, desc, minsto = r
            rows.append({
                "drawerCode": str(drawer).strip(),
                "stockQty": to_int(qty, fb=None),
                "productName": str(pname).strip(),
                "productCode": str(pcode).strip(),
                "description": str(desc).strip(),
                "minStock": to_int(minsto, fb=None),  # pot venir buit
            })
    return rows

def map_by_code(rows):
    return {r["drawerCode"]: r for r in rows if r["drawerCode"]}

def raw_github_url(repo: str, branch: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"

def find_product_image(drawer_code: str):
    if not drawer_code:
        return None
    patterns = [
        f"docs/**/img/**/*{drawer_code}*.jpg",
        f"docs/**/img/**/*{drawer_code}*.jpeg",
        f"docs/**/img/**/*{drawer_code}*.png",
        f"docs/**/img/**/*{drawer_code}*.webp",
        f"docs/**/images/**/*{drawer_code}*.jpg",
        f"docs/**/images/**/*{drawer_code}*.jpeg",
        f"docs/**/images/**/*{drawer_code}*.png",
        f"docs/**/images/**/*{drawer_code}*.webp",
    ]
    for pat in patterns:
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0].replace("\\", "/")
    return None

def find_html_for_code(drawer_code: str, root_dir: str):
    """Retorna el primer HTML dins root_dir/docs/** que contingui el drawer_code al nom del fitxer."""
    if not drawer_code:
        return None
    pattern = os.path.join(root_dir, "docs", "**", "*.html").replace("\\", "/")
    for p in glob.glob(pattern, recursive=True):
        name = os.path.basename(p)
        if drawer_code in name:
            return p.replace("\\", "/")
    return None

# Patrons per detectar min-stock dins HTML
MIN_PATTERNS = [
    re.compile(r'data[-_]?min[-_]?stock\s*=\s*["\']?(\d+)', re.I),
    re.compile(r'id=["\']min[-_]?stock["\'][^>]*>\s*(\d+)\s*<', re.I),
    re.compile(r'<!--\s*min\s*stock\s*:\s*(\d+)\s*-->', re.I),
    re.compile(r'<meta\s+name=["\']min[-_]?stock["\']\s+content=["\'](\d+)["\']', re.I),
    re.compile(r'(?:min(?:imum)?\s*stock|stock\s*min(?:im)?)\D{0,20}(\d+)', re.I),
]

def read_min_from_html(html_path):
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return None
    for rx in MIN_PATTERNS:
        m = rx.search(text)
        if m:
            return to_int(m.group(1), fb=None)
    return None

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", default=os.environ.get("STOCK_PATH", "docs/stock.csv"))
    ap.add_argument("--prev", default="prev.csv")
    ap.add_argument("--prev-root", default="prev_tree")   # <-- on hem buidat els HTMLs antics
    ap.add_argument("--default-min", type=int, default=int(os.environ.get("DEFAULT_MIN_STOCK", "10")))
    ap.add_argument("--logo-path", default=os.environ.get("LOGO_PATH", "docs/assets/parcsafe-logo.png"))
    ap.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME", "main"))
    args = ap.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "")  # ex: owner/repo

    cur_rows = load_csv(args.current)
    prev_rows = load_csv(args.prev) if os.path.isfile(args.prev) else []

    cur = map_by_code(cur_rows)
    prev = map_by_code(prev_rows)

    # Enriquir minStock (ara distingint arrel actual vs arrel "previa")
    for code, r in cur.items():
        if r["minStock"] is None or r["minStock"] == "":
            html_path = find_html_for_code(code, root_dir=".")
            if html_path:
                html_min = read_min_from_html(html_path)
                if html_min is not None:
                    r["minStock"] = html_min
        if r["minStock"] is None:
            r["minStock"] = args.default_min

    for code, r in prev.items():
        if r["minStock"] is None or r["minStock"] == "":
            html_path = find_html_for_code(code, root_dir=args.prev_root)
            if html_path:
                html_min = read_min_from_html(html_path)
                if html_min is not None:
                    r["minStock"] = html_min
        if r["minStock"] is None:
            r["minStock"] = args.default_min

    newly_low = []  # OK -> LOW en aquest commit (considerant canvis de mínim a l'HTML)

    for code, r in cur.items():
        qty_now = r["stockQty"]
        min_now = r["minStock"]
        if qty_now is None:
            continue
        is_low_now = qty_now <= min_now

        pr = prev.get(code)
        if pr is None:
            was_low_before = False
        else:
            qty_prev = pr["stockQty"]
            min_prev = pr["minStock"]
            was_low_before = (qty_prev is not None) and (qty_prev <= min_prev)

        if is_low_now and not was_low_before:
            img_rel = find_product_image(code)
            img_url = raw_github_url(repo, args.branch, img_rel) if (img_rel and repo) else None
            newly_low.append({
                "drawerCode": code,
                "stockQty": qty_now,
                "minStock": min_now,
                "productName": r["productName"],
                "productCode": r["productCode"],
                "description": r["description"],
                "image_url": img_url,
            })

    # Logo Parcsafe si existeix
    logo_url = None
    if args.logo_path and os.path.isfile(args.logo_path) and repo:
        logo_url = raw_github_url(repo, args.branch, args.logo_path.replace("\\", "/"))

    # HTML polit
    def esc(x): return html.escape(str(x)) if x is not None else ""

    cards_html = []
    for it in newly_low:
        card = f"""
        <div style="display:flex;gap:16px;align-items:flex-start;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin:12px 0;background:#ffffff;">
          {f'<img src="{it["image_url"]}" alt="product" style="width:88px;height:88px;object-fit:cover;border-radius:10px;border:1px solid #e5e7eb" />' if it["image_url"] else ''}
          <div>
            <div style="font-weight:600;font-size:16px;color:#111827">{esc(it["drawerCode"])} <span style="font-weight:400;color:#6b7280">— qty: {it["stockQty"]} (min: {it["minStock"]})</span></div>
            {f'<div style="margin-top:4px;color:#111827"><b>name:</b> {esc(it["productName"])}</div>' if it["productName"] else ''}
            {f'<div style="color:#111827"><b>code:</b> {esc(it["productCode"])}</div>' if it["productCode"] else ''}
            {f'<div style="color:#374151">{esc(it["description"])}</div>' if it["description"] else ''}
          </div>
        </div>
        """
        cards_html.append(card)

    if not newly_low:
        main_block = '<p style="margin:0">✅ No newly low-stock items in this commit.</p>'
    else:
        main_block = f"""
        <p style="margin:0 0 8px 0">⚠️ <b>Newly low-stock items detected (this commit)</b>:</p>
        {''.join(cards_html)}
        """

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
                <div>This email was generated automatically by the repository <code>{esc(repo)}</code>.</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    with open("email_body.html", "w", encoding="utf-8") as f:
        f.write(html_doc)

    with open("count.txt", "w", encoding="utf-8") as f:
        f.write(str(len(newly_low)))
