# Institution logo

`giu-logo.png` is the German International University logo, prepared for the
portal's dark interface:

- the white background removed (transparent PNG),
- the black artwork (the "G", the lettering, the Arabic name and the black
  flag segment) reversed to white so it stays visible on dark navy,
- the red and gold kept at the official values (210, 17, 25) and (218, 156, 4).

It is shown on the sign-in page and at the top of the sidebar. The Smart Lab
mark next to it is the portal's own, original design.

To use a different file (for example an official reversed logo from the
university's brand office), place it here and set in `frontend/.env`:

    VITE_INSTITUTION_LOGO=/brand/your-file.png

then restart `npm run dev` or rebuild. If the file cannot be loaded, the
portal shows the university's name as text instead.
