// Consumables bin (resistor bin) base, 2026-10-24 - a third part of Builder (helpers in door_enclosure/Build.cs,
// face / Grow helpers in env_enclosure/EnvParts.cs). A desk console: flat top carrying the acrylic scale (taped down,
// owner: tape better than screws, a 1 mm recess centres it), the front slopes down with the 16x2 LCD in it so it reads
// well from a standing position, electronics on the floor plate (screwed up into the body from below).
// Coordinates: x across (centred), y up (0 = underside of the body, the floor plate is below it), z from the back (0)
// to the front (depth).
using System;
using System.Collections.Generic;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

public partial class Builder
{
    static partial void BuildBinKind(P p, string outDir, string which)
    {
        if (which == "all" || which == "body") BuildBinBody(p, outDir);
        if (which == "all" || which == "floor") BuildBinFloor(p, outDir);
        if (which == "all" || which == "cup") BuildBinCup(p, outDir);
    }

    /// Lines through model points (mm) in a face sketch: any rectangle on a sloped face.
    static void PolyAt(Sketch s, double[][] q)
    {
        for (int i = 0; i < q.Length; i++)
        {
            var a = ToSk(s, q[i]); var b = ToSk(s, q[(i + 1) % q.Length]);
            doc.SketchManager.CreateLine(a[0] * MM, a[1] * MM, 0, b[0] * MM, b[1] * MM, 0);
        }
    }
    static double[] At(double[] m, double[] u, double ku, double[] v, double kv) { return Add(Add(m, u, ku), v, kv); }

