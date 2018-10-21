from exceptions import UnknownChannelError, NotConnectedException, MusicException
from typing import Union, Dict, List
from collections import defaultdict
from datetime import datetime
from client import client
import youtube_dl
import asyncio
import discord
import random
import json
import log
import os


client.basic_help(title="music", desc="Handles music functionality within the bot. (Currently disabled)")
detailed_help = {
	"Usage": f"{client.default_prefix}music <subcommand> [args]",
	"Arguments": "`subcommand` - subcommand to run\n`args` - (optional) arguments specific to the subcommand being run",
	"Description": "This command manages music related functionality within the bot. Music is available to several servers at once.",
	"Subcommands": "",
}
client.long_help(cmd="music", mapping=detailed_help)


voice_enable = False

guild_channel: Dict[int, discord.TextChannel] = {}
guild_queue: Dict[int, List["Song"]] = defaultdict(list)
guild_now_playing_song: Dict[int, "Song"] = {}
guild_volume: Dict[int, float] = defaultdict(lambda: float(default_volume))
active_clients: Dict[int, discord.VoiceClient] = {}
default_volume = 0.5

song_info_embed_colour = 0xbf35e3

playlist_dir = "playlists/"

class Song:
	def __init__(self, url: str, title: str = None, duration: int = None, requester: str = "<unknown requester>", noload: bool = False):
		self.submitted_url = url

		if not noload:
			with youtube_dl.YoutubeDL({"format": "bestaudio", "noplaylist": True}) as session:
				data = session.extract_info(download=False, url=url)
				# get url from the data dict. if it's a youtube link then you need to check for the best format url too
			if title is None:
				self.title = data.get("title", "<no title>")
			if duration is None:
				self.duration = data.get("duration", 0)
			formats = data.get("formats", None)
			if formats is None:
				log.error("no formats found????")
				self.media_url = ""
			else:
				self.media_url = formats[0].get("url", "")
			self.loaded = True

		if noload:
			self.media_url = ""
			self.title = title if title is not None else "<song data not loaded>"
			self.duration = duration if duration is not None else 0
			self.loaded = False

		self.requester = requester
		self.source = None

	def load(self):
		with youtube_dl.YoutubeDL({"format": "bestaudio", "noplaylist": True}) as session:
			data = session.extract_info(download=False, url=self.submitted_url)
		# get url from the data dict. if it's a youtube link then you need to check for the best format url too
		self.title = data.get("title", "<no title>")
		self.duration = data.get("duration", 0)
		formats = data.get("formats", None)
		if formats is None:
			log.error("no formats found????")
			self.media_url = ""
		else:
			self.media_url = formats[0].get("url", "")
		self.loaded = True

	def get_source(self, guild_id: int):
		"""Get an AudioSource object for the song."""
		if self.source is not None: return self.source
		self.source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(self.media_url), volume=guild_volume.get(guild_id, default_volume))
		return self.source


async def checkmark(message) -> bool:
	try:
		await message.add_reaction("☑")
	except:  # broad except but that's fine
		log.debug("{__name__}: couldn't add reaction (insufficient permissions?)")
		return False
	else:
		return True


def check_if_user_in_channel(channel: discord.VoiceChannel, user: Union[discord.User, int]) -> bool:
	return getattr(user, "id", user) in [x.id for x in channel.members]


def get_song_embed(song, is_next: bool = False, queue_position: int = None):
	if not song.loaded: song.load()
	if is_next:
		embed = discord.Embed(title="Now Playing", description=discord.Embed.Empty, colour=song_info_embed_colour)
	else:
		position = f"Queue position {queue_position}" if queue_position is not None else discord.Embed.Empty
		embed = discord.Embed(title="Song Info", description=position, colour=song_info_embed_colour)

	duration = "<length unknown>" if song.duration is 0 else f"{song.duration//60}m{song.duration%60}s"

	embed = embed.add_field(name="Title", value=song.title)
	embed = embed.add_field(name="Reference", value=song.submitted_url)
	embed = embed.add_field(name="Duration", value=duration)
	embed = embed.add_field(name="Requester", value=song.requester)
	embed = embed.add_footer(datetime.utcnow().__str__())
	return embed


