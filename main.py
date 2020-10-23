import os
import traceback
import asyncio
import discord
import youtube_dl
import subprocess
import json
import requests
import datetime
import atexit
import time

from discord.utils import get
from youtubesearchpython import SearchVideos
from threading import Thread, Event

TOKEN = ""

SERVER_ID = 

client = discord.Client()

youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
	'format': 'bestaudio/best',
	'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
	'restrictfilenames': True,
	'noplaylist': True,
	'nocheckcertificate': True,
	'ignoreerrors': False,
	'logtostderr': False,
	'quiet': True,
	'no_warnings': True,
	'default_search': 'auto',
	'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}


ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
ffmpeg_options = {
	'options': '-vn -ss 0'
}

vc = None
player = None
disconnected = True
loop = False
stopFlag = None
task = None

data = {}
comm_pref = '$'

class YTDLSource(discord.PCMVolumeTransformer):
	def __init__(self, source, *, data, volume=0.5):
		super().__init__(source, volume)

		self.data = data

		self.title = data.get('title')
		self.url = data.get('url')

	@classmethod
	async def from_url(cls, url, *, loop=None, stream=False, time=40):
		
		durf = subprocess.Popen(f'youtube-dl --get-duration {url}', shell=True, stdout=subprocess.PIPE)
		durf.wait()
		dur = float(str(durf.stdout.read().decode().replace(":",".")))
		if dur == 0:
			stream = True
		loop = loop or asyncio.get_event_loop()
		data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
		if 'entries' in data:
			# take first item from a playlist
			data = data['entries'][0]

		filename = data['url'] if stream else ytdl.prepare_filename(data)
		return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


# @client.event
# async def on_member_join(member):
# 	role = "Новичок"
# 	ch = await client.fetch_channel(GUILD)
# 	await member.add_roles(discord.utils.get(member.guild.roles, name=role))
# 	await ch.send(f"{member.mention} Ты получил роль {role}. Теперь тебе доступны все функции серверa")

async def pls(c, m, l, d):
	if d:
		os.system('rm tmp')
	if loop:
		await pl(c, m, l)

async def pl(ch, message, link):
	global vc
	global disconnected
	global player
	global loop
	global data
	if disconnected:
		vc = await ch.connect()
		disconnected = False
	else:
		if vc.is_playing():
			vc.stop()
	title = subprocess.Popen(f'youtube-dl -e {link}', shell=True, stdout=subprocess.PIPE)
	await message.channel.send(f"Play: **{str(title.stdout.read().decode())}**")
	title.wait()
	try:
		player = await YTDLSource.from_url(link)
		vc.play(player, after=await pls(ch, message, link, False))
	except:
		ok = os.system(f'youtube-dl -f bestaudio {link} -o tmp')
		if ok == 0:
			player = discord.FFmpegPCMAudio('tmp', **ffmpeg_options)
			vc.play(player, after=await pls(ch, message, link, True))


async def add_queue(link, message):
	with open('tmp.queue', 'a') as fa:
		fa.write(f'{link}\n')
	f = open("tmp.queue", "r")
	await message.channel.send(f"Queue:\n**{f.read()}**")

def getstime(author):
	return datetime.datetime.now() - author.joined_at

def levelformula(qq):
	fq = qq*10
	if qq > 1:
		fq = qq*1.5*10
	if qq >= 45:
		fq = qq*25
	return int(fq)

def checklvl(uid, author):
	global data

	exp = data[str(uid)][0]['exp']
	lvl = data[str(uid)][0]['level']

	if exp >= levelformula(lvl):
		data[str(uid)][0]['exp'] = exp - levelformula(lvl)
		data[str(uid)][0]['level'] += 1


def addexp(author, count = 1):
	data[str(author.id)][0]['exp'] += count

