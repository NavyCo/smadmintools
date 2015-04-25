# Sourcemod Admin Tools
smadmin provides a set of easy tools to manage a sourcemod server with.  
smadmin connects to your server over either FTP or SSH. It can remotely install plugins, disable them, automatically setup MetaMod:Source and SourceMod on a new server, and more.  
  
## Dependencies
smadmin is written in Python 3, using the libraries BeautifulSoup and requests. For SSH support, Paramiko is also required.  

To install these, run:  
```pip install BeautifulSoup4 requests paramiko```

Once these are installed, you must edit config.py, adding your server hostname, server user, and (if using) FTP password. SSH passwords are not and will not be supported - learn to use SSH keys.  
Valid commands are listed as follows:
```
help: Displays this help message
exit: Exits smadmintool
installt: Installs from the specified threads
installdir: Installs all files froum the specified directory.
	This directory must be laid out like an addons/ directory, with a sourcemod directory in it and such.
edit: Edits the specified file.
setup metamod: Downloads and installs Metamod:Source.
setup sourcemod: Downloads and installs SourceMod.
installf: Installs from a file or direct link.
	This command goes in the format: installf file <file_to_install_name> <filetype>
ls: Lists a remote directory.
enable: Enables a plugin.
lsplugine: Lists the enabled plugins.
disable: Disables a plugin.
lsplugind: Lists all the disabled plugins.
```