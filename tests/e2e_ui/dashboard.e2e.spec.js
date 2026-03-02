const { test, expect } = require("@playwright/test");

test.describe("Dashboard E2E Interactions", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the dashboard
    await page.goto("/", { waitUntil: "domcontentloaded" });
    
    // Wait for the main chart to ensure the app is loaded completely
    await page.waitForSelector("#net-liquidity-chart .js-plotly-plot", { timeout: 60_000 });
  });

  test("loads key panels and verifies content-level state", async ({ page }) => {
    // 1. Dashboard homepage loads and key top-level panels render
    await expect(page.getByText("Global Liquidity Monitor").first()).toBeVisible();
    
    // 8. Content-level assertion: verify that regime metrics show actual data
    const regimeMetrics = page.locator("#regime-metrics");
    await expect(regimeMetrics).toBeVisible();
    // Verify it contains actual text instead of just existing
    await expect(regimeMetrics).not.toBeEmpty();
    
    // Check if the regime gauge rendered successfully
    await expect(page.locator("#regime-gauge .js-plotly-plot")).toBeVisible();
  });

  test("can trigger refresh and maintain healthy state", async ({ page }) => {
    // 2. User-triggered refresh/update action
    const refreshBtn = page.locator("#refresh-btn");
    await expect(refreshBtn).toBeVisible();
    
    // Click refresh
    await refreshBtn.click();
    
    // Ensure charts are still in a healthy state after refresh
    await expect(page.locator("#net-liquidity-chart .js-plotly-plot")).toBeVisible();
    await expect(page.locator("#global-liquidity-chart .js-plotly-plot")).toBeVisible();
  });

  test("handles export download flow", async ({ page }) => {
    // 3. Export/download flow
    const exportBtn = page.locator("#export-btn");
    await expect(exportBtn).toBeVisible();
    
    // Wait for the download event when export is clicked
    const downloadPromise = page.waitForEvent("download", { timeout: 15_000 });
    await exportBtn.click();
    
    const download = await downloadPromise;
    expect(download).toBeTruthy();
    expect(download.suggestedFilename().length).toBeGreaterThan(0);
  });

  test("expands and collapses the quality panel", async ({ page }) => {
    // 4. Quality panel expand/collapse
    const toggleBtn = page.locator("#quality-collapse-toggle");
    await expect(toggleBtn).toBeVisible();
    
    const freshnessGauge = page.locator("#freshness-gauge");
    
    // Click to expand
    await toggleBtn.click();
    
    // Wait for visibility instead of sleep
    await expect(freshnessGauge).toBeVisible();
    
    // Click to collapse
    await toggleBtn.click();
    
    // Wait for hidden state
    await expect(freshnessGauge).toBeHidden();
  });

  test("news filter updates visible content", async ({ page }) => {
    // 5. News filter changes visible content
    const newsContainer = page.locator("#news-items-container");
    await expect(newsContainer).toBeVisible();
    
    // Initially it might be "Loading news..."
    const initialText = await newsContainer.textContent();
    
    const fedFilter = page.locator("#news-filter-fed");
    await expect(fedFilter).toBeVisible();
    
    await fedFilter.click();
    
    // Wait for the content to change from "Loading news..."
    // In fallback mode, it likely goes to "No news available" or "No FED news available"
    await expect(async () => {
      const currentText = await newsContainer.textContent();
      expect(currentText).not.toContain("Loading news...");
    }).toPass({ timeout: 10_000 });
    
    await expect(newsContainer).toBeVisible();
  });

  test("tab switch updates visible dashboard content", async ({ page }) => {
    // 6. Tab switch (commodity tabs)
    // Use a more robust selector for tabs text
    const copperTabBtn = page.locator("#commodity-tabs .nav-link").filter({ hasText: /Copper/i });
    const oilTabBtn = page.locator("#commodity-tabs .nav-link").filter({ hasText: /Oil/i });
    
    await expect(copperTabBtn).toBeVisible();
    await expect(oilTabBtn).toBeVisible();

    // Switch to Copper tab
    await copperTabBtn.click();
    await expect(page.locator("#copper-chart .js-plotly-plot")).toBeVisible();
    
    // Switch to Oil tab
    await oilTabBtn.click();
    await expect(page.locator("#oil-chart .js-plotly-plot")).toBeVisible();
  });

  test("verifies below-the-fold content is rendered", async ({ page }) => {
    // 7. Below-the-fold section assertion
    const correlationHeatmap = page.locator("#correlation-heatmap");
    await correlationHeatmap.scrollIntoViewIfNeeded();
    await expect(correlationHeatmap).toBeVisible();
    
    const fomcDiffView = page.locator("#fomc-diff-view");
    await expect(fomcDiffView).toBeVisible();
    await fomcDiffView.scrollIntoViewIfNeeded();
  });
});
