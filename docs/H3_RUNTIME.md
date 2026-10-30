# MiniMax H3 runtime (Kaggle → KEYSTONE)

KEYSTONE generates video on exactly one backend: the MiniMax H3 / PinkCherry 1.8
ComfyUI graph served by the Kaggle notebook. There is no fallback model and no
simulated output — if the runtime is unreachable the API refuses the job.

## Pipeline

```text
Composer + uploaded references
  -> POST /v1/sessions/{id}/messages      (asset_ids = 1 or 2 references)
  -> jobs row + reference_ids
  -> POST {runtime}/upload/image          references into ComfyUI input/
  -> POST {runtime}/prompt                workflows/h3-ref2va.json -> API format
  -> GET  {runtime}/history/{prompt_id}   poll
  -> GET  {runtime}/view                  download MP4
  -> assets row (media_type=video, relationship=animation, parent_asset_id=reference)
  -> SSE stages, canvas playback
```

`workflows/h3-ref2va.json` is the real workflow from
`SexGod1979/PinkCherry-NSFW_MiniMax-H3` (`ref2va`, turbo 8-step, video + audio).
Node mapping used by `apps/api/src/creative/h3.py`:

| Node | Role |
|---|---|
| 138 | prompt (`PrimitiveStringMultiline`) |
| 181 / 187 | reference images → `ref_image_0` / `ref_image_1` |
| 136 | `MiniMaxH3ReferenceToVideo` |
| 132 | duration in seconds |
| 143 | sampler steps |
| 115 | resolution selector (aspect + megapixels) |
| 148 | `VHS_VideoCombine` (H.264 + AAC output) |

Two references maximum; a single reference detaches `ref_image_1` instead of
sending a stale filename. Reference **audio** sockets are disconnected because
the UI does not collect audio yet.

## Bring-up

1. Kaggle notebook 02: ComfyUI running on `127.0.0.1:8188` with the H3 weights.
2. Kaggle notebook 03: starts `keystone_h3_bridge.py` on `127.0.0.1:8189` and a
   Cloudflare tunnel, then proves `/keystone/health` and `/system_stats` through
   the public URL. It prints:

   ```text
   KEYSTONE_COMFY_URL=https://<random>.trycloudflare.com
   KEYSTONE_COMFY_API_KEY=<token>
   ```

3. Put those in `.env` (see `.env.example`; `.env` is gitignored).
4. Restart the API. `GET /v1/health` reports `creative.configured`, and
   `GET /v1/creative/h3` adds live reachability.
5. Upload 1–2 reference images, choose Animate, and send a prompt.

## Security and limits

- The bridge requires `Authorization: Bearer <token>` on every proxied call;
  `GET /keystone/health` stays open for tunnel checks.
- The token grants use of the Kaggle GPU. Rotate it by restarting the bridge cell.
- The tunnel and ComfyUI die with the Kaggle session; rerun notebook 03 and
  update `.env` afterwards.
- ComfyUI runs on one T4 and the model is large: expect minutes per clip, not
  seconds. `KEYSTONE_COMFY_TIMEOUT` bounds the wait.
- The checkpoint is marked NSFW by its publisher. Use lawful content only and
  follow its license.
