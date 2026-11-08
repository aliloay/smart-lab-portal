// Environment node enclosure (Robotics Lab, 2026-10-24) - the second part of Builder (door_enclosure/Build.cs has the
// helpers, the plate, the envelopes and the assembly). One box, everything visible (owner): the two PIRs on 45-degree
// front corners (zone 1 left, zone 2 right), smoke (MQ-2 can) top centre, temperature / humidity (DHT22) in its own
// pocket bottom left, the 5-channel flame board half out of a slot at the bottom edge (its receivers fan out in front).
// Same coordinates as the door box: x across, y up (0 = bottom), z out of the wall (0 = back, panel rear at z = depth).
using System;
using System.Collections.Generic;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

public partial class Builder
{
    /// The consumables-bin box lives in ..\bin_enclosure\BinParts.cs (compiled with this file when building it).
    static partial void BuildBinKind(P p, string outDir, string which);
    /// The reusable bin's control box: ../ctrl_enclosure/CtrlParts.cs.
    static partial void BuildCtrlKind(P p, string outDir, string which);
    /// The reusable bin's floor dock (tray + pedal cover + curved control box): ../dock_enclosure/DockParts.cs.
    static partial void BuildDockKind(P p, string outDir, string which);

    static partial void BuildKind(P p, string outDir, string which, string kind)
    {
        if (kind == "bin") { BuildBinKind(p, outDir, which); return; }
        if (kind == "ctrl") { BuildCtrlKind(p, outDir, which); return; }
        if (kind == "dock") { BuildDockKind(p, outDir, which); return; }
        if (kind != "env") { L("ERROR: unknown kind " + kind); return; }
        if (which == "all" || which == "body") BuildEnvBody(p, outDir);
        if (which == "all" || which == "panel") BuildEnvPanel(p, outDir);
        if (which == "all" || which == "plate") BuildPlate(p, outDir);
    }

    // ---- helpers for faces that are not on a base plane (the 45-degree corners) ----

    /// The planar face whose plane has normal +-n and passes through point q (mm).
    static Face2 FaceThrough(double[] n, double[] q)
    {
        var bodies = (object[])((PartDoc)doc).GetBodies2((int)swBodyType_e.swSolidBody, true);
        if (bodies == null) return null;
        Face2 best = null; double area = -1;
        foreach (Body2 b in bodies)
            foreach (Face2 f in (object[])b.GetFaces())
            {
                var s = (Surface)f.GetSurface();
                if (!s.IsPlane()) continue;
                var pp = (double[])s.PlaneParams;
                double dot = pp[0] * n[0] + pp[1] * n[1] + pp[2] * n[2];
                if (Math.Abs(Math.Abs(dot) - 1) > 1e-6) continue;
                double dist = pp[0] * (q[0] * MM - pp[3]) + pp[1] * (q[1] * MM - pp[4]) + pp[2] * (q[2] * MM - pp[5]);
                if (Math.Abs(dist) > 1e-6) continue;
                double a = f.GetArea(); if (a > area) { area = a; best = f; }
            }
        return best;
    }

    /// Opens a sketch on a face; ToSk turns model points (mm) into this sketch's coordinates.
    static Sketch OpenOnFace(Face2 f, string what)
    {
        if (f == null) throw new Exception("face for " + what + " not found");
        doc.ClearSelection2(true); ((Entity)f).Select4(false, null);
        doc.SketchManager.InsertSketch(true); doc.SketchManager.AddToDB = true;
        return doc.SketchManager.ActiveSketch;
    }
    static double[] ToSk(Sketch s, double[] q)
    {
        var mu = (MathUtility)sw.GetMathUtility();
        var pt = (MathPoint)mu.CreatePoint(new double[] { q[0] * MM, q[1] * MM, q[2] * MM });
        pt = (MathPoint)pt.MultiplyTransform((MathTransform)s.ModelToSketchTransform);
        var a = (double[])pt.ArrayData; return new[] { a[0] / MM, a[1] / MM };
    }
    static void CircleAt(Sketch s, double[] q, double d) { var c = ToSk(s, q); Circle(c[0], c[1], d); }
    static double[] Add(double[] a, double[] b, double k) { return new[] { a[0] + k * b[0], a[1] + k * b[1], a[2] + k * b[2] }; }

