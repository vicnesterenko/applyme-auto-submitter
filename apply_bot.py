# ruff: noqa: E402, F541
# E402: imports must run after the distutils/SSL shim below.
# F541: one JS template below is an f-string with no interpolation (kept for parity).
# ---------------------------------------------------------------------
# Compatibility shims for Python 3.13+ on macOS:
#  * distutils.version.LooseVersion was removed in Python 3.12, but the
#    SeleniumBase driver auto-update path still imports it, so we back it
#    with packaging.version.Version.
#  * Relax SSL verification so the ChromeDriver/font downloads don't fail
#    on machines with an incomplete certificate chain.
# ---------------------------------------------------------------------
import sys
import types
import ssl
from packaging.version import Version as OriginalVersion

ssl._create_default_https_context = ssl._create_unverified_context


class FakeLooseVersion(OriginalVersion):
    def __init__(self, version_str):
        self._orig_str = str(version_str)
        super().__init__(self._orig_str)
        self.version = list(self.release)

    @property
    def vstring(self):
        return self._orig_str


distutils_module = types.ModuleType("distutils")
version_module = types.ModuleType("distutils.version")
version_module.LooseVersion = FakeLooseVersion
distutils_module.version = version_module
sys.modules["distutils"] = distutils_module
sys.modules["distutils.version"] = version_module
# ---------------------------------------------------------------------

import json
import os
import random
import time
import base64

from selenium.webdriver.common.by import By
from seleniumbase import DriverContext
from twocaptcha import TwoCaptcha

from helpers.parse_docx import load_candidate_data
from resources.values import JOBS_URLS, SCREENSHOTS_DIR, TWO_CAPTCHA_API_KEY


RESULTS_PATH = os.path.abspath("resources/result_report/results.json")
PROFILE_DIR = os.path.abspath("chrome_profile_sbase")

# When True, forms are filled and screenshotted but never submitted.
DRY_RUN = False

def human_delay(min_sec=1.5, max_sec=3.5):
    time.sleep(random.uniform(min_sec, max_sec))


def human_fill_sbase(driver, element, value):
    """Type value into element character by character with randomized delays."""
    if not value:
        return False
    try:
        current_val = element.get_attribute("value")
        if current_val and current_val.strip():
            return False

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        human_delay(0.2, 0.5)
        driver.uc_click(element)

        for char in str(value):
            element.send_keys(char)
            time.sleep(random.uniform(0.04, 0.11))

        human_delay(0.3, 0.8)
        return True
    except BaseException:
        return False


def get_clean_answer(label_text, candidate):
    """Return a best-effort answer for a form field based on its label text."""
    t = label_text.lower()

    if any(k in t for k in ["salary", "compensation", "очікувана зп", "budgeted", "range", "desired", "pay"]):
        return str(candidate.get("salary") or "140000")

    if "current company" in t or "company" in t:
        return str(candidate.get("org") or "company1")

    if "sponsorship" in t or "sponsor" in t or "visa" in t:
        return "No"

    if "relocat" in t:
        return candidate.get("willing_to_relocate") or "No"

    if any(k in t for k in ["authorized", "authorised", "legal", "lawfully", "eligible", "permit"]):
        if "canada" in t or "uk" in t:
            return "No"
        return "Yes"

    if any(k in t for k in ["how did you learn", "hear about", "source"]):
        return "LinkedIn"

    if any(k in t for k in
           ["degree", "python", "learning", "statistical", "optimization", "data", "spark", "experience", "years"]):
        return "Yes"

    if any(k in t for k in ["bound", "covenant", "restrict", "non-compete"]):
        return "No"

    if any(k in t for k in ["acknowledge", "certify", "confirm", "understand", "agree"]):
        return "Yes"

    if "notice" in t or "start" in t:
        return "Immediately"

    return ""


