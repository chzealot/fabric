from __future__ import with_statement

import sys
import time
from select import select

from fabric.state import env, output, win32
#from fabric.auth import get_password, set_password
from fabric.contrib.auth_keyring import get_sudo_password as get_password
from fabric.contrib.auth_keyring import set_sudo_password as set_password
import fabric.network
from fabric.network import ssh

if win32:
    import msvcrt


def _flush(pipe, text):
    pipe.write(text)
    pipe.flush()


def _endswith(char_list, substring):
    tail = char_list[-1 * len(substring):]
    substring = list(substring)
    return tail == substring


def _is_newline(byte):
    return byte in ('\n', '\r')


def _was_newline(capture, byte):
    """
    Determine if we are 'past' a newline and need to print the line prefix.
    """
    endswith_newline = _endswith(capture, '\n') or _endswith(capture, '\r')
    return endswith_newline and not _is_newline(byte)


def output_loop(chan, attr, stream, capture):
    """
    Loop, reading from <chan>.<attr>(), writing to <stream> and buffering to <capture>.
    """
    # Internal capture-buffer-like buffer, used solely for state keeping.
    # Unlike 'capture', nothing is ever purged from this.
    _buffer = []
    # Obtain stdout or stderr related values
    func = getattr(chan, attr)
    _prefix = "[%s] %s: " % (
        env.host_string,
        "out" if attr == 'recv' else "err"
    )
    printing = getattr(output, 'stdout' if (attr == 'recv') else 'stderr')
    # Initialize loop variables
    reprompt = False
    initial_prefix_printed = False
    line = []
    linewise = (env.linewise or env.parallel)
    while True:
        # Handle actual read/write
        byte = func(1)
        # Empty byte == EOS
        if byte == '':
            # If linewise, ensure we flush any leftovers in the buffer.
            if linewise and line:
                _flush(stream, _prefix)
                _flush(stream, "".join(line))
            break
        # A None capture variable implies that we're in open_shell()
        if capture is None:
            # Just print directly -- no prefixes, no capturing, nada
            # And since we know we're using a pty in this mode, just go
            # straight to stdout.
            _flush(sys.stdout, byte)
        # Otherwise, we're in run/sudo and need to handle capturing and
        # prompts.
        else:
            # Allow prefix to be turned off.
            if not env.output_prefix:
                _prefix = ""
            # Print to user
            if printing:
                if linewise:
                    # Print prefix + line after newline is seen
                    if _was_newline(_buffer, byte):
                        _flush(stream, _prefix)
                        _flush(stream, "".join(line))
                        line = []
                    # Add to line buffer
                    line += byte
                else:
                    # Prefix, if necessary
                    if (
                        not initial_prefix_printed
                        or _was_newline(_buffer, byte)
                    ):
                        _flush(stream, _prefix)
                        initial_prefix_printed = True
                    # Byte itself
                    _flush(stream, byte)
            # Store in capture buffer
            capture += byte
            # Store in internal buffer
            _buffer += byte
            # Handle prompts
            prompt = _endswith(capture, env.sudo_prompt)
            try_again = (_endswith(capture, env.again_prompt + '\n')
                or _endswith(capture, env.again_prompt + '\r\n'))
            if prompt:
                # Obtain cached password, if any
                password = get_password()
                # Remove the prompt itself from the capture buffer. This is
                # backwards compatible with Fabric 0.9.x behavior; the user
                # will still see the prompt on their screen (no way to avoid
                # this) but at least it won't clutter up the captured text.
                del capture[-1 * len(env.sudo_prompt):]
                # If the password we just tried was bad, prompt the user again.
                if (not password) or reprompt:
                    # Print the prompt and/or the "try again" notice if
                    # output is being hidden. In other words, since we need
                    # the user's input, they need to see why we're
                    # prompting them.
                    if not printing:
                        _flush(stream, _prefix)
                        if reprompt:
                            _flush(stream, env.again_prompt + '\n' + _prefix)
                        _flush(stream, env.sudo_prompt)
                    # Prompt for, and store, password. Give empty prompt so the
                    # initial display "hides" just after the actually-displayed
                    # prompt from the remote end.
                    chan.input_enabled = False
                    password = fabric.network.prompt_for_password(
                        prompt=" ", no_colon=True, stream=stream
                    )
                    chan.input_enabled = True
                    # Update env.password, env.passwords if necessary
                    set_password(password)
                    # Reset reprompt flag
                    reprompt = False
                # Send current password down the pipe
                chan.sendall(password + '\n')
            elif try_again:
                # Remove text from capture buffer
                capture = capture[:len(env.again_prompt)]
                # Set state so we re-prompt the user at the next prompt.
                reprompt = True


def input_loop(chan, using_pty):
    while not chan.exit_status_ready():
        if win32:
            have_char = msvcrt.kbhit()
        else:
            r, w, x = select([sys.stdin], [], [], 0.0)
            have_char = (r and r[0] == sys.stdin)
        if have_char and chan.input_enabled:
            # Send all local stdin to remote end's stdin
            byte = msvcrt.getch() if win32 else sys.stdin.read(1)
            chan.sendall(byte)
            # Optionally echo locally, if needed.
            if not using_pty and env.echo_stdin:
                # Not using fastprint() here -- it prints as 'user'
                # output level, don't want it to be accidentally hidden
                sys.stdout.write(byte)
                sys.stdout.flush()
        time.sleep(ssh.io_sleep)