    /// Extrude that must end up where expected: the part's box along `axis` (0 x, 1 y, 2 z) must reach lo..hi.
    static Feature Grow(Feature sketch, double depthMm, string what, int axis, double lo, double hi)
    {
        for (int attempt = 0; attempt < 2; attempt++)
        {
            doc.ClearSelection2(true); sketch.Select2(false, 0);
            var f = doc.FeatureManager.FeatureExtrusion2(true, false, attempt == 1, (int)swEndConditions_e.swEndCondBlind, 0, depthMm * MM, 0,
                false, false, false, false, 0, 0, false, false, false, false, true, true, true, 0, 0, false);
            if (f == null) continue;
            var bx = (double[])((PartDoc)doc).GetPartBox(true);
            if (Math.Abs(bx[axis] / MM - lo) < 0.01 && Math.Abs(bx[axis + 3] / MM - hi) < 0.01) { f.Name = what; return f; }
            doc.ClearSelection2(true); f.Select2(false, 0); doc.EditDelete();
        }
        L("WARNING: " + what + " did not land at " + lo + ".." + hi);
        return null;
    }

    /// Two walls left / right of a board (inner width w, from y0 to y1) behind the panel, `len` long, with zip-tie
    /// slots through both, tieZ behind the panel (Right Plane: sketch x = -z, as the USB / vent cuts). Only that one
    /// copy: a mirrored "+z" copy cut straight through the panel when tieZ was small (2026-10-24 MQ-2 slits).
    static void RailsWithTies(double cx, double y0, double y1, double w, double wall, double len, double tieZ, double tieH, double tieW, string what)
    {
        Behind(len, () => { RectXY(cx - w / 2 - wall, y0, cx - w / 2, y1); RectXY(cx + w / 2, y0, cx + w / 2 + wall, y1); }, what + " rails");
        Open(Plane("Right Plane", cx - w / 2 - wall - 1));
        foreach (var dy in new[] { -0.25, 0.25 }) Rect(tieZ, (y0 + y1) / 2 + dy * (y1 - y0), tieH, tieW);
        var sk = Close();
        Extrude(sk, 0, true, true, what + " tie slots");
    }

