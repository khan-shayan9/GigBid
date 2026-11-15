"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { DegradedBanner } from "@/components/DegradedBanner";
import { ErrorState, Loading } from "@/components/States";
import { api, ApiFailure, SIGNED_OUT_EVENT, unwrap, type Schemas } from "@/lib/client";

type SessionState = { session: Schemas["Session"]; refresh: () => Promise<void> };
const SessionContext = createContext<SessionState | null>(null);

export function useSession(): SessionState {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession outside AppShell");
  return value;
}

const NAV = [
  ["/inbox", "Inbox"],
  ["/pipeline", "Pipeline"],
  ["/messages", "Messages"],
  ["/analytics", "Analytics"],
  ["/settings", "Settings"],
] as const;
const PUBLIC = ["/login"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSession] = useState<Schemas["Session"]>();
  const [error, setError] = useState<unknown>();
  const isPublic = PUBLIC.includes(pathname);

  const refresh = useCallback(async () => {
    try {
      setSession(await unwrap(api.GET("/auth/session")));
      setError(undefined);
    } catch (failure) {
      if (failure instanceof ApiFailure && failure.status === 401) router.replace("/login");
      else setError(failure);
    }
  }, [router]);

  useEffect(() => {
    if (!isPublic) void refresh();
  }, [isPublic, refresh]);

  useEffect(() => {
    const signedOut = () => router.replace("/login");
    window.addEventListener(SIGNED_OUT_EVENT, signedOut);
    return () => window.removeEventListener(SIGNED_OUT_EVENT, signedOut);
  }, [router]);

  useEffect(() => {
    if (session && !session.profile.persona && pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [session, pathname, router]);

  if (isPublic) return <main className="mx-auto max-w-md px-4 py-10">{children}</main>;

  const signOut = async () => {
    await api.POST("/auth/logout");
    setSession(undefined);
    router.replace("/login");
  };

  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:p-2">
        Skip to content
      </a>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
          <Link href="/inbox" className="text-lg font-bold text-indigo-700">
            GigBid
          </Link>
          <nav aria-label="Main" className="order-last flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto sm:flex-1">
            {NAV.map(([href, label]) => (
              <Link
                key={href}
                href={href}
                aria-current={pathname.startsWith(href) ? "page" : undefined}
                className="whitespace-nowrap rounded px-2 py-1 text-sm hover:bg-slate-100 aria-[current=page]:bg-indigo-50 aria-[current=page]:font-semibold"
              >
                {label}
              </Link>
            ))}
          </nav>
          {session && (
            <div className="ml-auto flex items-center gap-2 text-sm text-slate-600">
              <span>
                {session.account}
                {session.profile.persona ? ` · ${session.profile.persona}` : ""}
              </span>
              <button type="button" onClick={signOut} className="btn-quiet">
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>
      <DegradedBanner />
      <main id="main" className="mx-auto max-w-6xl px-4 py-6">
        {error ? (
          <ErrorState error={error} retry={refresh} />
        ) : !session ? (
          <Loading what="your session" />
        ) : (
          <SessionContext.Provider value={{ session, refresh }}>{children}</SessionContext.Provider>
        )}
      </main>
    </>
  );
}
