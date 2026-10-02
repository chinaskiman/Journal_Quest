/**
 * Capture full-page screenshots of every Trade Quest v2 screen.
 *
 * Uses playwright-core with the locally installed Chrome (no browser
 * download).  Run the backend first (the built SPA is served from it):
 *
 *   $env:TRADEQUEST2_DB="data/tradequest_v2_demo.db"   # optional demo data
 *   backend\.venv\Scripts\python -m uvicorn app2.main:app --host 127.0.0.1 --port 8011
 *   cd frontend_v2 && npm run screenshots
 *
 * Options:  --base http://127.0.0.1:8011   --out ../../docs/screenshots/phase3
 */
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const here = dirname(fileURLToPath(import.meta.url))
const args = process.argv.slice(2)
const flag = (name, fallback) => {
  const i = args.indexOf(`--${name}`)
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback
}
const BASE = flag('base', 'http://127.0.0.1:8011').replace(/\/$/, '')
const OUT = resolve(here, flag('out', '../../docs/screenshots/phase3'))

const shots = []
const record = (file) => shots.push(file)

async function shoot(context, file, path, prepare) {
  const page = await context.newPage()
  await page.goto(`${BASE}${path}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(400)
  if (prepare) {
    await prepare(page)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
  }
  const target = resolve(OUT, file)
  await page.screenshot({ path: target, fullPage: true })
  const title = await page.title()
  console.log(`  ${file}  <-  ${path}${prepare ? ' (+interaction)' : ''}  [${title}]`)
  record(file)
  await page.close()
}

/** Pick the EURUSD trade (it has quick + deep reviews) in a review picker. */
async function selectEurUsd(page) {
  const value = await page
    .locator('select option')
    .filter({ hasText: 'EURUSD' })
    .first()
    .getAttribute('value')
  if (value) await page.selectOption('select', value)
  else console.warn('    (EURUSD trade not found in the picker - using default)')
}

async function main() {
  await mkdir(OUT, { recursive: true })
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    reducedMotion: 'reduce',
    colorScheme: 'dark',
  })
  console.log(`Capturing ${BASE} -> ${OUT}`)

  await shoot(context, '01-quest-hub.png', '/')
  await shoot(context, '02-trade-journal.png', '/trades')
  await shoot(context, '03-trade-detail.png', '/trades/2')
  await shoot(context, '04-quick-capture.png', '/quick-capture')
  await shoot(context, '05-quick-review.png', '/quick-review', selectEurUsd)
  await shoot(context, '06-deep-review.png', '/deep-review', selectEurUsd)
  await shoot(context, '07-emotional-journal.png', '/emotional')
  await shoot(context, '08-daily-review.png', '/daily-review')
  await shoot(context, '09-weekly-review.png', '/weekly-review')
  await shoot(context, '10-quest-center.png', '/quests')
  await shoot(context, '11-achievements.png', '/achievements')
  await shoot(context, '12-settings.png', '/settings')
  await shoot(context, '13-settings-options.png', '/settings', async (page) => {
    await page.getByRole('tab', { name: 'Options' }).click()
  })
  await shoot(context, '14-quest-claim-toast.png', '/quests', async (page) => {
    const claim = page.getByRole('button', { name: /claim reward/i }).first()
    if (await claim.count()) {
      await claim.click()
      await page.waitForTimeout(600)
    } else {
      console.warn('    (no claimable quest - toast shot shows the page as-is)')
    }
  })

  await browser.close()
  await writeFile(
    resolve(OUT, 'shots.json'),
    `${JSON.stringify({ base: BASE, capturedAt: new Date().toISOString(), files: shots }, null, 2)}\n`,
  )
  console.log(`\n${shots.length} screenshots written to ${OUT}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
