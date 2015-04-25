#!/usr/bin/env python3
import os
# MetaMod:Source and SM extracting
import tarfile
# HTML parsing
from bs4 import BeautifulSoup, element
# Standard import
import sys
# File downloading and such
import requests
# Heavy use of temporary directories
import tempfile
# Escaping user input
import shlex
# Running the editor
import subprocess
from config import config
global ssh
global ftp
if config['connection_agent'] == 'ssh':
    import paramiko
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
elif config['connection_agent'] == 'ftp':
    import ftplib

mmurl = "http://www.gsptalk.com/mirror/sourcemod/mmsource-1.10.4-linux.tar.gz"
smurl = "http://sourcemod.gameconnect.net/files/sourcemod-1.7.1-linux.tar.gz"

try:
    import readline
except: pass

def is_number(number: str):
    try:
        return int(number) != "abc"
    except ValueError:
        try:
            return float(number) != "abc"
        except ValueError:
            return False

# Any definitions here should be ignored unless you like seeing bad code
# Just get an IDE and compress it

def exists(remotefile: str) -> bool:
    """
    Check if a file exists on the server.
    :param remotefile: The filename to check.
    :return: If it exists or not.
    """
    if config['connection_agent'] == 'ssh':
        sftp = paramiko.SFTPClient.from_transport(ssh.get_transport())
        try:
            sftp.stat(remotefile)
        except IOError:
            return False
        else:
            return True
    elif config['connection_agent'] == 'ftp':
        l = ftp.nlst(config['server_root'] + '/' + remotefile.split('/')[:-1])
        return remotefile in l

def list_files(path: str):
    """
    Lists files.
    :param path: The path to list from.
    :return: A list of the files.
    """
    if config['connection_agent'] == 'ssh':
        sftp = paramiko.SFTPClient.from_transport(ssh.get_transport())
        return sftp.listdir(path)
    elif config['connection_agent'] == 'ftp':
        return ftp.nlst(path)

def put_file(filename: str, localfilename: str):
    """
    Puts a file on the server using the SSH or FTP method.
    :param filename: The server filename to write to.
    :param localfilename: The local file to open.
    """
    if config['connection_agent'] == 'ssh':
        assert isinstance(ssh, paramiko.SSHClient)
        sftp = paramiko.SFTPClient.from_transport(ssh.get_transport())
        # Check file exists
        rootdir = '/'.join(filename.split('/')[:-1])
        try:
            sftp.mkdir(rootdir)
        except IOError:
            pass
        with sftp.open(filename, 'wb') as f:
            local = open(localfilename, 'rb')
            f.write(local.read())
            local.close()
    elif config['connection_agent'] == 'ftp':
        rootdir = '/'.join(filename.split('/')[:-1])
        with open(localfilename, 'rb') as local:
            ftp.storbinary("STOR {}".format(filename), local)

def get_file(filename: str, localfilename: str):
    """
    Gets a file on the server using the SSH or FTP method.
    :param filename: The server filename to read from.
    :param localfilename: The local file to save to.
    :return: If the file was successfully downloaded.
    """
    if config['connection_agent'] == 'ssh':
        sftp = paramiko.SFTPClient.from_transport(ssh.get_transport())
        try:
            sftp.get(filename, localfilename)
        except FileNotFoundError:
            print("File not found on the server. Did you enter the right filename?")
            return False
        return True
    elif config['connection_agent'] == "ftp":
        with open(localfilename, 'wb') as f:
            try:
                ftp.retrbinary("RETR {}".format(filename), f.write)
            except Exception as e:
                print("Error: {}".format(e))
                return False
            return True

