

def space_version(*args):
    """\
    Show version of the space-command utility
    """

    import space
    import beyond

    print("Space-Command  {}".format(space.__version__))
    print("Beyond         {}".format(beyond.__version__))
