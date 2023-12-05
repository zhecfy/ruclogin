# from selenium import webdriver
import seleniumwire.webdriver as webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.common.exceptions import StaleElementReferenceException
from requests.exceptions import ConnectionError
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.core.os_manager import ChromeType
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from time import sleep
import datetime
import ddddocr
import base64
import os
import os.path as osp
import configparser
import requests
import pickle
import docopt

ROOT = os.path.dirname(os.path.abspath(__file__))
INI_PATH = osp.join(ROOT, "config.ini")

loginer_instance = None
config = configparser.ConfigParser()


class RUC_LOGIN:
    driver: webdriver.Chrome
    usernameInput: WebElement
    passwordInput: WebElement
    codeInput: WebElement
    codeImg: WebElement
    loginButton: WebElement
    login_alter: WebElement
    enableLogging: bool
    username: str
    password: str
    ocr: ddddocr.DdddOcr
    date: str
    lst_img: bytes
    lst_status: tuple

    def __init__(self) -> None:
        self.date = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.ocr = ddddocr.DdddOcr()
        global config
        config.read(INI_PATH, encoding="utf-8")
        browser = config["base"]["browser"]
        driver_path = config["base"]["driver"]

        def get_options(options):
            options.add_argument("--headless=new")
            options.add_argument("start-maximized")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-logging")
            options.add_argument("--silent")
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
            return options

        if browser == "Chrome":
            options = get_options(webdriver.ChromeOptions())
            try:
                self.driver = webdriver.Chrome(
                    options=options,
                    service=ChromeService(ChromeDriverManager().install()),
                )
            except ConnectionError as e:
                if not osp.exists(driver_path):
                    raise e
                self.driver = webdriver.Chrome(
                    options=options,
                    service=ChromeService(executable_path=driver_path),
                )
        elif browser == "Edge":
            options = get_options(webdriver.EdgeOptions())
            try:
                self.driver = webdriver.Edge(
                    options=options,
                    service=EdgeService(EdgeChromiumDriverManager().install()),
                )
            except ConnectionError as e:
                if not osp.exists(driver_path):
                    raise e
                self.driver = webdriver.Edge(
                    options=options,
                    service=EdgeService(executable_path=driver_path),
                )
        elif browser == "Chromium":
            options = get_options(webdriver.ChromeOptions())
            try:
                self.driver = webdriver.Chrome(
                    options=options,
                    service=ChromeService(
                        ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
                    ),
                )
            except ConnectionError as e:
                if not osp.exists(driver_path):
                    raise e
                self.driver = webdriver.Chrome(
                    options=options,
                    service=ChromeService(executable_path=driver_path),
                )
        else:
            raise ValueError("browser must be Chrome, Edge or Chromium")

    def initial_login(self, domain: str):
        global config
        config.read(INI_PATH, encoding="utf-8")
        self.username = config["base"]["username"]
        self.password = config["base"]["password"]
        self.enableLogging = config["base"].getboolean("enableLogging")
        if domain.startswith("v"):
            url = r"https://v.ruc.edu.cn/auth/login"
        else:
            url = r"https://v.ruc.edu.cn/auth/login?&proxy=true&redirect_uri=https%3A%2F%2Fv.ruc.edu.cn%2Foauth2%2Fauthorize%3Fresponse_type%3Dcode%26scope%3Dall%26state%3Dyourstate%26client_id%3D5d25ae5b90f4d14aa601ede8.ruc%26redirect_uri%3Dhttp%3A%2F%2Fjw.ruc.edu.cn%2FsecService%2Foauthlogin"
        self.driver.get(url)
        self.usernameInput = self.driver.find_element(
            By.XPATH, "/html/body/div/form/div[3]/input"
        )
        self.passwordInput = self.driver.find_element(
            By.XPATH, "/html/body/div/form/div[4]/input"
        )
        self.codeInput = self.driver.find_element(
            By.XPATH, "/html/body/div/form/div[6]/input"
        )
        self.codeImg = self.driver.find_element(
            By.XPATH, "/html/body/div/form/div[7]/img"
        )
        self.loginButton = self.driver.find_element(
            By.XPATH, "/html/body/div/form/div[12]/button"
        )
        self.login_alter = self.driver.find_element(
            By.XPATH, "/html/body/div/form/div[11]"
        )
        self.rememberMe = self.driver.find_element(
            By.XPATH, "/html/body/div/form/div[13]/span[1]/div"
        ).click()
        self.lst_img = None
        self.lst_status = self.current_status()

    def get_img(self):
        codeImgSrc = self.codeImg.get_attribute("src")
        img = codeImgSrc.split(",")[1]
        img = base64.b64decode(img)
        return img

    def current_status(self):
        try:
            return ("logging in", self.login_alter.text, self.get_img())
        except StaleElementReferenceException:  # 找不到元素，说明已经登录成功
            return ("success", None, None)

    def wait_for_new_img(self):
        waiting_time = 0
        img = self.get_img()
        while img == self.lst_img:
            sleep(0.1)
            waiting_time += 0.1
            if waiting_time > 10:
                raise TimeoutError("CodeImg refresh failed")
            img = self.get_img()
        self.lst_img = img
        return img

    def do_ocr(self):
        def is_valid_result(ocrRes: str):
            if len(ocrRes) != 4:
                return False
            for c in ocrRes:
                if not (
                    ord("a") <= ord(c) <= ord("z") or ord("A") <= ord(c) <= ord("Z")
                ):
                    return False
            return True

        for _ in range(100):
            img = self.wait_for_new_img()
            assert img == self.get_img()
            ocrRes = self.ocr.classification(img)
            if not is_valid_result(ocrRes):
                self.codeImg.click()
            else:
                return ocrRes, img
        raise TimeoutError("OCR failed")

    def try_login(self):
        self.usernameInput.clear()
        self.passwordInput.clear()
        self.codeInput.clear()
        self.usernameInput.send_keys(self.username)
        self.passwordInput.send_keys(self.password)
        ocrRes, img = self.do_ocr()
        self.codeInput.send_keys(ocrRes)

        self.loginButton.click()
        while (
            self.current_status() == self.lst_status
            and self.current_status()[0] == "logging in"
        ):
            sleep(0.1)
        self.lst_status = self.current_status()
        status_msg = self.lst_status[1]
        if status_msg == "验证码不正确或已失效,请重试！":
            return False
        elif status_msg == "用户不存在！" or status_msg == "用户名或密码不正确,请重试！":
            print("username: {}, password: {}".format(self.username, self.password))
            raise ValueError(status_msg)
        print(status_msg)
        return True

    def get_cookies(self, domain="v"):
        if domain.startswith("v"):
            raw_cookies = self.driver.get_cookies()
            cookies = {cookie["name"]: cookie["value"] for cookie in raw_cookies}
            return cookies
        elif domain.startswith("jw"):
            [
                self.driver.wait_for_request(
                    url,
                    timeout=10,
                )
                for url in [
                    "/Njw2017/index.html*",
                    "/secService/oauthlogin*",
                ]
            ]
            cookies = {}
            for request in self.driver.requests:
                if request.response:
                    cookie_header = request.response.headers["Set-Cookie"]
                    if cookie_header:
                        cookies.update(
                            {
                                cookie.split("=")[0]: cookie.split("=")[1].split(";")[0]
                                for cookie in cookie_header.split(", ")
                            }
                        )
            return cookies

    def login(self):
        for _ in range(10):
            success = self.try_login()
            if success:
                return
        raise TimeoutError("Login failed")


