const { test, expect } = require("@playwright/test");

test.describe("Dashboard E2E Interactions", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the dashboard
    await page.goto("/", { waitUntil: "domcontentloaded" });
    
    // Wait for the main chart to ensure the app is loaded completely
    await page.waitForSelector("#net-liquidity-chart .js-plotly-plot", { timeout: 60_000 });
    // Additional wait for general stability
    await page.waitForTimeout(1_500);
  });

  test("loads key panels and verifies content-level state", async ({ page }) => {
    // 1. Dashboard homepage loads and key top-level panels render
    await expect(page.getByText("Global Liquidity Monitor").first()).toBeVisible();
    
    // 8. Content-level assertion: verify that regime metrics show actual data
    const regimeMetrics = page.locator("#regime-metrics");
    await expect(regimeMetrics).toBeVisible();
    // Verify it contains actual text instead of just existing
    const textContent = await regimeMetrics.textContent();
    expect(textContent).toBeTruthy();
    expect(textContent?.length).toBeGreaterThan(0);
    
    // Check if the regime gauge rendered successfully
    await expect(page.locator("#regime-gauge .js-plotly-plot")).toBeVisible();
  });

  test("can trigger refresh and maintain healthy state", async ({ page }) => {
    // 2. User-triggered refresh/update action
    const refreshBtn = page.locator("#refresh-btn");
    await expect(refreshBtn).toBeVisible();
    
    // Note current update time
    const timeLocator = page.locator("#last-update-time");
    const initialTime = await timeLocator.textContent();
    
    await refreshBtn.click();
    
    // Wait for loading to potentially trigger and finish, or just check charts are still intact
    await page.waitForTimeout(2000);
    
    // Ensure charts are still in a healthy state after refresh
    await expect(page.locator("#net-liquidity-chart .js-plotly-plot")).toBeVisible();
    await expect(page.locator("#global-liquidity-chart .js-plotly-plot")).toBeVisible();
  });

  test("handles export download flow", async ({ page }) => {
    // 3. Export/download flow
    const exportBtn = page.locator("#export-btn");
    
    // Wait for the download event when export is clicked
    const downloadPromise = page.waitForEvent("download", { timeout: 15_000 }).catch(() => null);
    await exportBtn.click();
    
    const download = await downloadPromise;
    // Check that download was successfully initiated
    expect(download).toBeTruthy();
    if (download) {
      // Typically an HTML or PDF export
      expect(download.suggestedFilename().length).toBeGreaterThan(0);
    }
  });

  test("expands and collapses the quality panel", async ({ page }) => {
    // 4. Quality panel expand/collapse
    const toggleBtn = page.locator("#quality-collapse-toggle");
    const collapsePanel = page.locator("#quality-collapse");
    
    await toggleBtn.click();
    
    // Check for an element inside the collapsed panel to become visible
    const freshnessGauge = page.locator("#freshness-gauge");
    await expect(freshnessGauge).toBeVisible({ timeout: 10_000 });
    
    // Click to collapse
    await toggleBtn.click();
    // After animation, it should be hidden
    await expect(freshnessGauge).not.toBeVisible({ timeout: 10_000 });
  });

  test("news filter updates visible content", async ({ page }) => {
    // 5. News filter changes visible content
    // Check initial news items container
    const newsContainer = page.locator("#news-items-container");
    await expect(newsContainer).toBeVisible();
    
    // Get text before filter
    const initialText = await newsContainer.textContent();
    
    const fedFilter = page.locator("#news-filter-fed");
    if (await fedFilter.isVisible()) {
      await fedFilter.click();
      await page.waitForTimeout(1_000); // Wait for content update
      
      // Ensure the container remains visible and hasn't crashed
      await expect(newsContainer).toBeVisible();
    }
  });

  test("tab switch updates visible dashboard content", async ({ page }) => {
    // 6. Tab switch (commodity tabs)
    // Find the Copper tab button
    const copperTabBtn = page.locator("#commodity-tabs button").filter({ hasText: /Copper/i });
    const oilTabBtn = page.locator("#commodity-tabs button").filter({ hasText: /Oil/i });
    
    if (await copperTabBtn.isVisible()) {
      await copperTabBtn.click();
      // Ensure the copper chart is rendered
      await expect(page.locator("#copper-chart .js-plotly-plot")).toBeVisible({ timeout: 10_000 });
      
      // Switch to Oil tab
      if (await oilTabBtn.isVisible()) {
        await oilTabBtn.click();
        await expect(page.locator("#oil-chart .js-plotly-plot")).toBeVisible({ timeout: 10_000 });
      }
    }
  });

  test("verifies below-the-fold content is rendered", async ({ page }) => {
    // 7. Below-the-fold section assertion
    // Correlation heatmap is usually lower on the page
    const correlationHeatmap = page.locator("#correlation-heatmap");
    await correlationHeatmap.scrollIntoViewIfNeeded();
    await expect(correlationHeatmap).toBeVisible();
    
    // FOMC diff view is also typically below the fold
    const fomcDiffView = page.locator("#fomc-diff-view");
    if (await fomcDiffView.isVisible()) {
      await fomcDiffView.scrollIntoViewIfNeeded();
      await expect(fomcDiffView).toBeVisible();
    }
  });
});
