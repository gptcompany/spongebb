const { test, expect } = require("@playwright/test");

async function waitForDashboardReady(page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });

  await expect(page.getByText("Global Liquidity Monitor").first()).toBeVisible();
  await page.waitForSelector("#net-liquidity-chart .js-plotly-plot", { timeout: 60_000 });
  await page.waitForSelector("#global-liquidity-chart .js-plotly-plot", { timeout: 60_000 });
  await page.waitForTimeout(1_500);
}

test("dashboard above-the-fold visual regression", async ({ page }) => {
  await waitForDashboardReady(page);

  await expect(page).toHaveScreenshot("dashboard-above-fold.png", {
    animations: "disabled",
    maxDiffPixelRatio: 0.02
  });
});
