#!/bin/sh
# nginx image start hook: turn HTTPS on only when a certificate is mounted.
# Without a certificate the HTTP-to-HTTPS redirect is switched off too, so a fresh
# installation still serves the portal on plain HTTP instead of redirecting to a closed port.
CONF=/etc/nginx/conf.d/default.conf
[ -f /etc/nginx/default.conf.orig ] || cp "$CONF" /etc/nginx/default.conf.orig
cp /etc/nginx/default.conf.orig "$CONF"
if [ -s /etc/nginx/tls/server.crt ] && [ -s /etc/nginx/tls/server.key ]; then
  cp /etc/nginx/tls.conf.template /etc/nginx/conf.d/tls.conf
  echo "smartlab: HTTPS on (443, 8443)"
else
  rm -f /etc/nginx/conf.d/tls.conf
  sed -i 's|return 301 https://[^;]*;|# HTTPS off: no redirect|' "$CONF"
  echo "smartlab: no certificate in /etc/nginx/tls - HTTPS off, portal served on HTTP (see docs/SECURITY.md)"
fi
