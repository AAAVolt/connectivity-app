# Vercel environments — production vs preview

Vercel deploys the frontend in three contexts:

| Vercel environment | When | Should call |
|---|---|---|
| **Production** | Pushes to `main` (after merge) | Prod Cloud Run (`bizkaia-api`) |
| **Preview** | Every PR / non-main branch push | Staging Cloud Run (`bizkaia-api-staging`) |
| **Development** | `vercel dev` locally | Local backend on `localhost:8000` (or staging) |

The frontend never calls Cloud Run from the browser — every request goes through the Next.js proxy at `/api/backend/[...path]`, which reads `BACKEND_CLOUD_RUN_URL` server-side. So pointing previews at staging is one env-var change per environment, not a code change.

## One-time setup

In the Vercel project (`prj_gGjg2YQ9DvG3hgmKcOsSf0wUkTyU`):

1. **Settings → Environment Variables → Add**
2. For each environment, set `BACKEND_CLOUD_RUN_URL`:

   | Environment | Value |
   |---|---|
   | Production | `https://bizkaia-api-cos3esbs4a-no.a.run.app` |
   | Preview | `https://bizkaia-api-staging-<hash>-no.a.run.app` (look up after first staging deploy) |
   | Development | `http://localhost:8000` (or the staging URL — whichever you're testing against) |

3. Set `NEXT_PUBLIC_API_URL=/api/backend` for **all three** environments. The browser side never changes; only the proxy target does.

## After staging is live

```bash
# 1. Get the staging URL
STAGING_URL=$(gcloud run services describe bizkaia-api-staging \
  --region=europe-southwest1 --project=bizkaia-conn-staging \
  --format='value(status.url)')

# 2. Set it as a Vercel preview-environment var
vercel env add BACKEND_CLOUD_RUN_URL preview <<< "${STAGING_URL}"

# 3. Trigger a preview redeploy (push to any non-main branch, or:
vercel --env preview
```

After this, every PR's preview deployment automatically routes API traffic to staging. Production deploys keep pointing at prod.

## Verifying

Open a PR. The Vercel bot will comment with the preview URL. Visit `https://<preview-url>/api/backend/readiness` — the response should match staging's readiness payload, and Cloud Run logs should show traffic on `bizkaia-api-staging`, not `bizkaia-api`.

## Why this matters

Without it, every PR preview hits production. That means:

- Every `make loadtest` run, every `playwright test` against a preview, every `curl` from a teammate verifying a PR — all of it lands on prod traffic and prod logs.
- A PR that introduces a bad query has no chance to fail safely; it'll just degrade prod.
- The staging environment becomes pointless if no one's traffic actually hits it.

Once previews → staging, the runbook canary procedure becomes: PR → preview verifies on staging → merge → prod canary → 100%. That's the four-stage check the architecture has been designed for since Wave 5.
