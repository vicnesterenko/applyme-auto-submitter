import asyncio
import json
import os
import random

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from helpers.parse_docx import load_candidate_data
from resources.values import JOBS_URLS, USER_AGENT

HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
DRY_RUN = os.getenv("DRY_RUN", "true").lower() != "false"
RESULTS_PATH = os.path.abspath("results.json")


async def human_delay(min_sec=1.5, max_sec=3.5):
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def human_like_click(page, selector):
    element = await page.wait_for_selector(selector, state="visible")
    await element.scroll_into_view_if_needed()
    box = await element.bounding_box()
    if not box:
        await element.click()
        return

    target_x = box["x"] + box["width"] / 2 + random.uniform(-6, 6)
    target_y = box["y"] + box["height"] / 2 + random.uniform(-4, 4)

    start_x = random.uniform(0, page.viewport_size["width"])
    start_y = random.uniform(0, page.viewport_size["height"])
    steps = random.randint(3, 6)
    for i in range(1, steps + 1):
        t = i / steps
        jitter_x = random.uniform(-25, 25) * (1 - t)
        jitter_y = random.uniform(-25, 25) * (1 - t)
        x = start_x + (target_x - start_x) * t + jitter_x
        y = start_y + (target_y - start_y) * t + jitter_y
        await page.mouse.move(x, y, steps=random.randint(5, 12))
        await asyncio.sleep(random.uniform(0.02, 0.08))

    await page.mouse.move(target_x, target_y, steps=random.randint(4, 8))
    await human_delay(0.2, 0.5)
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.05, 0.15))
    await page.mouse.up()


async def human_fill(page, selector, value):
    if not value:
        return False
    locator = page.locator(selector).first
    if await locator.count() == 0:
        return False
    await locator.scroll_into_view_if_needed()
    await human_delay(0.2, 0.5)
    try:
        await locator.click(timeout=5000)
        await locator.press_sequentially(str(value), delay=random.uniform(40, 110))
    except Exception:
        await locator.fill(str(value), timeout=5000)
    await human_delay(0.3, 0.9)
    return True


async def fill_custom_fields(page, candidate):
    await page.evaluate(
        """(candidate) => {
            const skip = new Set([
                'name','email','phone','location','org','resume','pronouns','honey',
                'urls[LinkedIn]','urls[GitHub]','urls[Portfolio]','urls[Twitter]','urls[Other]',
                'eeo[gender]','eeo[race]','eeo[veteran]','eeo[disability]'
            ]);
            const positive = /^(yes|true|agree|accept|confirm|authorized|authorised|eligible|remote|hybrid|full[- ]?time)/i;
            const negative = /^(no|decline|prefer not|not applicable|n\\/a)/i;

            const pickRadio = (inputs) => {
                const visible = inputs.filter(i => i.offsetParent !== null);
                if (!visible.length) return;
                const labels = visible.map(i => ({
                    el: i,
                    text: (i.labels?.[0]?.innerText || i.value || '').trim()
                }));
                const preferred =
                    labels.find(l => positive.test(l.text)) ||
                    labels.find(l => !negative.test(l.text)) ||
                    labels[0];
                if (preferred && !preferred.el.checked) preferred.el.click();
            };

            const pickSelect = (sel) => {
                if (!sel || sel.value) return;
                const opts = [...sel.options].filter(o => o.value && !/select|choose|--/i.test(o.text));
                if (opts.length) sel.value = opts[0].value;
                sel.dispatchEvent(new Event('change', { bubbles: true }));
            };

            const answerText = (name) => {
                const n = (name || '').toLowerCase();
                if (n.includes('salary') || n.includes('compensation')) return String(candidate.salary || '140000');
                if (n.includes('sponsor') || n.includes('visa')) return candidate.requires_sponsorship ? 'Yes' : 'No';
                if (n.includes('relocat')) return candidate.willing_to_relocate || 'No';
                if (n.includes('authorized') || n.includes('authorised') || n.includes('eligible')) {
                    return (candidate.authorised_to_work && candidate.authorised_to_work[0]) || 'Yes';
                }
                if (n.includes('experience') || n.includes('years')) return String(candidate.total_experience || '10');

                // Intelligent matching logic for extended profile fields
                if (n.includes('industry') || n.includes('industries')) {
                    return (candidate.industries_experience && candidate.industries_experience.slice(0, 3).join(', ')) || 'Software';
                }
                if (n.includes('title') || n.includes('role')) {
                    return (candidate.target_job_titles && candidate.target_job_titles.join(', ')) || 'Product Manager';
                }
                if (n.includes('work_type') || n.includes('remote')) {
                    return (candidate.wanted_work_type && candidate.wanted_work_type.join('/')) || 'Remote';
                }

                if (n.includes('why') || n.includes('cover') || n.includes('motivat')) {
                    return (`I am excited about this role. ` +
                        `My core skills include ${candidate.skills || ''}.`).slice(0, 800);
                }
                if (n.includes('skill')) return candidate.skills || '';

                const fallbackText = candidate.summary || candidate.experience || '';
                return fallbackText.slice(0, 400);
            };

            // Radio groups
            const radioNames = new Set();
            document.querySelectorAll('input[type="radio"]').forEach(r => {
                if (r.name && !skip.has(r.name) && r.required) radioNames.add(r.name);
            });
            radioNames.forEach(name => {
                pickRadio([...document.querySelectorAll(`input[type="radio"][name="${CSS.escape(name)}"]`)]);
            });

            // Selects
            document.querySelectorAll('select').forEach(sel => {
                if (!sel.name || skip.has(sel.name)) return;
                if (sel.required || sel.closest('.required')) pickSelect(sel);
            });

            // Textareas and text-based custom fields
            document.querySelectorAll('textarea, input[type="text"]').forEach(el => {
                if (!el.name || skip.has(el.name) || el.value) return;
                if (!el.required && !el.closest('.required')) return;
                if (el.type === 'text' && el.name === 'pronouns') return;
                el.value = answerText(el.name);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            });

            // Required checkboxes (terms, acknowledgements)
            document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                if (!cb.name || skip.has(cb.name) || cb.checked) return;
                if (cb.required || cb.closest('.required')) cb.click();
            });
        }""",
        {
            "salary": candidate.get("salary"),
            "requires_sponsorship": candidate.get("requires_sponsorship"),
            "willing_to_relocate": candidate.get("willing_to_relocate"),
            "authorised_to_work": candidate.get("authorised_to_work"),
            "total_experience": candidate.get("total_experience"),
            "experience": candidate.get("experience"),
            "skills": candidate.get("skills"),
            "summary": candidate.get("summary"),
            "industries_experience": candidate.get("industries_experience"),
            "target_job_titles": candidate.get("target_job_titles"),
            "wanted_work_type": candidate.get("wanted_work_type"),
            "wanted_job_type": candidate.get("wanted_job_type")
        },
    )
    await human_delay(0.5, 1.0)


