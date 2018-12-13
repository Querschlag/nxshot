import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from shutil import copy
from urllib.error import URLError
from urllib.request import urlopen

from Crypto.Cipher import AES
from bs4 import BeautifulSoup

KEYHASH = "24e0dc62a15c11d38b622162ea2b4383"

updated = 0
idname = {}


def load_key(filename, keyhash):
	try:
		with open(filename, 'r') as keyfile:
			keystring = keyfile.read(32)
			key = bytes.fromhex(keystring)
			if hashlib.md5(key).hexdigest() not in keyhash:
				raise ValueError("Keys don't match!")
			return key

	except FileNotFoundError:
		print("Decryption key (key.txt) not found!")
	except ValueError:
		print("Decryption key (key.txt) doesn't match!")


def update_game_ids():
	key = load_key('key.txt', KEYHASH)
	if not key:
		return -1

	wiki = 'http://switchbrew.org/index.php?title=Title_list/Games'
	try:
		wikipage = urlopen(wiki)
	except URLError:
		print("Could not update gameids!")
		return -1

	wikisoup = BeautifulSoup(wikipage, 'html.parser')
	gametable = wikisoup.find('table', {"class": "wikitable sortable"})
	gametabler = gametable.find_all('tr')

	cipher = AES.new(key, AES.MODE_ECB)

	for row in gametabler[1:]:
		try:
			titleid = row.contents[1].contents[0][0:]
			gamename = row.contents[3].contents[0][0:]
			region = row.contents[5].contents[0][0:]
		except IndexError:  # At least one cell empty; ignore row
			continue

		if ":" in gamename:
			gamename = gamename.replace(":", " -")

		# print('TitleID = {}'.format(titleid))

		titleidb = bytes.fromhex(titleid)
		titleidb = titleidb[7::-1]
		conversion = titleidb.hex()
		conversion = conversion.ljust(32, '0')
		titleidb = bytes.fromhex(conversion)
		encrypted = cipher.encrypt(titleidb)
		screenshotid = encrypted.hex().upper()

		# print("ScreenshotID = {}".format(encrypted.hex()))
		idname[screenshotid] = gamename + ' (' + region + ')'

	with open('gameids.json', 'w', encoding='utf-8') as idfile:
		json.dump(idname, idfile, ensure_ascii=False, indent=4, sort_keys=True)
		print("Successfully updated Game IDs")

	return 1


def check_id(gameid, idname):
	if gameid in idname:
		return idname[gameid]
	else:
		return 'Unknown'


def check_folders(filelist):
	current = 0
	length = len(filelist)
	# print(filelist)
	for mediapath in filelist:
		year = mediapath.stem[0:4]
		month = mediapath.stem[4:6]
		day = mediapath.stem[6:8]
		hour = mediapath.stem[8:10]
		minute = mediapath.stem[10:12]
		second = mediapath.stem[12:14]
		gameid = mediapath.stem[17:]

		try:
			time = datetime(
				int(year),
				int(month),
				int(day),
				hour=int(hour),
				minute=int(minute),
				second=int(second))
			pass
		except ValueError:
			print(
				'Invalid filename for media {}: {}'.format(
					current,
					str(mediapath.stem)
				)
			)
			continue

		posixtimestamp = time.timestamp()

		outputfolder = args.filepath.joinpath('Organized', check_id(gameid, idname))

		outputfolder.mkdir(parents=True, exist_ok=True)

		newfile = copy(str(mediapath), str(outputfolder))

		os.utime(newfile, (posixtimestamp, posixtimestamp))

		current += 1

		print('Organized {} of {} files.'.format(current, length))


if __name__ == '__main__':
	# Argument parser
	parser = argparse.ArgumentParser(
		description='Automatically organize and timestamp your Nintendo Switch captures.')

	parser.add_argument(
		'filepath',
		metavar='FILEPATH',
		type=Path,
		help='"Nintendo/Album" folder from your SD card.')

	# If there are arguments, parse them. If not, exit
	args = parser.parse_args()

	# Load game ids and their names from external file
	try:
		with open('gameids.json', 'r', encoding='utf-8') as idfile:
			idname = json.load(idfile)
	except FileNotFoundError:
		print('Game ID list (gameids.json) not found! Fetching from Switchbrew...')
		updated = update_game_ids()
		if updated < 0:
			sys.exit()
	except json.decoder.JSONDecodeError:
		print('Invalid JSON format! Fetching from Switchbrew...')
		updated = update_game_ids()
		if updated < 0:
			sys.exit()

	if not updated:
		update_game_ids()

	albumfolder = args.filepath

	screenshotlist = sorted(
		Path(albumfolder).glob(
			'[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/*.jpg'
		)
	)

	videolist = sorted(
		Path(albumfolder).glob(
			'[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/*.mp4'
		)
	)

	if len(screenshotlist) != 0:
		print('Organizing screenshots...')
		check_folders(screenshotlist)
	else:
		print('No screenshots found!')

	if len(videolist) != 0:
		print('\nOrganizing videos...')
		check_folders(videolist)
	else:
		print('\nNo videos found!')

	print('Done!')