def get_plugin_name_and_link(b: BeautifulSoup):
    """
    Parses the HTML from the AlliedModders forum and gets the link
    """
    try:
        root_tag = b.find_all('fieldset')[0]
    # Fieldset is the tag for the attachment table.
    except IndexError:
        print("Error: Could not find a fieldset tag in data. Either the HTML layout has changed or the thread was entered incorrectly.")
        return None, None, None
    tables = root_tag.find_all('td')
    # Check if the result is empty.
    if tables == element.ResultSet(""):
        print("Error: Could not find any table tags - link is probably incorrect.")
        return None, None, None
    # Define tables to get data from
    extra_dls = []
    other_smxs = []
    maindl = None
    for table in tables:
        if table.text == "":
            # Probably just an image. Skip it.
            continue
        if 'Get Plugin' in table.text:
            # Main DL link, try and get the link out of it
            # But first verify the main dl hasn't already been gotten
            if maindl is None:
                # A new tuple, with the link to it, and the name of the file
                maindl = (table.find_all('a')[0].get('href'), table.text.split('(')[1].split('.sp')[0] + '.smx')
            else:
                other_smxs.append((table.find_all('a')[0].get('href'), table.text.split('(')[1].split('.sp')[0] + '.smx'))
        else:
            if '.smx' in table.text:
                # Extra plugin SMX
                other_smxs.append((table.find_all('a')[0].get('href'), table.text.replace('\n', '').split('(')[0][:-1])) # Kill me
            else:
                # print("Identified other download")
                extra_dls.append((table.find_all('a')[0].get('href'), table.text.replace('\n', '').split('(')[0][:-1])) # UGH
    return maindl, extra_dls, other_smxs

def install_file(flink, ftype='', name="guess"):
    """
    Installs from a file or direct download link.
    :param ftype: The type of file
    :param flink: The link to the file, or just file name
    :param name: The name of the file if downloading, or to guess it from the URL.
    """
    path = config['server_root'] + '/addons/sourcemod/'
    if ftype == 'smx':
        path += 'plugins/'
    elif ftype == 'cfg':
        path += 'configs/'
    elif ftype == 'translation':
        path += 'translations/'
    elif ftype == 'script':
        path += 'scripting/'
    elif ftype == 'include':
        path += 'scripting/include/'
    elif ftype == 'ext':
        path += 'extensions/'
    else:
        # Try and guess the path
        if '.smx' in flink:
            path += 'plugins/'
        elif '.cfg' in flink or '.ini' in flink:
            path += 'configs/'
        elif 'phrases' in flink or 'tf2items' in flink:
            path += 'translations/' # Special case
        elif '.txt' in flink:
            path += 'cfg/'
        elif '.sp' in flink:
            path += 'scripting/'
        elif '.inc' in flink:
            path += 'scripting/includes/'
        elif '.so' in flink:
            path += 'extensions/'
        else:
            if '/' not in name:
                print("Unrecognised file type. Cannot install properly. Please provide a directory along with the name.")
                return
            else:
                print("Warning: Unrecognised file type. Installing into the directory you provided...")
    if not "http://" in flink and not "https://" in flink:
        if not os.path.exists(flink):
            print("Error: File does not exist. Cannot be installed.")
            return
        if name == "guess":
            put_file(path + flink.split('/')[-1], flink)
        else:
            put_file(path + name, flink)
    else:
        if '.php' in flink and name == "guess":
            print("Error: Cannot extrapolate name from linked file. Cannot install. Please specify a name.")
            return
        else:
            r = requests.get(flink)
            if r.status_code != 200:
                print("Failed to get file.")
                return False
            if name == "guess": name = flink.split('/')[-1].split('?')[0] # Get the last part of the name without any args or such
            with tempfile.TemporaryDirectory() as dir:
                f = open(dir + '/' + name, 'wb')
                f.write(r.content)
                f.close()

                put_file(path + name, dir + '/' + name)
    print("Installed file.")


def swap_plugin_status(plugin, status):
    pass

