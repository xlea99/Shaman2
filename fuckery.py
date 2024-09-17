from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from shaman2.common.paths import paths


class Browser:
    def openBrowser(self):
        # Minimal setup
        chrome_options = webdriver.ChromeOptions()

        # Ensure ChromeDriver is correctly pointed to
        browserService = Service(paths["chromedriver"])

        # Initialize the Chrome driver
        self.driver = webdriver.Chrome(service=browserService, options=chrome_options)


b = Browser()
b.openBrowser()