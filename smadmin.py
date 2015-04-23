#!/usr/bin/env python3
from bs4 import BeautifulSoup
import sys
import requests
import tempfile
import shlex
from config import config
if config['connection_agent'] == 'ssh':
    import paramiko
    global ssh
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
elif config['connection_agent'] == 'ftp':
    import ftplib

import os.path

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

# Any definitions here  should be ignored unless you like seeing bad code
# Just get an IDE and compress it

def get_plugin_name_and_link(b: BeautifulSoup):
    root_tag = b.find_all('fieldset')[0]
    tables = root_tag.find_all('td')
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
                maindl = (table.find_all('a')[0].get('href'), table.text.split('(')[1].split('.sp')[0] + '.smx')
            else:
                other_smxs.append((table.find_all('a')[0].get('href'), table.text.split('(')[1].split('.sp')[0] + '.smx'))
        else:
            if '.smx' in table.text:
                # Extra plugin SMX
                # print("Identified extra SMX")
                other_smxs.append((table.find_all('a')[0].get('href'), table.text.replace('\n', '').split('(')[0][:-1])) # Kill me
            else:
                # print("Identified other download")
                extra_dls.append((table.find_all('a')[0].get('href'), table.text.replace('\n', '').split('(')[0][:-1])) # UGH
    return maindl, extra_dls, other_smxs

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
    else:
        print("Invalid command")

def get_user_input_plugin_url(url):
    try:
        r = requests.get(url)
    except requests.exceptions.MissingSchema:
        print("Sorry, the URL you provided is not valid.")
        return (None, None, None)

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
            print("ERROR: No SMX downloads available! Cannot install the plugin.")
            return (None, None, None)
    else:
        print("Extra SMX files: ")
        for smx in other_smxs:
            print("\t" + smx[1])
    return (maindl, extra_dls, other_smxs) if input("Continue? [Y/n] ").lower() == 'y' else (None, None, None)

def put_file(filename, localfilename):
    if config['connection_agent'] == 'ssh':
        sftp = paramiko.SFTPClient.from_transport(ssh.get_transport())
        with sftp.open(filename, 'wb') as f:
            local = open(localfilename, 'rb')
            f.write(local.read())
            local.close()

def download_plugin(maindl: tuple, extra: list, other_smxs: list):
    chosen_dl = None
    if other_smxs != []:
        if maindl is None and len(other_smxs) == 1:
            chosen_dl = other_smxs[0]
        print("Multiple SMXs have been identified.")
        offset = 1
        if maindl != None:
            print("1. Main Download ({name}) (recommended)".format(name=maindl[1]))
        for smx in other_smxs:
            print("{offset}. {name}".format(offset=offset+1, name=smx[1]))
            offset += 1
        choice = input("Please choose number of DL you want to install: ")
        if not is_number(choice):
            print("Not a number.")
            return False
        else:
            choice = int(choice)
            if maindl is not None:
                if choice == 1:
                    chosen_dl = maindl
                else:
                    chosen_dl = other_smxs[choice - 2]
            else:
                chosen_dl = other_smxs[choice - 1]
    with tempfile.TemporaryDirectory() as dir:
        print("Downloading plugin file...", end='')
        r = requests.get(chosen_dl[0])
        if r.content == b"Plugin failed to compile! Please try contacting the author.":
            print("Error: Main plugin DL failed to compile. Please set an alternative SMX to download.")
            return False
        with open('{d}/{f}'.format(d=dir, f=chosen_dl[1]), 'wb') as f:
                f.write(r.content)
        # print("Downloaded", os.path.getsize('{d}/{f}'.format(d=dir, f=chosen_dl[1])), "bytes")
        print("done.")
        # Copy file
        put_file(config['server_root'] + '/addons/sourcemod/plugins/{name}'.format(name=chosen_dl[1]),
                 '{d}/{f}'.format(d=dir, f=chosen_dl[1]))
        print("Copied plugin to server.")
        print("Setting up optional files...")
        if not extra:
            print("No extra files to setup.")
        else:
            for file in extra:
                # Identify filetype
                nname = "http://www.sourcemod.net/" + file[0]
                remotedir = '/addons/sourcemod/'
                if '.txt' in file[1]:
                    remotedir += 'translations/'
                elif '.cfg' in file[1] or \
                    'adminmenu_' in file[1]:
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

def edit_config_file(file): pass

if __name__ == "__main__":
    if config['connection_agent'] == "ssh":
        print("Connecting to {h} TF2 remote console...".format(h=config['host']))
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
        print("Sorry, only the SSH connection agent is currently supported.")
        motd = "No MOTD available."
    print("Connected. System MOTD:\n{motd}".format(motd=motd))

    print()
    while True:
        uip = get_user_parsed_input()
        if uip is False: break

    #maindl, extra_dls, other_smxs = get_user_input_plugin_url("https://forums.alliedmods.net/showthread.php?t=210221")
    #if not maindl and not extra_dls and not other_smxs:
    #    print("Download cancelled.")
    #else:
    #    download_plugin(maindl, extra_dls, other_smxs)

