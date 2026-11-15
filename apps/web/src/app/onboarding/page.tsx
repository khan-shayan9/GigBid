"use client";

import { useRouter } from "next/navigation";
import { useSession } from "@/components/AppShell";
import { Connections, PortfolioUpload } from "@/components/Connections";
import { ProfileForm } from "@/components/ProfileForm";

export default function OnboardingPage() {
  const router = useRouter();
  const { session } = useSession();
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1>Set up GigBid</h1>
      <section className="card" aria-labelledby="profile-heading">
        <h2 id="profile-heading">1. Profile, rates and searches</h2>
        <ProfileForm submitLabel="Save profile" onSaved={() => undefined} />
      </section>
      {session.profile.persona && (
        <>
          <section className="card" aria-labelledby="connect-heading">
            <h2 id="connect-heading">2. Marketplace</h2>
            <Connections />
          </section>
          <section className="card" aria-labelledby="portfolio-heading">
            <h2 id="portfolio-heading">3. Portfolio</h2>
            <PortfolioUpload />
          </section>
          <button type="button" className="btn-primary" onClick={() => router.push("/inbox")}>
            Continue to inbox
          </button>
        </>
      )}
    </div>
  );
}