def get_user_parsed_input():
    # I hate myself
    try:
        user_input = input("sm> ")
    except (EOFError, KeyboardInterrupt):
        return False
    newinput = shlex.split(user_input)
    cmd = newinput[0]
    if cmd == "installt":
        # Check command length
        if len(newinput) < 2:
            print("Error: Must specify at least one thread")
        else:
            for thread in newinput[1:]:
                maindl, extra_dls, other_smxs = get_user_input_plugin_url(thread)
                if not maindl and not extra_dls and not other_smxs:
                    print("Download cancelled.")
                else:
                    download_plugin(maindl, extra_dls, other_smxs)
    elif cmd == "exit":
        return False
    elif cmd == 'edit':
        if len(newinput) < 2:
            print("Error: Must specifiy at least one config.")
        else:
            for cfg in newinput[1:]:
                edit_file(cfg)
    elif cmd == 'installdir':
        if len(newinput) < 2:
            print("Error: Must specify a directory.")
        else:
            install_from_directory(newinput[1])
    elif cmd == "setup":
        if len(newinput) < 2:
            print("Error: Must specify mod to set up.")
        else:
            if newinput[1] == 'sourcemod':
                setup(2)
            elif newinput[1] == 'metamod':
                setup(1)
            else:
                print("Error: Unknown mod to setup.")
    elif cmd == "installf":
        if len(newinput) < 2:
            print("Error: Must specify a file or link to install.")
        else:
            if len(newinput) == 2:
                install_file(newinput[1])
            elif len(newinput) == 3:
                install_file(newinput[1], name=newinput[2])
            else:
                install_file(newinput[1], newinput[3], newinput[2])
    elif cmd == "ls":
        if len(newinput) < 2:
            path = config['server_root']
        else:
            path = config['server_root'] + newinput[1]
        print('\t'.join(list_files(path=path)))
    elif cmd == "lsplugine":
        print('\n'.join([x for x in list_files(path=config['server_root'] + '/addons/sourcemod/plugins') if '.smx' in x]))
    elif cmd == "lsplugind":
        print('\n'.join([x for x in list_files(path=config['server_root'] + '/addons/sourcemod/plugins/disabled') if '.smx' in x]))
    elif cmd == "disable":
        if len(newinput) < 2:
            print("Error: Must specify at least one plugin to disable.")
        else:
            for x in newinput[1:]:
                swap_plugin_status(x, False)
    elif cmd == "enable":
        if len(newinput) < 2:
            print("Error: Must specify at least one plugin to enable.")
        else:
            for x in newinput[1:]:
                swap_plugin_status(x, True)
    elif cmd == "help":
        print("List of commands: ")
        print("help: Displays this help message")
        print("exit: Exits smadmintool")
        print("installt: Installs from the specified threads")
        print("installdir: Installs all files froum the specified directory.")
        print("\tThis directory must be laid out like an addons/ directory, with a sourcemod directory in it and such.")
        print("edit: Edits the specified file.")
        print("setup metamod: Downloads and installs Metamod:Source.")
        print("setup sourcemod: Downloads and installs SourceMod.")
        print("installf: Installs from a file or direct link.")
        print("\tThis command goes in the format: installf file <file_to_install_name> <filetype>")
        print("ls: Lists a remote directory.")
        print("lsplugine: Lists the enabled plugins.")
        print("disable: Disables a plugin.")
        print("lsplugind: Lists all the disabled plugins.")
    else:
        print("Invalid command")

def setup(mod: int):
    if mod == 1:
        print("Downloading latest MM:S...")
        with tempfile.TemporaryDirectory() as dir:
            r = requests.get(mmurl)
            if r.status_code != 200:
                print("Error downloading. URL has probably changed.")
                return
            with open(dir + "/mm.tar.gz", 'wb') as f:
                f.write(r.content)
            os.mkdir(dir + '/mm')
            t = tarfile.open(dir + '/mm.tar.gz')
            t.extractall(dir + '/mm')
            install_from_directory(dir + '/mm/addons/')
        print("Installed.")
    elif mod == 2:
        print("Downloading latest SM...")
        with tempfile.TemporaryDirectory() as dir:
            r = requests.get(smurl)
            if r.status_code != 200:
                print("Error downloading. URL has probably changed.")
                return
            with open(dir + "/sm.tar.gz", 'wb') as f:
                f.write(r.content)
            os.mkdir(dir + '/sm')
            t = tarfile.open(dir + '/sm.tar.gz')
            t.extractall(dir + '/sm/')
            install_from_directory(dir + '/sm/addons/')
        print("Installed.")

