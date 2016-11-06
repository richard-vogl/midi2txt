from mido import MidiFile, MidiTrack, MetaMessage, Message, bpm2tempo
from settings import midi_drum_map
import argparse
import os


if __name__ == '__main__':

    # add argument parser
    parser = argparse.ArgumentParser(
        description='Convert text annotations for drum files to midi.')
    parser.add_argument('--infile', '-i', help='input audio file.')
    parser.add_argument('--outfile', '-o', help='output file name.', default=None)
    parser.add_argument('--tempo', '-t', help='tempo of midi file in BPM', default=120, type=float)
    parser.add_argument('--program', '-p', help='program number of midi track', default=0)
    parser.add_argument('--channel', '-c', help='channel number of midi track', default=10)

    args = parser.parse_args()

    input_file = args.infile
    # input_file = "/Users/Rich/Desktop/Red Bull Music Academy - Various Assets - Not For Sale- Red Bull Music - 01 August Rosenbaum, Jameszoo & Stephen Bruner - Jordi.drums_A.txt_orig"
    # "/Users/Rich/datasets/rbma/2013 New York/"
    # "/Users/Rich/datasets/rbma/2011 Madrid/"
    # "/Users/Rich/datasets/rbma/2010 London/"
    # input_file = "/Users/Rich/datasets/rbma/2013 New York/annotations (JKU)/Red Bull Music Academy - Various Assets - Not For Sale- Red Bull Music - 02 DJ Slow & Sinjin Hawke - On Now.drums.txt"
    output_file = args.outfile
    bpm = args.tempo
    program_nr = args.program
    channel_nr = args.channel

    in_file_path = os.path.dirname(input_file)
    is_input_dir = os.path.isdir(input_file)
    if is_input_dir:
        files = os.listdir(input_file)
        files = [x for x in files if x.endswith('.txt') or x.endswith('.drums')]
        has_out_dir = output_file is not None and os.path.isdir(output_file)
    else:
        files = [os.path.basename(input_file)]

    for input_file in files:
        file_name_wo_ext, _ = os.path.splitext(input_file)

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

            track.append(MetaMessage('set_tempo', tempo=midi_tempo))

            track.append(Message('program_change', program=program_nr, time=0))
            lastTime = 0
            times.sort(key=lambda tup: tup[0])
            for entry in times:
                curTime = max(int((entry[0]) / s_per_tick), 0)
                deltaTime = curTime - lastTime
                lastTime = curTime

                note = midi_drum_map[entry[1]]
                track.append(Message('note_on', note=note, velocity=100,
                                     time=deltaTime, channel=channel_nr))
                #  print('event: note: %d, time: %d'% (note, curTime))
                track.append(Message('note_off', note=note, velocity=100, time=0, channel=channel_nr))

            outfile.save(output_file)
