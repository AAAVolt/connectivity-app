import { NextRequest, NextResponse } from "next/server";

const CLOUD_RUN_URL = process.env.BACKEND_CLOUD_RUN_URL!;
const WIF_PROVIDER =
  "projects/254096570009/locations/global/workloadIdentityPools/vercel-pool/providers/vercel-provider";
const SERVICE_ACCOUNT = "bizkaia-backend@laxi-ai.iam.gserviceaccount.com";

async function getIdToken(): Promise<string | null> {
  // VERCEL_OIDC_TOKEN is injected automatically when "OpenID Connect" is enabled
  // in the Vercel project settings.
  const oidcToken = process.env.VERCEL_OIDC_TOKEN;
  if (!oidcToken) return null;

  try {
    // Step 1 – exchange Vercel OIDC token for a GCP STS token
    const stsRes = await fetch("https://sts.googleapis.com/v1/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        grantType: "urn:ietf:params:oauth:grant-type:token-exchange",
        audience: `//iam.googleapis.com/${WIF_PROVIDER}`,
        scope: "https://www.googleapis.com/auth/cloud-platform",
        requestedTokenType: "urn:ietf:params:oauth:token-type:access_token",
        subjectTokenType: "urn:ietf:params:oauth:token-type:jwt",
        subjectToken: oidcToken,
      }),
    });
    if (!stsRes.ok) {
      console.error("[proxy] STS exchange failed", await stsRes.text());
      return null;
    }
    const { access_token } = await stsRes.json();

    // Step 2 – impersonate SA to get a Cloud Run ID token
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
    if (!iamRes.ok) {
      console.error("[proxy] generateIdToken failed", await iamRes.text());
      return null;
    }
    const { token } = await iamRes.json();
    return token as string;
  } catch (err) {
    console.error("[proxy] getIdToken error", err);
    return null;
  }
}

async function proxy(req: NextRequest, path: string): Promise<NextResponse> {
  const targetUrl = `${CLOUD_RUN_URL}/${path}${req.nextUrl.search}`;

  const forwardHeaders: Record<string, string> = {};
  const contentType = req.headers.get("Content-Type");
  if (contentType) forwardHeaders["Content-Type"] = contentType;

  // Forward tenant header required by the backend
  const tenantId = req.headers.get("X-Tenant-ID");
  if (tenantId) forwardHeaders["X-Tenant-ID"] = tenantId;

  // User's app JWT → X-App-Token (Cloud Run IAM needs Authorization for itself)
  const userJwt = req.headers.get("Authorization");
  if (userJwt) forwardHeaders["X-App-Token"] = userJwt;

  const idToken = await getIdToken();
  if (idToken) {
    forwardHeaders["Authorization"] = `Bearer ${idToken}`;
  } else if (userJwt) {
    // Local dev: no WIF available, forward JWT directly
    forwardHeaders["Authorization"] = userJwt;
  }

  const body =
    req.method !== "GET" && req.method !== "HEAD"
      ? await req.arrayBuffer()
      : undefined;

  let upstream: Response;
  try {
    upstream = await fetch(targetUrl, {
      method: req.method,
      headers: forwardHeaders,
      body: body ? Buffer.from(body) : undefined,
    });
  } catch (err) {
    console.error("[proxy] upstream fetch failed", err);
    return NextResponse.json({ detail: "Backend unreachable" }, { status: 502 });
  }

  const resHeaders = new Headers();
  upstream.headers.forEach((v, k) => {
    if (!["transfer-encoding", "connection"].includes(k.toLowerCase()))
      resHeaders.set(k, v);
  });

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: resHeaders,
  });
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(req, (await params).path.join("/"));
}
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(req, (await params).path.join("/"));
}
export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(req, (await params).path.join("/"));
}
export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(req, (await params).path.join("/"));
}
