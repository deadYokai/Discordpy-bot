import os
import traceback
import asyncio
import discord
import youtube_dl
import subprocess
import json
import requests

from discord.utils import get


TOKEN = "your_token"

VOICE_ID = "763728618676944898"
TEXT_ID = "763728569834668042"

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


@client.event
async def on_ready():
	print(f'{client.user.name} has connected to Discord!')

# @client.event
# async def on_member_join(member):
# 	role = "Новичок"
# 	ch = await client.fetch_channel(GUILD)
# 	await member.add_roles(discord.utils.get(member.guild.roles, name=role))
# 	await ch.send(f"{member.mention} Ты получил роль {role}. Теперь тебе доступны все функции серверa")

@client.event
async def on_message(message):
	global vc
	if message.content.startswith('$pl '):
		s_pl = message.content.split()
		if s_pl is not None:
			ch = message.author.voice.channel
			if vc is None:
				vc = await ch.connect()
			else:
				if vc.is_playing():
					vc.stop()
			link = s_pl[1].split('&')[0]
			try:
				player = await YTDLSource.from_url(link)
				vc.play(player)
			except:
				ok = os.system(f'youtube-dl -f bestaudio {link} -o tmp')
				if ok == 0:
					player = discord.FFmpegPCMAudio('tmp', **ffmpeg_options)
					vc.play(player, after=lambda e: os.system('rm tmp'))
			vc.source = discord.PCMVolumeTransformer(vc.source)
			vc.source.volume = 1.0
	if message.content == '$plstop':
		if vc.is_playing():
			vc.stop()
		vc.disconnect()
	if message.content.startswith("$ps "):
		s_ps = message.content.split()
		if s_ps is not None:

			q_str = ""

			for x in range(1, len(s_ps)):
				q_str += s_ps[x]


			headers = {
			    'Accept': 'application/json',
			}

			params = (
			    ('q', q_str),
			    ('type', 'video'),
			    ('videoCategoryId', '10'),
			    ('key', 'AIzaSyDICPD-4KN1O5bT9YfNkUt96VHtThyevwU'),
			)

			response = requests.get('https://www.googleapis.com/youtube/v3/search', headers=headers, params=params)
			link = f"https://youtu.be/{response.json()['items'][0]['id']['videoId']}"
			title = subprocess.Popen(f'youtube-dl -e {link}', shell=True, stdout=subprocess.PIPE)
			title.wait()
			ch = message.author.voice.channel
			await message.channel.send(f"Found: **{str(title.stdout.read().decode())}**")
			if vc is None:
				vc = await ch.connect()
			else:
				if vc.is_playing():
					vc.stop()
			try:
				player = await YTDLSource.from_url(link)
				vc.play(player)
			except:
				ok = os.system(f'youtube-dl -f bestaudio {link} -o tmp')
				if ok == 0:
					player = discord.FFmpegPCMAudio('tmp', **ffmpeg_options)
					vc.play(player, after=lambda e: os.system('rm tmp'))

client.run(TOKEN)

