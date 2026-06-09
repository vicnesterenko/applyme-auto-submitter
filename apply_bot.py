import asyncio
import json
import os
import random

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright, ViewportSize
from playwright_stealth import Stealth

from helpers.parse_docx import load_candidate_data
from resources.values import JOBS_URLS, SCREENSHOTS_DIR, USER_AGENT

HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
DRY_RUN = False
RESULTS_PATH = os.path.abspath("results.json")
PROFILE_DIR = os.path.abspath("chrome_profile")

# Шлях до папки з розпакованим розширенням Buster у вашому проекті
EXTENSION_PATH = os.path.abspath("captcha_solver")


async def human_delay(min_sec=1.5, max_sec=3.5):
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def human_fill(page, selector_or_element, value):
    if not value:
        return False

    if isinstance(selector_or_element, str):
        locator = page.locator(selector_or_element).first
        if await locator.count() == 0:
            return False
        current_value = await locator.input_value()
        element_to_work = locator
    else:
        element_to_work = selector_or_element
        current_value = await element_to_work.input_value()

    if current_value and current_value.strip():
        return False

    await element_to_work.scroll_into_view_if_needed()
    await human_delay(0.2, 0.5)
    try:
        await element_to_work.click(timeout=5000)
        if hasattr(element_to_work, "press_sequentially"):
            await element_to_work.press_sequentially(str(value), delay=random.uniform(40, 110))
        else:
            await element_to_work.press(str(value), delay=random.uniform(40, 110))
    except Exception:
        if hasattr(element_to_work, "fill"):
            await element_to_work.fill(str(value), timeout=5000)
        else:
            await page.evaluate("(el, val) => el.value = val", element_to_work, str(value))

    await human_delay(0.3, 0.9)
    return True


def get_clean_answer(label_text, candidate):
    """Точний підбір відповіді на основі видимого текста мітки (Label)"""
    t = label_text.lower()

    if "salary" in t or "compensation" in t or "очікувана зп" in t:
        return str(candidate.get("salary") or "140000")

    if "sponsor" in t or "visa" in t:
        return "No"

    if "relocat" in t:
        return candidate.get("willing_to_relocate") or "No"

    if "authorized" in t or "authorised" in t or "legal" in t:
        return "Yes"

    if "how did you learn" in t or "hear about" in t:
        return "LinkedIn"

    if "experience" in t or "years" in t:
        return str(candidate.get("total_experience") or "10")

    if "notice period" in t or "start" in t:
        return "Immediately"

    return ""


async def fill_lever_custom_fields(page, candidate):
    """Кастомний парсер полів, заточений під архітектуру платформи Lever"""
    print("  Аналіз та розумне заповнення кастомних блоків...")

    form_cards = await page.query_selector_all('.application-card, .card, .application-question')
    if not form_cards:
        form_cards = await page.query_selector_all('div')

    for card in form_cards:
        try:
            label_el = await card.query_selector('.text, label, .application-label')
            if not label_el:
                continue

            label_text = await label_el.inner_text()
            if not label_text or not label_text.strip():
                continue

            label_text = label_text.strip()

            # 1. Обробка Радіо-кнопок
            radios = await card.query_selector_all('input[type="radio"]')
            if radios and not any([await r.is_checked() for r in radios]):
                t = label_text.lower()
                target_value = None

                if "sponsor" in t or "visa" in t:
                    target_value = "No"
                elif "authorized" in t or "authorised" in t or "legal" in t:
                    target_value = "Yes"
                elif "subject to an agreement" in t or "restrict" in t or "non-compete" in t:
                    target_value = "No"
                elif "text messages" in t or "opt-in" in t:
                    target_value = "No"

                if target_value:
                    for radio in radios:
                        r_label = await page.evaluate(
                            "el => el.nextElementSibling ? el.nextElementSibling.innerText : el.value", radio)
                        if r_label and target_value.lower() in r_label.lower():
                            await radio.click()
                            await human_delay(0.3, 0.6)
                            break
                continue

            # 2. Обробка текстових інпутів / textarea
            text_input = await card.query_selector('input[type="text"], textarea')
            if text_input:
                input_name = await text_input.get_attribute("name") or ""
                if any(k in input_name.lower() for k in ['name', 'email', 'phone', 'org', 'linkedin', 'github']):
                    continue

                current_val = await text_input.input_value()
                if not current_val.strip():
                    answer = get_clean_answer(label_text, candidate)
                    if answer:
                        await human_fill(page, text_input, answer)
                continue

            # 3. Обробка випадаючих списків (Select)
            select_input = await card.query_selector('select')
            if select_input:
                current_val = await select_input.input_value()
                if not current_val or current_val in ['0', '-1'] or 'select' in current_val.lower():
                    await page.evaluate("""(s) => {
                        const opts = [...s.options].filter(o => o.value && !/select|choose|--/i.test(o.text));
                        if (opts.length) s.value = opts[0].value;
                        s.dispatchEvent(new Event('change', { bubbles: true }));
                    }""", select_input)
                    await human_delay(0.4, 0.8)
                continue

        except Exception:
            pass

    # 4. Окреме заповнення фінальних чекбоксів згоди
    try:
        checkboxes = await page.query_selector_all('input[type="checkbox"]')
        for cb in checkboxes:
            if not await cb.is_checked():
                await cb.click()
                await human_delay(0.3, 0.7)
    except Exception:
        pass