def apply_company_specific_bypass(driver, url, candidate):
    """Apply company-specific field overrides via JavaScript for forms that need tailored handling."""
    lowered_url = url.lower()
    salary_value = str(candidate.get("salary") or "140000")
    linkedin_value = str(candidate.get("linkedin") or "https://linkedin.com/tsttst123123123123123")

    # PadSplit: LinkedIn URL, location, multiple-choice radios, and the free-text question.
    if "padsplit" in lowered_url:
        print("  [PadSplit] Applying company-specific field overrides...")
        try:
            driver.execute_script(f"""
                const li_field = document.querySelector('input[name*="LinkedIn"], input[name*="linkedin"], input[name*="urls"]');
                if (li_field) {{
                    li_field.value = '{linkedin_value}';
                    li_field.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}

                const loc_input = document.getElementById('location-input');
                if (loc_input) {{
                    loc_input.value = 'New York, NY, United States';
                    loc_input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    const hidden_loc = document.getElementById('selected-location');
                    if (hidden_loc) hidden_loc.value = 'New York, NY, United States';
                }}

                const radioGroups = document.querySelectorAll('ul[data-qa="multiple-choice"]');
                radioGroups.forEach(group => {{
                    const visibleRadios = [...group.querySelectorAll('input[type="radio"]')].filter(r => r.offsetHeight > 0);
                    if (visibleRadios.length > 2) {{
                        visibleRadios[visibleRadios.length - 1].checked = true;
                        visibleRadios[visibleRadios.length - 1].dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }} else if (visibleRadios.length === 2) {{
                        visibleRadios[0].checked = true;
                        visibleRadios[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }});

                const hot_take = document.querySelector('textarea[name*="field14"], textarea');
                if (hot_take && !hot_take.value) {{
                    hot_take.value = 'Good copywriting isn\\'t about fancy words; it\\'s about clear, data-driven empathy that solves a customer problem.';
                    hot_take.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            """)
            human_delay(0.5, 1.0)
        except Exception as e:
            print(f"  [PadSplit] Field override warning: {e}")

    # Aledade: fill the salary field.
    elif "aledade" in lowered_url:
        print("  [Aledade] Applying company-specific field overrides...")
        try:
            driver.execute_script(f"""
                const inputs = document.querySelectorAll('input, textarea');
                inputs.forEach(el => {{
                    const name = (el.getAttribute('name') || '').toLowerCase();
                    if (name === 'salary') {{
                        el.value = '{salary_value}';
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                }});
            """)
        except Exception as e:
            print(f"  [Aledade] Field override warning: {e}")

    # The Athletic: fill the free-text statement question.
    elif "theathletic" in lowered_url or "athletic" in lowered_url:
        print("  [The Athletic] Applying company-specific field overrides...")
        try:
            driver.execute_script(f"""
                const stmt = document.querySelector('textarea[name*="field0"], textarea');
                if (stmt && !stmt.value) {{
                    stmt.value = 'I am highly inspired by The Athletic\\'s world-class sports journalism and want to scale its interactive live media presence.';
                    stmt.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            """)
        except Exception as e:
            print(f"  [The Athletic] Field override warning: {e}")


