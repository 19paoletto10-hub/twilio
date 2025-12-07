FROM nginx:stable-alpine

# Small proxy image that embeds our nginx config into the image
# and supports optional runtime variable substitution via envsubst.

RUN apk add --no-cache gettext

WORKDIR /etc/nginx/conf.d

# Copy the repository default config as a template so we can run envsubst
COPY default.conf default.conf.template

# Copy entrypoint which will render templates (if present) and start nginx
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