async def handle_captcha_if_present(page):
    captcha_frame = await page.query_selector(
        'iframe[src*="recaptcha"], iframe[src*="hcaptcha"], iframe[title*="reCAPTCHA"]'
    )
    if not captcha_frame:
        return "ok"

    print("  CAPTCHA detected — checking if invisible processing clears via humanized actions...")
    await human_delay(3, 6)
    await page.mouse.move(random.randint(200, 900), random.randint(150, 600), steps=8)
    await human_delay(2, 4)

    still_present = await page.query_selector(
        'iframe[src*="recaptcha"], iframe[src*="hcaptcha"], iframe[title*="reCAPTCHA"]'
    )
    if still_present:
        print("  CAPTCHA challenge failed to clear natively under Playwright stealth framework.")
        return "captcha_blocked"

    print("  CAPTCHA not blocking submission (invisible bypass or solved).")
    return "ok"


async def apply_to_job(browser, url, stealth, candidate, resume_path, dry_run=True, screenshot_dir="."):
    apply_url = url if url.rstrip("/").endswith("/apply") else url.rstrip("/") + "/apply"

    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 800},
        locale="en-US",
    )
    await stealth.apply_stealth_async(context)
    page = await context.new_page()

    try:
        print(f"\nNavigating to: {apply_url}")
        await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
        await human_delay(2, 4)

        file_input = await page.query_selector('input[type="file"]')
        if file_input:
            if not os.path.exists(resume_path):
                if not dry_run:
                    return {"url": url, "status": f"failed:resume_not_found:{resume_path}"}
                print("  resume.pdf not found — skipping file injection block (dry-run).")
            else:
                await file_input.set_input_files(resume_path)
                print("  Resume file attached, awaiting automatic field parsing cycle...")
                await human_delay(3, 5)
        else:
            print("  Resume file upload component not found (or optional component).")

        for selector, key in (
                ('input[name="name"]', "name"),
                ('input[name="email"]', "email"),
                ('input[name="phone"]', "phone"),
                ('input[name="org"]', "org"),
                ('input[name="urls[LinkedIn]"]', "linkedin"),
                ('input[name="urls[GitHub]"]', "github"),
                ('input[name="urls[Portfolio]"]', "portfolio"),
        ):
            try:
                await human_fill(page, selector, candidate[key])
            except Exception as exc:
                print(f"  Field key tracking '{key}' skipped: {exc}")

        if candidate.get("location"):
            await page.evaluate(
                """(loc) => {
                    const el = document.querySelector('input[name="location"]');
                    if (el) {
                        el.value = loc;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""",
                candidate["location"],
            )

        await human_delay(1, 2)
        await fill_custom_fields(page, candidate)

        captcha_status = await handle_captcha_if_present(page)
        if captcha_status == "captcha_blocked":
            await _safe_screenshot(page, url, screenshot_dir=screenshot_dir)
            return {"url": url, "status": "captcha_blocked"}

        if dry_run:
            submit_btn = await page.query_selector('#btn-submit, button[type="submit"]')
            await _safe_screenshot(page, url, prefix="dryrun", screenshot_dir=screenshot_dir)
            status = "dry_run:reached_submit" if submit_btn else "dry_run:no_submit_button"
            print(f"  DRY-RUN: application form completed, execution stopped before Submit node ({status}).")
            return {"url": url, "status": status}

        print("  Triggering final form submission interaction...")
        submit = page.locator("#btn-submit.template-btn-submit, #btn-submit:visible").first
        await submit.wait_for(state="visible", timeout=15000)
        await submit.scroll_into_view_if_needed()
        await human_delay(0.5, 1.2)
        box = await submit.bounding_box()
        if box:
            await page.mouse.click(
                box["x"] + box["width"] / 2 + random.uniform(-3, 3),
                box["y"] + box["height"] / 2 + random.uniform(-2, 2),
            )
        else:
            await submit.click()

        try:
            await page.wait_for_url("**/thanks**", timeout=20000)
            print(f"  SUCCESS: {url}")
            await _safe_screenshot(page, url, prefix="success", screenshot_dir=screenshot_dir)
            return {"url": url, "status": "success"}
        except PlaywrightTimeout:
            error_msg = await page.evaluate(
                """() => {
                    const els = [...document.querySelectorAll('.application-error, .form-error, .error-message')];
                    const visible = els.filter(el => el.offsetParent !== null && el.innerText.trim());
                    return visible.map(el => el.innerText.trim()).join(' | ');
                }"""
            )
            if error_msg:
                msg = " ".join(error_msg.split())[:120]
                await _safe_screenshot(page, url, screenshot_dir=screenshot_dir)
                return {"url": url, "status": f"failed:required_fields:{msg}"}

            missing = await page.evaluate(
                """() => {
                    const bad = [];
                    document.querySelectorAll('input, textarea, select').forEach(el => {
                        if (!el.required || el.type === 'hidden') return;
                        if (el.type === 'radio') {
                            const group = document.querySelectorAll(`input[name="${CSS.escape(el.name)}"]`);
                            if (![...group].some(g => g.checked)) bad.push(el.name);
                            return;
                        }
                        if (el.type === 'checkbox' && !el.checked) bad.push(el.name);
                        else if (el.tagName === 'SELECT' && !el.value) bad.push(el.name);
                        else if ((el.type === 'text' || el.type === 'email' || el.tagName === 'TEXTAREA') && !el.value.trim()) bad.push(el.name);
                    });
                    return [...new Set(bad)].slice(0, 5);
                }"""
            )
            await _safe_screenshot(page, url, screenshot_dir=screenshot_dir)
            if missing:
                return {"url": url, "status": f"failed:missing_fields:{','.join(missing)}"}
            return {"url": url, "status": "failed:no_confirmation_or_custom_required_fields"}

    except PlaywrightTimeout as exc:
        await _safe_screenshot(page, url, screenshot_dir=screenshot_dir)
        return {"url": url, "status": f"failed:timeout:{str(exc).splitlines()[0][:80]}"}
    except Exception as exc:  # noqa: BLE001
        await _safe_screenshot(page, url, screenshot_dir=screenshot_dir)
        return {"url": url, "status": f"failed:{type(exc).__name__}:{str(exc)[:80]}"}
    finally:
        await context.close()


