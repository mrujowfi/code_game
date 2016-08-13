#coding=utf-8
from selenium import webdriver
import time

global driver


def driver_init():
    global driver
    driver = webdriver.Chrome()


def driver_quit():
    global driver
    driver.quit()


def driver_login():
    global driver

    driver.get('http://www.qlcoder.com/auth/login')
    time.sleep(1)
    driver.maximize_window()
    time.sleep(1)
    driver.find_element_by_xpath("//input[@id='email']").send_keys('mrujowfi@163.com')
    time.sleep(1)
    driver.find_element_by_xpath("//input[@id='password']").send_keys('kzchmwdi10')
    time.sleep(1)
    driver.find_element_by_xpath("//input[@id='login-submit']").click()
    time.sleep(3)

def scan():
    global driver

    first_mission = 0x751e
    failed_count = 0

    while True:
        print 'lbg now %x' % first_mission
        driver.get('http://www.qlcoder.com/task/%x' % first_mission)


        content = ''
        while content == '':
            time.sleep(1)
            print 'lbg wait'
            content = driver.find_element_by_xpath("//body").text

        if content.__contains__(u'404 Not Found'):
            failed_count += 1
            if failed_count > 20:
                print 'lbg break %x' % first_mission
                break
            else:
                print 'lbg continue %x' % first_mission
                first_mission += 1
                continue
        else:
            failed_count = 0

        if content.__contains__(u'奖励规则:'):
            print 'http://www.qlcoder.com/task/%x' % first_mission
            time.sleep(10)
        print 'lbg next %x' % first_mission
        first_mission += 1


if __name__ == '__main__':
    driver_init()
    driver_login()
    scan()
    driver_quit()