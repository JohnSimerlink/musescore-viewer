import { expect, test } from "@playwright/test";

async function openFirstScore(page) {
  await page.goto("/");
  // Mobile: open library drawer if the Scores button is visible.
  const libraryBtn = page.locator("#libraryOpenBtn");
  if (await libraryBtn.isVisible()) {
    await libraryBtn.click();
  }
  const first = page.locator("#scoreList .score-item").first();
  await expect(first).toBeVisible({ timeout: 20_000 });
  await first.click();
  await expect(page.locator("#scoreWorkspace")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator("#pages svg").first()).toBeVisible({ timeout: 20_000 });
}

async function expectReply(page, pattern, timeout = 30_000) {
  await expect
    .poll(async () => (await page.locator("#commandReply").innerText()).trim(), { timeout })
    .toMatch(pattern);
}

test.describe("Copland smoke", () => {
  test("loads catalog and opens a score", async ({ page }) => {
    await openFirstScore(page);
    await expect(page.locator("#agentRail")).toBeVisible();
  });

  test("insert measure and undo", async ({ page }) => {
    await openFirstScore(page);
    await page.locator("#editToolsDetails").evaluate((el) => {
      el.open = true;
    });
    await page.locator('[data-edit="insert-measure"]').click();
    await expectReply(page, /inserted|applied|Done|measure/i);
    await page.locator('[data-edit="undo"]').click();
    await expectReply(page, /undo|applied|Done|restored/i);
  });

  test("version label and hop", async ({ page }) => {
    await openFirstScore(page);
    await page.locator("#editToolsDetails").evaluate((el) => {
      el.open = true;
    });
    await page.locator('[data-edit="insert-measure"]').click();
    await expectReply(page, /inserted|applied|Done|measure/i);
    await page.locator("#versionsDetails").evaluate((el) => {
      el.open = true;
    });
    await page.locator("#versionLabelInput").fill("playwright-v1");
    await page.locator("#versionLabelBtn").click();
    await expect(page.locator("#versionList")).toContainText("playwright-v1", { timeout: 20_000 });
    await page.locator('[data-edit="insert-measure"]').click();
    await expectReply(page, /inserted|applied|Done|measure/i);
    const hop = page
      .locator("#versionList button.version-hop:not([disabled])")
      .filter({ hasText: "playwright-v1" })
      .first();
    await hop.click();
    await expect(page.locator("#versionList .is-current")).toContainText(/playwright-v1|current/i, {
      timeout: 20_000,
    });
  });

  test("pitch keypad adds a note", async ({ page }) => {
    await openFirstScore(page);
    await page.locator("#inspectorDetails").evaluate((el) => {
      el.open = true;
    });
    await page.locator('#pitchKeypad [data-pitch="60"]').click();
    await expectReply(page, /Added note|applied|pitch/i);
  });
});

test.describe("Mobile shell", () => {
  test("library drawer and chat expand", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "mobile", "mobile project only");
    await page.goto("/");
    await expect(page.locator("#libraryOpenBtn")).toBeVisible();
    await page.locator("#libraryOpenBtn").click();
    await expect(page.locator("body")).toHaveClass(/library-open/);
    await page.locator("#libraryCloseBtn").click();
    await expect(page.locator("body")).not.toHaveClass(/library-open/);

    await openFirstScore(page);
    await expect(page.locator("#agentExpandBtn")).toBeVisible();
    await page.locator("#agentExpandBtn").click();
    await expect(page.locator("body")).toHaveClass(/agent-expanded/);
    await page.locator("#agentBackBtn").click();
    await expect(page.locator("body")).not.toHaveClass(/agent-expanded/);
  });
});
