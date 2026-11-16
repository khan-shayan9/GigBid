import { expect, test } from "@playwright/test";
import { expectNoSideScroll, openClinicDraft, resetBackend, setMarketplace, signIn, signInOnboarded } from "./helpers";

test.beforeEach(async ({ page }) => {
  await resetBackend(page);
});

test("onboarding: sign in, choose a persona, set budgets, see the marketplace", async ({ page }) => {
  await signIn(page);
  await expect(page).toHaveURL(/onboarding/);
  await page.getByLabel("ai ml engineer").check();
  await page.getByLabel("Weekly Connects budget").fill("40");
  await page.getByLabel(/Saved searches/).fill("chatbot");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByText("connected · 120 Connects")).toBeVisible();
  await page.getByRole("button", { name: "Continue to inbox" }).click();
  // The saved search filters the inbox to the chatbot job.
  await expect(page.getByTestId("job-job-clinic")).toBeVisible();
  await expect(page.getByTestId("job-job-dash")).toHaveCount(0);
  await expectNoSideScroll(page);
});

test("approving a proposal submits it once, and a refresh keeps the pending approval", async ({ page }) => {
  await signInOnboarded(page);
  await openClinicDraft(page);
  // Every claim shows its evidence on hover or keyboard focus.
  await page.getByRole("button", { name: "ai-cs-01" }).first().focus();
  await expect(page.getByRole("tooltip").getByText("MedAssist")).toBeVisible();
  await expect(page.getByText("Connects cost")).toBeVisible();
  await expectNoSideScroll(page);
  await page.reload();
  await expect(page.getByRole("button", { name: "Approve and send" })).toBeVisible();
  await page.getByRole("button", { name: "Approve and send" }).click();
  await expect(page.getByText("Submitted. 4 Connects spent; 116 left.")).toBeVisible();
  await page.getByRole("link", { name: "Pipeline" }).click();
  await expect(page.getByRole("region", { name: "Submitted" }).getByText("Clinic FAQ chatbot")).toBeVisible();
});

test("rejecting with a reason sends nothing and records the reason", async ({ page }) => {
  await signInOnboarded(page);
  await openClinicDraft(page);
  await page.getByRole("button", { name: "Reject…" }).click();
  await page.getByLabel(/Reason/).fill("rate too low");
  await page.getByRole("button", { name: "Confirm rejection" }).click();
  await expect(page.getByText("Rejected. Nothing was sent. Reason: rate too low")).toBeVisible();
  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByText("rate too low (1)")).toBeVisible();
});

test("editing a draft: regenerate a paragraph, edit, approve with edits", async ({ page }) => {
  await signInOnboarded(page);
  await openClinicDraft(page);
  await page.getByRole("button", { name: "Regenerate this paragraph" }).first().click();
  const editor = page.getByLabel("Edit the cover letter");
  await expect(editor).toHaveValue(/I built exactly that \[ai-cs-01\]/);
  await editor.fill(`${await editor.inputValue()}\n\nI can start on Monday.`);
  await page.getByRole("button", { name: "Approve with my edits" }).click();
  await expect(page.getByText(/^Submitted\./)).toBeVisible();
  await expect(page.getByText("I can start on Monday.")).toBeVisible();
});

test("degraded mode: the marketplace-unavailable banner shows, then clears", async ({ page }) => {
  await signInOnboarded(page);
  await setMarketplace(page, true);
  await page.goto("/inbox");
  await expect(page.getByRole("alert").filter({ hasText: "Marketplace unavailable." })).toBeVisible();
  await setMarketplace(page, false);
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByTestId("job-job-clinic")).toBeVisible();
  await expect(page.getByText("Marketplace unavailable.")).toHaveCount(0);
});

test("a client reply is suggested with interview slots and sent after approval", async ({ page }) => {
  await signInOnboarded(page);
  await page.goto("/messages");
  await page.getByRole("button", { name: "Suggest a reply" }).click();
  await expect(page.getByText("Interview slots offered:")).toBeVisible();
  await expect(page.getByLabel("Suggested reply")).toHaveValue("Happy to talk. Tuesday 10:00 works for me.");
  await page.getByRole("button", { name: "Approve and send" }).click();
  await expect(page.getByText("freelancer", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("Reply approved.")).toBeVisible();
});

test("a scam post is flagged and recommended for skipping", async ({ page }) => {
  await signInOnboarded(page);
  await page.goto("/inbox");
  await page.getByTestId("job-job-scam").getByRole("button", { name: "Analyse" }).click();
  await expect(page.getByText("Recommended: skip")).toBeVisible();
  await expect(page.getByText(/injected instructions/).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Review the proposal" })).toHaveCount(0);
});

test("the run viewer streams progress node by node while the agents work", async ({ page }) => {
  test.setTimeout(60_000);
  await signInOnboarded(page);
  await setMarketplace(page, false, 3); // each evidence search takes 3 s: a run of ~20 s
  await page.goto("/inbox");
  await page.getByTestId("job-job-clinic").getByRole("button", { name: "Analyse" }).click();
  await page.getByRole("link", { name: "Run viewer" }).click();
  // Nodes appear one by one over the SSE stream, before the run reaches the approval.
  await expect(page.getByText("decision finished")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("region", { name: "Live" }).getByText("working…")).toBeVisible();
  await expect(page.getByText("paused: waiting for your approval")).toBeVisible({ timeout: 40_000 });
});

test("the pipeline board moves a card live when an approval elsewhere submits it", async ({ page }) => {
  await signInOnboarded(page);
  await openClinicDraft(page);
  await page.getByRole("link", { name: "Pipeline" }).click();
  await expect(page.getByRole("region", { name: "Awaiting approval" }).getByText("Clinic FAQ chatbot")).toBeVisible();
  // Approved from another tab or device: this board is not reloaded by hand.
  const thread = encodeURIComponent("reviewer:bid:job-clinic");
  expect((await page.request.post(`/api/runs/${thread}/resume`, { data: { action: "approve" } })).status()).toBe(202);
  await expect(page.getByRole("region", { name: "Submitted" }).getByText("Clinic FAQ chatbot")).toBeVisible();
});
