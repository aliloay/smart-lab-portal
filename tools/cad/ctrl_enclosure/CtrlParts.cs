// Reusable (smart) bin control box, 2026-10-24 - a fourth part of Builder. The bin itself is finished (servo, load
// cell, reed switch, LCD, PN532 on the bin); this box beside it holds the ESP32, the 5 V and 3.3 V breadboards and
// the buck. Body and plate are the door box's (BuildBody / BuildPlate, all from params); the lid is plain: screw
// holes, locating tabs 0.3 inside the walls, bold raised title and labels over the glands.
using System;
using System.Collections.Generic;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

public partial class Builder
{
    static partial void BuildCtrlKind(P p, string outDir, string which)
    {
        if (which == "all" || which == "body") BuildBody(p, outDir);
        if (which == "all" || which == "panel") BuildCtrlLid(p, outDir);
        if (which == "all" || which == "plate") BuildPlate(p, outDir);
    }

    static void BuildCtrlLid(P p, string dir)
    {
        var E = p.O("envelope"); var F = p.O("fasteners"); var FP = p.O("front_panel"); var C = p.O("print");
        double W = E.N("width"), H = E.N("height"), t = FP.N("thickness"), wall = E.N("wall"), r = E.N("corner_radius"), clr = C.N("clearance");
        NewPart();
        Open("Front Plane"); RoundRect(-W / 2, 0, W / 2, H, r); var sk = Close();
        Extrude(sk, t, false, false, "Lid");
        double ci = F.N("corner_boss_inset");
        Open("Front Plane"); foreach (var c in new[] { new[] { -W / 2 + ci, ci }, new[] { W / 2 - ci, ci }, new[] { -W / 2 + ci, H - ci }, new[] { W / 2 - ci, H - ci } })
            Circle(c[0], c[1], F.N("screw_clear_d")); sk = Close();
        Extrude(sk, t, true, true, "Screw holes");
        double tl = FP.N("locating_tab_len"), tt = FP.N("locating_tab_t"), tin = wall + clr;
        Behind(FP.N("locating_tab_h"), () => {
            RectXY(-tl / 2, tin, tl / 2, tin + tt); RectXY(-tl / 2, H - tin - tt, tl / 2, H - tin);
            RectXY(-W / 2 + tin, H / 2 - tl / 2, -W / 2 + tin + tt, H / 2 + tl / 2); RectXY(W / 2 - tin - tt, H / 2 - tl / 2, W / 2 - tin, H / 2 + tl / 2); }, "Locating tabs");
        Open(Plane("Front Plane", t));
        bool txt = Text(0, FP.N("title_y"), FP.S("title"), FP.N("title_height"));
        foreach (var o in FP.A("labels")) { var q = new P((Dictionary<string, object>)o); Text(q.N("x"), q.N("y"), q.S("text"), q.N("h")); }
        sk = Close();
        if (txt) Extrude(sk, FP.N("raised_height"), false, false, "Labels (raised)");
        Save(dir, Prefix + "_FrontPanel");
    }
}
