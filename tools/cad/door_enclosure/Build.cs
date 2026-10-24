// MASTER_LAB01 door controller enclosure - SOLIDWORKS part generator (2026-10-20).
// Every dimension comes from params.json (mm); build.ps1 compiles this file against the SOLIDWORKS
// interop assemblies and calls Builder.Run. Output: one .SLDPRT + .STL per part, an assembly and
// preview images in out/. Coordinates (all parts): x across (centred), y up (0 = bottom),
// z out of the wall (0 = back face of the box; the front panel's rear face sits at z = depth).
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

public class P   // tiny JSON reader for params.json (numbers, bools, strings, arrays, objects)
{
    public Dictionary<string, object> D;
    public P(Dictionary<string, object> d) { D = d; }
    public P O(string k) { return new P((Dictionary<string, object>)D[k]); }
    public double N(string k) { return Convert.ToDouble(D[k]); }
    public bool B(string k) { return (bool)D[k]; }
    public string S(string k) { return (string)D[k]; }
    public List<object> A(string k) { return (List<object>)D[k]; }

    public static object Parse(string s) { int i = 0; return Val(s, ref i); }
    static void Ws(string s, ref int i) { while (i < s.Length && char.IsWhiteSpace(s[i])) i++; }
    static object Val(string s, ref int i)
    {
        Ws(s, ref i);
        char c = s[i];
        if (c == '{') {
            var d = new Dictionary<string, object>(); i++;
            for (;;) { Ws(s, ref i); if (s[i] == '}') { i++; return d; }
                string k = (string)Val(s, ref i); Ws(s, ref i); i++; d[k] = Val(s, ref i); Ws(s, ref i); if (s[i] == ',') i++; }
        }
        if (c == '[') {
            var a = new List<object>(); i++;
            for (;;) { Ws(s, ref i); if (s[i] == ']') { i++; return a; } a.Add(Val(s, ref i)); Ws(s, ref i); if (s[i] == ',') i++; }
        }
        if (c == '"') {
            var b = new StringBuilder(); i++;
            while (s[i] != '"') { if (s[i] == '\\') { i++; b.Append(s[i] == 'n' ? '\n' : s[i]); } else b.Append(s[i]); i++; }
            i++; return b.ToString();
        }
        if (s.Substring(i).StartsWith("true")) { i += 4; return true; }
        if (s.Substring(i).StartsWith("false")) { i += 5; return false; }
        if (s.Substring(i).StartsWith("null")) { i += 4; return null; }
        int j = i; while (j < s.Length && "+-0123456789.eE".IndexOf(s[j]) >= 0) j++;
        double v = double.Parse(s.Substring(i, j - i), System.Globalization.CultureInfo.InvariantCulture); i = j; return v;
    }
}

public class Builder
{
    static SldWorks sw;
    static ModelDoc2 doc;
    static StringBuilder log = new StringBuilder();
    static int planeN = 0;
    const double MM = 0.001;

    static string progressFile;
    static void L(string m)
    {
        log.AppendLine(m);
        if (progressFile != null) File.AppendAllText(progressFile, DateTime.Now.ToString("HH:mm:ss ") + m + System.Environment.NewLine);
    }

