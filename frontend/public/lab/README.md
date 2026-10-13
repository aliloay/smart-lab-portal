# Lab photographs (served by the portal)

Only optimised, approved images go here. Originals stay OUTSIDE `public/` (not served):
`frontend/lab-photos/originals/` - never edited, never overwritten. No people in any photo (public repo).

```
public/lab/
  labs/<LAB_CODE>/hero.webp                 wide photo of the room (e.g. labs/LAB_01/hero.webp)
  equipment/<id>/hero.webp                  best realistic view       role 'hero'
  equipment/<id>/angle-1.webp, angle-2...   other sides               role 'angle'
  equipment/<id>/detail-1.webp              close-up                  role 'detail'
  equipment/<id>/isolated.webp              background removed        role 'isolated',     kind 'isolated'
  equipment/<id>/illustration.webp          exploded / annotated      role 'illustration', kind 'illustration'
  equipment/<id>/dimensional.webp           depth visual              role 'dimensional',  kind 'dimensional'
  equipment/<id>/thumb/<name>.webp          ~480 px wide, for grids   -> `thumb`
```
`<id>` = the `id` in `frontend/src/lib/labVisuals.ts` (ur5e, fanuc, robotics-pcs, s7-1200, iot, conveyor).

Sizes: hero 1920 px wide (~250-400 KB WebP q80), others 1600 px, thumbs 480 px.
Then add an entry to `images: [...]` in `labVisuals.ts` with `src`, `thumb`, `alt`, `role`, `kind`,
`width`/`height`, and for anything edited `from: '<original file name>'`. No component change needed.

Optional conversion (needs approval to install nothing - Pillow is already used by project tools if present):
`py -c "from PIL import Image; im=Image.open('in.jpg'); im.thumbnail((1920,1920)); im.save('hero.webp', quality=80)"`
