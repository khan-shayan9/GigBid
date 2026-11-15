import { expect, type Page } from "@playwright/test";

const API = "http://127.0.0.1:8010";

export async function resetBackend(page: Page): Promise<void> {
  await page.request.post(`${API}/__test__/reset`);
}

export async function setMarketplace(page: Page, down: boolean, slowSeconds = 0): Promise<void> {
  await page.request.post(`${API}/__test__/marketplace?down=${down}&slow=${slowSeconds}`);
}

export async function signIn(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Username").fill("reviewer");
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Signed in with a persona chosen, without going through the onboarding screen. */
export async function signInOnboarded(page: Page): Promise<void> {
  await signIn(page);
  await expect(page).toHaveURL(/onboarding/);
  const saved = await page.request.put("/api/profile", { data: { persona: "ai_ml_engineer" } });
  expect(saved.ok()).toBeTruthy();
}

/** Analyse the clinic job from the inbox and open its draft in the proposal studio. */
export async function openClinicDraft(page: Page): Promise<void> {
  await page.goto("/inbox");
  await page.getByTestId("job-job-clinic").getByRole("button", { name: "Analyse" }).click();
  await expect(page.getByRole("heading", { name: "Clinic FAQ chatbot" })).toBeVisible();
  await page.getByRole("link", { name: "Review the proposal" }).click();
  await expect(page.getByRole("heading", { name: "Proposal: Clinic FAQ chatbot" })).toBeVisible();
}

/** The page fits the viewport width: nothing scrolls sideways (phone layout). */
export async function expectNoSideScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}
