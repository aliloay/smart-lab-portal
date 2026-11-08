// Reusable (smart) bin DOCK, 2026-10-25 - a fifth part of Builder (helpers in door_enclosure/Build.cs and
// env_enclosure/EnvParts.cs). The bin stands in a tray traced from its own base; a screwed-on cover hides the pedal
// (only the NFC card + servo open the lid); the control box stands on the bin's left with a face curved to the bin,
// cable glands in its END walls, the electronics on a plate that slides into grooves and lifts out from the top.
// The 2D profiles come from gen_params.py (params "geometry", lists of [X, Z] mm).
// Frames: tray/assembly X along the bin (+X = pedal), Z toward the bin's left, Y up (0 = floor); sketches on the
// Top Plane family use (X, -Z). Box parts: xb along the bin, zb out of the bin's side (0 = face toward the bin),
// yb up from the box bottom; same axes, the assembly only moves them.
using System;
using System.Collections.Generic;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

public partial class Builder
{
    static partial void BuildDockKind(P p, string outDir, string which)
    {
        if (which == "all" || which == "tray") BuildDockTray(p, outDir);
        if (which == "all" || which == "cover") BuildDockCover(p, outDir);
        if (which == "all" || which == "body") BuildDockBody(p, outDir);
        if (which == "all" || which == "lid") BuildDockLid(p, outDir);
        if (which == "all" || which == "plate") BuildDockPlate(p, outDir);
        if (which == "all" || which == "bin") BuildBinReference(p, outDir);
    }

    /// Closed polylines from [[X, Z], ...] lists, drawn in a Top-Plane-family sketch as (X, -Z).
    static void Loops(List<object> loops)
    {
        foreach (var lo in loops)
        {
            var l = (List<object>)lo; int n = l.Count;
            for (int i = 0; i < n; i++)
            {
                var a = (List<object>)l[i]; var b = (List<object>)l[(i + 1) % n];
                doc.SketchManager.CreateLine(Convert.ToDouble(a[0]) * MM, -Convert.ToDouble(a[1]) * MM, 0,
                    Convert.ToDouble(b[0]) * MM, -Convert.ToDouble(b[1]) * MM, 0);
            }
        }
    }
    static double[] XZ(object o) { var a = (List<object>)o; return new[] { Convert.ToDouble(a[0]), Convert.ToDouble(a[1]) }; }

    /// Boss extrude that must go UP from its sketch plane: the part must not reach below minY afterwards.
    static Feature ExtrudeUp(Feature sketch, double depthMm, string what, double minY)
    {
        double v0 = Volume();
        for (int attempt = 0; attempt < 2; attempt++)
        {
            doc.ClearSelection2(true); sketch.Select2(false, 0);
            var f = doc.FeatureManager.FeatureExtrusion2(true, false, attempt == 1, (int)swEndConditions_e.swEndCondBlind, 0, depthMm * MM, 0,
                false, false, false, false, 0, 0, false, false, false, false, true, true, true, 0, 0, false);
            if (f == null) continue;
            var bx = (double[])((PartDoc)doc).GetPartBox(true);
            if (bx[1] / MM > minY - 0.01 && Volume() > v0 + 1e-12) { f.Name = what; L("  ok " + what); return f; }
            doc.ClearSelection2(true); f.Select2(false, 0); doc.EditDelete();
        }
        throw new Exception(what + ": extrude did not go up from its plane");
    }

    // ------------------------------------------------------------------ tray ---
    static void BuildDockTray(P p, string dir)
    {
        var G = p.O("geometry"); double ft = G.N("floor_t"), rimTop = G.N("rim_top"), cy = G.N("cover_y");
        var F = p.O("fasteners");
        NewPart();
        Open("Top Plane"); Loops(G.A("floor")); var sk = Close();
        Grow(sk, ft, "Floor (ring + tongues)", 1, 0, ft);
        Open(Plane("Top Plane", ft)); Loops(G.A("rim")); sk = Close();
        ExtrudeUp(sk, rimTop - ft, "Rim", 0);
        // pedal hood walls up to the cover, with the two screw columns
        Open(Plane("Top Plane", ft)); Loops(G.A("hood_walls")); sk = Close();
        ExtrudeUp(sk, cy - ft, "Pedal hood walls", 0);
        Open(Plane("Top Plane", cy)); foreach (var e in G.A("ears")) { var q = XZ(e); Circle(q[0], -q[1], F.N("insert_hole_d")); } sk = Close();
        Extrude(sk, F.N("insert_hole_depth"), true, false, "Cover insert holes");
        // pegs on the tongues: they key the control box (its holes are peg + 0.3)
        Open(Plane("Top Plane", ft)); foreach (var e in G.A("pegs")) { var q = XZ(e); Circle(q[0], -q[1], G.N("peg_d")); } sk = Close();
        Extrude(sk, G.N("peg_h"), false, false, "Box pegs");
        Save(dir, Prefix + "_Tray");
    }