    static void BuildBinBody(P p, string dir)
    {
        var E = p.O("envelope"); var F = p.O("fasteners"); var B = p.O("bin_body");
        double W = E.N("width"), D = E.N("depth"), H = E.N("height"), t = E.N("wall"), Hf = B.N("front_h"), Dt = B.N("top_flat");
        NewPart();
        // 1. side profile (Right Plane offset: sketch x = -z, y = y), extruded across the width
        Open(Plane("Right Plane", -W / 2));
        var pts = new double[,] { { 0, 0 }, { D, 0 }, { D, Hf }, { Dt, H }, { 0, H } };
        for (int i = 0; i < 5; i++) { int j = (i + 1) % 5; doc.SketchManager.CreateLine(-pts[i, 0] * MM, pts[i, 1] * MM, 0, -pts[j, 0] * MM, pts[j, 1] * MM, 0); }
        var sk = Close();
        Grow(sk, W, "Block", 0, -W / 2, W / 2);
        // 2. shell, open underneath
        var fb = FaceThrough(new double[] { 0, 1, 0 }, new double[] { 0, 0, D / 2 });
        if (fb == null) throw new Exception("Bin body: no bottom face");
        doc.ClearSelection2(true); ((Entity)fb).Select4(false, null);
        double vb = Volume(); doc.InsertFeatureShell(t * MM, false);
        if (Volume() >= vb - 1e-9) throw new Exception("Bin body: shell failed");
        // 3. corner columns (fused with the side walls) with heat-set inserts from below for the floor plate
        double ci = F.N("corner_boss_inset"); var bx0 = (double[])((PartDoc)doc).GetPartBox(true);
        var cols = new[] { new[] { -W / 2 + ci, ci }, new[] { W / 2 - ci, ci }, new[] { -W / 2 + ci, D - ci }, new[] { W / 2 - ci, D - ci } };
        Open("Top Plane"); foreach (var c in cols) Circle(c[0], -c[1], F.N("corner_boss_d")); sk = Close();
        Grow(sk, B.N("column_h"), "Floor columns", 1, bx0[1] / MM, bx0[4] / MM);
        Open("Top Plane"); foreach (var c in cols) Circle(c[0], -c[1], F.N("insert_hole_d")); sk = Close();
        Extrude(sk, F.N("insert_hole_depth"), true, false, "Floor insert holes");
        // 4. scale: 1 mm recess = bottom acrylic + 0.3 (tape inside it), load-cell cable slot beside it
        var S = p.O("scale"); string top = Plane("Top Plane", H);
        Open(top); Circle(S.N("x"), -S.N("z"), S.N("recess_d")); sk = Close();
        Extrude(sk, S.N("recess_depth"), true, false, "Scale recess");
        Open(top); Rect(S.N("cable_x"), -S.N("z"), S.N("cable_w"), S.N("cable_l")); sk = Close();
        Extrude(sk, t + 1, true, false, "Load-cell cable slot");
        // 5. LCD in the slope: window = black frame + 0.3, four M2.5 bosses inside at the 1602 hole pattern
        var LC = p.O("lcd");
        double L = Math.Sqrt((D - Dt) * (D - Dt) + (H - Hf) * (H - Hf));
        double[] n = { 0, (D - Dt) / L, (H - Hf) / L };                       // outward normal of the slope
        double[] v = { 0, (H - Hf) / L, -(D - Dt) / L };                      // up the slope
        double[] u = { 1, 0, 0 };
        double[] m = Add(new double[] { 0, (H + Hf) / 2, (Dt + D) / 2 }, v, LC.N("offset_up"));
        double a = LC.N("window_w") / 2, b = LC.N("window_h") / 2;
        var s = OpenOnFace(FaceThrough(n, m), "LCD window");
        PolyAt(s, new[] { At(m, u, -a, v, -b), At(m, u, a, v, -b), At(m, u, a, v, b), At(m, u, -a, v, b) });
        sk = Close();
        Extrude(sk, t + 1, true, false, "LCD window");
        double[] mi = Add(m, n, -t), hx = { LC.N("hole_dx") / 2, LC.N("hole_dy") / 2 };
        s = OpenOnFace(FaceThrough(n, mi), "LCD bosses");
        foreach (var ku in new[] { -1, 1 }) foreach (var kv in new[] { -1, 1 }) CircleAt(s, At(mi, u, ku * hx[0], v, kv * hx[1]), LC.N("boss_d"));
        sk = Close();
        Extrude(sk, LC.N("boss_h"), false, false, "LCD bosses");
        double[] mt = Add(mi, n, -LC.N("boss_h"));
        s = OpenOnFace(FaceThrough(n, At(mt, u, hx[0], v, hx[1])), "LCD pilots");
        foreach (var ku in new[] { -1, 1 }) foreach (var kv in new[] { -1, 1 }) CircleAt(s, At(mt, u, ku * hx[0], v, kv * hx[1]), F.N("pilot_m25_d"));
        sk = Close();
        Extrude(sk, LC.N("boss_h") + t - 1, true, false, "LCD M2.5 pilots");
        // 6. right wall: ESP32 USB-C (a notch from the bottom edge); back wall: 12 V gland; side vents
        var U = p.O("usb_access");
        Open(Plane("Right Plane", W / 2)); Rect(-U.N("z"), U.N("y"), U.N("w"), U.N("h")); sk = Close();
        Extrude(sk, t + 1, true, false, "USB access");
        var DC = p.O("dc_in");
        Open("Front Plane"); Circle(DC.N("x"), DC.N("y"), DC.N("d")); sk = Close();
        Extrude(sk, t + 1, true, false, "DC in");
        var V = p.O("vents");
        foreach (double sx in new double[] { -W / 2, W / 2 })
        {
            Open(Plane("Right Plane", sx)); foreach (var yo in V.A("y")) { double y = Convert.ToDouble(yo); Slot(-V.N("z0"), y, -V.N("z1"), V.N("slot_w")); } sk = Close();
            Extrude(sk, t + 1, true, false, sx < 0 ? "Vents left" : "Vents right");
        }
        // 7. title on the front wall (bold, raised)
        var FP = p.O("front_text");
        Open(Plane("Front Plane", D)); bool txt = Text(0, FP.N("y"), FP.S("title"), FP.N("height")); sk = Close();
        if (txt) Extrude(sk, FP.N("raised_height"), false, false, "Title (raised)");
        Save(dir, Prefix + "_Body");
    }