async def native_browser_captcha_bypass(page):
    """
    Автоматичний обхід капчі за допомогою розширення Buster з динамічним очікуванням DOM
    """
    try:
        print("  [🤖] Капча вимагає дій. Очікуємо ініціалізацію фрейму захисту...")

        # Даємо hCaptcha 3-5 секунд на рендеринг iframe після кліку по Submit
        await asyncio.sleep(4.0)

        challenge_frame = None
        for f in page.frames:
            if "challenge" in f.url or "bframe" in f.url:
                challenge_frame = f
                break

        if not challenge_frame:
            print("  [!] Активний фрейм з картинками капчі не знайдено.")
            return

        # Динамічне очікування появи кнопки розширення Buster всередині Shadow DOM hCaptcha
        buster_icon = None
        for attempt in range(7):  # Пробуємо знайти протягом 7 секунд
            buster_icon = await page.query_selector('iframe[title*="challenge"] >>> .buster-button, #buster-button')
            if not buster_icon:
                buster_icon = await challenge_frame.query_selector('.buster-button, button[title*="solve"]')

            if buster_icon:
                break
            await asyncio.sleep(1.0)

        if buster_icon:
            print("  [✅] Віджет Buster знайдено! Натискаємо на авторозв'язання...")
            await buster_icon.click()
            # Довга пауза, щоб Buster встиг прослухати аудіо, надіслати запит і підставити токен
            await asyncio.sleep(8.0)
        else:
            print("  [!] Віджет Buster не з'явився у DOM. Можливо, hCaptcha заблокувала аудіо-завдання.")
            print("  [🤖] ГІБРИДНИЙ РЕЖИМ: Будь ласка, швидко клікніть картинки руками (маєте 30 секунд)...")

            # Робимо паузу 30 секунд для ручного підстрахування у відкритому вікні браузера
            for sec in range(30):
                if "thanks" in page.url or await page.query_selector('.application-error') is not None:
                    break
                await asyncio.sleep(1.0)

    except Exception as e:
        print(f"  Помилка взаємодії з розширенням капчі: {e}")


async def apply_to_job(context, url, candidate, resume_path, dry_run=True, screenshot_dir="."):
    apply_url = url if url.rstrip("/").endswith("/apply") else url.rstrip("/") + "/apply"

    if context.pages:
        page = context.pages[0]
    else:
        page = await context.new_page()

    try:
        print(f"\nNavigating to: {apply_url}")
        await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
        await human_delay(2, 4)

        file_input = await page.query_selector('input[type="file"]')
        if file_input:
            if not os.path.exists(resume_path):
                print(f"  resume.pdf not found — skipping file injection block.")
                return {"url": url, "status": "failed", "reason": f"resume_not_found:{resume_path}"}
            else:
                await file_input.set_input_files(resume_path)
                print("  Resume file attached. Waiting 7-12s for automatic field parsing...")
                await human_delay(8.0, 12.0)
        else:
            print("  Resume file upload component not found.")

        # Базові поля
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

        await human_delay(1, 2)

        await fill_lever_custom_fields(page, candidate)
        await human_delay(1.5, 3.0)

        if dry_run:
            await _safe_screenshot(page, url, prefix="dryrun", screenshot_dir=screenshot_dir)
            print(f"  [DRY-RUN]: Форму повністю заповнено. Скрипт зупинено перед кнопкою Submit.")
            while True:
                await asyncio.sleep(1)

        print("  Triggering final form submission interaction...")
        submit = page.locator(
            "#btn-submit.template-btn-submit, #btn-submit:visible, button[type='submit']:visible").first
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

        # Викликаємо обхід від розширення ОДРАЗУ після надсилання форми
        await native_browser_captcha_bypass(page)

        try:
            await page.wait_for_url("**/thanks**", timeout=25000)
            print(f"  SUCCESS: {url}")
            await _safe_screenshot(page, url, prefix="success", screenshot_dir=screenshot_dir)
            return {"url": url, "status": "success"}
        except PlaywrightTimeout:
            print("  [ПОМИЛКА]: Форма не відправилась за вказаний час.")
            await _safe_screenshot(page, url, prefix="validation_error", screenshot_dir=screenshot_dir)
            return {"url": url, "status": "failed", "reason": "validation_error_or_captcha"}

    except Exception as exc:
        print(f"  Критична помилка виконання: {exc}")
        await _safe_screenshot(page, url, prefix="critical_error", screenshot_dir=screenshot_dir)
        return {"url": url, "status": "failed", "reason": str(exc)}


async def _safe_screenshot(page, url, prefix="error", screenshot_dir="."):
    try:
        path = os.path.join(screenshot_dir, f"{prefix}_{_safe_name(url)}.png")
        await page.screenshot(path=path, full_page=True)
    except Exception:
        pass


def _safe_name(url):
    return "".join(c if c.isalnum() else "_" for c in url)[-60:]


async def submit_applications(candidate, resume_path, urls, dry_run=True, headless=False, screenshot_dir="."):
    os.makedirs(screenshot_dir, exist_ok=True)
    stealth = Stealth()
    results = []

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=headless,
            channel="chrome" if not headless else None,
            ignore_default_args=["--enable-automation"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                f"--disable-extensions-except={EXTENSION_PATH}",
                f"--load-extension={EXTENSION_PATH}",
            ],
            user_agent=USER_AGENT,
            viewport=ViewportSize(width=1280, height=800),
            locale="en-US",
        )
        await stealth.apply_stealth_async(context)

        for url in urls:
            res = await apply_to_job(
                context=context,
                url=url,
                candidate=candidate,
                resume_path=resume_path,
                dry_run=dry_run,
                screenshot_dir=screenshot_dir,
            )
            results.append(res)

            try:
                with open(RESULTS_PATH, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Помилка запису в JSON: {e}")

            await asyncio.sleep(random.uniform(5, 10))

        await context.close()

    return results


async def auto_submitter():
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
        screenshot_dir=str(SCREENSHOTS_DIR),
    )

    print(f"\nРоботу завершено! Результати збережено в: {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(auto_submitter())