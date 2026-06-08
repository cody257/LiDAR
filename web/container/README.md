# lidar-arch pipeline container (Milestone B)

Runs the full pipeline behind a tiny HTTP server on `:8080`, for Cloudflare Containers
(and plain Docker in local dev).

    POST /run  {bbox:[w,s,e,n], resource:"<ept-url>", products:["lrm","rrim","svf"]}
          -> { bbox, products:[...], pngs:{ name: base64-png } }
    GET  /health -> {ok:true}

The Worker writes the returned PNGs to R2; the container itself is stateless.

## Build & test locally (Docker only — no Cloudflare account)

From the **repo root**:

    docker build -f web/container/Dockerfile -t lidar-arch:dev .
    docker run --rm -p 8080:8080 lidar-arch:dev

Then in another shell (Pueblo Grande test box):

    curl -s -X POST localhost:8080/run -H "content-type: application/json" -d "{\"bbox\":[-111.9856,33.4452,-111.9816,33.4482],\"resource\":\"https://s3-us-west-2.amazonaws.com/usgs-lidar-public/AZ_MaricopaPinal_1_2020/ept.json\",\"products\":[\"lrm\",\"rrim\"]}" > result.json

`result.json` contains base64 PNGs under `.pngs`; the platform mound should be visible in `lrm`/`rrim`.