    static void BuildDockCover(P p, string dir)
    {
        var G = p.O("geometry"); var F = p.O("fasteners"); double cy = G.N("cover_y"), ct = G.N("cover_t");
        NewPart();
        Open(Plane("Top Plane", cy)); Loops(G.A("cover")); var sk = Close();
        ExtrudeUp(sk, ct, "Pedal cover", cy);
        Open(Plane("Top Plane", cy)); foreach (var e in G.A("ears")) { var q = XZ(e); Circle(q[0], -q[1], F.N("screw_clear_d")); } sk = Close();
        Extrude(sk, ct, true, true, "Cover screw holes");
        Save(dir, Prefix + "_PedalCover");
    }

    /// The bin itself (body + rod-channel foot full height, the pedal pad under the cover): only for the
    /// interference check, never printed.
    static void BuildBinReference(P p, string dir)
    {
        var G = p.O("geometry"); double ft = G.N("floor_t"), bh = G.N("bin_h"), pt = G.N("pedal_top");
        NewPart();
        Open(Plane("Top Plane", ft)); Loops(G.A("bin_body")); var sk = Close();
        ExtrudeUp(sk, bh, "Bin body", ft);
        Open(Plane("Top Plane", ft)); Loops(G.A("bin_notch")); sk = Close();
        ExtrudeUp(sk, bh, "Rod channel", ft);
        Open(Plane("Top Plane", pt - 10)); Loops(G.A("bin_pedal")); sk = Close();
        ExtrudeUp(sk, 10, "Pedal pad (top " + pt + ")", ft);
        Save(dir, Prefix + "_BinReference");
    }

    // ------------------------------------------------------------------- box ---
    static double[][] DockColumns(P p)
    {
        var E = p.O("envelope"); double W = E.N("width"), D = E.N("depth"), ci = p.O("fasteners").N("corner_boss_inset");
        return new[] { new[] { -W / 2 + ci, ci }, new[] { W / 2 - ci, ci }, new[] { -W / 2 + ci, D - ci }, new[] { W / 2 - ci, D - ci } };
    }

