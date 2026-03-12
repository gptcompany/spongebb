const { test, expect } = require("@playwright/test");

/**
 * Dashboard Semantic Health E2E Tests (Observer Pattern).
 * Validates that each panel reaches a healthy state with meaningful data
 * without requiring user interaction.
 */
test.describe("Dashboard Semantic Health", () => {
  test.setTimeout(120_000);

  const expectPlotlyReady = async (page, chartContainerSelector, timeout = 30_000) => {
    const plotly = page.locator(`${chartContainerSelector} .js-plotly-plot:visible`).first();
    await expect(plotly).toBeVisible({ timeout });
    await expect(plotly).not.toHaveClass(/dash-graph--pending/, { timeout });
  };

  test.beforeEach(async ({ page }) => {
    // Navigate to the dashboard with a forced wait for network to settle
    await page.goto("/", { waitUntil: "networkidle" });
    
    // Global indicator that the dashboard is ready
    await expect(page.locator("#net-liquidity-chart")).toBeVisible({ timeout: 60_000 });
  });

  test("News Intelligence: content presence", async ({ page }) => {
    const container = page.locator("#news-items-container");
    await container.scrollIntoViewIfNeeded();
    
    // Should transition from loading to data/empty state
    await expect(container).not.toContainText("Loading news...", { timeout: 30_000 });
    
    // Verify it's not a broken shell
    const text = await container.textContent();
    expect(text?.length).toBeGreaterThan(5);
  });

  test("FOMC Statement: panel structure", async ({ page }) => {
    const section = page.locator(".card").filter({ hasText: /FOMC Statement Comparison/i });
    await section.scrollIntoViewIfNeeded();
    await expect(section).toBeVisible();
    
    // Verify dropdowns are present and initialized
    await expect(page.locator("#fomc-date-1")).toBeVisible();
    await expect(page.locator("#fomc-date-2")).toBeVisible();
  });

  test("EIA Petroleum: chart and KPI health", async ({ page }) => {
    const section = page.locator(".card").filter({ hasText: /EIA Weekly Petroleum/i });
    await section.scrollIntoViewIfNeeded();
    
    await expectPlotlyReady(page, "#cushing-inventory-chart");
    
    // Check KPI badge has data (not the default "--")
    const badge = page.locator("#cushing-utilization-badge");
    await expect(badge).not.toContainText("--", { timeout: 15_000 });
  });

  test("Inflation Expectations: summary and chart", async ({ page }) => {
    const section = page.locator(".card").filter({ hasText: /Inflation Expectations/i });
    await section.scrollIntoViewIfNeeded();
    
    await expectPlotlyReady(page, "#real-rates-chart");
    
    const summary = page.locator("#inflation-summary");
    await expect(summary).not.toContainText("Data unavailable");
    await expect(summary).not.toBeEmpty();
  });

  test("Consumer Credit Risk: indicator health", async ({ page }) => {
    const section = page.locator(".card").filter({ hasText: /Consumer Credit Risk/i });
    await section.scrollIntoViewIfNeeded();
    
    await expectPlotlyReady(page, "#xlp-xly-ratio-chart");
    
    const metrics = page.locator("#consumer-credit-metrics");
    await expect(metrics).not.toBeEmpty();
  });

  test("Liquidity Regime: indicator and gauge", async ({ page }) => {
    const indicator = page.locator("#regime-indicator");
    await expect(indicator).toBeVisible();
    
    // Semantic check: must match one of our domain terms
    const text = await indicator.textContent();
    expect(text?.toUpperCase()).toMatch(/EXPANSION|CONTRACTION|STABLE|DEGRADED/);
    
    await expectPlotlyReady(page, "#regime-gauge");
  });
});
