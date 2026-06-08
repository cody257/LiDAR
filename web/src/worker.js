/* lidar-arch Worker (Milestone B).
 *  - Serves the static map app (public/) via the ASSETS binding.
 *  - POST /api/run {bbox, [resource], [products]} -> runs the pipeline in the
 *    container, caches the PNGs in R2 (per product), returns result URLs.
 *  - GET  /api/result/:key/:product.png -> serves a cached PNG from R2.
 *
 * Local dev reaches the pipeline at env.CONTAINER_URL (the Docker container on
 * :8080). Production will swap that for the Cloudflare Container binding (B4).
 */

const PRODUCTS = ["svf", "lrm", "slope", "openness", "rrim"];
const DEFAULT_PRODUCTS = ["lrm", "rrim", "svf"];

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/run" && request.method === "POST") {
      return handleRun(request, env);
    }

    const m = url.pathname.match(/^\/api\/result\/([A-Za-z0-9_-]+)\/([a-z]+)\.png$/);
    if (m && request.method === "GET") {
      const obj = await env.RESULTS.get(`${m[1]}/${m[2]}.png`);
      if (!obj) return new Response("not found", { status: 404 });
      return new Response(obj.body, {
        headers: { "content-type": "image/png", "cache-control": "public, max-age=86400" },
      });
    }

    // everything else -> the static map app
    return env.ASSETS.fetch(request);
  },
};

async function handleRun(request, env) {
  let req;
  try {
    req = await request.json();
  } catch {
    return json({ error: "invalid JSON body" }, 400);
  }

  const bbox = req.bbox;
  const resource = req.resource || null;
  let products = Array.isArray(req.products)
    ? req.products.filter((p) => PRODUCTS.includes(p))
    : [];
  if (!products.length) products = DEFAULT_PRODUCTS.slice();
  if (!Array.isArray(bbox) || bbox.length !== 4 || bbox.some((n) => typeof n !== "number")) {
    return json({ error: "bbox must be [west, south, east, north] numbers" }, 400);
  }

  const key = cacheKey(bbox, resource);

  // per-product R2 cache check
  const present = {};
  await Promise.all(
    products.map(async (p) => {
      present[p] = !!(await env.RESULTS.head(`${key}/${p}.png`));
    })
  );
  const missing = products.filter((p) => !present[p]);

  if (missing.length) {
    const base = (env.CONTAINER_URL || "").replace(/\/+$/, "");
    if (!base) return json({ error: "CONTAINER_URL not configured" }, 500);

    let resp;
    try {
      resp = await fetch(`${base}/run`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ bbox, resource, products: missing }),
      });
    } catch (e) {
      return json({ error: "pipeline container unreachable", detail: String(e) }, 502);
    }
    if (!resp.ok) {
      const detail = await resp.text();
      return json({ error: "pipeline failed", detail: detail.slice(0, 2000) }, 502);
    }
    const data = await resp.json();
    await Promise.all(
      Object.entries(data.pngs || {}).map(([p, b64]) =>
        env.RESULTS.put(`${key}/${p}.png`, b64ToBytes(b64), {
          httpMetadata: { contentType: "image/png" },
        })
      )
    );
  }

  return json({
    key,
    bbox,
    products,
    cached: missing.length === 0,
    urls: Object.fromEntries(products.map((p) => [p, `/api/result/${key}/${p}.png`])),
  });
}

function cacheKey(bbox, resource) {
  const s = bbox.map((n) => Number(n).toFixed(5)).join(",") + "|" + (resource || "");
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return "b" + (h >>> 0).toString(36);
}

function b64ToBytes(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json" },
  });
}
