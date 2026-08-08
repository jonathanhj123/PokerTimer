def level(sb, bb, ante=0, minutes=15):
    return {"type": "level", "sb": sb, "bb": bb, "ante": ante, "minutes": minutes}


def brk(minutes=10):
    return {"type": "break", "minutes": minutes}
