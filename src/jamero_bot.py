'''
Created on Jun 27, 2019

@author: ZeMota
'''
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def get_round_state(tourn_url, driver):
    driver.get(test_tourn_url)
    table_xp_query = '//*[@class="roundColumn"]'
    rounds = driver.find_elements_by_xpath(table_xp_query)
    n_rounds = len(rounds)
    matchups = rounds[-1].find_elements_by_xpath('.//*[@class="matchup"]')
    round_status = []
    for match in matchups:
        match_info = match.text.split('\n')
        match_map = {}
        match_map[match_info[1]] = -1
        match_map[match_info[2]] = -1
        match_winner = match.find_elements_by_xpath('.//*[@class="competitor victor win "]')
        if len(match_winner) > 0:
            winner_trn = match_winner[0].text
            loser_trn = match.find_elements_by_xpath('.//*[@class="competitor loss "]')[0].text
            match_map[winner_trn] = 1
            match_map[loser_trn] = 0
        round_status.append(match_map)
    return n_rounds, round_status
    
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
#chrome_options.add_argument("--headless")
chrome_options.add_argument("--window-size=1920x1080")
chrome_options.add_argument("--enable-javascript")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

chrome_driver = "/home/pjdrm/workspace/TeamRocketSpy/chromedriver"
driver = webdriver.Chrome(chrome_options=chrome_options, executable_path=chrome_driver)
test_tourn_url = "https://silph.gg/tournaments/host/4ctb"
print("getting url")
n_rounds, round_status = get_round_state(test_tourn_url, driver)
print("Round %d\n%s"%(n_rounds, str(round_status)))
driver.close()
print("all done")
    