import os
import shutil
import sys
import tempfile
import zipfile
import yaml


def load_config():
    try:
        with open('fsnotifier.yaml') as f:
            return yaml.load(f)
    except FileNotFoundError:
        print('Config file not found')
        sys.exit(1)


def main():
    config = load_config()
    expected = os.path.getsize(config['fsnotifier']['local'])
    size = os.path.getsize('fsnotifier.exe')
    padding_size = expected - size
    if not padding_size:
        return
    # Figure out how much space the padding file entry needs
    temp = tempfile.TemporaryFile()
    with open('fsnotifier.exe', 'rb') as f:
        shutil.copyfileobj(f, temp)
    temp.seek(0)
    with zipfile.ZipFile(temp, 'a') as zf:
        zf.writestr('useless.padding', '', zipfile.ZIP_STORED)
    temp.seek(0, os.SEEK_END)
    file_entry_size = temp.tell() - size
    padding_size -= file_entry_size
    if padding_size <= 0:
        print('Cannot add a padding of {} bytes'.format(padding_size))
        sys.exit(1)
    # Create the actual padding
    with zipfile.ZipFile('fsnotifier.exe', 'a') as zf:
        padding = b'\0' * padding_size
        zf.writestr('useless.padding', padding, zipfile.ZIP_STORED)


if __name__ == '__main__':
    main()