def get_user_input_plugin_url(url):
    try:
        r = requests.get(url)
    except requests.exceptions.MissingSchema:
        print("Sorry, the URL you provided is not valid.")
        return (None, None, None)
    if r.status_code == 404:
        print("Error: Thread could not be located.")
        return None, None, None
    elif r.status_code != 200:
        print("Error: Unknown error. Exiting.")
        return None, None, None
    bs = BeautifulSoup(r.content)
    print("Downloading and installing plugin {pl}".format(
        pl='-'.join(bs.title.text.split('-')[:-1])
    ))
    maindl, extra_dls, other_smxs = get_plugin_name_and_link(bs)
    if maindl is None:
        print("WARNING: No main download file. You must pick an alternative SMX file.")
    else:
        print("Main Download: {mdl} ({name})".format(mdl=maindl[0], name=maindl[1]))
    if extra_dls == []:
        print("No extra files to download.")
    else:
        print("Extra downloads:")
        for dl in extra_dls:
            print("\t" + dl[1])
    if other_smxs == []:
        print("No extra SMX files identified.")
        if maindl is None:
            print("Warning: No SMX files identified. This may be a zip-plugin (results may vary) or a data-only plugin.")
            return (None, extra_dls, [])
    else:
        print("Extra SMX files: ")
        for smx in other_smxs:
            print("\t" + smx[1])
    return (maindl, extra_dls, other_smxs) if input("Continue? [Y/n] ").lower() == 'y' else (None, None, None)