    // ------------------------------------------------------------------ body ---
    static void BuildEnvBody(P p, string dir)
    {
        var E = p.O("envelope"); var F = p.O("fasteners"); var EP = p.O("electronics_plate"); var B = p.O("env_body");
        double W = E.N("width"), H = E.N("height"), D = E.N("depth"), t = E.N("wall"), c = B.N("chamfer");
        NewPart();
        // 1. block: top view with the two front corners cut at 45 degrees (Top Plane: sketch x = x, y = -z)
        Open("Top Plane");
        var pts = new double[,] { { -W / 2, 0 }, { W / 2, 0 }, { W / 2, D - c }, { W / 2 - c, D }, { -W / 2 + c, D }, { -W / 2, D - c } };
        for (int i = 0; i < 6; i++) { int j = (i + 1) % 6; doc.SketchManager.CreateLine(pts[i, 0] * MM, -pts[i, 1] * MM, 0, pts[j, 0] * MM, -pts[j, 1] * MM, 0); }
        var sk = Close();
        Grow(sk, H, "Block", 1, 0, H);
        doc.ClearSelection2(true);
        if (!SelectPlanarFace(D, true)) throw new Exception("Env body: no front face to open");
        double vb = Volume();
        doc.InsertFeatureShell(t * MM, false);
        if (Volume() >= vb - 1e-9) L("WARNING: shell failed");
        if (PlanarFaceArea(D) > 0.2 * (W - 2 * c) * H * MM * MM) throw new Exception("Env body: the shell left the front CLOSED");
        // 2. columns with heat-set inserts for the front panel (inside the flat front, clear of the corners)
        double cx = B.N("col_x"), ci = F.N("corner_boss_inset"), cd = F.N("corner_boss_d");
        double[,] cols = { { -cx, ci }, { cx, ci }, { -cx, H - ci }, { cx, H - ci } };
        Open("Front Plane"); for (int i = 0; i < 4; i++) Circle(cols[i, 0], cols[i, 1], cd); sk = Close();
        Extrude(sk, D, false, false, "Panel columns");
        Open(Plane("Front Plane", D)); for (int i = 0; i < 4; i++) Circle(cols[i, 0], cols[i, 1], F.N("insert_hole_d")); sk = Close();
        Extrude(sk, F.N("insert_hole_depth"), true, false, "Panel insert holes");
        // 3. bosses for the electronics plate (same as the door box)
        double pw = W - 2 * EP.N("x_margin"), py0 = EP.N("y_bottom"), py1 = H - EP.N("y_top_margin"), hi = EP.N("hole_inset");
        double[,] pb = { { -pw / 2 + hi, py0 + hi }, { pw / 2 - hi, py0 + hi }, { -pw / 2 + hi, py1 - hi }, { pw / 2 - hi, py1 - hi } };
        string pz = Plane("Front Plane", t);
        Open(pz); for (int i = 0; i < 4; i++) Circle(pb[i, 0], pb[i, 1], EP.N("boss_d")); sk = Close();
        Extrude(sk, EP.N("boss_h"), false, false, "Plate bosses");
        Open(Plane("Front Plane", t + EP.N("boss_h"))); for (int i = 0; i < 4; i++) Circle(pb[i, 0], pb[i, 1], F.N("insert_hole_d")); sk = Close();
        Extrude(sk, Math.Min(F.N("insert_hole_depth"), EP.N("boss_h") + t - 1), true, false, "Plate insert holes");
        // 4. side walls: ESP32 USB-C (its side) and the 12 V DC-in gland (left) (Right Plane offset: sketch x = -z, y = y)
        var U = p.O("usb_access"); var DC = p.O("dc_in");
        double ux = U.S("side") == "left" ? -W / 2 : W / 2;
        Open(Plane("Right Plane", ux)); Rect(-U.N("z"), U.N("y"), U.N("w"), U.N("h")); sk = Close();
        Extrude(sk, t + 1, true, false, "USB access");
        Open(Plane("Right Plane", -W / 2)); Circle(-DC.N("z"), DC.N("y"), DC.N("d")); sk = Close();
        Extrude(sk, t + 1, true, false, "DC in");
        // 5. air: intake slots in the bottom, outlet slots in the top (above the MQ-2 heater and the buck)
        var V = p.O("env_vents");
        Open("Top Plane"); foreach (var zo in V.A("bottom_z")) { double z = Convert.ToDouble(zo); Slot(V.N("bottom_x0"), -z, V.N("bottom_x1"), V.N("slot_w")); } sk = Close();
        Extrude(sk, t + 1, true, false, "Intake slots");
        foreach (double sx in new double[] { -W / 2, W / 2 })
        {
            Open(Plane("Right Plane", sx)); foreach (var yo in V.A("side_y")) { double y = Convert.ToDouble(yo); Slot(-V.N("side_z0"), y, -V.N("side_z1"), V.N("slot_w")); } sk = Close();
            Extrude(sk, t + 1, true, false, sx < 0 ? "Outlet slots left" : "Outlet slots right");
        }
        // 5b. flame board ON the top (owner's photos: trimmer in the centre, header at the back): pocket = board + 0.3,
        //     receivers fan out over the front edge, tie slots left / right, wire slot behind it (Top Plane: y = -z)
        var FL = p.O("flame"); double fx = FL.N("x"), fz = FL.N("z");
        string top = Plane("Top Plane", H);
        Open(top); Circle(fx, -fz, FL.N("pocket_d")); sk = Close();
        Extrude(sk, FL.N("pocket_depth"), true, false, "Flame pocket");
        Open(top);
        foreach (var k in new[] { -1, 1 }) Rect(fx + k * FL.N("tie_dx"), -(fz + FL.N("tie_dz")), FL.N("tie_w"), FL.N("tie_h"));
        Rect(fx, -FL.N("wire_z"), FL.N("wire_w"), FL.N("wire_h"));
        sk = Close();
        Extrude(sk, t + 1, true, false, "Flame tie + wire slots");
        Open(top); bool ftxt = Text(fx, -(FL.N("label_z") + FL.N("label_h") / 2), "FLAME", FL.N("label_h")); sk = Close();
        if (ftxt) Extrude(sk, 0.8, false, false, "FLAME label (raised)");
        // 6. feet (stands on a desk for the demo, air still gets under it)
        var FT = p.O("feet");
        Open("Top Plane"); foreach (var xo in FT.A("x")) foreach (var zo in FT.A("z")) Circle(Convert.ToDouble(xo), -Convert.ToDouble(zo), FT.N("d")); sk = Close();
        var bx0 = (double[])((PartDoc)doc).GetPartBox(true);              // the top already carries the raised label
        Grow(sk, FT.N("h"), "Feet", 1, -FT.N("h"), bx0[4] / MM);
        // 7. wall ears left / right, flush with the back (screw + 0.3); left / right so the bottom stays flat
        var WE = p.O("wall_ears"); double ew = WE.N("w"), er = WE.N("reach");
        Open("Front Plane");
        foreach (var yo in WE.A("y")) { double y = Convert.ToDouble(yo); RectXY(-W / 2 - er, y - ew / 2, -W / 2, y + ew / 2); RectXY(W / 2, y - ew / 2, W / 2 + er, y + ew / 2); }
        sk = Close();
        Extrude(sk, WE.N("t"), false, false, "Wall ears");
        Open("Front Plane");
        foreach (var yo in WE.A("y")) { double y = Convert.ToDouble(yo); Circle(-W / 2 - WE.N("hole_from_edge"), y, WE.N("hole_d")); Circle(W / 2 + WE.N("hole_from_edge"), y, WE.N("hole_d")); }
        sk = Close();
        Extrude(sk, WE.N("t"), true, true, "Wall ear screw holes");
        // 8. the two PIRs on the 45-degree corners: dome hole through the wall, two M2 bosses inside (HC-SR501 holes
        //    28 apart along the board), pilots blind so nothing shows outside
        var PI = p.O("pir"); double py = PI.N("y"), s2 = Math.Sqrt(0.5);
        foreach (int side in new[] { -1, 1 })
        {
            double[] n = { side * s2, 0, s2 };                                  // outward normal of this corner
            double[] u = { -side * s2, 0, s2 };                                 // along the corner face, horizontal
            double[] m = { side * (W / 2 - c / 2), py, D - c / 2 };            // middle of the corner face (outside)
            string nm = side < 0 ? "PIR 1 (left)" : "PIR 2 (right)";
            var s = OpenOnFace(FaceThrough(n, m), nm + " dome");
            CircleAt(s, m, PI.N("dome_hole_d")); sk = Close();
            Extrude(sk, t + 1, true, false, nm + " dome hole");
            double[] mi = Add(m, n, -t);                                        // same point on the inside face
            s = OpenOnFace(FaceThrough(n, mi), nm + " bosses");
            foreach (var k in new[] { -1, 1 }) CircleAt(s, Add(mi, u, k * PI.N("hole_dx") / 2), PI.N("boss_d"));
            sk = Close();
            Extrude(sk, PI.N("boss_h"), false, false, nm + " bosses");
            double[] mt = Add(mi, n, -PI.N("boss_h"));                           // boss tips
            s = OpenOnFace(FaceThrough(n, Add(mt, u, PI.N("hole_dx") / 2)), nm + " pilots");
            foreach (var k in new[] { -1, 1 }) CircleAt(s, Add(mt, u, k * PI.N("hole_dx") / 2), F.N("pilot_m2_d"));
            sk = Close();
            Extrude(sk, PI.N("boss_h") + t - 1, true, false, nm + " M2 pilots");
        }
        Save(dir, Prefix + "_Body");
    }

