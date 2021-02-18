from mido import MidiFile, MidiTrack, MetaMessage, Message
# we use our own bpm2tempo becaus the mido stuff cuts off decimals - which is not good when the bpm tempo is not an int
from settings import midi_drum_map
import argparse
import os
from midi2txt import bpm2tempo
import numpy as np

def fix_beats_list(beat_times):
    first_downbeat = 0
    for cur_beat in beat_times:
        if cur_beat[1] == 1:
            first_downbeat = cur_beat[0]
            break

    first_beat = beat_times[0][0]

    # fix beats:
    click_in_beats = max([x[1] for x in beat_times])  # 4
    start_beat_interval = (beat_times[1][0] - first_beat)
    add_beat_times = []
    # check if we started with a downbeat:
    if first_beat != first_downbeat:
        # count beats to fill:
        tf_num_beats = beat_times[0][1] - 1
        bar_finish_time = tf_num_beats * start_beat_interval
        if bar_finish_time <= first_beat:
            # enough time to fill up beats
            # split remaining time TODO: use tempo curve?
            remaining_time = bar_finish_time - first_beat
            init_interval = start_beat_interval
        else:
            remaining_time = 0
            init_interval = first_beat / tf_num_beats

        add_beat_times = [[remaining_time + beat * init_interval, beat + 1] for beat in range(tf_num_beats)]
    else:
        remaining_time = first_beat

    # add a bar to cover start silence
    if sync_to_audio and remaining_time > 0:
        interval = remaining_time / click_in_beats
        add_beat_times = [[beat * interval, beat + 1] for beat in range(click_in_beats)] + add_beat_times

    beat_times = add_beat_times + beat_times

    return beat_times


def smooth_beat_list(beat_times, smooth):
    #TODO sounds good, doesnt work like this...
    import numpy as np
    deltas = np.diff(np.asarray(beat_times)[:, 0])

    cumsum = np.cumsum(deltas)
    means = (cumsum[smooth:] - cumsum[:-smooth]) / float(smooth)

    shifts = deltas - np.hstack((np.repeat(means[0], smooth), means))

    beat_times_new = [[item[0][0] - item[1], item[0][1]] for item in zip(beat_times, np.hstack(([0], shifts)))]
    
    return beat_times


def midi_delta_time(delta_time, s_per_tick):
    return int(max(np.ceil(delta_time / s_per_tick), 0.0))


def back_from_midi_time(delta_time, s_per_tick):
    return delta_time*s_per_tick


