import { NextResponse } from "next/server";

const WIF_PROVIDER =
  "projects/254096570009/locations/global/workloadIdentityPools/vercel-pool/providers/vercel-provider";
const SERVICE_ACCOUNT = "bizkaia-backend@laxi-ai.iam.gserviceaccount.com";
const CLOUD_RUN_URL = process.env.BACKEND_CLOUD_RUN_URL ?? "";

export async function GET() {
  const oidcToken = process.env.VERCEL_OIDC_TOKEN;

  const result: Record<string, unknown> = {
    has_oidc_token: !!oidcToken,
    oidc_token_length: oidcToken?.length ?? 0,
    backend_url_set: !!CLOUD_RUN_URL,
  };

  if (!oidcToken) return NextResponse.json(result);

  // STS exchange
  const stsRes = await fetch("https://sts.googleapis.com/v1/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      grant_type: "urn:ietf:params:oauth:grant-type:token-exchange",
      audience: `//iam.googleapis.com/${WIF_PROVIDER}`,
      scope: "https://www.googleapis.com/auth/cloud-platform",
      requested_token_type: "urn:ietf:params:oauth:token-type:access_token",
      subject_token_type: "urn:ietf:params:oauth:token-type:jwt",
      subject_token: oidcToken,
    }),
  });

  const stsBody = await stsRes.json();
  result.sts_status = stsRes.status;
  result.sts_ok = stsRes.ok;
  if (!stsRes.ok) {
    result.sts_error = stsBody;
    return NextResponse.json(result);
  }

  const { access_token } = stsBody;
  result.has_access_token = !!access_token;

  // generateIdToken
  const iamRes = await fetch(
    `https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${SERVICE_ACCOUNT}:generateIdToken`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ audience: CLOUD_RUN_URL, includeEmail: true }),
    }
  );

  const iamBody = await iamRes.json();
  result.iam_status = iamRes.status;
  result.iam_ok = iamRes.ok;
  if (!iamRes.ok) result.iam_error = iamBody;
  else result.has_id_token = !!(iamBody as { token?: string }).token;

  return NextResponse.json(result);
}
