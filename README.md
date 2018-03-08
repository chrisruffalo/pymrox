# PyMrox

Makes proxy images by removing copyrights from MTG card images.

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