def get_target_voice_connection(object: Union[discord.Member, discord.Guild, discord.VoiceChannel, int]) -> Union[discord.VoiceClient, MusicException]:
	target = None

	if isinstance(object, discord.Member):
		target = object.voice.channel
	if isinstance(object, discord.Guild):
		target = getattr(discord.utils.find(lambda x: x.guild.id == object.id, client.voice_clients), "channel", None)
	if isinstance(object, discord.VoiceChannel):
		target = object

	if isinstance(object, int):
		# seriously :/
		log.warning("get_target_voice_channel() given a raw integer/ID; this probably should not happen but I'll try my best")

		channel = client.get_channel(object)
		guild = client.get_guild(object)
		if isinstance(guild, discord.Guild):
			target = discord.utils.find(lambda x: x.id == object, client.voice_clients).channel

		elif isinstance(channel, discord.VoiceChannel):
			target = channel

		else:
			target = None

	if not isinstance(target, discord.VoiceChannel):
		return UnknownChannelError("Requested channel is not known")
	# now we know that target is a VoiceChannel
	if not check_if_user_in_channel(target, client.user.id):
		# if we're not in the channel
		return NotConnectedException("We're not currently connected to this voice channel")
	else:
		return discord.utils.find(lambda x: x.channel.id == target.id, client.voice_clients)


def get_queue_list(queue):
	info = f"Next {'20' if len(queue) > 20 else len(queue)} items in queue:\n"
	i = 1
	for song in queue[:20]:
		duration = "length unknown" if song.duration is 0 else f"{song.duration//60}m{song.duration%60}s"
		info += f"{'0' if (len(queue) > 9) and (i < 9) else ''}" \
				f"{i}:` " \
				f"{song.title} ({duration}) (requested by {song.requester})\n"
		i += 1
	return info