def fill_lever_custom_fields_sbase(driver, candidate):
    """Detect and auto-fill Lever's custom question cards (radios, text inputs, selects, checkboxes)."""
    form_cards = driver.find_elements(
        By.CSS_SELECTOR,'.application-question, .application-card, .card, .custom-question'
    )
    if not form_cards:
        form_cards = driver.find_elements(By.TAG_NAME, 'div')

    for card in form_cards:
        try:
            label_el = card.find_element(By.CSS_SELECTOR, '.text, label, .application-label')
            label_text = label_el.text.strip()
            if not label_text:
                continue

            # 1. Radio Buttons processing
            radios = card.find_elements(By.CSS_SELECTOR, 'input[type="radio"]')
            if radios:
                visible_radios = [r for r in radios if r.is_displayed()]
                if not visible_radios or any([r.is_selected() for r in visible_radios]):
                    continue

                t = label_text.lower()
                target_value = None

                if "sponsor" in t or "visa" in t:
                    target_value = "No"
                elif any(
                        k in t for k in
                        [
                            "authorized", "authorised", "legal", "lawfully", "eligible", "accept", "offer", "degree",
                            "python", "learning", "experience", "years", "data", "spark"
                         ]
                ):
                    if "canada" in t or "uk" in t:
                        target_value = "No"
                    else:
                        target_value = "Yes"
                elif any(k in t for k in ["bound", "covenant", "restrict", "non-compete"]):
                    target_value = "No"
                elif any(k in t for k in ["text messages", "opt-in", "refer", "employed by"]):
                    target_value = "No"
                elif "physically located" in t or "location" in t:
                    target_value = "Yes"

                if target_value:
                    for radio in visible_radios:
                        r_label = driver.execute_script(
                            "return arguments[0].nextElementSibling ? arguments[0].nextElementSibling.innerText : arguments[0].value",
                            radio
                        )
                        if r_label and target_value.lower() in r_label.lower():
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", radio)
                            human_delay(0.2, 0.4)
                            driver.execute_script("arguments[0].click();", radio)
                            human_delay(0.3, 0.6)
                            break
                continue

            # 2. Text Inputs / Textareas / Number Fields processing
            try:
                text_input = card.find_element(By.CSS_SELECTOR, 'input, textarea')
                if text_input.is_displayed():
                    input_type = text_input.get_attribute("type") or ""
                    input_name = text_input.get_attribute("name") or ""

                    if input_type not in ["submit", "button", "hidden", "file", "radio", "checkbox"]:
                        if not any(k in label_text.lower() or k in input_name.lower() for k in
                                   ['email', 'phone', 'current location', 'location', 'name']):
                            current_val = text_input.get_attribute("value")

                            if current_val and (
                                    "company" in label_text.lower() or "current company" in label_text.lower()):
                                if current_val.lower() == "company2":
                                    driver.execute_script("arguments[0].value = '';", text_input)
                                    current_val = ""

                            if not current_val or not current_val.strip():
                                answer = get_clean_answer(label_text, candidate)
                                if answer:
                                    driver.execute_script("arguments[0].value = arguments[1];", text_input, answer)
                                    driver.execute_script(
                                        "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", text_input)
            except Exception as e:
                print(f"  [PadSplit] Field override warning: {e}")
                pass

            # 3. Dropdowns (Select elements) processing
            try:
                select_input = card.find_element(By.TAG_NAME, 'select')
                if select_input.is_displayed():
                    current_val = select_input.get_attribute("value")
                    select_name = select_input.get_attribute("name") or ""

                    if "race" in select_name.lower() or "race" in label_text.lower() or "ethnicity" in label_text.lower():
                        driver.execute_script("""
                            const s = arguments[0];
                            const opt = [...s.options].find(o => /decline|not to say|choose not/i.test(o.text));
                            if (opt) s.value = opt.value;
                            s.dispatchEvent(new Event('change', { bubbles: true }));
                        """, select_input)
                        human_delay(0.4, 0.8)
                        continue

                    if "veteran" in select_name.lower() or "veteran" in label_text.lower():
                        driver.execute_script("""
                            const s = arguments[0];
                            const opt = [...s.options].find(o => /not a veteran|decline/i.test(o.text));
                            if (opt) s.value = opt.value;
                            s.dispatchEvent(new Event('change', { bubbles: true }));
                        """, select_input)
                        human_delay(0.4, 0.8)
                        continue

                    if "outside" in label_text.lower() or "location" in label_text.lower() or "state" in label_text.lower():
                        driver.execute_script(r"""
                            const s = arguments[0];
                            const opt = [...s.options].find(o => /new york|united states|inside u\.s\./i.test(o.text));
                            if (opt) s.value = opt.value;
                            else if (s.options.length > 1) s.value = s.options[1].value;
                            s.dispatchEvent(new Event('change', { bubbles: true }));
                        """, select_input)
                        human_delay(0.4, 0.8)
                        continue

                    if not current_val or current_val in ['0', '-1'] or 'select' in current_val.lower():
                        driver.execute_script("""
                            const s = arguments[0];
                            const opts = [...s.options].filter(o => o.value && !/select|choose|--/i.test(o.text));
                            if (opts.length) s.value = opts[0].value;
                            s.dispatchEvent(new Event('change', { bubbles: true }));
                        """, select_input)
                        human_delay(0.4, 0.8)
            except Exception as e:
                print(f"  [PadSplit] Field override warning: {e}")
                pass

        except Exception as e:
            print(f"Fill lever custom fields sbase error: {e}")
            pass

    # 4. Consent checkboxes
    try:
        use_name_checkbox = driver.find_elements(By.ID, "useNameOnlyPronounsOption")
        if use_name_checkbox and use_name_checkbox[0].is_displayed():
            if not use_name_checkbox[0].is_selected():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", use_name_checkbox[0])
                human_delay(0.2, 0.4)
                driver.execute_script("arguments[0].click();", use_name_checkbox[0])
                human_delay(0.3, 0.6)

        checkboxes = driver.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]')
        for cb in checkboxes:
            cb_name = cb.get_attribute("name") or ""
            cb_id = cb.get_attribute("id") or ""
            if "pronouns" in cb_name or "Pronouns" in cb_id:
                continue

            if cb.is_displayed() and not cb.is_selected():
                driver.execute_script("arguments[0].click();", cb)
                human_delay(0.3, 0.7)
    except Exception as e:
        print(f"  [PadSplit] Field override warning: {e}")
        pass