def basecheck(author, ismsg=True):
	global data
	uid = author.id
	if uid != client.user.id:
		if data.get(str(uid)) is None:
			data[str(uid)] = []
			data[str(uid)].append({
				'curr_name': author.name,
				'display_name': author.display_name,
				'mention': author.mention,
				'exp': 0,
				'level': 1,
				'msg_counts': 0,
				'voicetime': 0,
			})
		else:
			if ismsg:
				data[str(uid)][0]['msg_counts'] += 1
				addexp(author)
		checklvl(uid, author)
	return data


class MyThread(Thread):
	def __init__(self, event):
		Thread.__init__(self)
		self.stopped = event

	def run(self):
		global data
		try:
			while not self.stopped.wait(1):
				for channel in client.get_guild(SERVER_ID).voice_channels:
					for x in channel.members:
						basecheck(x, False)
						data[str(x.id)][0]['voicetime'] += 1
						addexp(x)
		except KeyboardInterrupt:
			pass

def exit_handler():
	with open('database.json', 'w') as outfile:
		json.dump(data, outfile)


async def sset(message, typ, uid, count):
	global data
	if data[str(uid)] is not None:
		if typ == "exp":
			data[str(uid)][0]['exp'] = int(count)
			await message.channel.send(f"{data[str(uid)][0]['display_name']} setted {count} exp")
		elif typ == "level":
			data[str(uid)][0]['level'] = int(count)
			await message.channel.send(f"{data[str(uid)][0]['display_name']} setted {count} level")
		elif typ == "voice":
			data[str(uid)][0]['voicetime'] = int(count)
			await message.channel.send(f"{data[str(uid)][0]['display_name']} setted {count} voicetime")
		elif typ == "msgcount":
			data[str(uid)][0]['msg_counts'] = int(count)
			await message.channel.send(f"{data[str(uid)][0]['display_name']} setted {count} messages")
		else:
			await message.channel.send(f"Unknown type *{typ}*")

async def getstat(uid, message):
	d = data[str(uid)][0]
	authbyid = client.get_guild(SERVER_ID).get_member(int(uid))
	level = str(d['level'])
	exp = f'{str(d["exp"])}\/{levelformula(d["level"])}'
	voicet = str(datetime.timedelta(seconds=d['voicetime']))
	msgs = str(d['msg_counts'])
	e = discord.Embed(title = "Статистика пользователя", type="rich", colour=discord.Colour.red())
	if os.path.isfile(f'{str(uid)}.txt'):
		with open(f'{str(uid)}.txt') as file:
			e.description = file.read()
	if d['level'] >= 45:
		role = "Постоялец"
		await authbyid.add_roles(get(authbyid.guild.roles, name=role))
		e.set_thumbnail(url="https://icons-for-free.com/iconfiles/png/512/best+bookmark+premium+rating+select+star+icon-1320168257340660520.png")
		level = f'<a:dance3:767020580435132416>{str(d["level"])}'
	if os.path.isfile(f'{str(uid)}.secrets'):
		with open(f'{str(uid)}.secrets') as file:
			secrets = file.read()
			if '&' in secrets:
				secrets = secrets.split('&')
				if len(secrets) >= 1:
					exp = secrets[0]
					level = secrets[1]
				if len(secrets) >= 2:
					msgs = secrets[2]
				if len(secrets) >= 3:
					voicet = secrets[3]
	e.set_author(name=d['curr_name'], icon_url=authbyid.avatar_url)
	e.add_field(name="**UserID**", value=str(uid), inline=False)
	e.add_field(name="**EXP**", value=exp, inline=True)
	e.add_field(name="**Level**", value=level, inline=True)
	e.add_field(name="**Ник**", value=d['display_name'], inline=False)
	e.add_field(name="**Кол-во сообщений**", value=msgs, inline=False)
	e.add_field(name="**Время в воисе**", value=voicet, inline=False)
	e.add_field(name="**Время на сервере**", value=str(datetime.timedelta(seconds=getstime(authbyid).total_seconds())), inline=False)
	await message.channel.send(embed=e)

