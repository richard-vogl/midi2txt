from mido import MidiFile
import argparse
import copy
from midi2txt import bpm2tempo
from midi2txt import calc_beat_times

import os

MIDI_DRUM_MIN_NOTE = 35
MIDI_DRUM_MAX_NOTE = 81


def split_midi(input_file, output_file_midi_drums=None, output_file_beats=None, output_file_drums=None,
               output_file_midi_accomp=None, write_beats=True, mapping_catalog={}, folders_postfix=[''],
               mapping_sel=0, parse_and_write=True, add_velocity=True):

    in_file_path = os.path.dirname(input_file)
    in_file_name = os.path.basename(input_file)
    file_name_wo_ext, _ = os.path.splitext(in_file_name)

    fid = in_file_name.split('_')[0]
    if fid in mapping_catalog:
        mappings = mapping_catalog[fid]
        mapping_dict = {in_inst: out_inst for in_inst, out_inst in mappings}
    else:
        mapping_dict = {}
        
    if output_file_midi_drums is None:
        output_file_midi_drums = os.path.join(in_file_path, 'midi', 'drums' + folders_postfix[mapping_sel],
                                              file_name_wo_ext + ".mid")
    if output_file_midi_accomp is None:
        output_file_midi_accomp = os.path.join(in_file_path, 'midi', 'accomp' + folders_postfix[mapping_sel],
                                               file_name_wo_ext + ".mid")
    if output_file_beats is None:
        output_file_beats = os.path.join(in_file_path, 'annotations', 'beats' + folders_postfix[mapping_sel],
                                         file_name_wo_ext + ".beats")
    if output_file_drums is None:
        output_file_drums = os.path.join(in_file_path, 'annotations', 'drums' + folders_postfix[mapping_sel],
                                         file_name_wo_ext + ".drums")

    infile = MidiFile(input_file)

    # check events??
    for t_idx in reversed(range(len(infile.tracks))):
        for e_idx in reversed(range(len(infile.tracks[t_idx]))):
            if infile.tracks[t_idx][e_idx].time < 0:
                print('negative time in file %s, in track %d, in event nr %d : %s' % (in_file_name, t_idx, e_idx, str(infile.tracks[t_idx][e_idx])))
                del infile.tracks[t_idx][e_idx]

    bpm = 120  # default tempo
    offset = 0
    only_drums = False
    drum_times = []
    ppq = infile.ticks_per_beat
    midi_tempo = bpm2tempo(bpm)  # = 60 * 1000 * 1000 / bpm
    s_per_tick = midi_tempo / 1000.0 / 1000 / ppq

    # print("Reading midi file '"+input_file+"' ...")
    file_type = infile.type

    tempo_track = []

    track_channels = {}
    # check channels in tracks:
    for track_idx, track in enumerate(infile.tracks):
        track_channels[track_idx] = set()
        for message in track:
            if message.type == 'note_on':
                track_channels[track_idx].add(message.channel)
            
    drum_tracks = [idx for idx in track_channels if 9 in track_channels[idx]]

    if len(drum_tracks) < 1:
        print('no drum track / channel 9 events found for file: '+input_file)
        #todo: check if other tracks (channel 10?) fulfill gm midi drum properties?!
        drum_names = [idx for idx, track in enumerate(infile.tracks) if 'drum' in track.name.lower()]

    max_time = 0
    if parse_and_write:
        for track_idx, track in enumerate(infile.tracks):
            processing_track = None
            is_drum_track = track_idx in drum_tracks or only_drums

            if track_idx != 0 and not is_drum_track:
                continue

            if file_type == 1:
                if track_idx == 0:  # store track 0 as tempo track
                    tempo_track = track
                    continue
                else:
                    # merge tempo track into current track
                    tempo_idx = 0
                    track_msg_idx = 0
                    # copy tracks, because we change the delta times for merging.
                    cur_tempo_track = copy.deepcopy(tempo_track)
                    cur_track = copy.deepcopy(track)
                    processing_track = []
                    while tempo_idx < len(cur_tempo_track) or track_msg_idx < len(cur_track):
                        if tempo_idx >= len(cur_tempo_track):
                            processing_track.append(cur_track[track_msg_idx])
                            track_msg_idx += 1
                            continue
                        if track_msg_idx >= len(cur_track):
                            processing_track.append(cur_tempo_track[tempo_idx])
                            tempo_idx += 1
                            continue
                        if cur_tempo_track[tempo_idx].time <= cur_track[track_msg_idx].time:
                            processing_track.append(cur_tempo_track[tempo_idx])
                            cur_track[track_msg_idx].time -= cur_tempo_track[tempo_idx].time
                            tempo_idx += 1
                        else:
                            processing_track.append(cur_track[track_msg_idx])
                            cur_tempo_track[tempo_idx].time -= cur_track[track_msg_idx].time
                            track_msg_idx += 1
            elif file_type == 0:
                processing_track = track
            else:
                assert file_type == 2
                print("file type 2 detected!! "+input_file)
                exit()
            cur_time = 0
            # at this point we must have a processing track
            assert processing_track is not None and len(processing_track) > 0
            for m_idx, message in enumerate(processing_track):
                delta_tick = message.time
                delta_time = delta_tick * s_per_tick
                cur_time += delta_time
                if cur_time > max_time:  # collect max time for beats if necessary
                    max_time = cur_time

                if message.type == 'set_tempo':
                    midi_tempo = message.tempo
                    s_per_tick = midi_tempo / 1000.0 / 1000 / ppq

                if message.type == 'note_on' and message.velocity > 0:
                    inst_idx = message.note
                    if inst_idx in mapping_dict:
                        inst_idx = mapping_dict[inst_idx]
                    velocity = float(message.velocity) / 127.0  # velocity between 0 and 1
                    if inst_idx is not None and is_drum_track and message.channel == 9 and \
                       MIDI_DRUM_MIN_NOTE <= inst_idx <= MIDI_DRUM_MAX_NOTE:
                        drum_times.append([cur_time, inst_idx, velocity])

        beat_times = calc_beat_times(copy.deepcopy(infile.tracks[0]), max_time, ppq)

        assert len(beat_times) > 0
        if len(drum_times) > 0:
            assert beat_times[-1][0] >= drum_times[-1][0]
        # print("Writing output ...")
        # write beat text file
        beat_times.sort(key=lambda tup: tup[0])
        if write_beats:
            with open(output_file_beats, 'w') as f:
                for entry in beat_times:
                    f.write("%3.5f \t %d\n" % (entry[0]+offset, entry[1]))

        # write drum times
        # sort by time (for multiple tracks)
        drum_times.sort(key=lambda tup: tup[0])
        with open(output_file_drums, 'w') as f:
            for entry in drum_times:
                if add_velocity:
                    f.write("%3.5f \t %d \t %f\n" % (entry[0] + offset, entry[1], entry[2]))
                else:
                    f.write("%3.5f \t %d\n" % (entry[0]+offset, entry[1]))

        drum_tracks.sort(reverse=True)
        out_file_drums = copy.deepcopy(infile)
        for t_idx in reversed(range(len(out_file_drums.tracks))):
            for e_idx in range(len(out_file_drums.tracks[t_idx])):
                event = out_file_drums.tracks[t_idx][e_idx]
                if (event.type == 'note_on' or event.type == 'note_off') and \
                        (event.channel != 9 or MIDI_DRUM_MIN_NOTE > event.note > MIDI_DRUM_MAX_NOTE):
                    out_file_drums.tracks[t_idx][e_idx].velocity = 0
                elif event.type == 'note_on' or event.type == 'note_off':
                    cur_note = out_file_drums.tracks[t_idx][e_idx].note
                    if cur_note in mapping_dict:
                        out_file_drums.tracks[t_idx][e_idx].note = mapping_dict[cur_note]

        out_file_drums.save(output_file_midi_drums)

        # write accompaniment midi
        out_file_accomp = copy.deepcopy(infile)
        if file_type == 1:
            for t_idx in reversed(range(len(out_file_accomp.tracks))):
                for e_idx in range(len(out_file_accomp.tracks[t_idx])):
                    event = out_file_accomp.tracks[t_idx][e_idx]
                    if (event.type == 'note_on' or event.type == 'note_off') and event.channel == 9:
                        out_file_accomp.tracks[t_idx][e_idx].velocity = 0

        out_file_accomp.save(output_file_midi_accomp)

    print("Finished.")


if __name__ == '__main__':

    # add argument parser
    parser = argparse.ArgumentParser(
        description='extract drum track from midi and creates two separate files.')
    parser.add_argument('--infile', '-i', help='input midi file.', required=True)
    parser.add_argument('--mididrumsout', '-o', help='output file name midi drums.', required=True)
    parser.add_argument('--midiaccompout', '-a', help='output file name midi accompaniment.', required=True)
    parser.add_argument('--annotdrumout', '-t', help='output file name annotations drums.', required=True)
    parser.add_argument('--annotbeatout', '-b', help='output file name annotations beats.', required=True)

    args = parser.parse_args()
    #
    in_file = args.infile
    midi_drum_out = args.mididrumsout
    midi_acco_out = args.midiaccompout
    annot_drum_out = args.annotdrumout
    annot_beat_out = args.annotbeatout

    split_midi(in_file, output_file_midi_drums=midi_drum_out, output_file_midi_accomp=midi_acco_out,
               output_file_drums=annot_drum_out, output_file_beats=annot_beat_out)
