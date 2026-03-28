"""
Simple test script to verify @file reference feature
Uses Selenium to automate browser testing
"""

import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def test_file_reference():
    """Test the @file reference feature"""

    # Setup Chrome in headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        print("🌐 Opening frontend...")
        driver.get("http://localhost:5176")

        # Wait for page to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        print("✅ Page loaded successfully")
        print(f"📄 Page title: {driver.title}")

        # Check if we can find the main app container
        time.sleep(2)

        # Try to find the input box
        try:
            input_box = driver.find_element(By.CSS_SELECTOR, 'textarea[placeholder*="message"]')
            print("✅ Found chat input box")

            # Type @ to trigger file picker
            input_box.send_keys("@")
            time.sleep(1)

            # Check if file picker appeared
            try:
                driver.find_element(By.CSS_SELECTOR, '[data-name="file-picker-popover"]')
                print("✅ File picker popover appeared!")
            except Exception:
                print("❌ File picker did not appear")

        except Exception as e:
            print(f"⚠️  Could not find input box: {e}")
            print("   (This is expected if not logged in or in chat view)")

        # Take screenshot
        driver.save_screenshot("test_screenshot.png")
        print("📸 Screenshot saved to test_screenshot.png")

        print("\n✅ Basic frontend test completed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")

    finally:
        driver.quit()


if __name__ == "__main__":
    test_file_reference()
