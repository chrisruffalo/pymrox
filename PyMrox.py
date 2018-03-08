#!/usr/bin/python

# use unicode literals
from __future__ import unicode_literals

# sys arguments
import sys
# LINE_PATTERN_REGEX
import re
# opening urls
import urllib
# image manipulation
from PIL import Image, ImageOps, ImageEnhance, ImageDraw
# path checking
import os.path
# handle zip files
import zipfile
# handle tempfiles
import tempfile
# numpy and opencv
import numpy as np
import cv2

# get mtg json
from mtgjson import CardDb

# output directory name
output_dir = sys.argv[2]
output_dir = output_dir.strip()
if not output_dir:
	output_dir = "/tmp"
elif output_dir[-1] == "/":
    output_dir = output_dir[:-1]

# ensure output directory path and cache path exist
if not os.path.exists(output_dir):
	os.mkdir(output_dir)
if not os.path.exists(output_dir + "/.cache"):
	os.mkdir(output_dir + "/.cache")
if not os.path.exists(output_dir + "/.json"):
	os.mkdir(output_dir + "/.json")
if not os.path.exists(output_dir + "/.infill"):
	os.mkdir(output_dir + "/.infill")

# attempt to init from file, if not able, do from url
MTG_JSON_URL = "https://mtgjson.com/json/AllSets.json.zip"
MTG_JSON_ZIP = output_dir + "/.json/AllSets.json.zip"
MTG_JSON_FILE = output_dir + "/.json/AllSets.json"
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
M_04_RELEASE = db.sets.get("4ED").releaseDate

SAVE_MODIFIED_PATTERN = "{:s}/{:s}.png"
SAVE_CACHE_PATTERN = "{:s}/.cache/{:s}.png"

# compile regular expression to remove leading numbers
LINE_PATTERN_REGEX = re.compile(r"^[0-9]+?[ ]+?(.+)$")

# sets we are just not going to pull from
BANNED_SETS = ["mps_akh", "lea", "leb", "pjgp", "pgpx", "ppre", "plpa", "pmgd", "pfnm", "parl", "pmei", "pmpr", "prm", "pcmp", "dd3_gvl", "v14", "s99", "cma", "tsb", "ced", "c16", "ema", "jvc", "dd3_jvc", "exp"]

# url pattern
MCI_INFO_URL_PATTERN = "https://magiccards.info/scans/en/{:s}/{:s}.jpg"
SCRYFALL_INFO_URL_PATTERN = "https://img.scryfall.com/cards/png/en/{:s}/{:s}.png"

# target resize
RESIZE_TARGET = 816,1110

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

