#!/bin/sh
# nginx image start hook: turn HTTPS on only when a certificate is mounted.
if [ -s /etc/nginx/tls/server.crt ] && [ -s /etc/nginx/tls/server.key ]; then
  cp /etc/nginx/tls.conf.template /etc/nginx/conf.d/tls.conf
  echo "smartlab: HTTPS on (443, 8443)"
else
  rm -f /etc/nginx/conf.d/tls.conf
  echo "smartlab: no certificate in /etc/nginx/tls - HTTPS off (see docs/SECURITY.md)"
fi
