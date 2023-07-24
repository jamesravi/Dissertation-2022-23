# Requirements
* Python 3 (tested with Python versions 3.7 to 3.11)
* Windows, macOS or Linux (tested with Windows 11, Ubuntu 22.04.2 LTS and macOS Monterey)

# Instructions on how to run
1. Install the required requirements by running the command `pip install -r requirements.txt`
2. Now either:
	* Run `rafdp.py` to start a RAFDP dameon (which can be controlled using `rafdp-cli.py`, try `rafdp-cli.py -h` for help)
	* Run `virtfilesystem.py` to start a virtual filesystem and integrated RAFDP dameon (which can be controlled using `virtfilesystem-cli.py`, try `virtfilesystem-cli.py -h` for help)
	* Run `demo.py` to simulate the mounting and transfer of a video file between a virtual filesystem and integrated RAFDP peer and another RAFDP peer

# Dependencies license attribution
* [Paramiko](https://github.com/paramiko/paramiko), licensed under the GNU Lesser General Public License v2.1
* [Multiformats](https://github.com/hashberg-io/multiformats), licensed under the MIT license
* [Requests](https://github.com/psf/requests), licensed under the Apache License 2.0
* [bencode.py](https://github.com/fuzeman/bencode.py), licensed under the BitTorrent Open Source License
* [Flask](https://github.com/pallets/flask), licensed under the 3-clause BSD license
* [psutil](https://pypi.org/project/psutil), licensed under the 3-clause BSD license

# Test files license attribution
* ["Tabby cat with blue eyes"](https://commons.wikimedia.org/wiki/File:Tabby_cat_with_blue_eyes-3336579.jpg) (cat.jpg) by Adina Voicu is licensed under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/deed.en)
* ["Great Expectations"](https://www.gutenberg.org/ebooks/1400) (greatexpectations.txt) by Charles Dickens is in the public domain worldwide
* ["Poetic ballad in the empty streets of Paris"](https://commons.wikimedia.org/wiki/File:Paris_lockdown_-_Vimeo.webm) (videotest.webm) by Jean-Luc Perréard is licensed under [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/deed.en)

# Copyright
Copyright (c) 2023 James Ravindran. All rights reserved.