    // ----------------------------------------------------------------- panel ---
    static void BuildEnvPanel(P p, string dir)
    {
        var E = p.O("envelope"); var F = p.O("fasteners"); var FP = p.O("front_panel"); var C = p.O("print"); var B = p.O("env_body");
        var M = p.O("mq"); var DH = p.O("dht");
        double W = E.N("width"), H = E.N("height"), t = FP.N("thickness"), wall = E.N("wall"), clr = C.N("clearance"), c = B.N("chamfer");
        double Wf = W - 2 * c, th = FP.N("text_height");
        NewPart();
        Open("Front Plane"); RoundRect(-Wf / 2, 0, Wf / 2, H, FP.N("corner_r")); var sk = Close();
        Extrude(sk, t, false, false, "Panel");
        string front = Plane("Front Plane", t);
        double cx = B.N("col_x"), ci = F.N("corner_boss_inset");
        Open("Front Plane"); foreach (var q in new[] { new[] { -cx, ci }, new[] { cx, ci }, new[] { -cx, H - ci }, new[] { cx, H - ci } }) Circle(q[0], q[1], F.N("screw_clear_d")); sk = Close();
        Extrude(sk, t, true, true, "Screw holes");
        // locating tabs 0.3 inside the walls; left / right ones inside the corner walls where they meet the front
        double tl = FP.N("locating_tab_len"), tt = FP.N("locating_tab_t"), tin = wall + clr;
        double xin = W / 2 - c - wall * Math.Sqrt(2) - clr;                     // inner corner wall at the panel, - 0.3
        Behind(FP.N("locating_tab_h"), () => {
            RectXY(-tl / 2, tin, tl / 2, tin + tt); RectXY(-tl / 2, H - tin - tt, tl / 2, H - tin);
            RectXY(-xin, H / 2 - tl / 2, -xin + tt, H / 2 + tl / 2); RectXY(xin - tt, H / 2 - tl / 2, xin, H / 2 + tl / 2); }, "Locating tabs");
        // smoke: MQ-2 can through the panel (can + 0.3), the board between two rails, can at its top end
        double mx = M.N("x"), my = M.N("y"), mr = M.N("can_hole_d") / 2;
        Open("Front Plane"); Circle(mx, my, M.N("can_hole_d")); sk = Close();
        Extrude(sk, t, true, true, "MQ-2 can hole");
        double my1 = my + M.N("can_from_top"), my0 = my1 - M.N("board_h");
        RailsWithTies(mx, my0, my1, M.N("board_w"), M.N("rail_wall"), M.N("rail_len"), M.N("tie_z"), M.N("tie_h"), M.N("tie_w"), "MQ-2");
        // temperature / humidity: DHT22 module in its own pocket (shielded from the inside heat), grille behind a
        // window 1 mm smaller all round (lips keep it in), pins at the bottom end (open); a tie closes the back
        double dx = DH.N("x"), dy = DH.N("y"), dw = DH.N("pocket_w"), dh = DH.N("pocket_h"), lip = DH.N("lip");
        Open("Front Plane"); Rect(dx, dy, dw - 2 * lip, dh - 2 * lip); sk = Close();
        Extrude(sk, t, true, true, "DHT22 window");
        RailsWithTies(dx, dy - dh / 2, dy + dh / 2, dw, DH.N("wall"), DH.N("depth"), DH.N("tie_z"), DH.N("tie_h"), DH.N("tie_w"), "DHT22");
        Behind(DH.N("depth"), () => RectXY(dx - dw / 2 - DH.N("wall"), dy + dh / 2, dx + dw / 2 + DH.N("wall"), dy + dh / 2 + DH.N("wall")), "DHT22 pocket top");
        // labels: bold, raised (owner's choice)
        Open(front);
        bool txt = Text(0, FP.N("title_y"), FP.S("title"), FP.N("title_height"));
        Text(mx, my - mr - 3.5 - th, "SMOKE", th);
        Text(dx, dy + dh / 2 + DH.N("wall") + 3, "TEMP", th);
        sk = Close();
        if (!txt) L("WARNING: sketch text not available - labels skipped");
        else Extrude(sk, FP.N("raised_height"), false, false, "Labels (raised)");
        Save(dir, Prefix + "_FrontPanel");
    }
}
