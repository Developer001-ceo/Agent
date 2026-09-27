import json, os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe2_out.json")
res = {"ok": False}
def block(ws, r1, c1, r2, c2):
    ur = ws.Range(ws.Cells(r1, c1), ws.Cells(r2, c2))
    vals = ur.Value; forms = ur.Formula
    nr, nc = r2 - r1 + 1, c2 - c1 + 1
    if nr == 1 and nc == 1: vals = ((vals,),); forms = ((forms,),)
    elif nr == 1: vals = (tuple(vals),); forms = (tuple(forms),)
    elif nc == 1: vals = tuple((v,) for v in vals); forms = tuple((f,) for f in forms)
    out = []
    for ri in range(nr):
        for ci in range(nc):
            v = vals[ri][ci]; f = forms[ri][ci]
            if v is not None or (isinstance(f, str) and f.startswith("=")):
                out.append([r1 + ri, c1 + ci,
                            str(v)[:400] if v is not None else None,
                            str(f)[:400]])
    return out
try:
    import win32com.client
    xl = win32com.client.GetActiveObject("Excel.Application")
    wb = xl.Workbooks("Lab7_8-v1.xlsx")
    s7 = wb.Worksheets("Lab 7"); s8 = wb.Worksheets("Lab 8"); sd = wb.Worksheets("SustainabilityData")
    res = {"ok": True,
           "lab7_rest": block(s7, 85, 1, 130, 13),
           "lab8_full": block(s8, 1, 1, 130, 13),
           "sd_headers": block(sd, 1, 1, 8, 108),
           "sd_stats_area": block(sd, 1040, 1, 1070, 105),
           "task1_check": block(sd, 5, 93, 8, 100),
           "ztest_area": block(s7, 31, 4, 41, 13)}
except Exception as e:
    res = {"ok": False, "error": repr(e)}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(res, fh, ensure_ascii=False, indent=1)
print("probe2 ok=", res.get("ok"), "err=", res.get("error"))