@client.command(trigger="music")
async def command(command: str, message: discord.Message):
	global guild_channel, guild_now_playing_song, guild_queue, guild_volume, active_clients

	if "--bypass" not in command:
		await message.channel.send("Sorry, but this command has been temporarily removed as it is currently being rewritten.")
		return
	command = command.replace(" --bypass", "")

	if not voice_enable:
		await message.channel.send("Sorry, but the internal Opus library required for voice support was not loaded for whatever reason. Music will not work, sorry.")
		return

	parts = command.split(" ")
	# parts: music subcmd args args args

	# commands:
	# music join [channel_id]
	# music add <reference>
	# music play
	# music skip
	# music pause (toggle)
	# music volume <float>
	# music queue
	# music info [position in queue (else get now playing)]
	# music playing (like above but only for now playing)
	# music exit/quit/stop

	if not parts[1] in ["join", "add", "play", "skip", "pause", "volume", "queue", "info", "playing", "exit", "stop", "quit", "load", "remove"]:
		await message.channel.send("Unknown subcommand (see command help for available subcommands)")
		return

	# join their voice channel
	if parts[1] == "join":
		connection = get_target_voice_connection(message.author)
		if connection is None:
			# user's not in a channel
			connection = get_target_voice_connection(message.guild)
			if isinstance(connection, MusicException):
				# we're not in a channel either
				# cool, we have no idea what channel they want us to join to
				await message.channel.send("ambiguous/unknown target channel: please join the target voice channel")
				return
			else:
				# user's not in a channel but we are already in a channel
				await message.channel.send("already in a channel (also, next time please join the channel you are referring to first)")
				return
		if isinstance(connection, MusicException):
			# user is in there but we're not
			if isinstance(get_target_voice_connection(message.guild), discord.VoiceClient):
				await message.channel.send("cannot join channel: already in another channel in this server")
				return
			new_connection = await message.author.voice.channel.connect()
			guild_channel[message.guild.id] = message.channel
			active_clients[message.guild.id] = new_connection
			if not await checkmark(message):
				try:
					await message.channel.send("Joined the channel")
				except:
					pass
			return
		if isinstance(connection, discord.VoiceClient):
			# we're in the channel with them
			await message.channel.send("Already in this channel with you")
			return

	# add a new song to the queue
	if parts[1] == "add":
		# todo: auth check if user is in voice channel
		url = command.replace("music add ", "", 1)
		try:
			song = Song(url=url, requester=message.author.mention)
		except Exception:
			await message.channel.send("error getting song information; song not added to playlist")
			log.warning("Unable to add song", include_exception=True)
			return

		# todo: add warning for sending links with playlists, that they will not get added

		guild_queue[message.guild.id].append(song)
		guild_channel[message.guild.id] = message.channel
		guild_channel[message.guild.id].send("Song added to end of queue:", embed=get_song_embed(song, queue_position=len(guild_queue[message.guild.id])))
		return

	# start playing music for them
	if parts[1] == "play":
		vc = get_target_voice_connection(message.guild)
		if not isinstance(vc, discord.VoiceClient):
			await message.channel.send("cannot play music: not connected to any voice channel")
			return
		if not check_if_user_in_channel(vc.channel, message.author.id):
			try:
				await message.add_reaction("❌")
			except:
				try:
					await message.channel.send("command refused: you are not in the target channel")
				except:
					pass
			finally:
				return
		if len(guild_queue.get(message.channel.id, [])) is 0:
			await message.channel.send("queue empty: nothing to play")
			return

		if vc.is_playing():
			# we're already playing something
			await message.channel.send("Already playing music.")
			return

		while True:
			try:
				next_up = guild_queue[message.guild.id].pop(0)
				guild_now_playing_song[message.guild.id] = next_up
				await message.channel.send(embed=get_song_embed(next_up, is_next=True))
				vc.play(next_up.get_source(message.guild.id))
			except IndexError:
				if isinstance(get_target_voice_connection(message.guild), discord.VoiceClient):
					await message.channel.send("queue exhausted: stopping music playback")
				return
			except Exception as e:
				if isinstance(e, IndexError): return
				log.error("Unexpected error during music playback", include_exception=True)
				await message.channel.send("Sorry, there was an unexpected error while playing music.")
				await vc.disconnect()
			else:
				while vc.is_playing():
					try:
						await asyncio.sleep(1)
					except:
						pass

	# skip the current song
	if parts[1] == "skip":
		vc = get_target_voice_connection(message.guild)
		if not isinstance(vc, discord.VoiceClient):
			await message.channel.send("cannot skip song: not currently connected to any voice channel")
			return
		if not check_if_user_in_channel(vc.channel, message.author.id):
			await message.channel.send("command refused: you are not in the target channel")
			return
		vc.stop()
		await checkmark(message)

	# pause the current song (toggle)
	if parts[1] == "pause":
		vc = get_target_voice_connection(message.guild)
		if not isinstance(vc, discord.VoiceClient):
			await message.channel.send("cannot pause music: not currently connected to any voice channel")
			return
		if not check_if_user_in_channel(vc.channel, message.author.id):
			await message.channel.send("command refused: you are not in the target voice channel")
			return
		if vc.is_paused():
			vc.resume()
		else:
			vc.pause()
		await checkmark(message)

	# change the volume
	if parts[1] == "volume":
		try:
			new_vol = float(parts[2])
		except ValueError:
			await message.channel.send(f"That's not a float. (got: {parts[2]})")
			return
		except IndexError:
			await message.channel.send("New volume not supplied. See command help for help.")
			return

		vc = get_target_voice_connection(message.guild)
		if not check_if_user_in_channel(vc.channel, message.author):
			await message.channel.send("command refused: you are not in the target voice channel")
			await message.add_reaction("❌")
			return
		try:
			vc.source.volume = new_vol
		except:
			pass
		finally:
			guild_volume[message.channel.guild] = new_vol
			await checkmark(message)

	# see the queue
	if parts[1] == "queue":
		embed = discord.Embed(title="Upcoming Music Queue", description=get_queue_list(guild_queue.get(message.guild.id, [])), colour=discord.Embed.Empty)
		embed = embed.add_field(name="Currently Playing", value=getattr(guild_now_playing_song.get(message.guild.id, ""), "title", "<no song playing>"))
		embed = embed.add_footer(datetime.utcnow().__str__())
		await message.channel.send(embed=embed)
		return

	# see information about a song in the queue
	if parts[1] == "info":
		try:
			parts[2]
		except IndexError:
			target_song = guild_now_playing_song.get(message.guild.id, None)
			if target_song is None:
				await message.channel.send("cannot get song information: no song is currently playing and no queue index specified")
				return
			else:
				await message.channel.send(embed=get_song_embed(target_song, is_next=True))
				return

		try:
			index = int(parts[2])
		except ValueError:
			await message.channel.send(f"cannot get song info: noninteger queue index (got: {parts[2]})")
			return

		try:
			target_song = guild_queue.get(message.guild.id, [])[index-1]
		except IndexError:
			await message.channel.send(f"cannot get song info: invalid queue index (queue is shorter than index provided?)")
			return

		await message.channel.send(embed=get_song_embed(target_song, queue_position=index))

	# see information about what is currently playing
	if parts[1] == "playing":
		target_song = guild_now_playing_song.get(message.guild.id, None)
		if target_song is None:
			await message.channel.send("cannot get song informaiton: no song is currently playing")
			return
		else:
			await message.channel.send(embed=get_song_embed(target_song, is_next=True))
			return

	# bye
	if parts[1] in ["exit", "stop", "quit"]:
		vc = get_target_voice_connection(message.guild)
		if not isinstance(vc, discord.VoiceClient):
			await message.channel.send("cannot disconnect from voice channel: not connected to any voice channel to disconnect from")
			return
		if not check_if_user_in_channel(vc.channel, message.author.id):
			await message.channel.send("command refused: you are not in the target voice channel")
			return
		await vc.disconnect()
		if parts[2] not in ["--no-clear-queue", "-n"]:
			guild_queue[message.guild.id] = []

	# load a queue from a json file
	if parts[1] == "load":
		force_randomize = "--force-randomize" in command
		no_force_randomize = "--no-force-randomize" in command
		if force_randomize and no_force_randomize:
			await message.channel.send("exception: both --force-randomize and --no-force-randomize passed as arguments")
			return

		command = command.replace(" --force-randomize", "")
		command = command.replace(" --no-force-randomize", "")

		parts = command.split(" ")

		try:
			parts[2]
		except IndexError:
			await message.channel.send("cannot load playlist: no playlist specified. See command help or source code for help.")
			return

		target_filename = f"{parts[2]}.json"
		if target_filename not in os.listdir(playlist_dir):
			await message.channel.send("cannot load playlist: no such playlist exists")
			return

		try:
			data = json.load(open(playlist_dir+target_filename, "r"))
		except Exception as e:
			log.error("error loading playlist:", include_exception=True)
			await message.channel.send(f"cannot load playlist: unexpected exception loading playlist: {e.__class__.__name__}: {''.join(e.args)}\n\nThis exception has been logged.")
			return

		loaded_playlist = data['playlist']
		for i in range(data['exponential_extend_iter']):
			loaded_playlist.extend(loaded_playlist)
		if (data['randomize'] or force_randomize) and not no_force_randomize:
			random.shuffle(loaded_playlist)

		playlist_objects = [Song(url=x, requester=f"{message.author.mention} from playlist \"{parts[2]}.json\"", noload=True) for x in loaded_playlist]
		current_queue = guild_queue.get(message.channel.send, None)
		if current_queue is None:
			guild_queue[message.guild.id] = []
		guild_queue[message.guild.id].extend(playlist_objects)

	# remove (element) from queue or clear queue
	if parts[1] == "remove":
		try:
			parts[2]
		except IndexError:
			await message.channel.send("argument error: no queue index to remove")
			return

		clear_all = parts[2] in ["-c", "--clear", "--clear-all"]
		if clear_all:
			guild_queue[message.channel.send] = []
			return

		try:
			index = int(parts[2])
		except ValueError:
			await message.channel.send(f"cannot remove song from queue: invalid integer index (got: {parts[2]})")
			return

		guild_queue[message.channel.id].pop(index-1)

@client.ready
async def music_capable_check():
	global voice_enable
	if discord.opus.is_loaded():
		voice_enable = True
	else:
		voice_enable = False
		log.warning("Voice library not loaded for some unknown reason. Music functionality will not work.")