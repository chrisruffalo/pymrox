#!/usr/bin/python

# use unicode literals
from __future__ import unicode_literals

# sys arguments
import sys
# option parsing
import argparse
# LINE_PATTERN_REGEX
import re
# opening urls
import urllib
# image manipulation
from PIL import Image, ImageOps, ImageEnhance, ImageDraw
# path checking
import os.path
import glob
# removing files
import shutil
# handle zip files
import zipfile
# handle tempfiles
import tempfile
# numpy and opencv
import numpy as np
import cv2

# get mtg json
from mtgjson import CardDb

# parse options
parser = argparse.ArgumentParser(description='Remove information from border of MTG cards.')
parser.add_argument('--clear', '-c', dest='clear', action='store_true', default=False, help='Clear the downloaded image cache. (It will take longer to redownload cards.)')
parser.add_argument('--overwrite', '-w', dest='overwrite', action='store_true', default=False, help='Overwrite cards that have already been processed. (It takes longer to write every card.)')
parser.add_argument('--remove', '--rm', '-r', dest='remove', action='store_true', default=False, help='Delete all of the processed cards before processing more. (Basically like --overwrite except all at once and before it starts.)')
parser.add_argument('--bless', '-b', dest='bless', nargs='+', default=[], help='Tempoarily bless a given set during a run. Best used to pull a single card that is wrong after the rest of the cards have been pulled. (Hint: do not use with --overwrite.) ')
parser.add_argument('--single','-s', dest='single', action='store_true', default=False, help='Instead of accepting a deck list the tool accepts the name of a single card as the input. Implies --overwrite.')
parser.add_argument('decklist', metavar='D', help='The input deck list. See README.md for format information.')
parser.add_argument('outputdir', metavar='O', default='/tmp', help='The location that the downloaded card images will be written to.')
args = parser.parse_args()

# output directory name
output_dir = args.outputdir
output_dir = output_dir.strip()
if not output_dir:
	output_dir = "/tmp"
elif output_dir[-1] == "/":
    output_dir = output_dir[:-1]

# other dirs
cache_dir = output_dir + "/.cache"
json_dir = output_dir + "/.json"
infill_dir = output_dir + "/.infill"

# ensure output directory path and cache path exist
if not os.path.exists(output_dir):
	os.mkdir(output_dir)

# delete processed files before starting if asked
if args.remove:
	pngs = output_dir + "/*.png"
	r = glob.glob(pngs)
	for i in r:
		os.remove(i)

# delete directories
if args.clear and os.path.exists(cache_dir):
	shutil.rmtree(cache_dir)

# make directories if needed
if not os.path.exists(cache_dir):
	os.mkdir(cache_dir)
if not os.path.exists(output_dir + "/.json"):
	os.mkdir(output_dir + "/.json")
if not os.path.exists(output_dir + "/.infill"):
	os.mkdir(output_dir + "/.infill")

# attempt to init from file, if not able, do from url
MTG_JSON_URL = "https://mtgjson.com/json/AllSets.json.zip"
MTG_JSON_ZIP = json_dir + "/AllSets.json.zip"
MTG_JSON_FILE = json_dir + "/AllSets.json"
if not os.path.isfile(MTG_JSON_ZIP):
	urllib.urlretrieve(MTG_JSON_URL, MTG_JSON_ZIP)
zip_ref = zipfile.ZipFile(MTG_JSON_ZIP, "r")
zip_ref.extractall(output_dir + "/.json")
zip_ref.close()
db = CardDb.from_file(MTG_JSON_FILE)

# get release dates for card frame magic
BFZ_RELEASE = db.sets.get("BFZ").releaseDate
M_15_RELEASE = db.sets.get("M15").releaseDate
M_08_RELEASE = db.sets.get("8ED").releaseDate
M_06_RELEASE = db.sets.get("6ED").releaseDate
M_04_RELEASE = db.sets.get("4ED").releaseDate

# string patterns for save location
SAVE_MODIFIED_PATTERN = "{:s}/{:s}"
SAVE_CACHE_PATTERN = "{:s}/.cache/{:s}"

# compile regular expression to remove leading numbers
LINE_PATTERN_REGEX = re.compile(r"^[0-9]+?[ ]+?(.+)$")

