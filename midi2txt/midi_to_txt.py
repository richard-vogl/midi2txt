from mido import MidiFile
# we use our own bpm2tempo becaus the mido stuff cuts off decimals - which is not good when the bpm tempo is not an int
from . import bpm2tempo, tempo2bpm
import argparse
import os


def midi_to_txt(input_file, output_file=None, offset=0, bpm=120, write_beats=False, beats_file=None, ignore_unknown=False):

    in_file_path = os.path.dirname(input_file)
    in_file_name = os.path.basename(input_file)
    file_name_wo_ext, _ = os.path.splitext(in_file_name)

    if output_file is None:
        output_file = os.path.join(in_file_path, file_name_wo_ext + ".txt")

    out_file_path = os.path.dirname(output_file)
    out_file_name = os.path.basename(output_file)
    out_file_name_wo_ext, _ = os.path.splitext(out_file_name)

    if beats_file is None:
        beats_file = os.path.join(out_file_path, out_file_name_wo_ext + ".beats")

    times = []
    beat_times = [[0, 1]]
    beat_time = 0.0
    beat_num = 0
    sub_beat = 0

    time_sig_num = 4
    time_sig_denom = 4

    infile = MidiFile(input_file)
    ppq = infile.ticks_per_beat

    midi_tempo = bpm2tempo(bpm)  # = 60 * 1000 * 1000 / bpm
    s_per_tick = midi_tempo / 1000.0 / 1000 / ppq

    print("Reading midi file '"+input_file+"' ...")

    file_type = infile.type

    tempo_track = []
    beats_done = False

    for track_idx, track in enumerate(infile.tracks):
        cur_time = 0
        if file_type == 1:
            if track_idx == 0:  # store track 0 as tempo track
                tempo_track = track
                continue
            else:
                # merge tempo track into current track
                tempo_idx = 0
                track_idx = 0

                cur_track = []
                while tempo_idx < len(tempo_track) or track_idx < len(track):
                    if tempo_idx >= len(tempo_track):
                        cur_track.append(track[track_idx])
                        track_idx += 1
                        continue
                    if track_idx >= len(track):
                        cur_track.append(tempo_track[tempo_idx])
                        tempo_idx += 1
                        continue
                    if tempo_track[tempo_idx].time <= track[track_idx].time:
                        cur_track.append(tempo_track[tempo_idx])
                        track[track_idx].time -= tempo_track[tempo_idx].time
                        tempo_idx += 1
                    else:
                        cur_track.append(track[track_idx])
                        tempo_track[tempo_idx].time -= track[track_idx].time
                        track_idx += 1
        else:
            cur_track = track

        for message in cur_track:
            do_beats = False
            delta_tick = message.time
            delta_time = delta_tick * s_per_tick
            cur_time += delta_time
            if message.type == 'time_signature':
                time_sig_denom = message.denominator
                time_sig_num = message.numerator
                do_beats = True

            if message.type == 'set_tempo':
                midi_tempo = message.tempo
                bpm = tempo2bpm(midi_tempo)
                s_per_tick = midi_tempo / 1000.0 / 1000 / ppq
                do_beats = True

            if message.type == 'note_on' and message.velocity > 0:
                inst_idx = message.note
                velocity = float(message.velocity) / 127.0
                times.append([cur_time, inst_idx, velocity])
                do_beats = True

            # todo: fix beat writing - see and compare separate drums script!!
            if not beats_done and do_beats:
                sub_beat += delta_time * bpm / 60.0 * time_sig_denom / 4.0
                while sub_beat > 1:
                    sub_beat -= 1
                    beat_time += 60.0 / bpm * 4.0 / time_sig_denom
                    beat_num = (beat_num + 1) % time_sig_num
                    beat_times.append([beat_time, beat_num+1])

        beats_done = True

    print("Writing output ...")
    # sort by time (for multiple tracks)
    times.sort(key=lambda tup: tup[0])
    with open(output_file, 'w') as f:
        for entry in times:
            f.write("%3.5f \t %d \t %1.3f \n" % (entry[0]+offset, entry[1], entry[2]))

    if write_beats:
        with open(beats_file, 'w') as f:
            for entry in beat_times:
                f.write("%3.5f \t %d\n" % (entry[0]+offset, entry[1]))

    print("Finished.")


if __name__ == '__main__':

    # add argument parser
    parser = argparse.ArgumentParser(
        description='Convert midi annotations for drum files to txt.')
    parser.add_argument('--infile', '-i', help='input audio file.')
    parser.add_argument('--outfile', '-o', help='output file name.', default=None)
    parser.add_argument('--time_offset', '-m', help='offset for time of labels.', default=0, type=float)
    parser.add_argument('--tempo', '-t', help='Tempo to be used (in BPM) if MIDI file doesn\'t contain tempo events.', default=120, type=float)
    parser.add_argument('--ignore', '-g', help='Ignore unknown midi notes and continue', action='store_true', default=False)

    args = parser.parse_args()

    input_file = args.infile
    output_file = args.outfile
    offset = args.time_offset
    bpm = args.tempo
    ignore_unknown = args.ignore

    midi_to_txt(input_file, output_file, offset, bpm, False, None, ignore_unknown)
