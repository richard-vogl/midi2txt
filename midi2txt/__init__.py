

# we use our own bpm2tempo becaus the mido stuff cuts off decimals - which is not good when the bpm tempo is not an int
def bpm2tempo(bpm):
    """Convert beats per minute to MIDI file tempo.

    Returns microseconds per beat as an integer::

        240 => 250000
        120 => 500000
        60 => 1000000
    """
    # One minute is 60 million microseconds.
    return int(round((60.0 * 1000000.0) / bpm))


def tempo2bpm(tempo):
    """Convert MIDI file tempo to BPM.

    Returns BPM as an integer or float::

        250000 => 240
        500000 => 120
        1000000 => 60
    """
    # One minute is 60 million microseconds.
    return (60.0 * 1000000.0) / tempo


def calc_beat_times(track0events, max_time, ppq):
    # write beats with track0 (either only track, or track with tempo and time sig changes).
    beat_times = [[0, 1]]
    cur_time = 0
    beat_time = 0.0
    beat_num = 1
    sub_beat = 0
    time_sig_num = 4
    time_sig_denom = 4
    collected_beat_time = 0
    one_beat_time_at_bpm = 0.5
    bpm = 120
    midi_tempo = bpm2tempo(bpm)  # = 60 * 1000 * 1000 / bpm
    s_per_tick = midi_tempo / 1000.0 / 1000 / ppq
    track0events.append(None)
    for message in track0events:
        if message is not None:
            delta_tick = message.time
            delta_time = delta_tick * s_per_tick
        else:
            delta_time = max_time - cur_time + one_beat_time_at_bpm
            delta_tick = delta_time / s_per_tick
        cur_time += delta_time

        one_beat_time_at_bpm = 60.0 / bpm * 4.0 / time_sig_denom
        sub_beat_incr = delta_time / one_beat_time_at_bpm

        # handle beat writing if we passed a beat with the current increment:
        while sub_beat + sub_beat_incr > 1:  # sub beat is the percent of a beat we did with the delta_times so far
            beat_time = beat_time + collected_beat_time + one_beat_time_at_bpm * (1 - sub_beat)
            sub_beat_incr -= (1 - sub_beat)
            collected_beat_time = 0
            sub_beat = 0

            beat_num = beat_num + 1
            beat_times.append([beat_time, beat_num])
            beat_num = beat_num % time_sig_num

        # add remaining subbeat and time to current
        sub_beat += sub_beat_incr
        collected_beat_time += one_beat_time_at_bpm * sub_beat_incr

        if message is not None and message.type == 'time_signature':
            time_sig_denom = message.denominator
            time_sig_num = message.numerator
        if message is not None and message.type == 'set_tempo':
            midi_tempo = message.tempo
            bpm = tempo2bpm(midi_tempo)
            s_per_tick = midi_tempo / 1000.0 / 1000 / ppq

    return beat_times