# sets we are just not going to pull from because...
# - the artwork is not great because of print quality
# - or there are too many errors in the mtgjson for that set
# - or we want modern wording on the card to prevent issues
# - or we just don't like the set
BANNED_SETS = [
	"mps_akh", 
	"lea", 
	"leb", 
	"pjgp", 
	"pgpx", 
	"ppre", 
	"plpa", 
	"pmgd", 
	"pfnm", 
	"parl", 
	"pmei", 
	"pmpr", 
	"pcmp",
	"pwpn",
	"prel",
	"pwp09",
	"ddr",
	"dd3_gvl", 
	"v14", 
	"s99", 
	"cma", 
	"tsb", 
	"ced", 
	"c16", 
	"jvc", 
	"dd3_jvc", 
	"exp",
	"v10", 
	"v12",
	"v13",
	"mps",
	"leg",
	"cei",
	"4ed", # none of these seem to have the right image at all
	"3ed",
	"2ed",
	"me2",
	"me4",
	"por",
	"po2",
	"ath",
	"drk",
	"arc",
	"v09",
	"brb"

]

# blessing mechanism
if hasattr(args, 'bless') and len(args.bless) > 0:
	for blessed in args.bless:
		if blessed.lower() in BANNED_SETS:
			BANNED_SETS.remove(blessed.lower())
			print "Removed blessed set {:s} from banned list".format(blessed)

# not really banned but the mtgjson data is wrong
# you could also use this to ban specific wordings
# or artwork you hate
BANNED_CARDS = {
	"wth": ["Aura of Silence", "Gaea's Blessing"],
	"4ed": ["Armageddon", "Balance", "Island Sanctuary"],
	"5ed": ["Armageddon", "Island Sanctuary", "Wrath of God"],
	"por": ["Armageddon", "Wrath of God"],
	"ice": ["Swords to Plowshares"],
	"6ed": ["Armageddon"],
	"med": ["Armageddon"],
	"me3": ["Karakas", "Mana Drain"],
	"me4": ["Armageddon"],
	"vis": ["Man-o'-War"],
	"ptk": ["Rolling Earthquake"],
	"sth": ["Volrath's Stronghold", "Mox Diamond"],
	"fut": ["Venser, Shaper Savant"],
	"lrw": ["Shriekmaw"],
	"cmd": ["Shriekmaw"],
	"usg": ["Sneak Attack"],
	"con": ["Path to Exile"]
}

# url pattern
MCI_INFO_URL_PATTERN = "https://magiccards.info/scans/en/{:s}/{:s}.jpg"
SCRYFALL_INFO_URL_PATTERN = "https://img.scryfall.com/cards/png/en/{:s}/{:s}.png"

# target resize
RESIZE_TARGET = 816,1110

def getCardFileName(card):
	name = card.name.lower()
	name = re.sub(r'\W+', '_', name)
	return card.set.code.lower() + "-" + getCardId(card) + "-" + name + ".png"

def getCardId(card, urlPattern = None):
	cardId = None

	# find card id
	if hasattr(card, 'number') and card.number:
		cardId = card.number

	# need to look somwhere else for card id		
	if (not cardId or urlPattern == MCI_INFO_URL_PATTERN) and hasattr(card, 'mciNumber') and card.mciNumber:
		cardId = card.mciNumber

	return cardId

def getCardSetCode(card, urlPattern = None):
	setCode = card.set.code.lower()
	if urlPattern == MCI_INFO_URL_PATTERN and hasattr(card.set, 'magicCardsInfoCode'):
		setCode = card.set.magicCardsInfoCode.lower()
	return setCode

def downloadImage(card, urlPattern = SCRYFALL_INFO_URL_PATTERN):
	if not card:
		return None

	# get card id
	cardId = getCardId(card, urlPattern)

	# get set info
	setCode = getCardSetCode(card, urlPattern)

	# create url from pattern
	url = urlPattern.format(setCode, cardId)

	try:
		#print "Opening URL {:s}".format(url)
		# create url and get image
		imgData = urllib.urlopen(url)
		img = Image.open(imgData)
		return img
	except IOError as e:
		if urlPattern == SCRYFALL_INFO_URL_PATTERN:
			return downloadImage(card, MCI_INFO_URL_PATTERN)
		print "[ERROR] {:s} | could not find {:s} (id={:s}, set={:s}) at any URL".format(str(e), card.name, cardId, setCode, url)

