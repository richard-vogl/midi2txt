from mido import MidiFile, bpm2tempo, tempo2bpm
from settings import midi_drum_map
import argparse
import os


if __name__ == '__main__':

    # add argument parser
    parser = argparse.ArgumentParser(
        description='Convert midi annotations for drum files to txt.')
    parser.add_argument('--infile', '-i', help='input audio file.')
    parser.add_argument('--outfile', '-o', help='output file name.', default=None)
    parser.add_argument('--time_offset', '-m', help='offset for time of labels.', default=0, type=float)
    parser.add_argument('--tempo', '-t', help='Tempo to be used (in BPM) if MIDI file doesn\'t contain tempo events.', default=120, type=float)

    args = parser.parse_args()

    input_file = args.infile
    output_file = args.outfile
    offset = args.time_offset
    bpm = args.tempo

    in_file_path = os.path.dirname(input_file)
    in_file_name = os.path.basename(input_file)
    file_name_wo_ext, _ = os.path.splitext(in_file_name)

    if output_file is None:
        output_file = os.path.join(in_file_path, file_name_wo_ext + ".txt")

    cur_time = offset
    times = []

    infile = MidiFile(input_file)
    ppq = infile.ticks_per_beat

    midi_tempo = bpm2tempo(bpm)  # = 60 * 1000 * 1000 / bpm
    s_per_tick = midi_tempo / 1000.0 / 1000 / ppq

    print("Reading midi file ...")

    for msg_idx, track in enumerate(infile.tracks):
        for message in track:
            delta_time = message.time
            cur_time += delta_time * s_per_tick
            if message.type == 'set_tempo':
                midi_tempo = message.tempo
                bpm = tempo2bpm(midi_tempo)
                s_per_tick = midi_tempo / 1000.0 / 1000 / ppq

            if message.type == 'note_on' and message.velocity > 0:
                inst_idx = midi_drum_map.keys()[midi_drum_map.values().index(message.note)]
                if inst_idx is not None:
                    times.append([cur_time, inst_idx])

    print("Writing output ...")

    with open(output_file, 'w') as f:
        # f.write("time\tinstrument\n")
        for entry in times:
            f.write("%3.5f \t %d\n" % (entry[0], entry[1]))

    print("Finished.")
