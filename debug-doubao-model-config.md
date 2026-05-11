# Debug Session: doubao-model-config

Status: OPEN

## Symptom

User has quota for `doubao-seedream-4-5-251128` image generation and `doubao-seed-1-8-251228` responses model, but the app still fails to generate images.

## Constraints

- No business logic changes before evidence is collected.
- First debugging write is this session record.
- Avoid printing API keys; use masked values only.

## Hypotheses

1. Runtime model preset overwrites `.env.local`, switching image model back to `doubao-seedream-5-0-260128`.
2. `ai-service/local-env.ps1` and `.env.local` disagree, and the active startup path loads a different file than expected.
3. The frontend model-switch endpoint mutates `os.environ` in the running process, so current runtime config differs from files on disk.
4. The LLM client still calls `/chat/completions`, while `doubao-seed-1-8-251228` example requires `/responses`.
5. Image generation code can use `doubao-seedream-4-5-251128`, but the active process has not been restarted after config changes.

## Evidence Log

- Direct Seedream 4.5 API test with current ARK key returned HTTP 200 and a URL.
- Current runtime `/ai/health` reports image model `doubao-seedream-5-0-260128`, not `doubao-seedream-4-5-251128`.
- `.env.local` still configures `IMAGE_MODEL=doubao-seedream-5-0-lite-260128`.
- `local-env.ps1` configures `IMAGE_MODEL=doubao-seedream-4-5-251128`, but assigns image/video API keys from `LLM_API_KEY`, which is the GLM key in its active block.
- The runtime `doubao` preset in `app/main.py` configures image model `doubao-seedream-5-0-260128` and LLM model `doubao-seed-2-0-lite-260215`.
- `doubao-seed-1-8-251228` returned HTTP 200 on both `/chat/completions` and `/responses` for a simple text request.

## Current Conclusion

The active failure is caused by runtime configuration using the old Seedream 5.0 model, while the available quota is for Seedream 4.5. The API key itself is usable for Seedream 4.5.

## Fix Applied

- Updated `.env.local` to use `LLM_PROVIDER=doubao`, `LLM_MODEL=doubao-seed-1-8-251228`, and `IMAGE_MODEL=doubao-seedream-4-5-251128`.
- Updated `local-env.ps1` active block to use ARK key for Doubao LLM/Image/Video instead of using the GLM key for Seedream.
- Updated the runtime `doubao` preset in `app/main.py` to use `doubao-seed-1-8-251228` and `doubao-seedream-4-5-251128`.

## Post-Fix Verification

- Static diagnostics for edited files returned no errors.
- Loading `.env.local` through `get_llm_config()` and `get_image_config()` now returns:
  - LLM: `doubao` / `doubao-seed-1-8-251228`
  - Image: `seedream` / `doubao-seedream-4-5-251128`
- Restarted local `ai-service` on port 8000.
- Runtime `/ai/health` now reports:
  - LLM: `doubao` / `doubao-seed-1-8-251228`
  - Image: `seedream` / `doubao-seedream-4-5-251128`
- After changing `.env.local` `LLM_API_KEY` from the GLM-style key to the ARK key, a direct `GlmClient.complete()` call succeeded with the Doubao text model.
