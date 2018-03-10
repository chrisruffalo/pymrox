# PyMrox

Makes proxy images by removing copyrights from MTG card images. This is intended for proxy/playtest purposes only. I do not condone stealing MTG cards but sometimes you want to make a high quality proxy. Various card printing services will not print images with a copyright on them. Removing the copyright serves two purposes. The first is to allow them to be printed. The second is to do so in such a way that the card could **never** be mistaken for the real thing even to the most casual observer.

## Prerequisites
* python2
* python2-opencv
* numpy
* PIL
* mtgjson

## Use

Command looks like:
```bash
[]$ python PyMrox.py <path to card list> <output directory>
```

Card list is what would be exported from TappedOut or similar. Card number then card title.
```txt
1 Academy Ruins
1 Advantageous Proclamation
1 Ajani Vengeant
1 Albino Troll
1 Ancestral Recall
1 Approach of the Second Sun
1 Arc Blade
1 Arcane Denial
1 Armageddon
1 Aura of Silence
1 Avalanche Riders
1 Backup Plan
1 Badlands
1 Balance
1 Beast Within
1 Black Lotus
1 Braids, Cabal Minion
1 Mox Diamond
1 Mutavault
1 Nevinyrral's Disk
1 Sneak Attack
1 Sol Ring
1 Wrath of God
1 Wurmcoil Engine
```

Sample command:
```bash
[]$ python PyMrox.py ~/Downloads/mydeck.txt ~/mydeck
```

## Fixing Errors
Sometimes the MTG JSON for a card does not match up to the scryfall data (meaning that MTGJSON is a bit off). In these cases you have three choices.

### File an Issue with MTGJSON
This is the right way to fix errors. If the MTGJSON has an issue let them know so that the set/card/value can be realligned.

### Ban the Set
In `PyMrox.py` there is a variable called BANNED_SETS. What this does is skips the set when looking at the cards. Adding a set code to this value removes that set from consideration entirely.

### Ban the Card
In `PyMrox.py` there is a variable called BANNED_CARDS. This is a dictionary of card sets and the cards in those sets that have bad data. This is a lot more selective than removing the entire set from consideration.

### Overwrite the Image
You can also go to your output directory, overwrite the bad card with a good image from Scyfall or a similar collection, and then re-run PyMrox.