async def _safe_screenshot(page, url, prefix="error", screenshot_dir="."):
    try:
        path = os.path.join(screenshot_dir, f"{prefix}_{_safe_name(url)}.png")
        await page.screenshot(path=path, full_page=True)
    except Exception:
        pass


def _safe_name(url):
    return "".join(c if c.isalnum() else "_" for c in url)[-60:]


async def submit_applications(
        candidate,
        resume_path,
        urls,
        dry_run=True,
        headless=False,
        screenshot_dir=".",
):
    os.makedirs(screenshot_dir, exist_ok=True)
    stealth = Stealth()
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        try:
            for url in urls:
                res = await apply_to_job(
                    browser,
                    url,
                    stealth,
                    candidate,
                    resume_path,
                    dry_run=dry_run,
                    screenshot_dir=screenshot_dir,
                )
                results.append(res)
                await asyncio.sleep(random.uniform(3, 7))
        finally:
            await browser.close()
    return results


async def main():
    candidate, resume_path = load_candidate_data()
    print(f"Candidate Target profile: {candidate['name']} ({candidate['email']})")
    print(f"Associated resume: {resume_path}")
    print(f"Runtime parameters: {'DRY-RUN' if DRY_RUN else 'LIVE SUBMIT'}, headless={HEADLESS}")

    results = await submit_applications(
        candidate=candidate,
        resume_path=resume_path,
        urls=JOBS_URLS,
        dry_run=DRY_RUN,
        headless=HEADLESS,
    )

    print("\n=== EXECUTION SUBMISSION REPORT ===")
    for r in results:
        print(f"  {r['status']:<45} {r['url']}")

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nResults output log compiled successfully at: {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())