if __name__ == '__main__':

    # add argument parser
    parser = argparse.ArgumentParser(
        description='Convert text annotations for drum files to midi.')
    parser.add_argument('--infile', '-i', help='input audio file.')
    parser.add_argument('--beatfile', '-b', help='input beat file.', default=None)
    parser.add_argument('--outfile', '-o', help='output file name.', default=None)
    parser.add_argument('--tempo', '-t', help='tempo of midi file in BPM', default=120, type=float)
    parser.add_argument('--program', '-p', help='program number of midi track', default=0)
    parser.add_argument('--channel', '-c', help='channel number of midi track', default=10)
    parser.add_argument('--ignore', '-g', help='Ignore unknown instrument notes and continue', action='store_true', default=False)
    parser.add_argument('--no_map', '-n', help='Dont map midi isntrument notes', action='store_true',
                        default=False)
    parser.add_argument('--smooth', '-s', help='smooth tempo curve, use a floating window of N beats', type=int, default=0)
    parser.add_argument('--sync_to_audio', '-a', help='Make MIDI output synchronous to audio. If beats are used, usa a bar at the beginning to fill the silence', type=bool, default=True)

    args = parser.parse_args()
    # prepare input params
    input_file = args.infile
    input_beat_file = args.beatfile
    output_file = args.outfile
    bpm = args.tempo
    program_nr = args.program
    channel_nr = args.channel
    ignore_unknown = args.ignore
    sync_to_audio = args.sync_to_audio
    no_map = args.no_map
    smooth = args.smooth

    in_file_path = os.path.dirname(input_file)
    is_input_dir = os.path.isdir(input_file)

    beat_files = None
    use_beats = input_beat_file is not None
    if use_beats:
        beat_file_path = os.path.dirname(input_beat_file)
        use_beats = use_beats and os.path.exists(input_beat_file)
        is_input_beat_dir = os.path.isdir(input_beat_file)

    if is_input_dir:
        files = os.listdir(input_file)
        files = [x for x in files if x.endswith('.txt') or x.endswith('.drums')]
        has_out_dir = output_file is not None and os.path.isdir(output_file)

        if use_beats:
            assert is_input_beat_dir
            # find beat file for txt files
            beat_files = []
            for in_file_idx, input_file in enumerate(files):
                file_name_wo_ext, in_ext = os.path.splitext(input_file)
                found = False
                for beat_ext in ['.beats', '.beats.txt', '.'+in_ext+'.beats', '.'+in_ext+'.beats.txt']:
                    cand_beat_file = os.path.join(beat_file_path, file_name_wo_ext+beat_ext)
                    if os.path.exists(cand_beat_file):
                        beat_files.append(cand_beat_file)
                        found = True
                        break
                if not found:
                    beat_files.append(None)
    else:
        files = [os.path.basename(input_file)]
        if use_beats:
            beat_files = [os.path.basename(input_beat_file)]

    # loop over input files
    for in_file_idx, input_file in enumerate(files):
        file_name_wo_ext, _ = os.path.splitext(input_file)
        beat_times = None
        if use_beats:
            beat_file = beat_files[in_file_idx]

            if beat_files is not None:
                with open(os.path.join(beat_file_path, beat_file)) as f:
                    content = f.readlines()

                beat_times = []
                for i_line, line in enumerate(content):
                    parts = line.split()
                    time = float(parts[0])
                    beat_num = int(parts[1])
                    beat_times.append([time, beat_num])

                beat_times = fix_beats_list(beat_times)

                if smooth > 0:
                    # smooth tempo curve - i.e. move beats to average grid positions using a floating window
                    beat_times = smooth_beat_list(beat_times, smooth)

        if output_file is None or (not os.path.isdir(output_file) and is_input_dir):
            output_file = os.path.join(in_file_path, file_name_wo_ext + ".mid")
        elif os.path.isdir(output_file):
            output_file = os.path.join(output_file, file_name_wo_ext + ".mid")

        with open(os.path.join(in_file_path, input_file)) as f:
            content = f.readlines()

        times = []
        for i_line, line in enumerate(content):
            parts = line.split()
            time = float(parts[0])
            inst = int(parts[1])
            times.append([time, inst])

        with MidiFile() as outfile:
            ppq = 192
            midi_tempo = bpm2tempo(bpm)
            s_per_tick = midi_tempo / 1000.0 / 1000 / ppq

            track = MidiTrack()
            outfile.tracks.append(track)
            outfile.type = 0
            outfile.ticks_per_beat = ppq

            found_beats = use_beats and beat_times is not None and len(beat_times) > 0

            if not found_beats:
                track.append(MetaMessage('set_tempo', tempo=midi_tempo))

            track.append(Message('program_change', program=program_nr, time=0))
            lastTime = 0
            times.sort(key=lambda tup: tup[0])
            if use_beats:
                beat_times.sort(key=lambda tup: tup[0])

            beat_idx = 0
            last_tempo = None
            last_timesig = None
            for entry in times:

                if found_beats:
                    while beat_times[beat_idx][0] < entry[0]:
                        cur_time = beat_times[beat_idx][0]
                        # check time signature on downbeats and add an event if we must change signature
                        if beat_times[beat_idx][1] == 1:
                            time_sig_idx = beat_idx+1
                            while time_sig_idx < len(beat_times) and beat_times[time_sig_idx][1] != 1:
                                time_sig_idx += 1
                            cur_timesig = beat_times[time_sig_idx-1][1]

                            if last_timesig is None or cur_timesig != last_timesig:
                                deltaTime = midi_delta_time(cur_time - lastTime, s_per_tick)
                                lastTime = lastTime + back_from_midi_time(deltaTime, s_per_tick)
                                # lastTime = cur_time

                                track.append(MetaMessage('time_signature', time=deltaTime, numerator=cur_timesig,
                                                         denominator=4))
                                last_timesig = cur_timesig

                        # calculate current tempo and check if we need a tempo change event and add it in case
                        if beat_idx >= len(beat_times)-1:
                            cur_tempo = last_tempo
                        else:
                            cur_tempo = 1e6 * (beat_times[beat_idx+1][0] - beat_times[beat_idx][0])
                        if last_tempo is None or cur_tempo != last_tempo:
                            deltaTime = midi_delta_time(cur_time - lastTime, s_per_tick)
                            lastTime = lastTime + back_from_midi_time(deltaTime, s_per_tick)
                            # lastTime = cur_time

                            track.append(MetaMessage('set_tempo', tempo=int(round(cur_tempo)), time=deltaTime))
                            last_tempo = cur_tempo
                            s_per_tick = cur_tempo / 1000.0 / 1000 / ppq

                        beat_idx += 1

                cur_time = entry[0]
                deltaTime = midi_delta_time(cur_time - lastTime, s_per_tick)
                lastTime = lastTime + back_from_midi_time(deltaTime, s_per_tick)
                # lastTime = cur_time

                if entry[1] in midi_drum_map or no_map:
                    if no_map:
                        note = entry[1]
                    else:
                        note = midi_drum_map[entry[1]]
                    track.append(Message('note_on', note=note, velocity=100,
                                         time=deltaTime, channel=channel_nr))
                    #  print('event: note: %d, time: %d'% (note, curTime))
                    track.append(Message('note_off', note=note, velocity=100, time=0, channel=channel_nr))

                elif not ignore_unknown:
                    print("unknown instrument type with value: "+str(entry[1])+" . Remove event or run again with -g parameter to ignore.")
                    exit()

            outfile.save(output_file)
