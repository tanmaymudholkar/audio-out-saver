import argparse
import os
import subprocess
import pprint
import re
import yaml
import signal
import time

"""
Example of YAML input:
---
-
  - 'england_englishness'
  - '53:44'
- 
  - 'op_barbarossa'
  - '54:58'
- 
  - 'biggest_qs_1'
  - '56:42'
- 
  - 'biggest_qs_2'
  - '59:56'
- 
  - 'agatha_christie'
  - '53:13'
- 
  - 'how_pms_fall'
  - '1:05:39'
- 
  - 'first_fascist'
  - '59:50'
- 
  - 'watergate_1'
  - '45:17'
- 
  - 'watergate_2'
  - '48:02'
...
"""

node_id     = None
node_serial = None
vol_orig_pc = None

def set_volume(tgt):
    if node_id is None:
        raise ValueError
    subprocess.check_call(
        f'wpctl set-volume {node_id} {tgt}%',
        shell=True, executable='/usr/bin/zsh'
    )

def get_time_in_seconds(time_str: str)\
        -> int:
    time_str_split = time_str.split(':')
    if len(time_str_split) == 1:
        return int(time_str_split[0])
    if len(time_str_split) == 2:
        return (
            60*int(time_str_split[0]) +
            int(time_str_split[1])
        )
    if len(time_str_split) == 3:
        return (
            3600*int(time_str_split[0]) +
            60*int(time_str_split[1]) +
            int(time_str_split[2])
        )
    raise ValueError

def parse_serial_id(pw_cli_output: str) -> int:
    re_nodeinfo_begin = re.compile(r'id ([0-9]+), type .*')
    re_serial         = re.compile(r'object.serial = "([0-9]+)"')
    re_media_class    = re.compile(r'media\.class = "Audio/Sink"')
    re_node_desc      = re.compile(r'node\.description = ".*HD Audio Controller Analog Stereo"')
    node_id             = None
    node_serial         = None
    media_class_matches = False
    node_desc_matches   = False
    for line_raw in pw_cli_output.split('\n'):
        line = line_raw.strip()
        match_nodeinfo_begin = re_nodeinfo_begin.match(line)
        if match_nodeinfo_begin:
            node_id = int(match_nodeinfo_begin.group(1))
            node_serial         = None
            media_class_matches = False
            node_desc_matches   = False
            continue
        match_serial = re_serial.match(line)
        if match_serial:
            node_serial = int(match_serial.group(1))
        if not media_class_matches:
            if re_media_class.match(line):
                media_class_matches = True
        if not node_desc_matches:
            if re_node_desc.match(line):
                node_desc_matches = True
        if media_class_matches and node_desc_matches:
            break
    if (node_id is None) or (node_serial is None):
        raise ValueError('ERROR: Unable to find audio node ID.')

def parse_vol_output_pc(vol_output: str) -> int:
    re_match = re.match(r'Volume: (.*)', vol_output)
    if re_match is None:
        raise ValueError(f'Unable to parse vol_output: {vol_output}')
    return max(0, min(100, round(100.*float(re_match.group(1)))))

def main(args):
    os.makedirs(args.out_dir, exist_ok=True)
    tracks = None
    with open(args.tracks_yaml, 'r') as tracks_yaml_file_obj:
        tracks = yaml.safe_load(tracks_yaml_file_obj)

    pprint.pp(tracks)

    # find ID of audio sink
    pw_cli_output = subprocess.check_output(
        'pw-cli list-objects Node',
        shell=True, executable='/usr/bin/zsh', text=True,
    )
    parse_serial_id(pw_cli_output)
    print(f'Found audio serial number: {node_serial}')

    # get current volume level
    vol_output = subprocess.check_output(
        f'wpctl get-volume {node_id}',
        shell=True, executable='/usr/bin/zsh', text=True,
    )
    vol_orig_pc = parse_vol_output_pc(vol_output)
    # set volume to 100%
    set_volume(100)

    subprocess.check_call(
        'notify-send Get ready...',
        shell=True, executable='/usr/bin/zsh',
    )
    for i in range(5):
        time.sleep(1.)
        subprocess.check_call(
            f'notify-send {5-i}...',
            shell=True, executable='/usr/bin/zsh',
        )
    time.sleep(1.)
    subprocess.check_call(
        'notify-send Starting!',
        shell=True, executable='/usr/bin/zsh',
    )

    for i, track_info in enumerate(tracks):
        if not(len(track_info) == 2):
            print('Malformed input:')
            pprint.pp(track_info)
            raise ValueError
        title, time_str = track_info
        time_in_seconds = get_time_in_seconds(time_str)
        print(f'Saving track with title {title}, time in seconds: {time_in_seconds}')
        try:
            subprocess.check_call(
                f'pw-record --target "{node_serial}" {args.out_dir}/{(i+args.idx_min):04}_{title}.wav',
                shell=True,
                executable='/usr/bin/zsh',
                timeout=time_in_seconds,
            )
        except subprocess.TimeoutExpired:
            # always should end here
            pass
    set_volume(vol_orig_pc)
    print('All Done.')

def exit_gracefully() -> None:
    if (node_id is None) or (vol_orig_pc is None):
        return
    set_volume(vol_orig_pc)

if __name__ == '__main__':
    signal.signal(signal.SIGINT,  exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)
    parser = argparse.ArgumentParser()
    parser.add_argument('--tracks_yaml', required=True)
    parser.add_argument('--out_dir',     required=True)
    parser.add_argument('--idx_min', type=int, default=1)
    args = parser.parse_args()
    main(args)
