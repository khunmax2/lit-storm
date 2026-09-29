# The web app: built once, served as static files by nginx, which also
# forwards /api to the API service (docs/adr/0001). Build from web/.
#
# LITSTORM_BASE_PATH serves it under a path, as behind host 203's nginx at
# /litstorm (docs/web-app-design.md, base path); empty serves it at the root.
ARG LITSTORM_BASE_PATH=

FROM node:24-alpine AS build
ARG LITSTORM_BASE_PATH
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN LITSTORM_BASE_PATH="$LITSTORM_BASE_PATH" npm run build

FROM nginx:1.29-alpine
ARG LITSTORM_BASE_PATH
COPY nginx.conf /tmp/default.conf
# The files live under the base path, so nginx's root finds them by the
# request's own path. At the root there is no bare base path to redirect.
RUN base="$(echo "/$LITSTORM_BASE_PATH" | sed -e 's#//*#/#g' -e 's#/$##')" \
    && sed -e "s#__BASE__#$base#g" /tmp/default.conf > /etc/nginx/conf.d/default.conf \
    && if [ -z "$base" ]; then sed -i '/return 301 \/;/d' /etc/nginx/conf.d/default.conf; fi \
    && mkdir -p "/usr/share/nginx/html$base" \
    && echo "$base" > /etc/nginx/base-path
COPY --from=build /web/dist /tmp/dist
RUN mv /tmp/dist/* "/usr/share/nginx/html$(cat /etc/nginx/base-path)/" && rm -rf /tmp/dist
