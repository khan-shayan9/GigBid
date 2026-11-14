// source: synthetic · persona: fullstack_dev · repo: next-saas-starter
import { NextResponse, type NextRequest } from "next/server";
import { readSession } from "./lib/session";

export async function middleware(request: NextRequest) {
  const session = await readSession(request);
  if (!session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  const headers = new Headers(request.headers);
  headers.set("x-team-id", session.teamId);
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: ["/app/:path*", "/api/:path*"] };
