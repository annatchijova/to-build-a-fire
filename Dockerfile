FROM nginxinc/nginx-unprivileged:1.28.2-alpine3.23

COPY --chown=101:101 web/ /usr/share/nginx/html/
COPY --chown=101:101 deployment/cloud-run/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080