    static void BuildDockBody(P p, string dir)
    {
        var E = p.O("envelope"); var F = p.O("fasteners"); var G = p.O("geometry"); var RL = p.O("rails"); var EH = p.O("end_holes");
        double W = E.N("width"), H = E.N("height"), D = E.N("depth"), t = E.N("wall"), r = E.N("corner_radius"), clr = p.O("print").N("clearance");
        NewPart();
        // 1. block, shelled open at the top (the lid closes it)
        Open("Top Plane"); RoundRect(-W / 2, -D, W / 2, 0, r); var sk = Close();
        Grow(sk, H, "Block", 1, 0, H);
        var top = FaceThrough(new double[] { 0, 1, 0 }, new double[] { 0, H, D / 2 });
        if (top == null) throw new Exception("Dock body: no top face");
        doc.ClearSelection2(true); ((Entity)top).Select4(false, null);
        double vb = Volume(); doc.InsertFeatureShell(t * MM, false);
        if (Volume() >= vb - 1e-9) throw new Exception("Dock body: shell failed");
        if (FaceThrough(new double[] { 0, 1, 0 }, new double[] { 0, H, D / 2 }) != null && Volume() > 0.8 * vb) throw new Exception("Dock body: top still closed");
        // 2. corner columns for the lid screws (heat-set inserts at the top)
        var cols = DockColumns(p);
        Open(Plane("Top Plane", t)); foreach (var c in cols) Circle(c[0], -c[1], F.N("corner_boss_d")); sk = Close();
        ExtrudeUp(sk, H - t, "Lid columns", 0);
        Open(Plane("Top Plane", H)); foreach (var c in cols) Circle(c[0], -c[1], F.N("insert_hole_d")); sk = Close();
        Extrude(sk, F.N("insert_hole_depth"), true, false, "Lid insert holes");
        // 3. plate grooves: two ribs on each end wall, gap = plate + 0.3
        double pz0 = RL.N("plate_z0"), pt = RL.N("plate_t"), rt = RL.N("rib_t"), rr = RL.N("rib_reach");
        double g0 = pz0 - clr / 2, g1 = pz0 + pt + clr / 2, xi = W / 2 - t;
        Open(Plane("Top Plane", t));
        foreach (var s in new[] { -1.0, 1.0 })
        {
            RectXY(s * xi, -(g0 - rt), s * (xi - rr), -g0);
            RectXY(s * xi, -g1, s * (xi - rr), -(g1 + rt));
        }
        sk = Close();
        ExtrudeUp(sk, H - t, "Plate groove ribs", 0);
        // 4. the curved face toward the bin (starts above the tray rim)
        double sy = G.N("saddle_from_y");
        Open(Plane("Top Plane", sy)); Loops(new List<object> { G.A("saddle") }); sk = Close();
        ExtrudeUp(sk, H - sy, "Curved face to the bin", 0);
        // 45-degree underside so the box prints upright without supports (sketch x = -z, y = y)
        double sd = 0; foreach (var o in G.A("saddle")) sd = Math.Max(sd, -XZ(o)[1]);
        Open(Plane("Right Plane", -W / 2 - 1));
        var m = doc.SketchManager;
        m.CreateLine(0, sy * MM, 0, (sd + 1) * MM, sy * MM, 0);
        m.CreateLine((sd + 1) * MM, sy * MM, 0, (sd + 1) * MM, (sy + sd + 1) * MM, 0);
        m.CreateLine((sd + 1) * MM, (sy + sd + 1) * MM, 0, 0, sy * MM, 0);
        sk = Close();
        Extrude(sk, W + 2, true, false, "Curved face 45-degree underside");
        // 5. end walls: cable glands and the ESP32 USB (Right Plane offset: sketch x = -z, y = y)
        double gz = EH.N("z");
        foreach (var s in new[] { -1, 1 })
        {
            Open(Plane("Right Plane", s * W / 2)); bool any = false;
            foreach (var o in EH.A("holes")) { var h = new P((Dictionary<string, object>)o); if ((int)h.N("side") != s) continue; Circle(-gz, h.N("y"), h.N("d")); any = true; }
            var U = EH.O("usb"); if ((int)U.N("side") == s) { Rect(-U.N("z"), U.N("y"), U.N("w"), U.N("h")); any = true; }
            sk = Close();
            if (any) Extrude(sk, t + 0.5, true, false, s < 0 ? "Back-end holes (12 V, bin A)" : "Front-end holes (bin B, USB)");
        }
        // 6. vents and the raised title / labels on the outer wall (z = D)
        var V = p.O("vents"); string outer = Plane("Front Plane", D);
        Open(outer); foreach (var yo in V.A("y_list")) Slot(V.N("x_from"), Convert.ToDouble(yo), V.N("x_to"), V.N("slot_h")); sk = Close();
        Extrude(sk, t + 1, true, false, "Vents");
        var OT = p.O("outer_text");
        Open(outer);
        bool txt = Text(0, OT.N("title_y") - OT.N("title_height") / 2, OT.S("title"), OT.N("title_height"));
        foreach (var o in OT.A("labels")) { var q = new P((Dictionary<string, object>)o); Text(q.N("x"), q.N("y") - q.N("h") / 2, q.S("text"), q.N("h")); }
        sk = Close();
        if (txt) Extrude(sk, OT.N("raised_height"), false, false, "Outer text (raised)");
        // 7. bottom stays FLAT (prints on it, stands on the floor). The tray's tongues slide into pockets under the back
        //    edge (tongue + 0.3 all round, open toward the bin) and their pegs into blind holes (peg + 0.3) above; a pad
        //    inside keeps the bottom closed over each pocket.
        double tw = G.N("tongue_w") + 2 * clr, tz = G.N("tongue_zb") + clr, th = G.N("tongue_t") + clr;
        double pegTop = th + G.N("peg_h") + clr, padTop = pegTop + 1.6;
        Open(Plane("Top Plane", t));
        foreach (var xo in G.A("pegs_xb")) { double x = Convert.ToDouble(xo); RectXY(x - tw / 2 - 3, -t, x + tw / 2 + 3, -(tz + 3)); }
        sk = Close();
        ExtrudeUp(sk, padTop - t, "Tongue pads", 0);
        Open("Top Plane"); foreach (var xo in G.A("pegs_xb")) { double x = Convert.ToDouble(xo); RectXY(x - tw / 2, 1, x + tw / 2, -tz); } sk = Close();
        Extrude(sk, th, true, false, "Tongue pockets");
        Open("Top Plane"); foreach (var xo in G.A("pegs_xb")) Circle(Convert.ToDouble(xo), -G.N("peg_zb"), G.N("peg_d") + clr); sk = Close();
        Extrude(sk, pegTop, true, false, "Peg holes (blind)");
        Save(dir, Prefix + "_Body");
    }

