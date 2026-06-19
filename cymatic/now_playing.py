"""Best-effort 'now playing' track name from macOS media players.

Queries the Music and Spotify apps via AppleScript.  Uses System Events to
check whether each app is already running first, so we never launch a player
just to ask it.  Returns "" when nothing is playing or on any error.

First use will trigger a macOS Automation permission prompt ("… wants to
control Music"); if denied, this simply returns "".
"""

import subprocess

# AppleScript: read the playing track from Music, else Spotify, without
# launching either app.
_SCRIPT = '''
set out to ""
tell application "System Events"
    set procs to name of every process
end tell
if procs contains "Music" then
    try
        tell application "Music"
            if player state is playing then
                set out to (artist of current track) & " - " & (name of current track)
            end if
        end tell
    end try
end if
if out is "" and procs contains "Spotify" then
    try
        tell application "Spotify"
            if player state is playing then
                set out to (artist of current track) & " - " & (name of current track)
            end if
        end tell
    end try
end if
return out
'''


def current_track(timeout: float = 2.0) -> str:
    """Return 'Artist - Title' of the currently playing track, or ''."""
    try:
        r = subprocess.run(
            ['osascript', '-e', _SCRIPT],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout.strip()
    except Exception:
        return ""