def download_plugin(maindl: tuple, extra: list, other_smxs: list):
    to_dl = []
    if other_smxs:
        if maindl is None and len(other_smxs) == 1:
            to_dl.append(other_smxs[0])
        else:
            print("Multiple SMXs have been identified.")
            offset = 1
            if maindl != None:
                print("1. Main Download ({name}) (recommended)".format(name=maindl[1]))
            for smx in other_smxs:
                print("{offset}. {name}".format(offset=offset+1, name=smx[1]))
                offset += 1
            print("You can choose multiple SMXs by separating the numbers with commas.")
            choice = input("Please choose number(s) of DL you want to install: ")
            if ',' in choice:
                choice = [x.replace(' ', '') for x in choice.split(',') if x != '']
            else:
                choice = [choice]
            for smx in choice:
                if not is_number(smx):
                    print("Not a number.")
                    return False
                else:
                    smx = int(smx)
                    if maindl is not None:
                        if smx == 1:
                            to_dl.append(maindl)
                        else:
                            to_dl.append(other_smxs[smx - 2])
                    else:
                        to_dl.append(other_smxs[smx - 1])
    else:
        to_dl.append(maindl)
    with tempfile.TemporaryDirectory() as dir:
        print("Downloading primary plugin file...", end='')
        dl_link = to_dl[0][0] if 'http://' in to_dl[0][0] else "http://forums.alliedmods.net/" + to_dl[0][0]
        r = requests.get(dl_link)
        if r.content == b"Plugin failed to compile! Please try contacting the author.":
            print("\nError: Main plugin DL failed to compile. Continuing download...")
        else:
            with open('{d}/{f}'.format(d=dir, f=to_dl[0][1]), 'wb') as f:
                f.write(r.content)
            # print("Downloaded", os.path.getsize('{d}/{f}'.format(d=dir, f=chosen_dl[1])), "bytes")
            print("done.")
            # Copy file
            put_file(config['server_root'] + '/addons/sourcemod/plugins/{name}'.format(name=to_dl[0][1]),
                     '{d}/{f}'.format(d=dir, f=to_dl[0][1]))
            print("Copied plugin to server.")
        if len(to_dl) > 1:
            for num, smx in enumerate(to_dl[1:]):
                print("Downloading extra plugin {}/{}...".format(num+1, len(to_dl)-1))
                dl_link = smx[0] if 'http://' in smx[0] else "http://forums.alliedmods.net/" + smx[0]
                r = requests.get(dl_link)
                with open('{d}/{f}'.format(d=dir, f=smx[1]), 'wb') as f:
                    f.write(r.content)
                put_file(config['server_root'] + '/addons/sourcemod/plugins/{name}'.format(name=smx[1]),
                    '{d}/{f}'.format(d=dir, f=smx[1]))
        print("Setting up optional files...")
        if not extra:
            print("No extra files to setup.")
        else:
            for file in extra:
                # Identify filetype
                nname = "http://forums.alliedmods.net/" + file[0]
                remotedir = '/addons/sourcemod/'
                if 'phrases' in file[1] or \
                   'tf2items' in file[1]:
                    remotedir += 'translations/'
                elif '.cfg' in file[1] or \
                    'adminmenu_' in file[1] or \
                    '.txt' in file[1]:
                    remotedir += 'configs/'
                elif '.sp' in file[1]:
                    remotedir += 'scripting/'
                elif '.inc' in file[1]:
                    remotedir += 'scripting/include/'
                else:
                    print("Unidentified file {f}, skipping.".format(f=file[1]))
                    continue
                print("Downloading file {f}...".format(f=file[1]), end='')
                r = requests.get(nname, stream=True)
                with open('{d}/{f}'.format(d=dir, f=file[1]), 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk: f.write(chunk); f.flush()
                put_file(config['server_root'] + remotedir + file[1],
                         '{d}/{f}'.format(d=dir, f=file[1]))
                print("Downloaded and copied.")
        print("Installed plugin.")

def install_from_directory(directory):
    if not os.path.exists(directory):
        print("Directory does not exist. Cannot install.")
        return
    for root, _, files in os.walk(directory):
        for file in files:
            print("Copying file {f}...".format(f=file), end='')
            servroot = root.split('addons/')[1]
            put_file(config['server_root'] + 'addons/' + servroot + '/' + file, root + '/' + file)
            print("done.")

def edit_file(file):
    with tempfile.TemporaryDirectory() as dir:
        localfsname = dir + '/' + file.split('/')[-1]
        print("Downloading file...")
        has = get_file(config['server_root'] + file, localfsname)
        if not has:
            print("Cannot edit file.")
            return
        if os.name == "posix":
            editor = os.getenv('EDITOR')
            if not editor: editor = '/usr/bin/nano'
            subprocess.call([editor, localfsname])
        elif os.name == "nt": # Windows support
            os.startfile(localfsname)
        print("Saving file...")
        put_file(config['server_root'] + file, localfsname)

if __name__ == "__main__":
    has_ssh, has_ftp = False, False
    if config['connection_agent'] == "ssh":
        has_ssh = True
        print("Connecting to {h} SSH remote console...".format(h=config['host']))
        try:
            ssh.connect(config['host'], username=config['user'])
        except paramiko.AuthenticationException:
            print("Invalid SSH key!")
            ssh.close()
            sys.exit(1)
        except paramiko.BadHostKeyException:
            print("Server responded with invalid host key.")
            ssh.close()
            sys.exit(1)
        motd = ''.join(ssh.exec_command("cat /var/run/motd.dynamic")[1].readlines())
    else:
        if ['connection_agent'] != 'ftp':
            print("Unrecognised connection agent. Defaulting to FTP.")
        has_ftp = True
        print("Connecting to {h} FTP...".format(h=config['host']))
        ftp = ftplib.FTP(host=config['host'])
        print("Logging in as user {u}".format(u=config['user']))
        try:
            ftp.login(user=config['user'], passwd=config['ftp_pass'])
        except ftplib.error_perm:
            print("Login failed: Incorrect username or password.")
            sys.exit(1)
        motd = ftp.getwelcome()
    print("Connected. System MOTD:\n{motd}".format(motd=motd.replace('220', '')))
    if not exists(config['server_root'] + '/addons/metamod.vdf'):
        print("Metamod:Source doesn't seem to be installed.\nRun \"setup metamod\"to download and install it.")
    if not exists(config['server_root'] + '/addons/sourcemod'):
        print("SourceMod doesn't seem to be installed.\nRun \"setup sourcemod\" to download and install it.")
    while True:
        uip = get_user_parsed_input()
        if uip is False:
            if has_ssh: ssh.close()
            if has_ftp: ftp.close()
            break
