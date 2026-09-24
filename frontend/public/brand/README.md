# Institution logo slot

The portal shows the **Smart Lab** mark, which is an original design, and the
text "German International University". It never draws an imitation of the
university's logo.

To show the official GIU logo:

1. Put the file supplied by the university in this folder, for example
   `frontend/public/brand/giu-logo.png` (a transparent PNG or an SVG, light
   coloured for dark backgrounds, 64 px or more in height).
2. Create `frontend/.env` containing:

       VITE_INSTITUTION_LOGO=/brand/giu-logo.png

3. Restart `npm run dev` (or rebuild).

The sidebar and the login page then show the logo next to the Smart Lab mark.
If the setting is absent, or the file cannot be loaded, the text label is
shown instead, so nothing breaks.