    static void BuildBinFloor(P p, string dir)
    {
        var E = p.O("envelope"); var F = p.O("fasteners"); var FL = p.O("floor"); var C = p.O("print");
        double W = E.N("width"), D = E.N("depth"), t = E.N("wall"), tf = FL.N("thickness"), ci = F.N("corner_boss_inset");
        NewPart();
        Open("Top Plane"); RoundRect(-W / 2, -D, W / 2, 0, 1.0); var sk = Close();
        Grow(sk, tf, "Floor", 1, -tf, 0);
        // screws up into the body's inserts
        var cols = new[] { new[] { -W / 2 + ci, ci }, new[] { W / 2 - ci, ci }, new[] { -W / 2 + ci, D - ci }, new[] { W / 2 - ci, D - ci } };
        Open("Top Plane"); foreach (var c in cols) Circle(c[0], -c[1], F.N("screw_clear_d")); sk = Close();
        Extrude(sk, 0, true, true, "Screw holes");
        // cable-tie / M3 slots for the modules
        Open("Top Plane");
        foreach (var zo in FL.A("slot_rows_z")) { double z = Convert.ToDouble(zo);
            foreach (var xo in FL.A("slot_cols_x")) { double x = Convert.ToDouble(xo); Slot(x - FL.N("slot_len") / 2, -z, x + FL.N("slot_len") / 2, FL.N("slot_w")); } }
        sk = Close();
        Extrude(sk, 0, true, true, "Mounting slots");
        // where each module goes (engraved between slot rows; sketch y = -z, text reads from the front)
        Open("Top Plane"); bool any = false;
        foreach (var o in FL.A("zone_labels")) { var z = new P((Dictionary<string, object>)o); any |= Text(z.N("x"), -z.N("z") - 2.1, z.S("text"), 4.2); }
        sk = Close();
        if (any) Extrude(sk, 0.6, true, false, "Zone labels");
        // locating tabs 0.3 inside the walls (tab_h 0 = none: with tabs on top and feet below the plate could not lie
        // flat on the bed; the 4 screws locate it), and feet
        double tin = t + C.N("clearance"), tl = FL.N("tab_len"), tt = FL.N("tab_t");
        var bx0 = (double[])((PartDoc)doc).GetPartBox(true);
        if (FL.N("tab_h") > 0)
        {
            Open("Top Plane");
            RectXY(-tl / 2, -tin, tl / 2, -(tin + tt)); RectXY(-tl / 2, -(D - tin - tt), tl / 2, -(D - tin));
            RectXY(-W / 2 + tin, -(D / 2 - tl / 2), -W / 2 + tin + tt, -(D / 2 + tl / 2)); RectXY(W / 2 - tin - tt, -(D / 2 - tl / 2), W / 2 - tin, -(D / 2 + tl / 2));
            sk = Close();
            Grow(sk, FL.N("tab_h"), "Locating tabs", 1, bx0[1] / MM, FL.N("tab_h"));
            bx0 = (double[])((PartDoc)doc).GetPartBox(true);
        }
        Open(Plane("Top Plane", -tf)); foreach (var xo in FL.A("feet_x")) foreach (var zo in FL.A("feet_z")) Circle(Convert.ToDouble(xo), -Convert.ToDouble(zo), FL.N("feet_d")); sk = Close();
        Grow(sk, FL.N("feet_h"), "Feet", 1, -tf - FL.N("feet_h"), bx0[4] / MM);
        Save(dir, Prefix + "_Floor");
    }

    /// Ring that keeps the glass cup centred on the scale (taped to the top acrylic; it is weighed with the cup:
    /// tare includes it). ID = cup OD + 0.3.
    static void BuildBinCup(P p, string dir)
    {
        var S = p.O("scale"); var R = p.O("cup_ring");
        double y0 = S.N("top_y"), x = S.N("x"), z = S.N("z"), id = R.N("id"), w = R.N("wall"), bt = R.N("base_t");
        NewPart();
        Open(Plane("Top Plane", y0)); Circle(x, -z, id + 2 * w); var sk = Close();
        Grow(sk, bt, "Cup ring base", 1, y0, y0 + bt);
        Open(Plane("Top Plane", y0 + bt)); Circle(x, -z, id + 2 * w); Circle(x, -z, id); sk = Close();
        Grow(sk, R.N("h"), "Cup ring wall", 1, y0, y0 + bt + R.N("h"));
        Save(dir, Prefix + "_CupRing");
    }
}
