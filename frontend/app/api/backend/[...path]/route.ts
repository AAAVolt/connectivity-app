import { NextRequest, NextResponse } from "next/server";

const CLOUD_RUN_URL = process.env.BACKEND_CLOUD_RUN_URL!;

async function proxy(req: NextRequest, path: string): Promise<NextResponse> {
  const targetUrl = `${CLOUD_RUN_URL}/${path}${req.nextUrl.search}`;

  const forwardHeaders: Record<string, string> = {};
  const contentType = req.headers.get("Content-Type");
  if (contentType) forwardHeaders["Content-Type"] = contentType;

  const tenantId = req.headers.get("X-Tenant-ID");
  if (tenantId) forwardHeaders["X-Tenant-ID"] = tenantId;

  const auth = req.headers.get("Authorization");
  if (auth) forwardHeaders["Authorization"] = auth;

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
  const skipHeaders = ["transfer-encoding", "connection", "content-length", "content-encoding"];
  upstream.headers.forEach((v, k) => {
    if (!skipHeaders.includes(k.toLowerCase())) resHeaders.set(k, v);
  });

  // Buffer the body so Next.js can set content-length correctly
  const resBody = await upstream.arrayBuffer();

  return new NextResponse(resBody, {
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