def fix_card_with_infill(masky1, masky2, maskx1, maskx2, infillRange, card, img, fill_color = None, use_inverse = True, whiter_white = False, paint = True, dilate_iterations = 6):
	# fill colors for card identities
	FILL_COLORS = {
		"R": (0, 0, 200),
		"G": (0, 200, 0),
		"U": (200, 0, 0),
		"B": (0, 0, 0),
		"W": (210, 210, 210),
		"GLD": (120, 120, 120),
		"N": (195, 195, 195)
	}

	# color bounds for text searching
	WHITE_LOWER_BOUND = np.array([230, 230, 230], dtype = "uint8")
	if whiter_white:
		WHITE_LOWER_BOUND = np.array([240, 240, 240], dtype = "uint8")
	WHITE_UPPER_BOUND = np.array([255, 255, 255], dtype = "uint8")
	BLACK_LOWER_BOUND = np.array([0, 0, 0], dtype = "uint8")
	BLACK_UPPER_BOUND = np.array([95, 95, 95], dtype = "uint8")
	GRAY_LOWER_BOUND = np.array([140, 140, 140], dtype = "uint8")
	GRAY_UPPER_BOUND = np.array([255, 255, 255], dtype = "uint8")

	#  boundary for white text
	boundary_lower = WHITE_LOWER_BOUND
	boundary_upper = WHITE_UPPER_BOUND
	boundary_inverse_lower = BLACK_LOWER_BOUND
	boundary_inverse_upper = BLACK_UPPER_BOUND

	# eventually blend these? multi colored are gold, no color identity is more of a gray
	if not fill_color:
		fill_color = FILL_COLORS["N"]
		if hasattr(card, 'colorIdentity'):
			if len(card.colorIdentity) == 1:
				fill_color = FILL_COLORS[card.colorIdentity[0]]
			else:
				fill_color = FILL_COLORS["GLD"]

	if not hasattr(card, 'colorIdentity') or ("W" in card.colorIdentity or "G" in card.colorIdentity or "R" in card.colorIdentity or "U" in card.colorIdentity):
		# black text
		boundary_lower = BLACK_LOWER_BOUND
		boundary_upper = BLACK_UPPER_BOUND
		boundary_inverse_lower = WHITE_LOWER_BOUND
		boundary_inverse_upper = WHITE_UPPER_BOUND
	elif hasattr(card, 'colorIdentity') and ("B" in card.colorIdentity):
		# more gray-ish text
		boundary_lower = GRAY_LOWER_BOUND
		boundary_upper = GRAY_UPPER_BOUND

	# where files go
	tmpdir = output_dir + "/.infill"
	prefile = tmpdir + "/" + card.name + ".png"
	maskfile = tmpdir + "/mask-" + card.name + ".png"
	img.save(prefile)

	# open temporary file
	cv2_img = cv2.imread(prefile)

	# allow flipping of dilation, etc, when card is flipped
	rect_x = 4
	rect_y = 3
	if hasattr(card, 'layout') and "split" == card.layout:
		rect_x = 3
		rect_y = 4

	# kernel size for morph operations
	kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (rect_x, rect_y))

	# precondition image mask
	range_mask = cv2.blur(cv2_img, (3,3))
	range_mask_mc = range_mask
	#range_mask_invert = 255 - range_mask

	# determine areas of text
	range_mask = cv2.inRange(range_mask, boundary_lower, boundary_upper)
	# chop mask here to make processing faster
	range_mask[masky1:masky2, maskx1:maskx2] = range_mask[masky1:masky2, maskx1:maskx2]
	range_mask = cv2.dilate(range_mask, kernel, iterations = dilate_iterations / 2) # dilate some

	# we are going to invert the image and combine the masks because sometimes there
	# are multiple colors of text
	if use_inverse:
		range_mask_mc = cv2.inRange(range_mask_mc, boundary_inverse_lower, boundary_inverse_upper)
		range_mask_mc[masky1:masky2, maskx1:maskx2] = range_mask_mc[masky1:masky2, maskx1:maskx2]
		range_mask_mc = cv2.dilate(range_mask_mc, kernel, iterations = dilate_iterations) # dilate some because it's usually small
		# combine dilated masks
		range_mask = range_mask + range_mask_mc

	range_mask = cv2.morphologyEx(range_mask, cv2.MORPH_OPEN, kernel) # open
	range_mask = cv2.dilate(range_mask, kernel, iterations = dilate_iterations) # dilate again

	# close with large kernel to remove odd edges?
	lg_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (rect_x * 3, rect_y * 3))
	range_mask = cv2.morphologyEx(range_mask, cv2.MORPH_CLOSE, lg_kernel) # close

	# copy into zero'd arrays the contents of the detection/masking operation
	mask = np.zeros(range_mask.shape, np.uint8)
	mask[masky1:masky2, maskx1:maskx2] = range_mask[masky1:masky2, maskx1:maskx2]
	#mask = range_mask

	# mask out cv2_img
	cv2_img[np.where(mask)] = fill_color

	# write mask(s) so we can see it (debug)
	cv2.imwrite(maskfile, mask)

	# in paint image when requested
	if paint:
		cv2_img = cv2.inpaint(cv2_img, mask, infillRange, cv2.INPAINT_TELEA)
	cv2.imwrite(prefile, cv2_img)

	# return img
	return Image.open(prefile)

def fix_split(card, img):
	img = fix_card_with_infill(170, 480, img.size[0] - 60, img.size[0] - 28, 4, card, img, dilate_iterations = 4, use_inverse = False)
	img = fix_card_with_infill(680, 980, img.size[0] - 60, img.size[0] - 28, 4, card, img, dilate_iterations = 4, use_inverse = False)
	return img

def fix_m15(card, img):
	# variable height based on power/toughness or loyalty (creature/planeswalker)
	MAX_HEIGHT = 60
	MIN_HEIGHT = 38

	height = MAX_HEIGHT
	if hasattr(card, 'power') or hasattr(card, 'toughness') or hasattr(card, 'loyalty'):
		height = MIN_HEIGHT

	# fix right side
	img = fix_card_with_infill(img.size[1] - height, img.size[1] - 5, img.size[0] - 300, img.size[0] - 25, 2, card, img, fill_color = (0, 0, 0), use_inverse = False, whiter_white = True, paint = False)
	# fix left side
	img = fix_card_with_infill(img.size[1] - MAX_HEIGHT, img.size[1] - 5, 25, 300, 2, card, img, fill_color = (0, 0, 0), use_inverse = False, whiter_white = True, paint = False)
	# fix center
	img = fix_card_with_infill(img.size[1] - MIN_HEIGHT, img.size[1] - 5, 300, img.size[0] - 300, 2, card, img, fill_color = (0, 0, 0), use_inverse = False, whiter_white = True, paint = False)

	# return adjusted image
	return img

