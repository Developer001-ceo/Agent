import json, os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe_out.json")
res = {"ok": False}
try:
    import win32com.client
    xl = win32com.client.GetActiveObject("Excel.Application")
    res = {"ok": True, "version": xl.Version, "workbooks": []}
    for wb in xl.Workbooks:
        w = {"name": wb.Name, "path": wb.Path, "saved": bool(wb.Saved), "sheets": []}
        for ws in wb.Worksheets:
            sh = {"name": ws.Name, "cells": [], "errors": []}
            try:
                ur = ws.UsedRange
                r0, c0 = ur.Row, ur.Column
                nr = min(ur.Rows.Count, 300); nc = min(ur.Columns.Count, 12)
                vals = ur.Value
                forms = ur.Formula
                if nr == 1 and nc == 1:
                    vals = ((vals,),); forms = ((forms,),)
                elif nr == 1:
                    vals = (tuple(vals),); forms = (tuple(forms),)
                elif nc == 1:
                    vals = tuple((v,) for v in vals); forms = tuple((f,) for f in forms)
                for ri in range(min(nr, len(vals))):
                    for ci in range(min(nc, len(vals[ri]))):
                        v = vals[ri][ci]; f = forms[ri][ci]
                        if v is not None or (isinstance(f, str) and f.startswith("=")):
                            sh["cells"].append([r0 + ri, c0 + ci,
                                                str(v)[:160] if v is not None else None,
                                                str(f)[:160]])
            except Exception as e:
                sh["errors"].append(repr(e))
            w["sheets"].append(sh)
        res["workbooks"].append(w)
except Exception as e:
    res = {"ok": False, "error": repr(e)}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(res, fh, ensure_ascii=False, indent=1)
print("dumped ok=", res.get("ok"), "err=", res.get("error"),
      "wbs=", [wb.get("name") for wb in res.get("workbooks", [])])
