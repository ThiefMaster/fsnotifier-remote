# fsnotifier-remote

JetBrains IDEs such as PyCharm or IDEA do not support filesystem change notifications
for network drives. This is understandable since SMB itself does not support this and
you cannot know what's on the other side and/or how to access that machine directly.
However, in my case I do know this and have access to the machine, so let's work around
this. I usually work on windows with the code being on a Samba share on a linux machine
so let's get us some change notifications!

My tool acts as a proxy to both a local and a remote fsnotifier to work around the
inability of getting change notifications for network shares.

## Requirements

- A JetBrains IDE. I've only tested it with PyCharm 3.4 EAP.
- Python 3.4 on both machines. Maybe Python 3.3 works, too. Not tested.
- Key-based authentication on the remote machine
- Pageant on the local machine to provide the private key

## Usage

- Install the Python dependencies from `requirements.txt`
- [Fix](#python3-fixes) some Python3-related issues in PyCrypto and paramiko
- Copy `fsnotifier.yaml.example` to `fsnotifier.yaml` and edit it
- Run `compile-client.bat` to build `fsnotifier.exe` from `fsnotifier.py`
- Run `linux/make.sh` to compile the linux fs notifier
- Edit `bin/idea.properties` in your IDE's install dir and tell it to use our
  fsnotifier instead of the default one:

        idea.filewatcher.executable.path=X:/path/to/your/fsnotifier.exe
- Restart your IDE
- Check the logfile. If it doesn't exist check `idea.log`.
- Enjoy filesystem change notifications even for remote repos! :)

## Python3 fixes

### PyCrypto

They are still using an implicit relative import for `winrandom`. This is fixed
in Git but not in the current release. To fix it, edit `Crypto/Random/OSRNG/nt.py`
and apply this pseudo-diff

    -import winrandom
    +import Crypto.Random.OSRNG.winrandom

    -self.__winrand = winrandom.new()
    +self.__winrand = Crypto.Random.OSRNG.winrandom.new()

### Paramiko

The Pageant integration fails due to Python3's bytes/unicode change. Also easy
to fix:

    -return ctypes.windll.user32.FindWindowA('Pageant', 'Pageant')
    +return ctypes.windll.user32.FindWindowA(b'Pageant', b'Pageant')

    -char_buffer = array.array("c", b(map_name) + zero_byte)
    +char_buffer = array.array("B", b(map_name) + zero_byte)

## Misc

What the heck did the JetBrains devs smoke when adding a [hard file size check][1]
for the fsnotifier binary? At least when a custom path is set a different file
size should not cause it to be considered "outdated" and thus not used at all!

Also, why does [`zipimport`][2] not support ZIP archives with an archive
comment? This would have made adding the padding to get the correct file size
so much cleaner...



 [1]: http://git.io/ICN6JQ
 [2]: https://docs.python.org/3.4/library/zipimport.html