def fix_pw(card, img):
	return fix_card_with_infill(img.size[1] - 68, img.size[1] - 5, img.size[0] - 575, img.size[0] - 150, 2, card, img, fill_color = (0, 0, 0), use_inverse = False, whiter_white = True, paint = False)

def fix_modern(card, img):
	return fix_card_with_infill(945, 990, 45, 500, 4, card, img)

def fix_old(card, img):
	return fix_card_with_infill(925, 979, 150, 560, 4, card, img)

def fix_ancient(card, img):
	return fix_card_with_infill(930, 974, 50, 450, 4, card, img)

def fix_cards(card, img):
	# crop off 10 pixels on each side to remove borders, potentially adjust for each generation of card
	i_width, i_height = img.size
	img = img.crop([10,10,i_width - 10, i_height - 10])

	# just rgb because transparent corners actually hurt a bit
	img = img.convert('RGB') 

	# default brightness enhancement factor
	l_factor = 1.05

	# version/era specific fixes
	if hasattr(card, 'layout') and "split" == card.layout:
		#print "Fixing split layout card"
		img = ImageOps.autocontrast(img, 15)
		img = fix_split(card, img)
	elif card.set.releaseDate < BFZ_RELEASE and hasattr(card, 'loyalty'):
		#print "Fixing planeswalker card"
		img = ImageOps.autocontrast(img, 12)
		img = fix_pw(card, img)
		l_factor = 1.0
	elif card.set.releaseDate >= M_15_RELEASE:
		#print "Fixing >=M15 card"
		adjust = 0
		if hasattr(card, 'colorIdentity') and "W" in card.colorIdentity:
			adjust = 10
			l_factor = 1.02
		img = ImageOps.autocontrast(img, 18 + adjust)
		img = fix_m15(card, img)
	elif card.set.releaseDate >= M_08_RELEASE:
		#print "Fixing >=8ED card"
		img = ImageOps.autocontrast(img, 10)
		img = fix_modern(card, img)
	elif card.set.releaseDate >= M_04_RELEASE:
		#print "Fixing >=4ED card"
		img = ImageOps.autocontrast(img, 10)
		img = fix_old(card, img)
	else:
		#print "Fixing remaining cards"
		img = ImageOps.autocontrast(img, 10)
		img = fix_ancient(card, img)
		l_factor = 1.08

	# lighten just a little bit
	enhancer = ImageEnhance.Brightness(img)
	img = enhancer.enhance(l_factor)		

	return img

# open file specified to use to find cards
input_filename = sys.argv[1]
file = open(input_filename, "r")
for line in file:
	# condition string
	line = line.rstrip()
	line = LINE_PATTERN_REGEX.sub(r"\1", line)

	# if conditioned line is empty, go to next line
	if not line.strip():
		continue

	# look for oldest version of the card from black bordered sets that are not online only
	# this skips the first four sets because, frankly, they are a little outmoded
	card = None
	for cardSetId in reversed(db.sets.keys()):
		# get card set
		cardSet = db.sets[cardSetId]

		# skip sets without black borders
		if cardSetId.lower() in BANNED_SETS or (hasattr(cardSet,'onlineOnly') and cardSet.onlineOnly):
			continue

		# attempt to get card from db
		cardCheck = cardSet.cards_by_name.get(line)
		# lookup card another way if card not found
		if not cardCheck:
			cardCheck = cardSet.cards_by_ascii_name.get(line.lower())

		# keep card if it is valid and has some sort of numerical identifier
		if not card and cardCheck and getCardId(cardCheck):
			card = cardCheck

		# if card is found with a black border, break (otherwise keep searching)
		# this means that a white bordered card will still show up but if a black bordered
		# version exists it will be pulled down
		if cardCheck and getCardId(cardCheck) and hasattr(card, 'border') and "black" == card.border:
			card = cardCheck
			break

	# if no card is found after search we need to move on
	if not card:
		print "[ERROR] card {:s} not found".format(line)
		# skip rest of loop
		continue

	# look for original image and skip download
	img = None
	cacheImage = SAVE_CACHE_PATTERN.format(output_dir, card.name)
	if os.path.isfile(cacheImage):
		fileLoc = open(cacheImage, "r")
		img = Image.open(fileLoc)
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
		continue

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

	# save data as png to specified folder with file name of the card
	toSave = SAVE_MODIFIED_PATTERN.format(output_dir, card.name)
	output_image.save(toSave)
	print "Saved {:s} (set={:s}, id={:s})".format(toSave, getCardSetCode(card), getCardId(card))