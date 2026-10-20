/**
 * Robotics Lab hero background: the lab's own UR5e + FANUC photo (assets/labs/login-robots.jpg,
 * a crop of our real photos) with layered, decorative motion - a slow parallax drift of the photo,
 * a cyan network overlay drifting at another rate, and a light sweep. CSS/SVG only; nothing here
 * reflects live robot movement. Reduced motion: everything still.
 */
export default function RoboticsHero() {
  return (
    <div className="rh absolute inset-0 overflow-hidden" aria-hidden>
      <img src="/assets/labs/login-robots.jpg" alt="" decoding="async" className="rh-img" />
      <div className="absolute inset-0 bg-gradient-to-r from-ink-800 via-ink-800/70 to-ink-800/5" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_80%_30%,rgba(34,211,238,.18),transparent_55%),radial-gradient(ellipse_at_60%_90%,rgba(251,191,36,.10),transparent_50%)]" />
      <svg className="rh-net absolute inset-0 w-full h-full" viewBox="0 0 100 60" preserveAspectRatio="none">
        <g stroke="#67e8f9" strokeOpacity=".28" strokeWidth=".12" fill="none">
          <path d="M48 12 L62 20 L76 14 L90 24 M62 20 L68 36 L84 40 M68 36 L56 48 L74 54 M84 40 L96 50" />
        </g>
        <g fill="#67e8f9">{[[48, 12], [62, 20], [76, 14], [90, 24], [68, 36], [84, 40], [56, 48], [74, 54], [96, 50]].map(([x, y], i) =>
          <circle key={i} cx={x} cy={y} r=".45" className="rh-node" style={{ animationDelay: `${i * .4}s` }} />)}</g>
      </svg>
      <div className="rh-sweep" />
      <style>{`
.rh-img{position:absolute;top:-6%;right:-4%;height:112%;width:auto;max-width:none;min-width:70%;object-fit:cover;opacity:.75;animation:rhPan 26s ease-in-out infinite alternate}
.rh-net{animation:rhNet 18s ease-in-out infinite alternate}
.rh-node{animation:rhNode 3.6s ease-in-out infinite}
.rh-sweep{position:absolute;inset:0;background:linear-gradient(105deg,transparent 40%,rgba(103,232,249,.10) 50%,transparent 60%);background-size:250% 100%;animation:rhSweep 9s linear infinite}
@keyframes rhPan{from{transform:translate3d(0,0,0) scale(1)}to{transform:translate3d(-3%,-2%,0) scale(1.05)}}
@keyframes rhNet{from{transform:translate3d(0,0,0)}to{transform:translate3d(-1.5%,1%,0)}}
@keyframes rhNode{50%{opacity:.25}}
@keyframes rhSweep{from{background-position:120% 0}to{background-position:-120% 0}}
@media (prefers-reduced-motion:reduce){.rh-img,.rh-net,.rh-node,.rh-sweep{animation:none}}`}</style>
    </div>)
}
