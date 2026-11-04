FROM golang:1.25.0-alpine AS build

RUN apk update && apk add --no-cache git build-base libjpeg-turbo-dev libwebp-dev patch

WORKDIR /build

RUN git clone --depth 1 --branch 0.7.2 https://github.com/evolution-foundation/evolution-go.git .

COPY deploy/evolution-go/set-wa-version.patch /tmp/set-wa-version.patch
RUN patch -p1 < /tmp/set-wa-version.patch

RUN go mod download

ARG VERSION=0.7.2-setwaversion
RUN CGO_ENABLED=1 go build -ldflags "-X main.version=${VERSION}" -o server ./cmd/evolution-go

FROM alpine:3.19.1 AS final

RUN apk update && apk add --no-cache tzdata ffmpeg libjpeg-turbo libwebp poppler-utils

WORKDIR /app

COPY --from=build /build/server .
COPY --from=build /build/manager/dist ./manager/dist
COPY --from=build /build/VERSION ./VERSION

ENV TZ=America/Sao_Paulo

ENTRYPOINT ["/app/server"]