def solve_hcaptcha_via_api(driver):
    """Extract the hCaptcha sitekey, solve it via the 2Captcha API, inject the token, and submit."""
    if not TWO_CAPTCHA_API_KEY or "YOUR_" in TWO_CAPTCHA_API_KEY:
        print("  [captcha] 2Captcha API key is not configured; skipping automated solve.")
        return False
    try:
        print("  [captcha] hCaptcha detected. Extracting sitekey...")
        hcaptcha_container = driver.find_element(By.CSS_SELECTOR, ".h-captcha, [data-sitekey]")
        sitekey = hcaptcha_container.get_attribute("data-sitekey")
        current_url = driver.current_url

        if not sitekey:
            iframe = driver.find_element(By.XPATH, "//iframe[contains(@src, 'sitekey')]")
            src = iframe.get_attribute("src") or ""
            sitekey = src.split("sitekey=")[1].split("&")[0]

        print(f"  [captcha] Sitekey captured: {sitekey}. Submitting task to 2Captcha...")
        solver = TwoCaptcha(TWO_CAPTCHA_API_KEY)
        result = solver.hcaptcha(sitekey=sitekey, url=current_url)
        token = result['code']

        print("  [captcha] Token received. Injecting it into the Lever form...")
        driver.execute_script(f'document.getElementsByName("h-captcha-response")[0].innerHTML="{token}";')
        driver.execute_script(f'document.getElementsByName("g-recaptcha-response")[0].innerHTML="{token}";')

        print("  [captcha] Token injected. Submitting the form...")
        driver.execute_script("document.querySelector('form').submit();")
        time.sleep(4.0)
        return True
    except Exception as e:
        print(f"  [captcha] Automated solve failed: {e}")
        return False


