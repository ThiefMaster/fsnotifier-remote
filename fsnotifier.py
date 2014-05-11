import ntpath
import os
import posixpath
import sys
import time
import yaml
from threading import Thread, Lock

import paramiko
import sarge

local_watcher = None
local_stdin = None
ssh_stdin = None
ssh_stdout = None
logfile = None
config = None
lock = Lock()


def update_roots(roots):
    local_stdin.feed('ROOTS\n')
    ssh_stdin.write('ROOTS\n')
    for root in roots:
        root_path = root[1:] if root[0] == '|' else root
        if root_path[0] in config['mapping']:
            remote_path = posixpath.join(config['mapping'][root_path[0]], root_path[3:].replace('\\', '/'))
            prefix = '|' if root[0] == '|' else ''
            ssh_stdin.write(prefix + remote_path + '\n')
        else:
            local_stdin.feed(root + '\n')
    local_stdin.feed('#\n')
    ssh_stdin.write('#\n')


class LocalMonitorThread(Thread):
    def __init__(self, *args, **kwargs):
        super(LocalMonitorThread, self).__init__(*args, **kwargs)
        self.shutdown = False

    def run(self):
        while not self.shutdown:
            for line in local_watcher.stdout.readlines():
                line = line.strip().decode('utf-8')
                if line not in ('UNWATCHEABLE', '#', 'REMAP'):
                    with lock:
                        sys.stdout.write(line + '\n')
                        sys.stdout.flush()
                        if config['log']['verbose']:
                            logfile.write('<< {}\n'.format(line))
                            logfile.flush()
            time.sleep(0.1)


class RemoteMonitorThread(Thread):
    def __init__(self, *args, **kwargs):
        super(RemoteMonitorThread, self).__init__(*args, **kwargs)
        self.shutdown = False

    def run(self):
        while not self.shutdown:
            line = ssh_stdout.readline().strip()
            if not line:
                time.sleep(0.1)
                continue
            if line not in ('UNWATCHEABLE', '#', 'REMAP'):
                # TODO: buffer command + path and write both lines at once to avoid race conditions!
                if line[0] == '/':  # seems to be a path
                    for prefix, drive in config['reverse_mapping'].items():
                        if line.startswith(prefix):
                            line = ntpath.join(drive, ntpath.normpath(line[len(prefix):]))
                            break
                    else:
                        logfile.write('!! Got unmapped path: {}'.format(line))
                        logfile.flush()
                        continue
                with lock:
                    sys.stdout.write(line + '\n')
                    sys.stdout.flush()
                    if config['log']['verbose']:
                        logfile.write('<< {}\n'.format(line))
                        logfile.flush()


def main():
    global local_watcher, local_stdin, ssh_stdin, ssh_stdout, logfile, config

    exe_dir = os.path.dirname(os.path.realpath(sys.executable if hasattr(sys, 'frozen') else sys.argv[0]))
    config_file = os.path.join(exe_dir, 'fsnotifier.yaml')

    try:
        with open(config_file) as f:
            config = yaml.load(f)
    except FileNotFoundError:
        print('Config file not found: {}'.format(config_file))
        sys.exit(1)

    logfile = open(config['log']['file'] if config['log']['enabled'] else os.devnull, 'w')
    config['reverse_mapping'] = {v: '{}:'.format(k) for k, v in config['mapping'].items()}

    # Local notifier
    local_stdin = sarge.Feeder()
    local_watcher = sarge.run(config['fsnotifier']['local'], stdout=sarge.Capture(), input=local_stdin, async=True)
    local_monitor = LocalMonitorThread(daemon=True)

    # Remote notifier
    ssh_conn = paramiko.SSHClient()
    ssh_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_conn.connect(config['ssh']['host'], username=config['ssh']['user'], allow_agent=True)
    ssh_stdin, ssh_stdout, _ = ssh_conn.exec_command(config['fsnotifier']['remote'])
    remote_monitor = RemoteMonitorThread(daemon=True)

    local_monitor.start()
    remote_monitor.start()

    receiving_roots = False
    new_roots = []
    while True:
        line = sys.stdin.readline()
        logfile.write('>> ' + line)
        logfile.flush()
        line = line.strip()
        if receiving_roots:
            if line[0] == '#':
                receiving_roots = False
                update_roots(new_roots)
                with lock:
                    sys.stdout.write('UNWATCHEABLE\n#\nREMAP\n#\n')
                    sys.stdout.flush()
            else:
                new_roots.append(line)
        elif line.upper() == 'ROOTS':
            receiving_roots = True
            new_roots = []
        elif line.upper() == 'EXIT':
            break

    local_monitor.shutdown = True
    remote_monitor.shutdown = True
    local_stdin.feed('EXIT\n')
    try:
        ssh_stdin.write('EXIT\n')
    except OSError:
        # Fails if someone killed the command
        pass
    ssh_conn.close()
    logfile.close()


if __name__ == '__main__':
    main()
