'''
Created on Jun 27, 2019

@author: ZeMota
'''
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.select import Select
from discord.ext import commands
import asyncio
import discord
import json
from datetime import datetime as dt
from asyncio.tasks import sleep

SA_LOGIN_PAGE = 'https://thesilphroad.com/authenticate?app=arena'
TOURNAMENT_TYPES = {"unranked": 0, "ranked": 1, "oc": 2, "nc": 3}
MINUTE_INDEX = {0: 0, 15: 1, 30: 2, 45: 3}

WIN_EMOJI = '✅'
LOSS_EMOJI = '❌'
GLOVE_EMOJI = '🥊'
SIDEBAR_EMBED_COLOR = 0x5c7ce5

class JameroBot():
    
    def __init__(self, config,
                       log_file="./jamero_log.txt"):
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920x1080")
        chrome_options.add_argument("--enable-javascript")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        self.browser = webdriver.Chrome(chrome_options=chrome_options, executable_path=config["chrome_driver_path"])
        self.browser.implicitly_wait(3)
        
        self.tourn_lobby_dict = None
        self.tsr_user = config["tsr_user"]
        self.tsr_pass = config["tsr_pass"]
        self.towns = config["towns"]
        self.log_file = log_file
        self.check_frequency = config["check_frequency"]
        self.bot_token = config["bot_token"]
        self.bot = commands.Bot(command_prefix="$", description='UnownBot')
        self.bot.remove_command("help")
        self.run_discord_bot()
    
    async def click_button(self, xp_query):
        button = self.browser.find_elements_by_xpath(xp_query)
        i = 0
        while len(button) == 0:
            await asyncio.sleep(1)
            button = self.browser.find_elements_by_xpath(xp_query)
            if i == 5:
                print("ERROR: cant click button in %s"%self.browser.current_url)
                return
            i += 1
        button[0].click()
    
    async def sa_login(self):
        self.browser.get(SA_LOGIN_PAGE)
        log_button_xp = '//*[@id="homepageContent"]/div[1]/div/a[1]'
        await self.click_button(log_button_xp)
        actions = ActionChains(self.browser)
        actions.send_keys(self.tsr_user)
        actions.send_keys(Keys.TAB)
        actions.send_keys(self.tsr_pass)
        actions.send_keys(Keys.TAB)
        actions.send_keys(Keys.ENTER)
        actions.perform()
        allow_button_xp = '/html/body/div[3]/div/div[2]/form/div/input[1]'
        await self.click_button(allow_button_xp)
        
    def get_round_state(self, tourn_url):
        self.browser.get(tourn_url)
        table_xp_query = '//*[@class="roundColumn"]'
        rounds = self.browser.find_elements_by_xpath(table_xp_query)
        n_rounds = len(rounds)
        matchups = rounds[-1].find_elements_by_xpath('.//*[@class="matchup"]')
        round_status = {}
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
            match_id = int(match_info[0][1:])
            round_status[match_id] = match_map
        return n_rounds, round_status
    
    def get_pairings_emb(self, n_rounds, round_status):
        time_stamp = dt.now()
        round_embed = discord.Embed(color=SIDEBAR_EMBED_COLOR, timestamp=time_stamp)
        pairings_str = ""
        for match_i in range(1, len(round_status.keys())+1):
            pairings_str += "**"+str(match_i)+"**. "
            res_str = ""
            for i, trainer in enumerate(round_status[match_i]):
                pairings_str += trainer
                if round_status[match_i][trainer] == 1:
                    res_str += "1-"
                elif round_status[match_i][trainer] == 0:
                    res_str += "0-"
                
                if i == 0:
                    pairings_str += " *vs.* "
                else:
                    if len(res_str) > 0:
                        res_str = " ("+res_str[:-1]+")"
                    pairings_str += res_str+"\n"
        pairings_str = pairings_str[:-1]
        round_embed.add_field(name="Pairings", value=pairings_str, inline=False)
        round_embed.set_author(name="Round "+str(n_rounds)+" status", icon_url="https://cdn4.iconfinder.com/data/icons/sports-rounded-flat/512/boxing-512.png")
        return round_embed
    
    def get_town(self, lobby_channel_name):
        return lobby_channel_name.split("-")[0]
        
    async def is_new_round(self, round_i, lobby_chan):
        pins = await lobby_chan.pins()
        for msg in pins:
            if msg.author.id == self.bot.user.id:
                embed = msg.embeds[0]
                if embed.author.name.split(" ")[1] == str(round_i):
                    return False, msg
                else:
                    return True, msg
        return True, None
    
    async def update_lobby_round_status(self, lobby_chan_id):
        tourn_url = self.tourn_lobby_dict[lobby_chan_id]["tourn_url"]
        lobby_channel = self.bot.get_channel(lobby_chan_id)
        print("Round Status %s" % lobby_channel.name)
        round_i, round_status = self.get_round_state(tourn_url)
        pairings_embed = self.get_pairings_emb(round_i, round_status)
        new_round, round_pin = await self.is_new_round(round_i, lobby_channel)
        if new_round:
            print("Shouting new round!")
            await lobby_channel.send(self.tourn_lobby_dict[lobby_channel.id]["tag_role"]+" new round is up!")
            if round_pin is not None:
                await round_pin.delete()
            msg = await lobby_channel.send(embed=pairings_embed)
            await msg.pin()
        else:
            await round_pin.edit(embed=pairings_embed)
        return new_round
          
    async def check_round_status(self):
        #tourn_url = "https://silph.gg/tournaments/host/4ctb"
        #lobby_channel = self.bot.get_channel(594223228625354752)
        #n_rounds = 4
        #round_status = {1: {'IHaveLigma': 1, 'AgustinH': 0}, 2: {'DctrBanner': 0, 'FullMetalHobo': 1}, 3: {'Prolonova': 1, 'fugimaster24': 0}, 4: {'Jmillz113': 0, 'DrazenP': 1}, 5: {'ZeMota': 1, 'Ljazz7': 0}, 6: {'lrmistle': -1, 'gnomegfx': -1}, 7: {'JarramDM': 0, 'Dancobi': 1}, 8: {'Tigger226': 0, '13Malong13': 1}, 9: {'Rodiosvaldo': -1, 'Galdalf1': -1}}
        while True:
            for lobby_chan_id in self.tourn_lobby_dict:
                await self.update_lobby_round_status(lobby_chan_id)
            await asyncio.sleep(self.check_frequency)
    
    async def go_to_admin_page(self):
        admin_button_xp = '//*[@id="navbar"][.//*[@src="/img/icon-tournament-white.png"]]/ul/li[1]/a'
        await self.click_button(admin_button_xp)
        comm_button_xp = '//*[@id="navbar"]/ul/li[1]/ul/li[3]'#'//*[@id="navbar"]/ul/li[1]/ul/li[2]/a'
        await self.click_button(comm_button_xp)
    
    async def get_tourn_info(self):
        await self.go_to_admin_page()
        tourn_info = {}
        ongoing_tourn_xp = '//*[@class="tournamentWrap panel panel-dark active"][.//*[@style="color:green;font-size: 16px;line-height: 7px;"]]'
        tourn_panels = self.browser.find_elements_by_xpath(ongoing_tourn_xp)
        for panel in tourn_panels:
            tourn_url = panel.find_elements_by_xpath('.//*[@class="btn btn-success"]')[0].get_attribute("href")
            tourn_name = panel.find_elements_by_xpath('.//*[@class="tournamentName"]')[0].text.lower()
            tourn_info[tourn_name] = tourn_url
        return tourn_info
        
    def is_tourn_lobby(self, channel_name, tourn_name):
        if not channel_name.endswith("tcs") and\
           not channel_name.endswith("annoucements") and\
           channel_name in tourn_name:
            return True
        else:
            return False
    
    def get_tourn_lobby_tag_roles(self):
        tag_role_dict = {}
        guild_id = self.bot.guilds[0].id #HACK: assumes bot is only in one server
        roles = self.bot.get_guild(guild_id).roles
        for role in roles:
            role_name = role.name.lower()
            if role_name in self.towns:
                tag_role_dict[role_name] = "<@&"+str(role.id)+">"
        return tag_role_dict
        
    async def set_lobby_url_map(self):
        tourn_info = await self.get_tourn_info()
        all_channels = {}
        for channel in self.bot.get_all_channels():
                if hasattr(channel, 'send'): #hack to avoid categories
                    all_channels[channel.name] = channel.id
        
        self.tourn_lobby_dict = {}
        tag_role_dict = self.get_tourn_lobby_tag_roles()
        for tourn_url in tourn_info:
            for channel_name in all_channels:
                town = self.get_town(channel_name)
                if self.is_tourn_lobby(channel_name, tourn_url):
                    chan_id = all_channels[channel_name]
                    tag_role = tag_role_dict[town]
                    self.tourn_lobby_dict[chan_id] = {"tourn_url": tourn_info[tourn_url],
                                                      "tag_role": tag_role}
                    break
        
    def run_discord_bot(self):
        @self.bot.event
        async def on_ready():
            print('Jamero Ready')
            await self.sa_login()
            print('Logged in Silph Arena')
            await self.set_lobby_url_map()
            print('Got tournament info')
            #self.bot.loop.create_task(self.check_round_status())
        
        @self.bot.command(pass_context=True)
        async def nr(ctx):
            print("Received new round command")
            new_round = await self.update_lobby_round_status(ctx.message.channel.id)
            if not new_round:
                await ctx.message.channel.send(ctx.message.author.mention+" Please do not use this command if a new round is NOT up")
            
        self.bot.run(self.bot_token)
        
        
if __name__ == "__main__":
    bot_config_path = "./jamero_cfg.json"
    with open(bot_config_path) as data_file:    
        bot_config = json.load(data_file)
    JameroBot(bot_config)
        