def get_cookies(cache=True, domain="v") -> dict:
    """Get cookies from cache or selenium login.

    Args:
        cache (bool, optional): Force regain when set to False. Defaults to True.

        domain (str, optional): "v", "jw", "v.ruc.edu.cn", "jw.ruc.edu.cn". Defaults to "v".

    Returns:
        dict: Like {'tiup_uid': '6112329b90f4d162e19b83c9', 'access_token': 'rhMSVympSBON2Xr8yAdhnQ'}
    """
    global loginer_instance
    domain = domain.split(".")[0]
    cache_path = osp.join(ROOT, f"{domain}_cookies.pkl")
    if cache:
        if osp.exists(cache_path):
            cookies = pickle.load(open(cache_path, "rb"))
            if check_cookies(cookies, domain):
                return cookies
    if loginer_instance is None:
        loginer_instance = RUC_LOGIN()
    loginer_instance.initial_login(domain)
    loginer_instance.login()
    cookies = loginer_instance.get_cookies(domain)
    if not cookies:
        raise ValueError("Login failed")
    pickle.dump(cookies, open(cache_path, "wb"))
    return cookies


def check_cookies(cookies, domain="v"):
    """Check if cookies are valid.

    Args:
        cookies (dict): Like {'tiup_uid': '6112329b90f4d162e19b83c9', 'access_token': 'rhMSVympSBON2Xr8yAdhnQ'}

        domain (str, optional): "v", "jw", "v.ruc.edu.cn", "jw.ruc.edu.cn". Defaults to "v".

    Returns:
        optional[str]: None if cookies are invalid, else a greeting message.
    """
    try:
        if domain.startswith("v"):
            response = requests.get(
                "https://v.ruc.edu.cn/v3/api/me/roles", cookies=cookies
            )
            role = response.json()["data"][-1]
            return f"你好, {role['departmentname']} {role['username']}"
        elif domain.startswith("jw"):
            response = requests.post(
                "https://jw.ruc.edu.cn/resService/jwxtpt/v1/xsd/xsdqxxkb_info/searchOneXskbList",
                params={
                    "resourceCode": "XSMH0701",
                    "apiCode": "jw.xsd.xsdInfo.controller.XsdQxxkbController.searchOneXskbList",
                },
                cookies={"SESSION": cookies["SESSION"]},
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "TOKEN": cookies["token"],
                },
                json={
                    "jczy013id": "2023-2024-1",
                    "pkgl002id": "c134b10e0000WH",
                },
            )
            d = response.json()["data"]
            return "你这学期的课有：" + " ".join(set([kc["kc_name"] for kc in d]))
    except:
        return None


