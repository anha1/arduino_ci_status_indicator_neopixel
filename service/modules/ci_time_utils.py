import math


def seconds_to_hours(seconds):
    return (float(seconds) / 3600.)

def seconds_to_description(seconds):
    hours = math.floor(seconds / 3600.)
    minutes = math.floor((seconds - 3600 * hours) / 60)
    if hours > 0:
        return '%s h %s m' % (hours, minutes)
    else:
        return '%s m' % (minutes)

def seconds2dict(seconds):
    return {
        'seconds': seconds,
        'description': seconds_to_description(seconds),
    }