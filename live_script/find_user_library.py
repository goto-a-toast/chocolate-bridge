"""Print the path of Ableton Live's User Library.

Live stores it in ~/Library/Preferences/Ableton/Live <version>/Library.cfg as
<UserLibrary> ... <ProjectPath Value="/parent/folder" /> with the library
folder "User Library" inside that parent.  The newest Library.cfg wins; with
none found, Live's default (~/Music/Ableton/User Library) is printed.
"""
import glob, os, re

DEFAULT = os.path.expanduser("~/Music/Ableton/User Library")


def user_library():
    cfgs = glob.glob(os.path.expanduser("~/Library/Preferences/Ableton/Live */Library.cfg"))
    for cfg in sorted(cfgs, key=os.path.getmtime, reverse=True):
        with open(cfg, "rb") as f:
            m = re.search(rb'<UserLibrary>.*?<ProjectPath Value="([^"]*)"', f.read(), re.S)
        if m and m.group(1):
            return os.path.join(m.group(1).decode("utf-8"), "User Library")
    return DEFAULT


if __name__ == "__main__":
    print(user_library())