def mask_from_cv_image(card, cv_img):
	kern_x = 80
	kern_y = 10
	# rotate kernel if card is split layout
	if hasattr(card, 'layout') and "split" == card.layout:
		swap = kern_x
		kern_x = kern_y
		kern_y = swap

	# need grayscale copy
	gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)

	# kernels for operations
	rectKernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kern_x, kern_y))
	sqKernel = cv2.getStructuringElement(cv2.MORPH_RECT, (8, 8))
	smKernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

	# tophat
	tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, rectKernel)

	# gradient operations
	gradX = cv2.Sobel(gray, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
	gradX = np.absolute(gradX)
	(minVal, maxVal) = (np.min(gradX), np.max(gradX))
	gradX = (255 * ((gradX - minVal) / (maxVal - minVal)))
	gradX = gradX.astype("uint8")

	gradY = cv2.Sobel(gray, ddepth=cv2.CV_32F, dx=0, dy=1, ksize=-1)
	gradY = np.absolute(gradY)
	(minVal, maxVal) = (np.min(gradY), np.max(gradY))
	gradY = (255 * ((gradX - minVal) / (maxVal - minVal)))
	gradY = gradY.astype("uint8")

	# combine grads
	grads = gradX + gradY

	# close and find thresholds
	grads = cv2.morphologyEx(grads, cv2.MORPH_CLOSE, rectKernel)
	thresh = cv2.threshold(grads, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

	# dilate some
	thresh = cv2.dilate(thresh, smKernel, iterations = 5)

	# close with kernel
	thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, sqKernel)

	# return threshold (which can act as a mask)
	return thresh

# took a lot of hints from here:
# https://www.pyimagesearch.com/2017/07/17/credit-card-ocr-with-opencv-and-python/
def fix_card_with_infill(masky1, masky2, maskx1, maskx2, card, img, fill_color = None, paint = True, flood = False, infillRange = 15):

	# where files go
	tmpdir = output_dir + "/.infill"
	prefile = tmpdir + "/" + getCardFileName(card)
	img.save(prefile)

	img = cv2.imread(prefile)
	
	# get masks
	output = mask_from_cv_image(card, img)
	output_invert = mask_from_cv_image(card, 255 - img)

	# add masks together
	#output = output + output_invert

	mask = np.zeros(output.shape, np.uint8)
	mask[masky1:masky2, maskx1:maskx2] = output[masky1:masky2, maskx1:maskx2]

	output_masked_inv = np.zeros(output.shape, np.uint8)
	output_masked_inv[masky1:masky2, maskx1:maskx2] = output_invert[masky1:masky2, maskx1:maskx2]

	# decide which mask has more contours
	_, contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
	_, contours_inv, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
	if len(contours_inv) > len(contours):
		contours = contours_inv
		output_masked = output_masked_inv

	# get fill color from near mask
	if not fill_color:
	#	fill_color = img[maskx1 - 1, masky1 - 1]
		fill_color = (255, 255, 255)

	# mask out cv2_img
	img[np.where(mask)] = fill_color

	# do inpaint if requested
	if paint:
		img = cv2.inpaint(img, mask, infillRange, cv2.INPAINT_TELEA)

	# draw mask area (debuging)
	#cv2.drawContours(img, contours, -1, (255,0,0), 3)
	#cv2.rectangle(img, (maskx1, masky1), (maskx2, masky2), (0, 255, 0), 2)

	cv2.imwrite(prefile, img)
	return Image.open(prefile)

def fix_cards_with_split_layout(card, img):
	img = fix_card_with_infill(110, 480, img.size[0] - 60, img.size[0] - 28, card, img)
	img = fix_card_with_infill(610, 980, img.size[0] - 60, img.size[0] - 28, card, img)
	return img

def fix_cards_with_illustrator_on_black_background(card, img):
	# variable height based on power/toughness or loyalty (creature/planeswalker)
	MAX_HEIGHT = 64
	MIN_HEIGHT = 39

	height = MAX_HEIGHT
	if hasattr(card, 'power') or hasattr(card, 'toughness'):
		height = MIN_HEIGHT
	elif hasattr(card, 'loyalty'):
		height = MIN_HEIGHT + 4

	# fix right side
	img = fix_card_with_infill(img.size[1] - height, img.size[1] - 5, img.size[0] - 300, img.size[0] - 25, card, img, fill_color = (0, 0, 0), paint = False, flood = True)
	# fix left side
	img = fix_card_with_infill(img.size[1] - MAX_HEIGHT, img.size[1] - 5, 20, 300, card, img, fill_color = (0, 0, 0), paint = False, flood = True)
	# fix center
	img = fix_card_with_infill(img.size[1] - MIN_HEIGHT, img.size[1] - 5, 250, img.size[0] - 250, card, img, fill_color = (0, 0, 0), paint = False, flood = True)

	# return adjusted image
	return img

def fix_planeswalker(card, img):
	return fix_card_with_infill(img.size[1] - 70, img.size[1] - 5, img.size[0] - 575, img.size[0] - 150, card, img, fill_color = (0, 0, 0), paint = False, flood = True)

def fix_cards_with_paintbrush_illustrator(card, img):
	return fix_card_with_infill(940, 990, 35, 540, card, img)

def fix_futuresight_creature_card(card, img):
	return fix_card_with_infill(930, 985, 75, 555, card, img)

def fix_cards_in_sets_with_a_range_of_locations(card, img):
	return fix_card_with_infill(940, 990, 45, 560, card, img)

def fix_cards_in_sets_with_a_range_of_locations(card, img):
	return fix_card_with_infill(940, 990, 45, 555, card, img)

def fix_cards_with_centered_illustrator(card, img):
	return fix_card_with_infill(925, 979, 120, 575, card, img)

def fix_cards_with_left_illustrator(card, img):
	return fix_card_with_infill(925, 970, 50, 555, card, img)

# basically starts to fix the card, autocontrast, lighten, etc
# and also hands off to specific functions that handle masked
# areas of each different card style/type
def fix_cards(card, img):
	# crop off 10 pixels on each side to remove borders, potentially adjust for each generation of card
	i_width, i_height = img.size
	img = img.crop([10,10,i_width - 10, i_height - 10])

	# just rgb because transparent corners actually hurt a bit
	img = img.convert('RGB') 

	# default brightness enhancement factor
	l_factor = 1.05

	# get set code
	sCode = card.set.code.lower()

	# the pattern is to ALWAYS correct the contrast and then
	# to do the computer vision work on the card. this gives
	# us the _best_ chance of detecting contours nad having
	# blacks that fill in properly

	# version/era specific fixes
	if hasattr(card, 'layout') and "split" == card.layout:
		#print "Fixing split layout card"
		img = ImageOps.autocontrast(img, 15)
		img = fix_cards_with_split_layout(card, img)
	elif card.set.releaseDate < BFZ_RELEASE and hasattr(card, 'loyalty'):
		#print "Fixing planeswalker card"
		img = ImageOps.autocontrast(img, 15)
		img = fix_planeswalker(card, img)
		l_factor = 1.0
	elif sCode in ["vma", "ema"]:
		#print "Fixing ==VMA, EMA card"
		img = ImageOps.autocontrast(img, 12)
		img = fix_cards_with_illustrator_on_black_background(card, img)
	elif sCode in ["fut"] and (hasattr(card, 'power') or hasattr(card, 'toughness')): # future sight creatures have a different card layout ???
		img = ImageOps.autocontrast(img, 12)
		img = fix_futuresight_creature_card(card, img)
	elif sCode in ["vis", "wth", "sth", "me4", "5ed"]:
		#print "Fixing ==VIS, WTH, STH, ME4, ME3"
		img = ImageOps.autocontrast(img, 12)
		img = fix_cards_with_left_illustrator(card, img)
	elif sCode in ["med", "me3"]:
		#print "Fixing ==MED,ME3 card"
		img = ImageOps.autocontrast(img, 10)
		img = fix_cards_with_centered_illustrator(card, img)		
	elif card.set.releaseDate >= M_15_RELEASE:
		#print "Fixing >=M15 card"
		adjust = 0
		if hasattr(card, 'colorIdentity') and "W" in card.colorIdentity:
			adjust = 8
			l_factor = 1.02
		img = ImageOps.autocontrast(img, 18 + adjust)
		img = fix_cards_with_illustrator_on_black_background(card, img)
	elif card.set.releaseDate >= M_08_RELEASE:
		#print "Fixing >=8ED card"
		adjust = 0
		if hasattr(card, 'colorIdentity') and "W" in card.colorIdentity:
			l_factor = 1.00
		if "bng" == sCode:
			adjust = 16
		img = ImageOps.autocontrast(img, 10 + adjust)
		img = fix_cards_with_paintbrush_illustrator(card, img)
	elif card.set.releaseDate > M_04_RELEASE:
		#print "Fixing >=4ED card"
		img = ImageOps.autocontrast(img, 10)
		img = fix_cards_with_centered_illustrator(card, img)
	else:
		#print "Fixing remaining cards"
		img = ImageOps.autocontrast(img, 10)
		img = fix_cards_with_left_illustrator(card, img)
		l_factor = 1.08

	# lighten just a little bit
	enhancer = ImageEnhance.Brightness(img)
	img = enhancer.enhance(l_factor)		

	return img

def handle_card(card_name_input):
	# if conditioned line is empty, go to next line
	if not card_name_input.strip():
		return

	# look for oldest version of the card from black bordered sets that are not online only
	# this skips the first four sets because, frankly, they are a little outmoded
	card = None
	for cardSetId in db.sets.keys():
		# get card set
		cardSet = db.sets[cardSetId]

		# skip sets without black borders
		if cardSetId.lower() in BANNED_SETS: #or (hasattr(cardSet,'onlineOnly') and cardSet.onlineOnly):
			continue

		# attempt to get card from db
		cardCheck = cardSet.cards_by_name.get(card_name_input)
		# lookup card another way if card not found
		if not cardCheck:
			cardCheck = cardSet.cards_by_ascii_name.get(card_name_input.lower())

		# some cards have bad matches in each set so we don't want to keep the match
		if cardCheck and cardCheck.set.code.lower() in BANNED_CARDS and cardCheck.name in BANNED_CARDS[cardCheck.set.code.lower()]:
			continue

		# keep card if it is valid and has some sort of numerical identifier
		if not card and cardCheck and getCardId(cardCheck):
			card = cardCheck

		# dont immediately accept timeshifted cards
		if cardCheck and hasattr(cardCheck, 'timeshifted') and cardCheck.timeshifted:
			continue

		# if card is found with a black border, break (otherwise keep searching)
		# this means that a white bordered card will still show up but if a black bordered
		# version exists it will be pulled down
		if cardCheck and getCardId(cardCheck) and hasattr(card, 'border') and "black" == card.border:
			card = cardCheck
			break

	# if no card is found after search we need to move on
	if not card:
		print "[ERROR] card {:s} not found in available sets/cards".format(card_name_input)
		# skip rest of loop
		return

	# get card file name
	cardCacheFileName = getCardFileName(card)
	cardFileName = card.name + ".png"

	# get the save location to save the data so we can see if the file is there
	toSave = SAVE_MODIFIED_PATTERN.format(output_dir, cardFileName)

	# don't overwrite files unless asked
	if not args.single and not args.overwrite and os.path.isfile(toSave):
		print "Existing {:s} @ {:s} (set={:s}, id={:s})".format(card.name, toSave, getCardSetCode(card), getCardId(card))
		return

	# look for cached image and skip download if in cache
	img = None
	cacheImage = SAVE_CACHE_PATTERN.format(output_dir, cardCacheFileName)
	if os.path.isfile(cacheImage):
		img = Image.open(cacheImage)
		#print "Using cached image data for {:s}".format(card.name)

	# if the card has been identified get the set info to make the url
	if not img:
		# download image
		img = downloadImage(card)
		# cache on successful download
		if img:
			# save original image to cache
			img.save(cacheImage)
	
	if not img:
		print "[ERROR] No image data found for {:s}".format(card.name)
		return

	# convert to output_img for chaining and making this easier to move around and maintain
	output_image = img

	# mitigate copyright based on frame type
	output_image = fix_cards(card, output_image)

	# create 36px border
	fill_border = "black"
	if hasattr(card,'border') and "black" != card.border:
		fill_border = card.border
	output_image = ImageOps.expand(output_image,border=36,fill=fill_border)

	# final resize to fit
	output_image = output_image.resize(RESIZE_TARGET, Image.ANTIALIAS)

	output_image.save(toSave)
	print "Saved {:s} - {:s} (cached@ {:s}) (set={:s}, id={:s})".format(card.name, toSave, cacheImage, getCardSetCode(card), getCardId(card))

if not args.single:
	# open file specified to use to find cards
	input_filename = args.decklist
	file = open(input_filename, "r")
	for line in file:
		# condition string
		line = line.rstrip()
		line = LINE_PATTERN_REGEX.sub(r"\1", line)

		handle_card(line)
else:
	handle_card(args.decklist)
