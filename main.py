import discord
import discord.voice_client
import numpy as np
import json
import random
import asyncio

import youtube_dl
from discord.ext import commands
import requests
import pymongo
from pymongo import MongoClient
from decouple import config
from threading import Thread
import time
from discord.utils import get
from discord import FFmpegPCMAudio
from discord import TextChannel

LEADERBOARD = "LeaderBoard"

client = commands.Bot(command_prefix='!')
cluster = MongoClient(
    f"mongodb://127.0.0.1:27017/?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+1.5.4")
db = cluster["QuizDB"]


@client.event
async def on_ready():
    print('Bot is working')


difficult = {"hard": 3, "medium": 2, "easy": 1}


@client.command()
async def leaderboard(ctx, mode="Hard", page=1):
    difficulty = mode.lower()
    leader_board = list(
        db[f"{LEADERBOARD}_{difficulty}_{ctx.message.guild.id}"].find({}).sort("score", pymongo.DESCENDING))
    msg = ""
    size = len(leader_board)
    if page > size / 10 + 1:
        await ctx.send("Format error, try : !AmimeQuiz <Hard | Medium | Easy> <page (1 or 2)>")
        return

    start_index = 10 * (page - 1)
    end_index = start_index + 10
    if end_index > size:
        end_index = size

    for i in range(start_index, end_index):
        msg += "**" + str(i + 1) + "**" + ". " + '{0:45}'.format(leader_board[i]["name"]) + "         " + \
               str(leader_board[i]["score"]) + "\n"

    embed = discord.Embed(title="Anime Quiz LeaderBoard " + "[" + mode.upper() + "]", description=msg,
                          color=discord.Colour.blue())
    embed.set_author(name=ctx.guild, icon_url=ctx.guild.icon_url)
    await ctx.send("", embed=embed)


def update_collection(Score, ctx, collection_name):
    if Score > 0:
        list_board = list(db[collection_name].find({}).sort("score", pymongo.DESCENDING))
        if len(list_board) < 20:
            if len(list(db[collection_name].find({"name": ctx.message.author.name, "score": Score}))) == 0:
                db[collection_name].insert_one({"name": str(ctx.message.author.name), "score": Score})
        elif list_board[19]["score"] < Score:
            if len(list(db[collection_name].find({"name": ctx.message.author.name, "score": Score}))) == 0:
                db[collection_name].delete_one(list_board[19])
                db[collection_name].insert_one({"name": str(ctx.message.author.name), "score": Score})


@client.command(pass_context=True)
@commands.cooldown(1, 15, commands.BucketType.guild)
async def AnimeQuiz(ctx, mode="Hard"):
    try:
        guild_id = ctx.message.guild.id
        if len(list(db["Guilds"].find({"id": int(guild_id)}))) == 0:
            db.create_collection(f"{LEADERBOARD}_easy_{str(guild_id)}")
            db.create_collection(f"{LEADERBOARD}_medium_{str(guild_id)}")
            db.create_collection(f"{LEADERBOARD}_hard_{str(guild_id)}")
            db["Guilds"].insert_one({"id": guild_id})

        diff_game = difficult[mode.lower()]
        characters = list(db["Characters"].find({"type": {"$lte": diff_game}}))
        await ctx.send('Welcome ' + str(ctx.message.author.mention) + ' to AnimeQuiz!')
        gameOver = False
        Score = 0
        emoji = '\U00002705'
        number_of_question = 1
        while not gameOver:
            Play = random.sample(characters, 4)
            correctNum = random.randint(1, 4)
            Emb = discord.Embed(title="Choose One from Four", description="[1] " + (Play[0])["name"] + "\n" +
                                                                          "[2] " + (Play[1])["name"] + "\n" +
                                                                          "[3] " + (Play[2])["name"] + "\n" +
                                                                          "[4] " + (Play[3])["name"])
            Em = discord.Embed(title=f"\U00002753 Question #{number_of_question} \n Do you know who is it?")
            Em.set_image(url=(Play[correctNum - 1])["img"])
            Em.set_author(name=ctx.message.author, icon_url=ctx.message.author.avatar_url)
            await ctx.send("", embed=Em)
            await ctx.send("", embed=Emb)
            Answer = False
            collection_name = f"{LEADERBOARD}_{mode.lower()}_{str(guild_id)}"
            while not Answer:
                def is_correct(m):
                    return m.author == ctx.author and m.content.isdigit() and m.channel == ctx.channel and int(m.content) in range(1,5)

                msg = await client.wait_for('message', check=is_correct, timeout=20)
                mesaga = msg.content
                user_number = int(mesaga)
                if user_number == correctNum:
                    await ctx.send(str(emoji) + " Correct! You won **100 points** !")
                    number_of_question += 1
                    Score += 100
                    Answer = True
                    characters.remove(Play[correctNum - 1])
                    if len(characters) <= 3:
                        Embed = discord.Embed(title="\U0000274E The questions are over",
                                              description="**Your Score**: " + str(Score), color=discord.Colour.green())
                        await ctx.send("", embed=Embed)
                        thread_update = Thread(target=update_collection, args=(Score, ctx, collection_name))
                        thread_update.start()
                        gameOver = True
                else
                    Embed = discord.Embed(title="\U0000274C Incorrect! Game Over!",
                                          description="**Your Score**: " + str(
                                              Score) + "\nCorrect Answer is number " + f'**{correctNum}**\n**From**: [' + str(
                                              Play[correctNum - 1]["anime"]) + "](" + Play[correctNum - 1]["url"] + ")",
                                          color=discord.Colour.red())
                    await ctx.send("", embed=Embed)
                    thread_update = Thread(target=update_collection, args=(Score, ctx, collection_name))
                    thread_update.start()
                    gameOver = True
                    Answer = True
    except asyncio.TimeoutError:
        Embed = discord.Embed(title="\U000023F2 Time is up! Game Over", description="**Your Score**: " + str(
            Score) + "\nCorrect Answer is number " + f'**{correctNum}**\n**From**: [' + str(
            Play[correctNum - 1]["anime"]) + "](" + Play[correctNum - 1]["url"] + ")",
                              color=discord.Colour.red())
        await ctx.send("", embed=Embed)
        thread_update = Thread(target=update_collection, args=(Score, ctx, collection_name))
        thread_update.start()


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send('This command is on a **%.2f seconds** cooldown' % error.retry_after)
    raise error  # re-raise the error so all the errors will still show up in console