def update_username_and_password(username: str, password: str):
    """Update username and password, save to disk.

    Args:
        username (str): username
        password (str): password
    """
    global config
    config.read(INI_PATH, encoding="utf-8")
    if username:
        config["base"]["username"] = username
    if password:
        config["base"]["password"] = password
    if username or password:
        with open(INI_PATH, "w", encoding="utf-8") as f:
            config.write(f)
        if osp.exists(osp.join(ROOT, "jw_cookies.pkl")):
            os.remove(osp.join(ROOT, "jw_cookies.pkl"))
        if osp.exists(osp.join(ROOT, "v_cookies.pkl")):
            os.remove(osp.join(ROOT, "v_cookies.pkl"))


def get_username_and_password():
    """Get username and password, read from disk.

    Returns:
        (str, str): (username, password)
    """
    global config
    config.read(INI_PATH, encoding="utf-8")
    return config["base"]["username"], config["base"]["password"]


def update_other(browser=None, driver_path=None):
    global config
    config.read(INI_PATH, encoding="utf-8")
    if browser:
        config["base"]["browser"] = browser
    if driver_path:
        config["base"]["driver"] = driver_path
    with open(INI_PATH, "w", encoding="utf-8") as f:
        config.write(f)


def main():
    usage = r"""Usage:
    ruclogin [--browser=<browser>] [--username=<username>] [--password=<password>] [--driver=<driver_path>]
    
Options:
    --browser=<browser>     browser(Chrome/Edge/Chromium)
    --username=<username>   username
    --password=<password>   password
    --driver=<driver_path>  driver_path
    """
    args = docopt.docopt(usage)
    browser = args["--browser"] or input(
        "browser(Chrome/Edge/Chromium), type enter to skip: "
    )
    if browser not in ["Chrome", "Edge", "Chromium", ""]:
        raise ValueError("browser must be Chrome, Edge or Chromium")
    username = args["--username"] or input("username, type enter to skip: ")
    password = args["--password"] or input("password, type enter to skip: ")
    driver_path = args["--driver"] or input("driver_path, type enter to skip: ")
    update_username_and_password(username, password)
    update_other(browser, driver_path)
    print("\nConfig {} updated:".format(INI_PATH))
    print(
        "\tUsername: {}\n\tPassword: {}\n\tBrowser: {}\n\tdriver_path: {}".format(
            config["base"]["username"],
            config["base"]["password"],
            config["base"]["browser"],
            config["base"]["driver"],
        )
    )
    print("\n")
    isTest = input("Test login? (Y/n): ")
    if isTest.lower() in ["y", "yes", ""]:
        try:
            v_cookies = get_cookies(domain="v")
            v_msg = check_cookies(v_cookies, domain="v")
            jw_cookies = get_cookies(domain="jw")
            jw_msg = check_cookies(jw_cookies, domain="jw")
            print(v_msg, "from v.ruc.edu.cn")
            print(jw_msg, "from jw.ruc.edu.cn")
        except Exception as e:
            print(e)
            print("Login failed")


if __name__ == "__main__":
    main()
    # domain = "v"
    # cookies = get_cookies(cache=False, domain=domain)
    # print(cookies)
    # success = check_cookies(cookies, domain=domain)
    # print(success)
