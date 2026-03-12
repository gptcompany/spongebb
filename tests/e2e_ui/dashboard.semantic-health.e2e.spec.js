const { test, expect } = require("@playwright/test");

/**
 * Dashboard Semantic Health E2E Tests (Non-Interactive).
 * Validates that each panel renders and reaches a stable state (ok or degraded).
 * Avoids simulations of clicks or complex workflows to maintain stability.
 */
test.describe("Dashboard Semantic Health", () => {
  // Increase timeout for complex dashboard loading
  test.setTimeout(120_000);

  test.beforeEach(async ({ page }) => {
    // Navigate to the dashboard
    await page.goto("/", { waitUntil: "networkidle" });

    // Stable readiness gate: primary chart must be visible and rendered.
    // Generic ".js-plotly-plot:not(.dash-graph--pending)" is flaky due to hidden tab graphs.
    const primaryChart = page.locator("#net-liquidity-chart .js-plotly-plot");
    await expect(page.locator("#net-liquidity-chart")).toBeVisible({ timeout: 60_000 });
    await expect(primaryChart).toBeVisible({ timeout: 60_000 });
    await expect(primaryChart).not.toHaveClass(/dash-graph--pending/, { timeout: 60_000 });
  });

  test("Central Bank News panel health", async ({ page }) => {
    const container = page.locator("#news-items-container");
    await expect(container).toBeVisible();
    
    // Clear loading state
    await expect(container).not.toContainText("Loading news...", { timeout: 30_000 });
    
    // Verify it's either showing news items or an explicit "No news" message
    const newsItems = container.locator(".news-item");
    const count = await newsItems.count();
    const text = await container.textContent();
    
    expect(count > 0 || /no news|news unavailable/i.test(text || "")).toBeTruthy();
  });

  test("FOMC Comparison panel structure", async ({ page }) => {
    const fomcSection = page.locator(".card").filter({ hasText: /FOMC Statement Comparison/i });
    await expect(fomcSection).toBeVisible();
    
    // Verify selectors exist
    const date1 = page.locator("#fomc-date-1");
    const date2 = page.locator("#fomc-date-2");
    await expect(date1).toBeVisible();
    await expect(date2).toBeVisible();
    
    // In fallback mode, dropdowns should be populated
    // We check for the presence of the placeholder or value
    const text1 = await date1.textContent();
    expect(text1).toBeTruthy();
  });

  test("EIA Petroleum panel health", async ({ page }) => {
    const cushingChart = page.locator("#cushing-inventory-chart");
    await expect(cushingChart).toBeVisible();
    
    // Wait for Plotly to render if it's not pending
    const chart = cushingChart.locator(".js-plotly-plot");
    if (await chart.isVisible()) {
        await expect(chart).not.toHaveClass(/dash-graph--pending/, { timeout: 30_000 });
    }
    
    // KPI badges
    const badge = page.locator("#cushing-utilization-badge");
    await expect(badge).toBeVisible();
    // Should not be empty or showing the default "--" if data was found
    // In fallback it should have data
    const badgeText = await badge.textContent();
    expect(badgeText).not.toBe("");
  });

  test("Inflation Expectations panel health", async ({ page }) => {
    const chart = page.locator("#real-rates-chart");
    await expect(chart).toBeVisible();
    await expect(chart.locator(".js-plotly-plot")).not.toHaveClass(/dash-graph--pending/, { timeout: 30_000 });
    
    const summary = page.locator("#inflation-summary");
    await expect(summary).toBeVisible();
    await expect(summary).not.toContainText("Data unavailable");
  });

  test("Consumer Credit Risk panel health", async ({ page }) => {
    const chart = page.locator("#xlp-xly-ratio-chart");
    await expect(chart).toBeVisible();
    await expect(chart.locator(".js-plotly-plot")).not.toHaveClass(/dash-graph--pending/, { timeout: 30_000 });
    
    const metrics = page.locator("#consumer-credit-metrics");
    await expect(metrics).toBeVisible();
    await expect(metrics).not.toBeEmpty();
  });

  test("Liquidity Regime semantic health", async ({ page }) => {
    const indicator = page.locator("#regime-indicator");
    await expect(indicator).toBeVisible();
    const indicatorText = await indicator.textContent();
    // Should be one of the known states
    expect(indicatorText?.toUpperCase()).toMatch(/EXPANSION|CONTRACTION|STABLE|DEGRADED/);
    
    const gauge = page.locator("#regime-gauge");
    await expect(gauge).toBeVisible();
    await expect(gauge.locator(".js-plotly-plot")).not.toHaveClass(/dash-graph--pending/, { timeout: 30_000 });
    
    const metrics = page.locator("#regime-metrics");
    await expect(metrics).toBeVisible();
    await expect(metrics).toContainText("Net Liquidity");
  });
});