@client.command()
async def python(ctx):
    await ctx.send("https://oir.mobi/uploads/posts/2020-02/1582093607_16-p-smeshnie-kuritsi-24.jpg")


@client.command()
async def GayWebSite(ctx):
    await ctx.send("GayWebSite: https://vk.com/ilbond")


@client.command()
async def ready(ctx):
    await ctx.send(file=discord.File("images/tenor.gif"))


@client.command()
async def dance(ctx):
    await ctx.send(file=discord.File("images/chika.gif"))


@client.command()
async def oppai(ctx):
    oppai = ["images/oppai/oppai1.gif", "images/oppai/oppai2.gif", "images/oppai/oppai3.gif", "images/oppai/oppai4.gif"]
    num = np.random.randint(0, 4)
    await ctx.send(file=discord.File(oppai[num]))


@client.command()
async def sad(ctx):
    violet = ["images/VioletCry.gif", "images/GilbertCry.gif"]
    num = np.random.randint(0, 2)
    await ctx.send(file=discord.File(violet[num]))


@client.command()
async def ктобылпидоромпозавчера(ctx):
    users = ['275677557595308033', '459385814984687636', '706048398171570199', '194561202888638465',
             '375552698264584202', '295538077080748032']

    user = await client.fetch_user(users[np.random.randint(0,6)])
    await ctx.send("Вспоминаю...")
    await ctx.send("Смотрю записи...")
    await ctx.send("А,точно!")
    await ctx.send("Пидoром пидоромпозачера был " + f'{user.mention}')


@client.command()
async def Stepan(ctx):
    while True:
        user = await client.fetch_user('333574613298839562')
        await ctx.send(f" {user.mention}", file=discord.File('images/magik.gif'))
        await asyncio.sleep(1800)
        await ctx.send(file=discord.File('images/magik1.gif'))
        await asyncio.sleep(1800)
        client.move


@client.command(pass_content=True)
async def join(ctx):
    channel = ctx.message.author.voice.channel
    await channel.connect()
    await ctx.send("Получилось! Привет, уебок!")


@client.command(pass_content=True)
async def leave(ctx):
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()
    else:
        await ctx.send("Сам проваливай, еблан")


@client.command(pass_context=True)
async def Gay(ctx, *, id):
    response = requests.get(
        f"https://api.vk.com/method/users.get?user_ids={id}&fields=photo_400_orig&access_token=0ff1ff4a0ff1ff4a0ff1ff4aa80f831ad100ff10ff1ff4a50f1870290b613d3d15f0dc0&v=5.120")

    man = json.loads(response.text)["response"][0]
    if man == "[]":
        await ctx.send("ERROR 504 YOU AR GAY")
    else:
        em = discord.Embed(title='Вычисляю...')
        hash2 = hash(str(id)) + hash(man["last_name"]) + hash(man['first_name'])
        if id == "kukumber2k":
            e = discord.Embed(title=man["first_name"] + ' ' + man["last_name"] + ' ГЕЙ на ' + str(
                random.randint(94, 95)) + ' % ' + "<:Billy_Sex:778347488565264394>")
        else:
            e = discord.Embed(title=man["first_name"] + ' ' + man["last_name"] + ' ГЕЙ на ' + str(hash2 % 100) + ' % ')
        await ctx.send(man["photo_400_orig"])
        await ctx.send('', embed=em)
        accept_decline = await ctx.send('', embed=e)
        await accept_decline.add_reaction(client.get_emoji(778347488565264394))


@client.command(pass_context=True)
async def play(ctx, url):
    YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'True'}

    with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(url, download=False)
    URL = info['formats'][0]['url']
    voice = get(client.voice_clients, guild=ctx.guild)
    FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
    voice.play(FFmpegPCMAudio(executable="F:\Downloads\\bin\\ffmpeg.exe", source=URL, **FFMPEG_OPTIONS))


client.run(config('token', default=''))