def apply_to_job_selenium(driver, url, candidate, resume_path):
    if url.rstrip("/").endswith("/apply"):
        apply_url = url.rstrip("/")
    else:
        apply_url = url.rstrip("/") + "/apply"

    try:
        print(f"\nNavigating to: {apply_url}")
        driver.uc_open_with_reconnect(apply_url, 4)
        human_delay(3, 5)

        # Uploading the generated resume PDF file
        try:
            file_input = driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
            if not os.path.exists(resume_path):
                return {"url": url, "status": "failed", "reason": "resume_not_found"}

            file_input.send_keys(os.path.abspath(resume_path))
            print("  Resume file attached successfully. Waiting 10s for layout triggers...")
            time.sleep(10.0)
        except BaseException as fe:
            print(f"  Failed to attach candidate resume document: {fe}")

        # Basic identity text inputs mapping
        base_fields = [
            ('input[name="name"]', "name"), ('input[name="email"]', "email"),
            ('input[name="phone"]', "phone"), ('input[name="org"]', "org")
        ]

        for selector, key in base_fields:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and elements[0].is_displayed():
                    human_fill_sbase(driver, elements[0], candidate[key])
            except BaseException:
                pass

        # Apply company-specific field overrides for known forms.
        apply_company_specific_bypass(driver, apply_url, candidate)

        human_delay(1, 2)
        fill_lever_custom_fields_sbase(driver, candidate)
        human_delay(2.0, 4.0)

        # ---------------------------------------------------------------------
        # Capture a full-page screenshot of the filled form before submitting.
        # ---------------------------------------------------------------------
        print("  [screenshot] Capturing the filled form before submission...")
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        filled_screenshot_path = os.path.join(SCREENSHOTS_DIR, f"filled_form_{int(time.time())}.png")
        try:
            metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
            content_size = metrics["contentSize"]
            screenshot_data = driver.execute_cdp_cmd("Page.captureScreenshot", {
                "format": "png",
                "captureBeyondViewport": True,
                "clip": {
                    "x": 0, "y": 0, "width": content_size["width"], "height": content_size["height"], "scale": 1
                }
            })
            with open(filled_screenshot_path, "wb") as fh:
                fh.write(base64.b64decode(screenshot_data["data"]))
            print(f"  [screenshot] Saved filled-form screenshot: {filled_screenshot_path}")
        except BaseException as snap_err:
            print(f"  [screenshot] CDP capture failed, using fallback: {snap_err}")
            driver.save_screenshot(filled_screenshot_path)
        # ---------------------------------------------------------------------

        if DRY_RUN:
            print("  [dry-run] Stopping before clicking Submit.")
            time.sleep(5.0)
            return {"url": url, "status": "dry_run_passed"}

        # Submit the application for real.
        print("  Triggering final form submission...")
        submit_selector = "button[type='submit']"
        for sel in ["#btn-submit.template-btn-submit", "#btn-submit", "button[type='submit']"]:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                if elements and elements[0].is_displayed():
                    submit_selector = sel
                    break
            except Exception as e:
                print(f"  Failed to find {sel} selector: {e}")
                continue

        try:
            submit_btn = driver.find_element(By.CSS_SELECTOR, submit_selector)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
            human_delay(0.8, 1.5)
            driver.uc_click(submit_selector)
            print("  Submit button clicked. Checking the page response...")
        except BaseException as se:
            raise Exception(f"Submit interaction failed: {se}")

        time.sleep(4.0)

        # If an hCaptcha appears, attempt to solve it via the 2Captcha API.
        is_captcha = driver.find_elements(By.CSS_SELECTOR, "iframe[title*='hCaptcha'], .h-captcha")
        if is_captcha:
            solve_hcaptcha_via_api(driver)

        # Wait for the redirect to the "Thanks" confirmation page.
        success = False
        for _ in range(25):
            try:
                if "thanks" in str(driver.current_url or "").lower():
                    success = True
                    break
            except BaseException:
                break
            time.sleep(1.0)

        # Save the final screenshot for either outcome.
        if success:
            print(f"  SUCCESS: {url}")
            success_screenshot = os.path.join(SCREENSHOTS_DIR, f"success_sbase_{int(time.time())}.png")
            driver.save_screenshot(success_screenshot)
            print(f"  [screenshot] Saved success screenshot: {success_screenshot}")
            return {"url": url, "status": "success"}
        else:
            print("  [error] Success page was not reached within the timeout.")
            error_screenshot = os.path.join(SCREENSHOTS_DIR, f"error_sbase_{int(time.time())}.png")
            driver.save_screenshot(error_screenshot)
            print(f"  [screenshot] Saved error screenshot: {error_screenshot}")
            return {"url": url, "status": "failed", "reason": "captcha_or_timeout"}

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        print(f"  Critical execution failure: {error_msg}")
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        driver.save_screenshot(os.path.join(SCREENSHOTS_DIR, f"exception_sbase_{int(time.time())}.png"))
        return {"url": url, "status": "failed", "reason": error_msg}


def main():
    candidate, resume_path = load_candidate_data()
    print(f"Candidate Target profile: {candidate['name']} ({candidate['email']})")
    print(f"Associated resume: {resume_path}")

    mode_str = "DRY_RUN (fill only, no submit)" if DRY_RUN else "LIVE SUBMIT (2Captcha enabled)"
    print(f"Run mode: {mode_str}")

    with DriverContext(uc=True, user_data_dir=PROFILE_DIR, headless=False) as driver:
        results = []
        try:
            for url in JOBS_URLS:
                res = apply_to_job_selenium(driver, url, candidate, resume_path)
                results.append(res)
                with open(RESULTS_PATH, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=4, ensure_ascii=False)
                human_delay(5, 10)
        except Exception as e:
            print(f"Loop processing error occurred: {e}")
        finally:
            print(f"\nProcessing cycle finished. Diagnostic results stored at: {RESULTS_PATH}")


if __name__ == "__main__":
    main()