/**
 * Capture step-wise project execution screenshots (light theme) for the report.
 */
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "docs", "report_assets");
const URL = process.env.RR_URL || "http://localhost:8020/?t=steps";

async function shot(page, name) {
  const file = path.join(OUT, name);
  await page.waitForTimeout(600);
  await page.screenshot({ path: file, fullPage: false });
  console.log("saved", name);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(URL, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForSelector("#pickup", { timeout: 30000 });
  await page.waitForFunction(() => {
    const s = document.getElementById("pickup");
    return s && s.options && s.options.length > 3;
  }, null, { timeout: 30000 });

  // Force light theme
  await page.evaluate(() => {
    document.documentElement.dataset.theme = "light";
    try { localStorage.setItem("rescueroute-theme", "light"); } catch {}
  });
  await page.waitForTimeout(400);

  // Reset demo if possible
  const resetBtn = page.locator("#reset-demo");
  if (await resetBtn.count()) {
    try { await resetBtn.click({ timeout: 2000 }); await page.waitForTimeout(800); } catch {}
  }

  // STEP 1 — console loaded
  await shot(page, "step01_console_loaded.png");

  // STEP 2 — select pickup neighborhood
  await page.selectOption("#pickup", { index: 5 }).catch(async () => {
    await page.selectOption("#pickup", "N55").catch(async () => {
      const val = await page.$eval("#pickup", (el) => el.options[Math.min(5, el.options.length - 1)].value);
      await page.selectOption("#pickup", val);
    });
  });
  await page.waitForTimeout(500);
  await shot(page, "step02_pickup_selected.png");

  // STEP 3 — set emergency params
  await page.selectOption("#emergency", "urgent").catch(() => {});
  await page.selectOption("#category", "general").catch(() => {});
  await page.check("#use-ml").catch(() => {});
  await shot(page, "step03_parameters_set.png");

  // STEP 4 — find route
  await page.click("#calculate");
  await page.waitForFunction(() => {
    const b = document.getElementById("dispatch");
    const bar = document.getElementById("trip-summary");
    return (b && !b.disabled) || (bar && /ETA|min|km|hospital/i.test(bar.textContent || ""));
  }, null, { timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await shot(page, "step04_route_calculated.png");

  // STEP 5 — scroll to suggested hospitals
  await page.locator("#top-hospitals").scrollIntoViewIfNeeded().catch(() => {});
  await shot(page, "step05_hospital_suggestions.png");

  // STEP 6 — dispatch
  const dispatch = page.locator("#dispatch");
  if (await dispatch.isEnabled()) {
    await dispatch.click();
    await page.waitForTimeout(2000);
  }
  await page.locator("#mission-card, .mission-card, #mission-summary").first().scrollIntoViewIfNeeded().catch(() => {});
  await shot(page, "step06_dispatch_active.png");

  // STEP 7 — GPS / next junction
  const feed = page.locator("#run-feed");
  if (await feed.isEnabled().catch(() => false)) {
    await feed.click().catch(() => {});
    await page.waitForTimeout(2500);
  } else {
    const next = page.locator("#next-step");
    if (await next.isEnabled().catch(() => false)) {
      await next.click().catch(() => {});
      await page.waitForTimeout(1200);
    }
  }
  await page.locator("#street-map").scrollIntoViewIfNeeded().catch(() => {});
  await shot(page, "step07_gps_progress.png");

  // STEP 8 — hospital board
  await page.click('button.nav[data-view="hospitals"]');
  await page.waitForTimeout(800);
  await shot(page, "step08_hospital_board.png");

  // STEP 9 — city directory
  await page.click('button.nav[data-view="directory"]');
  await page.waitForTimeout(1000);
  await shot(page, "step09_city_directory.png");

  // STEP 10 — algorithms & ML
  await page.click('button.nav[data-view="analysis"]');
  await page.waitForTimeout(1000);
  await shot(page, "step10_algorithms_ml.png");

  // STEP 11 — AWS architecture
  await page.click('button.nav[data-view="cloud"]');
  await page.waitForTimeout(800);
  await shot(page, "step11_aws_architecture.png");

  // STEP 12 — back to dispatch overview
  await page.click('button.nav[data-view="dispatch"]');
  await page.waitForTimeout(600);
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot(page, "step12_dispatch_overview.png");

  await browser.close();
  console.log("DONE");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
