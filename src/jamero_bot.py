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
import pytz
import tzlocal
from datetime import datetime as dt
from dateutil.parser import parse
from asyncio.tasks import sleep
from selenium.common.exceptions import NoSuchElementException

NEW_ROUND_ICON = 'https://cdn4.iconfinder.com/data/icons/sports-rounded-flat/512/boxing-512.png'
SA_LOGIN_PAGE = 'https://thesilphroad.com/authenticate?app=arena'
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
        self.local_timezone = tzlocal.get_localzone()
        self.tsr_user = config["tsr_user"]
        self.tsr_pass = config["tsr_pass"]
        self.towns = config["towns"]
        self.season = config["season"]
        self.log_file = log_file
        self.check_frequency = config["check_frequency"]
        self.bot_token = config["bot_token"]
        self.bot = commands.Bot(command_prefix="$", description='UnownBot')
        self.bot.remove_command("help")
        self.run_discord_bot()
        
    def parse_date(self, date_str):
        try:
            date_str = date_str.replace("PDT", "-0700") #TODO: better handling of timezones. Now its converting PDT to UTC
            date_obj = parse(date_str)
            date_obj = date_obj.replace(tzinfo=pytz.utc).astimezone(self.local_timezone)
            month = int(date_obj.strftime("%m"))
            day = int(date_obj.strftime("%d"))
            hour = int(date_obj.strftime("%I"))
            minute = int(date_obj.strftime("%M"))
            period = date_obj.strftime("%p").lower()
            return month, day, hour, minute, period
        except ValueError:
            return None, None, None, None, None, None
    
    async def click_button(self, xp_query, browser=None):
        if browser is None:
            browser = self.browser
        button = browser.find_elements_by_xpath(xp_query)
        i = 0
        while len(button) == 0:
            await asyncio.sleep(1)
            button = browser.find_elements_by_xpath(xp_query)
            if i == 5:
                print("ERROR: cant click button in %s"%browser.current_url)
                return
            i += 1
        button[0].click()
        
    async def select_option_index(self, xp_query, option_i):
        sel_elemns = self.browser.find_elements_by_xpath(xp_query)
        i = 0
        while len(sel_elemns) == 0:
            await asyncio.sleep(1)
            sel_elemns = self.browser.find_elements_by_xpath(xp_query)
            if i == 5:
                print("ERROR: cant find selection in %s"%self.browser.current_url)
                return
            i += 1
        
        options = Select(sel_elemns[0])
        options.select_by_index(option_i)
        
    async def select_option_val(self, xp_query, option_val):
        sel_elemns = self.browser.find_elements_by_xpath(xp_query)
        i = 0
        while len(sel_elemns) == 0:
            await asyncio.sleep(1)
            sel_elemns = self.browser.find_elements_by_xpath(xp_query)
            if i == 5:
                print("ERROR: cant find selection in %s"%self.browser.current_url)
                return
            i += 1
        
        options = Select(sel_elemns[0])
        try:
            options.select_by_visible_text(option_val)
            return 1
        except NoSuchElementException:
            return None
    
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
    
    async def open_checkin(self):
        upcoming_tourn_xp = '//*[@class="tournamentWrap panel panel-dark "][.//*[@style="color:orange;font-size: 16px;line-height: 7px;"]]'
        next_upcoming_tourn = self.browser.find_elements_by_xpath(upcoming_tourn_xp)[0]
        host_page_bt_xp = './/*[@class="btn btn-success"]'
        await self.click_button(host_page_bt_xp, next_upcoming_tourn)
        checkin_bt_xp = '//*[@id="content"]/div/div/div[2]/div/a'
        await self.click_button(checkin_bt_xp)
        self.browser.switch_to.alert.accept()
        checkin_code_box_xp = '//*[@id="content"]/div[2]/div/div[3]/div/code'
        checkin_code = self.browser.find_elements_by_xpath(checkin_code_box_xp)[0].text
        tourn_id = self.browser.current_url.split("t/")[1][:-8]
        return checkin_code, tourn_id

    async def create_tourn(self,
                           lobby_name,
                           tournament_type,
                           tourn_name,
                           month,
                           day,
                           hour,
                           min,
                           period):
        await self.go_to_admin_page()
        host_tourn_xp = '//*[@id="content"]/div[2]/div/div/div/div/div[1]/a'
        await self.click_button(host_tourn_xp)
        tourn_type_options_xp = '//*[@id="TournamentTournamentTypeId"]'
        succ = await self.select_option_val(tourn_type_options_xp, tournament_type)
        if succ is None: #Tournament type does not exist in page
            return None, None
        event_title_xp = '//*[@id="TournamentName"]'
        event_title = self.browser.find_elements_by_xpath(event_title_xp)[0]
        event_title.send_keys(tourn_name)
        visible_button_xp = '//*[@id="showTournamentOnMapCheckbox"]'
        await self.click_button(visible_button_xp)
        month_xp = '//*[@id="TournamentStartTimeMonth"]'
        await self.select_option_index(month_xp, month-1)
        day_xp = '//*[@id="TournamentStartTimeDay"]'
        await self.select_option_index(day_xp, day-1)
        year_xp = '//*[@id="TournamentStartTimeYear"]'
        await self.select_option_index(year_xp, 1) #TODO: add logic to process year
        hour_xp = '//*[@id="TournamentStartTimeHour"]'
        await self.select_option_index(hour_xp, hour-1)
        min_xp = '//*[@id="TournamentStartTimeMin"]'
        await self.select_option_index(min_xp, MINUTE_INDEX[min])
        period_xp = '//*[@id="TournamentStartTimeMeridian"]'
        if period == "am":
            period = 0
        else:
            period = 1
        await self.select_option_index(period_xp, period)
        create_tourn_button_xp = '//*[@id="createTournamentForm"]/div[16]/button'
        await self. click_button(create_tourn_button_xp)
        await self.go_to_admin_page()
        checkin_code, tourn_id = await self.open_checkin()
        return checkin_code, tourn_id
        
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
        round_embed.set_author(name="Round "+str(n_rounds)+" status", icon_url=NEW_ROUND_ICON)
        return round_embed
    
    def get_town(self, lobby_channel_name):
        return lobby_channel_name.split("-")[0]
    
    def is_valid_tourn_name(self, tourn_name):
        return True
        
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
    
    async def update_lobby_round_status(self, tourn_name):
        lobby_chan_id = self.tourn_lobby_dict[tourn_name]["chan_id"]
        tourn_url = self.tourn_lobby_dict[tourn_name]["url"]
        lobby_channel = self.bot.get_channel(lobby_chan_id)
        print("Round Status %s" % lobby_channel.name)
        round_i, round_status = self.get_round_state(tourn_url)
        pairings_embed = self.get_pairings_emb(round_i, round_status)
        new_round, round_pin = await self.is_new_round(round_i, lobby_channel)
        if new_round:
            print("Shouting new round!")
            await lobby_channel.send(self.tourn_lobby_dict[tourn_name]["tag_role"]+" new round is up!")
            if round_pin is not None:
                await round_pin.delete()
            msg = await lobby_channel.send(embed=pairings_embed)
            await msg.pin()
        else:
            await round_pin.edit(embed=pairings_embed)
        return new_round
          
    async def check_round_status(self):
        while True:
            for tourn_name in self.tourn_lobby_dict:
                if self.tourn_lobby_dict[tourn_name]["status"] == "ongoing":
                    await self.update_lobby_round_status(tourn_name)
            await asyncio.sleep(self.check_frequency)
    
    async def go_to_admin_page(self):
        admin_button_xp = '//*[@id="navbar"][.//*[@src="/img/icon-tournament-white.png"]]/ul/li[1]/a'
        await self.click_button(admin_button_xp)
        comm_button_xp = '//*[@id="navbar"]/ul/li[1]/ul/li[2]/a'#'//*[@id="navbar"]/ul/li[1]/ul/li[3]'
        await self.click_button(comm_button_xp)
    
    def is_tourn_lobby(self, channel_name):
        split_str = channel_name.split("-")
        if len(split_str) == 0:
            return False
        if split_str[0] not in self.towns:
            return False
        
        if not channel_name.endswith("tcs") and\
           not channel_name.endswith("annoucements"):
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
    
    async def get_tourn_lobbies(self):
        tourn_lobbies = {}
        for channel in self.bot.get_all_channels():
            if hasattr(channel, 'send'): #hack to avoid categories
                if self.is_tourn_lobby(channel.name):
                    tourn_lobbies[channel.name] = channel.id
        return tourn_lobbies
    
    def get_tourn_info(self, xp_query, tourn_info_dict, tourn_status):
        tourn_panels = self.browser.find_elements_by_xpath(xp_query)
        for panel in tourn_panels:
            tourn_url = panel.find_elements_by_xpath('.//*[@class="btn btn-success"]')[0].get_attribute("href")
            tourn_name = panel.find_elements_by_xpath('.//*[@class="tournamentName"]')[0].text.lower()
            tourn_info_dict[tourn_name] = {}
            tourn_info_dict[tourn_name]["url"] = tourn_url
            tourn_info_dict[tourn_name]["status"] = tourn_status
            
    async def load_tourn_info(self):
        await self.go_to_admin_page()
        tourn_info = {}
        ongoing_tourn_xp = '//*[@class="tournamentWrap panel panel-dark active"][.//*[@style="color:green;font-size: 16px;line-height: 7px;"]]'
        self.get_tourn_info(ongoing_tourn_xp, tourn_info, "ongoing")
        ongoing_tourn_xp = '//*[@class="tournamentWrap panel panel-dark active"][.//*[@style="color:orange;font-size: 16px;line-height: 7px;"]]'
        self.get_tourn_info(ongoing_tourn_xp, tourn_info, "await-start")
        return tourn_info
    
    async def set_lobby_url_map(self):
        self.tourn_lobby_dict = await self.load_tourn_info()
        self.tag_role_dict = self.get_tourn_lobby_tag_roles()
        for tourn_name in self.tourn_lobby_dict:
            for channel_name in self.tourn_lobbies_channels:
                town = self.get_town(channel_name)
                league = channel_name.split(town+"-")[0].replace("-", " ")
                if town in tourn_name and league in tourn_name:
                    chan_id = self.tourn_lobbies_channels[channel_name]
                    tag_role = "TEST"#self.tag_role_dict[town]
                    self.tourn_lobby_dict[tourn_name]["tag_role"] = tag_role
                    self.tourn_lobby_dict[tourn_name]["chan_id"] = chan_id
                    break
    def add_tourn(self, tourn_name, url, chan_id, tag_role, tourn_status):
        self.tourn_lobby_dict[tourn_name] = {"url": url, "chan_id": chan_id, "tag_role": tag_role, "status": tourn_status}
        
    async def get_tourn_schedule_pin(self, lobby_chan):
        pins = await lobby_chan.pins()
        for msg in pins:
            if msg.content.startswith("TOURNAMENT SCHEDULE"):
                return msg
        return None
            
    async def add_tounr_schedule(self, lobby_chan, turn_type, date_str):
        tourn_schedule_pin = await self.get_tourn_schedule_pin(lobby_chan)
        new_tourn_str = turn_type+" ("+date_str+", no link yet)"
        if tourn_schedule_pin is None:
            new_schedule = "TOURNAMENT SCHEDULE\n**1.** "+new_tourn_str
            msg = await lobby_chan.send(new_schedule)
            await msg.pin()
        else:
            n_tourn = len(tourn_schedule_pin.content.split("\n"))
            new_schedule =tourn_schedule_pin.content+"\n**"+str(n_tourn)+".** "+new_tourn_str
            await tourn_schedule_pin.edit(content=new_schedule)
        
    def run_discord_bot(self):
        @self.bot.event
        async def on_ready():
            print('Jamero Ready')
            self.tourn_lobbies_channels = await self.get_tourn_lobbies()
            #await self.sa_login()
            print('Logged in Silph Arena')
            #await self.set_lobby_url_map()
            print('Got tournament info')
            #self.bot.loop.create_task(self.check_round_status())
        
        @self.bot.command(pass_context=True)
        async def help(ctx, cmd=None):
            if cmd == "ct":
                doc_str = "$ct <lobby_name> <tournament_type> <tourn_name> <date_str>\n\tdate_str: the date format is <mm>/<dd> <hh>:<mm><period>\n\nCreates a Silph Arena tournament."
            elif cmd == "nr":
                doc_str = "$nr\n\nAnnounces a new round is up in a tournament"
            elif cmd is None:
                doc_str = "Use $help <command> for more info on a command\n\n**Commands**\nct, nr"
            else:
                doc_str = "Unown command "+cmd
            await ctx.message.channel.send(doc_str)
        
        @self.bot.command(pass_context=True)
        async def nr(ctx):
            print("Received new round command")
            new_round = await self.update_lobby_round_status(ctx.message.channel.id)
            if not new_round:
                await ctx.message.channel.send(ctx.message.author.mention+" Please do not use this command if a new round is NOT up")
                
        @self.bot.command(pass_context=True)
        async def schedule_tourn(ctx,
                                 lobby_name,
                                 tourn_name,
                                 date_str): #$schedule_tourn pallet-rising-star-2 "Freestyle" "July 7, 05:00 pm PDT"
                    print("Got schedule_tourn command")
                    if lobby_name not in self.tourn_lobbies_channels:
                        await ctx.message.channel.send("**ERROR**: Invalid lobby channel `"+lobby_name+"`")
                        return
                    
                    if not self.is_valid_tourn_name(tourn_name):
                        await ctx.message.channel.send("**ERROR**: Invalid tournament name `"+tourn_name+"`")
                        return
                    
                    month, day, hour, min, period = self.parse_date(date_str)
                    if month is None:
                        await ctx.message.channel.send("**ERROR**: Invalid `date`. The format must be the following: `<mm>/<dd> <hh>:<mm> <period> <timezone>`")
                    elif min not in MINUTE_INDEX:
                        error_msg = "**ERROR**: Invalid minute value in `date`. Valid minute values are: "
                        mins_list = list(MINUTE_INDEX.keys())
                        mins_list.sort()
                        for valid_min in mins_list:
                            error_msg += str(valid_min)+", "
                        error_msg = error_msg[:-2]
                        await ctx.message.channel.send(error_msg)
                    else:
                        chan_id = self.tourn_lobbies_channels[lobby_name]
                        lobby_chan = self.bot.get_channel(chan_id)
                        await self.add_tounr_schedule(lobby_chan, tourn_name, date_str)
                        await ctx.message.channel.send("Success! %s (%s) scheduled for %s"%(tourn_name, date_str, lobby_name))
                    
        @self.bot.command(pass_context=True)
        async def ct(ctx,
                     lobby_name,
                     tournament_type,
                     tourn_name,
                     date_str):
            print("Got create tournament command")
            if lobby_name not in self.tourn_lobbies_channels:
                await ctx.message.channel.send("**ERROR**: Invalid lobby channel `"+lobby_name+"`")
                return
            tournament_type = tournament_type.title()
            month, day, hour, min, period = self.parse_date(date_str)
            
            if month is None:
                await ctx.message.channel.send("**ERROR**: Invalid `date`. The format must be the following: `<mm>/<dd> <hh>:<mm><period>`")
            elif min not in MINUTE_INDEX:
                error_msg = "**ERROR**: Invalid minute value in `date`. Valid minute values are: "
                mins_list = list(MINUTE_INDEX.keys())
                mins_list.sort()
                for valid_min in mins_list:
                    error_msg += str(valid_min)+", "
                error_msg = error_msg[:-2]
                await ctx.message.channel.send(error_msg)
            else:
                town = self.get_town(lobby_name)
                tourn_name += " ("+town+" "+self.season+" - "+lobby_name.replace(town+"-", "").replace("-", " ")+")"
                '''
                if tourn_name in  self.tourn_lobby_dict:
                    warn_msg = "**WARNING**: tournament `"+\
                                tourn_name+"` already exists and was **NOT** created: <"+\
                                self.tourn_lobby_dict[tourn_name]["url"]+">"
                    await ctx.message.channel.send(warn_msg)
                    return
                
                checkin_code, tourn_id = await self.create_tourn(lobby_name,
                                                                tournament_type,
                                                                tourn_name,
                                                                month,
                                                                day,
                                                                hour,
                                                                min,
                                                                period)
                '''
                checkin_code = "test"
                tourn_id = "test"
                if checkin_code is None: #TODO: allow handling different type of errors
                    await ctx.message.channel.send("**ERROR**: Invalid tournament type `"+tournament_type+"`")
                else:
                    chan_id = self.tourn_lobbies_channels[lobby_name]
                    lobby_chan = self.bot.get_channel(chan_id)
                    url = "https://silph.gg/t/"+tourn_id
                    tag_role = "TEST"#self.tag_role_dict[town]
                    #self.add_tourn(tourn_name, url, lobby_chan, tag_role, "await-start")
                    await self.update_tounr_schedule(lobby_chan, tournament_type, date_str, url, checkin_code)
                    await ctx.message.channel.send("Created tournament:\n\tLobby: %s\n\turl: <%s>\n\tcheck-in code: %s"%(lobby_name, url, checkin_code))
            
        self.bot.run(self.bot_token)
        
        
if __name__ == "__main__":
    bot_config_path = "./jamero_cfg.json"
    with open(bot_config_path) as data_file:    
        bot_config = json.load(data_file)
    JameroBot(bot_config)
        