    static void BuildDockLid(P p, string dir)
    {
        var E = p.O("envelope"); var F = p.O("fasteners"); var LD = p.O("lid");
        double W = E.N("width"), H = E.N("height"), D = E.N("depth"), t = E.N("wall"), r = E.N("corner_radius"), lt = LD.N("thickness"), clr = p.O("print").N("clearance");
        NewPart();
        string bot = Plane("Top Plane", H);
        Open(bot); RoundRect(-W / 2, -D, W / 2, 0, r); var sk = Close();
        ExtrudeUp(sk, lt, "Lid", H);
        Open(bot); foreach (var c in DockColumns(p)) Circle(c[0], -c[1], F.N("screw_clear_d")); sk = Close();
        Extrude(sk, lt, true, true, "Screw holes");
        // locating tabs 0.3 inside the walls (they clear the columns, the grooves and the gland nuts). Height 0 = none:
        // the lid then prints flat, text up, and the 4 screws locate it (3.3 holes on M3).
        double tl = LD.N("locating_tab_len"), tt = LD.N("locating_tab_t"), tin = t + clr;
        if (LD.N("locating_tab_h") > 0) {
        Open(bot);
        RectXY(-tl / 2, -tin, tl / 2, -(tin + tt)); RectXY(-tl / 2, -(D - tin - tt), tl / 2, -(D - tin));
        RectXY(-W / 2 + tin, -(D / 2 - tl / 2), -W / 2 + tin + tt, -(D / 2 + tl / 2)); RectXY(W / 2 - tin - tt, -(D / 2 - tl / 2), W / 2 - tin, -(D / 2 + tl / 2));
        sk = Close();
        Grow(sk, LD.N("locating_tab_h"), "Locating tabs", 1, H - LD.N("locating_tab_h"), H + lt);
        }
        // title on top, reading from the box's outer side (text up = toward the bin)
        Open(Plane("Top Plane", H + lt)); bool txt = Text(0, -D / 2 - LD.N("title_height") / 2, LD.S("title"), LD.N("title_height")); sk = Close();
        if (txt) Extrude(sk, LD.N("raised_height"), false, false, "Title (raised)");
        Save(dir, Prefix + "_Lid");
    }

    static void BuildDockPlate(P p, string dir)
    {
        var E = p.O("envelope"); var EP = p.O("electronics_plate"); var RL = p.O("rails");
        double W = E.N("width"), t = E.N("wall"), clr = p.O("print").N("clearance");
        double hw = W / 2 - t - clr, y0 = EP.N("y_bottom"), y1 = EP.N("y_top"), z0 = RL.N("plate_z0"), pt = RL.N("plate_t");
        NewPart();
        string back = Plane("Front Plane", z0);
        Open(back); RoundRect(-hw, y0, hw, y1, 2); var sk = Close();
        Grow(sk, pt, "Plate", 2, z0, z0 + pt);
        // finger notch at the top to lift it out, zip-tie / M3 slots for the modules
        Open(back);
        Rect(0, y1 - EP.N("lift_notch_h") / 2, EP.N("lift_notch_w"), EP.N("lift_notch_h"));
        double sl = EP.N("slot_len"), sxp = EP.N("slot_pitch_x"), syp = EP.N("slot_pitch_y");
        int nx = (int)Math.Floor((2 * hw - 24 - sl) / sxp) + 1; double x0 = -(nx - 1) * sxp / 2;
        for (double y = y0 + 12; y <= y1 - EP.N("lift_notch_h") - 8 + 1e-6; y += syp)
            for (int i = 0; i < nx; i++) Slot(x0 + i * sxp - sl / 2, y, x0 + i * sxp + sl / 2, EP.N("slot_w"));
        sk = Close();
        Extrude(sk, pt, true, true, "Notch and mounting slots");
        Open(Plane("Front Plane", z0 + pt)); bool any = false;
        foreach (var o in EP.A("zone_labels")) { var z = new P((Dictionary<string, object>)o); any |= Text(z.N("x"), z.N("y") - 2.1, z.S("text"), 4.2); }
        sk = Close();
        if (any) Extrude(sk, 0.6, true, false, "Zone labels");
        Save(dir, Prefix + "_ElectronicsPlate");
    }
}