@client.event
async def on_ready():
	global data
	global task
	global stopFlag
	print(f'{client.user.name} has connected to Discord!')
	if os.path.isfile('database.json'):
		with open('database.json') as json_file:
			data = json.load(json_file)

	stopFlag = Event()
	thread = MyThread(stopFlag)
	thread.start()

@client.event
async def on_disconnect():
	global data
	global stopFlag
	print(f'{client.user.name} has disconnected from Discord!')
	stopFlag.set()
	with open('database.json', 'w') as outfile:
		json.dump(data, outfile)

@client.event
async def on_message(message):
	global vc
	global disconnected
	global player
	global loop
	
	basecheck(message.author)

	########################
	## >>> Play link       #
	########################
	if message.content.startswith(f'{comm_pref}pl '):
		s_pl = message.content.split()
		if s_pl is not None:
			link = s_pl[1].split('&')[0]
			ch = message.author.voice.channel
			await pl(ch, message, link)

	########################
	## >>> Set stats       #
	########################
	if message.content.startswith(f'{comm_pref}statsset '):
		s_pl = message.content.split()
		if s_pl is not None:
			rol = get(client.get_guild(SERVER_ID).roles, id=0000)
			if rol in message.author.roles:
				await sset(message, s_pl[1], s_pl[2], s_pl[3])

	########################
	## >>> Check by id     #
	########################
	if message.content.startswith(f'{comm_pref}check '):
		s_pl = message.content.split()
		if s_pl is not None:
			await getstat(s_pl[1], message)

	########################
	## >>> Play stop       #
	########################
	if message.content == f'{comm_pref}plstop':
		if vc.is_playing():
			vc.stop()
		await vc.disconnect()
		disconnected = True

	########################
	## >>> Play loop       #
	########################
	if message.content == f'{comm_pref}ploop':
		loop = not loop
		await message.channel.send(f"Повтор: {loop}")
	if message.content == f'{comm_pref}ploos':
		await message.channel.send(f"Повтор: {loop}")
		for p in data['users']:
			await message.channel.send(channel)

	########################
	## >>> Checkme         #
	########################
	if message.content == f'{comm_pref}checkme':
		await getstat(message.author.id, message)

	########################
	## >>> Play query      #
	########################
	if message.content.startswith(f"{comm_pref}pq "):
		s_pq = message.content.split()
		if s_pq is not None:
			link = s_pq[1].split('&')[0]
			await add_queue(link, message)

	########################
	## >>> Play search     #
	########################
	if message.content.startswith(f"{comm_pref}ps "):
		s_ps = message.content.split()
		if s_ps is not None:

			q_str = ""

			for x in range(1, len(s_ps)):
				q_str += s_ps[x]

			search = SearchVideos(q_str, offset = 1, mode = "json", max_results = 1)
			link = json.loads(search.result())['search_result'][0]['link']
			ch = message.author.voice.channel
			await pl(ch, message, link)

	########################
	## >>> Days on server  #
	########################
	if message.content == f"{comm_pref}a":
		years = ''
		month = ''
		days = ''
		hours = ''
		minutes = ''
		sp = getstime(message.author)
		split = datetime.datetime.fromtimestamp(sp.total_seconds())
		if sp.total_seconds() > 31556952:
			years = f'{split.strftime("%y")} годиков '
		if sp.total_seconds() > 2629746:
			month = f'{split.strftime("%-m")} месяцев '
		if sp.total_seconds() > 86400:
			days = f'{split.strftime("%-d")} денёчков '
		if sp.total_seconds() > 3600:
			hours = f'{split.strftime("%-H")} часиков '
		if sp.total_seconds() > 60:
			minutes = f'{split.strftime("%-M")} минут '
		secs = split.strftime("%-S")
		await message.channel.send(f'{message.author.mention} на сервере уже {years}{month}{days}{hours}{minutes}{secs} секудночек')

client.run(TOKEN)
atexit.register(exit_handler)
