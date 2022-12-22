from os import link
import discord
import feedparser
import os.path
from discord.ext import tasks
from discord.ext import commands
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import config
import json
import time

intents = discord.Intents.all()
intents.messages = True
bot = commands.Bot(command_prefix=',', intents = intents)

@bot.event
async def on_ready():
    #check for stored credentials
    #if found, try to auth
    print('We have logged in as {0.user}'.format(bot))
    await loadSubscription()
    
    #if config.stored_username is not None:
        #try_auth(config.stored_username, config.stored_password)
    



@bot.command()
async def addfeed(ctx, url):
    await add_feed(ctx, url, 'fast')

@bot.command()
async def addslow(ctx, url):
    await add_feed(ctx, url, 'slow')

async def add_feed(ctx, url, speed='fast'):
    try:
        #print("blah")
        #print(1)
        feed = url
        #print(list)
        guild = ctx.message.guild
        #print("blah 2")
        if ctx.message.channel_mentions is None:
            channel = ctx.message.channel
        else:
            channel = ctx.message.channel_mentions[0]
        #print("blah 3")
        if ctx.message.role_mentions is None:
            role = []
        else:
            role = ctx.message.role_mentions[0]

        #print(2)
        await add_list(feed, guild, channel, role, True, True, [],speed)
        #print(config.subscribedFeeds)
        #print(1)
        await storeSubscription()
        config.loopcount = 0
        #print(2)
        if subscriptionLoop.is_running():
            subscriptionLoop.restart()
        else:
            await subscriptionLoop.start()

        await ctx.send("Subscription created successfully")
    except Exception as e:
        print(str(e))
        await ctx.send("Uncaught Error"+ str(e))


async def add_list(feed, guild, channel, role, active, firstRun, entryCache, speed):
    listdef = {"feed": feed, "guild": guild, "channel": channel, "role": role, "firstRun": firstRun, "active": active, "entryCache": entryCache, "speed":speed}
    
    if config.subscribedFeeds is []:
        config.subscribedFeeds.append(listdef)
    elif feed in [x['feed'] for x in config.subscribedFeeds]:
        config.subscribedFeeds = [listdef if x['feed'] == feed else x for x in config.subscribedFeeds]
    else:
        config.subscribedFeeds.append(listdef)

async def update_list(list):
    if config.subscribedFeeds is []:
        config.subscribedFeeds.append(list)
    elif list['feed'] in [x['feed'] for x in config.subscribedFeeds]:
        config.subscribedFeeds = [list if x['feed'] == list['feed'] else x for x in config.subscribedFeeds]
    else:
        config.subscribedFeeds.append(list)

async def removelist(feed):
    config.subscribedFeeds = [x for x in config.subscribedFeeds if not x['feed'] == feed]

@bot.command()
async def stop(ctx, temp=None):
    config.active = False
    await storeSubscription()
    subscriptionLoop.stop()
    config.loopcount = 0
    await ctx.send("Loop Stopped")

@bot.command()
async def restart(ctx, temp=None):
    config.active = True
    await storeSubscription()
    config.loopcount = 0
    if subscriptionLoop.is_running():
        subscriptionLoop.restart()
    else:
        await subscriptionLoop.start()
    await ctx.send("Loop restarted")

@bot.command()
async def viewfeeds(ctx, temp=None):
    guild = ctx.message.guild

    filtered = [x for x in config.subscribedFeeds if x['guild'] == guild]
    message = "Current Feeds for this server: \n"
    for list in config.subscribedFeeds:
        message += "URL: {0} Guild: {1} Channel: {2} role: {3} Speed: {4}\n".format(list['feed'], list['guild'].name, list['channel'].name, list['role'].name, list['speed'])
    await ctx.send(message)


@bot.command()
async def removefeed(ctx, arg):
    await removelist(arg)
    await storeSubscription()
    
    await ctx.send("Successfully unsubscribed from feed")

async def strip_tags(html):
    soup = BeautifulSoup(html, "html.parser")

    return soup.get_text()

#set loop start
@tasks.loop(seconds = 180)
async def subscriptionLoop():   
    for list in config.subscribedFeeds:
        if config.loopcount is 0 or list['speed'] is 'fast':
            messages2 = await getFeedItems(list, 0)
            if messages2 is not None:
                for m in messages2:
                    discordMessage = "{0}\n{1}".format(list['role'].mention, m)
                    await list['channel'].send(discordMessage)
    config.loopcount = (config.loopcount + 1) % 20
    await storeSubscription()



async def getFeedItems(list, offset = 0):
    try:
        if list['firstRun']:
            limit = 1

        
        feed = await getFeed(list)
        #= await apiCall("/list/{0}/feed".format(list['guid']), "GET",payload)
        #print("data received from feed")
        #got data
        #print(feed)
        if 'Error' in feed:
            #print("Error received")
            return ["Error in results"]
        #print(feed)
        messages = []

        #if temp list is not empty
        if feed is not None:
            feed.reverse()
            for entry in feed:
                #build messages and store
                message = "**{0}**\n".format(entry['title'])
                if "description" in entry:
                    content = await strip_tags(entry['description'])
                elif 'content' in entry:
                    content = await strip_tags(entry['content'])
                else:
                    content = ""
                message += "{0}\n".format(content)
                message += "{0}".format(entry['link'])
                messages.append(message)
                #push chapter to memory
                list['entryCache'].insert(0,entry['link'])
            #trim memory
            del list['entryCache'][10:]

        if list['firstRun'] == True:
            list['firstRun'] = False
        
        await update_list(list)

        #return message strings
        return messages
    except Exception as e:
        print(str(e))
        return []

async def getFeed(list):
    try:
        items = []
        if list['firstRun'] is True:
            max = 1
        else:
            max = 10
        d = feedparser.parse(list['feed'])
        for entry in d.entries[0:max]:
            if 'link' in entry and entry['link'] in list['entryCache']:
                #print(entry)
                break
            else:
                items.append(entry)
        return items
    except Exception as e:
        print(str(e))
        return []

async def loadSubscription():
    if os.path.isfile('subscription.json'):
        with open('subscription.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            if 'subscribedFeeds' in data:
                await deserializeList(data['subscribedFeeds'])
            else:
                config.subscribedFeeds = []

            print('subscription loaded')
            if subscriptionLoop.is_running():
                subscriptionLoop.restart()
            else:
                await subscriptionLoop.start()



async def storeSubscription():

    #if config.active is True:
    data = {"subscribedFeeds": await serializeLists()}
    with open('subscription.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    

async def serializeLists():
    listjson = []
    for x in config.subscribedFeeds:
        listjson.append({"feed": x['feed'], "guild": x['guild'].id, "channel": x['channel'].id, "role": x['role'].id, "firstRun": x['firstRun'], "active": x['active'], "entryCache": x['entryCache'], "speed": x['speed'] })
    return listjson

async def deserializeList(obj):
    config.subscribedFeeds = []
    for x in obj:
        guild = bot.get_guild(x['guild'])
        await add_list(x['feed'], guild, bot.get_channel(x['channel']), guild.get_role(x['role']), x['active'], x['firstRun'], x['entryCache'], x['speed'] if 'speed' in x else 'fast')


    
if os.path.isfile('secret.json'):
        with open('secret.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            config.secret = data['token']


bot.run(config.secret)
