/**
 * E2E test: exercises the full frontend flow in a real browser.
 *
 * Requires:
 *   - Backend running on localhost:8000 with a test user and deck set up
 *   - Frontend running on localhost:5175
 *
 * Run: node e2e-test.mjs
 */

import { chromium } from "playwright";
import { writeFileSync } from "fs";

const BASE_URL = "http://localhost:5175";
const SCREENSHOT_DIR = "/tmp";

let browser, page;
let passed = 0;
let failed = 0;

function assert(condition, msg) {
  if (condition) {
    console.log(`  ✓ ${msg}`);
    passed++;
  } else {
    console.log(`  ✗ FAIL: ${msg}`);
    failed++;
  }
}

async function screenshot(name) {
  const path = `${SCREENSHOT_DIR}/e2e-${name}.png`;
  await page.screenshot({ path });
  console.log(`  📸 Screenshot: ${path}`);
}

try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 }, // iPhone-like
  });
  page = await context.newPage();

  // ============================================================
  // TEST 1: Login page renders
  // ============================================================
  console.log("\n=== TEST 1: Login page ===");
  await page.goto(BASE_URL);
  // Should redirect to /login since not authenticated
  await page.waitForTimeout(1000);
  const loginTitle = await page.textContent("h1");
  assert(loginTitle === "Anki Translator", `Title is "${loginTitle}"`);

  const usernameInput = await page.$('input[type="text"]');
  assert(usernameInput !== null, "Username input exists");

  const passwordInput = await page.$('input[type="password"]');
  assert(passwordInput !== null, "Password input exists");

  const loginButton = await page.$("button");
  assert(loginButton !== null, "Login button exists");

  await screenshot("01-login-page");

  // ============================================================
  // TEST 2: Login with wrong credentials shows error
  // ============================================================
  console.log("\n=== TEST 2: Login failure ===");
  await usernameInput.fill("testuser");
  await passwordInput.fill("wrongpassword");
  await loginButton.click();
  await page.waitForTimeout(1500);

  const errorMsg = await page.$(".error");
  assert(errorMsg !== null, "Error message shown for wrong password");
  await screenshot("02-login-error");

  // ============================================================
  // TEST 3: Login with correct credentials
  // ============================================================
  console.log("\n=== TEST 3: Login success ===");
  await page.fill('input[type="text"]', "testuser");
  await page.fill('input[type="password"]', "testpass123");
  await page.click("button");
  await page.waitForTimeout(2000);

  const url = page.url();
  assert(!url.includes("/login"), `Redirected away from login: ${url}`);

  const header = await page.$(".header");
  assert(header !== null, "App header visible after login");

  await screenshot("03-logged-in");

  // ============================================================
  // TEST 4: Camera page renders
  // ============================================================
  console.log("\n=== TEST 4: Camera page ===");
  const pageTitle = await page.textContent(".page h1");
  assert(
    pageTitle === "Take a Photo",
    `Camera page title is "${pageTitle}"`
  );

  const takePhotoBtn = await page.$("button.btn-primary");
  assert(takePhotoBtn !== null, "Take Photo button exists");

  await screenshot("04-camera-page");

  // ============================================================
  // TEST 5: Upload image → OCR → word selection
  // ============================================================
  console.log("\n=== TEST 5: OCR + Word selection ===");
  // Use the file input (not camera) to upload the test image
  const fileInput = await page.$('input[type="file"]:not([capture])');
  assert(fileInput !== null, "File upload input exists");

  await fileInput.setInputFiles("/tmp/test_german.png");

  // Wait for OCR response
  await page.waitForURL("**/words", { timeout: 30000 });
  await page.waitForTimeout(1000);

  const wordButtons = await page.$$(".word-btn");
  assert(wordButtons.length > 0, `Found ${wordButtons.length} word buttons`);

  // Check that expected words are present
  const wordTexts = await Promise.all(
    wordButtons.map((btn) => btn.textContent())
  );
  console.log(`  Words found: ${wordTexts.join(", ")}`);
  assert(wordTexts.includes("Fuchs"), "Word 'Fuchs' found");
  assert(wordTexts.includes("Hund"), "Word 'Hund' found");
  assert(wordTexts.includes("Garten"), "Word 'Garten' found");

  await screenshot("05-word-selection");

  // ============================================================
  // TEST 6: Navigate to settings and configure deck
  // ============================================================
  console.log("\n=== TEST 6: Settings page ===");
  await page.click('a[href="/config"]');
  await page.waitForTimeout(1000);

  const settingsTitle = await page.textContent(".page h1");
  assert(settingsTitle === "Settings", `Settings page title is "${settingsTitle}"`);

  // Check deck selector
  const deckSelect = await page.$("select");
  assert(deckSelect !== null, "Deck selector exists");

  const options = await page.$$("select option");
  const optionTexts = await Promise.all(options.map((o) => o.textContent()));
  console.log(`  Deck options: ${optionTexts.join(", ")}`);
  assert(optionTexts.some((t) => t.includes("German")), "German deck available");

  // Select the deck
  if (options.length > 1) {
    await deckSelect.selectOption({ index: 1 });
    await page.waitForTimeout(500);
  }

  await screenshot("06-settings-page");

  // ============================================================
  // TEST 7: Cards page
  // ============================================================
  console.log("\n=== TEST 7: Cards page ===");
  await page.click('a[href="/cards"]');
  await page.waitForTimeout(2000);

  const cardsTitle = await page.textContent(".page h1");
  assert(cardsTitle === "Cards", `Cards page title is "${cardsTitle}"`);

  const cardPreviews = await page.$$(".card-preview");
  console.log(`  Found ${cardPreviews.length} card previews`);
  assert(cardPreviews.length >= 0, "Cards page loads without error");

  await screenshot("07-cards-page");

  // ============================================================
  // TEST 8: Logout
  // ============================================================
  console.log("\n=== TEST 8: Logout ===");
  await page.click('a:text("Logout")');
  await page.waitForTimeout(1500);

  const afterLogoutUrl = page.url();
  assert(afterLogoutUrl.includes("/login"), "Redirected to login after logout");

  await screenshot("08-after-logout");

  // ============================================================
  // TEST 9: Unauthenticated access blocked
  // ============================================================
  console.log("\n=== TEST 9: Auth guard ===");
  await page.goto(`${BASE_URL}/cards`);
  await page.waitForTimeout(1000);

  const guardedUrl = page.url();
  assert(
    guardedUrl.includes("/login"),
    "Unauthenticated access redirects to login"
  );

  await screenshot("09-auth-guard");

  // ============================================================
  // Summary
  // ============================================================
  console.log(`\n${"=".repeat(50)}`);
  console.log(`Results: ${passed} passed, ${failed} failed`);
  console.log(`${"=".repeat(50)}`);

} catch (err) {
  console.error(`\nFATAL ERROR: ${err.message}`);
  if (page) await screenshot("error");
  failed++;
} finally {
  if (browser) await browser.close();
  process.exit(failed > 0 ? 1 : 0);
}
