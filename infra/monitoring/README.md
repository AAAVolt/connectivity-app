# Cloud Monitoring alert policies

This directory holds alert-policy specs for the `bizkaia-api` Cloud Run service. Each YAML maps 1:1 to a Cloud Monitoring alerting policy and is applied with `gcloud`.

These files are configuration-only. **Nothing is wired to a notification channel by default** — applying a policy without one means alerts fire silently. See *Setup* below.

## Setup (one-time)

1. **Create a notification channel** for the team. Email and Slack/PagerDuty/etc. are all supported.

   ```bash
   gcloud beta monitoring channels create \
     --display-name="Bizkaia on-call email" \
     --type=email \
     --channel-labels=email_address=team@laxi.ai \
     --project=bizkaia-conn-pub
   ```

   Capture the returned channel name (looks like `projects/bizkaia-conn-pub/notificationChannels/12345...`).

2. **Edit each policy YAML** in this directory and replace the `notificationChannels:` placeholder with the real channel name.

3. **Apply each policy:**

   ```bash
   for f in infra/monitoring/*.yaml; do
     gcloud alpha monitoring policies create --policy-from-file="${f}" --project=bizkaia-conn-pub
   done
   ```

4. **Verify in the console:** https://console.cloud.google.com/monitoring/alerting?project=bizkaia-conn-pub

## Policies

| File | What it watches | Threshold |
|---|---|---|
| `policy-5xx-rate.yaml` | Cloud Run 5xx response rate | > 1% over 5 min |
| `policy-p95-latency.yaml` | p95 request latency | > 2s over 5 min |
| `policy-instance-count.yaml` | Container instance count | > 4 (we cap at 5) for 10 min |
| `policy-readiness-failures.yaml` | /readiness 503s | any sustained 503 for 3 min |

## Updating

After editing a policy file, re-apply with:

```bash
# Find the policy ID
gcloud alpha monitoring policies list --project=bizkaia-conn-pub \
  --format='value(name, displayName)'

# Update
gcloud alpha monitoring policies update <POLICY_ID> \
  --policy-from-file=infra/monitoring/policy-5xx-rate.yaml \
  --project=bizkaia-conn-pub
```