    // ---------------------------------------------------------------- helpers ---
    static ModelDoc2 NewPart()
    {
        string tpl = sw.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplatePart);
        doc = (ModelDoc2)sw.NewDocument(tpl, 0, 0, 0);
        // mm units in the part (display only - the API always takes metres)
        doc.Extension.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitSystem, 0, (int)swUnitSystem_e.swUnitSystem_MMGS);
        planeN = 0;
        return doc;
    }

    static void Sel(string name, string type) { doc.ClearSelection2(true); doc.Extension.SelectByID2(name, type, 0, 0, 0, false, 0, null, 0); }

    /// A plane parallel to "Front Plane" (z), "Top Plane" (y) or "Right Plane" (x) at `mm` from it.
    static string Plane(string basePlane, double mm)
    {
        if (Math.Abs(mm) < 1e-9) return basePlane;
        Sel(basePlane, "PLANE");
        var f = (Feature)doc.FeatureManager.InsertRefPlane((int)swRefPlaneReferenceConstraints_e.swRefPlaneReferenceConstraint_Distance
            | (mm < 0 ? (int)swRefPlaneReferenceConstraints_e.swRefPlaneReferenceConstraint_OptionFlip : 0), Math.Abs(mm) * MM, 0, 0, 0, 0);
        if (f == null) throw new Exception("plane " + basePlane + " " + mm + " failed");
        if (progressFile != null) File.AppendAllText(progressFile, DateTime.Now.ToString("HH:mm:ss ") + "  plane " + basePlane + " " + mm + System.Environment.NewLine);
        f.Name = "P" + (++planeN) + "_" + basePlane.Split(' ')[0] + "_" + mm.ToString("0.##");
        doc.ClearSelection2(true); f.Select2(false, 0); doc.BlankRefGeom();   // hide the helper plane
        return f.Name;
    }

    static void Open(string plane) { Sel(plane, "PLANE"); doc.SketchManager.InsertSketch(true); doc.SketchManager.AddToDB = true; }
    static Feature Close() { doc.SketchManager.AddToDB = false; doc.SketchManager.InsertSketch(true); return (Feature)doc.FeatureByPositionReverse(0); }

    // sketch primitives (sketch coordinates, mm)
    static void Rect(double cx, double cy, double w, double h)
    { doc.SketchManager.CreateCenterRectangle(cx * MM, cy * MM, 0, (cx + w / 2) * MM, (cy + h / 2) * MM, 0); }
    static void RectXY(double x1, double y1, double x2, double y2)
    { doc.SketchManager.CreateCornerRectangle(x1 * MM, y1 * MM, 0, x2 * MM, y2 * MM, 0); }
    static void Circle(double cx, double cy, double d) { doc.SketchManager.CreateCircleByRadius(cx * MM, cy * MM, 0, d / 2 * MM); }
    static void RoundRect(double x1, double y1, double x2, double y2, double r)
    {
        var m = doc.SketchManager;
        m.CreateLine((x1 + r) * MM, y1 * MM, 0, (x2 - r) * MM, y1 * MM, 0);
        m.CreateLine(x2 * MM, (y1 + r) * MM, 0, x2 * MM, (y2 - r) * MM, 0);
        m.CreateLine((x2 - r) * MM, y2 * MM, 0, (x1 + r) * MM, y2 * MM, 0);
        m.CreateLine(x1 * MM, (y2 - r) * MM, 0, x1 * MM, (y1 + r) * MM, 0);
        m.CreateArc((x1 + r) * MM, (y1 + r) * MM, 0, x1 * MM, (y1 + r) * MM, 0, (x1 + r) * MM, y1 * MM, 0, 1);
        m.CreateArc((x2 - r) * MM, (y1 + r) * MM, 0, (x2 - r) * MM, y1 * MM, 0, x2 * MM, (y1 + r) * MM, 0, 1);
        m.CreateArc((x2 - r) * MM, (y2 - r) * MM, 0, x2 * MM, (y2 - r) * MM, 0, (x2 - r) * MM, y2 * MM, 0, 1);
        m.CreateArc((x1 + r) * MM, (y2 - r) * MM, 0, (x1 + r) * MM, y2 * MM, 0, x1 * MM, (y2 - r) * MM, 0, 1);
    }
    static void Slot(double x1, double y, double x2, double w)
    {
        doc.SketchManager.CreateSketchSlot((int)swSketchSlotCreationType_e.swSketchSlotCreationType_line,
            (int)swSketchSlotLengthType_e.swSketchSlotLengthType_CenterCenter, w * MM, x1 * MM, y * MM, 0, x2 * MM, y * MM, 0, 0, 0, 0, 1, false);
    }
    static bool Text(double x, double y, string t, double h)
    {
        // left-aligned insert, then centred below (2026-10-20: the uncentred title ran off the panel edge)
        var st = (SketchText)doc.InsertSketchText(x * MM, y * MM, 0, t, 1, 0, 0, 100, 100);
        if (st == null) return false;
        var tf = (TextFormat)st.GetTextFormat();
        tf.CharHeight = h * MM; tf.Bold = true;
        st.SetTextFormat(false, tf);
        // SketchText has no justification: measure the glyph edges and move the text so it is centred on x
        double lo = 1e9, hi = -1e9;
        var edges = st.GetEdges2() as object[];
        if (edges != null)
            foreach (var o in edges)
            {
                var ed = o as Edge; if (ed == null) continue;
                var cv = (Curve)ed.GetCurve(); var cp = ed.GetCurveParams3();
                for (int i = 0; i <= 8; i++) { var v = (double[])cv.Evaluate2(cp.UMinValue + (cp.UMaxValue - cp.UMinValue) * i / 8, 0); lo = Math.Min(lo, v[0]); hi = Math.Max(hi, v[0]); }
            }
        if (hi > lo)
        {
            var c0 = (double[])st.GetCoordinates();
            st.SetCoordinates(c0[0] + (x * MM - (lo + hi) / 2), c0[1], 0);
            L(string.Format("  text '{0}' {1:0.0} mm high, {2:0.0} mm wide, centred on x = {3:0.0}", t, h, (hi - lo) / MM, x));
        }
        else L("  text '" + t + "': width not measured (left-aligned at x)");
        return true;
    }

    static double Volume()
    {
        var mp = (MassProperty)doc.Extension.CreateMassProperty();
        return mp == null ? 0 : mp.Volume;
    }

    /// Extrude the sketch just closed; tries the other direction when the first one does not
    /// produce the expected volume change (sign: +1 boss, -1 cut). Returns the feature.
    static Feature Extrude(Feature sketch, double depthMm, bool cut, bool throughAll, string what)
    {
        double v0 = Volume();
        for (int attempt = 0; attempt < 2; attempt++)
        {
            doc.ClearSelection2(true);
            sketch.Select2(false, 0);
            bool flip = attempt == 1;
            Feature f;
            int end = throughAll ? (int)swEndConditions_e.swEndCondThroughAll : (int)swEndConditions_e.swEndCondBlind;
            if (cut)
                f = doc.FeatureManager.FeatureCut4(true, false, flip, end, 0, depthMm * MM, 0, false, false, false, false, 0, 0,
                    false, false, false, false, false, true, true, true, true, false, 0, 0, false, false);
            else
                f = doc.FeatureManager.FeatureExtrusion2(true, false, flip, end, 0, depthMm * MM, 0, false, false, false, false, 0, 0,
                    false, false, false, false, true, true, true, 0, 0, false);
            if (f == null) continue;
            double v1 = Volume();
            if (cut ? v1 < v0 - 1e-12 : v1 > v0 + 1e-12) { f.Name = what; if (progressFile != null) File.AppendAllText(progressFile, DateTime.Now.ToString("HH:mm:ss ") + "  ok " + what + System.Environment.NewLine); return f; }
            // this direction changed nothing (a cut into air, a boss into existing material): other way
            doc.ClearSelection2(true); f.Select2(false, 0); doc.EditDelete();
        }
        L("WARNING: " + what + " did not change the part");
        return null;
    }

    static void Save(string dir, string name)
    {
        int e = 0, w = 0;
        doc.ForceRebuild3(false);
        doc.ShowNamedView2("*Isometric", (int)swStandardViews_e.swIsometricView);
        doc.ViewZoomtofit2();
        doc.Extension.SaveAs3(Path.Combine(dir, name + ".SLDPRT"), 0, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, null, ref e, ref w);
        doc.Extension.SaveAs3(Path.Combine(dir, name + ".STL"), 0, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, null, ref e, ref w);
        doc.Extension.SaveAs3(Path.Combine(dir, name + ".STEP"), 0, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, null, ref e, ref w);
        doc.SaveBMP(Path.Combine(dir, name + ".bmp"), 1400, 1000);
        var box = (double[])((PartDoc)doc).GetPartBox(true);
        L(string.Format("{0}: {1:0.0} x {2:0.0} x {3:0.0} mm, volume {4:0} cm3 -> {0}.SLDPRT / .STL / .STEP", name,
            (box[3] - box[0]) / MM, (box[4] - box[1]) / MM, (box[5] - box[2]) / MM, Volume() * 1e6));
    }

    /// Planar faces of the part lying in the plane z = zMm (normal along z).
    static List<Face2> FacesAtZ(double zMm)
    {
        var out_ = new List<Face2>();
        var bodies = (object[])((PartDoc)doc).GetBodies2((int)swBodyType_e.swSolidBody, true);
        if (bodies == null) return out_;
        foreach (Body2 b in bodies)
            foreach (Face2 f in (object[])b.GetFaces())
            {
                var s = (Surface)f.GetSurface();
                if (!s.IsPlane()) continue;
                var pp = (double[])s.PlaneParams;                  // normal x, y, z, root point x, y, z
                if (Math.Abs(Math.Abs(pp[2]) - 1) < 1e-6 && Math.Abs(pp[5] - zMm * MM) < 1e-6) out_.Add(f);
            }
        return out_;
    }

    static bool SelectPlanarFace(double zMm, bool largest)
    {
        Face2 best = null; double area = -1;
        foreach (var f in FacesAtZ(zMm)) { double a = f.GetArea(); if (a > area) { area = a; best = f; } }
        return best != null && ((Entity)best).Select4(false, null);
    }

    static double PlanarFaceArea(double zMm)
    {
        double a = 0; foreach (var f in FacesAtZ(zMm)) a += f.GetArea(); return a;
    }

    // ------------------------------------------------------------------ parts ---
    static void BuildBody(P p, string dir)
    {
        var E = p.O("envelope"); var F = p.O("fasteners"); var G = p.O("glands"); var U = p.O("usb_access");
        var V = p.O("vents"); var K = p.O("keyholes"); var EP = p.O("electronics_plate");
        double W = E.N("width"), H = E.N("height"), D = E.N("depth"), t = E.N("wall"), r = E.N("corner_radius");
        NewPart();
        // 1. solid block with rounded vertical edges, shelled open at the front
        Open("Front Plane"); RoundRect(-W / 2, 0, W / 2, H, r); var sk = Close();
        Extrude(sk, D, false, false, "Block");
        // The face to open is found by its geometry (planar, at z = D). Selecting it by a point went through the
        // graphics view and, depending on how the window was turned, picked nothing: SOLIDWORKS then shelled a
        // CLOSED box (2026-10-24 build: front closed, 19 interferences with the panel's parts).
        doc.ClearSelection2(true);
        if (!SelectPlanarFace(D, true)) throw new Exception("Body: no front face at z = depth to open");
        double vb = Volume();
        doc.InsertFeatureShell(t * MM, false);
        if (Volume() >= vb - 1e-9) L("WARNING: shell failed");
        if (PlanarFaceArea(D) > 0.2 * W * H * MM * MM)
            throw new Exception("Body: the shell left the front CLOSED - not saving a wrong box");
        // 2. corner columns, full depth, with heat-set insert holes for the front panel
        double ci = F.N("corner_boss_inset"), cd = F.N("corner_boss_d");
        double[,] corners = { { -W / 2 + ci, ci }, { W / 2 - ci, ci }, { -W / 2 + ci, H - ci }, { W / 2 - ci, H - ci } };
        Open("Front Plane"); for (int i = 0; i < 4; i++) Circle(corners[i, 0], corners[i, 1], cd); sk = Close();
        Extrude(sk, D, false, false, "Corner columns");
        Open(Plane("Front Plane", D)); for (int i = 0; i < 4; i++) Circle(corners[i, 0], corners[i, 1], F.N("insert_hole_d")); sk = Close();
        Extrude(sk, F.N("insert_hole_depth"), true, false, "Front panel insert holes");
        // 3. bosses for the removable electronics plate (heat-set inserts)
        double pw = W - 2 * EP.N("x_margin"), py0 = EP.N("y_bottom"), py1 = H - EP.N("y_top_margin"), hi = EP.N("hole_inset");
        double[,] pb = { { -pw / 2 + hi, py0 + hi }, { pw / 2 - hi, py0 + hi }, { -pw / 2 + hi, py1 - hi }, { pw / 2 - hi, py1 - hi } };
        string pz = Plane("Front Plane", t);
        Open(pz); for (int i = 0; i < 4; i++) Circle(pb[i, 0], pb[i, 1], EP.N("boss_d")); sk = Close();
        Extrude(sk, EP.N("boss_h"), false, false, "Plate bosses");
        Open(Plane("Front Plane", t + EP.N("boss_h"))); for (int i = 0; i < 4; i++) Circle(pb[i, 0], pb[i, 1], F.N("insert_hole_d")); sk = Close();
        Extrude(sk, Math.Min(F.N("insert_hole_depth"), EP.N("boss_h") + t - 1), true, false, "Plate insert holes");
        // 4. bottom cable-gland holes (Top Plane = the bottom face, y = 0; sketch y = -z)
        double gz = G.N("z");
        Open("Top Plane"); foreach (var o in G.A("holes")) { var h = new P((Dictionary<string, object>)o); Circle(h.N("x"), -gz, h.N("d")); } sk = Close();
        Extrude(sk, t + 1, true, false, "Cable gland holes");
        // 5. cable-tie bars on the back wall above the glands (strain relief), each with a tie slot
        double bw = G.N("tie_bar_w"), bh = G.N("tie_bar_h"), bd = G.N("tie_bar_d"), by = G.N("tie_bar_y");
        Open(pz); foreach (var o in G.A("holes")) { var h = new P((Dictionary<string, object>)o); Rect(h.N("x"), by, bw, bh); } sk = Close();
        Extrude(sk, bd, false, false, "Cable tie bars");
        // tie slots: vertical tunnels through each bar, from its lower face (sketch y = -z)
        string tieP = Plane("Top Plane", by - bh / 2 - 0.01);
        Open(tieP); foreach (var o in G.A("holes")) { var h = new P((Dictionary<string, object>)o); Rect(h.N("x"), -(t + bd / 2 + 1), G.N("tie_slot_w"), G.N("tie_slot_h")); } sk = Close();
        Extrude(sk, bh + 0.02, true, false, "Cable tie slots");
        // 6. ESP32 USB access in a side wall (Right Plane offset; sketch x = -z, y = y)
        double sx = U.S("side") == "left" ? -W / 2 : W / 2;
        Open(Plane("Right Plane", sx)); Rect(-U.N("z"), U.N("y"), U.N("w"), U.N("h")); sk = Close();
        Extrude(sk, t + 1, true, false, "USB access");
        // 7. vents in both side walls (upper part, beside the buck converter)
        foreach (double side in new double[] { -W / 2, W / 2 })
        {
            Open(Plane("Right Plane", side));
            foreach (var yo in V.A("y_list")) { double y = Convert.ToDouble(yo); Slot(-V.N("z_from"), y, -V.N("z_to"), V.N("slot_h")); }
            sk = Close();
            Extrude(sk, t + 1, true, false, side < 0 ? "Vents left" : "Vents right");
        }
        // 8. wall-mount keyholes in the back wall (head below, slot upward: hang, then slide down)
        // two cuts: a circle overlapping a slot in one sketch is not a valid profile
        Open("Front Plane"); foreach (var xo in K.A("x")) Circle(Convert.ToDouble(xo), K.N("y"), K.N("head_d")); sk = Close();
        Extrude(sk, t + 1, true, false, "Keyhole heads");
        Open("Front Plane");
        foreach (var xo in K.A("x")) { double x = Convert.ToDouble(xo);
            doc.SketchManager.CreateSketchSlot((int)swSketchSlotCreationType_e.swSketchSlotCreationType_line, (int)swSketchSlotLengthType_e.swSketchSlotLengthType_CenterCenter,
                K.N("slot_w") * MM, x * MM, K.N("y") * MM, 0, x * MM, (K.N("y") + K.N("slot_len")) * MM, 0, 0, 0, 0, 1, false); }
        sk = Close();
        Extrude(sk, t + 1, true, false, "Keyhole slots");
        Save(dir, "DoorEnclosure_Body");
    }

    /// Bosses / walls behind the panel (toward -z from the rear face): sketched at their tip plane and
    /// grown toward the panel, so they can only land on the rear. `draw` sketches the profile.
    static void Behind(double h, Action draw, string what)
    {
        Open(Plane("Front Plane", -h)); draw(); var sk = Close();
        Extrude(sk, h, false, false, what);
    }

    // ---- the module mounts, shared by the panel and the fit coupon (rear face z = 0, front z = t) ----
    static void TftMount(P T, P F, double cx, double cy, double t)
    {
        Open("Front Plane"); Rect(cx, cy + T.N("window_offset_y"), T.N("window_w"), T.N("window_h")); var sk = Close();
        Extrude(sk, t, true, true, "TFT window");
        double hx = T.N("hole_dx") / 2, hy = T.N("hole_dy") / 2, bh = T.N("boss_h");
        Behind(bh, () => { foreach (var sx in new[] { -1, 1 }) foreach (var sy in new[] { -1, 1 }) Circle(cx + sx * hx, cy + sy * hy, T.N("boss_d")); }, "TFT bosses");
        Open(Plane("Front Plane", -bh)); foreach (var sx in new[] { -1, 1 }) foreach (var sy in new[] { -1, 1 }) Circle(cx + sx * hx, cy + sy * hy, F.N("pilot_m25_d")); sk = Close();
        Extrude(sk, T.N("pilot_depth"), true, false, "TFT pilot holes");
    }

    static void NfcMount(P N, P F, double cx, double cy, double t)
    {
        // pocket with 4 islands left standing (the board rests on them at the rear plane)
        double ix = N.N("island_dx") / 2, iy = N.N("island_dy") / 2;
        Open("Front Plane"); Rect(cx, cy, N.N("pocket_w"), N.N("pocket_h"));
        foreach (var sx in new[] { -1, 1 }) foreach (var sy in new[] { -1, 1 }) Circle(cx + sx * ix, cy + sy * iy, N.N("island_d"));
        var sk = Close();
        Extrude(sk, N.N("pocket_depth"), true, false, "NFC pocket");
        Open("Front Plane"); foreach (var sx in new[] { -1, 1 }) foreach (var sy in new[] { -1, 1 }) Circle(cx + sx * ix, cy + sy * iy, F.N("pilot_m25_d")); sk = Close();
        Extrude(sk, N.N("pilot_depth"), true, false, "NFC pilot holes");
    }

    /// Owner 2026-10-24: the R307 stands OUT of the panel (finger on its 45-degree end). Opening = the measured end
    /// + 0.3; a sleeve behind the panel as long as the rest of the body; a back stop (two ledges, wires pass in
    /// the middle) takes the finger's push; one M2.5 self-tapping screw through the sleeve wall clamps the body.
    static void FpProtrude(P G, P F, double cx, double cy, double t)
    {
        double fw = G.N("face_w"), fh = G.N("face_h"), sw = G.N("sleeve_wall");
        double sl = G.N("body_l") - G.N("protrude") - t;                       // sleeve: rest of the body behind the panel
        double led = G.N("stop_ledge"), st = G.N("stop_t");
        Open("Front Plane"); Rect(cx, cy, fw, fh); var sk = Close();
        Extrude(sk, t, true, true, "Fingerprint opening");
        // sleeve: a ring (outer rect minus the opening) grown from its tip toward the panel
        Behind(sl, () => { Rect(cx, cy, fw + 2 * sw, fh + 2 * sw); Rect(cx, cy, fw, fh); }, "Fingerprint sleeve");
        // back stop: two ledges at the sleeve's end, reaching `led` inward from the left / right walls
        Open(Plane("Front Plane", -(sl + st)));
        RectXY(cx - fw / 2 - sw, cy - fh / 2 - sw, cx - fw / 2 + led, cy + fh / 2 + sw);
        RectXY(cx + fw / 2 - led, cy - fh / 2 - sw, cx + fw / 2 + sw, cy + fh / 2 + sw);
        sk = Close();
        Extrude(sk, st, false, false, "Fingerprint back stop");
        // clamp screw: an M2.5 pilot through the top and bottom walls, halfway down the sleeve (Top Plane:
        // sketch y = -z, as the tie slots) - the screw goes in from either side
        Open(Plane("Top Plane", cy + fh / 2 + sw + 1)); Circle(cx, sl / 2, F.N("pilot_m25_d")); sk = Close();
        Extrude(sk, 0, true, true, "Fingerprint clamp screw pilot");
    }

    static void FpMount(P G, double cx, double cy, double t)
    {
        double L = G.N("pocket_l"), Wd = G.N("pocket_w"), cw = G.N("cradle_wall"), ch = G.N("cradle_h");
        double s = G.S("sensor_end") == "left" ? -1 : 1;                     // sensor end side (x)
        Open("Front Plane"); Rect(cx, cy, L, Wd); var sk = Close();
        Extrude(sk, G.N("pocket_depth"), true, false, "Fingerprint pocket");
        double ax = cx + s * (G.N("body_l") / 2 - G.N("aperture_l") / 2);  // head face starts at the sensor end
        Open("Front Plane"); Rect(ax, cy, G.N("aperture_l"), G.N("aperture_w")); sk = Close();
        Extrude(sk, t, true, true, "Fingerprint aperture");
        // cradle: two side walls + the wall at the sensor end; the cable end stays open
        Behind(ch, () => { RectXY(cx - L / 2 - cw, cy + Wd / 2, cx + L / 2, cy + Wd / 2 + cw); RectXY(cx - L / 2 - cw, cy - Wd / 2 - cw, cx + L / 2, cy - Wd / 2); }, "Fingerprint cradle sides");
        double ex = s < 0 ? cx - L / 2 - cw : cx + L / 2;
        Behind(ch, () => RectXY(ex, cy - Wd / 2, ex + cw, cy + Wd / 2), "Fingerprint cradle end");
        // zip-tie slots through both side walls near their tips (Top Plane: sketch y = -z)
        double zt = ch - 1.5 - G.N("tie_slot_h") / 2;
        Open(Plane("Top Plane", cy + Wd / 2 + cw + 1));
        foreach (var dx in new[] { -10.0, 10.0 }) Rect(cx + dx, zt, G.N("tie_slot_w"), G.N("tie_slot_h"));
        sk = Close();
        Extrude(sk, 0, true, true, "Fingerprint tie slots");
    }

    static void BuzzerMount(P B, double cx, double cy, double t, double id)
    {
        Open("Front Plane"); Circle(cx, cy, B.N("sound_hole_d"));
        for (int i = 0; i < 6; i++) { double a = i * Math.PI / 3; Circle(cx + B.N("sound_ring_d") / 2 * Math.Cos(a), cy + B.N("sound_ring_d") / 2 * Math.Sin(a), B.N("sound_hole_d")); }
        var sk = Close();
        Extrude(sk, t, true, true, "Buzzer sound holes");
        Behind(B.N("cradle_h"), () => { Circle(cx, cy, id + 2 * B.N("cradle_wall")); Circle(cx, cy, id); }, "Buzzer cradle");
    }

    static void BuildPanel(P p, string dir)
    {
        var E = p.O("envelope"); var F = p.O("fasteners"); var FP = p.O("front_panel"); var C = p.O("print");
        var T = p.O("tft"); var N = p.O("nfc"); var FG = p.O("fingerprint"); var LD = p.O("leds"); var BZ = p.O("buzzer");
        double W = E.N("width"), H = E.N("height"), t = FP.N("thickness"), wall = E.N("wall"), r = E.N("corner_radius"), clr = C.N("clearance");
        double eng = FP.N("engrave_depth"), th = FP.N("text_height");
        NewPart();
        Open("Front Plane"); RoundRect(-W / 2, 0, W / 2, H, r); var sk = Close();
        Extrude(sk, t, false, false, "Panel");
        string front = Plane("Front Plane", t), rear = "Front Plane";
        double ci = F.N("corner_boss_inset");
        Open(rear); foreach (var c in new[] { new[] { -W / 2 + ci, ci }, new[] { W / 2 - ci, ci }, new[] { -W / 2 + ci, H - ci }, new[] { W / 2 - ci, H - ci } })
            Circle(c[0], c[1], F.N("screw_clear_d")); sk = Close();
        Extrude(sk, t, true, true, "Screw holes");
        double tl = FP.N("locating_tab_len"), tt = FP.N("locating_tab_t"), tin = wall + clr;
        Behind(FP.N("locating_tab_h"), () => {
            RectXY(-tl / 2, tin, tl / 2, tin + tt); RectXY(-tl / 2, H - tin - tt, tl / 2, H - tin);
            RectXY(-W / 2 + tin, H / 2 - tl / 2, -W / 2 + tin + tt, H / 2 + tl / 2); RectXY(W / 2 - tin - tt, H / 2 - tl / 2, W / 2 - tin, H / 2 + tl / 2); }, "Locating tabs");
        double tx = T.N("center_x"), ty = T.N("center_y"), nx = N.N("center_x"), ny = N.N("center_y"), fx = FG.N("center_x"), fy = FG.N("center_y");
        TftMount(T, F, tx, ty, t);
        NfcMount(N, F, nx, ny, t);
        double om = N.N("tap_outline_margin"), og = N.N("tap_outline_groove");
        Open(front); Rect(nx, ny, N.N("pocket_w") + 2 * (om + og), N.N("pocket_h") + 2 * (om + og)); sk = Close();
        Extrude(sk, eng, true, false, "NFC tap outline recess");
        Open(Plane("Front Plane", t - eng)); Rect(nx, ny, N.N("pocket_w") + 2 * om, N.N("pocket_h") + 2 * om); sk = Close();
        Extrude(sk, eng, false, false, "NFC tap outline fill");
        bool fpOut = FG.S("mount") == "protrude";
        if (fpOut) FpProtrude(FG, F, fx, fy, t); else FpMount(FG, fx, fy, t);
        double fpHalf = fpOut ? FG.N("face_h") / 2 : FG.N("pocket_w") / 2;
        double ld = LD.B("use_holder") ? LD.N("holder_d") : LD.N("bare_d");
        Open(rear); Circle(LD.N("green_x"), LD.N("y"), ld); Circle(LD.N("red_x"), LD.N("y"), ld); sk = Close();
        Extrude(sk, t, true, true, "LED holes");
        BuzzerMount(BZ, BZ.N("center_x"), BZ.N("center_y"), t, BZ.N("cradle_id"));
        // engraved labels (front), centred under / over each part
        Open(front);
        bool txt = Text(0, FP.N("title_y") - FP.N("title_height"), FP.S("title"), FP.N("title_height"));
        Text(nx, ny - N.N("pocket_h") / 2 - om - og - th - 2.5, "TAP CARD", th);
        Text(fx, fy - fpHalf - th - 4, "FINGER", th);
        Text(LD.N("green_x"), LD.N("y") - ld / 2 - th - 2.5, "OK", th);
        Text(LD.N("red_x"), LD.N("y") - ld / 2 - th - 2.5, "DENIED", th);
        sk = Close();
        bool raised = FP.S("label_style") == "raised";
        if (!txt) L("WARNING: sketch text not available - labels skipped");
        else if (raised) Extrude(sk, FP.N("raised_height"), false, false, "Labels (raised)");
        else Extrude(sk, eng, true, false, "Labels (engraved)");
        Save(dir, "DoorEnclosure_FrontPanel");
    }

    static void BuildPlate(P p, string dir)
    {
        var E = p.O("envelope"); var F = p.O("fasteners"); var EP = p.O("electronics_plate");
        double W = E.N("width"), H = E.N("height");
        double pw = W - 2 * EP.N("x_margin"), py0 = EP.N("y_bottom"), py1 = H - EP.N("y_top_margin"), hi = EP.N("hole_inset");
        NewPart();
        Open("Front Plane"); RoundRect(-pw / 2, py0, pw / 2, py1, 4); var sk = Close();
        Extrude(sk, EP.N("thickness"), false, false, "Plate");
        Open("Front Plane");
        foreach (var c in new[] { new[] { -pw / 2 + hi, py0 + hi }, new[] { pw / 2 - hi, py0 + hi }, new[] { -pw / 2 + hi, py1 - hi }, new[] { pw / 2 - hi, py1 - hi } })
            Circle(c[0], c[1], F.N("screw_clear_d"));
        double sl = EP.N("slot_len"), sxp = EP.N("slot_pitch_x"), syp = EP.N("slot_pitch_y");
        int nx = (int)Math.Floor((pw - 2 * hi - 16 - sl) / sxp) + 1;
        double x0 = -(nx - 1) * sxp / 2;
        for (double y = py0 + hi + 12; y <= py1 - hi - 12 + 1e-6; y += syp)
            for (int i = 0; i < nx; i++) Slot(x0 + i * sxp - sl / 2, y, x0 + i * sxp + sl / 2, EP.N("slot_w"));
        sk = Close();
        Extrude(sk, EP.N("thickness"), true, true, "Mounting slots");
        // where each part goes: engraved inside its footprint, in a gap between two slot rows
        Open(Plane("Front Plane", EP.N("thickness")));
        bool any = false;
        foreach (var o in EP.A("zone_labels")) { var z = new P((Dictionary<string, object>)o); any |= Text(z.N("x"), z.N("y") - 2.1, z.S("text"), 4.2); }
        sk = Close();
        if (any) Extrude(sk, 0.6, true, false, "Zone labels");
        Save(dir, "DoorEnclosure_ElectronicsPlate");
    }

    /// The fit coupon: every critical opening at full size, with the real module mounts, printed in the
    /// panel's material and orientation BEFORE the box. One print answers every MEASURE item.
    static void BuildCoupon(P p, string dir)
    {
        var FP = p.O("front_panel"); var F = p.O("fasteners"); var T = p.O("tft"); var N = p.O("nfc"); var G = p.O("fingerprint"); var B = p.O("buzzer");
        double t = FP.N("thickness"), th = 3.5, eng = FP.N("engrave_depth");
        double W = 180, H = 150;
        NewPart();
        Open("Front Plane"); RoundRect(-W / 2, -H / 2, W / 2, H / 2, 4); var sk = Close();
        Extrude(sk, t, false, false, "Coupon");
        string front = Plane("Front Plane", t);
        var labels = new List<object[]>();
        // row 1: the three real module mounts (same code as the panel)
        TftMount(T, F, -62, 30, t); labels.Add(new object[] { -62.0, -3.5, "TFT 30x40 + 4 bosses" });
        NfcMount(N, F, -6, 34, t); labels.Add(new object[] { -6.0, 9.0, "PN532 skin 1.5" });
        FpMount(G, 56, 40, t); labels.Add(new object[] { 56.0, 24.0, "R307 21.3x19.3" });
        // row 2: hole series (thru)
        Open("Front Plane");
        double[] led = { 5.1, 5.2, 5.3, 5.4 };
        for (int i = 0; i < led.Length; i++) { double x = -80 + i * 11; Circle(x, -14, led[i]); labels.Add(new object[] { x, -22.0, led[i].ToString("0.0") }); }
        double[] gl = { 12.6, 12.8, 13.0, 16.3 };
        for (int i = 0; i < gl.Length; i++) { double x = -26 + i * 20 + (i == 3 ? 2 : 0); Circle(x, -14, gl[i]); labels.Add(new object[] { x, -27.0, gl[i].ToString("0.0") }); }
        Rect(64, -14, 21.6, 19.6);                     // the looser FP aperture (the mount above has 21.3 x 19.3, the 0.3 rule)
        sk = Close();
        Extrude(sk, t, true, true, "Hole series");
        labels.Add(new object[] { 64.0, -28.5, "FP 21.6x19.6" });
        // row 3: insert bosses (D8, h6, hole 3.9/4.0/4.2, depth 7), pilot bosses (D6, h6, 2.0/2.2/2.4), buzzer cradles 12.2/12.3/12.5
        double[] ins = { 3.9, 4.0, 4.2 }, pil = { 2.0, 2.2, 2.4 };
        Behind(6, () => { for (int i = 0; i < 3; i++) { Circle(-78 + i * 12, -44, 8); Circle(-38 + i * 10, -44, 6); } }, "Test bosses");
        Open(Plane("Front Plane", -6)); for (int i = 0; i < 3; i++) { Circle(-78 + i * 12, -44, ins[i]); } sk = Close();
        Extrude(sk, 7, true, false, "Insert test holes");
        Open(Plane("Front Plane", -6)); for (int i = 0; i < 3; i++) { Circle(-38 + i * 10, -44, pil[i]); } sk = Close();
        Extrude(sk, 7, true, false, "Pilot test holes");
        for (int i = 0; i < 3; i++) { labels.Add(new object[] { -78.0 + i * 12, -54.0, ins[i].ToString("0.0") }); labels.Add(new object[] { -38.0 + i * 10, -54.0, pil[i].ToString("0.0") }); }
        double[] bz = { 12.2, 12.3, 12.5 };
        for (int i = 0; i < 3; i++) { BuzzerMount(B, 4 + i * 22, -44, t, bz[i]); labels.Add(new object[] { 4.0 + i * 22, -58.0, bz[i].ToString("0.0") }); }
        Open(front);
        bool ok = true;
        foreach (var lb in labels) ok &= Text((double)lb[0], (double)lb[1], (string)lb[2], th);
        Text(0, H / 2 - 9, "DOOR PANEL FIT CHECK  t=" + t.ToString("0.0"), th);
        Text(-68, -71, "ENGR 5", 5.0); Text(-33, -71, "ENGR 7", 7.0);
        Text(-80 + 0, -36, "LED", th); Text(-60, -36, "INSERT", th); Text(-28, -36, "PILOT", th); Text(26, -36, "BUZZER", th);
        sk = Close();
        if (ok) Extrude(sk, eng, true, false, "Labels"); else L("WARNING: coupon labels skipped");
        Open(front); Text(10, -71, "RAISED 5", 5.0); Text(55, -71, "RAISED 7", 7.0); sk = Close();
        Extrude(sk, 0.8, false, false, "Raised text test");
        Save(dir, "DoorEnclosure_FitCoupon");
    }

    /// One box per component (its envelope incl. the clearance in params "components") for the virtual
    /// assembly; built centred on x/y with the base at z = 0, extruded toward +z (or -z for "down": parts
    /// hanging behind the front panel). Returns the part names.
    static List<string[]> BuildEnvelopes(P p, string dir)
    {
        var made = new List<string[]>();
        foreach (var o in p.A("components"))
        {
            var c = new P((Dictionary<string, object>)o);
            NewPart();
            Open("Front Plane"); if (c.D.ContainsKey("round") && c.B("round")) Circle(0, 0, c.N("w")); else Rect(0, 0, c.N("w"), c.N("h")); var sk = Close();
            var f = Extrude(sk, c.N("d"), false, false, "Envelope");
            if (f == null) continue;
            string n = "Env_" + c.S("id");
            int e = 0, w = 0;
            doc.ForceRebuild3(false);
            doc.Extension.SaveAs3(Path.Combine(dir, "envelopes", n + ".SLDPRT"), 0, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, null, ref e, ref w);
            made.Add(new[] { n, c.S("id") });
        }
        L("envelopes: " + made.Count + " component boxes -> out/envelopes/");
        return made;
    }

    static void BuildAssembly(P p, string dir)
    {
        var E = p.O("envelope"); var EP = p.O("electronics_plate");
        string tpl = sw.GetUserPreferenceStringValue((int)swUserPreferenceStringValue_e.swDefaultTemplateAssembly);
        var asm = (ModelDoc2)sw.NewDocument(tpl, 0, 0, 0);
        var ad = (AssemblyDoc)asm;
        // AddComponent5 places the centre of the part's bounding box: offset each part by its own box centre
        var centre = new Dictionary<string, double[]>();
        foreach (var n in new[] { "DoorEnclosure_Body", "DoorEnclosure_FrontPanel", "DoorEnclosure_ElectronicsPlate" })
        { int err = 0, warn = 0; var pd = sw.OpenDoc6(Path.Combine(dir, n + ".SLDPRT"), 1, 1, "", ref err, ref warn);
          var bx = (double[])((PartDoc)pd).GetPartBox(true);
          centre[n] = new[] { (bx[0] + bx[3]) / 2, (bx[1] + bx[4]) / 2, (bx[2] + bx[5]) / 2 }; }
        int aerr = 0; sw.ActivateDoc3(asm.GetTitle(), false, 0, ref aerr);
        // 2026-10-24: then put each part's ORIGIN exactly where it belongs. Placing by the box centre alone went
        // wrong once the panel grew the fingerprint sleeve (an offset plane 27 mm behind it): SOLIDWORKS' box and
        // GetPartBox disagreed and the parts overlapped (19 false interferences). Logged so it can be checked.
        var mu = (MathUtility)sw.GetMathUtility();
        Action<string, double, double, double> add = (n, x, y, z) => {
            var c0 = centre[n];
            var c = ad.AddComponent5(Path.Combine(dir, n + ".SLDPRT"), 0, "", false, "", x * MM + c0[0], y * MM + c0[1], z * MM + c0[2]);
            if (c == null) { L("WARNING: could not add " + n); return; }
            if (c.IsFixed()) { c.Select4(false, null, false); ad.UnfixComponent(); asm.ClearSelection2(true); }
            c.Transform2 = (MathTransform)mu.CreateTransform(new double[] { 1, 0, 0, 0, 1, 0, 0, 0, 1, x * MM, y * MM, z * MM, 1, 0, 0, 0 });
            var at = (double[])c.Transform2.ArrayData;
            L(string.Format("placed {0}: origin at x {1:0.0}  y {2:0.0}  z {3:0.0} mm (wanted {4:0.0} {5:0.0} {6:0.0})",
                n, at[9] / MM, at[10] / MM, at[11] / MM, x, y, z));
        };
        add("DoorEnclosure_Body", 0, 0, 0);
        add("DoorEnclosure_FrontPanel", 0, 0, E.N("depth"));
        add("DoorEnclosure_ElectronicsPlate", 0, 0, E.N("wall") + EP.N("boss_h"));
        // component envelopes: placed by their box centre (base z + d/2 up, base z - d/2 down)
        int placed = 0;
        foreach (var o in p.A("components"))
        {
            var c = new P((Dictionary<string, object>)o);
            string f = Path.Combine(dir, "envelopes", "Env_" + c.S("id") + ".SLDPRT");
            if (!File.Exists(f)) continue;
            int err = 0, warn = 0; sw.OpenDoc6(f, 1, 1, "", ref err, ref warn);
            sw.ActivateDoc3(asm.GetTitle(), false, 0, ref aerr);
            double zc = c.D.ContainsKey("dir") && c.S("dir") == "down" ? c.N("z") - c.N("d") / 2 : c.N("z") + c.N("d") / 2;
            if (ad.AddComponent5(f, 0, "", false, "", c.N("x") * MM, c.N("y") * MM, zc * MM) != null) placed++;
            else L("WARNING: could not place envelope " + c.S("id"));
        }
        doc = asm;
        asm.ForceRebuild3(false);
        // interference detection: every pair of solids that overlap (touching faces are not counted)
        var idm = ad.InterferenceDetectionManager;
        idm.TreatCoincidenceAsInterference = false;
        idm.TreatSubAssembliesAsComponents = false;
        idm.IncludeMultibodyPartInterferences = false;
        var found = idm.GetInterferences() as object[];
        var lines = new List<string>();
        if (found != null)
            foreach (var io in found)
            {
                var it = (IInterference)io;
                var comps = (object[])it.Components;
                var names = new List<string>();
                foreach (var co in comps) names.Add(((Component2)co).Name2);
                lines.Add(string.Format("{0}  <->  {1}: {2:0.000} cm3", names[0], names.Count > 1 ? names[1] : "?", it.Volume * 1e6));
            }
        idm.Done();
        File.WriteAllLines(Path.Combine(dir, "interference.txt"), lines.Count == 0 ? new[] { "NO INTERFERENCES (" + (3 + placed) + " bodies)" } : lines.ToArray());
        L("interference check: " + (3 + placed) + " bodies, " + lines.Count + " interference(s)" + (lines.Count > 0 ? ":\n  " + string.Join("\n  ", lines) : ""));
        asm.ShowNamedView2("*Isometric", (int)swStandardViews_e.swIsometricView); asm.ViewZoomtofit2();
        int e = 0, w = 0;
        asm.Extension.SaveAs3(Path.Combine(dir, "DoorEnclosure_Assembly.SLDASM"), 0, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, null, ref e, ref w);
        asm.Extension.SaveAs3(Path.Combine(dir, "DoorEnclosure_Assembly.STEP"), 0, (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, null, ref e, ref w);
        asm.SaveBMP(Path.Combine(dir, "DoorEnclosure_Assembly.bmp"), 1400, 1000);
        // views for the docs: front (through the panel's openings) and a section-like right view
        asm.ShowNamedView2("*Front", (int)swStandardViews_e.swFrontView); asm.ViewZoomtofit2();
        asm.SaveBMP(Path.Combine(dir, "DoorEnclosure_Assembly_front.bmp"), 1400, 1000);
        asm.ShowNamedView2("*Right", (int)swStandardViews_e.swRightView); asm.ViewZoomtofit2();
        asm.SaveBMP(Path.Combine(dir, "DoorEnclosure_Assembly_right.bmp"), 1400, 1000);
        // the inside: front panel hidden
        foreach (var co in (object[])ad.GetComponents(true))
        { var cc = (Component2)co; if (cc.Name2.StartsWith("DoorEnclosure_FrontPanel")) cc.Visible = (int)swComponentVisibilityState_e.swComponentHidden; }
        asm.ShowNamedView2("*Isometric", (int)swStandardViews_e.swIsometricView); asm.ViewZoomtofit2();
        asm.SaveBMP(Path.Combine(dir, "DoorEnclosure_Assembly_inside.bmp"), 1400, 1000);
        asm.ShowNamedView2("*Front", (int)swStandardViews_e.swFrontView); asm.ViewZoomtofit2();
        asm.SaveBMP(Path.Combine(dir, "DoorEnclosure_Assembly_inside_front.bmp"), 1400, 1000);
        L("assembly: body + front panel + plate + " + placed + " component envelopes -> DoorEnclosure_Assembly.SLDASM / .STEP");
    }

    public static string Run(string paramsPath, string outDir, string which)
    {
        log.Clear();
        Directory.CreateDirectory(outDir); Directory.CreateDirectory(Path.Combine(outDir, "envelopes"));
        progressFile = Path.Combine(outDir, "build_progress.log"); File.WriteAllText(progressFile, "");
        var p = new P((Dictionary<string, object>)P.Parse(File.ReadAllText(paramsPath)));
        sw = (SldWorks)Activator.CreateInstance(Type.GetTypeFromProgID("SldWorks.Application"));
        sw.Visible = true;
        sw.CloseAllDocuments(true);
        // Sketch snapping off while building (2026-10-20, found by comparing with an independent SolidCraft
        // model): with it on, a shape drawn next to another in the same sketch snapped to it - the coupon's
        // 21 x 19 FP test opening came out 21 x 16.2 (its edges on the 16.2 gland circle's quadrants) and the
        // second R307 tie slot was not cut. The user's own setting is put back afterwards.
        var inferPref = (int)swUserPreferenceToggle_e.swSketchInference;
        bool inferWas = sw.GetUserPreferenceToggle(inferPref);
        sw.SetUserPreferenceToggle(inferPref, false);
        try
        {
            if (which == "all" || which == "coupon") BuildCoupon(p, outDir);
            if (which == "all" || which == "body") BuildBody(p, outDir);
            if (which == "all" || which == "panel") BuildPanel(p, outDir);
            if (which == "all" || which == "plate") BuildPlate(p, outDir);
            if (which == "all" || which == "assembly") { BuildEnvelopes(p, outDir); BuildAssembly(p, outDir); }
        }
        catch (Exception ex) { L("ERROR: " + ex.Message + "\n" + ex.StackTrace); }
        finally { sw.SetUserPreferenceToggle(inferPref, inferWas); }
        return log.ToString();
    }
}
